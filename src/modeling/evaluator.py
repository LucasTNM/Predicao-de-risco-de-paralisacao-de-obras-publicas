"""Orquestrador de experimentos de validacao cruzada, benchmarking de modelos e metricas computacionais."""
import time
from typing import Any, Dict, List, Tuple
import numpy as np

from src.modeling.baselines import DummyMajorityClassifier, RandomForestTabularBaseline
from src.modeling.lightgbm_engine import LightGBMClassifierEngine
from src.modeling.loader import compute_class_weights
from src.modeling.metrics import evaluate_multiclass
from src.modeling.splitter import StratifiedGroupSplitter


CLASS_NAMES = [
    "0_Regular",
    "1_Defic_Tecnica",
    "2_Defic_Orcamentaria",
    "3_Abandono",
]


class CrossValidationEvaluator:
    """Executa validacao cruzada agrupada e consolida comparativo de desempenho."""

    def __init__(self, n_splits: int = 5, seed: int = 42):
        self.n_splits = n_splits
        self.seed = seed
        self.splitter = StratifiedGroupSplitter(n_splits=n_splits, seed=seed)

    def run_benchmark(
        self,
        X_tab: np.ndarray,
        X_comb: np.ndarray,
        y: np.ndarray,
        groups: np.ndarray,
        tab_feature_names: List[str],
        comb_feature_names: List[str],
    ) -> Dict[str, Any]:
        """Treina e avalia todos os modelos nas mesmas dobras agrupadas."""
        splits = list(self.splitter.split(X_comb, y, groups, num_classes=4))

        model_configs = [
            ("Dummy_Majoritario", "dummy", False),
            ("RandomForest_Tabular", "rf_tab", False),
            ("LightGBM_Tabular", "lgb_tab", False),
            ("LightGBM_Tabular_Balanceado", "lgb_tab", True),
            ("LightGBM_Hibrido_768d", "lgb_comb", False),
            ("LightGBM_Hibrido_768d_Balanceado", "lgb_comb", True),
        ]

        results: Dict[str, Any] = {}

        for model_name, model_type, use_balancing in model_configs:
            print(f"  [Benchmark] Avaliando {model_name} em {self.n_splits} dobras...")
            res = self._evaluate_single_model(
                model_name=model_name,
                model_type=model_type,
                use_balancing=use_balancing,
                splits=splits,
                X_tab=X_tab,
                X_comb=X_comb,
                y=y,
                tab_names=tab_feature_names,
                comb_names=comb_feature_names
            )
            results[model_name] = res

        return results

    def _evaluate_single_model(
        self,
        model_name: str,
        model_type: str,
        use_balancing: bool,
        splits: List[Tuple[np.ndarray, np.ndarray]],
        X_tab: np.ndarray,
        X_comb: np.ndarray,
        y: np.ndarray,
        tab_names: List[str],
        comb_names: List[str]
    ) -> Dict[str, Any]:
        n_samples = len(y)
        oof_preds = np.zeros(n_samples, dtype=np.int32)
        oof_probas = np.zeros((n_samples, 4), dtype=np.float32)

        fold_metrics: List[Dict[str, float]] = []
        train_times: List[float] = []

        for fold_idx, (train_idx, val_idx) in enumerate(splits):
            y_train, y_val = y[train_idx], y[val_idx]

            # Calcula pesos estritamente dentro da dobra de treino
            class_weights = compute_class_weights(y_train) if use_balancing else None

            # Seleciona matriz de entrada
            if model_type in ("rf_tab", "lgb_tab", "dummy"):
                X_tr = X_tab[train_idx]
                X_vl = X_tab[val_idx]
                feat_names = tab_names
            else:
                X_tr = X_comb[train_idx]
                X_vl = X_comb[val_idx]
                feat_names = comb_names

            t_start = time.perf_counter()

            if model_type == "dummy":
                model = DummyMajorityClassifier()
                model.fit(X_tr, y_train)
            elif model_type == "rf_tab":
                model = RandomForestTabularBaseline(
                    n_estimators=100,
                    max_depth=8,
                    seed=self.seed,
                    class_weights=class_weights
                )
                model.fit(X_tr, y_train)
            elif model_type in ("lgb_tab", "lgb_comb"):
                model = LightGBMClassifierEngine(
                    n_estimators=120,
                    learning_rate=0.05,
                    num_leaves=45,
                    max_depth=7,
                    min_child_samples=20,
                    seed=self.seed,
                    class_weights=class_weights,
                    use_goss=False,
                )
                model.fit(X_tr, y_train, feature_names=feat_names)
            else:
                raise ValueError(f"Modelo desconhecido: {model_type}")

            t_elapsed = time.perf_counter() - t_start
            train_times.append(t_elapsed)

            val_preds = model.predict(X_vl)
            val_probas = model.predict_proba(X_vl)

            oof_preds[val_idx] = val_preds
            oof_probas[val_idx] = val_probas

            # Metricas da dobra
            m_fold = evaluate_multiclass(y_val, val_preds, class_names=CLASS_NAMES)
            fold_metrics.append({
                "fold": fold_idx + 1,
                "macro_f1": m_fold["macro_f1"],
                "balanced_accuracy": m_fold["balanced_accuracy"],
                "rec_classe_2": m_fold["por_classe"]["2_Defic_Orcamentaria"]["recall"],
                "rec_classe_3": m_fold["por_classe"]["3_Abandono"]["recall"],
                "tempo_segundos": round(t_elapsed, 3),
            })

        # Metricas consolidadas fora da dobra (Out-Of-Fold)
        oof_eval = evaluate_multiclass(y, oof_preds, class_names=CLASS_NAMES)

        avg_macro_f1 = float(np.mean([m["macro_f1"] for m in fold_metrics]))
        std_macro_f1 = float(np.std([m["macro_f1"] for m in fold_metrics]))
        avg_balanced_acc = float(np.mean([m["balanced_accuracy"] for m in fold_metrics]))
        total_time = float(np.sum(train_times))

        return {
            "modelo": model_name,
            "tipo": model_type,
            "balanceado": use_balancing,
            "total_amostras": n_samples,
            "tempo_total_segundos": round(total_time, 2),
            "tempo_medio_por_dobra": round(float(np.mean(train_times)), 2),
            "macro_f1_medio": round(avg_macro_f1, 4),
            "macro_f1_desvio": round(std_macro_f1, 4),
            "balanced_accuracy_media": round(avg_balanced_acc, 4),
            "oof_metricas": oof_eval,
            "dobras": fold_metrics,
        }
