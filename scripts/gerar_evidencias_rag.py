# -*- coding: utf-8 -*-
"""
scripts/gerar_evidencias_rag.py
===============================
Script CLI para materializar lotes congelados de evidências RAG por obra (Feature 019).

Gera:
- dados_processados/sprint7/evidencias_rag_dev.jsonl
- dados_processados/sprint7/evidencias_rag_teste.jsonl
- dados_processados/sprint7/manifesto_evidencias_rag.json
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.database.connection import connect
from src.rag.materializer import materialize_partition_evidence
from src.rag.retriever import WorkEvidenceRetriever


def main():
    parser = argparse.ArgumentParser(description="Gera lotes de evidências RAG congelados para treino e teste")
    parser.add_argument("--k", type=int, default=4, help="Número máximo de fragmentos por obra")
    args = parser.parse_args()

    t_start = time.time()
    out_dir = ROOT / "dados_processados" / "sprint7"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("MATERIALIZAÇÃO DE EVIDÊNCIAS RAG POR OBRA (FEATURE 019)")
    print(f"Top-k: {args.k} | Horário: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 80)

    # 1. Carregar partições
    dev_path = ROOT / "dados_processados" / "sprint6" / "dataset_treino_dev_2025.parquet"
    test_path = ROOT / "dados_processados" / "sprint6" / "dataset_teste_retido_2025.parquet"

    if not dev_path.exists() or not test_path.exists():
        raise FileNotFoundError("Partições da Feature 014 não encontradas em dados_processados/sprint6/!")

    print(f"[1/4] Carregando {dev_path.name} e {test_path.name} via DuckDB...")
    df_dev = duckdb.query(f"SELECT id_fato, id_tcu, label_risco FROM read_parquet('{dev_path.as_posix()}')").df()
    df_test = duckdb.query(f"SELECT id_fato, id_tcu, label_risco FROM read_parquet('{test_path.as_posix()}')").df()

    # Validação de não-vazamento
    dev_ids = set(df_dev["id_tcu"])
    test_ids = set(df_test["id_tcu"])
    overlap = dev_ids.intersection(test_ids)
    if len(overlap) > 0:
        raise RuntimeError(f"ERRO CRÍTICO: Vazamento de {len(overlap)} obras entre treino e teste!")
    print(f"      Treino/Dev: {len(df_dev):,} obras | Teste: {len(df_test):,} obras | Interseção: 0")

    # 2. Conexão ao PostgreSQL somente leitura
    print("[2/4] Conectando ao PostgreSQL local (modo somente leitura)...")
    conn = connect()
    conn.read_only = True

    retriever = WorkEvidenceRetriever(conn=conn, k=args.k)

    # 3. Materializar Treino/Dev
    dev_out_file = out_dir / "evidencias_rag_dev.jsonl"
    print(f"[3/4] Materializando {dev_out_file.name} ({len(df_dev):,} obras)...")
    stats_dev = materialize_partition_evidence(df_dev, retriever, dev_out_file, ano_base=2025)
    print(f"      Concluído em {stats_dev['tempo_segundos']:.1f}s | Obras com texto: {stats_dev['obras_com_evidencias']:,} ({stats_dev['percentual_cobertura_global']}%) | Chunks: {stats_dev['total_chunks_materializados']:,}")

    # 4. Materializar Teste Retido
    test_out_file = out_dir / "evidencias_rag_teste.jsonl"
    print(f"[4/4] Materializando {test_out_file.name} ({len(df_test):,} obras)...")
    stats_test = materialize_partition_evidence(df_test, retriever, test_out_file, ano_base=2025)
    print(f"      Concluído em {stats_test['tempo_segundos']:.1f}s | Obras com texto: {stats_test['obras_com_evidencias']:,} ({stats_test['percentual_cobertura_global']}%) | Chunks: {stats_test['total_chunks_materializados']:,}")

    # Manifesto Consolidado
    manifesto = {
        "versao": "1.0.0",
        "gerado_em_utc": datetime.now(timezone.utc).isoformat(),
        "top_k": args.k,
        "particao_dev": stats_dev,
        "particao_teste": stats_test,
    }

    manifesto_path = out_dir / "manifesto_evidencias_rag.json"
    with open(manifesto_path, "w", encoding="utf-8") as f:
        json.dump(manifesto, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 80)
    print("RESUMO CONSOLIDADO DE COBERTURA TEXTUAL RAG (DOCUMENTOS AUTÊNTICOS)")
    print("=" * 80)
    print(f"{'Partição':<12} | {'Classe':<8} | {'Total Obras':<12} | {'Obras com Texto':<16} | {'Cobertura':<10}")
    print("-" * 65)

    for p_name, p_stats in [("Treino/Dev", stats_dev), ("Teste Retido", stats_test)]:
        for c, data in p_stats["cobertura_por_classe"].items():
            print(f"{p_name:<12} | {c:<8} | {data['total']:<12,d} | {data['com_texto']:<16,d} | {data['percentual']:<10.2f}%")
        print("-" * 65)

    print(f"Manifesto salvo em: {manifesto_path.name}")
    print(f"Tempo total de execução: {time.time() - t_start:.2f}s")


if __name__ == "__main__":
    main()
