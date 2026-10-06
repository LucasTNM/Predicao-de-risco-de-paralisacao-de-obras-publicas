"""Particionador deterministico de validacao cruzada agrupada e estratificada por obra."""
from collections import defaultdict
from typing import Dict, Iterator, List, Tuple
import numpy as np


class StratifiedGroupSplitter:
    """Divide dataset em K dobras agrupadas por id_tcu com estratificacao das classes."""

    def __init__(self, n_splits: int = 5, seed: int = 42):
        self.n_splits = n_splits
        self.seed = seed

    def split(
        self,
        X: np.ndarray,
        y: np.ndarray,
        groups: np.ndarray,
        num_classes: int = 4
    ) -> Iterator[Tuple[np.ndarray, np.ndarray]]:
        """Gera pares (train_indices, val_indices) para cada dobra sem vazamento de grupos."""
        rng = np.random.RandomState(self.seed)

        # 1. Agrupa indices e contagens de classe por grupo (id_tcu)
        group_indices = defaultdict(list)
        group_class_counts = defaultdict(lambda: np.zeros(num_classes, dtype=np.int32))

        for idx, (grp, label) in enumerate(zip(groups, y)):
            group_indices[grp].append(idx)
            group_class_counts[grp][label] += 1

        # 2. Determina a classe preponderante/mais rara para cada grupo
        def get_primary_class(counts):
            # Prioriza classes raras se presentes no grupo
            if counts[2] > 0:
                return 2
            if counts[3] > 0:
                return 3
            if counts[1] > 0:
                return 1
            return 0

        group_primary = {grp: get_primary_class(counts) for grp, counts in group_class_counts.items()}

        # 3. Distribuicao gulosa balanceada por classe (da mais rara para a mais comum)
        fold_counts = np.zeros((self.n_splits, num_classes), dtype=np.int64)
        fold_groups: List[List[str]] = [[] for _ in range(self.n_splits)]

        # Ordem de alocacao das classes: 2 (orcamentaria), 3 (abandono), 1 (tecnica), 0 (regular)
        class_allocation_order = [2, 3, 1, 0]

        for target_c in class_allocation_order:
            grps_for_c = [g for g, p in group_primary.items() if p == target_c]
            # Embaralha com semente deterministica para desempates estaveis
            rng.shuffle(grps_for_c)
            # Ordena por tamanho do grupo decrescente
            sorted_grps = sorted(grps_for_c, key=lambda g: len(group_indices[g]), reverse=True)

            for grp in sorted_grps:
                # Escolhe o fold com menor contagem acumulada da classe alvo (ou menor total)
                c_counts = fold_counts[:, target_c]
                min_c = np.min(c_counts)
                candidate_folds = np.where(c_counts == min_c)[0]

                if len(candidate_folds) == 1:
                    best_fold = candidate_folds[0]
                else:
                    # Desempata pelo fold com menor numero total de amostras
                    total_counts = np.sum(fold_counts[candidate_folds], axis=1)
                    best_fold = candidate_folds[np.argmin(total_counts)]

                fold_groups[best_fold].append(grp)
                fold_counts[best_fold] += group_class_counts[grp]

        # 4. Gera pares de indices e valida integridade
        for fold_idx in range(self.n_splits):
            val_grps = set(fold_groups[fold_idx])
            val_idx_list = []
            train_idx_list = []

            for grp, idxs in group_indices.items():
                if grp in val_grps:
                    val_idx_list.extend(idxs)
                else:
                    train_idx_list.extend(idxs)

            train_idx = np.array(train_idx_list, dtype=np.int64)
            val_idx = np.array(val_idx_list, dtype=np.int64)

            # Validacao estrita de nao vazamento
            train_grps = set(groups[train_idx])
            overlap = train_grps.intersection(val_grps)
            if overlap:
                raise RuntimeError(f"Vazamento detectado no fold {fold_idx}: {len(overlap)} grupos compartilhados!")

            if len(val_idx) == 0:
                raise RuntimeError(f"Fold {fold_idx} vazio gerado na particao!")

            yield train_idx, val_idx


def audit_splits(
    splits: List[Tuple[np.ndarray, np.ndarray]],
    y: np.ndarray,
    groups: np.ndarray,
    num_classes: int = 4
) -> List[Dict[str, int]]:
    """Audita a distribuicao das classes e verifica vazamento em cada dobra."""
    reports = []
    for f, (train_idx, val_idx) in enumerate(splits):
        train_grps = set(groups[train_idx])
        val_grps = set(groups[val_idx])
        overlap = len(train_grps & val_grps)

        val_classes = np.bincount(y[val_idx], minlength=num_classes)
        reports.append({
            "fold": f + 1,
            "train_size": len(train_idx),
            "val_size": len(val_idx),
            "overlap_groups": overlap,
            "val_class_0": int(val_classes[0]),
            "val_class_1": int(val_classes[1]),
            "val_class_2": int(val_classes[2]),
            "val_class_3": int(val_classes[3]),
        })
    return reports
