# -*- coding: utf-8 -*-
"""
tests/test_bertimbau_lora.py
============================
Testes unitários para a arquitetura BERTimbau + LoRA (Feature 020).
"""

import pytest

try:
    import torch
    import torch.nn as nn
    from src.modeling.bertimbau_lora import (
        create_bertimbau_lora_classifier,
        get_trainable_parameter_stats,
    )
    HAS_TORCH_PEFT = True
except ImportError:
    HAS_TORCH_PEFT = False


@pytest.mark.skipif(not HAS_TORCH_PEFT, reason="PyTorch/PEFT não disponíveis neste ambiente")
def test_trainable_parameter_stats_mock():
    # Cria rede simples com 1 camada congelada e 1 treinável
    class DummyNet(nn.Module):
        def __init__(self):
            super().__init__()
            self.fc1 = nn.Linear(100, 100)
            self.fc2 = nn.Linear(100, 1)
            for p in self.fc1.parameters():
                p.requires_grad = False

    model = DummyNet()
    stats = get_trainable_parameter_stats(model)
    assert stats["total_parameters"] == 100 * 100 + 100 + 100 * 1 + 1  # 10100 + 101 = 10201
    assert stats["trainable_parameters"] == 101
    assert stats["meets_lightweight_criteria"] is True
    assert stats["trainable_percentage"] < 1.0


@pytest.mark.skipif(not HAS_TORCH_PEFT, reason="PyTorch/PEFT não disponíveis neste ambiente")
def test_bertimbau_lora_initialization_and_trainable_fraction():
    """Garante que o BERTimbau + LoRA possui menos de 2% de parâmetros treináveis."""
    # Carrega com r=8 para teste rápido
    model, tokenizer = create_bertimbau_lora_classifier(
        num_labels=2,
        r=8,
        lora_alpha=16,
        target_modules=["query", "value"],
        device="cpu",
    )

    stats = get_trainable_parameter_stats(model)
    assert stats["meets_lightweight_criteria"] is True
    assert stats["trainable_percentage"] < 2.0
    print(f"Parâmetros treináveis: {stats['trainable_parameters']:,} / {stats['total_parameters']:,} ({stats['trainable_percentage']}%)")

    # Testa forward pass com dummy input
    inputs = tokenizer(
        ["Texto de teste da obra", "Outro documento de teste"],
        padding=True,
        truncation=True,
        max_length=32,
        return_tensors="pt",
    )
    outputs = model(**inputs)
    assert hasattr(outputs, "logits")
    assert outputs.logits.shape == (2, 2)
