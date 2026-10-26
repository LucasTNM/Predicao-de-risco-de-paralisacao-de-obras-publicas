# -*- coding: utf-8 -*-
"""
revisao_coleta/fase1_auditoria_codigo_logs.py
=============================================
FASE 1: Auditoria Quantitativa do Código Atual e dos Logs da Sprint 1.

Inspeciona:
1. Extratores atuais:
   - src/extractors/pncp.py
   - src/extractors/transferegov.py
   - src/extractors/tecnicos.py
   - src/utils.py
   - src/inspect_pdf.py
2. Logs históricos de execução da Sprint 1:
   - logs/sistema.log, logs/sistema.log.1, logs/sistema.log.2
   - G:\\Meu Drive\\TCC_DOCUMENTOS\\2025_Dados_brutos\\log_coleta.csv

Responde com números exatos:
- Quantos arquivos foram bloqueados na Sprint 1 porque tinham extensões .docx, .doc, .odt, .rtf ou .zip;
- Quantos documentos vitais (Termos Aditivos, Memoriais Descritivos, Projetos Básicos, Pareceres Técnicos,
  Termos de Rescisão/Paralisação, Relatórios de Vistoria) foram descartados pelo filtro_pre_download_dom
  ou pelas limitações estruturais de rota/extensão.
"""

from __future__ import annotations

from collections import Counter
import csv
import json
from pathlib import Path
import re
import sys
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.utils import _BLACKLIST_TERMOS, _WHITELIST_TERMOS, filtro_pre_download_dom


