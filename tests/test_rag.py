# -*- coding: utf-8 -*-
"""
tests/test_rag.py
=================
Testes unitários para o motor RAG por obra (Feature 019):
- Auditoria de consultas causais (sem termos de vazamento).
- Recusa estrita de termos proibidos pelo validador.
- Integridade do hash das consultas versionadas.
"""

from pathlib import Path
import pytest

from src.rag.queries import (
    PROHIBITED_TERMS,
    audit_query_text,
    get_causal_queries,
    compute_queries_hash,
    save_queries_catalog,
)


def test_causal_queries_audit_clean():
    """Garante que 100% das consultas oficiais passam na auditoria sem termos proibidos."""
    queries = get_causal_queries()
    assert len(queries) == 4
    assert set(queries.keys()) == {"regular", "tecnica", "orcamentaria", "abandono"}
    for name, text in queries.items():
        assert audit_query_text(text) is True


def test_audit_query_text_rejects_leakage_terms():
    """Verifica que qualquer termo de situação dispara ValueError imediatamente."""
    bad_texts = [
        "obra paralisada por falta de verba",
        "serviços em execução regular",
        "situação da obra cadastrada no sistema",
        "notificação de obra reiniciada",
        "obra concluída em 2024",
    ]
    for bad in bad_texts:
        with pytest.raises(ValueError, match="Violação do Artigo I"):
            audit_query_text(bad)


def test_queries_catalog_hash_reproducibility(tmp_path: Path):
    """Garante determinismo do hash SHA-256 das consultas."""
    catalog_path = tmp_path / "consultas.json"
    save_queries_catalog(catalog_path)
    assert catalog_path.exists()

    queries = get_causal_queries()
    h1 = compute_queries_hash(queries)
    h2 = compute_queries_hash(queries)
    assert h1 == h2
    assert len(h1) == 64


def test_work_evidence_retriever_empty_for_work_without_docs():
    """Garante retorno limpo para obra sem documentos autênticos."""
    from unittest.mock import MagicMock
    from src.rag.retriever import WorkEvidenceRetriever
    import numpy as np

    fake_conn = MagicMock()
    fake_cursor = MagicMock()
    fake_conn.cursor.return_value.__enter__.return_value = fake_cursor
    fake_cursor.execute.return_value.fetchall.return_value = []

    dummy_vectors = {q: np.zeros(768, dtype=np.float32) for q in ["regular", "tecnica", "orcamentaria", "abandono"]}
    retriever = WorkEvidenceRetriever(fake_conn, query_vectors=dummy_vectors, k=4)

    res = retriever.retrieve_for_work(id_fato=99999)
    assert res["id_fato"] == 99999
    assert res["sem_evidencia_textual"] is True
    assert res["total_chunks_recuperados"] == 0
    assert res["chunks"] == []


def test_work_evidence_retriever_ranking_and_deduplication():
    """Garante ordenação determinística por menor distância e deduplicação de chunks."""
    from unittest.mock import MagicMock
    from src.rag.retriever import WorkEvidenceRetriever
    import numpy as np

    fake_conn = MagicMock()
    fake_cursor = MagicMock()
    fake_conn.cursor.return_value.__enter__.return_value = fake_cursor

    # 3 chunks mockados, sendo dois com mesmo id_embedding (duplicata de documento)
    fake_rows = [
        {
            "id_embedding": 101,
            "conteudo_chunk": "Texto sobre solo e fundacao",
            "id_documento": 50,
            "caminho_pdf_relativo": "doc1.pdf",
            "origem_documento": "original",
            "base_origem": "dnit",
            "posicao_chunk": 1,
            "char_inicio": 0,
            "char_fim": 100,
            "dist_reg": 0.50,
            "dist_tec": 0.15,  # menor distancia
            "dist_orc": 0.60,
            "dist_aba": 0.70,
        },
        {
            "id_embedding": 102,
            "conteudo_chunk": "Texto sobre orcamento e repasse",
            "id_documento": 50,
            "caminho_pdf_relativo": "doc1.pdf",
            "origem_documento": "original",
            "base_origem": "dnit",
            "posicao_chunk": 2,
            "char_inicio": 100,
            "char_fim": 200,
            "dist_reg": 0.40,
            "dist_tec": 0.45,
            "dist_orc": 0.10,  # menor distancia
            "dist_aba": 0.65,
        },
        {
            "id_embedding": 101,  # duplicata do chunk 101 em outro documento
            "conteudo_chunk": "Texto sobre solo e fundacao",
            "id_documento": 51,
            "caminho_pdf_relativo": "doc2.pdf",
            "origem_documento": "original",
            "base_origem": "dnit",
            "posicao_chunk": 1,
            "char_inicio": 0,
            "char_fim": 100,
            "dist_reg": 0.50,
            "dist_tec": 0.15,
            "dist_orc": 0.60,
            "dist_aba": 0.70,
        },
    ]
    fake_cursor.execute.return_value.fetchall.return_value = fake_rows

    dummy_vectors = {q: np.zeros(768, dtype=np.float32) for q in ["regular", "tecnica", "orcamentaria", "abandono"]}
    retriever = WorkEvidenceRetriever(fake_conn, query_vectors=dummy_vectors, k=4)

    res = retriever.retrieve_for_work(id_fato=123)
    assert res["id_fato"] == 123
    assert res["sem_evidencia_textual"] is False
    assert res["total_chunks_recuperados"] == 2  # Deduplicou o chunk 101!

    # Chunk 102 teve menor dist (0.10) que chunk 101 (0.15), deve vir em primeiro
    assert res["chunks"][0]["id_embedding"] == 102
    assert res["chunks"][0]["consulta_origem"] == "orcamentaria"
    assert res["chunks"][0]["similaridade"] == round(1.0 - 0.10, 6)

    assert res["chunks"][1]["id_embedding"] == 101
    assert res["chunks"][1]["consulta_origem"] == "tecnica"

