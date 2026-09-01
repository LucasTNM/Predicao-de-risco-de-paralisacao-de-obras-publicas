# -*- coding: utf-8 -*-
"""Testes do Card 5: limpeza determinística, LLM mockada e orquestração segura."""

from __future__ import annotations

import csv
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.parsers.limpeza_llm import limpar_texto_camada2
from src.parsers.limpeza_nlp import (
    calcular_score_sujeira,
    limpar_caracteres_especiais,
    limpar_texto_camada1,
    normalizar_encoding,
    remover_cabecalhos_repetidos,
    unificar_quebras_de_linha,
)
from src.parsers.run_higienizacao import (
    carregar_textos_ja_higienizados,
    executar_pipeline_higienizacao,
)


class TestLimpezaCamada1(unittest.TestCase):
    def test_normalizar_encoding(self) -> None:
        texto = normalizar_encoding("Refer�ncia nº 7 para Licita�o e or�amento.")
        self.assertEqual(texto, "Referência nº 7 para Licitação e orçamento.")

    def test_remover_cabecalhos_repetidos(self) -> None:
        cabecalho = "DEPARTAMENTO NACIONAL DE INFRAESTRUTURA DE TRANSPORTES"
        texto = "\n".join([cabecalho, "Primeiro conteúdo", cabecalho, "Segundo conteúdo", cabecalho, cabecalho])
        limpo = remover_cabecalhos_repetidos(texto)
        self.assertNotIn(cabecalho, limpo)
        self.assertIn("Primeiro conteúdo", limpo)
        self.assertIn("Segundo conteúdo", limpo)

    def test_unificar_quebras_linha(self) -> None:
        texto = "O contrato deverá ser executado\nconforme o cronograma aprovado.\n\nNovo parágrafo."
        limpo = unificar_quebras_de_linha(texto)
        self.assertIn("executado conforme o cronograma aprovado.", limpo)
        self.assertIn("\n\nNovo parágrafo.", limpo)

    def test_limpar_caracteres_especiais(self) -> None:
        texto = "Início\n___\n===\n---\n***\nFim"
        self.assertEqual(limpar_caracteres_especiais(texto), "Início\nFim")

    def test_score_sujeira(self) -> None:
        self.assertEqual(calcular_score_sujeira("texto limpo"), 0.0)
        self.assertEqual(calcular_score_sujeira("abc□"), 0.25)
        self.assertGreater(calcular_score_sujeira("A\x00B"), 0.0)

    def test_pipeline_camada1_completo(self) -> None:
        cabecalho = "MINISTÉRIO DA INFRAESTRUTURA"
        bruto = "\n".join([
            cabecalho,
            "Refer�ncia da",
            "licita�o em andamento",
            cabecalho,
            "1.",
            cabecalho,
            "---",
            cabecalho,
        ])
        limpo, score = limpar_texto_camada1(bruto)
        self.assertEqual(limpo, "Referência da licitação em andamento")
        self.assertEqual(score, 0.0)


class _Resposta:
    def __init__(self, texto: str) -> None:
        self.text = texto


class _ClienteGeminiSimulado:
    def __init__(self) -> None:
        self.chunks: list[str] = []

    def generate_content(self, chunk: str, generation_config: dict[str, float]) -> _Resposta:
        self.chunks.append(chunk)
        if generation_config["temperature"] != 0.1:
            raise AssertionError("A temperatura deve ser determinística")
        return _Resposta(f"Aqui está o texto limpo:\n{chunk.upper()}")


class TestLimpezaCamada2(unittest.TestCase):
    def test_prompt_llm_sem_preambulo(self) -> None:
        cliente = _ClienteGeminiSimulado()
        with patch("src.parsers.limpeza_llm._aguardar_rate_limit"):
            resposta = limpar_texto_camada2("texto técnico", cliente=cliente)
        self.assertEqual(resposta, "TEXTO TÉCNICO")
        self.assertNotIn("Aqui está", resposta)
        self.assertEqual(cliente.chunks, ["texto técnico"])


