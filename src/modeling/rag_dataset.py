# -*- coding: utf-8 -*-
"""
src/modeling/rag_dataset.py
===========================
Dataset PyTorch para carregar e tokenizar as evidências RAG por obra (Feature 020).

Lê o lote congelado 'evidencias_rag_dev.jsonl' gerado na Feature 019,
concatena os fragmentos recuperados por obra e tokeniza até 512 tokens.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import torch
from torch.utils.data import Dataset
from transformers import PreTrainedTokenizerBase


class WorkRAGDataset(Dataset):
    """Dataset de evidências RAG por obra para classificação binária no BERTimbau."""

    def __init__(
        self,
        jsonl_path: Path,
        tokenizer: PreTrainedTokenizerBase,
        max_length: int = 512,
        only_with_text: bool = True,
        limit: Optional[int] = None,
    ):
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.samples: List[Dict[str, Any]] = []

        if not jsonl_path.exists():
            raise FileNotFoundError(f"Arquivo de evidências RAG não encontrado: {jsonl_path}")

        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                record = json.loads(line)
                has_text = not record.get("sem_evidencia_textual", True)
                if only_with_text and not has_text:
                    continue

                chunks = record.get("chunks", [])
                concatenated_text = " [SEP] ".join(c.get("texto", "") for c in chunks)

                label_multiclass = int(record.get("label_risco", 0))
                # Binarização: 0 = Regular, 1 = Em Risco (classes 1, 2, 3)
                label_binary = 1 if label_multiclass > 0 else 0

                self.samples.append({
                    "id_fato": record.get("id_fato"),
                    "id_tcu": record.get("id_tcu"),
                    "label_multiclass": label_multiclass,
                    "label_binary": label_binary,
                    "text": concatenated_text,
                    "has_text": has_text,
                })

                if limit is not None and len(self.samples) >= limit:
                    break

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> Dict[str, Any]:
        item = self.samples[idx]
        text = item["text"]

        encoding = self.tokenizer(
            text,
            truncation=True,
            max_length=self.max_length,
            padding="max_length",
            return_tensors="pt",
        )

        return {
            "id_fato": item["id_fato"],
            "input_ids": encoding["input_ids"].squeeze(0),
            "attention_mask": encoding["attention_mask"].squeeze(0),
            "label": torch.tensor(item["label_binary"], dtype=torch.long),
        }
