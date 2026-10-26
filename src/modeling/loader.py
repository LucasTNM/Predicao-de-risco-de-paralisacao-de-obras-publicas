"""Carregamento seguro de dados Parquet e preparacao de matrizes tabulares e vetoriais."""
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import duckdb
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DEV_DATASET_DEFAULT = ROOT / "dados_processados" / "sprint6" / "dataset_treino_dev_2025.parquet"
TEST_DATASET_DEFAULT = ROOT / "dados_processados" / "sprint6" / "dataset_teste_retido_2025.parquet"

# Perfis de colunas por cenário
NUMERIC_COLUMNS_C0 = [
    "valor_investimento",
    "valor_desbloqueado",
    "exec_fisica",
    "exec_financeira",
    "num_docs_validos",
    "num_chunks_validos",
    "has_embedding",
]

NUMERIC_COLUMNS_LIMPO = [
    "valor_investimento",
    "valor_desbloqueado",
    "exec_fisica",
    "exec_financeira",
]

NUMERIC_COLUMNS = NUMERIC_COLUMNS_C0

CATEGORICAL_COLUMNS = [
    "base",
    "uf",
]


def load_dataset(parquet_path: Union[Path, str] = DEV_DATASET_DEFAULT) -> pd.DataFrame:
    """Carrega dataset Parquet utilizando DuckDB para garantir compatibilidade nativa."""
    path = Path(parquet_path)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        raise FileNotFoundError(f"Arquivo de dataset nao encontrado: {path}")

    # Leitura direta via engine C++ do DuckDB
    query = f"SELECT * FROM read_parquet('{path.as_posix()}')"
    return duckdb.query(query).df()


def extract_tabular_features(
    df: pd.DataFrame,
    categorical_mappings: Optional[Dict[str, Dict[str, int]]] = None,
    numeric_imputations: Optional[Dict[str, float]] = None,
    feature_profile: str = "c0_original",
    return_imputations: bool = False
) -> Union[Tuple[np.ndarray, List[str], Dict[str, Dict[str, int]]], Tuple[np.ndarray, List[str], Dict[str, Dict[str, int]], Dict[str, float]]]:
    """Extrai atributos numericos e categoricos com controle estrito de vazamento de treino."""
    df_feat = pd.DataFrame(index=df.index)

    num_cols = NUMERIC_COLUMNS_C0 if feature_profile == "c0_original" else NUMERIC_COLUMNS_LIMPO
    new_imputations: Dict[str, float] = {}

    # 1. Atributos numericos
    for col in num_cols:
        if col in df.columns:
            s = pd.to_numeric(df[col], errors="coerce")
            if col == "has_embedding":
                df_feat[col] = s.fillna(0).astype(np.float32)
            elif col in ("exec_fisica", "exec_financeira"):
                df_feat[col] = s.fillna(0.0).astype(np.float32)
            else:
                if numeric_imputations and col in numeric_imputations:
                    med = numeric_imputations[col]
                else:
                    med = float(s.dropna().median()) if s.dropna().size > 0 else 0.0
                    new_imputations[col] = med
                df_feat[col] = s.fillna(med).astype(np.float32)
        else:
            df_feat[col] = np.zeros(len(df), dtype=np.float32)

    # 2. Atributos categoricos (codificacao inteira deterministica)
    new_mappings: Dict[str, Dict[str, int]] = {}
    for col in CATEGORICAL_COLUMNS:
        if col in df.columns:
            s_cat = df[col].astype(str).fillna("DESCONHECIDO")
            if categorical_mappings and col in categorical_mappings:
                cat_map = categorical_mappings[col]
            else:
                uniques = sorted(s_cat.unique().tolist())
                cat_map = {val: idx for idx, val in enumerate(uniques)}
                new_mappings[col] = cat_map
            df_feat[f"{col}_cat"] = s_cat.map(cat_map).fillna(-1).astype(np.float32)
        else:
            df_feat[f"{col}_cat"] = np.zeros(len(df), dtype=np.float32)

    feature_names = df_feat.columns.tolist()
    X_tab = df_feat.to_numpy(dtype=np.float32)
    maps = new_mappings or (categorical_mappings or {})
    imps = new_imputations or (numeric_imputations or {})
    if return_imputations:
        return X_tab, feature_names, maps, imps
    return X_tab, feature_names, maps


def extract_embedding_matrix(df: pd.DataFrame, embedding_dim: int = 768) -> Tuple[np.ndarray, List[str]]:
    """Extrai ou preenche com zeros os embeddings de 768 dimensoes por obra."""
    n_samples = len(df)
    X_emb = np.zeros((n_samples, embedding_dim), dtype=np.float32)

    if "embedding" in df.columns:
        for idx, val in enumerate(df["embedding"]):
            if val is not None and isinstance(val, (np.ndarray, list)):
                arr = np.asarray(val, dtype=np.float32)
                if len(arr) == embedding_dim:
                    X_emb[idx] = arr

    feature_names = [f"emb_{i:03d}" for i in range(embedding_dim)]
    return X_emb, feature_names


def prepare_dataset_matrices(
    df: pd.DataFrame,
    categorical_mappings: Optional[Dict[str, Dict[str, int]]] = None,
    numeric_imputations: Optional[Dict[str, float]] = None,
    include_embeddings: bool = True,
    feature_profile: str = "c0_original",
    override_embeddings: Optional[np.ndarray] = None
) -> Dict[str, Any]:
    """Prepara matrizes consolidadas X_tab, X_emb, X_comb, y, groups e pesos."""
    X_tab, tab_names, mappings, imputations = extract_tabular_features(
        df,
        categorical_mappings=categorical_mappings,
        numeric_imputations=numeric_imputations,
        feature_profile=feature_profile,
        return_imputations=True
    )

    if include_embeddings:
        if override_embeddings is not None:
            X_emb = override_embeddings
            emb_names = [f"emb_{i:03d}" for i in range(override_embeddings.shape[1])]
        else:
            X_emb, emb_names = extract_embedding_matrix(df, embedding_dim=768)
        X_comb = np.hstack([X_tab, X_emb])
        all_feature_names = tab_names + emb_names
    else:
        X_emb = None
        X_comb = X_tab
        all_feature_names = tab_names

    y = df["label_risco"].to_numpy(dtype=np.int32)
    groups = df["id_tcu"].astype(str).to_numpy()

    class_weights = compute_class_weights(y)
    sample_weights = compute_sample_weights(y, class_weights)

    return {
        "X_tab": X_tab,
        "X_emb": X_emb,
        "X_comb": X_comb,
        "y": y,
        "groups": groups,
        "feature_names": all_feature_names,
        "tab_feature_names": tab_names,
        "class_weights": class_weights,
        "sample_weights": sample_weights,
        "categorical_mappings": mappings,
        "numeric_imputations": imputations,
    }


def compute_class_weights(y: np.ndarray, num_classes: int = 4) -> Dict[int, float]:
    """Calcula pesos de classes inversamente proporcionais: N / (num_classes * N_c)."""
    n_samples = len(y)
    weights: Dict[int, float] = {}
    for c in range(num_classes):
        n_c = int(np.sum(y == c))
        if n_c > 0:
            weights[c] = float(n_samples / (num_classes * n_c))
        else:
            weights[c] = 1.0
    return weights


def compute_sample_weights(y: np.ndarray, class_weights: Dict[int, float]) -> np.ndarray:
    """Atribui o peso balanceado a cada observacao com base na sua classe real."""
    weights = np.empty(len(y), dtype=np.float32)
    for c, w in class_weights.items():
        weights[y == c] = w
    return weights
