"""Classificador hierarquico em dois estagios para deteccao de risco e atribuicao causal."""
import time
from typing import Any, Dict, List, Optional, Tuple
import lightgbm as lgb
import numpy as np


class BinaryRiskDetector:
    """Estagio 1: Classificador binario especializado em detectar Regular (0) vs. Risco/Paralisacao (1)."""

    def __init__(
        self,
        n_estimators: int = 120,
        learning_rate: float = 0.05,
        num_leaves: int = 35,
        max_depth: int = 6,
        min_child_samples: int = 20,
        feature_fraction: float = 0.8,
        seed: int = 42,
        use_balanced_scale: bool = True,
    ):
        self.n_estimators = n_estimators
        self.learning_rate = learning_rate
        self.num_leaves = num_leaves
        self.max_depth = max_depth
        self.min_child_samples = min_child_samples
        self.feature_fraction = feature_fraction
        self.seed = seed
        self.use_balanced_scale = use_balanced_scale
        self.booster: Optional[lgb.Booster] = None
        self.feature_names: Optional[List[str]] = None
        self.scale_pos_weight: float = 1.0

    def fit(
        self,
        X: np.ndarray,
        y_bin: np.ndarray,
        feature_names: Optional[List[str]] = None
    ) -> "BinaryRiskDetector":
        n_neg = int(np.sum(y_bin == 0))
        n_pos = int(np.sum(y_bin == 1))

        if self.use_balanced_scale and n_pos > 0:
            self.scale_pos_weight = float(n_neg / n_pos)
        else:
            self.scale_pos_weight = 1.0

        ds = lgb.Dataset(X, label=y_bin, feature_name=feature_names or "auto", free_raw_data=False)

        params = {
            "objective": "binary",
            "metric": "binary_logloss",
            "scale_pos_weight": self.scale_pos_weight,
            "learning_rate": self.learning_rate,
            "num_leaves": self.num_leaves,
            "max_depth": self.max_depth,
            "min_child_samples": self.min_child_samples,
            "feature_fraction": self.feature_fraction,
            "seed": self.seed,
            "verbose": -1,
            "num_threads": 4,
            "max_bin": 255,
        }

        self.booster = lgb.train(params, ds, num_boost_round=self.n_estimators)
        self.feature_names = feature_names
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if self.booster is None:
            raise RuntimeError("O modelo precisa ser ajustado antes de predizer.")
        p_raw = np.asarray(self.booster.predict(X), dtype=np.float32)
        # Retorna matriz (N, 2): [P(classe 0), P(risco)]
        p_pos = p_raw.reshape(-1, 1)
        p_neg = 1.0 - p_pos
        return np.hstack([p_neg, p_pos])

    def predict(self, X: np.ndarray, threshold: float = 0.5) -> np.ndarray:
        probas = self.predict_proba(X)[:, 1]
        return (probas >= threshold).astype(np.int32)


class ConditionalCausalClassifier:
    """Estagio 2: Classificador multiclasse especializado nas causas (1 Tecnica, 2 Orcamentaria, 3 Abandono)."""

    def __init__(
        self,
        n_estimators: int = 100,
        learning_rate: float = 0.05,
        num_leaves: int = 31,
        max_depth: int = 6,
        min_child_samples: int = 10,
        feature_fraction: float = 0.8,
        seed: int = 42,
        use_balanced_weights: bool = True,
    ):
        self.n_estimators = n_estimators
        self.learning_rate = learning_rate
        self.num_leaves = num_leaves
        self.max_depth = max_depth
        self.min_child_samples = min_child_samples
        self.feature_fraction = feature_fraction
        self.seed = seed
        self.use_balanced_weights = use_balanced_weights
        self.booster: Optional[lgb.Booster] = None
        self.feature_names: Optional[List[str]] = None
        self.target_classes = [1, 2, 3]

    def fit(
        self,
        X_causas: np.ndarray,
        y_causas: np.ndarray,
        feature_names: Optional[List[str]] = None
    ) -> "ConditionalCausalClassifier":
        if len(X_causas) == 0:
            raise ValueError("Conjunto de causas vazio para o Estagio 2.")

        # Mapeia classes {1, 2, 3} para indices internos {0, 1, 2}
        y_mapped = np.array([self.target_classes.index(c) for c in y_causas], dtype=np.int32)

        sample_weights = None
        if self.use_balanced_weights:
            n_samples = len(y_mapped)
            weights_map = {}
            for i, c in enumerate(self.target_classes):
                n_c = int(np.sum(y_causas == c))
                weights_map[i] = float(n_samples / (3.0 * n_c)) if n_c > 0 else 1.0

            sample_weights = np.empty(n_samples, dtype=np.float32)
            for i, w in weights_map.items():
                sample_weights[y_mapped == i] = w

        ds = lgb.Dataset(
            X_causas,
            label=y_mapped,
            weight=sample_weights,
            feature_name=feature_names or "auto",
            free_raw_data=False
        )

        params = {
            "objective": "multiclass",
            "num_class": 3,
            "learning_rate": self.learning_rate,
            "num_leaves": self.num_leaves,
            "max_depth": self.max_depth,
            "min_child_samples": self.min_child_samples,
            "feature_fraction": self.feature_fraction,
            "seed": self.seed,
            "verbose": -1,
            "num_threads": 4,
            "max_bin": 255,
        }

        self.booster = lgb.train(params, ds, num_boost_round=self.n_estimators)
        self.feature_names = feature_names
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if self.booster is None:
            raise RuntimeError("O modelo precisa ser ajustado antes de predizer.")
        probas = np.asarray(self.booster.predict(X), dtype=np.float32)
        if probas.ndim == 1 and len(X) > 0:
            probas = probas.reshape(len(X), 3)
        return probas

    def predict(self, X: np.ndarray) -> np.ndarray:
        probas = self.predict_proba(X)
        best_indices = np.argmax(probas, axis=1)
        # Remapeia {0, 1, 2} de volta para {1, 2, 3}
        return np.array([self.target_classes[idx] for idx in best_indices], dtype=np.int32)


