"""Sliding Window em IDs WordPiece. Sem banco, arquivo ou chamadas Gemini."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
import re

from src.config import CHUNKING_VERSION, TOKENIZER_NAME, TOKENIZER_REVISION


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Chunk:
    position: int
    token_start: int
    token_end: int
    char_start: int
    char_end: int
    text: str
    token_ids: tuple[int, ...]


class SlidingWindow:
    def __init__(self, tokenizer, size=450, overlap=50, name=TOKENIZER_NAME,
                 revision=TOKENIZER_REVISION, version=CHUNKING_VERSION):
        special = tokenizer.num_special_tokens_to_add(pair=False)
        if not tokenizer.is_fast:
            raise ValueError("Tokenizer rapido com offsets obrigatorio.")
        if not isinstance(size, int) or not isinstance(overlap, int) or not 0 <= overlap < size:
            raise ValueError("Exigir 0 <= overlap < tamanho da janela.")
        if size + special > 512 or size + special > tokenizer.model_max_length:
            raise ValueError("Janela excede o limite do BERT com tokens especiais.")
        self.tokenizer = tokenizer
        self.size, self.overlap = size, overlap
        self.name, self.revision, self.version = name, revision, version
        self.config = digest([name, revision, version, size, overlap, special])

    def chunks(self, text: str) -> list[Chunk]:
        if not text.strip():
            return []
        encoded = self.tokenizer(text, add_special_tokens=False, truncation=False,
                                 return_offsets_mapping=True, verbose=False)
        ids, offsets = encoded["input_ids"], encoded["offset_mapping"]
        result = []
        start = 0
        while start < len(ids):
            end = min(start + self.size, len(ids))
            char_start, char_end = offsets[start][0], offsets[end - 1][1]
            if char_end <= char_start:
                raise ValueError("Tokenizer retornou intervalo de caracteres vazio.")
            result.append(Chunk(len(result), start, end, char_start, char_end,
                                text[char_start:char_end], tuple(ids[start:end])))
            if end == len(ids):
                break
            start = end - self.overlap
        return result


def load_chunker() -> SlidingWindow:
    from transformers import AutoTokenizer

    if not re.fullmatch(r"[0-9a-f]{40}", TOKENIZER_REVISION):
        raise ValueError("TOKENIZER_REVISION deve ser um commit SHA de 40 caracteres.")
    tokenizer = AutoTokenizer.from_pretrained(TOKENIZER_NAME, revision=TOKENIZER_REVISION,
                                             use_fast=True, trust_remote_code=False)
    return SlidingWindow(tokenizer, int(os.getenv("CHUNK_SIZE_TOKENS", "450")),
                         int(os.getenv("CHUNK_OVERLAP_TOKENS", "50")))
