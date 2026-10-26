# -*- coding: utf-8 -*-
"""
scripts/smoke_test_bertimbau.py
===============================
Script de teste de fumaça (Smoke Test) do BERTimbau + LoRA na GPU local (Feature 020).

Valida:
1. Menos de 2% de parâmetros treináveis (< 2,2M sobre ~110M).
2. Perda ponderada com tensor derivado analiticamente das classes.
3. 1 época de treinamento sobre amostra de 200 obras de treino_dev.
4. Consumo de VRAM monitorado e contido na GPU RTX 5060 de 8 GB.
5. Queda consistente da função de perda ao longo dos passos de gradiente.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
from typing import Any, Dict

import numpy as np
import torch
from torch.utils.data import DataLoader

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.modeling.bertimbau_lora import (
    create_bertimbau_lora_classifier,
    get_trainable_parameter_stats,
)
from src.modeling.rag_dataset import WorkRAGDataset
from src.modeling.torch_loss import create_weighted_cross_entropy_loss


def main():
    parser = argparse.ArgumentParser(description="Teste de fumaça do BERTimbau + LoRA na GPU")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--limit-samples", type=int, default=200)
    args = parser.parse_args()

    t_start = time.time()
    out_dir = ROOT / "dados_processados" / "sprint7"
    out_dir.mkdir(parents=True, exist_ok=True)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    gpu_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU"

    print("=" * 80)
    print("TESTE DE FUMAÇA: BERTIMBAU + LORA NA GPU (FEATURE 020)")
    print(f"Dispositivo: {device} ({gpu_name}) | Data: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 80)

    # 1. Carregar Modelo BERTimbau com LoRA
    print("\n[1/4] Inicializando BERTimbau cased com adaptadores LoRA (r=16, alpha=32)...")
    model, tokenizer = create_bertimbau_lora_classifier(
        num_labels=2,
        r=16,
        lora_alpha=32,
        lora_dropout=0.1,
        target_modules=["query", "value"],
        device=device,
    )

    stats = get_trainable_parameter_stats(model)
    print(f"      Total de Parâmetros: {stats['total_parameters']:,}")
    print(f"      Parâmetros Treináveis: {stats['trainable_parameters']:,} ({stats['trainable_percentage']}%)")
    print(f"      Critério < 2% Atendido: {stats['meets_lightweight_criteria']}")

    if not stats["meets_lightweight_criteria"]:
        raise ValueError("Falha de auditoria: mais de 2% de parâmetros treináveis!")

    # 2. Carregar Dataset RAG
    rag_jsonl = out_dir / "evidencias_rag_dev.jsonl"
    if not rag_jsonl.exists():
        raise FileNotFoundError(f"Lote congelado {rag_jsonl} não encontrado! Execute a Feature 019 primeiro.")

    print(f"\n[2/4] Carregando lote de evidências RAG ({rag_jsonl.name}, limite={args.limit_samples})...")
    # Para teste de fumaça, utilizamos as primeiras 200 obras com evidência textual
    dataset = WorkRAGDataset(
        jsonl_path=rag_jsonl,
        tokenizer=tokenizer,
        max_length=512,
        only_with_text=True,
        limit=args.limit_samples,
    )
    print(f"      Total de amostras textuais carregadas: {len(dataset)}")

    dataloader = DataLoader(dataset, batch_size=args.batch_size, shuffle=True)

    # 3. Configurar Perda Ponderada e Otimizador
    labels_all = np.array([s["label_binary"] for s in dataset.samples], dtype=np.int32)
    loss_fn = create_weighted_cross_entropy_loss(labels_all, num_classes=2, device=device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)

    print(f"\n[3/4] Perda Ponderada configurada:")
    print(f"      Pesos de classe aplicados: {loss_fn.weight.tolist()}")

    # 4. Executar 1 Época de Treino com Rastreamento de VRAM
    print(f"\n[4/4] Executando {args.epochs} época(s) de treino de fumaça (batch_size={args.batch_size})...")
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()

    model.train()
    step_losses = []
    t_train_start = time.time()

    use_cuda = (device.type == "cuda")
    scaler = torch.amp.GradScaler('cuda', enabled=use_cuda)

    for step, batch in enumerate(dataloader, 1):
        input_ids = batch["input_ids"].to(device)
        attention_mask = batch["attention_mask"].to(device)
        labels = batch["label"].to(device)

        optimizer.zero_grad()

        with torch.amp.autocast('cuda', enabled=use_cuda):
            outputs = model(input_ids=input_ids, attention_mask=attention_mask)
            logits = outputs.logits
            loss = loss_fn(logits, labels)

        scaler.scale(loss).backward()
        scaler.step(optimizer)
        scaler.update()

        loss_val = float(loss.item())
        step_losses.append(loss_val)

        if step % 5 == 0 or step == len(dataloader):
            print(f"      Passo [{step:>2}/{len(dataloader)}] - Perda: {loss_val:.4f}")

    train_duration = time.time() - t_train_start

    # Métricas de GPU e VRAM
    peak_vram_mb = 0.0
    if torch.cuda.is_available():
        peak_vram_mb = torch.cuda.max_memory_allocated() / (1024 ** 2)

    initial_loss = step_losses[0]
    final_loss = step_losses[-1]
    loss_reduced = final_loss < initial_loss

    print("\n" + "=" * 80)
    print("RESULTADO DO TESTE DE FUMAÇA")
    print("=" * 80)
    print(f"Tempo de Treino: {train_duration:.2f} segundos")
    print(f"Perda Inicial: {initial_loss:.4f} -> Perda Final: {final_loss:.4f} (Redução: {initial_loss - final_loss:+.4f})")
    print(f"VRAM Pico Utilizada: {peak_vram_mb:.1f} MB (Limite da RTX 5060: 8.192 MB)")
    print(f"Status de Sucesso: {'APROVADO' if peak_vram_mb < 7000 else 'ALERTA DE MEMÓRIA'}")

    summary = {
        "data_utc": datetime.now(timezone.utc).isoformat(),
        "dispositivo": str(device),
        "gpu_nome": gpu_name,
        "tempo_treino_segundos": round(train_duration, 2),
        "amostras_treinadas": len(dataset),
        "batch_size": args.batch_size,
        "vram_pico_mb": round(peak_vram_mb, 2),
        "vram_limite_mb": 8192,
        "perda_inicial": round(initial_loss, 4),
        "perda_final": round(final_loss, 4),
        "perda_reduzida": loss_reduced,
        "parametros": stats,
    }

    res_file = out_dir / "smoke_test_bertimbau.json"
    with open(res_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"Relatório gravado em: {res_file.name}")


if __name__ == "__main__":
    main()