class TwoStageHierarchicalClassifier:
    """Classificador integrado em dois estagios com combinacao probabilistica ou cascata dura."""

    def __init__(
        self,
        n_estimators_stage1: int = 120,
        n_estimators_stage2: int = 100,
        learning_rate: float = 0.05,
        seed: int = 42,
        stage1_balanced: bool = True,
        stage2_balanced: bool = True,
    ):
        self.seed = seed
        self.stage1 = BinaryRiskDetector(
            n_estimators=n_estimators_stage1,
            learning_rate=learning_rate,
            seed=seed,
            use_balanced_scale=stage1_balanced,
        )
        self.stage2 = ConditionalCausalClassifier(
            n_estimators=n_estimators_stage2,
            learning_rate=learning_rate,
            seed=seed,
            use_balanced_weights=stage2_balanced,
        )
        self.training_time_seconds: float = 0.0

    def fit(self, X: np.ndarray, y: np.ndarray, feature_names: Optional[List[str]] = None) -> "TwoStageHierarchicalClassifier":
        t0 = time.perf_counter()

        # 1. Binarizacao para o Estagio 1
        y_bin = (y > 0).astype(np.int32)
        self.stage1.fit(X, y_bin, feature_names=feature_names)

        # 2. Filtragem causal para o Estagio 2
        mask_causal = (y > 0)
        X_causas = X[mask_causal]
        y_causas = y[mask_causal]

        self.stage2.fit(X_causas, y_causas, feature_names=feature_names)
        self.training_time_seconds = time.perf_counter() - t0
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Calcula probabilidades conjuntas: P(Y=0) = 1 - P_risco; P(Y=c) = P_risco * P_causa."""
        p_bin = self.stage1.predict_proba(X)        # (N, 2): [1 - p_risco, p_risco]
        p_causal = self.stage2.predict_proba(X)     # (N, 3): [p_tecnica, p_orcamentaria, p_abandono]

        p_risco = p_bin[:, 1].reshape(-1, 1)

        p_0 = p_bin[:, 0].reshape(-1, 1)
        p_1 = p_risco * p_causal[:, 0].reshape(-1, 1)
        p_2 = p_risco * p_causal[:, 1].reshape(-1, 1)
        p_3 = p_risco * p_causal[:, 2].reshape(-1, 1)

        p_total = np.hstack([p_0, p_1, p_2, p_3])

        # Normalizacao para garantir soma estrita 1.0 por observacao
        row_sums = np.sum(p_total, axis=1, keepdims=True)
        row_sums[row_sums == 0] = 1.0
        return (p_total / row_sums).astype(np.float32)

    def predict(
        self,
        X: np.ndarray,
        mode: str = "soft",
        risk_threshold: float = 0.50,
        class2_multiplier: float = 1.0
    ) -> np.ndarray:
        """Prediz classe em {0, 1, 2, 3} via cascata suave (soft) ou cascata dura (hard)."""
        if mode == "hard":
            is_risk = self.stage1.predict(X, threshold=risk_threshold)
            preds = np.zeros(len(X), dtype=np.int32)
            if np.any(is_risk):
                idx_risk = np.where(is_risk == 1)[0]
                preds_causal = self.stage2.predict(X[idx_risk])
                preds[idx_risk] = preds_causal
            return preds
        elif mode == "soft":
            probas = self.predict_proba(X)
            if class2_multiplier != 1.0:
                probas[:, 2] *= class2_multiplier
            return np.argmax(probas, axis=1).astype(np.int32)
        else:
            raise ValueError(f"Modo desconhecido: {mode}. Use 'soft' ou 'hard'.")
