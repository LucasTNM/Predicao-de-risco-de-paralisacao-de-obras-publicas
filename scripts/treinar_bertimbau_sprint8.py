# -*- coding: utf-8 -*-
"""
scripts/treinar_bertimbau_sprint8.py
====================================
Orquestrador GPU (Feature 022 / Sprint 8) para:
1. Ajuste fino do BERTimbau + LoRA (Binário e Multiclasse 4 classes) em 5 dobras
   estratificadas e agrupadas por id_tcu sobre as 3.088 obras com texto autêntico
   de evidencias_rag_dev.jsonl, com parada antecipada e perda ponderada por dobra.
2. Treinamento do modelo final pré-registrado em treino_dev e predição única nas
   739 obras com texto autêntico do teste retido (evidencias_rag_teste.jsonl).
3. Extração de explicações XAI (Atenção do Encoder + Input x Gradient), Teste de
   Fidelidade por Deleção e Auditoria de Termos Proibidos em >= 60 obras do teste.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import sys
import time
from typing import Any, Dict, List, Tuple

import numpy as np
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    f1_score,
    matthews_corrcoef,
    precision_recall_fscore_support,
)
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, TensorDataset

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.modeling.bertimbau_lora import (
    BERTIMBAU_MODEL_NAME,
    create_bertimbau_lora_classifier,
    get_bertimbau_tokenizer,
    get_trainable_parameter_stats,
)
from src.modeling.metrics import compute_confusion_matrix
from src.modeling.splitter import StratifiedGroupSplitter
from src.modeling.torch_loss import create_weighted_cross_entropy_loss
from src.modeling.xai import (
    audit_prohibited_terms_in_top_tokens,
    extract_attention_and_grad_attribution,
    run_deletion_faithfulness_test,
)


def set_global_seed(seed: int = 42) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def load_and_pretokenize_rag_jsonl(
    jsonl_path: Path,
    tokenizer: Any,
    max_length: int = 512,
) -> Dict[str, Any]:
    """Lê todas as obras do JSONL e pré-tokeniza aquelas que possuem evidência textual."""
    all_records: List[Dict[str, Any]] = []
    text_records: List[Dict[str, Any]] = []

    with open(jsonl_path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            if not line.strip():
                continue
            rec = json.loads(line)
            rec["row_idx"] = idx
            all_records.append(rec)
            if not rec.get("sem_evidencia_textual", True):
                chunks = rec.get("chunks", [])
                text = " [SEP] ".join(c.get("texto", "") for c in chunks)
                rec["concat_text"] = text
                text_records.append(rec)

    texts = [r["concat_text"] for r in text_records]
    print(f"[Tokenização] Tokenizando {len(texts):,} obras com texto de {jsonl_path.name} (max_length={max_length})...", flush=True)
    enc = tokenizer(
        texts,
        truncation=True,
        max_length=max_length,
        padding="max_length",
        return_tensors="pt",
    )

    y_multi = np.array([int(r["label_risco"]) for r in text_records], dtype=np.int64)
    y_bin = (y_multi > 0).astype(np.int64)
    groups = np.array([str(r["id_tcu"]) for r in text_records])
    id_fatos = np.array([int(r["id_fato"]) for r in text_records], dtype=np.int64)
    row_indices = np.array([int(r["row_idx"]) for r in text_records], dtype=np.int64)

    return {
        "all_records": all_records,
        "text_records": text_records,
        "input_ids": enc["input_ids"],
        "attention_mask": enc["attention_mask"],
        "y_multi": y_multi,
        "y_bin": y_bin,
        "groups": groups,
        "id_fatos": id_fatos,
        "row_indices": row_indices,
    }


def evaluate_probs(y_true: np.ndarray, probs: np.ndarray, num_classes: int) -> Dict[str, Any]:
    y_pred = np.argmax(probs, axis=1)
    macro_f1 = float(f1_score(y_true, y_pred, average="macro", zero_division=0))
    bal_acc = float(balanced_accuracy_score(y_true, y_pred))
    mcc = float(matthews_corrcoef(y_true, y_pred))
    cm = compute_confusion_matrix(y_true, y_pred, num_classes=num_classes).tolist()
    labels_list = list(range(num_classes))
    prec, rec, f1_c, _ = precision_recall_fscore_support(y_true, y_pred, labels=labels_list, zero_division=0)

    pr_auc = {}
    for c in labels_list:
        y_b = (y_true == c).astype(int)
        pr_auc[f"classe_{c}"] = float(average_precision_score(y_b, probs[:, c])) if np.sum(y_b) > 0 else 0.0

    res = {
        "macro_f1": round(macro_f1, 4),
        "balanced_acc": round(bal_acc, 4),
        "mcc": round(mcc, 4),
        "pr_auc": {k: round(v, 4) for k, v in pr_auc.items()},
        "confusion_matrix": cm,
    }
    for c in labels_list:
        res[f"recall_classe_{c}"] = round(float(rec[c]), 4)
        res[f"precision_classe_{c}"] = round(float(prec[c]), 4)
        res[f"f1_classe_{c}"] = round(float(f1_c[c]), 4)
    return res


def predict_loader(model: torch.nn.Module, loader: DataLoader, device: torch.device, num_classes: int) -> np.ndarray:
    model.eval()
    all_probs = []
    use_cuda = device.type == "cuda"
    with torch.no_grad():
        for b_ids, b_mask in loader:
            b_ids = b_ids.to(device)
            b_mask = b_mask.to(device)
            with torch.amp.autocast("cuda", enabled=use_cuda):
                logits = model(input_ids=b_ids, attention_mask=b_mask).logits
                probs = F.softmax(logits.float(), dim=-1)
            all_probs.append(probs.cpu().numpy())
    return np.vstack(all_probs) if all_probs else np.zeros((0, num_classes), dtype=np.float32)


def train_and_eval_fold(
    train_ids: torch.Tensor,
    train_mask: torch.Tensor,
    y_train: np.ndarray,
    val_ids: torch.Tensor,
    val_mask: torch.Tensor,
    y_val: np.ndarray,
    num_classes: int,
    epochs: int,
    batch_size: int,
    lr: float,
    device: torch.device,
    seed: int,
) -> Tuple[np.ndarray, int, List[Dict[str, Any]]]:
    set_global_seed(seed)
    model, _ = create_bertimbau_lora_classifier(
        num_labels=num_classes,
        r=16,
        lora_alpha=32,
        lora_dropout=0.1,
        target_modules=["query", "value"],
        device=device,
    )

    loss_fn = create_weighted_cross_entropy_loss(y_train, num_classes=num_classes, device=device)
    optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=lr, weight_decay=0.01)

    train_ds = TensorDataset(train_ids, train_mask, torch.tensor(y_train, dtype=torch.long))
    val_ds = TensorDataset(val_ids, val_mask)

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size * 2, shuffle=False)

    use_cuda = device.type == "cuda"
    scaler = torch.amp.GradScaler("cuda", enabled=use_cuda)

    best_score = -1.0
    best_epoch = 1
    best_probs = np.zeros((len(y_val), num_classes), dtype=np.float32)
    history = []

    for ep in range(1, epochs + 1):
        model.train()
        ep_loss = 0.0
        steps = 0
        for b_ids, b_mask, b_y in train_loader:
            b_ids = b_ids.to(device)
            b_mask = b_mask.to(device)
            b_y = b_y.to(device)

            optimizer.zero_grad()
            with torch.amp.autocast("cuda", enabled=use_cuda):
                logits = model(input_ids=b_ids, attention_mask=b_mask).logits
                loss = loss_fn(logits, b_y)

            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()

            ep_loss += float(loss.item())
            steps += 1

        val_probs = predict_loader(model, val_loader, device, num_classes)
        val_metrics = evaluate_probs(y_val, val_probs, num_classes)
        val_metrics["epoch"] = ep
        val_metrics["train_loss"] = round(ep_loss / max(1, steps), 4)
        history.append(val_metrics)

        score = val_metrics["macro_f1"] + 0.5 * val_metrics["balanced_acc"]
        if score > best_score:
            best_score = score
            best_epoch = ep
            best_probs = val_probs.copy()

    del model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    return best_probs, best_epoch, history


def train_final_model(
    train_ids: torch.Tensor,
    train_mask: torch.Tensor,
    y_train: np.ndarray,
    num_classes: int,
    epochs: int,
    batch_size: int,
    lr: float,
    device: torch.device,
    seed: int,
) -> torch.nn.Module:
    set_global_seed(seed)
    model, _ = create_bertimbau_lora_classifier(
        num_labels=num_classes,
        r=16,
        lora_alpha=32,
        lora_dropout=0.1,
        target_modules=["query", "value"],
        device=device,
    )
    loss_fn = create_weighted_cross_entropy_loss(y_train, num_classes=num_classes, device=device)
    optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=lr, weight_decay=0.01)

    train_ds = TensorDataset(train_ids, train_mask, torch.tensor(y_train, dtype=torch.long))
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)

    use_cuda = device.type == "cuda"
    scaler = torch.amp.GradScaler("cuda", enabled=use_cuda)

    for ep in range(1, epochs + 1):
        model.train()
        ep_loss = 0.0
        steps = 0
        for b_ids, b_mask, b_y in train_loader:
            b_ids = b_ids.to(device)
            b_mask = b_mask.to(device)
            b_y = b_y.to(device)

            optimizer.zero_grad()
            with torch.amp.autocast("cuda", enabled=use_cuda):
                logits = model(input_ids=b_ids, attention_mask=b_mask).logits
                loss = loss_fn(logits, b_y)

            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()

            ep_loss += float(loss.item())
            steps += 1
        print(f"    [Modelo Final {num_classes} classes] Época {ep}/{epochs} - Loss: {ep_loss/max(1, steps):.4f}", flush=True)

    model.eval()
    return model


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    t_start = time.time()
    set_global_seed(args.seed)

    out_dir = ROOT / "dados_processados" / "sprint8"
    out_dir.mkdir(parents=True, exist_ok=True)
    model_dir = ROOT / "modelos" / "sprint8_bertimbau_lora"
    model_dir.mkdir(parents=True, exist_ok=True)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    gpu_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU"

    print("=" * 85, flush=True)
    print("SPRINT 8 (FEATURE 022) — TREINAMENTO BERTIMBAU + LORA, AVALIAÇÃO E XAI", flush=True)
    print(f"Dispositivo: {device} ({gpu_name}) | Semente: {args.seed}", flush=True)
    print("=" * 85, flush=True)

    tokenizer = get_bertimbau_tokenizer(BERTIMBAU_MODEL_NAME)

    dev_jsonl = ROOT / "dados_processados" / "sprint7" / "evidencias_rag_dev.jsonl"
    test_jsonl = ROOT / "dados_processados" / "sprint7" / "evidencias_rag_teste.jsonl"

    dev_data = load_and_pretokenize_rag_jsonl(dev_jsonl, tokenizer, max_length=512)
    test_data = load_and_pretokenize_rag_jsonl(test_jsonl, tokenizer, max_length=512)

    n_dev_text = len(dev_data["text_records"])
    n_test_text = len(test_data["text_records"])
    print(f"[Corpus Textual] Treino/Dev: {n_dev_text:,} obras com texto | Teste Retido: {n_test_text:,} obras com texto", flush=True)

    splitter = StratifiedGroupSplitter(n_splits=5, seed=args.seed)
    dummy_X = np.zeros((n_dev_text, 1), dtype=np.float32)
    folds = list(splitter.split(dummy_X, dev_data["y_multi"], dev_data["groups"]))

    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()

    bin_save_dir = model_dir / "binario"
    multi_save_dir = model_dir / "multiclasse"

    # 1. Validação Cruzada 5-Fold — Detector Binário de Risco (2 classes)
    print("\n[1/4] Executando 5-Fold Stratified Group CV — BERTimbau + LoRA Binário (0: Regular vs 1: Risco)...", flush=True)
    oof_probs_bin = np.zeros((n_dev_text, 2), dtype=np.float32)
    fold_metrics_bin = []
    best_epochs_bin = []

    for fold_idx, (tr_idx, va_idx) in enumerate(folds, 1):
        t_f = time.time()
        probs_va, best_ep, hist = train_and_eval_fold(
            train_ids=dev_data["input_ids"][tr_idx],
            train_mask=dev_data["attention_mask"][tr_idx],
            y_train=dev_data["y_bin"][tr_idx],
            val_ids=dev_data["input_ids"][va_idx],
            val_mask=dev_data["attention_mask"][va_idx],
            y_val=dev_data["y_bin"][va_idx],
            num_classes=2,
            epochs=args.epochs,
            batch_size=args.batch_size,
            lr=args.lr,
            device=device,
            seed=args.seed + fold_idx,
        )
        oof_probs_bin[va_idx] = probs_va
        best_epochs_bin.append(best_ep)
        m_fold = evaluate_probs(dev_data["y_bin"][va_idx], probs_va, num_classes=2)
        m_fold["fold"] = fold_idx
        m_fold["best_epoch"] = best_ep
        m_fold["history"] = hist
        fold_metrics_bin.append(m_fold)
        print(
            f"  [Binário Fold {fold_idx}/5] Macro-F1: {m_fold['macro_f1']:.4f} | "
            f"Bal.Acc: {m_fold['balanced_acc']:.4f} | MCC: {m_fold['mcc']:.4f} | "
            f"Rec.Risco: {m_fold['recall_classe_1']:.2%} (Ep {best_ep}, {time.time()-t_f:.1f}s)",
            flush=True,
        )

    oof_summary_bin = evaluate_probs(dev_data["y_bin"], oof_probs_bin, num_classes=2)
    print(f"  => [OOF Global Binário] Macro-F1: {oof_summary_bin['macro_f1']:.4f} | Bal.Acc: {oof_summary_bin['balanced_acc']:.4f} | MCC: {oof_summary_bin['mcc']:.4f}", flush=True)

    # 2. Validação Cruzada 5-Fold — Multiclasse (4 classes)
    print("\n[2/4] Executando 5-Fold Stratified Group CV — BERTimbau + LoRA Multiclasse ( Classes 0, 1, 2, 3)...", flush=True)
    oof_probs_multi = np.zeros((n_dev_text, 4), dtype=np.float32)
    fold_metrics_multi = []
    best_epochs_multi = []

    for fold_idx, (tr_idx, va_idx) in enumerate(folds, 1):
        t_f = time.time()
        probs_va, best_ep, hist = train_and_eval_fold(
            train_ids=dev_data["input_ids"][tr_idx],
            train_mask=dev_data["attention_mask"][tr_idx],
            y_train=dev_data["y_multi"][tr_idx],
            val_ids=dev_data["input_ids"][va_idx],
            val_mask=dev_data["attention_mask"][va_idx],
            y_val=dev_data["y_multi"][va_idx],
            num_classes=4,
            epochs=args.epochs,
            batch_size=args.batch_size,
            lr=args.lr,
            device=device,
            seed=args.seed + 100 + fold_idx,
        )
        oof_probs_multi[va_idx] = probs_va
        best_epochs_multi.append(best_ep)
        m_fold = evaluate_probs(dev_data["y_multi"][va_idx], probs_va, num_classes=4)
        m_fold["fold"] = fold_idx
        m_fold["best_epoch"] = best_ep
        m_fold["history"] = hist
        fold_metrics_multi.append(m_fold)
        print(
            f"  [Multiclasse Fold {fold_idx}/5] Macro-F1: {m_fold['macro_f1']:.4f} | "
            f"Bal.Acc: {m_fold['balanced_acc']:.4f} | MCC: {m_fold['mcc']:.4f} (Ep {best_ep}, {time.time()-t_f:.1f}s)",
            flush=True,
        )

    oof_summary_multi = evaluate_probs(dev_data["y_multi"], oof_probs_multi, num_classes=4)
    print(f"  => [OOF Global Multiclasse] Macro-F1: {oof_summary_multi['macro_f1']:.4f} | Bal.Acc: {oof_summary_multi['balanced_acc']:.4f} | MCC: {oof_summary_multi['mcc']:.4f}", flush=True)

    # 3. Treinar Modelos Finais Pré-Registrados e Inferir no Teste Retido
    opt_ep_bin = int(round(float(np.median(best_epochs_bin))))
    opt_ep_multi = int(round(float(np.median(best_epochs_multi))))
    print(f"\n[3/4] Treinando Modelos Finais Pré-Registrados (Binário={opt_ep_bin} ep, Multiclasse={opt_ep_multi} ep)...", flush=True)

    final_model_bin = train_final_model(
        train_ids=dev_data["input_ids"],
        train_mask=dev_data["attention_mask"],
        y_train=dev_data["y_bin"],
        num_classes=2,
        epochs=opt_ep_bin,
        batch_size=args.batch_size,
        lr=args.lr,
        device=device,
        seed=args.seed,
    )
    param_stats = get_trainable_parameter_stats(final_model_bin)
    bin_save_dir.mkdir(parents=True, exist_ok=True)
    final_model_bin.save_pretrained(bin_save_dir)

    test_loader = DataLoader(
        TensorDataset(test_data["input_ids"], test_data["attention_mask"]),
        batch_size=args.batch_size * 2,
        shuffle=False,
    )
    test_probs_bin = predict_loader(final_model_bin, test_loader, device, num_classes=2)
    test_summary_bin = evaluate_probs(test_data["y_bin"], test_probs_bin, num_classes=2)
    print(f"  => [Teste Retido 739 obras - Binário] Macro-F1: {test_summary_bin['macro_f1']:.4f} | Bal.Acc: {test_summary_bin['balanced_acc']:.4f} | MCC: {test_summary_bin['mcc']:.4f}", flush=True)

    final_model_multi = train_final_model(
        train_ids=dev_data["input_ids"],
        train_mask=dev_data["attention_mask"],
        y_train=dev_data["y_multi"],
        num_classes=4,
        epochs=opt_ep_multi,
        batch_size=args.batch_size,
        lr=args.lr,
        device=device,
        seed=args.seed + 200,
    )
    multi_save_dir.mkdir(parents=True, exist_ok=True)
    final_model_multi.save_pretrained(multi_save_dir)

    test_probs_multi = predict_loader(final_model_multi, test_loader, device, num_classes=4)
    test_summary_multi = evaluate_probs(test_data["y_multi"], test_probs_multi, num_classes=4)
    print(f"  => [Teste Retido 739 obras - Multiclasse] Macro-F1: {test_summary_multi['macro_f1']:.4f} | Bal.Acc: {test_summary_multi['balanced_acc']:.4f} | MCC: {test_summary_multi['mcc']:.4f}", flush=True)

    # 4. Explicabilidade (XAI) e Teste de Fidelidade por Deleção em >= 60 obras de teste
    print("\n[4/4] Extraindo Explicações XAI (Atenção + Gradientes + Deleção) nas obras do teste retido...", flush=True)
    selected_test_indices: List[int] = []
    for c in [0, 1, 2, 3]:
        c_indices = [i for i, y in enumerate(test_data["y_multi"]) if int(y) == c]
        limit_c = 25 if c in (0, 1) else len(c_indices)
        selected_test_indices.extend(c_indices[:limit_c])

    xai_records: List[Dict[str, Any]] = []
    faithful_count = 0
    leakage_alerts = 0
    drops_topk = []
    drops_rand = []

    for idx_in_text in selected_test_indices:
        rec = test_data["text_records"][idx_in_text]
        ids_i = test_data["input_ids"][idx_in_text]
        mask_i = test_data["attention_mask"][idx_in_text]

        attr = extract_attention_and_grad_attribution(
            model=final_model_bin,
            tokenizer=tokenizer,
            input_ids=ids_i,
            attention_mask=mask_i,
            target_class=None,
            top_k=12,
        )
        del_res = run_deletion_faithfulness_test(
            model=final_model_bin,
            tokenizer=tokenizer,
            input_ids=ids_i,
            attention_mask=mask_i,
            target_class=attr["target_class"],
            grad_scores=attr["grad_scores"],
            valid_indices=attr["valid_indices"],
            k_ratio=0.15,
            seed=args.seed + idx_in_text,
        )
        leak_audit = audit_prohibited_terms_in_top_tokens(attr["top_grad_tokens"] + attr["top_attn_tokens"])

        if del_res["faithful"]:
            faithful_count += 1
        if leak_audit["alerta_vazamento"]:
            leakage_alerts += 1
        drops_topk.append(del_res["drop_topk"])
        drops_rand.append(del_res["drop_random"])

        xai_records.append({
            "id_fato": int(rec["id_fato"]),
            "id_tcu": str(rec["id_tcu"]),
            "row_idx_teste": int(rec["row_idx"]),
            "label_real_multiclasse": int(rec["label_risco"]),
            "label_real_binario": int(1 if int(rec["label_risco"]) > 0 else 0),
            "pred_binario": int(attr["pred_class"]),
            "probs_binario": attr["probs"],
            "probs_multiclasse": [round(float(p), 6) for p in test_probs_multi[idx_in_text].tolist()],
            "top_grad_tokens": attr["top_grad_tokens"],
            "top_attn_tokens": attr["top_attn_tokens"],
            "deletion_test": del_res,
            "auditoria_vazamento_tokens": leak_audit,
        })

    peak_vram_mb = float(torch.cuda.max_memory_allocated() / (1024 ** 2)) if torch.cuda.is_available() else 0.0

    # Salvar matrizes NPZ de predições OOF e Teste
    npz_path = out_dir / "predicoes_bertimbau_sprint8.npz"
    np.savez_compressed(
        npz_path,
        dev_id_fatos=dev_data["id_fatos"],
        dev_row_indices=dev_data["row_indices"],
        dev_y_multi=dev_data["y_multi"],
        dev_y_bin=dev_data["y_bin"],
        oof_probs_bin=oof_probs_bin,
        oof_probs_multi=oof_probs_multi,
        test_id_fatos=test_data["id_fatos"],
        test_row_indices=test_data["row_indices"],
        test_y_multi=test_data["y_multi"],
        test_y_bin=test_data["y_bin"],
        test_probs_bin=test_probs_bin,
        test_probs_multi=test_probs_multi,
    )

    xai_summary = {
        "total_obras_explicadas": len(xai_records),
        "distribuicao_classes_explicadas": {
            str(c): sum(1 for r in xai_records if r["label_real_multiclasse"] == c)
            for c in [0, 1, 2, 3]
        },
        "taxa_fidelidade_delecao": round(faithful_count / max(1, len(xai_records)), 4),
        "media_drop_topk": round(float(np.mean(drops_topk)), 6),
        "media_drop_random": round(float(np.mean(drops_rand)), 6),
        "media_faithfulness_gap": round(float(np.mean(np.array(drops_topk) - np.array(drops_rand))), 6),
        "alertas_vazamento_termos_proibidos": leakage_alerts,
        "obras": xai_records,
    }
    xai_path = out_dir / "xai_bertimbau_teste.json"
    with open(xai_path, "w", encoding="utf-8") as f:
        json.dump(xai_summary, f, indent=2, ensure_ascii=False)

    cv_report = {
        "gerado_em_utc": datetime.now(timezone.utc).isoformat(),
        "dispositivo": str(device),
        "gpu_nome": gpu_name,
        "vram_pico_mb": round(peak_vram_mb, 2),
        "tempo_total_segundos": round(time.time() - t_start, 2),
        "parametros_lora": param_stats,
        "corpus": {
            "treino_dev_obras_com_texto": n_dev_text,
            "teste_retido_obras_com_texto": n_test_text,
        },
        "cv_5fold_binario": {
            "epocas_otimas_por_fold": best_epochs_bin,
            "epoca_final_selecionada": opt_ep_bin,
            "oof_global": oof_summary_bin,
            "folds": fold_metrics_bin,
        },
        "cv_5fold_multiclasse": {
            "epocas_otimas_por_fold": best_epochs_multi,
            "epoca_final_selecionada": opt_ep_multi,
            "oof_global": oof_summary_multi,
            "folds": fold_metrics_multi,
        },
        "teste_retido_apenas_com_texto": {
            "binario": test_summary_bin,
            "multiclasse": test_summary_multi,
        },
        "xai_resumo": {k: v for k, v in xai_summary.items() if k != "obras"},
        "artefatos_sha256": {
            "predicoes_bertimbau_sprint8.npz": compute_sha256(npz_path),
            "xai_bertimbau_teste.json": compute_sha256(xai_path),
        },
    }
    cv_path = out_dir / "metricas_bertimbau_cv_sprint8.json"
    with open(cv_path, "w", encoding="utf-8") as f:
        json.dump(cv_report, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 85, flush=True)
    print(f"CONCLUÍDO EM {time.time() - t_start:.1f}s | VRAM Pico: {peak_vram_mb:.1f} MB", flush=True)
    print(f"Fidelidade XAI ({len(xai_records)} obras): {xai_summary['taxa_fidelidade_delecao']*100:.1f}% (Drop Top-K: {xai_summary['media_drop_topk']:+.4f} vs Aleatório: {xai_summary['media_drop_random']:+.4f})", flush=True)
    print("=" * 85, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
