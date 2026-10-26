# -*- coding: utf-8 -*-
"""
src/modeling/xai.py
===================
Módulo de Explicabilidade (XAI), Teste de Fidelidade por Deleção e Inferência
Estatística por Bootstrap para a Sprint 8 (Feature 022).

Inclui:
1. Extração de pesos de atenção do encoder BERTimbau (última camada, token [CLS]).
2. Atribuição por gradiente (Input x Gradient sobre a camada de embeddings).
3. Teste de fidelidade por deleção (remoção dos top-k tokens mais atribuídos vs. aleatórios).
4. Auditoria de termos proibidos de vazamento de alvo nos tokens mais relevantes.
5. Valores SHAP exatos (TreeSHAP via pred_contrib=True) para a referência LightGBM.
6. Intervalos de confiança de 95% e teste pareado via Bootstrap (B=1.000).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from sklearn.metrics import balanced_accuracy_score, f1_score, matthews_corrcoef

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
except ImportError:  # Permite importar funções de bootstrap e SHAP no ambiente tabular (.venv)
    torch = None  # type: ignore[assignment]
    nn = None     # type: ignore[assignment]
    F = None      # type: ignore[assignment]

from src.rag.queries import PROHIBITED_TERMS

SPECIAL_TOKENS = {"[CLS]", "[SEP]", "[PAD]", "[UNK]", "[MASK]"}


def extract_attention_and_grad_attribution(
    model: nn.Module,
    tokenizer: Any,
    input_ids: torch.Tensor,
    attention_mask: torch.Tensor,
    target_class: Optional[int] = None,
    top_k: int = 12,
) -> Dict[str, Any]:
    """
    Calcula simultaneamente os pesos de atenção do encoder ([CLS] -> tokens) e a
    atribuição por gradiente (Input x Gradient) para uma sequência de entrada (1, L).
    """
    model.eval()
    device = next(model.parameters()).device
    ids = input_ids.unsqueeze(0).to(device) if input_ids.dim() == 1 else input_ids.to(device)
    mask = attention_mask.unsqueeze(0).to(device) if attention_mask.dim() == 1 else attention_mask.to(device)

    emb_layer = model.get_input_embeddings()
    captured_embeds: List[torch.Tensor] = []

    def forward_hook(module, inp, out):
        if not out.requires_grad:
            out = out.detach().requires_grad_(True)
        out.retain_grad()
        captured_embeds.append(out)
        return out

    handle = emb_layer.register_forward_hook(forward_hook)
    try:
        model.zero_grad()
        outputs = model(
            input_ids=ids,
            attention_mask=mask,
            output_attentions=True,
        )
        logits = outputs.logits
        probs = F.softmax(logits, dim=-1)
        pred_class = int(torch.argmax(probs, dim=-1).item())
        if target_class is None:
            target_class = pred_class

        num_classes = logits.shape[-1]
        if num_classes > 1:
            other_mean = (logits[0].sum() - logits[0, target_class]) / float(num_classes - 1)
            target_logit = logits[0, target_class] - other_mean
        else:
            target_logit = logits[0, target_class]
        target_logit.backward()

        # 1. Atribuição Direcional por Gradiente (Signed Input x Gradient em relação ao baseline zero)
        embeds = captured_embeds[0]  # (1, L, D)
        grads = embeds.grad          # (1, L, D)
        signed_scores = torch.sum((embeds * grads).detach()[0], dim=-1)  # (L,)
        pos_scores = torch.clamp(signed_scores, min=0.0)
        if float(pos_scores.sum().item()) > 1e-12:
            grad_scores = pos_scores.cpu().numpy()
        else:
            input_x_grad = (embeds * grads).detach()[0]
            grad_scores = torch.norm(input_x_grad, p=2, dim=-1).cpu().numpy()

        # 2. Atenção do Encoder (média das cabeças da última camada a partir de [CLS])
        if outputs.attentions is not None and len(outputs.attentions) > 0:
            last_attn = outputs.attentions[-1].detach()[0]  # (H, L, L)
            cls_attn = last_attn.mean(dim=0)[0].cpu().numpy()  # (L,)
        else:
            cls_attn = grad_scores.copy()
    finally:
        handle.remove()

    tokens = tokenizer.convert_ids_to_tokens(ids[0].detach().cpu().tolist())
    active_mask = mask[0].detach().cpu().numpy().astype(bool)

    valid_indices = [
        i for i, (tok, act) in enumerate(zip(tokens, active_mask))
        if act and tok not in SPECIAL_TOKENS
    ]

    if valid_indices:
        g_valid = grad_scores[valid_indices]
        g_sum = float(np.sum(g_valid))
        if g_sum > 0:
            grad_scores_norm = np.zeros_like(grad_scores)
            grad_scores_norm[valid_indices] = g_valid / g_sum
        else:
            grad_scores_norm = grad_scores

        a_valid = cls_attn[valid_indices]
        a_sum = float(np.sum(a_valid))
        if a_sum > 0:
            attn_scores_norm = np.zeros_like(cls_attn)
            attn_scores_norm[valid_indices] = a_valid / a_sum
        else:
            attn_scores_norm = cls_attn
    else:
        grad_scores_norm = grad_scores
        attn_scores_norm = cls_attn

    top_grad_idx = sorted(valid_indices, key=lambda i: float(grad_scores_norm[i]), reverse=True)[:top_k]
    top_attn_idx = sorted(valid_indices, key=lambda i: float(attn_scores_norm[i]), reverse=True)[:top_k]

    top_grad_tokens = [
        {"pos": int(i), "token": tokens[i], "score": round(float(grad_scores_norm[i]), 6)}
        for i in top_grad_idx
    ]
    top_attn_tokens = [
        {"pos": int(i), "token": tokens[i], "score": round(float(attn_scores_norm[i]), 6)}
        for i in top_attn_idx
    ]

    return {
        "pred_class": pred_class,
        "target_class": int(target_class),
        "prob_target": round(float(probs[0, target_class].item()), 6),
        "probs": [round(float(p), 6) for p in probs[0].detach().cpu().tolist()],
        "valid_indices": valid_indices,
        "grad_scores": grad_scores_norm,
        "attn_scores": attn_scores_norm,
        "top_grad_tokens": top_grad_tokens,
        "top_attn_tokens": top_attn_tokens,
    }


def run_deletion_faithfulness_test(
    model: nn.Module,
    tokenizer: Any,
    input_ids: torch.Tensor,
    attention_mask: torch.Tensor,
    target_class: int,
    grad_scores: np.ndarray,
    valid_indices: List[int],
    k_ratio: float = 0.15,
    seed: int = 42,
) -> Dict[str, Any]:
    """
    Teste de fidelidade por deleção: substitui os top-k tokens mais atribuídos por [MASK]
    e compara a queda na probabilidade da classe prevista contra a remoção de k tokens aleatórios.
    """
    model.eval()
    device = next(model.parameters()).device
    ids = input_ids.unsqueeze(0).to(device) if input_ids.dim() == 1 else input_ids.clone().to(device)
    mask = attention_mask.unsqueeze(0).to(device) if attention_mask.dim() == 1 else attention_mask.to(device)

    if not valid_indices:
        return {
            "k_deleted": 0,
            "prob_original": 0.0,
            "prob_after_topk_deletion": 0.0,
            "prob_after_random_deletion": 0.0,
            "drop_topk": 0.0,
            "drop_random": 0.0,
            "faithfulness_gap": 0.0,
            "faithful": False,
        }

    k = max(3, min(len(valid_indices), int(round(len(valid_indices) * k_ratio))))
    top_k_indices = sorted(valid_indices, key=lambda i: float(grad_scores[i]), reverse=True)[:k]

    rng = np.random.default_rng(seed)
    pad_token_id = getattr(tokenizer, "pad_token_id", None)
    if pad_token_id is None:
        pad_token_id = getattr(tokenizer, "mask_token_id", 0) or 0

    ids_topk = ids.clone()
    ids_topk[0, top_k_indices] = pad_token_id

    rand_batches = []
    for _ in range(5):
        r_idx = rng.choice(valid_indices, size=k, replace=False).tolist()
        ids_r = ids.clone()
        ids_r[0, r_idx] = pad_token_id
        rand_batches.append(ids_r)

    with torch.no_grad():
        batch_ids = torch.cat([ids, ids_topk] + rand_batches, dim=0)
        batch_mask = mask.repeat(2 + len(rand_batches), 1)
        logits = model(input_ids=batch_ids, attention_mask=batch_mask).logits
        probs = F.softmax(logits, dim=-1)[:, target_class].cpu().numpy()

    p_orig = float(probs[0])
    p_topk = float(probs[1])
    p_rand = float(np.mean(probs[2:]))

    drop_topk = p_orig - p_topk
    drop_rand = p_orig - p_rand
    gap = drop_topk - drop_rand

    return {
        "k_deleted": int(k),
        "prob_original": round(p_orig, 6),
        "prob_after_topk_deletion": round(p_topk, 6),
        "prob_after_random_deletion": round(p_rand, 6),
        "drop_topk": round(drop_topk, 6),
        "drop_random": round(drop_rand, 6),
        "faithfulness_gap": round(gap, 6),
        "faithful": bool(drop_topk > drop_rand),
    }


def audit_prohibited_terms_in_top_tokens(top_tokens: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Verifica se algum termo proibido de situação cadastral aparece entre os top tokens atribuídos.
    Reconstrói palavras a partir de subwords WordPiece (##).
    """
    reconstructed = ""
    for item in top_tokens:
        tok = str(item.get("token", ""))
        if tok.startswith("##"):
            reconstructed += tok[2:]
        else:
            reconstructed += " " + tok
    lower_text = reconstructed.lower()
    found = [term for term in PROHIBITED_TERMS if term.lower() in lower_text]
    return {
        "alerta_vazamento": len(found) > 0,
        "termos_detectados": found,
    }


