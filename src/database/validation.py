"""Contagens e verificacoes independentes da integridade da carga."""
from src.database.schema import TABLES, validate_schema
from src.parsers.chunker import digest


def content_integrity(conn):
    """Recalcula a chave sem carregar o corpus inteiro na memoria."""
    errors = 0
    with conn.transaction(), conn.cursor(name='sprint3_content_audit') as cursor:
        cursor.itersize = 2048
        cursor.execute('SELECT chave_conteudo,conteudo_chunk,token_ids,chunk_config FROM tcc.dim_embedding')
        for key, text, ids, config in cursor:
            errors += key != digest([text, ids, config])
    return errors


def coverage_integrity(conn):
    """Confere inicio, progresso, lacunas e IDs sobrepostos por documento.

    A cauda e offsets textuais exatos exigem a fonte; o loader os confere no reuso.
    """
    errors = 0
    previous = None
    with conn.transaction(), conn.cursor(name='sprint3_coverage_audit') as cursor:
        cursor.itersize = 2048
        cursor.execute('''
            SELECT DISTINCT p.id_documento,p.posicao_chunk,p.token_inicio,p.token_fim,e.token_ids
            FROM tcc.ponte_documento_embedding p JOIN tcc.dim_embedding e USING (id_embedding)
            ORDER BY p.id_documento,p.posicao_chunk
        ''')
        for document, position, start, end, ids in cursor:
            if previous is None or document != previous[0]:
                errors += start != 0 or position != 0
            else:
                _, prev_position, prev_start, prev_end, prev_ids = previous
                overlap = prev_end - start
                if (position != prev_position + 1 or start <= prev_start or
                        end <= prev_end or overlap < 0 or overlap > len(ids) or
                        (overlap > 0 and prev_ids[-overlap:] != ids[:overlap])):
                    errors += 1
            previous = document, position, start, end, ids
    return errors


def validate_data(conn, *, allow_embeddings=True):
    validate_schema(conn)
    counts = {t: conn.execute(f'SELECT count(*) FROM tcc.{t}').fetchone()[0] for t in sorted(TABLES)}
    checks = {
        'obra_sem_fato': '''SELECT count(*) FROM tcc.dim_obra o WHERE NOT EXISTS
                           (SELECT 1 FROM tcc.fato_risco f WHERE f.id_obra=o.id_obra)''',
        'fragmento_sem_ponte': '''SELECT count(*) FROM tcc.dim_embedding e WHERE NOT EXISTS
                           (SELECT 1 FROM tcc.ponte_documento_embedding p WHERE p.id_embedding=e.id_embedding)''',
        'documento_incompleto': '''SELECT count(*) FROM tcc.dim_documento d WHERE
            (SELECT count(*) FROM tcc.ponte_documento_embedding p WHERE p.id_documento=d.id_documento) <> d.num_chunks*d.num_obras
            OR (SELECT count(DISTINCT id_fato) FROM tcc.ponte_documento_embedding p WHERE p.id_documento=d.id_documento) <> d.num_obras
            OR (SELECT count(DISTINCT posicao_chunk) FROM tcc.ponte_documento_embedding p WHERE p.id_documento=d.id_documento) <> d.num_chunks
            OR (SELECT min(posicao_chunk) FROM tcc.ponte_documento_embedding p WHERE p.id_documento=d.id_documento) <> 0
            OR (SELECT max(posicao_chunk) FROM tcc.ponte_documento_embedding p WHERE p.id_documento=d.id_documento) <> d.num_chunks-1''',
        'offset_ou_tokens_inconsistentes': '''SELECT count(*) FROM tcc.ponte_documento_embedding p
            JOIN tcc.dim_embedding e USING (id_embedding) JOIN tcc.dim_documento d USING (id_documento)
            WHERE p.token_fim-p.token_inicio <> e.num_tokens OR p.char_fim > d.total_chars
               OR p.char_fim-p.char_inicio <> length(e.conteudo_chunk)''',
        'posicao_documental_inconsistente': '''SELECT count(*) FROM (
            SELECT id_documento,chunk_config,posicao_chunk FROM tcc.ponte_documento_embedding
            GROUP BY id_documento,chunk_config,posicao_chunk
            HAVING count(DISTINCT (id_embedding,token_inicio,token_fim,char_inicio,char_fim))<>1) x''',
        'vetor_preenchido_antes_card8': ('SELECT 0' if allow_embeddings else
            'SELECT count(*) FROM tcc.dim_embedding WHERE embedding IS NOT NULL'),
        'vetor_inconsistente_card8': '''SELECT count(*) FROM tcc.dim_embedding WHERE embedding IS NOT NULL
            AND (modelo_embedding IS NULL OR modelo_embedding = '' OR
                 revisao_embedding IS NULL OR revisao_embedding !~ '^[0-9a-f]{40}$' OR
                 vector_norm(embedding) < 0.99 OR vector_norm(embedding) > 1.01)''',
        'rotulo_preenchido_sem_homologacao': 'SELECT count(*) FROM tcc.fato_risco WHERE label_risco IS NOT NULL',
    }
    errors = {key: conn.execute(query).fetchone()[0] for key, query in checks.items()}
    errors['conteudo_hash_inconsistente'] = content_integrity(conn)
    errors['cobertura_tokens_inconsistente'] = coverage_integrity(conn)
    return {'contagens': counts, 'inconsistencias': errors, 'valido': not any(errors.values())}
