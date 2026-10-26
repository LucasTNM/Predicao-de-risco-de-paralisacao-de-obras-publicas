# -*- coding: utf-8 -*-
"""
tests/test_torch_loss.py
========================
Testes unitários para o módulo de funções de perda ponderadas no PyTorch (Feature 020).
"""

import numpy as np
import pytest

try:
    import torch
    import torch.nn as nn
    from src.modeling.torch_loss import (
        compute_binary_scale_pos_weight,
        create_binary_risk_loss,
        create_weighted_cross_entropy_loss,
    )
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False


@pytest.mark.skipif(not HAS_TORCH, reason="PyTorch não disponível neste ambiente")
def test_binary_scale_pos_weight():
    # 90 regulares (0) e 10 paralisadas (1) -> escala deve ser 9.0
    y_bin = np.array([0] * 90 + [1] * 10, dtype=np.int32)
    scale = compute_binary_scale_pos_weight(y_bin)
    assert scale == 9.0

    loss_fn = create_binary_risk_loss(y_bin)
    assert isinstance(loss_fn, nn.BCEWithLogitsLoss)
    assert float(loss_fn.pos_weight.item()) == 9.0


@pytest.mark.skipif(not HAS_TORCH, reason="PyTorch não disponível neste ambiente")
def test_weighted_cross_entropy_equivalence():
    from src.modeling.loader import compute_class_weights

    # Vetor com 3 classes: 100 de 0, 10 de 1, 5 de 2 (N = 115)
    y = np.array([0] * 100 + [1] * 10 + [2] * 5, dtype=np.int32)
    loss_fn = create_weighted_cross_entropy_loss(y, num_classes=3)
    assert isinstance(loss_fn, nn.CrossEntropyLoss)

    expected_cw = compute_class_weights(y, num_classes=3)
    actual_weights = loss_fn.weight.tolist()

    for c in range(3):
        assert abs(actual_weights[c] - expected_cw[c]) < 1e-5


@pytest.mark.skipif(not HAS_TORCH, reason="PyTorch não disponível neste ambiente")
def test_loss_penalizes_false_negatives_more_than_false_positives():
    # Demonstrar empiricamente que errar um caso positivo (falso negativo)
    # gera uma perda significativamente maior do que errar um caso negativo (falso positivo)
    y_bin = np.array([0] * 90 + [1] * 10, dtype=np.int32)
    loss_fn = create_binary_risk_loss(y_bin)

    # Caso 1: Rótulo real = 1 (Risco), modelo predisse logits = -2.0 (Falso Negativo)
    loss_fn_fn = loss_fn(torch.tensor([-2.0]), torch.tensor([1.0]))

    # Caso 2: Rótulo real = 0 (Regular), modelo predisse logits = +2.0 (Falso Positivo)
    loss_fp = loss_fn(torch.tensor([2.0]), torch.tensor([0.0]))

    # Como pos_weight = 9.0, o erro no positivo é severamente mais penalizado
    assert float(loss_fn_fn.item()) > float(loss_fp.item())
