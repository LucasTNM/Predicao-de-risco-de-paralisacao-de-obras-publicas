# -*- coding: utf-8 -*-
"""
tests/test_integration_pipeline.py
==================================
Teste de integração ponta a ponta simulando o fluxo de download concorrente,
buffer temporário, bloqueio pré-download, poda de baixa densidade e gravação
no log de coleta em arquivo CSV temporário.
"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import unittest
import pandas as pd
import requests
from unittest.mock import MagicMock, patch
from fpdf import FPDF

from src.utils import (
    inicializar_log_csv,
    carregar_chaves_log_existentes,
    carregar_obras_concluidas,
    validar_e_registrar_pdf,
    filtro_pre_download_dom,
    verificar_duplicata_sha256,
    validar_densidade_textual,
)
from src.extractors.pncp import coletar_obra_pncp


def criar_pdf(caminho: Path, texto: str) -> Path:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(0, 10, text=texto)
    pdf.output(str(caminho))
    return caminho


class TestPipelineIntegrado(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root_path = Path(self.temp_dir.name)
        self.drive_path = self.root_path / "DriveMock"
        self.drive_path.mkdir(parents=True, exist_ok=True)
        self.csv_log = self.drive_path / "log_coleta.csv"
        inicializar_log_csv(self.csv_log)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_fluxo_completo_com_bloqueios_e_poda(self):
        """Simula um lote de 4 documentos de uma obra para testar as 3 barreiras e persistência."""
        cache_log = carregar_chaves_log_existentes(self.csv_log)
        cache_hashes: dict[str, set[str]] = {}
        id_obra = "102030"
        pasta_obra = self.drive_path / "DNIT"
        pasta_obra.mkdir(parents=True, exist_ok=True)

        # 1. Simula Doc 1: "Comprovante de Publicação" -> Rejeitado na Barreira 1 (DOM/API)
        pode_baixar_1, motivo_1 = filtro_pre_download_dom("Comprovante de Publicação no DOU")
        self.assertFalse(pode_baixar_1)
        self.assertIn("comprovante", motivo_1.lower())

        # 2. Simula Doc 2: "Edital Completo" (denso) -> Aprovado nas 3 barreiras e persistido
        texto_edital = (
            "EDITAL DE LICITAÇÃO PÚBLICA NACIONAL Nº 01/2024 - DNIT. "
            "OBJETO: EXECUÇÃO DE OBRAS DE RESTAURAÇÃO RODOVIÁRIA NA BR-101/SC. "
            "REGIME DE EXECUÇÃO: EMPREITADA POR PREÇO GLOBAL CONFORME LEI FEDERAL 14.133/2021. "
            "PROJETO BÁSICO E PLANILHA ORÇAMENTÁRIA ANEXOS AO PRESENTE INSTRUMENTO CONVOCATÓRIO. "
            "FISCALIZAÇÃO A CARGO DA SUPERINTENDÊNCIA REGIONAL DO DNIT."
        ) * 2
        temp_pdf_2 = self.root_path / "temp_edital.pdf"
        criar_pdf(temp_pdf_2, texto_edital)

        pode_baixar_2, _ = filtro_pre_download_dom("Edital de Licitação")
        self.assertTrue(pode_baixar_2)

        eh_dup_2, _ = verificar_duplicata_sha256(temp_pdf_2, id_obra, cache_hashes)
        self.assertFalse(eh_dup_2)

        aprov_dens_2, chars_2, _ = validar_densidade_textual(temp_pdf_2)
        self.assertTrue(aprov_dens_2)

        # Mover para destino e registrar no log
        dest_2 = pasta_obra / "DNIT_2024_01_1_edital.pdf"
        temp_pdf_2.replace(dest_2)

        res_2 = validar_e_registrar_pdf(
            caminho_pdf=dest_2,
            base_nome="DNIT",
            id_obra=id_obra,
            num_inst="01/2024",
            emp="Restauração BR-101",
            obs_extra="Teste",
            cache_log=cache_log,
            caminho_csv=self.csv_log,
        )
        self.assertIn(res_2["validation"]["result"], ("VALIDADO", "VALIDADO_COM_RESSALVAS"))

        # 3. Simula Doc 3: "Outros Documentos" (cópia idêntica do Edital) -> Rejeitado na Barreira 2 (SHA-256)
        temp_pdf_3 = self.root_path / "temp_duplicata.pdf"
        criar_pdf(temp_pdf_3, texto_edital)

        eh_dup_3, hash_3 = verificar_duplicata_sha256(temp_pdf_3, id_obra, cache_hashes)
        self.assertTrue(eh_dup_3, "Mesmo conteúdo SHA-256 deve ser barrado como duplicata")
        temp_pdf_3.unlink()  # Poda de duplicata sem gravar no Drive

        # 4. Simula Doc 4: "Despacho de 1 linha" -> Rejeitado na Barreira 3 (Densidade < 300 chars)
        temp_pdf_4 = self.root_path / "temp_despacho.pdf"
        criar_pdf(temp_pdf_4, "Ciente. Encaminhe-se ao setor financeiro.")

        pode_baixar_4, _ = filtro_pre_download_dom("Nota Informativa")
        self.assertTrue(pode_baixar_4)

        eh_dup_4, _ = verificar_duplicata_sha256(temp_pdf_4, id_obra, cache_hashes)
        self.assertFalse(eh_dup_4)

        aprov_dens_4, chars_4, _ = validar_densidade_textual(temp_pdf_4)
        self.assertFalse(aprov_dens_4, f"Despacho de {chars_4} caracteres deve ser rejeitado")
        temp_pdf_4.unlink()  # Poda sem gravar no Drive

        # 5. Verifica integridade do Log e Cache
        obras_concluidas = carregar_obras_concluidas(self.csv_log)
        self.assertIn(("dnit", id_obra), obras_concluidas)

        # Apenas 1 arquivo deve existir na pasta de destino (o edital rico)
        arquivos_salvos = list(pasta_obra.glob("*.pdf"))
        self.assertEqual(len(arquivos_salvos), 1)
        self.assertEqual(arquivos_salvos[0].name, "DNIT_2024_01_1_edital.pdf")


if __name__ == "__main__":
    unittest.main(verbosity=2)
