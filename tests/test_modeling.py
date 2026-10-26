"""Testes unitarios para os componentes de modelagem supervisionada da Sprint 6."""
import numpy as np
import pandas as pd
import pytest

from src.modeling.baselines import DummyMajorityClassifier, RandomForestTabularBaseline
from src.modeling.lightgbm_engine import LightGBMClassifierEngine
from src.modeling.loader import (
    compute_class_weights,
    compute_sample_weights,
    extract_embedding_matrix,
    extract_tabular_features,
    prepare_dataset_matrices,
)
from src.modeling.metrics import compute_confusion_matrix, evaluate_multiclass
from src.modeling.splitter import StratifiedGroupSplitter, audit_splits


def test_confusion_matrix_and_metrics():
    """Valida o cálculo exato da matriz de confusão e métricas multiclasse."""
    y_true = np.array([0, 0, 1, 1, 2, 3])
    y_pred = np.array([0, 0, 1, 0, 2, 2])  # 1 erro na classe 1, 1 erro na classe 3

    cm = compute_confusion_matrix(y_true, y_pred, num_classes=4)
    assert cm.shape == (4, 4)
    assert cm[0, 0] == 2  # Dois zeros acertados
    assert cm[1, 1] == 1  # Um 1 acertado
    assert cm[1, 0] == 1  # Um 1 predito como 0
    assert cm[2, 2] == 1  # Um 2 acertado
    assert cm[3, 2] == 1  # Um 3 predito como 2

    metrics = evaluate_multiclass(y_true, y_pred, num_classes=4)
    assert metrics["total_amostras"] == 6
    assert 0.0 < metrics["macro_f1"] < 1.0
    assert "por_classe" in metrics
    assert metrics["por_classe"]["Classe_0"]["tp"] == 2
    assert metrics["por_classe"]["Classe_2"]["tp"] == 1


def test_stratified_group_splitter_no_leakage():
    """Valida que o StratifiedGroupSplitter garante zero vazamento de obras entre dobras."""
    np.random.seed(42)
    n_samples = 400
    n_groups = 250

    groups = np.array([f"OBRA_{i % n_groups}" for i in range(n_samples)])
    # Desbalanceamento severo: 85% classe 0, 8% classe 1, 2% classe 2, 5% classe 3
    y = np.random.choice([0, 1, 2, 3], size=n_samples, p=[0.85, 0.08, 0.02, 0.05])
    X = np.random.randn(n_samples, 10).astype(np.float32)

    splitter = StratifiedGroupSplitter(n_splits=5, seed=42)
    splits = list(splitter.split(X, y, groups, num_classes=4))

    assert len(splits) == 5

    audit = audit_splits(splits, y, groups, num_classes=4)
    for rep in audit:
        assert rep["overlap_groups"] == 0, f"Vazamento detectado no fold {rep['fold']}"
        assert rep["val_size"] > 0
        assert rep["train_size"] > 0


def test_feature_extraction_and_weights():
    """Valida a extracao de atributos tabulares, embeddings e pesos de classe."""
    df_mock = pd.DataFrame({
        "valor_investimento": [1000.0, None, 500.0],
        "valor_desbloqueado": [800.0, 200.0, None],
        "exec_fisica": [50.0, 10.0, 90.0],
        "exec_financeira": [45.0, 15.0, 85.0],
        "has_embedding": [True, False, True],
        "base": ["SICONV", "CAIXA", "SICONV"],
        "uf": ["SP", "RJ", "SP"],
        "embedding": [
            np.ones(768, dtype=np.float32),
            None,
            np.full(768, 0.5, dtype=np.float32),
        ],
        "label_risco": [0, 0, 1],
    })

    X_tab, names, maps = extract_tabular_features(df_mock)
    assert X_tab.shape == (3, 9)  # 7 numericos + 2 categoricos

    X_emb, emb_names = extract_embedding_matrix(df_mock, embedding_dim=768)
    assert X_emb.shape == (3, 768)
    assert np.all(X_emb[1] == 0.0)  # Caso None preenchido com zero
    assert np.all(X_emb[0] == 1.0)

    y = df_mock["label_risco"].to_numpy()
    weights = compute_class_weights(y, num_classes=2)
    assert weights[0] < weights[1]  # Classe 1 mais rara deve ter peso maior

    sample_w = compute_sample_weights(y, weights)
    assert len(sample_w) == 3
    assert sample_w[2] > sample_w[0]


