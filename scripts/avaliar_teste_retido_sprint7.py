# -*- coding: utf-8 -*-
"""
scripts/avaliar_teste_retido_sprint7.py
======================================
Executa a avaliação única oficial no dataset de teste retido (3.632 obras de 2025)
para o Cenário Eleito C2 (Texto Limpo sem Fichas) e Cenário C1 (Tabular Limpo).

Garante:
1. Zero vazamento de id_tcu entre treino_dev e teste_retido.
2. Mapeamentos categóricos e medianas imputadas estritamente aprendidos em treino_dev.
3. Uso dos embeddings C2 auditados (apenas documentos autênticos, zero fichas sintéticas).
4. Registro de Macro-F1, Balanced Accuracy, MCC, Recall por classe e Matriz de Confusão.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
from typing import Any, Dict

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    f1_score,
    matthews_corrcoef,
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


def evaluate_predictions(y_true: np.ndarray, y_pred: np.ndarray, y_proba: np.ndarray = None) -> Dict[str, Any]:
    """Calcula métricas robustas multiclasse para o teste retido."""
    macro_f1 = float(f1_score(y_true, y_pred, average="macro", zero_division=0))
    bal_acc = float(balanced_accuracy_score(y_true, y_pred))
    mcc = float(matthews_corrcoef(y_true, y_pred))
    cm = compute_confusion_matrix(y_true, y_pred, num_classes=4).tolist()

    prec, rec, f1, supp = precision_recall_fscore_support(y_true, y_pred, labels=[0, 1, 2, 3], zero_division=0)

    pr_auc: Dict[str, float] = {}
    if y_proba is not None and y_proba.shape[1] == 4:
        for c in range(4):
            y_bin = (y_true == c).astype(int)
            if np.sum(y_bin) > 0:
                pr_auc[f"classe_{c}"] = float(average_precision_score(y_bin, y_proba[:, c]))
            else:
                pr_auc[f"classe_{c}"] = 0.0

    return {
        "macro_f1": macro_f1,
        "balanced_acc": bal_acc,
        "mcc": mcc,
        "recall_classe_0": float(rec[0]),
        "recall_classe_1": float(rec[1]),
        "recall_classe_2": float(rec[2]),
        "recall_classe_3": float(rec[3]),
        "precision_classe_0": float(prec[0]),
        "precision_classe_1": float(prec[1]),
        "precision_classe_2": float(prec[2]),
        "precision_classe_3": float(prec[3]),
        "pr_auc": pr_auc,
        "confusion_matrix": cm,
    }


def evaluate_scenario(
    df_dev: pd.DataFrame,
    df_test: pd.DataFrame,
    scenario_id: str,
    override_dev_emb: np.ndarray = None,
    override_test_emb: np.ndarray = None,
    seed: int = 42,
) -> Dict[str, Any]:
    inc_emb = (scenario_id == "C2")
    feature_prof = "c1_sem_proxies"

    # Preparar matrizes do treino
    data_dev = prepare_dataset_matrices(
        df_dev,
        include_embeddings=inc_emb,
        feature_profile=feature_prof,
        override_embeddings=override_dev_emb,
    )

    # Preparar matrizes do teste com mapeamentos e medianas do treino
    data_test = prepare_dataset_matrices(
        df_test,
        categorical_mappings=data_dev["categorical_mappings"],
        numeric_imputations=data_dev["numeric_imputations"],
        include_embeddings=inc_emb,
        feature_profile=feature_prof,
        override_embeddings=override_test_emb,
    )

    X_tr = data_dev["X_comb"]
    y_tr = data_dev["y"]
    cw = data_dev["class_weights"]

    X_te = data_test["X_comb"]
    y_te = data_test["y"]

    results = {}

    # 1. Dummy
    t0 = time.time()
    dummy = DummyMajorityClassifier()
    dummy.fit(X_tr, y_tr)
    preds = dummy.predict(X_te)
    probas = dummy.predict_proba(X_te)
    results["Dummy"] = evaluate_predictions(y_te, preds, probas)
    results["Dummy"]["tempo_treino_s"] = round(time.time() - t0, 3)

    # 2. Random Forest (apenas tabular)
    t0 = time.time()
    rf = RandomForestTabularBaseline(n_estimators=100, max_depth=12, seed=seed, class_weights=cw)
    rf.fit(data_dev["X_tab"], y_tr)
    preds = rf.predict(data_test["X_tab"])
    probas = rf.predict_proba(data_test["X_tab"])
    results["RandomForest"] = evaluate_predictions(y_te, preds, probas)
    results["RandomForest"]["tempo_treino_s"] = round(time.time() - t0, 3)

    # 3. LightGBM Conjunto
    t0 = time.time()
    lgb = LightGBMClassifierEngine(
        n_estimators=150,
        learning_rate=0.05,
        num_leaves=31,
        max_depth=6,
        min_child_samples=20,
        feature_fraction=0.8,
        bagging_fraction=0.8,
        seed=seed,
        class_weights=cw,
    )
    lgb.fit(X_tr, y_tr)
    preds = lgb.predict(X_te)
    probas = lgb.predict_proba(X_te)
    results["LightGBM_Conjunto"] = evaluate_predictions(y_te, preds, probas)
    results["LightGBM_Conjunto"]["tempo_treino_s"] = round(time.time() - t0, 3)

    # 4. Hierárquico Campeão
    t0 = time.time()
    hier = TwoStageHierarchicalClassifier(
        n_estimators_stage1=120,
        n_estimators_stage2=100,
        learning_rate=0.05,
        seed=seed,
        stage1_balanced=True,
        stage2_balanced=True,
    )
    hier.fit(X_tr, y_tr)
    preds = hier.predict(X_te)
    probas = hier.predict_proba(X_te)
    results["Hierarquico_Campeao"] = evaluate_predictions(y_te, preds, probas)
    results["Hierarquico_Campeao"]["tempo_treino_s"] = round(time.time() - t0, 3)

    # Métricas binárias do Estágio 1 do Hierárquico
    y_te_bin = (y_te > 0).astype(int)
    p_risk = probas[:, 1:].sum(axis=1) if probas.shape[1] == 4 else (preds > 0).astype(float)
    preds_bin = (preds > 0).astype(int)
    results["Hierarquico_Estagio1_Binario"] = {
        "recall_risco": float(np.sum((preds_bin == 1) & (y_te_bin == 1)) / np.sum(y_te_bin == 1)),
        "especificidade_regular": float(np.sum((preds_bin == 0) & (y_te_bin == 0)) / np.sum(y_te_bin == 0)),
        "balanced_acc_bin": float(balanced_accuracy_score(y_te_bin, preds_bin)),
    }

    return results


def main():
    parser = argparse.ArgumentParser(description="Avaliação única e oficial no teste retido (Sprint 7)")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    t_start = time.time()
    out_dir = ROOT / "dados_processados" / "sprint7"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("AVALIAÇÃO OFICIAL NO DATASET DE TESTE RETIDO — SPRINT 7 (FEATURE 018)")
    print(f"Semente: {args.seed} | Horário: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 80)

    # 1. Carregar partições
    df_dev = load_dataset(DEV_DATASET_DEFAULT)
    df_test = load_dataset(TEST_DATASET_DEFAULT)

    # Verificação de vazamento por id_tcu
    dev_ids = set(df_dev["id_tcu"])
    test_ids = set(df_test["id_tcu"])
    inter = dev_ids.intersection(test_ids)
    if len(inter) > 0:
        raise RuntimeError(f"ERRO CRÍTICO: Vazamento de {len(inter)} obras entre treino e teste!")
    print(f"[Auditoria] Treino/Dev: {len(df_dev):,} obras | Teste Retido: {len(df_test):,} obras | Interseção: 0")

    # 2. Carregar embeddings C2
    c2_path = out_dir / "embeddings_c2_sem_fichas.npz"
    if not c2_path.exists():
        raise FileNotFoundError(f"Arquivo {c2_path} não encontrado!")
    npz_c2 = np.load(c2_path)
    X_dev_c2 = npz_c2["X_dev"]
    X_test_c2 = npz_c2["X_test"]

    # 3. Avaliar Cenário C1 (Tabular Limpo - Controle)
    print("\n[Avaliação] Executando Cenário C1 (Tabular Limpo)...")
    res_c1 = evaluate_scenario(df_dev, df_test, "C1", seed=args.seed)

    # 4. Avaliar Cenário Eleito C2 (Texto Limpo sem Fichas)
    print("\n[Avaliação] Executando Cenário Oficial C2 (Texto Limpo sem Fichas)...")
    res_c2 = evaluate_scenario(df_dev, df_test, "C2", override_dev_emb=X_dev_c2, override_test_emb=X_test_c2, seed=args.seed)

    final_payload = {
        "data_execucao_utc": datetime.now(timezone.utc).isoformat(),
        "semente": args.seed,
        "total_treino": len(df_dev),
        "total_teste": len(df_test),
        "distribuicao_teste": {str(k): int(v) for k, v in df_test["label_risco"].value_counts().to_dict().items()},
        "cenario_c1_tabular_limpo": res_c1,
        "cenario_c2_oficial_sem_fichas": res_c2,
    }

    # Salvar resultados
    res_file = out_dir / "resultado_teste_retido_sprint7.json"
    with open(res_file, "w", encoding="utf-8") as f:
        json.dump(final_payload, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 90)
    print("TABELA COMPARATIVA NO TESTE RETIDO (3.632 OBRAS)")
    print("=" * 90)
    print(f"{'Cenário':<15} | {'Modelo':<22} | {'Macro-F1':<10} | {'Bal. Acc':<10} | {'MCC':<8} | {'Rec. 0':<8} | {'Rec. 1':<8} | {'Rec. 2':<8} | {'Rec. 3':<8}")
    print("-" * 105)

    for scen_name, s_data in [("C1_Tabular", res_c1), ("C2_Oficial_C2", res_c2)]:
        for mod_name in ["Dummy", "RandomForest", "LightGBM_Conjunto", "Hierarquico_Campeao"]:
            m = s_data[mod_name]
            print(f"{scen_name:<15} | {mod_name:<22} | {m['macro_f1']:<10.4f} | {m['balanced_acc']:<10.4f} | {m['mcc']:<8.4f} | {m['recall_classe_0']:<8.2%} | {m['recall_classe_1']:<8.2%} | {m['recall_classe_2']:<8.2%} | {m['recall_classe_3']:<8.2%}")
        print("-" * 105)

    print(f"Estágio 1 Binário C2: Sensibilidade de Risco: {res_c2['Hierarquico_Estagio1_Binario']['recall_risco']:.2%} | Especificidade: {res_c2['Hierarquico_Estagio1_Binario']['especificidade_regular']:.2%}")
    print(f"Resultados gravados em: {res_file.name}")
    print(f"Tempo total: {time.time() - t_start:.1f}s")


if __name__ == "__main__":
    main()
