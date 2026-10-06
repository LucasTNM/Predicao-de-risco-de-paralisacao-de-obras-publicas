"""Modulo de extracao de dados e agregacao de embeddings a partir do PostgreSQL."""
import logging
from typing import Dict, Any, Set, Tuple, Optional
import numpy as np
import pandas as pd
from psycopg.rows import dict_row

from src.database.connection import connect
from src.dataset.quarantine import get_quarantined_document_ids

logger = logging.getLogger("dataset.extractor")


def extract_observations(
    ano: Optional[int] = 2025,
    conn = None
) -> pd.DataFrame:
    """Extrai observacoes de fato_risco e dim_obra preservando cardinalidade 1:1."""
    should_close = False
    if conn is None:
        conn = connect()
        should_close = True

    try:
        cur = conn.cursor(row_factory=dict_row)
        where_clause = ""
        params = []
        if ano is not None:
            where_clause = "WHERE f.ano_base = %s"
            params.append(ano)

        query = f"""
        SELECT
            f.id_fato,
            f.id_obra,
            f.ano_base AS ano,
            o.id_tcu,
            o.base_de_dados AS base,
            COALESCE(o.uf, 'BR') AS uf,
            COALESCE(o.municipio, '') AS municipio,
            COALESCE(o.situacao, '') AS situacao_cadastral,
            COALESCE(o.situacao_origem, '') AS situacao_origem,
            f.causa_paralisacao AS causa_cadastral,
            f.label_risco,
            f.origem_rotulo,
            f.status_rotulagem,
            COALESCE(f.valor_investimento, 0.0)::float AS valor_investimento,
            COALESCE(f.valor_desbloqueado, 0.0)::float AS valor_desbloqueado,
            COALESCE(f.exec_fisica, 0.0)::float AS exec_fisica,
            COALESCE(f.exec_financeira, 0.0)::float AS exec_financeira
        FROM tcc.fato_risco f
        JOIN tcc.dim_obra o ON f.id_obra = o.id_obra
        {where_clause}
        ORDER BY f.id_fato;
        """
        cur.execute(query, params)
        rows = cur.fetchall()
        return pd.DataFrame(rows)
    finally:
        if should_close:
            conn.close()


def extract_work_embeddings(
    ano: Optional[int] = 2025,
    quarantined_doc_ids: Optional[Set[int]] = None,
    conn = None
) -> Tuple[Dict[int, np.ndarray], Dict[int, Dict[str, int]]]:
    """Calcula mean pooling normalizado dos embeddings por fato aplicando quarentena."""
    should_close = False
    if conn is None:
        conn = connect()
        should_close = True

    if quarantined_doc_ids is None:
        quarantined_doc_ids = get_quarantined_document_ids()

    q_list = list(quarantined_doc_ids)

    try:
        cur = conn.cursor(row_factory=dict_row)
        conditions = ["e.embedding IS NOT NULL"]
        params = []

        if ano is not None:
            conditions.append("p.ano_base = %s")
            params.append(ano)

        if q_list:
            conditions.append("NOT (p.id_documento = ANY(%s))")
            params.append(q_list)

        where_clause = "WHERE " + " AND ".join(conditions)

        query = f"""
        SELECT
            p.id_fato,
            COUNT(DISTINCT p.id_documento) AS num_docs_validos,
            COUNT(p.id_embedding) AS num_chunks_validos,
            AVG(e.embedding) AS vetor_medio
        FROM tcc.ponte_documento_embedding p
        JOIN tcc.dim_embedding e ON p.id_embedding = e.id_embedding
        {where_clause}
        GROUP BY p.id_fato;
        """
        cur.execute(query, params)
        rows = cur.fetchall()

        embeddings_map: Dict[int, np.ndarray] = {}
        meta_map: Dict[int, Dict[str, int]] = {}

        for r in rows:
            id_fato = int(r["id_fato"])
            num_docs = int(r["num_docs_validos"])
            num_chunks = int(r["num_chunks_validos"])
            raw_vec = r["vetor_medio"]

            if raw_vec is not None:
                vec = np.fromstring(str(raw_vec).strip("[]"), sep=",", dtype=np.float32)
                norm = np.linalg.norm(vec)
                if norm > 0:
                    vec = vec / norm
                embeddings_map[id_fato] = vec

            meta_map[id_fato] = {
                "num_docs_validos": num_docs,
                "num_chunks_validos": num_chunks,
            }

        return embeddings_map, meta_map
    finally:
        if should_close:
            conn.close()


def build_consolidated_dataset(
    ano: Optional[int] = 2025,
    include_vectors: bool = True,
    conn = None
) -> pd.DataFrame:
    """Extrai e consolida dataset completo por observacao com metadados e vetores."""
    should_close = False
    if conn is None:
        conn = connect()
        should_close = True

    try:
        df_obs = extract_observations(ano=ano, conn=conn)

        if not include_vectors:
            df_obs["has_embedding"] = False
            df_obs["num_docs_validos"] = 0
            df_obs["num_chunks_validos"] = 0
            return df_obs

        embeddings_map, meta_map = extract_work_embeddings(ano=ano, conn=conn)

        has_emb = []
        docs_validos = []
        chunks_validos = []
        vectors = []

        dim = 768
        zero_vec = np.zeros(dim, dtype=np.float32)

        for _, row in df_obs.iterrows():
            id_fato = int(row["id_fato"])
            meta = meta_map.get(id_fato)
            vec = embeddings_map.get(id_fato)

            if vec is not None:
                has_emb.append(True)
                docs_validos.append(meta["num_docs_validos"])
                chunks_validos.append(meta["num_chunks_validos"])
                vectors.append(vec.tolist())
            else:
                has_emb.append(False)
                docs_validos.append(0)
                chunks_validos.append(0)
                vectors.append(zero_vec.tolist())

        df_obs["has_embedding"] = has_emb
        df_obs["num_docs_validos"] = docs_validos
        df_obs["num_chunks_validos"] = chunks_validos
        df_obs["embedding"] = vectors

        return df_obs
    finally:
        if should_close:
            conn.close()
