# -*- coding: utf-8 -*-
"""
tests/test_curadoria_nlp.py
===========================
Bateria de testes automatizados para validar as 3 barreiras de curadoria NLP
e a integridade do pipeline de coleta:
1. Barreira 1: Filtro Pré-Download DOM (Whitelist & Blacklist)
2. Barreira 2: Deduplicação Criptográfica In-Memory (SHA-256 por id_obra)
3. Barreira 3: Poda de Baixa Densidade Textual (Heurística Pós-Download)
4. Teste Integrado: Simulação de Coleta PNCP com Buffer Temporário
"""

import os
from pathlib import Path
import tempfile
import unittest
from fpdf import FPDF

from src.utils import (
    filtro_pre_download_dom,
    verificar_duplicata_sha256,
    validar_densidade_textual,
    arquivo_ja_existe_valido,
    _WHITELIST_TERMOS,
    _BLACKLIST_TERMOS,
)


def criar_pdf_teste(caminho: Path, conteudo_texto: str, paginas: int = 1) -> Path:
    """Cria um PDF sintético para testes com conteúdo e páginas controladas."""
    pdf = FPDF()
    for _ in range(paginas):
        pdf.add_page()
        pdf.set_font("Helvetica", size=12)
        pdf.multi_cell(0, 10, text=conteudo_texto)
    pdf.output(str(caminho))
    return caminho


class TestBarreira1FiltroDOM(unittest.TestCase):
    """Testa a Barreira 1: Filtro pré-download no DOM/HTML e metadados."""

    def test_whitelist_aprovados(self):
        amostras_validas = [
            "EDITAL DE LICITAÇÃO Nº 01/2024",
            "TERMO DE REFERÊNCIA PARA CONTRATAÇÃO DE OBRAS",
            "PROJETO BÁSICO DE ENGENHARIA - DRENAGEM",
            "CONTRATO ADMINISTRATIVO Nº 45/2023",
            "MATRIZ DE RISCO E MAPA DE PROBABILIDADES",
            "ESTUDO TÉCNICO PRELIMINAR - ETP",
            "TERMO ADITIVO Nº 02 AO CONVÊNIO",
            "Planilha Orçamentária Detalhada",
        ]
        for texto in amostras_validas:
            aprovado, motivo = filtro_pre_download_dom(texto)
            self.assertTrue(aprovado, f"Deveria aprovar: '{texto}', mas retornou {motivo}")

    def test_blacklist_rejeitados(self):
        amostras_ruido = [
            "E-mail de confirmação de envio",
            "Comprovante de publicação no DOU",
            "Despacho de encaminhamento de processo",
            "Recibo de entrega de documentos",
            "Notificação extrajudicial de prazo",
            "Leitura de mensagem protocolada",
            "ENC: Reencaminhamento de ofício",
            "FW: Confirmação de recebimento",
        ]
        for texto in amostras_ruido:
            aprovado, motivo = filtro_pre_download_dom(texto)
            self.assertFalse(aprovado, f"Deveria BLOQUEAR: '{texto}', mas foi aprovado com {motivo}")
            self.assertTrue(motivo.startswith("BLACKLIST"), f"Motivo deveria indicar blacklist: {motivo}")


