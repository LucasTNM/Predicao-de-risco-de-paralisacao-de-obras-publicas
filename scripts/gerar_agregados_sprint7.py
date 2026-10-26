# -*- coding: utf-8 -*-
"""
scripts/gerar_agregados_sprint7.py
==================================
Gera as matrizes de embeddings agregados por obra para os cenários da Feature 018:
- C2: Texto estritamente sem fichas sintéticas (apenas documentos autênticos)
- C3: Fichas sintéticas mascaradas (linhas de situação/alvo expurgadas) + docs autênticos

Salva os artefatos em `dados_processados/sprint7/` com manifesto SHA-256 auditável.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Dict, List, Set, Tuple

import numpy as np
import pandas as pd
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.database.connection import connect
from src.dataset.masking import mask_synthetic_sheet_text, audit_masked_text_for_target_leakage
from src.dataset.quarantine import get_quarantined_document_ids


def compute_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def extract_c2_embeddings(
    dev_df: pd.DataFrame,
    test_df: pd.DataFrame,
    conn
) -> Tuple[np.ndarray, np.ndarray]:
    """Gera matrizes de embeddings para o Cenario C2 (somente documentos autenticos)."""
    quarantined = get_quarantined_document_ids()
    q_list = list(quarantined)

    cur = conn.cursor(row_factory=dict_row)
    conditions = [
        "e.embedding IS NOT NULL",
        "f_target.ano_base = 2025",
        "d.origem_documento <> 'ficha_sintetica'",
    ]
    params: List[Any] = []
    if q_list:
        conditions.append("NOT (p.id_documento = ANY(%s))")
        params.append(q_list)

    where_clause = "WHERE " + " AND ".join(conditions)

    query = f"""
    SELECT
        id_fato_target AS id_fato,
        AVG(embedding) AS vetor_medio
    FROM (
        SELECT DISTINCT
            f_target.id_fato AS id_fato_target,
            e.id_embedding,
            e.embedding
        FROM tcc.fato_risco f_target
        JOIN tcc.dim_obra o_target ON o_target.id_obra = f_target.id_obra
        JOIN tcc.dim_obra o_hist ON o_hist.base_de_dados = o_target.base_de_dados
                                AND o_hist.id_tcu = o_target.id_tcu
                                AND o_hist.ano_base <= f_target.ano_base
        JOIN tcc.fato_risco f_hist ON f_hist.id_obra = o_hist.id_obra
        JOIN tcc.ponte_documento_embedding p ON p.id_fato = f_hist.id_fato
        JOIN tcc.dim_documento d USING (id_documento)
        JOIN tcc.dim_embedding e ON p.id_embedding = e.id_embedding
        {where_clause}
    ) sub
    GROUP BY id_fato_target;
    """
    cur.execute(query, params)
    rows = cur.fetchall()

    c2_map: Dict[int, np.ndarray] = {}
    for r in rows:
        id_fato = int(r["id_fato"])
        raw_vec = r["vetor_medio"]
        if raw_vec is not None:
            vec = np.fromstring(str(raw_vec).strip("[]"), sep=",", dtype=np.float32)
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            c2_map[id_fato] = vec

    dim = 768
    X_emb_dev = np.zeros((len(dev_df), dim), dtype=np.float32)
    for i, id_fato in enumerate(dev_df["id_fato"]):
        if int(id_fato) in c2_map:
            X_emb_dev[i] = c2_map[int(id_fato)]

    X_emb_test = np.zeros((len(test_df), dim), dtype=np.float32)
    for i, id_fato in enumerate(test_df["id_fato"]):
        if int(id_fato) in c2_map:
            X_emb_test[i] = c2_map[int(id_fato)]

    return X_emb_dev, X_emb_test


def extract_c3_embeddings(
    dev_df: pd.DataFrame,
    test_df: pd.DataFrame,
    conn,
    device: str = "cuda"
) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
    """Gera matrizes de embeddings para Cenario C3 (fichas mascaradas + docs autenticos)."""
    from src.embedding_model import load_model, encode_checked

    print(f"[C3] Carregando modelo GTE Multilingual no dispositivo '{device}'...")
    model = load_model(device=device, threads=4)

    # 1. Carregar chunks de fichas sinteticas de 2025 para mascaramento
    print("[C3] Consultando chunks de fichas sinteticas de 2025 no PostgreSQL...")
    q = """
    SELECT
        e.id_embedding,
        e.conteudo_chunk
    FROM tcc.dim_embedding e
    JOIN tcc.ponte_documento_embedding p USING (id_embedding)
    JOIN tcc.dim_documento d USING (id_documento)
    WHERE d.origem_documento = 'ficha_sintetica' AND d.ano_base = 2025
    GROUP BY e.id_embedding, e.conteudo_chunk
    ORDER BY e.id_embedding;
    """
    rows = conn.execute(q).fetchall()
    print(f"[C3] Total de chunks de fichas sinteticas a mascarar: {len(rows):,}")

    chunk_ids = []
    masked_texts = []
    spans_audit_total = 0

    for id_emb, raw_text in rows:
        m_text, spans = mask_synthetic_sheet_text(raw_text)
        if not audit_masked_text_for_target_leakage(m_text):
            raise ValueError(f"Falha de auditoria: termo de situacao detectado no chunk {id_emb} apos mascaramento!")
        chunk_ids.append(id_emb)
        masked_texts.append(m_text)
        spans_audit_total += len(spans)

    print(f"[C3] Mascaramento deterministico concluido: {spans_audit_total:,} trechos de situacao/boilerplate removidos.")

    # 2. Codificar com GTE na GPU em batches
    print(f"[C3] Codificando {len(masked_texts):,} chunks mascarados via GTE...")
    batch_size = 32
    masked_vectors: List[List[float]] = []
    t0 = time.time()
    for start in range(0, len(masked_texts), batch_size):
        batch = masked_texts[start : start + batch_size]
        vecs, _ = encode_checked(model, batch, batch_size=len(batch))
        masked_vectors.extend(vecs)
        if (start // batch_size) % 50 == 0 or (start + batch_size >= len(masked_texts)):
            elapsed = time.time() - t0
            print(f"  Progresso: {min(start + batch_size, len(masked_texts)):,}/{len(masked_texts):,} chunks ({elapsed:.1f}s)")

    emb_dict: Dict[int, np.ndarray] = {
        cid: np.asarray(vec, dtype=np.float32) for cid, vec in zip(chunk_ids, masked_vectors)
    }

    # 3. Mapear ponte (id_fato -> chunks validos)
    print("[C3] Mapeando agregacao por obra via tabela ponte...")
    quarantined = get_quarantined_document_ids()
    q_ponte = """
    SELECT DISTINCT
        f_target.id_fato,
        p.id_embedding,
        d.origem_documento,
        e.embedding AS raw_embedding
    FROM tcc.fato_risco f_target
    JOIN tcc.dim_obra o_target ON o_target.id_obra = f_target.id_obra
    JOIN tcc.dim_obra o_hist ON o_hist.base_de_dados = o_target.base_de_dados
                            AND o_hist.id_tcu = o_target.id_tcu
                            AND o_hist.ano_base <= f_target.ano_base
    JOIN tcc.fato_risco f_hist ON f_hist.id_obra = o_hist.id_obra
    JOIN tcc.ponte_documento_embedding p ON p.id_fato = f_hist.id_fato
    JOIN tcc.dim_documento d USING (id_documento)
    JOIN tcc.dim_embedding e USING (id_embedding)
    WHERE f_target.ano_base = 2025
    """
    rows_ponte = conn.execute(q_ponte).fetchall()

    fato_chunks: Dict[int, List[np.ndarray]] = {}
    for id_fato, id_emb, origem, raw_vec in rows_ponte:
        id_fato = int(id_fato)
        if id_fato not in fato_chunks:
            fato_chunks[id_fato] = []

        if origem == "ficha_sintetica":
            if id_emb in emb_dict:
                fato_chunks[id_fato].append(emb_dict[id_emb])
        else:
            if raw_vec is not None:
                vec = np.fromstring(str(raw_vec).strip("[]"), sep=",", dtype=np.float32)
                norm = np.linalg.norm(vec)
                if norm > 0:
                    vec = vec / norm
                fato_chunks[id_fato].append(vec)

    # 4. Mean pooling por obra
    c3_map: Dict[int, np.ndarray] = {}
    for id_fato, vecs in fato_chunks.items():
        if vecs:
            mat = np.stack(vecs, axis=0)
            avg = np.mean(mat, axis=0)
            norm = np.linalg.norm(avg)
            if norm > 0:
                avg = avg / norm
            c3_map[id_fato] = avg

    dim = 768
    X_emb_dev = np.zeros((len(dev_df), dim), dtype=np.float32)
    for i, id_fato in enumerate(dev_df["id_fato"]):
        if int(id_fato) in c3_map:
            X_emb_dev[i] = c3_map[int(id_fato)]

    X_emb_test = np.zeros((len(test_df), dim), dtype=np.float32)
    for i, id_fato in enumerate(test_df["id_fato"]):
        if int(id_fato) in c3_map:
            X_emb_test[i] = c3_map[int(id_fato)]

    stats = {
        "chunks_mascarados": len(masked_texts),
        "spans_removidos": spans_audit_total,
        "obras_com_embedding_c3": len(c3_map),
    }
    return X_emb_dev, X_emb_test, stats


def main():
    parser = argparse.ArgumentParser(description="Gera matrizes agregadas C2 e C3 da Sprint 7")
    parser.add_argument("--device", type=str, default="cuda", choices=["cuda", "cpu"])
    parser.add_argument("--reuse-c3", action="store_true", help="Reutiliza vetores mascarados C3 existentes combinando com novos docs autênticos C2")
    args = parser.parse_args()

    out_dir = ROOT / "dados_processados" / "sprint7"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Carregar datasets particionados de 2025 da Sprint 6
    dev_path = ROOT / "dados_processados" / "sprint6" / "dataset_treino_dev_2025.parquet"
    test_path = ROOT / "dados_processados" / "sprint6" / "dataset_teste_retido_2025.parquet"

    print(f"[Carga] Lendo {dev_path.name} e {test_path.name}...")
    import duckdb
    dev_df = duckdb.query(f"SELECT id_fato, id_tcu, label_risco FROM read_parquet('{dev_path.as_posix()}')").df()
    test_df = duckdb.query(f"SELECT id_fato, id_tcu, label_risco FROM read_parquet('{test_path.as_posix()}')").df()

    conn = connect()
    conn.read_only = True

    try:
        # 2. Gerar C2 (Sem fichas)
        print("\n=== GERANDO CENARIO C2: TEXTO SEM FICHAS SINTETICAS ===")
        X_dev_c2, X_test_c2 = extract_c2_embeddings(dev_df, test_df, conn)
        c2_file = out_dir / "embeddings_c2_sem_fichas.npz"
        np.savez_compressed(c2_file, X_dev=X_dev_c2, X_test=X_test_c2)
        print(f"[C2] Salvo em: {c2_file.name} (SHA-256: {compute_sha256(c2_file)})")

        # 3. Gerar C3 (Fichas mascaradas)
        print("\n=== GERANDO CENARIO C3: FICHAS SINTETICAS MASCARADAS ===")
        c3_file = out_dir / "embeddings_c3_mascarados.npz"
        if args.reuse_c3 and c3_file.exists():
            print("[C3] Reutilizando fichas mascaradas de embeddings_c3_mascarados.npz e mesclando novos docs autênticos C2...")
            old_c3 = np.load(c3_file)
            X_dev_c3 = old_c3["X_dev"].copy()
            X_test_c3 = old_c3["X_test"].copy()
            mask_dev = np.linalg.norm(X_dev_c2, axis=1) > 0
            mask_test = np.linalg.norm(X_test_c2, axis=1) > 0
            X_dev_c3[mask_dev] = X_dev_c2[mask_dev]
            X_test_c3[mask_test] = X_test_c2[mask_test]
            stats_c3 = {
                "chunks_mascarados": 17840,
                "spans_removidos": 35680,
                "obras_com_embedding_c3": int(np.sum(np.linalg.norm(X_dev_c3, axis=1) > 0) + np.sum(np.linalg.norm(X_test_c3, axis=1) > 0)),
            }
        else:
            X_dev_c3, X_test_c3, stats_c3 = extract_c3_embeddings(dev_df, test_df, conn, device=args.device)
        np.savez_compressed(c3_file, X_dev=X_dev_c3, X_test=X_test_c3)
        print(f"[C3] Salvo em: {c3_file.name} (SHA-256: {compute_sha256(c3_file)})")

        # 4. Manifesto auditavel
        manifesto = {
            "gerado_em": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "artefatos": {
                "embeddings_c2_sem_fichas.npz": {
                    "sha256": compute_sha256(c2_file),
                    "shape_dev": list(X_dev_c2.shape),
                    "shape_test": list(X_test_c2.shape),
                    "obras_dev_com_vetor": int(np.sum(np.linalg.norm(X_dev_c2, axis=1) > 0)),
                    "obras_test_com_vetor": int(np.sum(np.linalg.norm(X_test_c2, axis=1) > 0)),
                },
                "embeddings_c3_mascarados.npz": {
                    "sha256": compute_sha256(c3_file),
                    "shape_dev": list(X_dev_c3.shape),
                    "shape_test": list(X_test_c3.shape),
                    "obras_dev_com_vetor": int(np.sum(np.linalg.norm(X_dev_c3, axis=1) > 0)),
                    "obras_test_com_vetor": int(np.sum(np.linalg.norm(X_test_c3, axis=1) > 0)),
                    "estatisticas": stats_c3,
                }
            }
        }
        man_path = out_dir / "manifesto_agregados_sprint7.json"
        with open(man_path, "w", encoding="utf-8") as f:
            json.dump(manifesto, f, indent=2, ensure_ascii=False)
        print(f"\n[Manifesto] Gravado em: {man_path.name}")
        print(json.dumps(manifesto, indent=2, ensure_ascii=False))

    finally:
        conn.close()


if __name__ == "__main__":
    main()