class TestOrquestradorHigienizacao(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.raiz = Path(self.temp_dir.name)
        self.entrada = self.raiz / "2025_Textos_extraidos" / "dnit"
        self.entrada.mkdir(parents=True)
        (self.entrada / "edital.txt").write_text(
            "DNIT\nDNIT\nDNIT\nDNIT\nRefer�ncia\ntexto\ncontinuado",
            encoding="utf-8",
        )
        (self.entrada / "contrato.txt").write_text("1.\nLicita�o\n---", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_idempotencia_cache(self) -> None:
        primeiro = executar_pipeline_higienizacao(
            ano_base="2025",
            base_drive=self.raiz,
            max_workers=2,
            skip_llm=True,
        )["2025"]
        pasta_saida = self.raiz / "2025_Textos_Limpos"
        caminho_csv = pasta_saida / "log_higienizacao.csv"

        self.assertEqual(primeiro.sucesso_camada1, 2)
        self.assertTrue((pasta_saida / "dnit" / "edital.txt").exists())
        self.assertIn("Referência", (pasta_saida / "dnit" / "edital.txt").read_text(encoding="utf-8"))

        cache = carregar_textos_ja_higienizados(caminho_csv)
        self.assertEqual(cache[("2025", "dnit", "edital.txt")], "OK")
        self.assertEqual(len(cache), 2)

        segundo = executar_pipeline_higienizacao(ano_base="2025", base_drive=self.raiz)["2025"]
        self.assertEqual(segundo.pulos_idempotencia, 2)
        self.assertEqual(segundo.processados_lote, 0)

        with caminho_csv.open(encoding="utf-8") as arquivo:
            self.assertEqual(len(list(csv.DictReader(arquivo))), 2)

    def test_force_reprocessa_checkpoint_ok(self) -> None:
        executar_pipeline_higienizacao(ano_base="2025", base_drive=self.raiz, skip_llm=True)
        reprocessado = executar_pipeline_higienizacao(
            ano_base="2025",
            base_drive=self.raiz,
            skip_llm=True,
            force=True,
        )["2025"]
        self.assertEqual(reprocessado.processados_lote, 2)
        with (self.raiz / "2025_Textos_Limpos" / "log_higienizacao.csv").open(encoding="utf-8") as arquivo:
            self.assertEqual(len(list(csv.DictReader(arquivo))), 4)

    def test_persistencia_concorrente_camada1_mantem_manifesto_consistente(self) -> None:
        for indice in range(12):
            (self.entrada / f"lote_{indice:02d}.txt").write_text(
                f"Texto {indice}\\ncontinuado.", encoding="utf-8"
            )

        estatisticas = executar_pipeline_higienizacao(
            ano_base="2025",
            base_drive=self.raiz,
            max_workers=4,
            skip_llm=True,
        )["2025"]
        caminho_csv = self.raiz / "2025_Textos_Limpos" / "log_higienizacao.csv"

        self.assertEqual(estatisticas.processados_lote, 14)
        self.assertEqual(estatisticas.sucesso_camada1, 14)
        self.assertEqual(estatisticas.falhas, 0)
        with caminho_csv.open(encoding="utf-8") as arquivo:
            linhas = list(csv.DictReader(arquivo))
        self.assertEqual(len(linhas), 14)
        self.assertEqual({linha["status"] for linha in linhas}, {"OK"})
        self.assertTrue((self.raiz / "2025_Textos_Limpos" / "dnit" / "lote_11.txt").exists())

    def test_dry_run_nao_grava_saida(self) -> None:
        estatisticas = executar_pipeline_higienizacao(
            ano_base="2025",
            base_drive=self.raiz,
            dry_run=True,
        )["2025"]
        self.assertEqual(estatisticas.processados_lote, 0)
        self.assertFalse((self.raiz / "2025_Textos_Limpos").exists())

    def test_sem_acesso_ao_drive_encerra_sem_excecao(self) -> None:
        with patch("src.parsers.run_higienizacao.Path.is_dir", side_effect=PermissionError("acesso negado")):
            estatisticas = executar_pipeline_higienizacao(ano_base="2025", base_drive=self.raiz)["2025"]
        self.assertEqual(estatisticas.processados_lote, 0)
        self.assertTrue(estatisticas.observacoes)

    def test_fallback_sem_chave_gemini_persiste_camada1(self) -> None:
        (self.entrada / "tabela_degradada.txt").write_text("□" * 40, encoding="utf-8")
        estatisticas = executar_pipeline_higienizacao(
            ano_base="2025",
            base_drive=self.raiz,
            max_workers=1,
        )["2025"]
        self.assertGreaterEqual(estatisticas.candidatos_camada2, 1)
        self.assertGreaterEqual(estatisticas.camada2_indisponivel, 1)
        self.assertTrue((self.raiz / "2025_Textos_Limpos" / "dnit" / "tabela_degradada.txt").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
