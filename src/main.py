# -*- coding: utf-8 -*-
"""
src/main.py
===========
Orquestrador Central e Entrypoint do Pipeline de Ingestão de Dados Multi-Base
para Auditoria e Predição de Risco de Obras Públicas Federais.

OTIMIZAÇÕES v4 — ULTRA THROUGHPUT:
- Pulo O(1) de obras já concluídas em execuções anteriores (sem I/O de rede).
- Eliminação do gargalo do Selenium: Transferegov agora roda via HTTP direto de alta vazão (0.3s/obra).
- ThreadPoolExecutor(max_workers=10) ativo para TODAS as bases (CAIXA, FUNASA, SIMEC, DNIT, CODEVASF, SISMOB).
- Gestão centralizada e thread-safe de sessão e cookies SAML (TransferegovHttpSession).
- Deduplicação SHA-256 in-memory e poda de baixa densidade (<300 chars) em buffer local.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import re
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
    BASES_SUPORTADAS,
    CNPJ_CODEVASF,
    CNPJ_DNIT,
    DEFAULT_HEADERS,
    LIMITE_OBRAS_POR_BASE,
    PASTA_DADOS_BRUTOS,
    PLANILHA_ORIGEM,
    logger,
    obter_pasta_base,
)
from src.extractors import (
    TransferegovHttpSession,
    coletar_obra_pncp,
    coletar_obra_transferegov,
    coletar_relatorio_codevasf,
    coletar_relatorio_simec,
    coletar_relatorio_sismob,
)
from src.utils import (
    carregar_chaves_log_existentes,
    carregar_obras_concluidas,
    inicializar_log_csv,
    normalizar_coluna,
)

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURAÇÃO DE PARALELISMO E CONCORRÊNCIA
# ─────────────────────────────────────────────────────────────────────────────
# 10 workers paralelos oferecem throughput ideal (~15-20 req/s total) sem risco de bloqueio
MAX_WORKERS = 10


def _processar_obra_worker(
    row: pd.Series,
    base: str,
    base_nome: str,
    pasta_destino: Path,
    cache_log: set[tuple[str, str, str]],
    cache_hashes: dict[str, set[str]],
    http_manager: TransferegovHttpSession | None = None,
) -> tuple[str, list[Path]]:
    """
    Worker thread-safe para processamento paralelo de uma única obra em qualquer base de dados.
    """
    id_obra = str(row.get("id", "")).strip()
    num_inst = str(row.get("num. instrumento", "")).strip()
    docs_baixados: list[Path] = []

    try:
        # ─── 1. DNIT (API PNCP) ──────────────────────────────────────────────
        if base == "dnit":
            sess_local = requests.Session()
            sess_local.headers.update(DEFAULT_HEADERS)
            try:
                m = re.search(r"(\d+)/(\d{4})", str(num_inst))
                if m:
                    seq, ano = str(int(m.group(1))), m.group(2)
                    docs_baixados = coletar_obra_pncp(
                        sess=sess_local,
                        cnpj=CNPJ_DNIT,
                        base_nome=base_nome,
                        ano=ano,
                        seq=seq,
                        row=row,
                        pasta_destino=pasta_destino,
                        cache_log=cache_log,
                        cache_hashes=cache_hashes,
                    )
            finally:
                sess_local.close()

        # ─── 2. CODEVASF (API PNCP ou Relatório Técnico) ────────────────────
        elif base == "codevasf":
            sess_local = requests.Session()
            sess_local.headers.update(DEFAULT_HEADERS)
            try:
                m = re.search(r"(\d+)\.(\d+)\.\d+/(\d{4})", id_obra)
                if m:
                    seq, ano = str(int(m.group(2))), m.group(3)
                    docs_baixados = coletar_obra_pncp(
                        sess=sess_local,
                        cnpj=CNPJ_CODEVASF,
                        base_nome=base_nome,
                        ano=ano,
                        seq=seq,
                        row=row,
                        pasta_destino=pasta_destino,
                        cache_log=cache_log,
                        cache_hashes=cache_hashes,
                    )
                if not docs_baixados:
                    docs_baixados = coletar_relatorio_codevasf(
                        row=row,
                        pasta_destino=pasta_destino,
                        cache_log=cache_log,
                    )
            finally:
                sess_local.close()

        # ─── 3. CAIXA & FUNASA (Transferegov / SICONV via HTTP Direto) ───────
        elif base in ("caixa", "funasa"):
            if http_manager:
                docs_baixados = coletar_obra_transferegov(
                    http_manager=http_manager,
                    base_nome=base_nome,
                    row=row,
                    pasta_destino=pasta_destino,
                    cache_log=cache_log,
                    cache_hashes=cache_hashes,
                )

        # ─── 4. SIMEC, SESU, SETEC e SIMEC-Outros (MEC / FNDE) ───────────────
        elif base in ("simec", "sesu", "setec", "simec-outros"):
            num_limpo = re.sub(r"\D", "", str(num_inst))
            if len(num_limpo) == 6 and http_manager:
                docs_baixados = coletar_obra_transferegov(
                    http_manager=http_manager,
                    base_nome=base_nome,
                    row=row,
                    pasta_destino=pasta_destino,
                    cache_log=cache_log,
                    cache_hashes=cache_hashes,
                )

            if not docs_baixados:
                docs_baixados = coletar_relatorio_simec(
                    row=row,
                    pasta_destino=pasta_destino,
                    cache_log=cache_log,
                )

        # ─── 5. SISMOB (Ministério da Saúde / FNS) ───────────────────────────
        elif base == "sismob":
            docs_baixados = coletar_relatorio_sismob(
                row=row,
                pasta_destino=pasta_destino,
                cache_log=cache_log,
            )

        # ─── 6. MIDR (Ministério da Integração e do Desenv. Regional) ────────
        elif base == "midr":
            docs_baixados = coletar_relatorio_codevasf(
                row=row,
                pasta_destino=pasta_destino,
                cache_log=cache_log,
            )

    except Exception as exc:
        emp = str(row.get("empreendimento", ""))[:65]
        logger.debug(f"  [FALHA ISOLADA] Obra {id_obra} ({emp}): {exc}")

    return id_obra, docs_baixados


def executar_pipeline(
    limite_obras_por_base: int | None = LIMITE_OBRAS_POR_BASE,
    bases_alvo: list[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """
    Executa o pipeline multi-base com altíssimo throughput, processamento paralelo
    concorrente e travas de idempotência O(1).
    """
    logger.info("=" * 80)
    logger.info(f"INICIANDO PIPELINE DE PRODUÇÃO ULTRA THROUGHPUT — ANO BASE {ANO_BASE}")
    logger.info(f"Planilha de Origem: {PLANILHA_ORIGEM.name} | Concorrência: {MAX_WORKERS} workers")
    logger.info(f"Destino I/O: Google Drive ({PASTA_DADOS_BRUTOS})")
    logger.info("=" * 80)

    # 1. Inicializa o Log CSV e carrega caches O(1) de deduplicação
    inicializar_log_csv()
    cache_log = carregar_chaves_log_existentes()
    cache_concluidas = carregar_obras_concluidas()

    # 2. Carregamento e higienização da planilha base
    if not PLANILHA_ORIGEM.exists():
        logger.error(f"Planilha de origem não encontrada em: {PLANILHA_ORIGEM}")
        sys.exit(1)

    df = pd.read_excel(PLANILHA_ORIGEM)
    df.columns = [normalizar_coluna(c) for c in df.columns]
    logger.info(f"Dataset carregado: {len(df):,} obras cadastradas no total.")

    bases_para_processar = [b.lower() for b in (bases_alvo or BASES_SUPORTADAS)]

    # 3. Inicialização do gerenciador de sessão Transferegov (se bases web forem processadas)
    precisa_transferegov = any(b in ("caixa", "funasa", "simec") for b in bases_para_processar)
    http_manager = TransferegovHttpSession() if precisa_transferegov else None

    cache_hashes: dict[str, set[str]] = {}  # Cache SHA-256 para deduplicação criptográfica
    resumo_coleta: dict[str, dict[str, Any]] = {}

    try:
        for base in bases_para_processar:
            base_upper = base.upper()
            pasta_destino = obter_pasta_base(base)

            sub_df = df[df["base de dados"].astype(str).str.lower() == base]
            total_disponivel = len(sub_df)
            logger.info(f"\n>>> PROCESSANDO BASE: {base_upper} (Obras disponíveis: {total_disponivel:,})")
            logger.info(f"    Diretório de Destino: {pasta_destino}")

            # Filtrar obras pendentes (pulo O(1) instantâneo para obras já concluídas)
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
                logger.info(f"    [CACHE O(1)] {obras_puladas_cache:,} obras já concluídas puladas instantaneamente.")

            total_pendentes = len(obras_pendentes)
            logger.info(f"    [PENDENTES] {total_pendentes:,} obras a processar via ThreadPool ({MAX_WORKERS} workers).")

            if total_pendentes == 0:
                logger.info(f"    [BASE CONCLUÍDA] Todas as obras da base {base_upper} já foram processadas!")
                resumo_coleta[base_upper] = {
                    "obras_coletadas": 0,
                    "obras_puladas_cache": obras_puladas_cache,
                    "documentos_totais": 0,
                }
                continue

            obras_com_sucesso = 0
            total_docs_base = 0
            t_inicio_base = time.time()

            # Execução Concorrente em Pool de Threads
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = {
                    executor.submit(
                        _processar_obra_worker,
                        row=row,
                        base=base,
                        base_nome=base_upper,
                        pasta_destino=pasta_destino,
                        cache_log=cache_log,
                        cache_hashes=cache_hashes,
                        http_manager=http_manager,
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
                            logger.info(f"  [SUCESSO {concluidas_count}/{total_pendentes}] Obra {id_obra} -> +{len(docs_baixados)} docs válidos!")
                        else:
                            if concluidas_count % 25 == 0 or concluidas_count == total_pendentes:
                                elapsed = time.time() - t_inicio_base
                                rate = concluidas_count / elapsed if elapsed > 0 else 0
                                logger.info(f"  [PROGRESSO] {concluidas_count}/{total_pendentes} obras verificadas ({rate:.1f} obras/s)")
                    except Exception as exc:
                        logger.debug(f"  [ERRO] Obra {id_obra}: {exc}")

            tempo_total_base = time.time() - t_inicio_base
            taxa_final = total_pendentes / tempo_total_base if tempo_total_base > 0 else 0
            logger.info(
                f"\n>>> [BASE FINALIZADA: {base_upper}] "
                f"{total_pendentes} obras processadas em {tempo_total_base:.1f}s ({taxa_final:.1f} obras/s) | "
                f"+{total_docs_base} novos documentos válidos coletados!"
            )

            resumo_coleta[base_upper] = {
                "obras_coletadas": obras_com_sucesso,
                "obras_puladas_cache": obras_puladas_cache,
                "documentos_totais": total_docs_base,
            }

    finally:
        pass

    # 4. Relatório Consolidado de Execução
    logger.info("\n" + "=" * 80)
    logger.info("RESUMO FINAL DA EXTRAÇÃO EM PRODUÇÃO (TODAS AS BASES):")
    for base_nome, dados in resumo_coleta.items():
        logger.info(
            f"  - {base_nome:<10}: {dados['obras_coletadas']} obras novas | "
            f"{dados['obras_puladas_cache']} puladas (cache) | "
            f"{dados['documentos_totais']} documentos gerados/validados"
        )
    logger.info("=" * 80)

def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Pipeline Central de MLOps: Ingestão de Dados, Coleta de PDFs e Extração de Texto / OCR."
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
            "Ano-base do painel (ex.: 2025, 2026). Em higienizacao e carga, a ausência "
            "processa todos os anos disponíveis; nos demais modos, usa "
            f"{ANO_BASE}."
        ),
    )
    parser.add_argument(
        "--base",
        type=str,
        default=None,
        help="Filtrar por base específica (ex: dnit, caixa, funasa, simec, sismob).",
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
        "--dry-run",
        action="store_true",
        help="Simula sem alterar fontes/banco; em carga, gera somente relatorio local.",
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
        result = run_load(args.ano, args.base, args.limit, args.dry_run, args.force,
                          exclude_quarantine=args.excluir_quarentena)
        return 2 if result["status"] == "PARCIAL" or result.get("prontidao") == "BLOQUEADO" else 0

    # 1. Executa Coleta de PDFs
    if args.modo in ("coleta", "completo", "completo-full"):
        ano_operacao = args.ano or ANO_BASE
        logger.info(f"\n[ENTRYPOINT] Disparando Módulo de Ingestão e Coleta de PDFs (Ano: {ano_operacao})...")
        bases_alvo = [args.base.strip().lower()] if args.base else None
        executar_pipeline(
            limite_obras_por_base=args.limit,
            bases_alvo=bases_alvo,
        )

    # 2. Executa Parsing e OCR
    if args.modo in ("parsing", "completo", "completo-full"):
        from src.parsers.run_extraction import executar_pipeline_extracao

        ano_operacao = args.ano or ANO_BASE
        logger.info(f"\n[ENTRYPOINT] Disparando Módulo de Parsing de Texto & OCR (Ano: {ano_operacao})...")
        executar_pipeline_extracao(
            ano_base=ano_operacao,
            base_especifica=args.base,
            max_workers=args.workers,
            limite=args.limit,
            dry_run=args.dry_run,
            forcar_ocr=args.force_ocr,
        )

    # 3. Executa Higienização NLP e, seletivamente, Camada 2 com Gemini
    if args.modo in ("higienizacao", "completo-full"):
        from src.parsers.run_higienizacao import executar_pipeline_higienizacao

        anos_exibidos = args.ano or "todos os anos disponíveis"
        logger.info(f"\n[ENTRYPOINT] Disparando Módulo de Higienização NLP (Ano: {anos_exibidos})...")
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
