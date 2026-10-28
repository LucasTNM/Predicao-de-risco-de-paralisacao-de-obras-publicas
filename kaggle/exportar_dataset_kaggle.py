# -*- coding: utf-8 -*-
"""
kaggle/exportar_dataset_kaggle.py
=================================
Exporta para o Kaggle as partições congeladas da Sprint 6/7 (treino_dev: 14.522 obras;
teste_retido: 3.632 obras) com:

- atributos tabulares do perfil ``c1_sem_proxies`` (os mesmos do baseline C1);
- embeddings GTE 768d do cenário oficial C2 (``embeddings_c2_sem_fichas.npz``);
- evidências textuais autênticas do RAG (lista de chunks e texto concatenado);
- dobra de validação cruzada agrupada por ``id_tcu`` (semente 42), única para todos os modelos.

Revisão v2 (auditoria 2026-10-27): remove colunas que definem/derivam o rótulo
(situação, causa, origem e status de rotulagem), remove o embedding legado da Sprint 6,
remove contagens de documentos (proxies) e não grava identificadores no texto.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.modeling.loader import DEV_DATASET_DEFAULT, TEST_DATASET_DEFAULT, load_dataset
from src.modeling.splitter import StratifiedGroupSplitter

# Colunas que definem ou derivam o rótulo: NUNCA podem sair do ambiente local.
COLUNAS_PROIBIDAS = [
    "situacao_cadastral",
    "situacao_origem",
    "causa_cadastral",
    "origem_rotulo",
    "status_rotulagem",
]
# Embedding legado (Sprint 6, pode conter fichas sintéticas) e proxies de coleta.
COLUNAS_DESCARTADAS = ["embedding", "has_embedding", "num_docs_validos", "num_chunks_validos"]

COLUNAS_EXPORTADAS = [
    "id_fato", "id_obra", "id_tcu", "ano", "particao", "fold_cv",
    "base", "uf", "municipio",
    "valor_investimento", "valor_desbloqueado", "exec_fisica", "exec_financeira",
    "label_risco", "label_binario",
    "tem_texto", "n_chunks", "caracteres_texto", "chunks", "texto_integral",
    "gte_c2",
]

SEPARADOR_CHUNKS = "\n\n"


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def carregar_chunks_rag(jsonl_path: Path) -> dict[int, list[str]]:
    """Mapeia id_fato -> lista ordenada de chunks autênticos recuperados pelo RAG."""
    mapa: dict[int, list[str]] = {}
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            item = json.loads(line)
            chunks = []
            if not item.get("sem_evidencia_textual", True):
                chunks = [c.get("texto", "") for c in item.get("chunks", []) if c.get("texto", "").strip()]
            mapa[int(item["id_fato"])] = chunks
    return mapa


def montar_particao(df: pd.DataFrame, chunks_map: dict[int, list[str]], emb: np.ndarray) -> pd.DataFrame:
    if len(df) != emb.shape[0]:
        raise ValueError(f"Desalinhamento: {len(df)} linhas vs {emb.shape[0]} embeddings C2")
    faltantes = set(df["id_fato"].astype(int)) - set(chunks_map)
    if faltantes:
        raise ValueError(f"{len(faltantes)} id_fato sem registro no JSONL do RAG")

    out = df.drop(columns=[c for c in COLUNAS_PROIBIDAS + COLUNAS_DESCARTADAS if c in df.columns]).copy()
    out["label_risco"] = out["label_risco"].astype(int)
    out["label_binario"] = (out["label_risco"] > 0).astype(int)
    out["chunks"] = out["id_fato"].astype(int).map(chunks_map)
    out["n_chunks"] = out["chunks"].map(len).astype(int)
    out["tem_texto"] = out["n_chunks"] > 0
    out["texto_integral"] = out["chunks"].map(SEPARADOR_CHUNKS.join)
    out["caracteres_texto"] = out["texto_integral"].str.len().astype(int)
    out["gte_c2"] = list(emb.astype(np.float32))
    return out


def exportar_corpus(out_dir: Path, seed: int = 42) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    print("=" * 80)
    print("EXPORTAÇÃO DO CORPUS PARA O KAGGLE (v2 — auditada)")
    print("=" * 80)

    df_dev = load_dataset(DEV_DATASET_DEFAULT)
    df_test = load_dataset(TEST_DATASET_DEFAULT)
    npz = np.load(ROOT / "dados_processados" / "sprint7" / "embeddings_c2_sem_fichas.npz")
    dev_map = carregar_chunks_rag(ROOT / "dados_processados" / "sprint7" / "evidencias_rag_dev.jsonl")
    test_map = carregar_chunks_rag(ROOT / "dados_processados" / "sprint7" / "evidencias_rag_teste.jsonl")

    dev = montar_particao(df_dev, dev_map, npz["X_dev"])
    test = montar_particao(df_test, test_map, npz["X_test"])

    # Dobras agrupadas por obra, compartilhadas por TODOS os modelos (árvores e LLMs).
    splitter = StratifiedGroupSplitter(n_splits=5, seed=seed)
    folds = np.zeros(len(dev), dtype=np.int32)
    for k, (_, va) in enumerate(
        splitter.split(np.zeros((len(dev), 1)), dev["label_risco"].values, dev["id_tcu"].astype(str).values), 1
    ):
        folds[va] = k
    dev["fold_cv"] = folds
    test["fold_cv"] = -1

    # Verificações de integridade antes de gravar.
    assert not set(COLUNAS_PROIBIDAS) & set(dev.columns), "Coluna proibida no export"
    assert set(dev["id_tcu"]).isdisjoint(set(test["id_tcu"])), "Vazamento de obra entre partições"
    for k in range(1, 6):
        tr, va = dev[dev.fold_cv != k], dev[dev.fold_cv == k]
        assert set(tr["id_tcu"]).isdisjoint(set(va["id_tcu"])), f"Vazamento de obra na dobra {k}"

    dev = dev[COLUNAS_EXPORTADAS]
    test = test[COLUNAS_EXPORTADAS]
    dev_path = out_dir / "treino_dev_completo.parquet"
    test_path = out_dir / "teste_retido_completo.parquet"
    dev.to_parquet(dev_path, compression="zstd", index=False)
    test.to_parquet(test_path, compression="zstd", index=False)

    # Metadados para a CLI do Kaggle: substitua SEU_USUARIO antes de `kaggle datasets create`.
    meta_path = out_dir / "dataset-metadata.json"
    meta_path.write_text(json.dumps({
        "title": "TCC Obras TCU - corpus multimodal (privado)",
        "id": "SEU_USUARIO/tcc-obras-tcu-multimodal",
        "licenses": [{"name": "unknown"}],
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    def stats(d: pd.DataFrame) -> dict:
        t = d[d.tem_texto]
        return {
            "total_obras": int(len(d)),
            "obras_com_texto": int(len(t)),
            "distribuicao_classes": {str(k): int(v) for k, v in d["label_risco"].value_counts().sort_index().items()},
            "distribuicao_classes_com_texto": {str(k): int(v) for k, v in t["label_risco"].value_counts().sort_index().items()},
            "chunks_por_obra_com_texto": {str(k): int(v) for k, v in t["n_chunks"].value_counts().sort_index().items()},
            "media_caracteres_com_texto": round(float(t["caracteres_texto"].mean()), 1) if len(t) else 0.0,
        }

    manifesto = {
        "versao": 2,
        "gerado_em_utc": datetime.now(timezone.utc).isoformat(),
        "semente_folds": seed,
        "colunas": COLUNAS_EXPORTADAS,
        "colunas_removidas_por_vazamento": COLUNAS_PROIBIDAS,
        "colunas_removidas_outras": COLUNAS_DESCARTADAS,
        "origem_embeddings": "dados_processados/sprint7/embeddings_c2_sem_fichas.npz (GTE multilingual base, 768d)",
        "estatisticas": {"treino_dev": stats(dev), "teste_retido": stats(test)},
        "arquivos_sha256": {
            dev_path.name: compute_sha256(dev_path),
            test_path.name: compute_sha256(test_path),
        },
    }
    (out_dir / "manifesto_dataset_kaggle.json").write_text(
        json.dumps(manifesto, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(manifesto["estatisticas"], indent=2, ensure_ascii=False))
    print(f"Concluído em {time.time() - t0:.1f}s | {dev_path.stat().st_size/1e6:.1f} MB + {test_path.stat().st_size/1e6:.1f} MB")
    return manifesto


def main() -> None:
    parser = argparse.ArgumentParser(description="Exporta o corpus auditado para o Kaggle")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "kaggle" / "datasets_preparados")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    exportar_corpus(args.out_dir, seed=args.seed)


if __name__ == "__main__":
    main()