def test_dummy_classifier():
    """Valida que o DummyMajorityClassifier prediz a classe dominante."""
    clf = DummyMajorityClassifier()
    X = np.zeros((10, 5))
    y = np.array([0, 0, 0, 1, 2, 0, 0, 3, 0, 0])  # Classe 0 domina

    clf.fit(X, y)
    preds = clf.predict(X)
    assert np.all(preds == 0)

    probas = clf.predict_proba(X)
    assert probas.shape == (10, 4)
    assert probas[0, 0] > 0.5


def test_lightgbm_engine_synthetic_768d():
    """Valida que o LightGBMClassifierEngine treina e infere sobre 768 dimensoes."""
    np.random.seed(42)
    n_samples = 120
    X = np.random.randn(n_samples, 768).astype(np.float32)
    y = np.random.choice([0, 1, 2, 3], size=n_samples, p=[0.7, 0.1, 0.05, 0.15])

    weights = compute_class_weights(y, num_classes=4)

    engine = LightGBMClassifierEngine(
        n_estimators=10,
        learning_rate=0.1,
        num_leaves=15,
        max_depth=4,
        min_child_samples=5,
        seed=42,
        class_weights=weights,
    )

    engine.fit(X, y)
    assert engine.booster is not None

    preds = engine.predict(X[:10])
    assert len(preds) == 10
    assert preds.dtype == np.int32

    probas = engine.predict_proba(X[:10])
    assert probas.shape == (10, 4)
    assert np.allclose(np.sum(probas, axis=1), 1.0, atol=1e-5)


def test_feature_profiles_and_imputations():
    """Valida perfis de atributos c0 vs c1_sem_proxies e passagem de imputacoes."""
    df_train = pd.DataFrame({
        "valor_investimento": [100.0, 200.0, 300.0],
        "valor_desbloqueado": [50.0, np.nan, 150.0],  # mediana train = 100.0
        "exec_fisica": [10.0, 20.0, 30.0],
        "exec_financeira": [10.0, 20.0, 30.0],
        "num_docs_validos": [1, 2, 0],
        "num_chunks_validos": [2, 4, 0],
        "has_embedding": [True, True, False],
        "base": ["SICONV", "CAIXA", "SICONV"],
        "uf": ["SP", "RJ", "SP"],
        "label_risco": [0, 1, 0],
        "id_tcu": ["1", "2", "3"]
    })

    # 1. Perfil C0 inclui proxies documentais
    res_c0 = prepare_dataset_matrices(df_train, feature_profile="c0_original", include_embeddings=False)
    assert "has_embedding" in res_c0["tab_feature_names"]
    assert "num_docs_validos" in res_c0["tab_feature_names"]

    # 2. Perfil C1 exclui proxies documentais
    res_c1 = prepare_dataset_matrices(df_train, feature_profile="c1_sem_proxies", include_embeddings=False)
    assert "has_embedding" not in res_c1["tab_feature_names"]
    assert "num_docs_validos" not in res_c1["tab_feature_names"]
    assert res_c1["tab_feature_names"] == ["valor_investimento", "valor_desbloqueado", "exec_fisica", "exec_financeira", "base_cat", "uf_cat"]
    assert res_c1["numeric_imputations"]["valor_desbloqueado"] == 100.0

    # 3. Aplicar imputacoes do treino no teste
    df_test = pd.DataFrame({
        "valor_investimento": [np.nan],
        "valor_desbloqueado": [np.nan],
        "exec_fisica": [np.nan],
        "exec_financeira": [np.nan],
        "base": ["CAIXA"],
        "uf": ["SP"],
        "label_risco": [0],
        "id_tcu": ["4"]
    })
    res_test = prepare_dataset_matrices(
        df_test,
        categorical_mappings=res_c1["categorical_mappings"],
        numeric_imputations=res_c1["numeric_imputations"],
        feature_profile="c1_sem_proxies",
        include_embeddings=False
    )
    # valor_desbloqueado no teste deve receber exatamente a mediana do treino (100.0)
    col_idx = res_test["tab_feature_names"].index("valor_desbloqueado")
    assert res_test["X_tab"][0, col_idx] == 100.0

