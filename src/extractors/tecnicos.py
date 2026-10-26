# -*- coding: utf-8 -*-
"""
src/extractors/tecnicos.py
==========================
Coletor de justificativas e relatórios técnicos oficiais via API Pública do SISMOB Cidadão
(`sismobcidadao.saude.gov.br/api/public/obras`) e adaptadores para SIMEC / CODEVASF.

Melhorias da Reengenharia de Coleta (Feature 021):
1. Consulta real à API pública do SISMOB com cache em memória O(1) por município IBGE,
   extraindo `dsJustificativa` e histórico oficial de execução/paralisação.
2. Avaliação obrigatória pelo Gatekeeper Anti-Lixo (>= 800 caracteres úteis).
3. Desativação por padrão (`permitir_fallback_sintetico=False`) da geração de fichas FPDF
   sintéticas em produção, eliminando a contaminação por vazamento tabular identificada na Sprint 7.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import re
import threading
import unicodedata
from typing import Any

from fpdf import FPDF
import pandas as pd
import requests

from src.config import ARQUIVO_LOG_COLETA, DEFAULT_HEADERS, logger
from src.multiformato import (
    DocumentoProcessado,
    MIN_CHARS_UTEIS_GATEKEEPER,
    avaliar_gatekeeper_anti_lixo,
    materializar_documento_aprovado_em_pdf,
)
from src.utils import arquivo_ja_existe_valido, validar_e_registrar_pdf

_LOCK_SISMOB_CACHE = threading.Lock()
_CACHE_MUNICIPIOS_IBGE: dict[str, str] = {}
_CACHE_OBRAS_MUNICIPIO: dict[str, list[dict[str, Any]]] = {}

MAPA_UF_IBGE = {
    "RO": "11", "AC": "12", "AM": "13", "RR": "14", "PA": "15", "AP": "16", "TO": "17",
    "MA": "21", "PI": "22", "CE": "23", "RN": "24", "PB": "25", "PE": "26", "AL": "27", "SE": "28", "BA": "29",
    "MG": "31", "ES": "32", "RJ": "33", "SP": "35", "PR": "41", "SC": "42", "RS": "43",
    "MS": "50", "MT": "51", "GO": "52", "DF": "53",
}


def _normalizar_ascii(texto: Any) -> str:
    if not texto:
        return ""
    return unicodedata.normalize("NFKD", str(texto)).encode("ASCII", "ignore").decode("ASCII").lower().strip()


# ─────────────────────────────────────────────────────────────────────────────
# GERADORES SINTÉTICOS LEGADOS (DESATIVADOS POR PADRÃO EM PRODUÇÃO)
# ─────────────────────────────────────────────────────────────────────────────

def gerar_pdf_relatorio_sismob(caminho: Path, row: pd.Series | dict[str, Any]) -> None:
    """[LEGADO] Gera Ficha Técnica de Monitoramento de Saúde em PDF para obras do SISMOB."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 15)
    pdf.cell(0, 10, text="MINISTÉRIO DA SAÚDE - GOVERNO FEDERAL", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, text="SISMOB - Sistema de Monitoramento de Obras da Saúde", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.cell(0, 8, text="Ficha Técnica de Acompanhamento e Fiscalização de Obra Pública", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(4)

    id_obra = str(row.get("id", ""))
    id_limpo = id_obra.replace("SISMOB-", "").strip()
    cnpj_mun = id_limpo[:14] if len(id_limpo) >= 14 else "Não informado"
    proposta = id_limpo[14:] if len(id_limpo) > 14 else ""

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 7, text=f"Identificador SISMOB: {id_obra}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, text=f"Fundo Municipal / Proponente (CNPJ): {cnpj_mun} (Proposta nº: {proposta})", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, text=f"Empreendimento: {str(row.get('empreendimento', ''))[:100]}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, text=f"Localização / UF: {row.get('local', 'Não identificado')}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, text=f"Órgão Concedente / Repassador: {row.get('repassador', 'Ministério da Saúde')}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, text=f"Situação Operacional: {row.get('situacao', '')} (Origem: {row.get('situacao origem', '')})", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, text=f"Execução Física: {float(row.get('exec. fisica', 0) or 0)*100:.1f}% | Execução Financeira: {float(row.get('exec. financeira', 0) or 0)*100:.1f}%", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, text=f"Valor de Investimento Federal: R$ {float(row.get('valor investimento', 0) or 0):,.2f}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, text=f"Valor Desbloqueado: R$ {float(row.get('valor desbloqueado', 0) or 0):,.2f}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(
        0, 6,
        text="Documento técnico oficial consolidado para fins de auditoria contínua de obras públicas federais. "
             "Contém a parametrização de transferências financeiras fundo a fundo do Ministério da Saúde, termos de "
             "repasse de recursos da União e registro de fiscalização e medição de infraestrutura em saúde."
    )
    pdf.output(str(caminho))


def gerar_pdf_relatorio_simec(caminho: Path, row: pd.Series | dict[str, Any]) -> None:
    """[LEGADO] Gera Ficha Técnica Consolidada FNDE/SIMEC em PDF para termos do PAR."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 15)
    pdf.cell(0, 10, text="MINISTÉRIO DA EDUCAÇÃO - FNDE", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, text="SIMEC - Sistema Integrado de Monitoramento Execução e Controle", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.cell(0, 8, text="Relatório Técnico de Fiscalização de Obras da Educação (PAR)", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 7, text=f"Identificador SIMEC: {row.get('id', '')}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, text=f"Termo de Compromisso / PAR: {row.get('num. instrumento', 'N/A')}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, text=f"Empreendimento: {str(row.get('empreendimento', ''))[:100]}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, text=f"Localização / Município: {row.get('local', 'Não identificado')}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, text=f"Órgão Concedente: {row.get('repassador', 'Fundo Nacional de Desenvolvimento da Educação')}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, text=f"Situação no FNDE: {row.get('situacao', '')} (Origem: {row.get('situacao origem', '')})", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, text=f"Evolução Física: {float(row.get('exec. fisica', 0) or 0)*100:.1f}% | Execução Financeira: {float(row.get('exec. financeira', 0) or 0)*100:.1f}%", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, text=f"Valor Previsto: R$ {float(row.get('valor investimento', 0) or 0):,.2f} | Valor Repassado: R$ {float(row.get('valor desbloqueado', 0) or 0):,.2f}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(
        0, 6,
        text="Laudo e ficha técnica de acompanhamento emitida para auditoria de contratos de engenharia e obras públicas "
             "financiadas com recursos federais da União. Apresenta o registro de medições, vistorias técnicas e situação "
             "de paralisação das edificações escolares e de infraestrutura educacional."
    )
    pdf.output(str(caminho))


def gerar_pdf_relatorio_codevasf(caminho: Path, row: pd.Series | dict[str, Any]) -> None:
    """[LEGADO] Gera Documento Técnico Contratual Oficial para obras da CODEVASF."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 15)
    pdf.cell(0, 10, text="CODEVASF - COMPANHIA DE DESENVOLVIMENTO DOS VALES", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, text="Superintendência Regional / Ministério da Integração Nacional", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.cell(0, 8, text="Instrumento Contratual e Termo de Execução de Obras", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 7, text=f"Identificador CODEVASF: {row.get('id', '')}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, text=f"Empreendimento: {str(row.get('empreendimento', ''))[:100]}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, text=f"Local / Estado: {row.get('local', 'Não identificado')}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, text=f"Órgão Concedente: {row.get('repassador', 'Ministério da Integração')}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, text=f"Situação Contratual: {row.get('situacao', '')} (Origem: {row.get('situacao origem', '')})", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, text=f"Execução Física: {float(row.get('exec. fisica', 0) or 0)*100:.1f}% | Execução Financeira: {float(row.get('exec. financeira', 0) or 0)*100:.1f}%", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, text=f"Valor de Investimento Federal: R$ {float(row.get('valor investimento', 0) or 0):,.2f}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, text=f"Valor Desbloqueado: R$ {float(row.get('valor desbloqueado', 0) or 0):,.2f}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(
        0, 6,
        text="Instrumento de acompanhamento da execução física e financeira de obras e serviços de engenharia "
             "da CODEVASF. Consolida os dados orçamentários, fiscalização das medições e registros de paralisação "
             "em conformidade com a auditoria de obras públicas do Tribunal de Contas da União."
    )
    pdf.output(str(caminho))


# ─────────────────────────────────────────────────────────────────────────────
# COLETORES DE PRODUÇÃO V2 (API PÚBLICA SISMOB + GATEKEEPER >= 800 CHARS)
# ─────────────────────────────────────────────────────────────────────────────

def _resolver_ibge6_sismob(sess: requests.Session, uf_sigla: str, mun_nome: str) -> str | None:
    uf_cod = MAPA_UF_IBGE.get(uf_sigla.upper(), "")
    if not uf_cod or not mun_nome:
        return None
    chave = f"{uf_sigla.upper()}:{_normalizar_ascii(mun_nome)}"
    with _LOCK_SISMOB_CACHE:
        if chave in _CACHE_MUNICIPIOS_IBGE:
            return _CACHE_MUNICIPIOS_IBGE[chave]

    ibge6 = None
    try:
        rm = sess.get(
            "https://sismobcidadao.saude.gov.br/api/public/endereco/municipios",
            params={"ufIbge": uf_cod, "query": _normalizar_ascii(mun_nome).upper(), "pageSize": 50},
            timeout=12,
        )
        if rm.status_code == 200 and isinstance(rm.json(), list):
            for item_m in rm.json():
                if _normalizar_ascii(item_m.get("nome", "")) == _normalizar_ascii(mun_nome):
                    ibge6 = str(item_m.get("ibge", ""))
                    break
            if not ibge6 and rm.json():
                ibge6 = str(rm.json()[0].get("ibge", ""))
    except Exception:
        pass

    if ibge6:
        with _LOCK_SISMOB_CACHE:
            _CACHE_MUNICIPIOS_IBGE[chave] = ibge6
    return ibge6


def _listar_obras_municipio_sismob(sess: requests.Session, ibge6: str) -> list[dict[str, Any]]:
    with _LOCK_SISMOB_CACHE:
        if ibge6 in _CACHE_OBRAS_MUNICIPIO:
            return _CACHE_OBRAS_MUNICIPIO[ibge6]

    obras_mun: list[dict[str, Any]] = []
    try:
        for page in range(5):
            ro = sess.get(
                "https://sismobcidadao.saude.gov.br/api/public/obras",
                params={"municipioIbge": ibge6, "page": page, "size": 200},
                timeout=15,
            )
            if ro.status_code != 200:
                break
            payload = ro.json()
            content = payload.get("content") or []
            obras_mun.extend(content)
            if payload.get("last") is True or page + 1 >= payload.get("totalPages", 1) or not content:
                break
    except Exception:
        pass

    if obras_mun:
        with _LOCK_SISMOB_CACHE:
            _CACHE_OBRAS_MUNICIPIO[ibge6] = obras_mun
    return obras_mun


def coletar_relatorio_sismob(
    row: pd.Series | dict[str, Any],
    pasta_destino: Path,
    cache_log: dict[tuple[str, str, str], str] | set[tuple[str, str, str]],
    caminho_csv: Path = ARQUIVO_LOG_COLETA,
    permitir_fallback_sintetico: bool = False,
) -> list[Path]:
    """
    Consulta a API pública oficial do SISMOB Cidadão (`sismobcidadao.saude.gov.br/api/public/obras`),
    extrai a justificativa técnica (`dsJustificativa`) e valida pelo Gatekeeper Anti-Lixo (>= 800 chars).
    Em produção (`permitir_fallback_sintetico=False`), jamais gera fichas sintéticas FPDF.
    """
    id_obra = str(row.get("id", "")).strip()
    emp = str(row.get("empreendimento", "")).strip()
    num_inst = str(row.get("num. instrumento", "")).strip()
    local_str = str(row.get("local", "")).strip()

    nome_doc_api = f"SISMOB_{id_obra}_JustificativaOficial_API.pdf"
    caminho_doc_api = pasta_destino / nome_doc_api

    if arquivo_ja_existe_valido(caminho_doc_api):
        avaliacao = validar_e_registrar_pdf(
            caminho_pdf=caminho_doc_api,
            base_nome="SISMOB",
            id_obra=id_obra,
            num_inst=num_inst,
            emp=emp,
            obs_extra="Justificativa Oficial API Pública SISMOB Cidadão",
            cache_log=cache_log,
            caminho_csv=caminho_csv,
        )
        if avaliacao["validation"]["result"] in ("VALIDADO", "VALIDADO_COM_RESSALVAS"):
            return [caminho_doc_api]

    num_proposta_alvo = re.sub(r"\D", "", id_obra.replace("SISMOB-", ""))
    if "/" in local_str:
        mun_nome, uf_sigla = [p.strip() for p in local_str.rsplit("/", 1)]
    else:
        mun_nome, uf_sigla = local_str, ""

    sess = requests.Session()
    sess.headers.update(DEFAULT_HEADERS)
    try:
        ibge6 = _resolver_ibge6_sismob(sess, uf_sigla, mun_nome)
        if ibge6:
            obras_mun = _listar_obras_municipio_sismob(sess, ibge6)
            cand_match = None
            for item_o in obras_mun:
                num_p = re.sub(r"\D", "", str(item_o.get("numeroProposta") or ""))
                if num_proposta_alvo and num_p == num_proposta_alvo:
                    cand_match = item_o
                    break
            if not cand_match:
                emp_alvo = _normalizar_ascii(emp)
                for item_o in obras_mun:
                    nome_est = _normalizar_ascii(item_o.get("nomeEstabelecimento") or item_o.get("titulo") or "")
                    if emp_alvo and nome_est and (emp_alvo in nome_est or nome_est in emp_alvo):
                        cand_match = item_o
                        break

            if cand_match and cand_match.get("propostaId"):
                prop_id = cand_match["propostaId"]
                rd = sess.get(f"https://sismobcidadao.saude.gov.br/api/public/obras/{prop_id}", timeout=15)
                if rd.status_code == 200 and isinstance(rd.json(), dict):
                    det = rd.json()
                    just = str(det.get("dsJustificativa") or "").strip()
                    if just:
                        texto_sismob = (
                            f"MINISTÉRIO DA SAÚDE — SISTEMA DE MONITORAMENTO DE OBRAS (SISMOB CIDADÃO)\n"
                            f"Proposta SISMOB: {det.get('nuProposta', num_proposta_alvo)} (ID Interno: {prop_id})\n"
                            f"Município / UF: {det.get('noMunicipioAcentuado', mun_nome)} / {det.get('sgUf', uf_sigla)}\n"
                            f"Data Mudança Situação: {det.get('dtMudancaSituacao', '')} | Última Atualização: {det.get('dtAtualizacao', '')}\n\n"
                            f"JUSTIFICATIVA TÉCNICA E PARECER DE MONITORAMENTO DA OBRA:\n{just}"
                        )
                        raw_s = texto_sismob.encode("utf-8", errors="replace")
                        aprov, mot, txt_corr, chars_u, parags, eh_em, eh_ht = avaliar_gatekeeper_anti_lixo(
                            texto_bruto=texto_sismob,
                            formato="sismob_api_json",
                            tamanho_bytes=len(raw_s),
                            min_chars_uteis=MIN_CHARS_UTEIS_GATEKEEPER,
                        )
                        doc_s = DocumentoProcessado(
                            nome_origem=f"SISMOB_API_{prop_id}.json",
                            caminho_interno_zip=None,
                            formato_detectado="sismob_api_json",
                            tamanho_bytes=len(raw_s),
                            sha256=hashlib.sha256(raw_s).hexdigest(),
                            aprovado_gatekeeper=aprov,
                            motivo_gatekeeper=mot,
                            chars_brutos=len(texto_sismob),
                            chars_uteis_corridos=chars_u,
                            paragrafos_validos=parags,
                            eh_email_bloqueado=eh_em,
                            eh_espelho_html=eh_ht,
                            texto_util_preview=txt_corr[:400] if txt_corr else "",
                            texto_completo_limpo=txt_corr,
                            raw_bytes=raw_s if aprov else b"",
                        )
                        if doc_s.aprovado_gatekeeper:
                            ok = materializar_documento_aprovado_em_pdf(
                                doc=doc_s,
                                caminho_destino=caminho_doc_api,
                                titulo_cabecalho=f"RELATÓRIO E JUSTIFICATIVA TÉCNICA OFICIAL SISMOB — {id_obra}",
                            )
                            if ok and arquivo_ja_existe_valido(caminho_doc_api):
                                avaliacao = validar_e_registrar_pdf(
                                    caminho_pdf=caminho_doc_api,
                                    base_nome="SISMOB",
                                    id_obra=id_obra,
                                    num_inst=num_inst,
                                    emp=emp,
                                    obs_extra=f"API Pública SISMOB Cidadão (propostaId={prop_id}, chars_uteis={chars_u})",
                                    cache_log=cache_log,
                                    caminho_csv=caminho_csv,
                                )
                                if avaliacao["validation"]["result"] in ("VALIDADO", "VALIDADO_COM_RESSALVAS"):
                                    return [caminho_doc_api]
    except Exception as exc:
        logger.debug(f"Erro SISMOB API ({id_obra}): {exc}")
    finally:
        sess.close()

    if not permitir_fallback_sintetico:
        return []

    nome_doc = f"SISMOB_{id_obra}_FichaTecnica_Saude.pdf"
    caminho_doc = pasta_destino / nome_doc
    if not arquivo_ja_existe_valido(caminho_doc):
        gerar_pdf_relatorio_sismob(caminho_doc, row)
    avaliacao = validar_e_registrar_pdf(
        caminho_pdf=caminho_doc,
        base_nome="SISMOB",
        id_obra=id_obra,
        num_inst=num_inst,
        emp=emp,
        obs_extra="Ficha Técnica SISMOB/Ministério da Saúde",
        cache_log=cache_log,
        caminho_csv=caminho_csv,
    )
    if avaliacao["validation"]["result"] in ("VALIDADO", "VALIDADO_COM_RESSALVAS"):
        return [caminho_doc]
    return []


def coletar_relatorio_simec(
    row: pd.Series | dict[str, Any],
    pasta_destino: Path,
    cache_log: dict[tuple[str, str, str], str] | set[tuple[str, str, str]],
    caminho_csv: Path = ARQUIVO_LOG_COLETA,
    permitir_fallback_sintetico: bool = False,
) -> list[Path]:
    """
    Adaptador SIMEC/FNDE. Em produção (`permitir_fallback_sintetico=False`), não gera
    fichas FPDF sintéticas quando o portal público exige reCAPTCHA/autenticação.
    """
    if not permitir_fallback_sintetico:
        return []

    id_obra = str(row.get("id", "")).strip()
    emp = str(row.get("empreendimento", "")).strip()
    num_inst = str(row.get("num. instrumento", "")).strip()
    nome_doc = f"SIMEC_{id_obra}_FichaTecnica_FNDE.pdf"
    caminho_doc = pasta_destino / nome_doc

    if not arquivo_ja_existe_valido(caminho_doc):
        gerar_pdf_relatorio_simec(caminho_doc, row)

    avaliacao = validar_e_registrar_pdf(
        caminho_pdf=caminho_doc,
        base_nome="SIMEC",
        id_obra=id_obra,
        num_inst=num_inst,
        emp=emp,
        obs_extra="Ficha Técnica Consolidada FNDE/SIMEC",
        cache_log=cache_log,
        caminho_csv=caminho_csv,
    )
    if avaliacao["validation"]["result"] in ("VALIDADO", "VALIDADO_COM_RESSALVAS"):
        return [caminho_doc]
    return []


def coletar_relatorio_codevasf(
    row: pd.Series | dict[str, Any],
    pasta_destino: Path,
    cache_log: dict[tuple[str, str, str], str] | set[tuple[str, str, str]],
    caminho_csv: Path = ARQUIVO_LOG_COLETA,
    permitir_fallback_sintetico: bool = False,
) -> list[Path]:
    """
    Adaptador CODEVASF/MIDR. Em produção (`permitir_fallback_sintetico=False`), não gera
    fichas FPDF sintéticas quando a obra não possui documentos contratuais no PNCP.
    """
    if not permitir_fallback_sintetico:
        return []

    id_obra = str(row.get("id", "")).strip()
    emp = str(row.get("empreendimento", "")).strip()
    num_inst = str(row.get("num. instrumento", "")).strip()
    nome_doc = f"CODEVASF_{id_obra.replace('/', '_')}_Relatorio_Tecnico.pdf"
    caminho_doc = pasta_destino / nome_doc

    if not arquivo_ja_existe_valido(caminho_doc):
        gerar_pdf_relatorio_codevasf(caminho_doc, row)

    avaliacao = validar_e_registrar_pdf(
        caminho_pdf=caminho_doc,
        base_nome="CODEVASF",
        id_obra=id_obra,
        num_inst=num_inst,
        emp=emp,
        obs_extra="Relatório Técnico CODEVASF",
        cache_log=cache_log,
        caminho_csv=caminho_csv,
    )
    if avaliacao["validation"]["result"] in ("VALIDADO", "VALIDADO_COM_RESSALVAS"):
        return [caminho_doc]
    return []
