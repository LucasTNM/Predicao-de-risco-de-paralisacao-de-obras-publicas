# -*- coding: utf-8 -*-
"""
src/dataset/leakage_audit.py
============================
Funções analíticas reutilizáveis para verificação de vazamento do alvo (Target Leakage)
em bases relacionais e documentais do projeto TCC.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from psycopg.rows import dict_row


def get_leakage_distribution(conn) -> List[Dict[str, Any]]:
    """Calcula a distribuicao de composicao documental por classe de risco."""
    q = """
    WITH docs AS (
        SELECT
            f.id_fato,
            f.label_risco,
            bool_or(d.origem_documento = 'ficha_sintetica') AS tem_ficha,
            bool_or(d.origem_documento <> 'ficha_sintetica') AS tem_outro
        FROM tcc.fato_risco f
        LEFT JOIN tcc.ponte_documento_embedding p ON p.id_fato = f.id_fato
        LEFT JOIN tcc.dim_documento d ON d.id_documento = p.id_documento
        WHERE f.ano_base = 2025 AND f.label_risco IS NOT NULL
        GROUP BY f.id_fato, f.label_risco
    )
    SELECT
        label_risco,
        count(*)::int AS total,
        count(*) FILTER (WHERE tem_ficha IS NULL)::int AS sem_docs,
        count(*) FILTER (WHERE tem_ficha AND NOT coalesce(tem_outro, false))::int AS so_ficha,
        count(*) FILTER (WHERE tem_ficha AND tem_outro)::int AS ficha_e_outro,
        count(*) FILTER (WHERE NOT tem_ficha)::int AS so_outros
    FROM docs
    GROUP BY label_risco
    ORDER BY label_risco;
    """
    rows = conn.execute(q).fetchall()
    return [
        {
            "label_risco": r[0],
            "total": r[1],
            "sem_docs": r[2],
            "so_ficha": r[3],
            "ficha_e_outro": r[4],
            "so_outros": r[5],
        }
        for r in rows
    ]


def get_leakage_terms(conn) -> List[Dict[str, Any]]:
    """Calcula a presenca de termos reveladores de situacao nas fichas sinteticas."""
    q = """
    WITH f AS (
        SELECT
            fr.id_fato,
            fr.label_risco,
            bool_or(e.conteudo_chunk ILIKE '%%paralisad%%') AS paralisad,
            bool_or(e.conteudo_chunk ILIKE '%%em execu%%') AS em_exec,
            bool_or(e.conteudo_chunk ILIKE '%%conclu%%') AS conclu
        FROM tcc.fato_risco fr
        JOIN tcc.ponte_documento_embedding p ON p.id_fato = fr.id_fato
        JOIN tcc.dim_documento d ON d.id_documento = p.id_documento
        JOIN tcc.dim_embedding e ON e.id_embedding = p.id_embedding
        WHERE fr.ano_base = 2025 AND fr.label_risco IS NOT NULL
          AND d.origem_documento = 'ficha_sintetica'
        GROUP BY fr.id_fato, fr.label_risco
    )
    SELECT
        label_risco,
        count(*)::int AS obras_com_ficha,
        count(*) FILTER (WHERE paralisad)::int AS com_paralisad,
        count(*) FILTER (WHERE em_exec)::int AS com_em_exec,
        count(*) FILTER (WHERE conclu)::int AS com_conclu
    FROM f
    GROUP BY label_risco
    ORDER BY label_risco;
    """
    rows = conn.execute(q).fetchall()
    return [
        {
            "label_risco": r[0],
            "obras_com_ficha": r[1],
            "com_paralisad": r[2],
            "com_em_exec": r[3],
            "com_conclu": r[4],
        }
        for r in rows
    ]
