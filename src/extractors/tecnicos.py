# -*- coding: utf-8 -*-
"""
src/extractors/tecnicos.py
==========================
Gerador e validador de Fichas Técnicas Oficiais e Relatórios de Monitoramento
em PDF para auditoria contínua de obras (SISMOB, SIMEC, CODEVASF).
"""

from __future__ import annotations

from pathlib import Path
import pandas as pd
from fpdf import FPDF

from src.config import logger
from src.utils import arquivo_ja_existe_valido, validar_e_registrar_pdf


def gerar_pdf_relatorio_sismob(caminho: Path, row: pd.Series) -> None:
    """Gera Ficha Técnica de Monitoramento de Saúde em PDF para obras do SISMOB."""
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


def gerar_pdf_relatorio_simec(caminho: Path, row: pd.Series) -> None:
    """Gera Ficha Técnica Consolidada FNDE/SIMEC em PDF para termos do PAR."""
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


def gerar_pdf_relatorio_codevasf(caminho: Path, row: pd.Series) -> None:
    """Gera Documento Técnico Contratual Oficial para obras da CODEVASF."""
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


def coletar_relatorio_sismob(
    row: pd.Series,
    pasta_destino: Path,
    cache_log: set[tuple[str, str, str]],
) -> list[Path]:
    """Coleta e valida a Ficha Técnica de Saúde do SISMOB com trava de idempotência."""
    id_obra = str(row.get("id", "")).strip()
    emp = str(row.get("empreendimento", "")).strip()
    num_inst = str(row.get("num. instrumento", "")).strip()
    nome_doc = f"SISMOB_{id_obra}_FichaTecnica_Saude.pdf"
    caminho_doc = pasta_destino / nome_doc

    if not arquivo_ja_existe_valido(caminho_doc):
        gerar_pdf_relatorio_sismob(caminho_doc, row)
    else:
        logger.info(f"    [IDEMPOTÊNCIA] Ficha técnica SISMOB já existente: {nome_doc}")

    avaliacao = validar_e_registrar_pdf(
        caminho_pdf=caminho_doc,
        base_nome="SISMOB",
        id_obra=id_obra,
        num_inst=num_inst,
        emp=emp,
        obs_extra="Ficha Técnica SISMOB/Ministério da Saúde",
        cache_log=cache_log,
    )
    if avaliacao["validation"]["result"] in ("VALIDADO", "VALIDADO_COM_RESSALVAS"):
        return [caminho_doc]
    return []


def coletar_relatorio_simec(
    row: pd.Series,
    pasta_destino: Path,
    cache_log: set[tuple[str, str, str]],
) -> list[Path]:
    """Coleta e valida a Ficha Técnica do FNDE/SIMEC com trava de idempotência."""
    id_obra = str(row.get("id", "")).strip()
    emp = str(row.get("empreendimento", "")).strip()
    num_inst = str(row.get("num. instrumento", "")).strip()
    nome_doc = f"SIMEC_{id_obra}_FichaTecnica_FNDE.pdf"
    caminho_doc = pasta_destino / nome_doc

    if not arquivo_ja_existe_valido(caminho_doc):
        gerar_pdf_relatorio_simec(caminho_doc, row)
    else:
        logger.info(f"    [IDEMPOTÊNCIA] Ficha técnica SIMEC já existente: {nome_doc}")

    avaliacao = validar_e_registrar_pdf(
        caminho_pdf=caminho_doc,
        base_nome="SIMEC",
        id_obra=id_obra,
        num_inst=num_inst,
        emp=emp,
        obs_extra="Ficha Técnica Consolidada FNDE/SIMEC",
        cache_log=cache_log,
    )
    if avaliacao["validation"]["result"] in ("VALIDADO", "VALIDADO_COM_RESSALVAS"):
        return [caminho_doc]
    return []


def coletar_relatorio_codevasf(
    row: pd.Series,
    pasta_destino: Path,
    cache_log: set[tuple[str, str, str]],
) -> list[Path]:
    """Coleta e valida o Relatório Técnico da CODEVASF com trava de idempotência."""
    id_obra = str(row.get("id", "")).strip()
    emp = str(row.get("empreendimento", "")).strip()
    num_inst = str(row.get("num. instrumento", "")).strip()
    nome_doc = f"CODEVASF_{id_obra.replace('/', '_')}_Relatorio_Tecnico.pdf"
    caminho_doc = pasta_destino / nome_doc

    if not arquivo_ja_existe_valido(caminho_doc):
        gerar_pdf_relatorio_codevasf(caminho_doc, row)
    else:
        logger.info(f"    [IDEMPOTÊNCIA] Relatório técnico CODEVASF já existente: {nome_doc}")

    avaliacao = validar_e_registrar_pdf(
        caminho_pdf=caminho_doc,
        base_nome="CODEVASF",
        id_obra=id_obra,
        num_inst=num_inst,
        emp=emp,
        obs_extra="Relatório Técnico CODEVASF",
        cache_log=cache_log,
    )
    if avaliacao["validation"]["result"] in ("VALIDADO", "VALIDADO_COM_RESSALVAS"):
        return [caminho_doc]
    return []
