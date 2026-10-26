# -*- coding: utf-8 -*-
"""
src/main.py
===========
Orquestrador Central e Entrypoint do Pipeline de Ingestão de Dados Multi-Base e Multi-Ano
(`2022` a `2026`) para Auditoria e Predição de Risco de Obras Públicas Federais.

OTIMIZAÇÕES v5 — REENGENHARIA MULTIFORMATO & MULTI-ANO (FEATURE 021):
- Suporte nativo às 5 safras do painel do TCU (`2022`, `2023`, `2024`, `2025`, `2026` ou `--ano todos`).
- Pulo O(1) de obras já concluídas com documentos autênticos (ignorando fichas sintéticas FPDF legadas).
- Cache Cross-Ano O(1): se uma mesma `(base, id_obra)` já teve documentos autênticos coletados em outra safra,
  reutiliza os PDFs validados localmente sem repetir requisições HTTP/SAML externas.
- Priorização automática das obras `Paralisadas / Inacabadas` na fila de coleta (e flag `--apenas-paralisadas`).
- Integração com `PNCPContractsIndex` (Termos Aditivos/Rescisões + Contratos + Compras `.zip`),
  `TransferegovHttpSession` (5 abas internas + `.zip` in-memory + Obrasgov CIPI) e `SISMOB API Pública`.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
import json
from pathlib import Path
import re
import shutil
import sys
import time
from typing import Any

# Garante a raiz do projeto no sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
import requests

from src.config import (
    ANO_BASE,
    ANOS_DISPONIVEIS,
    ANOS_PAINEL_TCU,
    BASE_DRIVE,
    BASES_SUPORTADAS,
    CNPJ_CODEVASF,
    CNPJ_DNIT,
    DEFAULT_HEADERS,
    LIMITE_OBRAS_POR_BASE,
    logger,
    obter_arquivo_log_coleta,
    obter_pasta_base,
    obter_pasta_dados_brutos,
    obter_planilha_origem,
)
from src.extractors import (
    PNCPContractsIndex,
    TransferegovHttpSession,
    coletar_obra_pncp,
    coletar_obra_transferegov,
    coletar_relatorio_codevasf,
    coletar_relatorio_simec,
    coletar_relatorio_sismob,
)
from src.utils import (
    arquivo_ja_existe_valido,
    carregar_chaves_log_existentes,
    carregar_obras_concluidas,
    eh_ficha_sintetica_legada,
    inicializar_log_csv,
    normalizar_coluna,
    validar_e_registrar_pdf,
)

MAX_WORKERS = 10


def _limpar_num_instrumento(val: Any) -> str:
    """Normaliza `num. instrumento`, removendo sufixo `.0` de floats do Excel e valores nulos."""
    if val is None or pd.isna(val):
        return ""
    s = re.sub(r"\.0+$", "", str(val).strip())
    if s.lower() in ("", "nan", "none", "-", "null"):
        return ""
    return s


def _carregar_mapa_instrumentos_cross_ano(
    anos_painel: list[str] = ANOS_PAINEL_TCU,
) -> dict[tuple[str, str], str]:
    """
    Constrói ou lê do cache local o mapeamento `(base_lower, id_obra) -> num_instrumento_limpo`
    a partir das planilhas `data_2022.xlsx`..`data_2026.xlsx`, permitindo preencher o `num. instrumento`
    que veio em branco (`NaN`) para DNIT, SIMEC e FUNASA nas safras antigas (2022–2024).
    """
    arq_cache = ROOT_DIR / "logs" / "cache_mapa_instrumentos_cross_ano.json"
    if arq_cache.exists() and arq_cache.stat().st_size > 100:
        try:
            raw_map = json.loads(arq_cache.read_text(encoding="utf-8"))
            if isinstance(raw_map, dict) and raw_map:
                return {(k.split("|", 1)[0], k.split("|", 1)[1]): v for k, v in raw_map.items() if "|" in k}
        except Exception:
            pass

    mapa: dict[tuple[str, str], str] = {}
    # Varre do mais recente (2026) ao mais antigo (2022) para priorizar instrumentos atualizados
    for ano in reversed(anos_painel):
        plan = obter_planilha_origem(ano)
        if not plan.exists():
            continue
        try:
            df_p = pd.read_excel(plan, dtype=str)
            df_p.columns = [normalizar_coluna(c) for c in df_p.columns]
            if "id" not in df_p.columns or "base de dados" not in df_p.columns or "num. instrumento" not in df_p.columns:
                continue
            for b, i, inst in zip(
                df_p["base de dados"].fillna(""),
                df_p["id"].fillna(""),
                df_p["num. instrumento"].fillna(""),
            ):
                b_c = str(b).strip().lower()
                i_c = str(i).strip()
                inst_c = _limpar_num_instrumento(inst)
                if b_c and i_c and inst_c:
                    mapa.setdefault((b_c, i_c), inst_c)
                    if b_c == "caixa" and len(re.sub(r"\D", "", i_c)) == 8:
                        mapa.setdefault((b_c, i_c[:-2]), inst_c)
        except Exception as exc:
            logger.debug(f"Aviso ao indexar num. instrumento de {plan.name}: {exc}")

    if mapa:
        try:
            arq_cache.parent.mkdir(parents=True, exist_ok=True)
            serializavel = {f"{b}|{i}": v for (b, i), v in mapa.items()}
            arq_cache.write_text(json.dumps(serializavel, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    return mapa


def _obter_fontes_cross_ano(
    base: str,
    id_obra: str,
    num_inst: str,
    indice_cross_ano: dict[tuple[str, str], list[Path]],
) -> list[Path]:
    """
    Busca documentos autênticos já coletados em outros anos por:
    1. `(base, id_obra)` exato;
    2. `(base, id_obra[:-2])` para IDs da CAIXA de 2022 que trazem 2 dígitos verificadores extras;
    3. `(f"{base}:inst", num_inst_limpo)` quando o número do convênio/contrato é idêntico.
    """
    b_l = base.strip().lower()
    id_c = str(id_obra).strip()
    inst_c = _limpar_num_instrumento(num_inst)

    fontes = indice_cross_ano.get((b_l, id_c))
    if fontes:
        return fontes
    if b_l == "caixa" and len(re.sub(r"\D", "", id_c)) == 8:
        fontes = indice_cross_ano.get((b_l, id_c[:-2]))
        if fontes:
            return fontes
    if inst_c:
        fontes = indice_cross_ano.get((f"{b_l}:inst", inst_c))
        if fontes:
            return fontes
        if "/" in inst_c and b_l in ("simec", "funasa", "caixa", "midr"):
            parte_conv = inst_c.split("/")[0].strip()
            if len(re.sub(r"\D", "", parte_conv)) >= 5:
                fontes = indice_cross_ano.get((f"{b_l}:inst", parte_conv))
                if fontes:
                    return fontes
    return []


def _carregar_indice_cross_ano_autentico(
    anos_painel: list[str] = ANOS_PAINEL_TCU,
) -> dict[tuple[str, str], list[Path]]:
    """
    Varre os `log_coleta.csv` das safras existentes no Google Drive e indexa em memória O(1):
    - `(base_lower, id_obra) -> [caminhos_pdfs_autenticos]`
    - `(f"{base_lower}:inst", num_instrumento_limpo) -> [caminhos_pdfs_autenticos]`
    Ignora rigorosamente qualquer ficha sintética legada (`_FichaTecnica_*`, `_Relatorio_Tecnico.pdf`).
    A verificação física (`arquivo_ja_existe_valido`) ocorre sob demanda no momento do reuso.
    """
    indice: dict[tuple[str, str], list[Path]] = {}
    nomes_por_chave: dict[tuple[str, str], set[str]] = {}

    def _adicionar(chave: tuple[str, str], caminho: Path) -> None:
        vistos = nomes_por_chave.setdefault(chave, set())
        if caminho.name not in vistos:
            vistos.add(caminho.name)
            indice.setdefault(chave, []).append(caminho)

    for ano in anos_painel:
        csv_path = obter_arquivo_log_coleta(ano)
        if not csv_path.exists():
            continue
        pasta_brutos = obter_pasta_dados_brutos(ano)
        try:
            with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    status = (row.get("status_validacao") or "").strip().upper()
                    if status not in ("VALIDADO", "VALIDADO_COM_RESSALVAS"):
                        continue
                    nome_arq = (row.get("nome_arquivo") or "").strip()
                    if not nome_arq or eh_ficha_sintetica_legada(nome_arq):
                        continue
                    base = (row.get("base_de_dados") or "").strip().lower()
                    id_obra = (row.get("id_obra") or "").strip()
                    num_inst = _limpar_num_instrumento(row.get("num_instrumento"))
                    if not base or not id_obra:
                        continue
                    caminho_pdf = pasta_brutos / base / nome_arq
                    _adicionar((base, id_obra), caminho_pdf)
                    if base == "caixa" and len(re.sub(r"\D", "", id_obra)) == 8:
                        _adicionar((base, id_obra[:-2]), caminho_pdf)
                    if num_inst:
                        _adicionar((f"{base}:inst", num_inst), caminho_pdf)
                        if "/" in num_inst and base in ("simec", "funasa", "caixa", "midr"):
                            parte_conv = num_inst.split("/")[0].strip()
                            if len(re.sub(r"\D", "", parte_conv)) >= 5:
                                _adicionar((f"{base}:inst", parte_conv), caminho_pdf)
        except Exception as exc:
            logger.debug(f"Aviso ao ler índice cross-ano ({csv_path}): {exc}")
    return indice


def _reutilizar_docs_cross_ano(
    *,
    row: pd.Series,
    base: str,
    base_nome: str,
    pasta_destino: Path,
    caminho_csv: Path,
    cache_log: dict[tuple[str, str, str], str] | set[tuple[str, str, str]],
    indice_cross_ano: dict[tuple[str, str], list[Path]],
) -> list[Path]:
    """
    Se a obra `(base, id_obra)` ou `(base, num_instrumento)` já possuir documentos autênticos
    validados em outro ano-base, copia-os para a partição do ano atual e registra no `log_coleta.csv`.
    """
    id_obra = str(row.get("id", "")).strip()
    num_inst = _limpar_num_instrumento(row.get("num. instrumento", ""))
    emp = str(row.get("empreendimento", "")).strip()

    fontes = _obter_fontes_cross_ano(base, id_obra, num_inst, indice_cross_ano)
    if not fontes:
        return []

    reutilizados: list[Path] = []
    for src_pdf in fontes:
        if not arquivo_ja_existe_valido(src_pdf):
            continue
        dst_pdf = pasta_destino / src_pdf.name
        if not arquivo_ja_existe_valido(dst_pdf):
            try:
                dst_pdf.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_pdf, dst_pdf)
            except Exception:
                continue
        avaliacao = validar_e_registrar_pdf(
            caminho_pdf=dst_pdf,
            base_nome=base_nome,
            id_obra=id_obra,
            num_inst=num_inst,
            emp=emp,
            obs_extra=f"Reuso Cross-Ano O(1) de documento autêntico ({src_pdf.parent.parent.name})",
            cache_log=cache_log,
            caminho_csv=caminho_csv,
        )
        if avaliacao["validation"]["result"] in ("VALIDADO", "VALIDADO_COM_RESSALVAS"):
            reutilizados.append(dst_pdf)

    return reutilizados


def _processar_obra_worker(
    row: pd.Series,
    base: str,
    base_nome: str,
    pasta_destino: Path,
    caminho_csv: Path,
    cache_log: dict[tuple[str, str, str], str] | set[tuple[str, str, str]],
    cache_hashes: dict[str, set[str]],
    http_manager: TransferegovHttpSession | None = None,
    indice_dnit: PNCPContractsIndex | None = None,
    indice_codevasf: PNCPContractsIndex | None = None,
    indice_cross_ano: dict[tuple[str, str], list[Path]] | None = None,
) -> tuple[str, list[Path]]:
    """
    Worker thread-safe para processamento paralelo de uma única obra em qualquer base de dados.
    """
    id_obra = str(row.get("id", "")).strip()
    num_inst = _limpar_num_instrumento(row.get("num. instrumento", ""))
    docs_baixados: list[Path] = []

    try:
        # ─── 0. REUSO CROSS-ANO O(1) DE DOCUMENTOS AUTÊNTICOS ────────────────
        if indice_cross_ano:
            docs_reuso = _reutilizar_docs_cross_ano(
                row=row,
                base=base,
                base_nome=base_nome,
                pasta_destino=pasta_destino,
                caminho_csv=caminho_csv,
                cache_log=cache_log,
                indice_cross_ano=indice_cross_ano,
            )
            if docs_reuso:
                return id_obra, docs_reuso

        # ─── 1. DNIT (API PNCP: Termos + Contrato + Compra Vinculada .zip) ───
        if base == "dnit":
            sess_local = requests.Session()
            sess_local.headers.update(DEFAULT_HEADERS)
            try:
                docs_baixados = coletar_obra_pncp(
                    sess=sess_local,
                    cnpj=CNPJ_DNIT,
                    base_nome=base_nome,
                    ano="",
                    seq="",
                    row=row,
                    pasta_destino=pasta_destino,
                    cache_log=cache_log,
                    cache_hashes=cache_hashes,
                    indice_contratos=indice_dnit,
                    caminho_csv=caminho_csv,
                )
            finally:
                sess_local.close()

        # ─── 2. CODEVASF (API PNCP: Termos + Contrato + Compra .zip) ─────────
        elif base == "codevasf":
            sess_local = requests.Session()
            sess_local.headers.update(DEFAULT_HEADERS)
            try:
                docs_baixados = coletar_obra_pncp(
                    sess=sess_local,
                    cnpj=CNPJ_CODEVASF,
                    base_nome=base_nome,
                    ano="",
                    seq="",
                    row=row,
                    pasta_destino=pasta_destino,
                    cache_log=cache_log,
                    cache_hashes=cache_hashes,
                    indice_contratos=indice_codevasf,
                    caminho_csv=caminho_csv,
                )
                if not docs_baixados:
                    docs_baixados = coletar_relatorio_codevasf(
                        row=row,
                        pasta_destino=pasta_destino,
                        cache_log=cache_log,
                        caminho_csv=caminho_csv,
                        permitir_fallback_sintetico=False,
                    )
            finally:
                sess_local.close()

        # ─── 3. CAIXA & FUNASA (Transferegov 5 Abas + .zip + Obrasgov CIPI) ──
        elif base in ("caixa", "funasa"):
            if http_manager:
                docs_baixados = coletar_obra_transferegov(
                    http_manager=http_manager,
                    base_nome=base_nome,
                    row=row,
                    pasta_destino=pasta_destino,
                    cache_log=cache_log,
                    cache_hashes=cache_hashes,
                    caminho_csv=caminho_csv,
                )

        # ─── 4. SIMEC, SESU, SETEC e SIMEC-Outros (MEC / FNDE) ───────────────
        elif base in ("simec", "sesu", "setec", "simec-outros"):
            parte_conv = num_inst.split("/")[0].strip() if "/" in num_inst else num_inst
            num_limpo = re.sub(r"\D", "", parte_conv)
            if 5 <= len(num_limpo) <= 7 and http_manager:
                docs_baixados = coletar_obra_transferegov(
                    http_manager=http_manager,
                    base_nome=base_nome,
                    row=row,
                    pasta_destino=pasta_destino,
                    cache_log=cache_log,
                    cache_hashes=cache_hashes,
                    caminho_csv=caminho_csv,
                )

            if not docs_baixados:
                docs_baixados = coletar_relatorio_simec(
                    row=row,
                    pasta_destino=pasta_destino,
                    cache_log=cache_log,
                    caminho_csv=caminho_csv,
                    permitir_fallback_sintetico=False,
                )

        # ─── 5. SISMOB (API Pública SISMOB Cidadão — Justificativa Oficial) ──
        elif base == "sismob":
            docs_baixados = coletar_relatorio_sismob(
                row=row,
                pasta_destino=pasta_destino,
                cache_log=cache_log,
                caminho_csv=caminho_csv,
                permitir_fallback_sintetico=False,
            )

        # ─── 6. MIDR (Ministério da Integração e do Desenv. Regional) ────────
        elif base == "midr":
            parte_conv = num_inst.split("/")[0].strip() if "/" in num_inst else num_inst
            num_limpo = re.sub(r"\D", "", parte_conv)
            if 5 <= len(num_limpo) <= 7 and http_manager:
                docs_baixados = coletar_obra_transferegov(
                    http_manager=http_manager,
                    base_nome=base_nome,
                    row=row,
                    pasta_destino=pasta_destino,
                    cache_log=cache_log,
                    cache_hashes=cache_hashes,
                    caminho_csv=caminho_csv,
                )
            if not docs_baixados:
                docs_baixados = coletar_relatorio_codevasf(
                    row=row,
                    pasta_destino=pasta_destino,
                    cache_log=cache_log,
                    caminho_csv=caminho_csv,
                    permitir_fallback_sintetico=False,
                )

        # Se coletou documentos novos, atualiza o índice cross-ano em memória
        if docs_baixados and indice_cross_ano is not None:
            b_l = base.lower()
            indice_cross_ano[(b_l, id_obra)] = list(docs_baixados)
            if b_l == "caixa" and len(re.sub(r"\D", "", id_obra)) == 8:
                indice_cross_ano[(b_l, id_obra[:-2])] = list(docs_baixados)
            if num_inst:
                indice_cross_ano[(f"{b_l}:inst", num_inst)] = list(docs_baixados)

    except Exception as exc:
        emp_curto = str(row.get("empreendimento", ""))[:65]
        logger.debug(f"  [FALHA ISOLADA] Obra {id_obra} ({emp_curto}): {exc}")

    return id_obra, docs_baixados


def executar_pipeline(
    limite_obras_por_base: int | None = LIMITE_OBRAS_POR_BASE,
    bases_alvo: list[str] | None = None,
    ano_base: str = ANO_BASE,
    max_workers: int = MAX_WORKERS,
    apenas_paralisadas: bool = False,
    dry_run: bool = False,
    http_manager_compartilhado: TransferegovHttpSession | None = None,
    indice_dnit_compartilhado: PNCPContractsIndex | None = None,
    indice_codevasf_compartilhado: PNCPContractsIndex | None = None,
    indice_cross_ano: dict[tuple[str, str], list[Path]] | None = None,
    mapa_instrumentos: dict[tuple[str, str], str] | None = None,
) -> dict[str, dict[str, Any]]:
    """
    Executa o pipeline multi-base para um `ano_base` específico (`2022`..`2026`),
    com priorização de obras paralisadas, suporte multiformato, descompactação `.zip` in-memory
    e reuso O(1) de documentos autênticos entre anos.
    """
    planilha_ano = obter_planilha_origem(ano_base)
    pasta_dados_brutos = obter_pasta_dados_brutos(ano_base)
    caminho_log_coleta = obter_arquivo_log_coleta(ano_base)

    logger.info("=" * 80)
    logger.info(f"INICIANDO PIPELINE DE COLETA PROFUNDA v5 — ANO BASE {ano_base}")
    logger.info(
        f"Planilha: {planilha_ano.name} | Concorrência: {max_workers} workers | "
        f"Apenas Paralisadas: {apenas_paralisadas} | Dry-Run: {dry_run}"
    )
    logger.info(f"Destino I/O: Google Drive ({pasta_dados_brutos})")
    logger.info("=" * 80)

    if not planilha_ano.exists():
        logger.error(f"Planilha de origem não encontrada em: {planilha_ano}")
        return {}

    if not dry_run:
        inicializar_log_csv(caminho_log_coleta)
    cache_log = carregar_chaves_log_existentes(caminho_log_coleta)
    cache_concluidas = carregar_obras_concluidas(caminho_log_coleta, ignorar_fichas_sinteticas=True)

    if indice_cross_ano is None:
        indice_cross_ano = _carregar_indice_cross_ano_autentico()
    if mapa_instrumentos is None:
        mapa_instrumentos = _carregar_mapa_instrumentos_cross_ano()

    df = pd.read_excel(planilha_ano, dtype=str)
    df.columns = [normalizar_coluna(c) for c in df.columns]
    # Remove linhas de rodapé ("Total", "Filtros aplicados:")
    df = df[df["id"].notna() & df["base de dados"].notna()].copy()

    # Normaliza `num. instrumento` (remove sufixo `.0` de floats do Excel) e faz backfill cross-ano quando NaN
    if "num. instrumento" in df.columns:
        instrumentos_enriquecidos: list[str] = []
        recuperados_cross = 0
        for b_val, id_val, inst_val in zip(
            df["base de dados"].fillna(""),
            df["id"].fillna(""),
            df["num. instrumento"].fillna(""),
        ):
            inst_limpo = _limpar_num_instrumento(inst_val)
            if not inst_limpo and mapa_instrumentos:
                b_c = str(b_val).strip().lower()
                i_c = str(id_val).strip()
                inst_limpo = mapa_instrumentos.get((b_c, i_c), "")
                if not inst_limpo and b_c == "caixa" and len(re.sub(r"\D", "", i_c)) == 8:
                    inst_limpo = mapa_instrumentos.get((b_c, i_c[:-2]), "")
                if inst_limpo:
                    recuperados_cross += 1
            instrumentos_enriquecidos.append(inst_limpo)
        df["num. instrumento"] = instrumentos_enriquecidos
        if recuperados_cross > 0:
            logger.info(
                f"Enriquecimento Cross-Ano ({ano_base}): {recuperados_cross:,} números de instrumento ausentes "
                "recuperados das safras 2023–2026."
            )

    logger.info(f"Dataset {ano_base} carregado: {len(df):,} obras válidas cadastradas.")

    if apenas_paralisadas:
        mask_par = df["situacao"].astype(str).str.contains(
            r"paralis|inacab|rescind|cancel|suspens", case=False, na=False
        )
        df = df[mask_par].copy()
        logger.info(f"Filtro --apenas-paralisadas ativo: {len(df):,} obras paralisadas/inacabadas selecionadas.")

    bases_para_processar = [b.lower() for b in (bases_alvo or BASES_SUPORTADAS)]

    precisa_transferegov = any(b in ("caixa", "funasa", "simec", "sesu", "setec", "simec-outros", "midr") for b in bases_para_processar)
    http_manager = http_manager_compartilhado
    if precisa_transferegov and http_manager is None and not dry_run:
        http_manager = TransferegovHttpSession()

    indice_dnit = indice_dnit_compartilhado
    if "dnit" in bases_para_processar and indice_dnit is None and not dry_run:
        logger.info("  [PNCP INDEX] Carregando índice de contratos do DNIT (2020-2026)...")
        indice_dnit = PNCPContractsIndex(cnpj=CNPJ_DNIT, anos=[2020, 2021, 2022, 2023, 2024, 2025, 2026])
        logger.info(f"  [PNCP INDEX] {indice_dnit.total_contratos_indexados:,} contratos do DNIT indexados em memória.")

    indice_codevasf = indice_codevasf_compartilhado
    if "codevasf" in bases_para_processar and indice_codevasf is None and not dry_run:
        logger.info("  [PNCP INDEX] Carregando índice de contratos da CODEVASF (2020-2026)...")
        indice_codevasf = PNCPContractsIndex(cnpj=CNPJ_CODEVASF, anos=[2020, 2021, 2022, 2023, 2024, 2025, 2026])
        logger.info(f"  [PNCP INDEX] {indice_codevasf.total_contratos_indexados:,} contratos da CODEVASF indexados.")

    cache_hashes: dict[str, set[str]] = {}
    resumo_coleta: dict[str, dict[str, Any]] = {}

    for base in bases_para_processar:
        base_upper = base.upper()
        pasta_destino = obter_pasta_base(base, ano_base=ano_base) if not dry_run else (pasta_dados_brutos / base)

        sub_df = df[df["base de dados"].astype(str).str.strip().str.lower() == base].copy()
        if sub_df.empty:
            continue

        # Prioriza obras Paralisadas/Inacabadas no início da fila
        sub_df["_prio_paralisada"] = sub_df["situacao"].astype(str).str.contains(
            r"paralis|inacab|rescind|cancel", case=False, na=False
        )
        sub_df = sub_df.sort_values(by="_prio_paralisada", ascending=False)

        total_disponivel = len(sub_df)
        logger.info(f"\n>>> [{ano_base}] PROCESSANDO BASE: {base_upper} (Obras no escopo: {total_disponivel:,})")
        logger.info(f"    Diretório de Destino: {pasta_destino}")

        obras_pendentes: list[tuple[int, pd.Series]] = []
        obras_puladas_cache = 0

        for idx_row, (_, row) in enumerate(sub_df.iterrows(), start=1):
            id_obra = str(row.get("id", "")).strip()
            if (base, id_obra) in cache_concluidas:
                obras_puladas_cache += 1
                continue
            if limite_obras_por_base and len(obras_pendentes) >= limite_obras_por_base:
                break
            obras_pendentes.append((idx_row, row))

        if obras_puladas_cache > 0:
            logger.info(f"    [CACHE O(1)] {obras_puladas_cache:,} obras já com documento autêntico puladas.")

        total_pendentes = len(obras_pendentes)
        logger.info(f"    [PENDENTES] {total_pendentes:,} obras a processar via ThreadPool ({max_workers} workers).")

        if dry_run:
            reusaveis = sum(
                1 for _, r in obras_pendentes
                if _obter_fontes_cross_ano(
                    base,
                    str(r.get("id", "")).strip(),
                    str(r.get("num. instrumento", "")).strip(),
                    indice_cross_ano,
                )
            )
            logger.info(
                f"    [DRY-RUN] {base_upper} ({ano_base}): {total_pendentes:,} pendentes "
                f"({reusaveis:,} disponíveis para reuso cross-ano imediato)."
            )
            resumo_coleta[base_upper] = {
                "ano_base": ano_base,
                "obras_pendentes_dry_run": total_pendentes,
                "obras_reusaveis_cross_ano": reusaveis,
                "obras_puladas_cache": obras_puladas_cache,
                "obras_coletadas": 0,
                "documentos_totais": 0,
            }
            continue

        if total_pendentes == 0:
            resumo_coleta[base_upper] = {
                "ano_base": ano_base,
                "obras_coletadas": 0,
                "obras_puladas_cache": obras_puladas_cache,
                "documentos_totais": 0,
            }
            continue

        obras_com_sucesso = 0
        total_docs_base = 0
        t_inicio_base = time.time()

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    _processar_obra_worker,
                    row=row,
                    base=base,
                    base_nome=base_upper,
                    pasta_destino=pasta_destino,
                    caminho_csv=caminho_log_coleta,
                    cache_log=cache_log,
                    cache_hashes=cache_hashes,
                    http_manager=http_manager,
                    indice_dnit=indice_dnit,
                    indice_codevasf=indice_codevasf,
                    indice_cross_ano=indice_cross_ano,
                ): (idx_row, row)
                for idx_row, row in obras_pendentes
            }

            concluidas_count = 0
            for future in as_completed(futures):
                concluidas_count += 1
                idx_row, row = futures[future]
                id_obra = str(row.get("id", "")).strip()
                try:
                    _, docs_baixados = future.result()
                    if docs_baixados:
                        obras_com_sucesso += 1
                        total_docs_base += len(docs_baixados)
                        logger.info(
                            f"  [SUCESSO {concluidas_count}/{total_pendentes}] "
                            f"[{ano_base} {base_upper}] Obra {id_obra} -> +{len(docs_baixados)} docs autênticos!"
                        )
                    else:
                        if concluidas_count % 25 == 0 or concluidas_count == total_pendentes:
                            elapsed = time.time() - t_inicio_base
                            rate = concluidas_count / elapsed if elapsed > 0 else 0
                            logger.info(
                                f"  [PROGRESSO {ano_base} {base_upper}] "
                                f"{concluidas_count}/{total_pendentes} obras verificadas ({rate:.1f} obras/s)"
                            )
                except Exception as exc:
                    logger.debug(f"  [ERRO] Obra {id_obra}: {exc}")

        tempo_total_base = time.time() - t_inicio_base
        taxa_final = total_pendentes / tempo_total_base if tempo_total_base > 0 else 0
        logger.info(
            f"\n>>> [BASE FINALIZADA: {ano_base} {base_upper}] "
            f"{total_pendentes} obras processadas em {tempo_total_base:.1f}s ({taxa_final:.1f} obras/s) | "
            f"{obras_com_sucesso} obras com documentos | +{total_docs_base} documentos autênticos validados!"
        )

        resumo_coleta[base_upper] = {
            "ano_base": ano_base,
            "obras_coletadas": obras_com_sucesso,
            "obras_puladas_cache": obras_puladas_cache,
            "documentos_totais": total_docs_base,
        }

    logger.info("\n" + "=" * 80)
    logger.info(f"RESUMO DA EXECUÇÃO DE COLETA — ANO-BASE {ano_base}:")
    for base_nome, dados in resumo_coleta.items():
        logger.info(
            f"  - {base_nome:<12}: {dados.get('obras_coletadas', 0)} obras c/ docs | "
            f"{dados.get('obras_puladas_cache', 0)} puladas (cache) | "
            f"{dados.get('documentos_totais', 0)} docs autênticos"
        )
    logger.info("=" * 80)
    return resumo_coleta


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Pipeline Central de MLOps: Ingestão Multiformato Multi-Ano (2022-2026), Parsing/OCR e Higienização."
    )
    parser.add_argument(
        "--modo",
        type=str,
        choices=["coleta", "parsing", "higienizacao", "completo", "completo-full", "schema", "carga", "validar-banco"],
        default="coleta",
        help=(
            "Modo de operação: 'coleta', 'parsing', 'higienizacao', 'completo' "
            "(coleta + parsing), 'completo-full' (ingestao completa), 'schema', 'carga' ou 'validar-banco'."
        ),
    )
    parser.add_argument(
        "--ano",
        type=str,
        default=None,
        help=(
            "Ano-base do painel (2022, 2023, 2024, 2025, 2026 ou 'todos' para processar 2022-2026 em sequência)."
        ),
    )
    parser.add_argument(
        "--base",
        type=str,
        default=None,
        help="Filtrar por base específica (ex: dnit, caixa, funasa, codevasf, sismob, simec).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=MAX_WORKERS,
        help=f"Número de threads para concorrência paralela. Padrão: {MAX_WORKERS}",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limite de obras/arquivos a processar por base (ideal para testes).",
    )
    parser.add_argument(
        "--apenas-paralisadas",
        action="store_true",
        help="No modo coleta, filtra exclusivamente obras com situação Paralisada/Inacabada.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula sem alterar fontes/banco; lista obras pendentes e reuso cross-ano.",
    )
    parser.add_argument(
        "--force-ocr",
        action="store_true",
        help="No modo parsing, força OCR em todas as páginas dos PDFs.",
    )
    parser.add_argument(
        "--excluir-quarentena",
        action="store_true",
        help="Em carga, autoriza somente o lote elegivel apos revisar a destinacao das quarentenas; nao as inclui.",
    )
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        help="No modo higienizacao, mantém apenas a Camada 1 determinística.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reprocessa higienizacao ou substitui transacionalmente documentos alterados na carga.",
    )

    args = parser.parse_args()

    if args.modo == "schema":
        if args.dry_run:
            parser.error("Use --modo carga --dry-run para preflight; schema aplica o DDL.")
        import json
        from src.database.schema import apply_schema
        print(json.dumps(apply_schema(), ensure_ascii=False))
        return 0
    if args.modo == "validar-banco":
        import json
        from src.database.connection import connect
        from src.database.validation import validate_data
        with connect() as conn:
            conn.read_only = True
            with conn.transaction():
                result = validate_data(conn)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result["valido"] else 1
    if args.modo == "carga":
        from src.database.run_load import run_load
        if args.ano and args.ano.strip().lower() == "todos":
            for ano_item in ANOS_PAINEL_TCU:
                run_load(ano_item, args.base, args.limit, args.dry_run, args.force,
                         exclude_quarantine=args.excluir_quarentena)
            return 0
        result = run_load(args.ano, args.base, args.limit, args.dry_run, args.force,
                          exclude_quarantine=args.excluir_quarentena)
        return 2 if result["status"] == "PARCIAL" or result.get("prontidao") == "BLOQUEADO" else 0

    anos_operacao = (
        list(ANOS_PAINEL_TCU)
        if (args.ano and args.ano.strip().lower() == "todos")
        else [args.ano or ANO_BASE]
    )

    # 1. Executa Coleta Profunda Multiformato
    if args.modo in ("coleta", "completo", "completo-full"):
        bases_alvo = [b.strip().lower() for b in args.base.split(",") if b.strip()] if args.base else None
        indice_cross = _carregar_indice_cross_ano_autentico()
        mapa_inst = _carregar_mapa_instrumentos_cross_ano()
        http_mgr = None
        ind_dnit = None
        ind_codevasf = None

        if not args.dry_run:
            precisa_transf = any(
                b in ("caixa", "funasa", "simec", "sesu", "setec", "simec-outros", "midr")
                for b in (bases_alvo or BASES_SUPORTADAS)
            )
            if precisa_transf:
                try:
                    logger.info("  [TRANSFEREGOV] Inicializando gerenciador compartilhado de sessão com Selenium...")
                    http_mgr = TransferegovHttpSession()
                except Exception as exc:
                    logger.warning(f"Não foi possível pré-iniciar TransferegovHttpSession: {exc}")

            if not bases_alvo or "dnit" in bases_alvo:
                try:
                    logger.info("  [PNCP INDEX] Carregando índice compartilhado de contratos do DNIT (2020-2026)...")
                    ind_dnit = PNCPContractsIndex(cnpj=CNPJ_DNIT, anos=[2020, 2021, 2022, 2023, 2024, 2025, 2026])
                    logger.info(f"  [PNCP INDEX] {ind_dnit.total_contratos_indexados:,} contratos do DNIT indexados em memória.")
                except Exception as exc:
                    logger.warning(f"Não foi possível pré-carregar índice DNIT: {exc}")

            if not bases_alvo or "codevasf" in bases_alvo:
                try:
                    logger.info("  [PNCP INDEX] Carregando índice compartilhado de contratos da CODEVASF (2020-2026)...")
                    ind_codevasf = PNCPContractsIndex(cnpj=CNPJ_CODEVASF, anos=[2020, 2021, 2022, 2023, 2024, 2025, 2026])
                    logger.info(f"  [PNCP INDEX] {ind_codevasf.total_contratos_indexados:,} contratos da CODEVASF indexados em memória.")
                except Exception as exc:
                    logger.warning(f"Não foi possível pré-carregar índice CODEVASF: {exc}")

        for ano_op in anos_operacao:
            logger.info(f"\n[ENTRYPOINT] Disparando Módulo de Coleta Profunda Multiformato (Ano: {ano_op})...")
            executar_pipeline(
                limite_obras_por_base=args.limit,
                bases_alvo=bases_alvo,
                ano_base=ano_op,
                max_workers=args.workers,
                apenas_paralisadas=args.apenas_paralisadas,
                dry_run=args.dry_run,
                http_manager_compartilhado=http_mgr,
                indice_dnit_compartilhado=ind_dnit,
                indice_codevasf_compartilhado=ind_codevasf,
                indice_cross_ano=indice_cross,
                mapa_instrumentos=mapa_inst,
            )

    # 2. Executa Parsing e OCR
    if args.modo in ("parsing", "completo", "completo-full"):
        from src.parsers.run_extraction import executar_pipeline_extracao

        for ano_op in anos_operacao:
            logger.info(f"\n[ENTRYPOINT] Disparando Módulo de Parsing de Texto & OCR (Ano: {ano_op})...")
            executar_pipeline_extracao(
                ano_base=ano_op,
                base_especifica=args.base,
                max_workers=args.workers,
                limite=args.limit,
                dry_run=args.dry_run,
                forcar_ocr=args.force_ocr,
            )

    # 3. Executa Higienização NLP
    if args.modo in ("higienizacao", "completo-full"):
        from src.parsers.run_higienizacao import executar_pipeline_higienizacao

        if args.ano and args.ano.strip().lower() == "todos":
            for ano_op in ANOS_PAINEL_TCU:
                executar_pipeline_higienizacao(
                    ano_base=ano_op,
                    base_especifica=args.base,
                    max_workers=args.workers,
                    limite=args.limit,
                    dry_run=args.dry_run,
                    skip_llm=args.skip_llm,
                    force=args.force,
                )
        else:
            executar_pipeline_higienizacao(
                ano_base=args.ano,
                base_especifica=args.base,
                max_workers=args.workers,
                limite=args.limit,
                dry_run=args.dry_run,
                skip_llm=args.skip_llm,
                force=args.force,
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())
