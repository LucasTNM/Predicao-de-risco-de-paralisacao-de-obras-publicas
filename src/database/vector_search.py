"""Busca cosseno exata, com proveniencia e filtros antes do top-k."""
from src.database.embeddings import validate_vector


def search_embeddings(conn, values, *, model, revision, k=5, year=None, origin=None):
    if type(k) is not int or not 1 <= k <= 100:
        raise ValueError('k deve estar entre 1 e 100')
    if year is not None and year not in (2025, 2026):
        raise ValueError('ano deve ser 2025 ou 2026')
    if origin is not None and origin not in ('original', 'ficha_sintetica', 'nao_confirmada'):
        raise ValueError('origem invalida')
    literal = '[' + ','.join(map(str, validate_vector(values))) + ']'
    # MATERIALIZED impede uso acidental de ANN: esta e a referencia exata do piloto.
    # EXISTS evita repetir chunks compartilhados por documentos/obras.
    query = '''WITH candidates AS MATERIALIZED (
        SELECT e.id_embedding,e.chave_conteudo,e.conteudo_chunk,e.embedding
        FROM tcc.dim_embedding e
        WHERE e.embedding IS NOT NULL AND e.modelo_embedding=%s AND e.revisao_embedding=%s
        AND EXISTS (SELECT 1 FROM tcc.ponte_documento_embedding p
                    JOIN tcc.dim_documento d USING (id_documento)
                    WHERE p.id_embedding=e.id_embedding
                    AND (%s::integer IS NULL OR d.ano_base=%s)
                    AND (%s::text IS NULL OR d.origem_documento=%s)))
        SELECT id_embedding,chave_conteudo,conteudo_chunk,embedding <=> %s::vector AS distance
        FROM candidates ORDER BY distance,id_embedding LIMIT %s'''
    rows = conn.execute(query, (model, revision, year, year, origin, origin, literal, k)).fetchall()
    results = []
    for identity, key, text, distance in rows:
        links = conn.execute('''SELECT DISTINCT d.id_documento,d.ano_base,d.base_origem,
            d.origem_documento,p.id_fato,p.posicao_chunk,p.char_inicio,p.char_fim
            FROM tcc.ponte_documento_embedding p JOIN tcc.dim_documento d USING (id_documento)
            WHERE p.id_embedding=%s AND (%s::integer IS NULL OR d.ano_base=%s)
            AND (%s::text IS NULL OR d.origem_documento=%s)
            ORDER BY d.id_documento,p.id_fato,p.posicao_chunk,p.char_inicio,p.char_fim''',
            (identity, year, year, origin, origin)).fetchall()
        results.append(dict(id_embedding=identity, chave_conteudo=key, conteudo_chunk=text,
                            distancia=float(distance), similaridade=1.0-float(distance),
                            ocorrencias=[dict(zip(('id_documento', 'ano', 'base', 'origem',
                                'id_fato', 'posicao', 'char_inicio', 'char_fim'), row)) for row in links]))
    return results


def retrieval_metrics(ranked, relevant, k):
    """Relevantes devem ser julgados no universo avaliado, nao inferidos pelo ranking."""
    if type(k) is not int or k < 1 or len(ranked) != len(set(ranked)):
        raise ValueError('ranking/k invalido')
    relevant = set(relevant)
    if not relevant:
        raise ValueError('recall exige pelo menos um relevante julgado')
    hits = [i for i, identity in enumerate(ranked[:k], 1) if identity in relevant]
    return {'precision_at_k': len(hits)/k, 'recall_at_k': len(hits)/len(relevant),
            'reciprocal_rank_at_k': 1/hits[0] if hits else 0.0}
