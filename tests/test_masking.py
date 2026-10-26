# -*- coding: utf-8 -*-
"""Testes unitarios para o modulo de mascaramento deterministico de fichas sinteticas."""
import pytest
from src.dataset.masking import (
    mask_synthetic_sheet_text,
    audit_masked_text_for_target_leakage,
)


SAMPLE_RAW_SHEET_PARALISADA = """MINISTÉRIO DA EDUCAÇÃO - FNDE
SIMEC - Sistema Integrado de Monitoramento Execução e Controle
Relatório Técnico de Fiscalização de Obras da Educação (PAR)
Identificador SIMEC: SESU-10594
Termo de Compromisso / PAR: nan
Empreendimento: UFVJM - Restaurante Universitário
Localização / Município: Diamantina/MG
Órgão Concedente: Ministério da Educação
Situação no FNDE: Paralisada (Origem: PARALISADA)
Evolução Física: 31.9% | Execução Financeira: 44.9%
Valor Previsto: R$ 1,898,382.90 | Valor Repassado: R$ 852,582.03
Laudo e ficha técnica de acompanhamento emitida para auditoria de contratos de engenharia e obras."""


SAMPLE_RAW_SHEET_EXECUCAO = """CODEVASF - COMPANHIA DE DESENVOLVIMENTO DOS VALES
Superintendência Regional / Ministério da Integração Nacional
Instrumento Contratual e Termo de Execução de Obras
Identificador CODEVASF: MIDR-3-778904
Empreendimento: CONSTRUÇÃO DE PASSAGENS MOLHADAS
Local / Estado: Tauá/CE
Órgão Concedente: Ministério da Integração e Desenvolvimento Regional
Situação Contratual: Em execução (Origem: EM EXECUCAO)
Execução Física: 1.0% | Execução Financeira: 36.0%
Valor de Investimento Federal: R$ 2,584,560.65
Valor Desbloqueado: R$ 894,796.73
Instrumento de acompanhamento para controle governamental."""


def test_mask_synthetic_sheet_paralisada():
    """Valida a remocao total da linha de situacao paralisada e boilerplate."""
    masked, spans = mask_synthetic_sheet_text(SAMPLE_RAW_SHEET_PARALISADA)

    # 1. Auditoria de termos proibidos
    assert audit_masked_text_for_target_leakage(masked) is True
    assert "paralisada" not in masked.lower()
    assert "situação no fnde" not in masked.lower()
    assert "laudo e ficha técnica" not in masked.lower()

    # 2. Preservacao de dados legitimos de engenharia
    assert "UFVJM - Restaurante Universitário" in masked
    assert "Diamantina/MG" in masked
    assert "R$ 1,898,382.90" in masked

    # 3. Spans removidos registrados
    assert len(spans) >= 2
    motivos = [s["motivo"] for s in spans]
    assert "vazamento_situacao_alvo" in motivos
    assert "boilerplate_sintetico" in motivos


def test_mask_synthetic_sheet_execucao():
    """Valida a remocao total da situacao em execucao."""
    masked, spans = mask_synthetic_sheet_text(SAMPLE_RAW_SHEET_EXECUCAO)

    assert audit_masked_text_for_target_leakage(masked) is True
    assert "em execução" not in masked.lower()
    assert "situação contratual" not in masked.lower()
    assert "CONSTRUÇÃO DE PASSAGENS MOLHADAS" in masked
    assert "Tauá/CE" in masked


def test_audit_forbidden_terms_detection():
    """Valida que o auditor rejeita textos com termos reveladores e aceita textos limpos."""
    assert audit_masked_text_for_target_leakage("Obra paralisada por falta de verbas") is False
    assert audit_masked_text_for_target_leakage("Contrato em execução normal") is False
    assert audit_masked_text_for_target_leakage("Construção de escola municipal em Diamantina") is True
