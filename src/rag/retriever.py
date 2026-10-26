# -*- coding: utf-8 -*-
"""
src/rag/retriever.py
====================
Motor de busca RAG restrito por obra no PostgreSQL/pgvector (Feature 019).

Garante:
1. Distância cosseno exata (<=>) sobre os vetores GTE existentes.
2. Restrição estrita aos fragmentos vinculados à obra consultada.
3. Expurgo absoluto de fichas sintéticas (apenas documentos autênticos).
4. Deduplicação determinística dos top-k fragmentos mais relevantes.
5. Retorno com proveniência completa (documento, offsets, distância, consulta).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import numpy as np
import psycopg.rows

DEFAULT_VECTORS_PATH = Path(__file__).resolve().parent / "consultas_causais_vetores.npz"


class WorkEvidenceRetriever:
    """Recuperador de evidências textuais restrito por obra no PostgreSQL."""

    def __init__(
        self,
        conn,
        query_vectors: Optional[Dict[str, np.ndarray]] = None,
        k: int = 4,
        vectors_path: Optional[Path] = None,
    ):
        self.conn = conn
        self.k = k

        if query_vectors is not None:
            self.query_vectors = query_vectors
        else:
            p = vectors_path or DEFAULT_VECTORS_PATH
            if not p.exists():
                raise FileNotFoundError(f"Arquivo de vetores de consulta não encontrado: {p}")
            data = np.load(p)
            self.query_vectors = {name: data[name] for name in data.files}

        # Formata literais para o operador <=> do pgvector
        self.vector_literals = {
            q_name: "[" + ",".join(map(str, vec.tolist())) + "]"
            for q_name, vec in self.query_vectors.items()
        }

    def retrieve_for_work(self, id_fato: int) -> Dict[str, Any]:
        """
        Recupera os top-k fragmentos mais relevantes para a obra id_fato
        através das consultas causais, garantindo zero contaminação e proveniência.
        """
        query = """
        SELECT
            e.id_embedding,
            e.conteudo_chunk,
            d.id_documento,
            d.caminho_pdf_relativo,
            d.origem_documento,
            d.base_origem,
            p.posicao_chunk,
            p.char_inicio,
            p.char_fim,
            e.embedding <=> %(vec_reg)s::vector AS dist_reg,
            e.embedding <=> %(vec_tec)s::vector AS dist_tec,
            e.embedding <=> %(vec_orc)s::vector AS dist_orc,
            e.embedding <=> %(vec_aba)s::vector AS dist_aba
        FROM tcc.fato_risco f_target
        JOIN tcc.dim_obra o_target ON o_target.id_obra = f_target.id_obra
        JOIN tcc.dim_obra o_hist ON o_hist.base_de_dados = o_target.base_de_dados
                                AND o_hist.id_tcu = o_target.id_tcu
                                AND o_hist.ano_base <= f_target.ano_base
        JOIN tcc.fato_risco f_hist ON f_hist.id_obra = o_hist.id_obra
        JOIN tcc.ponte_documento_embedding p ON p.id_fato = f_hist.id_fato
        JOIN tcc.dim_documento d ON d.id_documento = p.id_documento
        JOIN tcc.dim_embedding e ON e.id_embedding = p.id_embedding
        WHERE f_target.id_fato = %(id_fato)s
          AND d.origem_documento != 'ficha_sintetica'
          AND e.embedding IS NOT NULL;
        """

        params = {
            "id_fato": id_fato,
            "vec_reg": self.vector_literals["regular"],
            "vec_tec": self.vector_literals["tecnica"],
            "vec_orc": self.vector_literals["orcamentaria"],
            "vec_aba": self.vector_literals["abandono"],
        }

        with self.conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            rows = cur.execute(query, params).fetchall()

        if not rows:
            return {
                "id_fato": id_fato,
                "sem_evidencia_textual": True,
                "total_chunks_recuperados": 0,
                "chunks": [],
            }

        # Para cada chunk, seleciona a consulta de menor distância cosseno
        chunk_candidates = []
        for r in rows:
            dists = {
                "regular": float(r["dist_reg"]),
                "tecnica": float(r["dist_tec"]),
                "orcamentaria": float(r["dist_orc"]),
                "abandono": float(r["dist_aba"]),
            }
            best_query, best_dist = min(dists.items(), key=lambda item: item[1])

            chunk_candidates.append({
                "id_embedding": r["id_embedding"],
                "id_documento": r["id_documento"],
                "caminho_pdf_relativo": r["caminho_pdf_relativo"],
                "origem_documento": r["origem_documento"],
                "base_origem": r["base_origem"],
                "posicao_chunk": r["posicao_chunk"],
                "char_inicio": r["char_inicio"],
                "char_fim": r["char_fim"],
                "distancia_cosseno": round(best_dist, 6),
                "similaridade": round(1.0 - best_dist, 6),
                "consulta_origem": best_query,
                "texto": r["conteudo_chunk"],
            })

        # Ordenação determinística: menor distância cosseno, desempate por menor id_embedding
        chunk_candidates.sort(key=lambda x: (x["distancia_cosseno"], x["id_embedding"]))

        # Deduplicação por id_embedding (caso o mesmo chunk pertença a mais de um documento da obra)
        seen_ids: Set[int] = set()
        selected_chunks = []
        for c in chunk_candidates:
            if c["id_embedding"] not in seen_ids:
                seen_ids.add(c["id_embedding"])
                selected_chunks.append(c)
                if len(selected_chunks) >= self.k:
                    break

        return {
            "id_fato": id_fato,
            "sem_evidencia_textual": False,
            "total_chunks_recuperados": len(selected_chunks),
            "chunks": selected_chunks,
        }
