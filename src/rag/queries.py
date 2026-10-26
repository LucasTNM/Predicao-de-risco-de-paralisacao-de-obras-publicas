# -*- coding: utf-8 -*-
"""
src/rag/queries.py
==================
Definição, validação contra vazamento de alvo e serialização das consultas causais
para o motor de recuperação semântica RAG por obra (Feature 019).

Garante que nenhuma consulta contenha termos de situação da obra (Artigo I da Constituição).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unicodedata
from typing import Any, Dict, List, Tuple

PROHIBITED_TERMS: Tuple[str, ...] = (
    "paralisad",     # paralisada, paralisado, paralisacao, paralisadas
    "em execu",      # em execucao, em execucoes
    "situacao",      # situacao cadastral/fisica
    "concluid",      # concluida, concluido
    "reiniciad",     # reiniciada, reiniciado
    "em andamento",  # em andamento
    "cadastrada",    # cadastrada
    "sem informacao",
)

CAUSAL_QUERIES: Dict[str, str] = {
    "regular": (
        "execucao regular do objeto conforme cronograma fisico-financeiro, "
        "avanco das medicoes dentro do prazo previsto, cumprimento das etapas "
        "contratuais e conformidade com as metas pactuadas"
    ),
    "tecnica": (
        "deficiencia de projeto basico e executivo, falhas de engenharia, "
        "divergencias geotecnicas de solo, necessidade de revisao de tracado, "
        "inconformidades tecnicas estruturais e pareceres tecnicos de correcao"
    ),
    "orcamentaria": (
        "indisponibilidade orcamentaria, contingenciamento de recursos, "
        "atraso na liberacao de parcelas de empenho e repasse financeiro, "
        "contrapartida municipal ou estadual pendente e bloqueio de pagamentos"
    ),
    "abandono": (
        "descumprimento de clausulas contratuais pela empresa contratada, "
        "desmobilizacao injustificada de maquinas e canteiro de obras, "
        "rescisao unilateral, notificacoes extrajudiciais, aplicacao de sancoes "
        "administrativas e abandono de servicos"
    ),
}


def normalize_text_for_audit(text: str) -> str:
    """Normaliza texto para auditoria estrita de termos de vazamento (caixa baixa, sem acentos)."""
    norm = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in norm if not unicodedata.combining(c))


def audit_query_text(text: str) -> bool:
    """
    Verifica se o texto da consulta contém qualquer termo proibido de vazamento.
    Retorna True se o texto estiver 100% limpo; lança ValueError se encontrar violação.
    """
    clean_text = normalize_text_for_audit(text)
    for term in PROHIBITED_TERMS:
        norm_term = normalize_text_for_audit(term)
        if norm_term in clean_text:
            raise ValueError(
                f"Violação do Artigo I da Constituição: termo proibido '{term}' detectado na consulta RAG."
            )
    return True


def get_causal_queries() -> Dict[str, str]:
    """Retorna as consultas causais auditadas."""
    for q_name, q_text in CAUSAL_QUERIES.items():
        audit_query_text(q_text)
    return dict(CAUSAL_QUERIES)


def compute_queries_hash(queries: Dict[str, str]) -> str:
    """Calcula hash SHA-256 determinístico das consultas."""
    serialized = json.dumps(queries, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def save_queries_catalog(output_path: Path) -> Path:
    """Salva o catálogo de consultas auditadas em JSON com hash embutido."""
    queries = get_causal_queries()
    h = compute_queries_hash(queries)
    payload = {
        "version": "1.0.0",
        "sha256": h,
        "prohibited_terms": list(PROHIBITED_TERMS),
        "queries": queries,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return output_path
