"""Classificadores de referencia inicial: Baseline Trivial e Random Forest Tabular."""
from typing import Any, Dict, Optional
import lightgbm as lgb
import numpy as np


class DummyMajorityClassifier:
    """Classificador trivial que sempre prediz a classe majoritaria do conjunto de treino."""

    def __init__(self):
        self.majority_class: Optional[int] = None
        self.num_classes: int = 4
        self.class_probabilities: Optional[np.ndarray] = None

    def fit(self, X: np.ndarray, y: np.ndarray) -> "DummyMajorityClassifier":
        counts = np.bincount(y, minlength=self.num_classes)
        self.majority_class = int(np.argmax(counts))
        self.class_probabilities = counts / float(np.sum(counts))
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        if self.majority_class is None:
            raise RuntimeError("O modelo precisa ser ajustado antes de predizer.")
        return np.full(len(X), self.majority_class, dtype=np.int32)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if self.class_probabilities is None:
            raise RuntimeError("O modelo precisa ser ajustado antes de predizer.")
        return np.tile(self.class_probabilities, (len(X), 1))


class RandomForestTabularBaseline:
    """Baseline Random Forest operando exclusivamente sobre atributos tabulares via LightGBM RF mode."""

    def __init__(
        self,
        n_estimators: int = 100,
        max_depth: int = 8,
        seed: int = 42,
        class_weights: Optional[Dict[int, float]] = None
    ):
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.seed = seed
        self.class_weights = class_weights
        self.booster: Optional[lgb.Booster] = None
        self.num_classes: int = 4

    def fit(self, X: np.ndarray, y: np.ndarray) -> "RandomForestTabularBaseline":
        sample_weights = None
        if self.class_weights:
            sample_weights = np.empty(len(y), dtype=np.float32)
            for c, w in self.class_weights.items():
                sample_weights[y == c] = w

        ds = lgb.Dataset(X, label=y, weight=sample_weights, free_raw_data=False)

        # Configuracao de Random Forest no motor LightGBM
        params = {
            "objective": "multiclass",
            "num_class": self.num_classes,
            "boosting_type": "rf",
            "bagging_fraction": 0.8,
            "bagging_freq": 1,
            "feature_fraction": 0.8,
            "max_depth": self.max_depth,
            "num_leaves": min(2 ** self.max_depth, 63),
            "seed": self.seed,
            "verbose": -1,
            "num_threads": 4,
        }

        self.booster = lgb.train(params, ds, num_boost_round=self.n_estimators)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        probas = self.predict_proba(X)
        if len(probas) == 0:
            return np.empty(0, dtype=np.int32)
        if probas.ndim == 1:
            return (probas >= 0.5).astype(np.int32)
        return np.argmax(probas, axis=1).astype(np.int32)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if self.booster is None:
            raise RuntimeError("O modelo precisa ser ajustado antes de predizer.")
        if len(X) == 0:
            return np.empty((0, self.num_classes), dtype=np.float32)
        preds = np.asarray(self.booster.predict(X), dtype=np.float32)
        if preds.ndim == 1 and len(X) > 0 and self.num_classes > 2:
            preds = preds.reshape(len(X), self.num_classes)
        return preds