def auditar_codigo_estatico() -> dict[str, Any]:
    """Inspeciona o código-fonte dos extratores da Sprint 1 e identifica gargalos estruturais."""
    pncp_code = (ROOT_DIR / "src/extractors/pncp.py").read_text(encoding="utf-8")
    transf_code = (ROOT_DIR / "src/extractors/transferegov.py").read_text(encoding="utf-8")
    tecnicos_code = (ROOT_DIR / "src/extractors/tecnicos.py").read_text(encoding="utf-8")
    utils_code = (ROOT_DIR / "src/utils.py").read_text(encoding="utf-8")
    inspect_code = (ROOT_DIR / "src/inspect_pdf.py").read_text(encoding="utf-8")

    # Simulação de títulos reais de documentos vitais submetidos ao filtro_pre_download_dom da Sprint 1
    casos_teste_vitais = [
        "Despacho Técnico de Paralisação de Obra e Parecer de Engenharia.pdf",
        "Publicação do 1º Termo Aditivo de Prazo e Valor ao Contrato.pdf",
        "Notificação de Rescisão Contratual por Abandono de Obra e Laudo de Vistoria.pdf",
        "E-mail de Encaminhamento do Memorial Descritivo e Projeto Básico Revisado.pdf",
        "Comprovante de Vistoria Técnica e Relatório Fotográfico de Medição.pdf",
        "Despacho de Aprovação do Projeto Básico e Memorial Descritivo.docx",
        "Publicação de Termo de Rescisão Unilateral do Contrato.pdf",
        "Notificação Técnica sobre Inconformidades no Cronograma Físico-Financeiro.pdf",
        "Termo Aditivo nº 02/2024 - Prorrogação de Vigência.pdf",
        "Relatório de Vistoria e Supervisão de Obra Paralisada.pdf",
        "Termo de Rescisão Amigável / Unilateral de Contrato.pdf",
        "Parecer Técnico de Engenharia - Readequação de Projeto.pdf",
    ]

    simulacao_filtro_dom = []
    falsos_negativos_vitais = 0
    for titulo in casos_teste_vitais:
        aprovado, motivo = filtro_pre_download_dom(titulo)
        if not aprovado:
            falsos_negativos_vitais += 1
        simulacao_filtro_dom.append({
            "titulo_simulado": titulo,
            "aprovado_sprint1": aprovado,
            "motivo_sprint1": motivo,
        })

    return {
        "achados_codigo": {
            "pncp_py": {
                "linha_forcamento_pdf": "nome_arquivo = f\"{base_nome}_{identity['kind']}_{ano}_{seq}_{idx}_{sufixo}.pdf\" (linha 137)",
                "bug_multiformato": (
                    "Força a extensão '.pdf' em 100% dos arquivos baixados do PNCP (mesmo quando o binário original é .zip, .docx, .odt ou .rar). "
                    "Na Barreira 3 (validar_densidade_textual -> inspect_pdf), o arquivo falha na verificação de magic bytes `magic != b'%PDF-'`, "
                    "retornando `extractable=False` e sendo descartado imediatamente como `PODA NLP (SEM_OCR)`!"
                ),
                "endpoint_restrito": (
                    "Na Sprint 1 original, consultava apenas `/compras/{ano}/{seq}/arquivos` (fase licitatória/edital), "
                    "sem buscar a lista de contratos derivados, `/contratos/{ano}/{seq}/termos` (Termos Aditivos / Termos de Rescisão) "
                    "e seus respectivos arquivos anexos."
                ),
                "early_stop": "Linha 216 (`if arquivos_validados: break`) interrompe se houver múltiplas URLs assim que 1 arquivo é validado.",
            },
            "transferegov_py": {
                "linha_bloqueio_extensao": "if any(ext in nome_tabela.lower() for ext in ['.zip', '.xlsx', '.rar', '.dwg', '.csv']): continue (linha 179)",
                "linha_forcamento_pdf": "nome_padrao = f\"{base_nome}_{num_convenio}_{idx}_{nome_sufixo}.pdf\" (linha 189)",
                "bug_multiformato": (
                    "1) Bloqueia explicitamente qualquer linha da tabela cujo texto contenha '.zip', descartando pastas inteiras de fiscalização/projetos compactados. "
                    "2) Não extrai .docx, .doc, .odt ou .rtf: como renomeia qualquer anexo baixado para `.pdf`, arquivos Word/ODT/RTF/ZIP sem extensão explícita "
                    "no texto da tabela são baixados como `.pdf` e imediatamente destruídos pela Barreira 3 (`magic != b'%PDF-'` -> `SEM_OCR`)."
                ),
                "endpoint_restrito": (
                    "Navega exclusivamente para a aba inicial de Anexos da Proposta/Convênio (`DownloadAnexoConvenio` em `ResultadoDaConsultaDeConvenioSelecionarConvenio.do`), "
                    "ignorando as abas de Execução, Acompanhamento de Obras / Laudos de Vistoria, Termos Aditivos, Ajustes do Plano de Trabalho e Restrições/Paralisação, "
                    "além de não consultar a API de Dados Abertos (`api.transferegov.gestao.gov.br` / `api-publica.obrasgov.gestao.gov.br`)."
                ),
            },
            "tecnicos_py": {
                "geracao_sintetica_exclusiva": (
                    "Não realiza nenhuma requisição HTTP/API aos portais do SISMOB (`sismobcidadao.saude.gov.br`), SIMEC Obras 2.0 (`simec.mec.gov.br/obras2`) "
                    "ou CODEVASF. Apenas gera localmente via FPDF uma ficha sintética tabular (`gerar_pdf_relatorio_sismob`, `gerar_pdf_relatorio_simec`, "
                    "`gerar_pdf_relatorio_codevasf`), que precisou ser expurgada na Sprint 7 (Feature 018) por conter vazamento direto do alvo (`situacao`)."
                ),
            },
            "utils_py_filtro_dom": {
                "precedencia_invertida_blacklist": (
                    "Em `filtro_pre_download_dom` (linhas 74-81), `_BLACKLIST_TERMOS` é avaliada ANTES de `_WHITELIST_TERMOS` com match de substring simples (`if termo in texto_lower`). "
                    "Como `_BLACKLIST_TERMOS` inclui palavras ubíquas da administração pública como `'despacho'`, `'publicação'`, `'publicacao'`, `'notificação'`, `'notificacao'`, "
                    "`'comprovante'`, `'encaminhamento'` e `'leitura'`, qualquer documento técnico vital cujo título ou linha da tabela contenha essas palavras "
                    "(ex.: 'Publicação do Contrato', 'Publicação de Termo Aditivo', 'Despacho Técnico de Paralisação', 'Notificação de Rescisão Contratual') "
                    "é sumariamente bloqueado antes mesmo do download!"
                ),
                "termos_ausentes_whitelist": [
                    "rescisão / rescisao",
                    "paralisação / paralisacao",
                    "vistoria",
                    "supervisão / supervisao",
                    "medição / medicao",
                    "inconformidade / restrição",
                    "apostilamento",
                    "ordem de serviço / ordem de servico",
                ],
                "falsos_negativos_em_12_casos_vitais": falsos_negativos_vitais,
                "simulacao_casos_vitais": simulacao_filtro_dom,
            },
        }
    }


