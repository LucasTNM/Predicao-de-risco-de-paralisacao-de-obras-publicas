# -*- coding: utf-8 -*-
"""
src/dataset/masking.py
======================
Módulo de mascaramento determinístico de fichas sintéticas para eliminação de
Target Leakage (vazamento do alvo), em cumprimento ao Art. I da Constituição do TCC
e à Feature 018 do SpecKit.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

# Padrões de linhas que revelam a situação da obra (alvo) em fichas sintéticas
SITUATION_LINE_PATTERNS = [
    re.compile(r"^.*situa[çc][ãa]o.*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^.*\(origem:\s*(paralisada|em execu[çc][ãa]o|conclu[íi]da|cancelada)\).*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^.*status\s*(da obra|fnde|contratual).*$", re.IGNORECASE | re.MULTILINE),
]

# Rodapé boilerplate sintético gerado por tecnicos.py
BOILERPLATE_PATTERNS = [
    re.compile(r"^.*laudo e ficha t[ée]cnica de acompanhamento emitida.*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^.*instrumento de acompanh.*$", re.IGNORECASE | re.MULTILINE),
]

# Termos proibidos que não podem restar no texto mascarado de fichas sintéticas
FORBIDDEN_TERMS_REGEX = re.compile(
    r"\b(paralisad[ao]s?|em\s+execu[çc][ãa]o|conclu[íi]d[ao]s?)\b",
    re.IGNORECASE
)


def mask_synthetic_sheet_text(text: str) -> Tuple[str, List[Dict[str, Any]]]:
    """Expurga linhas e expressões que revelam a situação/alvo de fichas sintéticas.

    Retorna:
        masked_text: Texto higienizado sem termos do alvo.
        removed_spans: Lista de metadados dos trechos removidos com offsets originais.
    """
    if not text:
        return "", []

    removed_spans: List[Dict[str, Any]] = []

    # 1. Identificar e registrar trechos de situação
    for pattern in SITUATION_LINE_PATTERNS:
        for match in pattern.finditer(text):
            removed_spans.append({
                "char_inicio": match.start(),
                "char_fim": match.end(),
                "motivo": "vazamento_situacao_alvo",
                "texto_removido": match.group(0).strip(),
            })

    # 2. Identificar e registrar rodapés boilerplate
    for pattern in BOILERPLATE_PATTERNS:
        for match in pattern.finditer(text):
            removed_spans.append({
                "char_inicio": match.start(),
                "char_fim": match.end(),
                "motivo": "boilerplate_sintetico",
                "texto_removido": match.group(0).strip(),
            })

    # 3. Remover as linhas afetadas linha a linha
    lines = text.splitlines()
    cleaned_lines = []
    for line in lines:
        line_clean = line.strip()
        is_situation = any(p.search(line_clean) for p in SITUATION_LINE_PATTERNS)
        is_boilerplate = any(p.search(line_clean) for p in BOILERPLATE_PATTERNS)

        if not (is_situation or is_boilerplate):
            cleaned_lines.append(line)

    masked_text = "\n".join(cleaned_lines).strip()

    # 4. Fallback de sanitização residual: se ainda restar termo proibido isolado, mascarar
    masked_text = FORBIDDEN_TERMS_REGEX.sub("[STATUS_OMITIDO]", masked_text)

    return masked_text, removed_spans


def audit_masked_text_for_target_leakage(text: str) -> bool:
    """Verifica se o texto está 100% livre de termos de situação proibidos.

    Retorna True se aprovado (limpo de vazamento) e False se reprovado.
    """
    if not text:
        return True
    return bool(FORBIDDEN_TERMS_REGEX.search(text) is None)
