# -*- coding: utf-8 -*-
"""
tests/test_multiformato_producao.py
===================================
Testes unitários e de integração da Reengenharia de Coleta (Feature 021 — Produção):
- Ingestão multiformato (`.pdf`, `.docx`, `.odt`, `.rtf`) em `src/multiformato.py`
- Descompactação cirúrgica in-memory de `.zip` (`ZipFile.infolist()`)
- Gatekeeper Anti-Lixo (>= 800 chars úteis + bloqueio regex de comprovantes de e-mail)
- Materialização em PDF nativo compatível com `src/inspect_pdf.py` e `src/parsers/pdf_to_text.py`
- Prioridade da Whitelist Técnica em `src/utils.py` (`filtro_pre_download_dom`)
- Ignorar fichas sintéticas legadas em `carregar_obras_concluidas`
- Bloqueio da geração de fichas FPDF sintéticas em produção (`src/extractors/tecnicos.py`)
"""

from __future__ import annotations

import csv
import io
from pathlib import Path
import tempfile
import unittest
import zipfile

import docx
from fpdf import FPDF

from src.extractors.tecnicos import (
    coletar_relatorio_codevasf,
    coletar_relatorio_simec,
)
from src.inspect_pdf import avaliar_pdf
from src.multiformato import (
    ingerir_payload_multiformato,
    inspecionar_e_extrair_zip_in_memory,
    materializar_documento_aprovado_em_pdf,
    processar_bytes_documento,
)
from src.parsers.pdf_to_text import processar_pdf
from src.utils import (
    carregar_obras_concluidas,
    eh_ficha_sintetica_legada,
    filtro_pre_download_dom,
)


TEXTO_TECNICO_DENSO = (
    "MINISTÉRIO DAS CIDADES - CAIXA ECONÔMICA FEDERAL - PARECER TÉCNICO DE ENGENHARIA E TERMO ADITIVO.\n"
    "Em vistoria técnica realizada na obra de pavimentação e drenagem pluvial referente ao Contrato de Repasse, "
    "constatou-se a paralisação temporária das frentes de serviço em decorrência de interferências não previstas "
    "na rede subterrânea de abastecimento e necessidade de revisão do projeto executivo de fundações.\n"
    "A contratada apresentou memorial justificativo detalhando o desequilíbrio econômico-financeiro de insumos "
    "asfálticos e solicitou reprogramação do cronograma físico-financeiro por mais 180 dias corridos.\n"
    "A fiscalização municipal atestou a execução física acumulada de 42,5% dos serviços medidos e recomendou "
    "a celebração de termo aditivo de prazo condicionado à apresentação das novas composições analíticas SINAPI/SICRO "
    "e à regularização das licenças ambientais junto ao órgão estadual competente.\n"
    "Conclui-se pela viabilidade técnica do ajuste do plano de trabalho, mantendo-se a funcionalidade integral "
    "do objeto pactuado com recursos federais da União."
) * 2


def _gerar_docx_bytes(texto: str) -> bytes:
    buf = io.BytesIO()
    d = docx.Document()
    for p in texto.split("\n"):
        if p.strip():
            d.add_paragraph(p.strip())
    d.save(buf)
    return buf.getvalue()


def _gerar_odt_bytes(texto: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("mimetype", "application/vnd.oasis.opendocument.text")
        paragrafos_xml = "".join(
            f"<text:p>{p.strip()}</text:p>" for p in texto.split("\n") if p.strip()
        )
        content_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
            'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">'
            f"<office:body><office:text>{paragrafos_xml}</office:text></office:body>"
            "</office:document-content>"
        )
        zf.writestr("content.xml", content_xml.encode("utf-8"))
    return buf.getvalue()


def _gerar_pdf_bytes(texto: str) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=10)
    pdf.multi_cell(0, 6, text=texto.encode("latin-1", errors="replace").decode("latin-1"))
    return bytes(pdf.output())