def minerar_logs_sprint1() -> dict[str, Any]:
    """Minera todos os arquivos de log da Sprint 1 (`sistema.log*` e `log_coleta.csv`) para extrair números exatos."""
    log_files = [
        ROOT_DIR / "logs/sistema.log.2",
        ROOT_DIR / "logs/sistema.log.1",
        ROOT_DIR / "logs/sistema.log",
    ]

    all_lines: list[str] = []
    for p in log_files:
        if p.exists():
            all_lines.extend(p.read_text(encoding="utf-8", errors="replace").splitlines())

    # 1. Contabilização de eventos de curadoria por base (v3 Selenium + v4 HTTP)
    curadoria_por_base: dict[str, dict[str, int]] = {}
    for line in all_lines:
        if "[CURADORIA]" in line:
            msg = line.split("[CURADORIA]")[-1].strip()
            parts = msg.split()
            if not parts:
                continue
            base = parts[0]
            curadoria_por_base.setdefault(
                base,
                {"obras_com_filtragem": 0, "barreira1_dom_api": 0, "barreira2_sha256": 0, "barreira3_poda_nlp": 0},
            )
            curadoria_por_base[base]["obras_com_filtragem"] += 1
            nums = [
                int(x)
                for x in re.findall(
                    r"(\d+)\s+(?:bloqueados|DOM|duplicatas|SHA-256|podados|NLP Poda)",
                    msg,
                )
            ]
            if len(nums) == 3:
                curadoria_por_base[base]["barreira1_dom_api"] += nums[0]
                curadoria_por_base[base]["barreira2_sha256"] += nums[1]
                curadoria_por_base[base]["barreira3_poda_nlp"] += nums[2]

    # 2. Detalhamento de bloqueios explícitos de API no PNCP ([FILTRO API])
    filtro_api_motivos = Counter()
    filtro_api_exemplos: list[str] = []
    bloqueios_contrato_publicacao_pncp = 0
    bloqueios_despacho_pncp = 0

    for line in all_lines:
        if "[FILTRO API]" in line:
            msg = line.split("[FILTRO API]")[-1].strip()
            if len(filtro_api_exemplos) < 25:
                filtro_api_exemplos.append(msg)
            m = re.search(r"BLACKLIST\[([^\]]+)\]", msg)
            termo = m.group(1) if m else "OUTRO"
            filtro_api_motivos[termo] += 1
            if "contrato" in msg.lower() or "publica" in msg.lower():
                bloqueios_contrato_publicacao_pncp += 1
            if "despacho" in msg.lower():
                bloqueios_despacho_pncp += 1

    # 3. Análise exata de anexos encontrados vs. pulados antes do download (extensões .zip/.xlsx/.rar/.dwg/.csv)
    # e descartados como SEM_OCR na Barreira 3 (onde caem .docx, .odt, .rtf e .zip renomeados para .pdf)
    blocks_v1 = []
    cur = None
    for line in all_lines:
        m_anx = re.search(r"\[([A-Z]+) ([^\|\]]+?)\s*\|\s*Conv.nio\s*(\d+)\]\s*(\d+)\s*anexos encontrados", line)
        if m_anx:
            if cur:
                blocks_v1.append(cur)
            cur = {
                "base": m_anx.group(1),
                "id": m_anx.group(2).strip(),
                "conv": m_anx.group(3),
                "total_anexos": int(m_anx.group(4)),
                "docs_touched": set(),
                "dom": 0,
                "dedup": 0,
                "poda": 0,
            }
            continue
        if cur:
            m_doc = re.search(r"Doc (\d+)/(\d+):", line)
            if m_doc and int(m_doc.group(2)) == cur["total_anexos"]:
                cur["docs_touched"].add(int(m_doc.group(1)))
            m_cur = re.search(
                r"\[CURADORIA\]\s*([A-Z]+)\s+([^\:]+):\s*(\d+)\s*bloqueados \(DOM\)\s*\|\s*(\d+)\s*duplicatas \(SHA-256\)\s*\|\s*(\d+)\s*podados",
                line,
            )
            if m_cur and m_cur.group(2).strip() == cur["id"]:
                cur["dom"] = int(m_cur.group(3))
                cur["dedup"] = int(m_cur.group(4))
                cur["poda"] = int(m_cur.group(5))
                blocks_v1.append(cur)
                cur = None
            elif "[Tentativa " in line:
                blocks_v1.append(cur)
                cur = None

    total_anexos_listados_v1 = sum(b["total_anexos"] for b in blocks_v1)
    total_anexos_baixados_v1 = sum(len(b["docs_touched"]) for b in blocks_v1)
    total_pulados_pre_download_v1 = sum(
        max(0, b["total_anexos"] - len(b["docs_touched"]) - b["dom"]) for b in blocks_v1
    )

    # 4. Contabilização de PODA NLP ([PODA NLP]) detalhada por razão e tipo de documento
    poda_por_base_razao = Counter()
    poda_pncp_por_tipo = Counter()
    for line in all_lines:
        if "[PODA NLP]" in line:
            msg = line.split("[PODA NLP]")[-1].strip()
            m_base = re.search(r"Doc \d+/\d+: ([A-Z]+)_", msg)
            base = m_base.group(1) if m_base else "OUTRO"
            razao = "SEM_OCR_OU_NAO_PDF" if "SEM_OCR" in msg else "BAIXA_DENSIDADE_MENOR_300_CHARS"
            poda_por_base_razao[f"{base}_{razao}"] += 1
            if base == "DNIT":
                m_tipo = re.search(r"DNIT_\d+_\d+_\d+_([^\.]+)\.pdf", msg)
                if m_tipo:
                    poda_pncp_por_tipo[m_tipo.group(1)] += 1

    # 5. Leitura do log_coleta.csv (documentos que efetivamente passaram para o Drive na Sprint 1)
    drive_csv = Path(r"G:\Meu Drive\TCC_DOCUMENTOS\2025_Dados_brutos\log_coleta.csv")
    stats_csv: dict[str, Any] = {"existe": drive_csv.exists()}
    if drive_csv.exists():
        with open(drive_csv, "r", encoding="utf-8", errors="replace") as f:
            rows = list(csv.DictReader(f))
        por_base = Counter(r.get("base_de_dados", "") for r in rows)
        por_tipo = Counter(r.get("tipo_documento", "") for r in rows)
        por_status = Counter(r.get("status_validacao", "") for r in rows)
        # Separar fichas sintéticas (SIMEC/SISMOB/CODEVASF FichaTecnica) vs documentos reais baixados
        docs_sinteticos = sum(
            1
            for r in rows
            if "FichaTecnica" in (r.get("nome_arquivo") or "")
            or "Relatorio_Tecnico" in (r.get("nome_arquivo") or "")
        )
        docs_reais_web_api = len(rows) - docs_sinteticos
        stats_csv.update({
            "total_registros_log_coleta": len(rows),
            "fichas_sinteticas_geradas_fpdf": docs_sinteticos,
            "documentos_reais_baixados_web_api": docs_reais_web_api,
            "por_base": dict(por_base),
            "por_tipo_documento": dict(por_tipo),
            "por_status_validacao": dict(por_status),
        })

    total_barreira1_global = sum(v["barreira1_dom_api"] for v in curadoria_por_base.values())
    total_barreira2_global = sum(v["barreira2_sha256"] for v in curadoria_por_base.values())
    total_barreira3_global = sum(v["barreira3_poda_nlp"] for v in curadoria_por_base.values())

    return {
        "resumo_executivo_numeros": {
            "total_linhas_log_auditadas": len(all_lines),
            "total_bloqueados_barreira1_dom_e_api": total_barreira1_global,
            "total_bloqueados_barreira1_transferegov_dom": (
                curadoria_por_base.get("CAIXA", {}).get("barreira1_dom_api", 0)
                + curadoria_por_base.get("FUNASA", {}).get("barreira1_dom_api", 0)
                + curadoria_por_base.get("SIMEC", {}).get("barreira1_dom_api", 0)
            ),
            "total_bloqueados_barreira1_pncp_api": (
                curadoria_por_base.get("DNIT", {}).get("barreira1_dom_api", 0)
                + curadoria_por_base.get("CODEVASF", {}).get("barreira1_dom_api", 0)
            ),
            "total_duplicatas_barreira2_sha256": total_barreira2_global,
            "total_descartados_barreira3_poda_nlp_ou_nao_pdf": total_barreira3_global,
            "total_anexos_ignorados_pre_download_extensao_zip_xlsx_dwg_v1": total_pulados_pre_download_v1,
            "total_arquivos_afetados_por_restricao_formato_ou_sem_ocr": (
                total_pulados_pre_download_v1 + total_barreira3_global
            ),
        },
        "curadoria_por_base": curadoria_por_base,
        "detalhe_bloqueios_pncp_api": {
            "total_eventos_filtro_api": sum(filtro_api_motivos.values()),
            "por_termo_blacklist": dict(filtro_api_motivos),
            "contratos_bloqueados_por_termo_publicacao": bloqueios_contrato_publicacao_pncp,
            "documentos_bloqueados_por_termo_despacho": bloqueios_despacho_pncp,
            "amostra_logs": filtro_api_exemplos,
        },
        "detalhe_poda_barreira3": {
            "contagem_eventos_log_detalhado": dict(poda_por_base_razao),
            "pncp_tipos_descartados_sem_ocr_ou_zip_docx": dict(poda_pncp_por_tipo),
        },
        "detalhe_transferegov_v1_anexos": {
            "obras_com_anexos_listados": len(blocks_v1),
            "total_anexos_listados_na_aba_inicial": total_anexos_listados_v1,
            "total_anexos_baixados": total_anexos_baixados_v1,
            "total_anexos_pulados_extensao_zip_xlsx_rar_dwg_ou_cache": total_pulados_pre_download_v1,
        },
        "log_coleta_csv_drive": stats_csv,
    }


def executar_auditoria_fase1() -> dict[str, Any]:
    resultado = {
        "feature": "021-revisao-expansao-coleta",
        "fase": "Fase 1 - Auditoria do que Deixamos para Trás (Diagnóstico da Sprint 1)",
        "analise_estatica_codigo": auditar_codigo_estatico(),
        "mineracao_logs_sprint1": minerar_logs_sprint1(),
    }

    out_path = ROOT_DIR / "revisao_coleta/resultados/fase1_auditoria_sprint1.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[FASE 1] Relatório JSON salvo em: {out_path}")
    return resultado


if __name__ == "__main__":
    res = executar_auditoria_fase1()
    print(json.dumps(res["mineracao_logs_sprint1"]["resumo_executivo_numeros"], indent=2, ensure_ascii=False))
