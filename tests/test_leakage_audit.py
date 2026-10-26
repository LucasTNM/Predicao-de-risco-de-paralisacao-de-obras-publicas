# -*- coding: utf-8 -*-
"""Testes unitarios para o modulo de auditoria de vazamento de alvo."""
from unittest.mock import MagicMock
import pytest
from src.dataset.leakage_audit import get_leakage_distribution, get_leakage_terms


def test_get_leakage_distribution_parser():
    """Valida o mapeamento de tuplas retornadas do banco para dicionario."""
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchall.return_value = [
        (0, 16649, 9761, 6478, 0, 410),
        (1, 978, 966, 1, 0, 11),
        (2, 104, 12, 91, 0, 1),
        (3, 423, 0, 423, 0, 0),
    ]

    res = get_leakage_distribution(mock_conn)
    assert len(res) == 4
    assert res[0]["label_risco"] == 0
    assert res[0]["total"] == 16649
    assert res[0]["sem_docs"] == 9761
    assert res[1]["label_risco"] == 1
    assert res[1]["sem_docs"] == 966
    assert res[2]["so_ficha"] == 91
    assert res[3]["so_ficha"] == 423


def test_get_leakage_terms_parser():
    """Valida o mapeamento de termos de vazamento retornados do banco."""
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchall.return_value = [
        (0, 6478, 2, 4859, 2836),
        (1, 1, 1, 0, 0),
        (2, 91, 91, 0, 8),
        (3, 423, 423, 0, 127),
    ]

    res = get_leakage_terms(mock_conn)
    assert len(res) == 4
    assert res[0]["com_paralisad"] == 2
    assert res[2]["com_paralisad"] == 91
    assert res[3]["com_paralisad"] == 423