class TestBarreira2DedupSHA256(unittest.TestCase):
    """Testa a Barreira 2: Deduplicação SHA-256 em memória por obra."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_deduplicacao_mesma_obra(self):
        cache_hashes: dict[str, set[str]] = {}
        id_obra = "OBRA_TESTE_001"

        # Arquivo 1
        pdf1 = self.dir_path / "edital_v1.pdf"
        criar_pdf_teste(pdf1, "Conteúdo Idêntico do Edital 12345")

        # Arquivo 2 (mesmo conteúdo, nome diferente)
        pdf2 = self.dir_path / "outros_documentos.pdf"
        criar_pdf_teste(pdf2, "Conteúdo Idêntico do Edital 12345")

        # 1ª verificação: Deve ser NOVO (não duplicata)
        eh_dup1, hash1 = verificar_duplicata_sha256(pdf1, id_obra, cache_hashes)
        self.assertFalse(eh_dup1, "Primeiro arquivo não pode ser duplicata")
        self.assertTrue(len(hash1) == 64, "Hash SHA-256 deve ter 64 caracteres hex")

        # 2ª verificação: Deve ser detectado como DUPLICATA
        eh_dup2, hash2 = verificar_duplicata_sha256(pdf2, id_obra, cache_hashes)
        self.assertTrue(eh_dup2, "Segundo arquivo idêntico DEVE ser detectado como duplicata")
        self.assertEqual(hash1, hash2, "Hashes devem ser rigorosamente idênticos")

    def test_obras_distintas_permitem_mesmo_hash(self):
        cache_hashes: dict[str, set[str]] = {}
        pdf = self.dir_path / "doc.pdf"
        criar_pdf_teste(pdf, "Minuta padronizada nacional")

        eh_dup_obra1, _ = verificar_duplicata_sha256(pdf, "OBRA_A", cache_hashes)
        eh_dup_obra2, _ = verificar_duplicata_sha256(pdf, "OBRA_B", cache_hashes)

        self.assertFalse(eh_dup_obra1)
        self.assertFalse(eh_dup_obra2, "Obra B deve poder ter o mesmo documento sem colisão entre obras")


class TestBarreira3PodaDensidade(unittest.TestCase):
    """Testa a Barreira 3: Poda de baixa densidade (< 300 chars ou sem texto)."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_pdf_baixa_densidade_descartado(self):
        pdf_curto = self.dir_path / "despacho_curto.pdf"
        # Despacho de poucas palavras (< 300 caracteres)
        criar_pdf_teste(pdf_curto, "Ao setor competente para ciência e providências cabíveis. Brasília, 10/02/2024.")

        aprovado, chars, extraivel = validar_densidade_textual(pdf_curto)
        self.assertFalse(aprovado, f"PDF com {chars} caracteres DEVE ser podado (< 300)")
        self.assertTrue(extraivel, "Texto era extraível, mas densidade era insuficiente")
        self.assertLess(chars, 300)

    def test_pdf_alta_densidade_aprovado(self):
        pdf_longo = self.dir_path / "edital_completo.pdf"
        texto_denso = (
            "ESTADO DE MINAS GERAIS - PREFEITURA MUNICIPAL - EDITAL DE CONCORRÊNCIA PÚBLICA Nº 05/2024. "
            "OBJETO: CONTRATAÇÃO DE EMPRESA DE ENGENHARIA PARA EXECUÇÃO DAS OBRAS DE PAVIMENTAÇÃO ASFÁLTICA, "
            "DRENAGEM PLUVIAL, SINALIZAÇÃO VIÁRIA E ACESSIBILIDADE URBANA NO MUNICÍPIO. "
            "VALOR ESTIMADO: R$ 4.500.000,00 (QUATRO MILHÕES E QUINHENTOS MIL REAIS). "
            "RECURSOS FEDERAIS ORIUNDOS DO MINISTÉRIO DAS CIDADES - CONTRATO DE REPASSE CAIXA ECONÔMICA FEDERAL. "
            "PRAZO DE EXECUÇÃO: 12 (DOZE) MESES CONTADOS DA ORDEM DE SERVIÇO. "
            "DISPOSIÇÕES PRELIMINARES: A PRESENTE LICITAÇÃO SERÁ REGIDA PELA LEI Nº 14.133/2021. "
            "CRITÉRIO DE JULGAMENTO: MENOR PREÇO GLOBAL SOB O REGIME DE EMPREITADA POR PREÇO UNITÁRIO."
        ) * 2  # Garante > 600 caracteres de conteúdo técnico denso
        criar_pdf_teste(pdf_longo, texto_denso, paginas=2)

        aprovado, chars, extraivel = validar_densidade_textual(pdf_longo)
        self.assertTrue(aprovado, f"PDF denso com {chars} caracteres DEVE ser aprovado")
        self.assertTrue(extraivel)
        self.assertGreaterEqual(chars, 300)


if __name__ == "__main__":
    unittest.main(verbosity=2)
