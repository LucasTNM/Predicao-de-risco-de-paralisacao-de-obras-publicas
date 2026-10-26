# -*- coding: utf-8 -*-
"""
scripts/vetorizar_novos_chunks_gte.py
=====================================
Codifica em GPU (CUDA) com o modelo oficial GTE (Alibaba-NLP/gte-multilingual-base)
todos os fragmentos em tcc.dim_embedding com embedding IS NULL vinculados às obras
do painel de 2025 (incluindo histórico <= 2025 da mesma obra), preservando o contrato
de validação (validate_vector, digest, modelo_embedding, revisao_embedding).
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.database.connection import connect
from src.database.embeddings import validate_vector
from src.embedding_model import MODEL, REVISION, encode_checked, load_model
from src.parsers.chunker import digest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", choices=["cuda", "cpu"], default="cuda")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--escopo", choices=["2025_rotulado", "2025_todos", "global"], default="2025_rotulado")
    args = parser.parse_args()

    with connect() as conn:
        if args.escopo == "2025_rotulado":
            query = """
            SELECT DISTINCT e.id_embedding, e.chave_conteudo, e.conteudo_chunk, e.token_ids, e.chunk_config
            FROM tcc.fato_risco f_target
            JOIN tcc.dim_obra o_target ON o_target.id_obra = f_target.id_obra
            JOIN tcc.dim_obra o_hist ON o_hist.base_de_dados = o_target.base_de_dados
                                    AND o_hist.id_tcu = o_target.id_tcu
                                    AND o_hist.ano_base <= f_target.ano_base
            JOIN tcc.fato_risco f_hist ON f_hist.id_obra = o_hist.id_obra
            JOIN tcc.ponte_documento_embedding p ON p.id_fato = f_hist.id_fato
            JOIN tcc.dim_documento d ON d.id_documento = p.id_documento
            JOIN tcc.dim_embedding e ON e.id_embedding = p.id_embedding
            WHERE f_target.ano_base = 2025
              AND f_target.status_rotulagem = 'ROTULADO'
              AND d.origem_documento <> 'ficha_sintetica'
              AND e.embedding IS NULL
            ORDER BY e.id_embedding;
            """
        elif args.escopo == "2025_todos":
            query = """
            SELECT DISTINCT e.id_embedding, e.chave_conteudo, e.conteudo_chunk, e.token_ids, e.chunk_config
            FROM tcc.ponte_documento_embedding p
            JOIN tcc.dim_embedding e USING (id_embedding)
            WHERE p.ano_base = 2025
              AND e.embedding IS NULL
            ORDER BY e.id_embedding;
            """
        else:
            query = """
            SELECT id_embedding, chave_conteudo, conteudo_chunk, token_ids, chunk_config
            FROM tcc.dim_embedding
            WHERE embedding IS NULL
            ORDER BY id_embedding;
            """

        rows = conn.execute(query).fetchall()
        total = len(rows)
        print(f"[GTE] Fragmentos pendentes de vetorização ({args.escopo}): {total:,}", flush=True)
        if total == 0:
            return 0

        print(f"[GTE] Carregando modelo {MODEL} ({REVISION[:10]}) em '{args.device}'...", flush=True)
        model = load_model(device=args.device, threads=8)

        t0 = time.monotonic()
        commit_chunk = 256
        processed = 0

        for start in range(0, total, commit_chunk):
            sub_rows = rows[start : start + commit_chunk]
            updates = []
            for b_start in range(0, len(sub_rows), args.batch_size):
                batch = sub_rows[b_start : b_start + args.batch_size]
                texts = [r[2] for r in batch]
                vectors, _ = encode_checked(model, texts, batch_size=len(batch))
                for (id_emb, key, text, tokens, cfg), vec in zip(batch, vectors):
                    if digest([text, tokens, cfg]) != key:
                        raise RuntimeError(f"Hash inconsistente no chunk {id_emb}")
                    checked = validate_vector(vec)
                    vec_lit = "[" + ",".join(repr(v) for v in checked) + "]"
                    updates.append((vec_lit, MODEL, REVISION, id_emb, key))

            with conn.transaction():
                with conn.cursor() as cur:
                    cur.executemany(
                        """
                        UPDATE tcc.dim_embedding
                        SET embedding = %s::vector(768),
                            modelo_embedding = %s,
                            revisao_embedding = %s
                        WHERE id_embedding = %s
                          AND chave_conteudo = %s
                          AND embedding IS NULL
                        """,
                        updates,
                    )
            processed += len(sub_rows)
            elapsed = time.monotonic() - t0
            rate = processed / max(elapsed, 0.001)
            if processed % 1024 == 0 or processed == total:
                print(
                    f"[GTE] {processed:,}/{total:,} ({processed/total*100:.1f}%) | "
                    f"{elapsed:.1f}s | {rate:.1f} chunks/s",
                    flush=True,
                )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
