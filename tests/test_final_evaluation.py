"""Testes de integridade e auditoria de nao-vazamento para a avaliacao no teste retido."""
from pathlib import Path
import numpy as np
import pytest

from src.modeling.loader import (
    DEV_DATASET_DEFAULT,
    TEST_DATASET_DEFAULT,
    extract_tabular_features,
    load_dataset,
    prepare_dataset_matrices,
)


def test_test_dataset_cardinality_and_classes():
    """Valida que o dataset de teste retido contem exatamente 3.632 obras e distribuicao natural."""
    assert TEST_DATASET_DEFAULT.exists(), f"Arquivo nao encontrado: {TEST_DATASET_DEFAULT}"
    df_test = load_dataset(TEST_DATASET_DEFAULT)

    assert len(df_test) == 3632
    assert df_test["id_tcu"].nunique() == 3632

    class_counts = df_test["label_risco"].value_counts().to_dict()
    assert class_counts[0] == 3330
    assert class_counts[1] == 196
    assert class_counts[2] == 21
    assert class_counts[3] == 85


def test_strict_zero_leakage_between_dev_and_test():
    """Valida que a intersecao de obras entre treino/desenvolvimento e teste e rigorosamente zero."""
    df_dev = load_dataset(DEV_DATASET_DEFAULT)
    df_test = load_dataset(TEST_DATASET_DEFAULT)

    dev_ids = set(df_dev["id_tcu"])
    test_ids = set(df_test["id_tcu"])

    overlap = dev_ids.intersection(test_ids)
    assert len(overlap) == 0, f"Vazamento detectado: {len(overlap)} obras compartilhadas!"


def test_feature_alignment_between_dev_and_test():
    """Valida que o pre-processamento de atributos reaplica os mapeamentos do treino sem contaminacao."""
    df_dev = load_dataset(DEV_DATASET_DEFAULT)
    df_test = load_dataset(TEST_DATASET_DEFAULT)

    dev_data = prepare_dataset_matrices(df_dev, include_embeddings=True)
    maps_dev = dev_data["categorical_mappings"]

    test_data = prepare_dataset_matrices(
        df_test,
        categorical_mappings=maps_dev,
        include_embeddings=True
    )

    assert dev_data["X_comb"].shape[1] == test_data["X_comb"].shape[1]
    assert dev_data["feature_names"] == test_data["feature_names"]
    assert test_data["X_comb"].shape[0] == 3632
    assert len(test_data["y"]) == 3632
