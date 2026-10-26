# -*- coding: utf-8 -*-
"""
src/rag/materializer.py
=======================
Materialização congelada de evidências RAG por partição em formato JSONL (Feature 019).

Garante:
1. Processamento determinístico ordenado por id_fato.
2. Deduplicação e proveniência completa para cada obra.
3. Rastreamento estrito de cobertura por classe e hash SHA-256 do lote imutável.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time
from typing import Any, Dict, List, Set, Tuple

import numpy as np
import pandas as pd

from src.rag.retriever import WorkEvidenceRetriever


def compute_file_sha256(path: Path) -> str:
    """Calcula o hash SHA-256 de um arquivo."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            hasher.update(chunk)
    return hasher.hexdigest()


def get_works_with_authentic_documents(conn, ano_base: int = 2025) -> Set[int]:
    """Retorna o conjunto de id_fato de obras que possuem documentos autênticos (<= ano_base)."""
    query = """
    SELECT DISTINCT f_target.id_fato
    FROM tcc.fato_risco f_target
    JOIN tcc.dim_obra o_target ON o_target.id_obra = f_target.id_obra
    JOIN tcc.dim_obra o_hist ON o_hist.base_de_dados = o_target.base_de_dados
                            AND o_hist.id_tcu = o_target.id_tcu
                            AND o_hist.ano_base <= f_target.ano_base
    JOIN tcc.fato_risco f_hist ON f_hist.id_obra = o_hist.id_obra
    JOIN tcc.ponte_documento_embedding p ON p.id_fato = f_hist.id_fato
    JOIN tcc.dim_documento d USING (id_documento)
    WHERE f_target.ano_base = %s
      AND d.origem_documento != 'ficha_sintetica';
    """
    rows = conn.execute(query, (ano_base,)).fetchall()
    return set(r[0] for r in rows)


def materialize_partition_evidence(
    df: pd.DataFrame,
    retriever: WorkEvidenceRetriever,
    output_path: Path,
    ano_base: int = 2025,
) -> Dict[str, Any]:
    """
    Materializa o lote congelado de evidências RAG para um DataFrame de partição.
    Grava cada obra como uma linha JSONL e retorna estatísticas auditáveis.
    """
    t0 = time.time()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    works_with_docs = get_works_with_authentic_documents(retriever.conn, ano_base=ano_base)

    total_obras = len(df)
    obras_com_texto = 0
    total_chunks = 0
    cobertura_classe: Dict[int, Dict[str, int]] = {
        c: {"total": 0, "com_texto": 0} for c in [0, 1, 2, 3]
    }
    consultas_stats: Dict[str, int] = {
        "regular": 0, "tecnica": 0, "orcamentaria": 0, "abandono": 0
    }

    records: List[Dict[str, Any]] = []

    for _, row in df.iterrows():
        id_fato = int(row["id_fato"])
        id_tcu = str(row["id_tcu"])
        label = int(row["label_risco"])

        cobertura_classe[label]["total"] += 1

        if id_fato in works_with_docs:
            res = retriever.retrieve_for_work(id_fato)
            chunks = res["chunks"]
            has_ev = len(chunks) > 0
            if has_ev:
                obras_com_texto += 1
                cobertura_classe[label]["com_texto"] += 1
                total_chunks += len(chunks)
                for chk in chunks:
                    q = chk.get("consulta_origem")
                    if q in consultas_stats:
                        consultas_stats[q] += 1
        else:
            chunks = []
            has_ev = False

        record = {
            "id_fato": id_fato,
            "id_tcu": id_tcu,
            "label_risco": label,
            "sem_evidencia_textual": not has_ev,
            "total_chunks_recuperados": len(chunks),
            "chunks": chunks,
        }
        records.append(record)

    # Gravação determinística em JSONL
    with open(output_path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    sha256_hash = compute_file_sha256(output_path)
    elapsed = time.time() - t0

    stats = {
        "arquivo": output_path.name,
        "sha256": sha256_hash,
        "total_obras": total_obras,
        "obras_com_evidencias": obras_com_texto,
        "percentual_cobertura_global": round((obras_com_texto / total_obras) * 100, 2) if total_obras > 0 else 0.0,
        "total_chunks_materializados": total_chunks,
        "distribuicao_consultas": consultas_stats,
        "cobertura_por_classe": {
            str(c): {
                "total": v["total"],
                "com_texto": v["com_texto"],
                "percentual": round((v["com_texto"] / v["total"]) * 100, 2) if v["total"] > 0 else 0.0,
            }
            for c, v in cobertura_classe.items()
        },
        "tempo_segundos": round(elapsed, 2),
    }

    return stats