class TestMultiformatoProducao(unittest.TestCase):
    def test_whitelist_prioritaria_evita_falsos_negativos(self) -> None:
        casos_vitais = [
            "Publicação do Contrato nº 12/2024 no DOU",
            "Despacho Decisório de Paralisação e Termo Aditivo",
            "Notificação de Rescisão Contratual por Inexecução",
            "Comprovante de Vistoria e Parecer Técnico de Engenharia",
            "Memorial Descritivo e Projeto Básico Compactado.zip",
        ]
        for titulo in casos_vitais:
            ok, motivo = filtro_pre_download_dom(titulo)
            self.assertTrue(ok, f"Deveria aprovar documento vital '{titulo}', mas retornou {motivo}")
            self.assertTrue(motivo.startswith("WHITELIST"), f"Deveria acionar WHITELIST em '{titulo}': {motivo}")

    def test_docx_odt_rtf_materializados_em_pdf_nativo_compativel(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            docx_bytes = _gerar_docx_bytes(TEXTO_TECNICO_DENSO)
            odt_bytes = _gerar_odt_bytes(TEXTO_TECNICO_DENSO)
            rtf_bytes = (
                "{\\rtf1\\ansi\\deff0\n" + TEXTO_TECNICO_DENSO.replace("\n", "\\par\n") + "}"
            ).encode("utf-8")

            for ext, raw in (("docx", docx_bytes), ("odt", odt_bytes), ("rtf", rtf_bytes)):
                doc_proc = processar_bytes_documento(raw, f"parecer_engenharia.{ext}")
                self.assertTrue(doc_proc.aprovado_gatekeeper, f"Falhou para {ext}: {doc_proc.motivo_gatekeeper}")
                self.assertGreaterEqual(doc_proc.chars_uteis_corridos, 800)

                pdf_out = tmp_dir / f"convertido_{ext}.pdf"
                ok = materializar_documento_aprovado_em_pdf(doc_proc, pdf_out)
                self.assertTrue(ok)
                self.assertTrue(pdf_out.exists())

                # Verifica compatibilidade com inspect_pdf.py e pdf_to_text.py
                aval = avaliar_pdf(pdf_out)
                self.assertIn(aval["validation"]["result"], ("VALIDADO", "VALIDADO_COM_RESSALVAS"))
                res_ext = processar_pdf(pdf_out)
                self.assertGreaterEqual(res_ext.total_chars, 800)

    def test_zip_in_memory_ignora_dwg_jpg_xlsx_e_extrai_texto_rico(self) -> None:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("plantas/prancha_01.dwg", b"AC1027_DWG_BINARIO_PESADO" * 500)
            zf.writestr("fotos/vistoria_01.jpg", b"\xff\xd8\xff\xe0JFIF_IMAGEM" * 200)
            zf.writestr("orcamento/planilha.xlsx", b"PK_FAKE_XLSX" * 100)
            zf.writestr("documentos/Memorial_Descritivo.pdf", _gerar_pdf_bytes(TEXTO_TECNICO_DENSO))
            zf.writestr("documentos/Parecer_Tecnico.docx", _gerar_docx_bytes(TEXTO_TECNICO_DENSO))

        docs, insp = ingerir_payload_multiformato(buf.getvalue(), "Pasta_Tecnica_Obra.pdf")
        self.assertIsNotNone(insp)
        assert insp is not None
        self.assertEqual(len(insp.entradas_ignoradas_engenharia_midia), 3)
        self.assertEqual(len(insp.entradas_texto_rico_extraidas), 2)
        aprovados = [d for d in docs if d.aprovado_gatekeeper]
        self.assertEqual(len(aprovados), 2)

    def test_gatekeeper_bloqueia_comprovante_email(self) -> None:
        texto_email = (
            "De: fiscalizacao@prefeitura.gov.br\n"
            "Para: gigov@caixa.gov.br\n"
            "Assunto: Encaminha documentos de medição\n"
            "Enviado em: segunda-feira, 12 de maio de 2025 14:32\n\n"
            + ("Prezado gerente, encaminhamos em anexo os comprovantes solicitados para análise administrativa. " * 15)
        )
        pdf_email = _gerar_pdf_bytes(texto_email)
        doc_proc = processar_bytes_documento(pdf_email, "comprovante.pdf")
        self.assertFalse(doc_proc.aprovado_gatekeeper)
        self.assertTrue(doc_proc.eh_email_bloqueado)

    def test_ignora_fichas_sinteticas_no_cache_e_desativa_gerador_fpdf(self) -> None:
        self.assertTrue(eh_ficha_sintetica_legada("SISMOB_12345_FichaTecnica_Saude.pdf"))
        self.assertTrue(eh_ficha_sintetica_legada("SIMEC_999_FichaTecnica_FNDE.pdf"))
        self.assertFalse(eh_ficha_sintetica_legada("SISMOB_12345_JustificativaOficial_API.pdf"))
        self.assertFalse(eh_ficha_sintetica_legada("CAIXA_882211_PARECER_1.pdf"))

        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            csv_path = tmp_dir / "log_coleta.csv"
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["timestamp", "base_de_dados", "id_obra", " nome_arquivo", "status_validacao"])
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(
                    f,
                    fieldnames=["timestamp", "base_de_dados", "id_obra", "nome_arquivo", "status_validacao"],
                )
                w.writeheader()
                w.writerow({
                    "timestamp": "2026-01-01",
                    "base_de_dados": "SIMEC",
                    "id_obra": "1001",
                    "nome_arquivo": "SIMEC_1001_FichaTecnica_FNDE.pdf",
                    "status_validacao": "VALIDADO",
                })
                w.writerow({
                    "timestamp": "2026-01-01",
                    "base_de_dados": "CAIXA",
                    "id_obra": "2002",
                    "nome_arquivo": "CAIXA_2002_PARECER_1.pdf",
                    "status_validacao": "VALIDADO",
                })

            concluidas = carregar_obras_concluidas(csv_path, ignorar_fichas_sinteticas=True)
            self.assertNotIn(("simec", "1001"), concluidas)
            self.assertIn(("caixa", "2002"), concluidas)

            # Verifica que os adaptadores SIMEC e CODEVASF não geram FPDF sintético por padrão
            res_simec = coletar_relatorio_simec({"id": "1001", "empreendimento": "Escola"}, tmp_dir, set())
            res_codevasf = coletar_relatorio_codevasf({"id": "3003", "empreendimento": "Ponte"}, tmp_dir, set())
            self.assertEqual(res_simec, [])
            self.assertEqual(res_codevasf, [])

    def test_normalizacao_num_instrumento_e_reuso_cross_ano_2022(self) -> None:
        from src.main import _limpar_num_instrumento, _obter_fontes_cross_ano

        self.assertEqual(_limpar_num_instrumento("676829.0"), "676829")
        self.assertEqual(_limpar_num_instrumento("nan"), "")
        self.assertEqual(_limpar_num_instrumento(None), "")

        pdf_fake = Path("CAIXA_676829_PARECER_1.pdf")
        indice = {
            ("caixa", "CAIXA-421239"): [pdf_fake],
            ("caixa:inst", "676829"): [pdf_fake],
            ("simec:inst", "657664"): [Path("SIMEC_657664_TA_1.pdf")],
        }
        # 2022 CAIXA com 8 dígitos ("CAIXA-42123974") casa automaticamente com "CAIXA-421239"
        self.assertEqual(
            _obter_fontes_cross_ano("caixa", "CAIXA-42123974", "676829.0", indice),
            [pdf_fake],
        )
        # SIMEC com barra ("657664/2009") casa pelo número base do convênio ("657664")
        self.assertEqual(
            len(_obter_fontes_cross_ano("simec", "SIMEC-999999", "657664/2009", indice)),
            1,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
