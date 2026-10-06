"""Script oficial de preparacao, quarentena e particionamento de datasets da Sprint 6."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd
from src.docker_runtime import ensure_postgres
from src.dataset.extractor import build_consolidated_dataset
from src.dataset.partition import partition_by_work_identity, audit_leakage
from src.dataset.quarantine import get_quarantine_summary


def compute_sha256(path: Path) -> str:
    """Calcula o hash SHA-256 de um arquivo."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def main():
    parser = argparse.ArgumentParser(description="Prepara datasets particionados com quarentena documental.")
    parser.add_argument("--output-dir", type=str, default="dados_processados/sprint6",
                        help="Diretorio de destino dos artefatos")
    parser.add_argument("--seed", type=int, default=42,
                        help="Semente pseudo-aleatoria para particao estavel")
    parser.add_argument("--test-ratio", type=float, default=0.20,
                        help="Proporcao do conjunto de teste reservado")
    parser.add_argument("--skip-vectors", action="store_true",
                        help="Ignora extracao de vetores (somente atributos tabulares)")
    args = parser.parse_args()

    start_time = time.time()
    out_dir = ROOT / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Prepara ambiente Docker/PostgreSQL
    ensure_postgres(ROOT)

    # 2. Extrai dados consolidados com vetores e quarentena
    print("[Dataset] Extraindo observacoes e agregando embeddings com quarentena...")
    df_all = build_consolidated_dataset(ano=None, include_vectors=not args.skip_vectors)

    if len(df_all) != 60580:
        raise ValueError(f"Cardinalidade total inconsistente: esperado 60.580, obtido {len(df_all):,}")

    # 3. Particiona estritamente por identidade de obra (id_tcu)
    print("[Dataset] Particionando por identidade de obra sem vazamento...")
    df_part = partition_by_work_identity(df_all, seed=args.seed, test_ratio=args.test_ratio)

    # 4. Audita vazamento de dados
    audit = audit_leakage(df_part)
    if audit["vazamento_detectado"]:
        print(f"[ERRO] Vazamento detectado: {audit}", file=sys.stderr)
        return 2

    # 5. Segrega os subconjuntos
    df_dev = df_part[df_part["particao"] == "treino_dev"].copy()
    df_test = df_part[df_part["particao"] == "teste_retido"].copy()
    df_pendentes = df_part[df_part["particao"] == "pendentes_2025"].copy()
    df_isolado_2026 = df_part[df_part["particao"] == "isolado_2026"].copy()

    datasets = {
        "dataset_treino_dev_2025.parquet": df_dev,
        "dataset_teste_retido_2025.parquet": df_test,
        "dataset_pendentes_2025.parquet": df_pendentes,
        "dataset_isolado_2026.parquet": df_isolado_2026,
    }

    arquivos_manifesto = []

    # 6. Salva arquivos Parquet e calcula hashes SHA-256
    print("[Dataset] Gravando artefatos Parquet e calculando hashes...")
    for filename, df_sub in datasets.items():
        filepath = out_dir / filename
        df_sub.to_parquet(filepath, index=False, engine="pyarrow")
        sha256 = compute_sha256(filepath)
        arquivos_manifesto.append({
            "nome": filename,
            "caminho_relativo": str(filepath.relative_to(ROOT)),
            "linhas": len(df_sub),
            "obras_unicas": int(df_sub["id_tcu"].nunique()),
            "sha256": sha256,
        })

    # 7. Computa distribuicoes de classes para o manifesto
    def get_class_dist(df_sub):
        s = df_sub["label_risco"].dropna().astype(int).value_counts().to_dict()
        return {str(k): int(v) for k, v in sorted(s.items())}

    quarantine_summary = get_quarantine_summary()

    manifesto = {
        "versao_protocolo": "1.0.0",
        "data_geracao": datetime.now(timezone.utc).isoformat(),
        "seed": args.seed,
        "test_ratio": args.test_ratio,
        "skip_vectors": args.skip_vectors,
        "corte_historico_ano": 2025,
        "totais": {
            "total_banco": len(df_all),
            "total_2025": int((df_all["ano"] == 2025).sum()),
            "total_rotulado_2025": len(df_dev) + len(df_test),
            "total_pendente_2025": len(df_pendentes),
            "total_isolado_2026": len(df_isolado_2026),
        },
        "particoes": {
            "treino_dev": {
                "total_observacoes": len(df_dev),
                "obras_unicas": int(df_dev["id_tcu"].nunique()),
                "distribuicao_classes": get_class_dist(df_dev),
                "has_embedding_pct": round(float((df_dev["has_embedding"]).mean() * 100), 2),
            },
            "teste_retido": {
                "total_observacoes": len(df_test),
                "obras_unicas": int(df_test["id_tcu"].nunique()),
                "distribuicao_classes": get_class_dist(df_test),
                "has_embedding_pct": round(float((df_test["has_embedding"]).mean() * 100), 2),
            },
            "pendentes_2025": {
                "total_observacoes": len(df_pendentes),
                "obras_unicas": int(df_pendentes["id_tcu"].nunique()),
            },
            "isolado_2026": {
                "total_observacoes": len(df_isolado_2026),
                "obras_unicas": int(df_isolado_2026["id_tcu"].nunique()),
            },
        },
        "quarentena": quarantine_summary,
        "auditoria_vazamento": {
            "vazamento_detectado": audit["vazamento_detectado"],
            "intersecao_obras_dev_test": audit["intersecao_obras"],
            "linhas_2026_em_treino": audit["vazamento_linhas_2026"],
            "conforme_constituicao": not audit["vazamento_detectado"],
        },
        "arquivos_gerados": arquivos_manifesto,
        "duracao_segundos": round(time.time() - start_time, 2),
    }

    manifesto_path = out_dir / "manifesto_particionamento.json"
    with open(manifesto_path, "w", encoding="utf-8") as f:
        json.dump(manifesto, f, indent=2, ensure_ascii=False)

    total_time = round(time.time() - start_time, 2)
    print(f"[Dataset] Concluido em {total_time}s. Manifesto gravado em {manifesto_path}")

    result_json = {
        "sucesso": True,
        "total_processado": len(df_all),
        "particoes": {
            "treino_dev": len(df_dev),
            "teste_retido": len(df_test),
            "pendentes_2025": len(df_pendentes),
            "isolado_2026": len(df_isolado_2026),
        },
        "quarentena_aplicada": quarantine_summary["documentos_excluidos"],
        "vazamento_detectado": audit["vazamento_detectado"],
        "manifesto": str(manifesto_path.relative_to(ROOT)),
        "tempo_segundos": total_time,
    }
    print(json.dumps(result_json))
    return 0


if __name__ == "__main__":
    sys.exit(main())
