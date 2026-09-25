"""Persistencia transacional de vetores do Card 8, sem alterar chunks ou ponte."""
from __future__ import annotations

import math
from src.parsers.chunker import digest


class EmbeddingError(ValueError):
    """Vetor ou estado do fragmento incompativel com o piloto."""


def validate_vector(values) -> list[float]:
    vector = [float(value) for value in values]
    if len(vector) != 768 or not all(math.isfinite(value) for value in vector):
        raise EmbeddingError('vetor_invalido_dimensao_ou_finitude')
    norm = math.sqrt(sum(value * value for value in vector))
    if not 0.99 <= norm <= 1.01:
        raise EmbeddingError('vetor_nao_normalizado')
    return vector


def persist_embedding(conn, *, identity: int, key: str, text: str,
                      values, model: str, revision: str) -> str:
    """Grava vetor/proveniencia juntos; reuso exige mesmo modelo e revisao."""
    vector = validate_vector(values)
    if not model or len(revision) != 40 or not all(c in '0123456789abcdef' for c in revision):
        raise EmbeddingError('proveniencia_modelo_invalida')
    vector_literal = '[' + ','.join(repr(value) for value in vector) + ']'
    with conn.transaction():
        row = conn.execute('''SELECT chave_conteudo,conteudo_chunk,embedding IS NOT NULL,
                                   modelo_embedding,revisao_embedding,token_ids,chunk_config
                              FROM tcc.dim_embedding WHERE id_embedding=%s FOR UPDATE''',
                           (identity,)).fetchone()
        if row is None or row[0] != key or row[1] != text:
            raise EmbeddingError('fragmento_alterado_apos_leitura')
        if digest([row[1], row[5], row[6]]) != key:
            raise EmbeddingError('hash_do_fragmento_inconsistente')
        if row[2]:
            if (row[3], row[4]) != (model, revision):
                raise EmbeddingError('vetor_existente_de_outro_modelo')
            return 'reutilizado'
        updated = conn.execute('''UPDATE tcc.dim_embedding SET
                                  embedding=%s::vector(768),modelo_embedding=%s,
                                  revisao_embedding=%s
                                  WHERE id_embedding=%s AND chave_conteudo=%s
                                  AND conteudo_chunk=%s AND embedding IS NULL
                                  RETURNING id_embedding''',
                               (vector_literal, model, revision, identity, key, text)).fetchone()
        if updated is None:
            raise EmbeddingError('fragmento_alterado_apos_leitura')
    return 'gravado'
