# -*- coding: utf-8 -*-
"""
revisao_coleta/test_motor_multiformato.py
=========================================
FASE 2: Suíte de Testes e Validação Empírica do Motor de Ingestão Multiformato,
Descompactação Cirúrgica In-Memory de .zip e Gatekeeper Anti-Lixo.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
import sys
import zipfile

import docx
from fpdf import FPDF
from odf.opendocument import OpenDocumentText
from odf.text import P

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from revisao_coleta.motor_multiformato import (
    filtro_pre_download_dom_v2,
    ingerir_payload_multiformato,
    inspecionar_e_extrair_zip_in_memory,
    processar_bytes_documento,
)


TEXTO_DENSO_ENGENHARIA = (
    "RELATÓRIO TÉCNICO DE VISTORIA E PARECER DE ENGENHARIA SOBRE PARALISAÇÃO DE OBRA PÚBLICA.\n\n"
    "1. HISTÓRICO CONTRATUAL E OBJETO DO EMPREENDIMENTO\n"
    "O presente Parecer Técnico tem por finalidade registrar a vistoria in loco realizada na obra de "
    "implantação e pavimentação asfáltica vinculada ao Termo de Compromisso Federal, analisando as "
    "causas determinantes da interrupção do cronograma físico-financeiro vigente.\n\n"
    "2. CONSTATAÇÕES TÉCNICAS E DEFICIÊNCIAS DE PROJETO BÁSICO\n"
    "Durante a supervisão de engenharia realizada pela equipe de fiscalização, constatou-se a "
    "necessidade de revisão integral do memorial descritivo e das sondagens geotécnicas do subleito, "
    "tendo em vista o afloramento inesperado de lençol freático e solo mole de baixa capacidade de suporte "
    "entre as estacas 140 e 290. Adicionalmente, a empresa contratada reduziu drasticamente o efetivo de "
    "mão de obra e retirou os equipamentos de terraplenagem do canteiro sem prévia anuência da administração, "
    "configurando descumprimento de cláusula contratual e ensejando a abertura de processo administrativo "
    "para celebração de Termo Aditivo de readequação técnica ou eventual Termo de Rescisão Unilateral.\n\n"
    "3. CONCLUSÃO E ENCAMINHAMENTO DA FISCALIZAÇÃO\n"
    "Diante do exposto, recomenda-se a imediata notificação da contratada para apresentação de plano de "
    "contingência em até 10 dias úteis, sob pena de rescisão contratual e aplicação das penalidades previstas "
    "na Lei Federal de Licitações e Contratos Administrativos."
)


def gerar_pdf_bytes(texto: str) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    # FPDF latin-1 encoding
    texto_latin = texto.encode("latin-1", errors="replace").decode("latin-1")
    pdf.multi_cell(0, 6, text=texto_latin)
    return bytes(pdf.output())


def gerar_docx_bytes(texto: str) -> bytes:
    doc = docx.Document()
    for bloco in texto.split("\n\n"):
        doc.add_paragraph(bloco)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def gerar_odt_bytes(texto: str) -> bytes:
    textdoc = OpenDocumentText()
    for bloco in texto.split("\n\n"):
        p = P(text=bloco)
        textdoc.text.addElement(p)
    buf = io.BytesIO()
    textdoc.save(buf)
    return buf.getvalue()


def gerar_rtf_bytes(texto: str) -> bytes:
    # Converte caracteres acentuados para escape RTF \'xx (cp1252)
    partes = ["{\\rtf1\\ansi\\deff0\n"]
    for ch in texto:
        if ch == "\n":
            partes.append("\\par\n")
        elif ord(ch) < 128:
            partes.append(ch)
        else:
            b = ch.encode("cp1252", errors="ignore")
            if b:
                partes.append(f"\\'{b[0]:02x}")
    partes.append("\n}")
    return "".join(partes).encode("ascii")


def executar_testes_fase2() -> dict:
    resultados_testes = []

    # 1. Teste de PDF Denso (>= 800 chars)
    pdf_b = gerar_pdf_bytes(TEXTO_DENSO_ENGENHARIA)
    res_pdf = processar_bytes_documento(pdf_b, "Laudo_Vistoria_Obra.pdf")
    assert res_pdf.aprovado_gatekeeper is True, f"PDF denso falhou: {res_pdf}"
    assert res_pdf.chars_uteis_corridos >= 800
    resultados_testes.append({"teste": "PDF_DENSO", "status": "PASS", "detalhes": res_pdf.to_summary_dict()})

    # 2. Teste de DOCX Denso (>= 800 chars)
    docx_b = gerar_docx_bytes(TEXTO_DENSO_ENGENHARIA)
    res_docx = processar_bytes_documento(docx_b, "Parecer_Tecnico_Aditivo.docx")
    assert res_docx.aprovado_gatekeeper is True, f"DOCX denso falhou: {res_docx}"
    assert res_docx.formato_detectado == "docx"
    assert res_docx.chars_uteis_corridos >= 800
    resultados_testes.append({"teste": "DOCX_DENSO", "status": "PASS", "detalhes": res_docx.to_summary_dict()})

    # 3. Teste de DOCX salvo com extensão .pdf forçada (Bug da Sprint 1)
    res_docx_renomeado = processar_bytes_documento(docx_b, "DNIT_compras_2024_10_1_Outros_Documentos.pdf")
    assert res_docx_renomeado.formato_detectado == "docx"
    assert res_docx_renomeado.aprovado_gatekeeper is True
    resultados_testes.append({
        "teste": "DOCX_COM_EXTENSAO_PDF_FORCADA",
        "status": "PASS",
        "detalhes": res_docx_renomeado.to_summary_dict(),
    })

    # 4. Teste de ODT Denso (>= 800 chars)
    odt_b = gerar_odt_bytes(TEXTO_DENSO_ENGENHARIA)
    res_odt = processar_bytes_documento(odt_b, "Memorial_Descritivo.odt")
    assert res_odt.aprovado_gatekeeper is True, f"ODT denso falhou: {res_odt}"
    assert res_odt.formato_detectado == "odt"
    assert res_odt.chars_uteis_corridos >= 800
    resultados_testes.append({"teste": "ODT_DENSO", "status": "PASS", "detalhes": res_odt.to_summary_dict()})

    # 5. Teste de RTF Denso (>= 800 chars)
    rtf_b = gerar_rtf_bytes(TEXTO_DENSO_ENGENHARIA)
    res_rtf = processar_bytes_documento(rtf_b, "Termo_Rescisao_Contratual.rtf")
    assert res_rtf.aprovado_gatekeeper is True, f"RTF denso falhou: {res_rtf}"
    assert res_rtf.formato_detectado == "rtf"
    assert res_rtf.chars_uteis_corridos >= 800
    resultados_testes.append({"teste": "RTF_DENSO", "status": "PASS", "detalhes": res_rtf.to_summary_dict()})

    # 6. Teste do Gatekeeper Anti-Lixo: Print de E-mail (mesmo com texto longo > 900 chars)
    texto_email = (
        "De: fiscalizacao.obras@dnit.gov.br\n"
        "Para: construtora.contratada@empresa.com.br\n"
        "Assunto: ENC: Encaminhamento de planilha e solicitação de comprovante\n"
        "Enviado em: Segunda-feira, 14 de Agosto de 2024 10:35\n\n"
        "Prezados senhores, encaminhamos em anexo os arquivos solicitados conforme conversa telefônica "
        "para conhecimento e providências administrativas cabíveis junto ao setor de protocolo. " * 6
    )
    pdf_email = gerar_pdf_bytes(texto_email)
    res_email = processar_bytes_documento(pdf_email, "Notificacao_Email.pdf")
    assert res_email.aprovado_gatekeeper is False, "E-mail deveria ter sido bloqueado!"
    assert res_email.eh_email_bloqueado is True
    resultados_testes.append({"teste": "BLOQUEIO_EMAIL_REGEX", "status": "PASS", "detalhes": res_email.to_summary_dict()})

    # 7. Teste do Gatekeeper Anti-Lixo: Despacho de 1 parágrafo curto (< 800 chars)
    texto_despacho_curto = (
        "MINISTÉRIO DOS TRANSPORTES\n"
        "DESPACHO DE ENCAMINHAMENTO\n"
        "Encaminhe-se o presente processo administrativo à Coordenação-Geral para ciência e arquivamento."
    )
    pdf_curto = gerar_pdf_bytes(texto_despacho_curto)
    res_curto = processar_bytes_documento(pdf_curto, "Despacho_Simples.pdf")
    assert res_curto.aprovado_gatekeeper is False
    resultados_testes.append({
        "teste": "BLOQUEIO_DESPACHO_CURTO_MENOR_800_CHARS",
        "status": "PASS",
        "detalhes": res_curto.to_summary_dict(),
    })

    # 8. Teste do Gatekeeper Anti-Lixo: Espelho HTML vazio / SAML
    html_saml = (
        b"<!DOCTYPE html><html><head><title>SAML 2.0 HTTP Post Binding</title></head>"
        b"<body><form action='/idp/SSO'><input type='hidden' name='SAMLRequest'/></form></body></html>"
    ) * 10
    res_html = processar_bytes_documento(html_saml, "Espelho_Transferegov.pdf")
    assert res_html.aprovado_gatekeeper is False
    assert res_html.eh_espelho_html is True
    resultados_testes.append({"teste": "BLOQUEIO_ESPELHO_HTML", "status": "PASS", "detalhes": res_html.to_summary_dict()})

    # 9. Teste de Inspeção Cirúrgica de .zip In-Memory (Pasta Técnica de Fiscalização mista)
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("Pasta_Fiscalizacao/Planta_Baixa_Estrutural.dwg", b"AC1027_FAKE_DWG_BINARY" * 500)
        zf.writestr("Pasta_Fiscalizacao/Fotos_Vistoria/Foto_01_Canteiro.jpg", b"\xff\xd8\xff\xe0FAKE_JPEG" * 500)
        zf.writestr("Pasta_Fiscalizacao/Video_Drone.mp4", b"\x00\x00\x00\x18ftypmp42" * 500)
        zf.writestr("Pasta_Fiscalizacao/Planilha_Medicao_Bruta.xlsx", b"PK\x03\x04FAKE_XLSX" * 200)
        zf.writestr("Pasta_Fiscalizacao/Laudo_Vistoria_Paralisacao.pdf", pdf_b)
        zf.writestr("Pasta_Fiscalizacao/Parecer_Tecnico_Engenharia.docx", docx_b)
        zf.writestr("Pasta_Fiscalizacao/Memorial_Descritivo.odt", odt_b)
        zf.writestr("Pasta_Fiscalizacao/Comprovante_Email.pdf", pdf_email)

    zip_bytes = zip_buf.getvalue()
    docs_zip, insp_zip = ingerir_payload_multiformato(zip_bytes, "Processo_Fiscalizacao_Pasta_Tecnica.zip")
    assert insp_zip is not None
    assert insp_zip.total_entradas_zip == 8
    assert len(insp_zip.entradas_ignoradas_engenharia_midia) == 4  # dwg, jpg, mp4, xlsx
    assert len(insp_zip.entradas_texto_rico_extraidas) == 4        # pdf, docx, odt, pdf_email
    aprovados_zip = [d for d in docs_zip if d.aprovado_gatekeeper]
    rejeitados_zip = [d for d in docs_zip if not d.aprovado_gatekeeper]
    assert len(aprovados_zip) == 3  # pdf denso, docx denso, odt denso
    assert len(rejeitados_zip) == 1 and rejeitados_zip[0].eh_email_bloqueado is True

    resultados_testes.append({
        "teste": "INSPECAO_CIRURGICA_ZIP_IN_MEMORY",
        "status": "PASS",
        "detalhes": {
            "nome_zip": insp_zip.nome_zip,
            "total_entradas_zip": insp_zip.total_entradas_zip,
            "entradas_ignoradas_engenharia_midia": insp_zip.entradas_ignoradas_engenharia_midia,
            "entradas_texto_rico_extraidas": insp_zip.entradas_texto_rico_extraidas,
            "aprovados_gatekeeper": len(aprovados_zip),
            "rejeitados_gatekeeper": len(rejeitados_zip),
        },
    })

    # 10. Teste de Filtro Pré-Download v2 vs Títulos Vitais antes bloqueados na Sprint 1
    titulos_vitais = [
        "Publicação do Contrato e 1º Termo Aditivo.pdf",
        "Despacho Técnico de Paralisação e Parecer de Engenharia.docx",
        "Notificação de Rescisão Contratual e Relatório de Vistoria.pdf",
        "Pasta_Tecnica_Memorial_Projeto_Basico.zip",
    ]
    for t in titulos_vitais:
        ok, mot = filtro_pre_download_dom_v2(t)
        assert ok is True, f"Título vital bloqueado indevidamente: {t} ({mot})"

    resumo = {
        "feature": "021-revisao-expansao-coleta",
        "fase": "Fase 2 - Validação do Motor Multiformato In-Memory e Gatekeeper Anti-Lixo",
        "total_testes": len(resultados_testes),
        "testes_aprovados": len(resultados_testes),
        "status_global": "100% PASS",
        "resultados": resultados_testes,
    }

    out_path = ROOT_DIR / "revisao_coleta/resultados/fase2_validacao_multiformato.json"
    out_path.write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[FASE 2] Todos os {len(resultados_testes)} testes multiformato/ZIP/Gatekeeper passaram! Salvo em: {out_path}")
    return resumo


if __name__ == "__main__":
    executar_testes_fase2()
