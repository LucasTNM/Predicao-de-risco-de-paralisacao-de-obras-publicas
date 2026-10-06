"""Motor de metricas de avaliacao multiclasse implementado puramente em NumPy."""
from typing import Any, Dict, List, Optional
import numpy as np


def compute_confusion_matrix(y_true: np.ndarray, y_pred: np.ndarray, num_classes: int = 4) -> np.ndarray:
    """Calcula a matriz de confusao quadrada (num_classes x num_classes).
    
    Linhas correspondem a classe real, colunas a classe predita.
    """
    cm = np.zeros((num_classes, num_classes), dtype=np.int64)
    for t, p in zip(y_true, y_pred):
        if 0 <= t < num_classes and 0 <= p < num_classes:
            cm[t, p] += 1
    return cm


def evaluate_multiclass(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    num_classes: int = 4,
    class_names: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Calcula metricas completas: Macro-F1, Balanced Accuracy, Precision/Recall por classe."""
    if class_names is None:
        class_names = [f"Classe_{c}" for c in range(num_classes)]

    cm = compute_confusion_matrix(y_true, y_pred, num_classes=num_classes)
    total_samples = len(y_true)

    # Acuracia geral (apenas referencia)
    accuracy = float(np.trace(cm) / total_samples) if total_samples > 0 else 0.0

    per_class: Dict[str, Dict[str, float]] = {}
    precisions: List[float] = []
    recalls: List[float] = []
    f1s: List[float] = []
    supports: List[int] = []

    for c in range(num_classes):
        tp = float(cm[c, c])
        fn = float(np.sum(cm[c, :]) - tp)
        fp = float(np.sum(cm[:, c]) - tp)
        tn = float(total_samples - tp - fn - fp)
        support = int(np.sum(cm[c, :]))

        p = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
        r = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
        f1 = float(2 * p * r / (p + r)) if (p + r) > 0 else 0.0

        precisions.append(p)
        recalls.append(r)
        f1s.append(f1)
        supports.append(support)

        name = class_names[c] if c < len(class_names) else f"Classe_{c}"
        per_class[name] = {
            "classe": c,
            "support": support,
            "precision": round(p, 4),
            "recall": round(r, 4),
            "f1_score": round(f1, 4),
            "tp": int(tp),
            "fp": int(fp),
            "fn": int(fn),
            "tn": int(tn),
        }

    macro_precision = float(np.mean(precisions))
    macro_recall = float(np.mean(recalls))
    macro_f1 = float(np.mean(f1s))
    balanced_accuracy = macro_recall  # Equivalente a media aritmetica dos recalls

    weighted_f1 = float(np.sum(np.array(f1s) * np.array(supports)) / total_samples) if total_samples > 0 else 0.0

    return {
        "total_amostras": total_samples,
        "acuracia_geral": round(accuracy, 4),
        "macro_f1": round(macro_f1, 4),
        "balanced_accuracy": round(balanced_accuracy, 4),
        "macro_precision": round(macro_precision, 4),
        "macro_recall": round(macro_recall, 4),
        "weighted_f1": round(weighted_f1, 4),
        "por_classe": per_class,
        "matriz_confusao": cm.tolist(),
    }
