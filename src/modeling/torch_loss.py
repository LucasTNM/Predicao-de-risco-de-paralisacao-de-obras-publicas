# -*- coding: utf-8 -*-
"""
src/modeling/torch_loss.py
==========================
Fábrica de funções de perda ponderadas no PyTorch para tratamento de assimetria extrema (Card Balanceamento).

Vincula analiticamente as funções de perda do PyTorch aos pesos de classe de treino
garantindo penalização estrita de erros na classe minoritária de risco.
"""

from __future__ import annotations

from typing import Dict, Optional
import numpy as np
import torch
import torch.nn as nn

from src.modeling.loader import compute_class_weights


def compute_binary_scale_pos_weight(y_binary: np.ndarray) -> float:
    """
    Calcula a razão scale_pos_weight = n_negativos / n_positivos
    para binarização de risco (0: Regular vs 1: Em Risco).
    """
    n_neg = int(np.sum(y_binary == 0))
    n_pos = int(np.sum(y_binary == 1))
    if n_pos == 0:
        return 1.0
    return float(n_neg / n_pos)


def create_binary_risk_loss(
    y_binary: np.ndarray,
    device: Optional[torch.device | str] = None,
) -> nn.BCEWithLogitsLoss:
    """
    Cria uma função BCEWithLogitsLoss com pos_weight calibrado estritamente
    sobre os rótulos binários de treino fornecidos.
    """
    scale = compute_binary_scale_pos_weight(y_binary)
    pos_weight_tensor = torch.tensor([scale], dtype=torch.float32)
    if device is not None:
        pos_weight_tensor = pos_weight_tensor.to(device)
    return nn.BCEWithLogitsLoss(pos_weight=pos_weight_tensor)


def create_weighted_cross_entropy_loss(
    y: np.ndarray,
    num_classes: int = 2,
    device: Optional[torch.device | str] = None,
) -> nn.CrossEntropyLoss:
    """
    Cria uma função CrossEntropyLoss com tensor de pesos calculado analiticamente
    pela fórmula balanceada N / (K * N_c), idêntica à do Scikit-Learn e LightGBM.
    """
    cw = compute_class_weights(y, num_classes=num_classes)
    weights_list = [cw[c] for c in range(num_classes)]
    weights_tensor = torch.tensor(weights_list, dtype=torch.float32)
    if device is not None:
        weights_tensor = weights_tensor.to(device)
    return nn.CrossEntropyLoss(weight=weights_tensor)