def extract_lightgbm_shap_top_features(
    booster: Any,
    X_row: np.ndarray,
    feature_names: List[str],
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """
    Extrai os valores TreeSHAP exatos (pred_contrib=True) de um booster LightGBM
    para uma observação (1, F) ou (F,).
    """
    x_2d = X_row.reshape(1, -1) if X_row.ndim == 1 else X_row
    contribs = np.asarray(booster.predict(x_2d, pred_contrib=True))
    n_feat = len(feature_names)

    if contribs.ndim == 2 and contribs.shape[1] == n_feat + 1:
        shap_vals = contribs[0, :n_feat]
    elif contribs.ndim == 2 and contribs.shape[1] % (n_feat + 1) == 0:
        n_classes = contribs.shape[1] // (n_feat + 1)
        reshaped = contribs[0].reshape(n_classes, n_feat + 1)
        shap_vals = np.mean(np.abs(reshaped[:, :n_feat]), axis=0)
    else:
        shap_vals = contribs.ravel()[:n_feat]

    top_idx = np.argsort(np.abs(shap_vals))[::-1][:top_k]
    return [
        {
            "feature": feature_names[int(i)],
            "shap_value": round(float(shap_vals[int(i)]), 6),
            "abs_shap": round(float(abs(shap_vals[int(i)])), 6),
        }
        for i in top_idx
    ]


def compute_bootstrap_ci_and_paired_test(
    y_true: np.ndarray,
    y_pred_model: np.ndarray,
    y_pred_ref: Optional[np.ndarray] = None,
    n_bootstraps: int = 1000,
    seed: int = 42,
) -> Dict[str, Any]:
    """
    Calcula intervalos de confiança de 95% via bootstrap (B=1.000) para Macro-F1,
    Balanced Accuracy e MCC, e teste pareado contra um modelo de referência.
    """
    rng = np.random.default_rng(seed)
    n = len(y_true)
    f1_scores = np.zeros(n_bootstraps, dtype=np.float64)
    bal_scores = np.zeros(n_bootstraps, dtype=np.float64)
    mcc_scores = np.zeros(n_bootstraps, dtype=np.float64)

    diff_f1 = np.zeros(n_bootstraps, dtype=np.float64) if y_pred_ref is not None else None
    diff_mcc = np.zeros(n_bootstraps, dtype=np.float64) if y_pred_ref is not None else None

    for b in range(n_bootstraps):
        idx = rng.integers(0, n, size=n)
        yt = y_true[idx]
        yp = y_pred_model[idx]

        f1_m = f1_score(yt, yp, average="macro", zero_division=0)
        bal_m = balanced_accuracy_score(yt, yp)
        mcc_m = matthews_corrcoef(yt, yp)

        f1_scores[b] = f1_m
        bal_scores[b] = bal_m
        mcc_scores[b] = mcc_m

        if y_pred_ref is not None:
            yr = y_pred_ref[idx]
            f1_r = f1_score(yt, yr, average="macro", zero_division=0)
            mcc_r = matthews_corrcoef(yt, yr)
            diff_f1[b] = f1_m - f1_r
            diff_mcc[b] = mcc_m - mcc_r

    res: Dict[str, Any] = {
        "n_bootstraps": n_bootstraps,
        "macro_f1_ci95": [round(float(np.percentile(f1_scores, 2.5)), 4), round(float(np.percentile(f1_scores, 97.5)), 4)],
        "balanced_acc_ci95": [round(float(np.percentile(bal_scores, 2.5)), 4), round(float(np.percentile(bal_scores, 97.5)), 4)],
        "mcc_ci95": [round(float(np.percentile(mcc_scores, 2.5)), 4), round(float(np.percentile(mcc_scores, 97.5)), 4)],
    }

    if diff_f1 is not None and diff_mcc is not None:
        obs_diff_f1 = float(
            f1_score(y_true, y_pred_model, average="macro", zero_division=0)
            - f1_score(y_true, y_pred_ref, average="macro", zero_division=0)
        )
        obs_diff_mcc = float(
            matthews_corrcoef(y_true, y_pred_model) - matthews_corrcoef(y_true, y_pred_ref)
        )
        # p-value bilateral por bootstrap
        p_val_f1 = float(2.0 * min(np.mean(diff_f1 <= 0.0), np.mean(diff_f1 >= 0.0)))
        p_val_mcc = float(2.0 * min(np.mean(diff_mcc <= 0.0), np.mean(diff_mcc >= 0.0)))
        res["paired_comparison"] = {
            "delta_macro_f1": round(obs_diff_f1, 4),
            "delta_macro_f1_ci95": [round(float(np.percentile(diff_f1, 2.5)), 4), round(float(np.percentile(diff_f1, 97.5)), 4)],
            "p_value_macro_f1": round(min(1.0, p_val_f1), 4),
            "delta_mcc": round(obs_diff_mcc, 4),
            "delta_mcc_ci95": [round(float(np.percentile(diff_mcc, 2.5)), 4), round(float(np.percentile(diff_mcc, 97.5)), 4)],
            "p_value_mcc": round(min(1.0, p_val_mcc), 4),
        }

    return res
