"""Testes unitarios para a classificacao hierarquica em dois estagios."""
import numpy as np
import pytest

from src.modeling.hierarchical import (
    BinaryRiskDetector,
    ConditionalCausalClassifier,
    TwoStageHierarchicalClassifier,
)


def test_binary_risk_detector_predictions():
    """Valida o Estagio 1 na deteccao binaria de risco."""
    np.random.seed(42)
    n_samples = 100
    X = np.random.randn(n_samples, 20).astype(np.float32)
    y_bin = np.random.choice([0, 1], size=n_samples, p=[0.9, 0.1]).astype(np.int32)

    detector = BinaryRiskDetector(n_estimators=10, seed=42)
    detector.fit(X, y_bin)

    probas = detector.predict_proba(X)
    assert probas.shape == (n_samples, 2)
    assert np.allclose(np.sum(probas, axis=1), 1.0, atol=1e-5)

    preds_50 = detector.predict(X, threshold=0.50)
    preds_20 = detector.predict(X, threshold=0.20)
    # Limiar menor deve gerar pelo menos a mesma quantidade ou mais de positivos
    assert np.sum(preds_20 == 1) >= np.sum(preds_50 == 1)


def test_conditional_causal_classifier_predictions():
    """Valida o Estagio 2 na atribuicao causal para classes {1, 2, 3}."""
    np.random.seed(42)
    n_samples = 60
    X = np.random.randn(n_samples, 20).astype(np.float32)
    y_causas = np.random.choice([1, 2, 3], size=n_samples, p=[0.6, 0.1, 0.3]).astype(np.int32)

    causal = ConditionalCausalClassifier(n_estimators=10, seed=42)
    causal.fit(X, y_causas)

    probas = causal.predict_proba(X)
    assert probas.shape == (n_samples, 3)
    assert np.allclose(np.sum(probas, axis=1), 1.0, atol=1e-5)

    preds = causal.predict(X)
    assert len(preds) == n_samples
    assert set(np.unique(preds)).issubset({1, 2, 3})


def test_two_stage_hierarchical_classifier_full_flow():
    """Valida a integracao dos dois estagios com probabilidades conjuntas e cascata."""
    np.random.seed(42)
    n_samples = 150
    X = np.random.randn(n_samples, 30).astype(np.float32)
    # 85% classe 0, 7% classe 1, 2% classe 2, 6% classe 3
    y = np.random.choice([0, 1, 2, 3], size=n_samples, p=[0.85, 0.07, 0.02, 0.06]).astype(np.int32)

    model = TwoStageHierarchicalClassifier(
        n_estimators_stage1=10,
        n_estimators_stage2=10,
        seed=42
    )
    model.fit(X, y)

    # 1. Probabilidades conjuntas
    probas = model.predict_proba(X)
    assert probas.shape == (n_samples, 4)
    assert np.allclose(np.sum(probas, axis=1), 1.0, atol=1e-5)
    assert np.all(probas >= 0.0)

    # 2. Predicao soft
    preds_soft = model.predict(X, mode="soft")
    assert len(preds_soft) == n_samples
    assert set(np.unique(preds_soft)).issubset({0, 1, 2, 3})

    # 3. Predicao hard
    preds_hard = model.predict(X, mode="hard", risk_threshold=0.40)
    assert len(preds_hard) == n_samples
    assert set(np.unique(preds_hard)).issubset({0, 1, 2, 3})

    # 4. Multiplicador de classe 2
    preds_boost = model.predict(X, mode="soft", class2_multiplier=5.0)
    assert np.sum(preds_boost == 2) >= np.sum(preds_soft == 2)
