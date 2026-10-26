# -*- coding: utf-8 -*-
"""
scripts/rebaseline_sprint7.py
=============================
Executa o Rebaseline oficial da Feature 018 nas 5 dobras agrupadas de treino_dev:
4 Modelos x 4 Cenários experimentais (C0, C1, C2, C3).

Modelos:
- Dummy_Majoritario
- RandomForest_Tabular
- LightGBM_Conjunto
- Hierarquico_Campeao (Estágio 1 Binário + Estágio 2 Causal x5.0)

Cenários:
- C0: Original Sprint 6 (Controle de auditoria)
- C1: Tabular limpo (sem proxies documentais, medianas aprendidas no treino)
- C2: Texto limpo sem fichas sintéticas (apenas documentos autênticos)
- C3: Fichas sintéticas mascaradas (situação expurgada) + documentos autênticos
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Tuple

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
from src.modeling.loader import load_dataset, prepare_dataset_matrices
from src.modeling.metrics import compute_confusion_matrix
from src.modeling.splitter import StratifiedGroupSplitter


def evaluate_predictions(y_true: np.ndarray, y_pred: np.ndarray, y_proba: np.ndarray = None) -> Dict[str, Any]:
    """Calcula métricas robustas multiclasse para validação."""
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


def run_5fold_cv_for_scenario(
    df: pd.DataFrame,
    scenario_id: str,
    override_embeddings: np.ndarray = None,
    n_splits: int = 5,
    seed: int = 42
) -> Dict[str, Any]:
    """Executa a validação cruzada agrupada para os 4 modelos sob o cenário especificado."""
    y_all = df["label_risco"].to_numpy(dtype=np.int32)
    groups_all = df["id_tcu"].astype(str).to_numpy()
    dummy_X = np.zeros((len(df), 1), dtype=np.float32)
    splitter = StratifiedGroupSplitter(n_splits=n_splits, seed=seed)
    folds = list(splitter.split(dummy_X, y_all, groups_all))

    # Determinar perfil de atributos
    is_c0 = (scenario_id == "C0")
    feature_prof = "c0_original" if is_c0 else "c1_sem_proxies"
    inc_emb = (scenario_id in ["C0", "C2", "C3"])

    models_to_run = ["Dummy", "RandomForest", "LightGBM_Conjunto", "Hierarquico_Campeao"]
    oof_predictions = {m: np.zeros(len(df), dtype=np.int32) for m in models_to_run}
    oof_probas = {m: np.zeros((len(df), 4), dtype=np.float32) for m in models_to_run}
    times = {m: 0.0 for m in models_to_run}

    print(f"\n[{scenario_id}] Iniciando CV em 5 dobras agrupadas (Perfil: {feature_prof}, Embeddings: {inc_emb})...")

    for fold_idx, (train_idx, val_idx) in enumerate(folds, 1):
        df_train = df.iloc[train_idx]
        df_val = df.iloc[val_idx]

        emb_train = override_embeddings[train_idx] if override_embeddings is not None else None
        emb_val = override_embeddings[val_idx] if override_embeddings is not None else None

        # 1. Ajustar mapeamentos e imputações ESTRITAMENTE no treino do fold
        data_train = prepare_dataset_matrices(
            df_train,
            include_embeddings=inc_emb,
            feature_profile=feature_prof,
            override_embeddings=emb_train
        )

        # 2. Aplicar mapeamentos e medianas do treino na validação
        data_val = prepare_dataset_matrices(
            df_val,
            categorical_mappings=data_train["categorical_mappings"],
            numeric_imputations=data_train["numeric_imputations"],
            include_embeddings=inc_emb,
            feature_profile=feature_prof,
            override_embeddings=emb_val
        )

        X_tr = data_train["X_comb"]
        y_tr = data_train["y"]
        cw = data_train["class_weights"]

        X_va = data_val["X_comb"]

        # Modelo 1: Dummy
        t0 = time.time()
        dummy = DummyMajorityClassifier()
        dummy.fit(X_tr, y_tr)
        oof_predictions["Dummy"][val_idx] = dummy.predict(X_va)
        oof_probas["Dummy"][val_idx] = dummy.predict_proba(X_va)
        times["Dummy"] += (time.time() - t0)

        # Modelo 2: RandomForest (apenas tabular)
        t0 = time.time()
        rf = RandomForestTabularBaseline(n_estimators=100, max_depth=12, seed=seed, class_weights=cw)
        rf.fit(data_train["X_tab"], y_tr)
        oof_predictions["RandomForest"][val_idx] = rf.predict(data_val["X_tab"])
        oof_probas["RandomForest"][val_idx] = rf.predict_proba(data_val["X_tab"])
        times["RandomForest"] += (time.time() - t0)

        # Modelo 3: LightGBM Conjunto
        t0 = time.time()
        lgb_conj = LightGBMClassifierEngine(
            n_estimators=150,
            learning_rate=0.05,
            num_leaves=31,
            max_depth=6,
            min_child_samples=20,
            feature_fraction=0.8,
            bagging_fraction=0.8,
            seed=seed,
            class_weights=cw
        )
        lgb_conj.fit(X_tr, y_tr)
        oof_predictions["LightGBM_Conjunto"][val_idx] = lgb_conj.predict(X_va)
        oof_probas["LightGBM_Conjunto"][val_idx] = lgb_conj.predict_proba(X_va)
        times["LightGBM_Conjunto"] += (time.time() - t0)

        # Modelo 4: Hierárquico Campeão (Estágio 1 Binário + Estágio 2 Causal)
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
        oof_predictions["Hierarquico_Campeao"][val_idx] = hier.predict(X_va)
        oof_probas["Hierarquico_Campeao"][val_idx] = hier.predict_proba(X_va)
        times["Hierarquico_Campeao"] += (time.time() - t0)

    y_real = df["label_risco"].to_numpy(dtype=np.int32)
    scenario_results = {}
    for m in models_to_run:
        metrics = evaluate_predictions(y_real, oof_predictions[m], oof_probas[m])
        metrics["tempo_total_cv"] = round(times[m], 2)
        scenario_results[m] = metrics
        print(f"  [{scenario_id}] {m:<20} -> Macro-F1: {metrics['macro_f1']:.4f} | Bal.Acc: {metrics['balanced_acc']:.4f} | Rec2: {metrics['recall_classe_2']:.2%} | Rec3: {metrics['recall_classe_3']:.2%} ({times[m]:.1f}s)")

    return scenario_results


def main():
    parser = argparse.ArgumentParser(description="Executa o rebaseline C0-C3 da Sprint 7")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    t_start = time.time()
    out_dir = ROOT / "dados_processados" / "sprint7"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Carregar dataset de desenvolvimento
    dev_path = ROOT / "dados_processados" / "sprint6" / "dataset_treino_dev_2025.parquet"
    print(f"[Rebaseline] Carregando {dev_path.name}...")
    df_dev = load_dataset(dev_path)

    # 2. Carregar matrizes de embeddings C2 e C3 geradas pela T006
    c2_path = out_dir / "embeddings_c2_sem_fichas.npz"
    c3_path = out_dir / "embeddings_c3_mascarados.npz"
    if not c2_path.exists() or not c3_path.exists():
        raise FileNotFoundError("Artefatos de embeddings C2 ou C3 ausentes. Execute scripts/gerar_agregados_sprint7.py primeiro!")

    npz_c2 = np.load(c2_path)
    X_dev_c2 = npz_c2["X_dev"]

    npz_c3 = np.load(c3_path)
    X_dev_c3 = npz_c3["X_dev"]

    all_benchmarks: Dict[str, Any] = {}

    # Executar Cenário C0: Controle Histórico da Sprint 6
    all_benchmarks["C0_Original"] = run_5fold_cv_for_scenario(df_dev, "C0", seed=args.seed)

    # Executar Cenário C1: Tabular sem Proxies Documentais
    all_benchmarks["C1_Tabular_Limpo"] = run_5fold_cv_for_scenario(df_dev, "C1", seed=args.seed)

    # Executar Cenário C2: Texto Limpo sem Fichas Sintéticas
    all_benchmarks["C2_Texto_Sem_Fichas"] = run_5fold_cv_for_scenario(df_dev, "C2", override_embeddings=X_dev_c2, seed=args.seed)

    # Executar Cenário C3: Fichas Sintéticas Mascaradas
    all_benchmarks["C3_Fichas_Mascaradas"] = run_5fold_cv_for_scenario(df_dev, "C3", override_embeddings=X_dev_c3, seed=args.seed)

    total_duration = time.time() - t_start

    # Salvar resultados consolidados em JSON
    res_path = out_dir / "benchmark_rebaseline_sprint7.json"
    with open(res_path, "w", encoding="utf-8") as f:
        json.dump(all_benchmarks, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 100)
    print("RESUMO CONSOLIDADO DO REBASELINE EXPERIMENTAL (5 DOBRAS AGRUPADAS - 14.522 OBRAS)")
    print("=" * 100)
    print(f"{'Cenário':<22} | {'Modelo':<22} | {'Macro-F1':<10} | {'Bal. Acc':<10} | {'MCC':<8} | {'Rec. 0':<8} | {'Rec. 1':<8} | {'Rec. 2':<8} | {'Rec. 3':<8}")
    print("-" * 115)

    for scen_name, scen_res in all_benchmarks.items():
        for mod_name, m in scen_res.items():
            print(f"{scen_name:<22} | {mod_name:<22} | {m['macro_f1']:<10.4f} | {m['balanced_acc']:<10.4f} | {m['mcc']:<8.4f} | {m['recall_classe_0']:<8.2%} | {m['recall_classe_1']:<8.2%} | {m['recall_classe_2']:<8.2%} | {m['recall_classe_3']:<8.2%}")
        print("-" * 115)

    print(f"Tempo total de execução do Rebaseline: {total_duration:.1f} segundos.")
    print(f"Resultados salvos em: {res_path.name}")


if __name__ == "__main__":
    main()
