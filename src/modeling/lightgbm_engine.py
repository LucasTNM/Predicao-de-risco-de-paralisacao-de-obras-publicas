"""Motor de treinamento e predicao do LightGBM otimizado para alta dimensionalidade (768d)."""
import time
from typing import Any, Dict, List, Optional, Tuple
import lightgbm as lgb
import numpy as np


class LightGBMClassifierEngine:
    """Classificador LightGBM multiclasse otimizado para combinacao de atributos tabulares e embeddings."""

    def __init__(
        self,
        n_estimators: int = 150,
        learning_rate: float = 0.05,
        num_leaves: int = 63,
        max_depth: int = -1,
        min_child_samples: int = 15,
        feature_fraction: float = 0.8,
        bagging_fraction: float = 0.8,
        bagging_freq: int = 1,
        seed: int = 42,
        class_weights: Optional[Dict[int, float]] = None,
        use_goss: bool = False,
        num_classes: int = 4,
    ):
        self.n_estimators = n_estimators
        self.learning_rate = learning_rate
        self.num_leaves = num_leaves
        self.max_depth = max_depth
        self.min_child_samples = min_child_samples
        self.feature_fraction = feature_fraction
        self.bagging_fraction = bagging_fraction
        self.bagging_freq = bagging_freq
        self.seed = seed
        self.class_weights = class_weights
        self.use_goss = use_goss
        self.num_classes = num_classes

        self.booster: Optional[lgb.Booster] = None
        self.feature_names: Optional[List[str]] = None
        self.training_time_seconds: float = 0.0

    def fit(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        feature_names: Optional[List[str]] = None
    ) -> "LightGBMClassifierEngine":
        """Treina o modelo LightGBM aplicando pesos de classe balanceados."""
        start_time = time.perf_counter()

        # Atribui pesos amostrais baseados na ponderacao balanceada das classes
        sample_weights = None
        if self.class_weights:
            sample_weights = np.empty(len(y_train), dtype=np.float32)
            for c, w in self.class_weights.items():
                sample_weights[y_train == c] = w

        ds_train = lgb.Dataset(
            X_train,
            label=y_train,
            weight=sample_weights,
            feature_name=feature_names or "auto",
            free_raw_data=False
        )

        valid_sets = [ds_train]
        valid_names = ["train"]

        if X_val is not None and y_val is not None:
            ds_val = lgb.Dataset(
                X_val,
                label=y_val,
                feature_name=feature_names or "auto",
                reference=ds_train,
                free_raw_data=False
            )
            valid_sets.append(ds_val)
            valid_names.append("val")

        boosting_type = "goss" if self.use_goss else "gbdt"

        params = {
            "objective": "multiclass",
            "num_class": self.num_classes,
            "boosting_type": boosting_type,
            "learning_rate": self.learning_rate,
            "num_leaves": self.num_leaves,
            "max_depth": self.max_depth,
            "min_child_samples": self.min_child_samples,
            "feature_fraction": self.feature_fraction,
            "seed": self.seed,
            "verbose": -1,
            "num_threads": 4,
            "max_bin": 255,  # Divisao por histogramas de alta precisao e baixo consumo de memoria
        }

        # GOSS nao permite bagging simultaneo
        if not self.use_goss:
            params["bagging_fraction"] = self.bagging_fraction
            params["bagging_freq"] = self.bagging_freq

        callbacks = []

        self.booster = lgb.train(
            params,
            ds_train,
            num_boost_round=self.n_estimators,
            valid_sets=valid_sets,
            valid_names=valid_names,
            callbacks=callbacks
        )

        self.feature_names = feature_names
        self.training_time_seconds = time.perf_counter() - start_time
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        probas = self.predict_proba(X)
        return np.argmax(probas, axis=1).astype(np.int32)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if self.booster is None:
            raise RuntimeError("O modelo precisa ser ajustado antes de predizer.")
        return np.asarray(self.booster.predict(X), dtype=np.float32)

    def get_feature_importances(self, top_k: int = 20, importance_type: str = "gain") -> List[Tuple[str, float]]:
        """Retorna os atributos mais importantes com base no ganho de divisao ou contagem."""
        if self.booster is None:
            return []

        importances = self.booster.feature_importance(importance_type=importance_type)
        names = self.feature_names or [f"feat_{i}" for i in range(len(importances))]

        paired = sorted(zip(names, importances), key=lambda x: x[1], reverse=True)
        return [(str(k), float(v)) for k, v in paired[:top_k]]
