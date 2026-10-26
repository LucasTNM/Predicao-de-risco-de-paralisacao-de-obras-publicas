# -*- coding: utf-8 -*-
"""
src/modeling/bertimbau_lora.py
==============================
Setup do modelo BERTimbau cased com adaptadores LoRA (PEFT) e cabeça de classificação (Feature 020).

Garante:
1. Carregamento do BERTimbau cased oficial ('neuralmind/bert-base-portuguese-cased').
2. Congelamento total dos parâmetros da rede base.
3. Acoplamento de adaptadores LoRA nos módulos de atenção ('query', 'value').
4. Menos de 2% de parâmetros treináveis (< 2,2M sobre ~110M totais).
5. Configuração para Detector Binário de Risco (0: Regular vs 1: Em Risco).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import torch
import torch.nn as nn
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from peft import LoraConfig, TaskType, get_peft_model, PeftModel

BERTIMBAU_MODEL_NAME: str = "neuralmind/bert-base-portuguese-cased"


def get_bertimbau_tokenizer(model_name: str = BERTIMBAU_MODEL_NAME) -> AutoTokenizer:
    """Carrega o tokenizer oficial do BERTimbau cased."""
    return AutoTokenizer.from_pretrained(model_name)


def create_bertimbau_lora_classifier(
    model_name: str = BERTIMBAU_MODEL_NAME,
    num_labels: int = 2,
    r: int = 16,
    lora_alpha: int = 32,
    lora_dropout: float = 0.1,
    target_modules: Optional[List[str]] = None,
    device: Optional[torch.device | str] = None,
) -> Tuple[PeftModel, AutoTokenizer]:
    """
    Inicializa o BERTimbau cased com cabeça de classificação e adaptadores LoRA acoplados.
    Todos os parâmetros do transformer base são congelados.
    """
    if target_modules is None:
        target_modules = ["query", "value"]

    # 1. Carregar modelo base com cabeça de classificação
    base_model = AutoModelForSequenceClassification.from_pretrained(
        model_name,
        num_labels=num_labels,
    )

    # 2. Configurar adaptadores LoRA para classificação de sequência
    lora_config = LoraConfig(
        task_type=TaskType.SEQ_CLS,
        r=r,
        lora_alpha=lora_alpha,
        lora_dropout=lora_dropout,
        target_modules=target_modules,
        bias="none",
    )

    # 3. Aplicar PEFT e congelar o backbone
    peft_model = get_peft_model(base_model, lora_config)

    if device is not None:
        peft_model = peft_model.to(device)

    tokenizer = get_bertimbau_tokenizer(model_name)
    return peft_model, tokenizer


def get_trainable_parameter_stats(model: nn.Module) -> Dict[str, Any]:
    """
    Calcula o total de parâmetros, parâmetros treináveis e a porcentagem treinável.
    Garante rastreabilidade e auditoria (meta: < 2.0%).
    """
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    trainable_pct = (trainable_params / total_params) * 100 if total_params > 0 else 0.0

    return {
        "total_parameters": total_params,
        "trainable_parameters": trainable_params,
        "frozen_parameters": total_params - trainable_params,
        "trainable_percentage": round(trainable_pct, 4),
        "meets_lightweight_criteria": trainable_pct < 2.0,
    }
