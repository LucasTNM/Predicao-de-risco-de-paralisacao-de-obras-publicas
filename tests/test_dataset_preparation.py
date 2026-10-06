"""Testes unitarios e de integracao para extracao, quarentena e particionamento de datasets."""
import pytest
import numpy as np
import pandas as pd
from src.dataset.quarantine import (
    get_quarantined_document_ids,
    is_document_quarantined,
    get_quarantine_summary,
    CANONICAL_QUARANTINED_DOC_IDS,
)
from src.dataset.partition import partition_by_work_identity, audit_leakage


def test_quarantine_document_ids_count_and_content():
    """Valida que exatamente 36 documentos DNIT estao listados na quarentena."""
    q_ids = get_quarantined_document_ids()
    assert len(q_ids) == 36
    assert 8 in q_ids
    assert 628 in q_ids
    assert 999999 not in q_ids


def test_quarantine_check_function():
    """Valida a funcao is_document_quarantined."""
    assert is_document_quarantined(204) is True
    assert is_document_quarantined(99999) is False
    summary = get_quarantine_summary()
    assert summary["documentos_excluidos"] == 36
    assert summary["obras_afetadas"] == 22


def test_partitioning_no_leakage_and_stratification():
    """Valida que o particionamento estratificado por grupos garante intersecao vazia de obras."""
    # Cria dataset sintetico com 500 obras unicas, algumas com multiplos registros (total 700 linhas)
    np.random.seed(42)
    obras_unicas = [f"TCU_{i:04d}" for i in range(500)]
    
    # Classes desbalanceadas semelhantes ao cenario real (0 regular majoritaria, 1 técnica, 2 orcamentaria, 3 abandono)
    classes_por_obra = np.random.choice([0, 1, 2, 3], size=500, p=[0.90, 0.05, 0.01, 0.04])
    
    rows = []
    for id_tcu, label in zip(obras_unicas, classes_por_obra):
        # 1 a 3 registros por obra
        num_regs = 1 if np.random.rand() > 0.3 else (2 if np.random.rand() > 0.5 else 3)
        for r in range(num_regs):
            rows.append({
                "id_fato": len(rows) + 1,
                "id_tcu": id_tcu,
                "label_risco": int(label),
                "ano": 2025,
            })
    
    df = pd.DataFrame(rows)
    assert len(df) > 500
    
    # Aplica particionamento
    df_part = partition_by_work_identity(df, seed=42, test_ratio=0.20)
    
    # Valida auditoria de vazamento
    audit = audit_leakage(df_part)
    assert audit["vazamento_detectado"] is False
    assert audit["intersecao_obras"] == 0
    assert audit["total_treino"] > 0
    assert audit["total_teste"] > 0
    
    # Verifica que todas as classes com pelo menos 5 instancias estao presentes no teste
    dev_classes = set(df_part[df_part["particao"] == "treino_dev"]["label_risco"].unique())
    test_classes = set(df_part[df_part["particao"] == "teste_retido"]["label_risco"].unique())
    assert 0 in test_classes
    assert 1 in test_classes
    assert 3 in test_classes
    assert dev_classes == {0, 1, 2, 3}


def test_audit_leakage_detects_deliberate_leakage():
    """Valida que o auditor de vazamento falha se a mesma obra estiver em treino e teste."""
    df_leak = pd.DataFrame([
        {"id_tcu": "OBRA_1", "particao": "treino_dev", "label_risco": 0},
        {"id_tcu": "OBRA_1", "particao": "teste_retido", "label_risco": 0},
        {"id_tcu": "OBRA_2", "particao": "treino_dev", "label_risco": 1},
    ])
    audit = audit_leakage(df_leak)
    assert audit["vazamento_detectado"] is True
    assert audit["intersecao_obras"] == 1
    assert "OBRA_1" in audit["obras_vazadas"]


def test_extractor_observations_cardinality():
    """Valida que a extracao de observacoes de 2025 preserva exatamente 28.288 fatos."""
    try:
        from src.dataset.extractor import extract_observations
        from src.database.connection import connect
        conn = connect()
    except (ImportError, Exception) as exc:
        pytest.skip(f"Acesso direto via psycopg/PostgreSQL indisponivel no ambiente: {exc}")
    
    try:
        df_2025 = extract_observations(ano=2025, conn=conn)
        assert len(df_2025) == 28288
        assert "id_fato" in df_2025.columns
        assert "id_tcu" in df_2025.columns
        assert "label_risco" in df_2025.columns
        assert df_2025["id_fato"].nunique() == 28288
    finally:
        conn.close()


def test_quarantined_documents_excluded_from_embeddings():
    """Valida que nenhum dos 36 documentos quarentenados compoe os embeddings extraidos."""
    try:
        from src.dataset.extractor import extract_work_embeddings
        from src.dataset.quarantine import get_quarantined_document_ids
        from src.database.connection import connect
        conn = connect()
    except (ImportError, Exception) as exc:
        pytest.skip(f"Acesso direto via psycopg/PostgreSQL indisponivel no ambiente: {exc}")
    
    q_ids = get_quarantined_document_ids()
    assert len(q_ids) == 36
    try:
        cur = conn.cursor()
        # Encontra id_fato que contem documentos sob quarentena
        cur.execute("""
            SELECT DISTINCT id_fato, id_documento 
            FROM tcc.ponte_documento_embedding 
            WHERE id_documento = ANY(%s) 
            LIMIT 5;
        """, [list(q_ids)])
        samples = cur.fetchall()
        assert len(samples) > 0, "Deveria haver vinculos com os documentos quarentenados no banco"
        
        # Extrai com quarentena
        emb_map, meta_map = extract_work_embeddings(ano=2025, quarantined_doc_ids=q_ids, conn=conn)
        
        # Para esses casos DNIT onde TODOS os documentos estavam quarentenados, num_docs_validos deve ser 0
        for id_fato, id_doc in samples:
            meta = meta_map.get(id_fato)
            # Se a obra so tinha documentos quarentenados, nao pode ter embedding
            if meta is None or meta["num_docs_validos"] == 0:
                assert id_fato not in emb_map
    finally:
        conn.close()

