# -*- coding: utf-8 -*-
"""
scripts/avaliar_hibrido_xai_sprint8.py
======================================
Avaliação comparativa única no conjunto de teste retido (3.632 obras totais e
739 obras com texto autêntico), calibragem do Sistema Híbrido (BERTimbau + LoRA +
LightGBM Hierárquico C2) via OOF em treino_dev, intervalos de confiança 95% via
Bootstrap (B=1.000), curvas PR por classe e explicações TreeSHAP para as obras do teste.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
from typing import Any, Dict, List

import numpy as np
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    f1_score,
    matthews_corrcoef,
    precision_recall_curve,
    precision_recall_fscore_support,
)

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.modeling.baselines import DummyMajorityClassifier, RandomForestTabularBaseline
from src.modeling.hierarchical import TwoStageHierarchicalClassifier
from src.modeling.lightgbm_engine import LightGBMClassifierEngine
from src.modeling.loader import (
    DEV_DATASET_DEFAULT,
    TEST_DATASET_DEFAULT,
    load_dataset,
    prepare_dataset_matrices,
)
from src.modeling.metrics import compute_confusion_matrix
from src.modeling.splitter import StratifiedGroupSplitter
from src.modeling.xai import (
    compute_bootstrap_ci_and_paired_test,
    extract_lightgbm_shap_top_features,
)


def evaluate_multiclass_full(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_proba: np.ndarray,
    y_ref_c1: np.ndarray | None = None,
    y_ref_c2: np.ndarray | None = None,
    n_bootstraps: int = 1000,
    seed: int = 42,
) -> Dict[str, Any]:
    macro_f1 = float(f1_score(y_true, y_pred, average="macro", zero_division=0))
    bal_acc = float(balanced_accuracy_score(y_true, y_pred))
    mcc = float(matthews_corrcoef(y_true, y_pred))
    cm = compute_confusion_matrix(y_true, y_pred, num_classes=4).tolist()
    prec, rec, f1_c, _ = precision_recall_fscore_support(y_true, y_pred, labels=[0, 1, 2, 3], zero_division=0)

    pr_auc = {}
    for c in range(4):
        yb = (y_true == c).astype(int)
        pr_auc[f"classe_{c}"] = round(float(average_precision_score(yb, y_proba[:, c])), 4) if np.sum(yb) > 0 else 0.0

    # Métricas binárias agregadas (0 vs Risco 1+2+3)
    y_true_bin = (y_true > 0).astype(int)
    y_pred_bin = (y_pred > 0).astype(int)
    prob_bin_risk = y_proba[:, 1:].sum(axis=1)
    bin_f1 = float(f1_score(y_true_bin, y_pred_bin, average="macro", zero_division=0))
    bin_bal = float(balanced_accuracy_score(y_true_bin, y_pred_bin))
    bin_mcc = float(matthews_corrcoef(y_true_bin, y_pred_bin))
    bin_pr_auc = float(average_precision_score(y_true_bin, prob_bin_risk)) if np.sum(y_true_bin) > 0 else 0.0

    boot_c1 = compute_bootstrap_ci_and_paired_test(y_true, y_pred, y_ref_c1, n_bootstraps=n_bootstraps, seed=seed)
    boot_c2 = (
        compute_bootstrap_ci_and_paired_test(y_true, y_pred, y_ref_c2, n_bootstraps=n_bootstraps, seed=seed)["paired_comparison"]
        if y_ref_c2 is not None
        else None
    )

    return {
        "macro_f1": round(macro_f1, 4),
        "balanced_acc": round(bal_acc, 4),
        "mcc": round(mcc, 4),
        "recall_classe_0": round(float(rec[0]), 4),
        "recall_classe_1": round(float(rec[1]), 4),
        "recall_classe_2": round(float(rec[2]), 4),
        "recall_classe_3": round(float(rec[3]), 4),
        "precision_classe_0": round(float(prec[0]), 4),
        "precision_classe_1": round(float(prec[1]), 4),
        "precision_classe_2": round(float(prec[2]), 4),
        "precision_classe_3": round(float(prec[3]), 4),
        "f1_classe_0": round(float(f1_c[0]), 4),
        "f1_classe_1": round(float(f1_c[1]), 4),
        "f1_classe_2": round(float(f1_c[2]), 4),
        "f1_classe_3": round(float(f1_c[3]), 4),
        "pr_auc": pr_auc,
        "confusion_matrix": cm,
        "binario_agregado": {
            "macro_f1_bin": round(bin_f1, 4),
            "balanced_acc_bin": round(bin_bal, 4),
            "mcc_bin": round(bin_mcc, 4),
            "pr_auc_risco": round(bin_pr_auc, 4),
            "recall_risco": round(float(np.sum((y_pred_bin == 1) & (y_true_bin == 1)) / max(1, np.sum(y_true_bin == 1))), 4),
            "especificidade_regular": round(float(np.sum((y_pred_bin == 0) & (y_true_bin == 0)) / max(1, np.sum(y_true_bin == 0))), 4),
        },
        "bootstrap_ci95": {
            "macro_f1_ci95": boot_c1["macro_f1_ci95"],
            "balanced_acc_ci95": boot_c1["balanced_acc_ci95"],
            "mcc_ci95": boot_c1["mcc_ci95"],
        },
        "comparacao_pareada_vs_hierarquico_c1": boot_c1.get("paired_comparison"),
        "comparacao_pareada_vs_hierarquico_c2": boot_c2,
    }


def compute_pr_curves_summary(y_true: np.ndarray, y_proba: np.ndarray, max_points: int = 40) -> Dict[str, Any]:
    curves = {}
    for c in range(4):
        yb = (y_true == c).astype(int)
        prec, rec, thresh = precision_recall_curve(yb, y_proba[:, c])
        step = max(1, len(prec) // max_points)
        idx = list(range(0, len(prec), step))
        if (len(prec) - 1) not in idx:
            idx.append(len(prec) - 1)
        curves[f"classe_{c}"] = {
            "auc_pr": round(float(average_precision_score(yb, y_proba[:, c])), 4),
            "precision": [round(float(prec[i]), 4) for i in idx],
            "recall": [round(float(rec[i]), 4) for i in idx],
        }
    return curves


def fuse_probabilities(
    hier_proba: np.ndarray,
    bert_probs_bin: np.ndarray,
    bert_probs_multi: np.ndarray,
    text_row_indices: np.ndarray,
    alpha_multi: float,
    beta_bin: float,
) -> np.ndarray:
    """
    Combina as probabilidades 4-classes do Hierárquico C2 com as probabilidades do
    BERTimbau + LoRA (multiclasse e detector binário de risco) apenas nas obras que
    possuem evidência textual autêntica; obras sem texto usam o Hierárquico C2.
    """
    fused = hier_proba.copy()
    for i, r_idx in enumerate(text_row_indices):
        p_h = hier_proba[r_idx].copy()
        p_bm = bert_probs_multi[i]
        p_bb_risk = float(bert_probs_bin[i, 1])

        # Combinação linear convexa 4-classes
        p_comb = (1.0 - alpha_multi) * p_h + alpha_multi * p_bm

        # Modulação suave do risco binário (Estágio 1)
        if beta_bin > 0.0:
            h_risk = float(np.sum(p_comb[1:]))
            new_risk = (1.0 - beta_bin) * h_risk + beta_bin * p_bb_risk
            new_reg = 1.0 - new_risk
            p_comb[0] = new_reg
            if h_risk > 1e-6:
                p_comb[1:] = p_comb[1:] * (new_risk / h_risk)
            else:
                p_comb[1:] = p_bm[1:] * new_risk

        s = float(np.sum(p_comb))
        if s > 0:
            p_comb /= s
        fused[r_idx] = p_comb
    return fused


def main() -> int:
    t0 = time.time()
    out_dir = ROOT / "dados_processados" / "sprint8"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 85, flush=True)
    print("SPRINT 8 — AVALIAÇÃO COMPARATIVA ÚNICA NO TESTE RETIDO, SISTEMA HÍBRIDO E SHAP", flush=True)
    print("=" * 85, flush=True)

    df_dev = load_dataset(DEV_DATASET_DEFAULT)
    df_test = load_dataset(TEST_DATASET_DEFAULT)

    npz_c2 = np.load(ROOT / "dados_processados" / "sprint7" / "embeddings_c2_sem_fichas.npz")
    X_dev_c2 = npz_c2["X_dev"]
    X_test_c2 = npz_c2["X_test"]

    npz_bert = np.load(out_dir / "predicoes_bertimbau_sprint8.npz")
    dev_text_rows = npz_bert["dev_row_indices"]
    oof_bert_bin = npz_bert["oof_probs_bin"]
    oof_bert_multi = npz_bert["oof_probs_multi"]

    test_text_rows = npz_bert["test_row_indices"]
    test_bert_bin = npz_bert["test_probs_bin"]
    test_bert_multi = npz_bert["test_probs_multi"]

    # 1. Obter OOF de Hierarquico_C2 em treino_dev para calibrar alpha_multi e beta_bin sem tocar no teste
    print("[1/4] Calibrando pesos do Sistema Híbrido via OOF em treino_dev (14.522 obras)...", flush=True)
    y_dev = df_dev["label_risco"].to_numpy(dtype=np.int32)
    groups_dev = df_dev["id_tcu"].astype(str).to_numpy()
    splitter = StratifiedGroupSplitter(n_splits=5, seed=42)
    oof_hier_c2 = np.zeros((len(df_dev), 4), dtype=np.float32)

    for tr_idx, va_idx in splitter.split(np.zeros((len(df_dev), 1)), y_dev, groups_dev):
        d_tr = prepare_dataset_matrices(df_dev.iloc[tr_idx], include_embeddings=True, feature_profile="c1_sem_proxies", override_embeddings=X_dev_c2[tr_idx])
        d_va = prepare_dataset_matrices(
            df_dev.iloc[va_idx],
            categorical_mappings=d_tr["categorical_mappings"],
            numeric_imputations=d_tr["numeric_imputations"],
            include_embeddings=True,
            feature_profile="c1_sem_proxies",
            override_embeddings=X_dev_c2[va_idx],
        )
        h_fold = TwoStageHierarchicalClassifier(n_estimators_stage1=120, n_estimators_stage2=100, learning_rate=0.05, seed=42, stage1_balanced=True, stage2_balanced=True)
        h_fold.fit(d_tr["X_comb"], d_tr["y"])
        oof_hier_c2[va_idx] = h_fold.predict_proba(d_va["X_comb"])

    best_alpha, best_beta = 0.15, 0.10
    best_oof_score = -1.0
    for alpha in [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40]:
        for beta in [0.0, 0.05, 0.10, 0.15, 0.20, 0.30]:
            cand_proba = fuse_probabilities(oof_hier_c2, oof_bert_bin, oof_bert_multi, dev_text_rows, alpha, beta)
            cand_pred = np.argmax(cand_proba[dev_text_rows], axis=1)
            f1_sub = f1_score(y_dev[dev_text_rows], cand_pred, average="macro", zero_division=0)
            mcc_sub = matthews_corrcoef(y_dev[dev_text_rows], cand_pred)
            score = f1_sub + 0.5 * mcc_sub
            if score > best_oof_score:
                best_oof_score = score
                best_alpha, best_beta = alpha, beta

    print(f"      Pesos ótimos selecionados em treino_dev: alpha_multi={best_alpha:.2f}, beta_bin={best_beta:.2f}", flush=True)

    # 2. Treinar modelos finais em treino_dev e avaliar uma única vez no teste retido (3.632 obras)
    print("[2/4] Treinando modelos finais em treino_dev e avaliando no teste retido (3.632 obras)...", flush=True)
    data_dev_c1 = prepare_dataset_matrices(df_dev, include_embeddings=False, feature_profile="c1_sem_proxies")
    data_test_c1 = prepare_dataset_matrices(
        df_test,
        categorical_mappings=data_dev_c1["categorical_mappings"],
        numeric_imputations=data_dev_c1["numeric_imputations"],
        include_embeddings=False,
        feature_profile="c1_sem_proxies",
    )

    data_dev_c2 = prepare_dataset_matrices(df_dev, include_embeddings=True, feature_profile="c1_sem_proxies", override_embeddings=X_dev_c2)
    data_test_c2 = prepare_dataset_matrices(
        df_test,
        categorical_mappings=data_dev_c2["categorical_mappings"],
        numeric_imputations=data_dev_c2["numeric_imputations"],
        include_embeddings=True,
        feature_profile="c1_sem_proxies",
        override_embeddings=X_test_c2,
    )

    y_tr = data_dev_c1["y"]
    y_te = data_test_c1["y"]
    cw = data_dev_c1["class_weights"]

    # Modelos C1 (Tabular Limpo)
    dummy = DummyMajorityClassifier()
    dummy.fit(data_dev_c1["X_tab"], y_tr)
    proba_dummy = dummy.predict_proba(data_test_c1["X_tab"])
    pred_dummy = dummy.predict(data_test_c1["X_tab"])

    rf_c1 = RandomForestTabularBaseline(n_estimators=100, max_depth=12, seed=42, class_weights=cw)
    rf_c1.fit(data_dev_c1["X_tab"], y_tr)
    proba_rf_c1 = rf_c1.predict_proba(data_test_c1["X_tab"])
    pred_rf_c1 = rf_c1.predict(data_test_c1["X_tab"])

    lgb_c1 = LightGBMClassifierEngine(n_estimators=150, learning_rate=0.05, num_leaves=31, max_depth=6, min_child_samples=20, feature_fraction=0.8, bagging_fraction=0.8, seed=42, class_weights=cw)
    lgb_c1.fit(data_dev_c1["X_tab"], y_tr)
    proba_lgb_c1 = lgb_c1.predict_proba(data_test_c1["X_tab"])
    pred_lgb_c1 = lgb_c1.predict(data_test_c1["X_tab"])

    hier_c1 = TwoStageHierarchicalClassifier(n_estimators_stage1=120, n_estimators_stage2=100, learning_rate=0.05, seed=42, stage1_balanced=True, stage2_balanced=True)
    hier_c1.fit(data_dev_c1["X_tab"], y_tr)
    proba_hier_c1 = hier_c1.predict_proba(data_test_c1["X_tab"])
    pred_hier_c1 = hier_c1.predict(data_test_c1["X_tab"])

    # Modelos C2 (Texto Autêntico sem Fichas)
    lgb_c2 = LightGBMClassifierEngine(n_estimators=150, learning_rate=0.05, num_leaves=31, max_depth=6, min_child_samples=20, feature_fraction=0.8, bagging_fraction=0.8, seed=42, class_weights=cw)
    lgb_c2.fit(data_dev_c2["X_comb"], y_tr)
    proba_lgb_c2 = lgb_c2.predict_proba(data_test_c2["X_comb"])
    pred_lgb_c2 = lgb_c2.predict(data_test_c2["X_comb"])

    hier_c2 = TwoStageHierarchicalClassifier(n_estimators_stage1=120, n_estimators_stage2=100, learning_rate=0.05, seed=42, stage1_balanced=True, stage2_balanced=True)
    hier_c2.fit(data_dev_c2["X_comb"], y_tr)
    proba_hier_c2 = hier_c2.predict_proba(data_test_c2["X_comb"])
    pred_hier_c2 = hier_c2.predict(data_test_c2["X_comb"])

    # Sistema Híbrido (BERTimbau + LoRA + Hierárquico C2)
    proba_hibrido = fuse_probabilities(proba_hier_c2, test_bert_bin, test_bert_multi, test_text_rows, best_alpha, best_beta)
    pred_hibrido = np.argmax(proba_hibrido, axis=1)

    # Avaliação na População Integral (3.632 obras)
    models_3632 = {
        "Dummy_Majoritario": (pred_dummy, proba_dummy),
        "RandomForest_C1_Tabular": (pred_rf_c1, proba_rf_c1),
        "LightGBM_C1_Tabular": (pred_lgb_c1, proba_lgb_c1),
        "Hierarquico_C1_Tabular": (pred_hier_c1, proba_hier_c1),
        "LightGBM_C2_Texto_Autentico": (pred_lgb_c2, proba_lgb_c2),
        "Hierarquico_C2_Texto_Autentico": (pred_hier_c2, proba_hier_c2),
        "Sistema_Hibrido_BERTimbau_C2": (pred_hibrido, proba_hibrido),
    }

    eval_3632 = {}
    for m_name, (yp, ypr) in models_3632.items():
        eval_3632[m_name] = evaluate_multiclass_full(
            y_true=y_te,
            y_pred=yp,
            y_proba=ypr,
            y_ref_c1=pred_hier_c1,
            y_ref_c2=pred_hier_c2,
            n_bootstraps=1000,
            seed=42,
        )

    # Avaliação no Subconjunto com Texto Autêntico (739 obras)
    print("[3/4] Avaliando subconjunto com texto autêntico no teste retido (739 obras)...", flush=True)
    y_te_sub = y_te[test_text_rows]
    pred_bert_multi = np.argmax(test_bert_multi, axis=1)

    # Estágio 1 BERTimbau Binário + Estágio 2 Causal do Hierárquico C2 nas 739 obras com texto
    proba_bert_hier_stage2 = proba_hier_c2[test_text_rows].copy()
    for i in range(len(test_text_rows)):
        p_b_risk = float(test_bert_bin[i, 1])
        p_h_sub = proba_bert_hier_stage2[i]
        h_r = float(np.sum(p_h_sub[1:]))
        proba_bert_hier_stage2[i, 0] = 1.0 - p_b_risk
        if h_r > 1e-6:
            proba_bert_hier_stage2[i, 1:] = p_h_sub[1:] * (p_b_risk / h_r)
        else:
            proba_bert_hier_stage2[i, 1:] = test_bert_multi[i, 1:]
    pred_bert_hier_stage2 = np.argmax(proba_bert_hier_stage2, axis=1)

    models_739 = {
        "LightGBM_C1_Tabular": (pred_lgb_c1[test_text_rows], proba_lgb_c1[test_text_rows]),
        "Hierarquico_C1_Tabular": (pred_hier_c1[test_text_rows], proba_hier_c1[test_text_rows]),
        "BERTimbau_LoRA_Puro_Multiclasse": (pred_bert_multi, test_bert_multi),
        "BERTimbau_LoRA_Binario_Stage2_C2": (pred_bert_hier_stage2, proba_bert_hier_stage2),
        "Hierarquico_C2_Texto_Autentico": (pred_hier_c2[test_text_rows], proba_hier_c2[test_text_rows]),
        "Sistema_Hibrido_BERTimbau_C2": (pred_hibrido[test_text_rows], proba_hibrido[test_text_rows]),
    }

    eval_739 = {}
    for m_name, (yp, ypr) in models_739.items():
        eval_739[m_name] = evaluate_multiclass_full(
            y_true=y_te_sub,
            y_pred=yp,
            y_proba=ypr,
            y_ref_c1=pred_hier_c1[test_text_rows],
            y_ref_c2=pred_hier_c2[test_text_rows],
            n_bootstraps=1000,
            seed=42,
        )

    # Curvas PR
    pr_curves = {
        "populacao_integral_3632": {
            "Hierarquico_C1_Tabular": compute_pr_curves_summary(y_te, proba_hier_c1),
            "Hierarquico_C2_Texto_Autentico": compute_pr_curves_summary(y_te, proba_hier_c2),
            "Sistema_Hibrido_BERTimbau_C2": compute_pr_curves_summary(y_te, proba_hibrido),
        },
        "subconjunto_com_texto_739": {
            "Hierarquico_C1_Tabular": compute_pr_curves_summary(y_te_sub, proba_hier_c1[test_text_rows]),
            "BERTimbau_LoRA_Puro_Multiclasse": compute_pr_curves_summary(y_te_sub, test_bert_multi),
            "Hierarquico_C2_Texto_Autentico": compute_pr_curves_summary(y_te_sub, proba_hier_c2[test_text_rows]),
            "Sistema_Hibrido_BERTimbau_C2": compute_pr_curves_summary(y_te_sub, proba_hibrido[test_text_rows]),
        },
    }
    with open(out_dir / "curvas_pr_sprint8.json", "w", encoding="utf-8") as f:
        json.dump(pr_curves, f, indent=2, ensure_ascii=False)

    # 4. Adicionar TreeSHAP do LightGBM às 64 obras explicadas pelo XAI
    print("[4/4] Calculando valores TreeSHAP (LightGBM) e consolidando xai_explicacoes_teste.json...", flush=True)
    xai_bert_path = out_dir / "xai_bertimbau_teste.json"
    xai_data = json.loads(xai_bert_path.read_text(encoding="utf-8"))

    tab_feature_names = data_test_c1["feature_names"]
    comb_feature_names = data_test_c2["feature_names"]

    # Importância global SHAP no teste retido para C1 Tabular
    shap_matrix_c1 = np.asarray(lgb_c1.booster.predict(data_test_c1["X_tab"], pred_contrib=True))
    n_tab = len(tab_feature_names)
    if shap_matrix_c1.ndim == 2 and shap_matrix_c1.shape[1] % (n_tab + 1) == 0:
        reshaped_all = shap_matrix_c1.reshape(len(y_te), 4, n_tab + 1)
        mean_abs_shap_tab = np.mean(np.abs(reshaped_all[:, :, :n_tab]), axis=(0, 1))
    else:
        mean_abs_shap_tab = np.zeros(n_tab)

    global_shap_ranking = [
        {"feature": tab_feature_names[i], "mean_abs_shap": round(float(mean_abs_shap_tab[i]), 6)}
        for i in np.argsort(mean_abs_shap_tab)[::-1]
    ]

    for obra_rec in xai_data["obras"]:
        r_idx = int(obra_rec["row_idx_teste"])
        obra_rec["pred_hierarquico_c1"] = int(pred_hier_c1[r_idx])
        obra_rec["pred_hierarquico_c2"] = int(pred_hier_c2[r_idx])
        obra_rec["pred_sistema_hibrido"] = int(pred_hibrido[r_idx])
        obra_rec["probs_sistema_hibrido"] = [round(float(p), 6) for p in proba_hibrido[r_idx].tolist()]
        obra_rec["shap_top_features_tabular"] = extract_lightgbm_shap_top_features(
            lgb_c1.booster,
            data_test_c1["X_tab"][r_idx],
            tab_feature_names,
            top_k=5,
        )
        obra_rec["shap_top_features_c2_comb"] = extract_lightgbm_shap_top_features(
            hier_c2.stage1.booster,
            data_test_c2["X_comb"][r_idx],
            comb_feature_names,
            top_k=5,
        )

    xai_data["shap_importancia_global_tabular"] = global_shap_ranking
    xai_final_path = out_dir / "xai_explicacoes_teste.json"
    with open(xai_final_path, "w", encoding="utf-8") as f:
        json.dump(xai_data, f, indent=2, ensure_ascii=False)

    final_eval_payload = {
        "gerado_em_utc": datetime.now(timezone.utc).isoformat(),
        "pesos_fusao_hibrida_calibrados_oof": {
            "alpha_multiclasse": best_alpha,
            "beta_binario": best_beta,
        },
        "populacao_integral_teste_3632_obras": eval_3632,
        "subconjunto_com_texto_autentico_739_obras": eval_739,
        "shap_importancia_global_tabular": global_shap_ranking,
    }
    eval_path = out_dir / "avaliacao_final_sprint8.json"
    with open(eval_path, "w", encoding="utf-8") as f:
        json.dump(final_eval_payload, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 95, flush=True)
    print("TABELA FINAL — TESTE RETIDO INTEGRAL (3.632 OBRAS)", flush=True)
    print("=" * 95, flush=True)
    for m_name, d in eval_3632.items():
        ci_f1 = d["bootstrap_ci95"]["macro_f1_ci95"]
        print(
            f"{m_name:<32} | Macro-F1: {d['macro_f1']:.4f} [{ci_f1[0]:.4f}, {ci_f1[1]:.4f}] | "
            f"Bal.Acc: {d['balanced_acc']:.4f} | MCC: {d['mcc']:.4f} | "
            f"Rec(0/1/2/3): {d['recall_classe_0']:.1%}/{d['recall_classe_1']:.1%}/{d['recall_classe_2']:.1%}/{d['recall_classe_3']:.1%}",
            flush=True,
        )

    print("\n" + "=" * 95, flush=True)
    print("TABELA FINAL — SUBCONJUNTO COM TEXTO AUTÊNTICO (739 OBRAS)", flush=True)
    print("=" * 95, flush=True)
    for m_name, d in eval_739.items():
        b_bin = d["binario_agregado"]
        print(
            f"{m_name:<32} | 4-Cls F1: {d['macro_f1']:.4f} (MCC {d['mcc']:.4f}) | "
            f"Bin F1: {b_bin['macro_f1_bin']:.4f} (Bal.Acc {b_bin['balanced_acc_bin']:.4f}, MCC {b_bin['mcc_bin']:.4f})",
            flush=True,
        )
    print("=" * 95, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
