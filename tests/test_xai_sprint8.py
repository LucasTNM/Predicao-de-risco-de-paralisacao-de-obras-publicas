# -*- coding: utf-8 -*-
"""
tests/test_xai_sprint8.py
=========================
Testes unitários para o módulo XAI e inferência via Bootstrap da Sprint 8 (Feature 022).
"""

from types import SimpleNamespace
import numpy as np
import torch
import torch.nn as nn

from src.modeling.xai import (
    audit_prohibited_terms_in_top_tokens,
    compute_bootstrap_ci_and_paired_test,
    extract_attention_and_grad_attribution,
    extract_lightgbm_shap_top_features,
    run_deletion_faithfulness_test,
)


class _DummyBertClassifier(nn.Module):
    def __init__(self, vocab_size: int = 50, hidden_dim: int = 16, num_labels: int = 2):
        super().__init__()
        self.emb = nn.Embedding(vocab_size, hidden_dim)
        with torch.no_grad():
            self.emb.weight.fill_(0.05)
            # Token 10 fortement associado à classe 1
            self.emb.weight[10].fill_(2.5)
        self.head = nn.Linear(hidden_dim, num_labels, bias=False)
        with torch.no_grad():
            self.head.weight[0].fill_(-1.0)
            self.head.weight[1].fill_(1.0)

    def get_input_embeddings(self):
        return self.emb

    def forward(self, input_ids, attention_mask=None, output_attentions=False):
        x = self.emb(input_ids)  # (B, L, D)
        if attention_mask is not None:
            x = x * attention_mask.unsqueeze(-1).float()
        pooled = x.mean(dim=1)
        logits = self.head(pooled)
        attentions = None
        if output_attentions:
            b, l = input_ids.shape
            attn = torch.ones((b, 2, l, l), dtype=torch.float32, device=input_ids.device) / float(l)
            attentions = (attn,)
        return SimpleNamespace(logits=logits, attentions=attentions)


class _DummyTokenizer:
    mask_token_id = 4
    pad_token_id = 0

    def convert_ids_to_tokens(self, ids):
        mapping = {0: "[PAD]", 1: "[CLS]", 2: "[SEP]", 4: "[MASK]", 10: "aditivo", 11: "obra", 12: "medicao"}
        return [mapping.get(int(i), f"tok_{i}") for i in ids]


def test_extract_attention_and_grad_and_deletion_faithfulness():
    model = _DummyBertClassifier()
    tokenizer = _DummyTokenizer()
    input_ids = torch.tensor([1, 10, 11, 12, 11, 12, 2, 0], dtype=torch.long)
    attention_mask = torch.tensor([1, 1, 1, 1, 1, 1, 1, 0], dtype=torch.long)

    attr = extract_attention_and_grad_attribution(
        model=model,
        tokenizer=tokenizer,
        input_ids=input_ids,
        attention_mask=attention_mask,
        target_class=1,
        top_k=5,
    )
    assert attr["pred_class"] == 1
    assert attr["top_grad_tokens"][0]["token"] == "aditivo"
    assert abs(sum(t["score"] for t in attr["top_grad_tokens"]) - 1.0) < 1e-4

    del_res = run_deletion_faithfulness_test(
        model=model,
        tokenizer=tokenizer,
        input_ids=input_ids,
        attention_mask=attention_mask,
        target_class=1,
        grad_scores=attr["grad_scores"],
        valid_indices=attr["valid_indices"],
        k_ratio=0.20,
        seed=42,
    )
    assert del_res["k_deleted"] >= 1
    assert del_res["prob_after_topk_deletion"] < del_res["prob_original"]
    assert del_res["drop_topk"] > 0.0


def test_audit_prohibited_terms():
    clean_tokens = [{"token": "termo"}, {"token": "aditivo"}, {"token": "cronograma"}]
    res_clean = audit_prohibited_terms_in_top_tokens(clean_tokens)
    assert res_clean["alerta_vazamento"] is False
    assert res_clean["termos_detectados"] == []

    leaked_tokens = [{"token": "obra"}, {"token": "paralis"}, {"token": "##ada"}]
    res_leaked = audit_prohibited_terms_in_top_tokens(leaked_tokens)
    assert res_leaked["alerta_vazamento"] is True
    assert "paralisad" in res_leaked["termos_detectados"]


def test_bootstrap_ci_and_paired_test():
    y_true = np.array([0, 0, 0, 1, 1, 2, 3] * 20)
    y_ref = np.array([0, 0, 1, 1, 0, 2, 0] * 20)
    y_mod = np.array([0, 0, 0, 1, 1, 2, 3] * 20)

    res = compute_bootstrap_ci_and_paired_test(y_true, y_mod, y_ref, n_bootstraps=100, seed=42)
    assert res["macro_f1_ci95"][0] >= 0.99
    assert res["paired_comparison"]["delta_macro_f1"] > 0.10
    assert res["paired_comparison"]["p_value_macro_f1"] < 0.05


def test_extract_lightgbm_shap_top_features():
    class _FakeBooster:
        def predict(self, X, pred_contrib=False):
            return np.array([[0.1, -0.8, 0.4, 0.05]])  # 3 features + 1 bias

    feats = extract_lightgbm_shap_top_features(
        _FakeBooster(),
        np.array([1.0, 2.0, 3.0]),
        ["f1", "f2", "f3"],
        top_k=2,
    )
    assert len(feats) == 2
    assert feats[0]["feature"] == "f2"
    assert feats[0]["shap_value"] == -0.8
