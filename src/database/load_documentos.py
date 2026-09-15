"""Carga atomica por documento: hashes, fragmentos, ponte e retomada."""
from __future__ import annotations

from src.database.load_obras import jsonb
from src.database.preflight import DocumentError, validate_document_files
from src.parsers.chunker import digest


def load_document(conn, doc, drive, facts, chunker, force=False):
    text, text_hash, pdf_hash = validate_document_files(doc, drive)
    fact_ids = sorted({facts[key] for key in doc.works})
    if not fact_ids:
        raise DocumentError('documento_sem_obras')
    metadata = doc.metadata
    metadata['offsets_sobre'] = 'texto UTF-8 com quebras de linha normalizadas para LF'
    signature = digest([metadata, text_hash, pdf_hash, chunker.config, fact_ids])
    pdf_relative, txt_relative = f'{doc.base}/{doc.pdf}', f'{doc.base}/{doc.txt}'
    with conn.transaction():
        conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',
                     (f'{doc.year}/{pdf_relative}',))
        existing = conn.execute('''
            SELECT id_documento,assinatura_carga,num_chunks,num_obras,
                   (SELECT count(*) FROM tcc.ponte_documento_embedding p WHERE p.id_documento=d.id_documento)
            FROM tcc.dim_documento d WHERE ano_base=%s AND base_origem=%s AND caminho_pdf_relativo=%s
        ''', (doc.year, doc.base, pdf_relative)).fetchone()
        if existing and existing[1] != signature and not force:
            raise DocumentError('documento_ou_config_alterado_use_force')
        chunks = chunker.chunks(text)
        if not chunks:
            raise DocumentError('texto_sem_tokens')
        keyed = [(digest([c.text, c.token_ids, chunker.config]), c) for c in chunks]
        if existing and not force:
            expected = {
                (fact_id, c.position, c.token_start, c.token_end, c.char_start, c.char_end,
                 key, c.text, c.token_ids, len(c.token_ids), chunker.name, chunker.revision,
                 chunker.version, chunker.config)
                for key, c in keyed for fact_id in fact_ids
            }
            actual = set()
            for row in conn.execute('''
                SELECT p.id_fato,p.posicao_chunk,p.token_inicio,p.token_fim,p.char_inicio,p.char_fim,
                       e.chave_conteudo,e.conteudo_chunk,e.token_ids,e.num_tokens,e.tokenizer_name,
                       e.tokenizer_revision,e.versao_chunking,e.chunk_config
                FROM tcc.ponte_documento_embedding p JOIN tcc.dim_embedding e USING (id_embedding)
                WHERE p.id_documento=%s
            ''', (existing[0],)):
                actual.add((*row[:8], tuple(row[8]), *row[9:]))
            if (existing[2], existing[3], existing[4]) != (len(chunks), len(fact_ids), len(expected)) or actual != expected:
                raise DocumentError('carga_inconsistente_use_force')
            return {'estado': 'reutilizado', 'chunks': existing[2]}
        origin = 'ficha_sintetica' if any(tag in doc.pdf for tag in
                 ('_FichaTecnica_Saude.pdf', '_FichaTecnica_FNDE.pdf', '_Relatorio_Tecnico.pdf')) else 'nao_confirmada'
        # As evidencias ficam registradas; nao inferir "original" pelo tipo documental.
        metadata['evidencia_origem'] = 'padrao_de_nome_do_gerador_tecnicos.py' if origin == 'ficha_sintetica' else 'nao_verificada'
        old_ids = []
        if existing:
            old_ids = [r[0] for r in conn.execute('DELETE FROM tcc.ponte_documento_embedding WHERE id_documento=%s RETURNING id_embedding', (existing[0],))]
        values = (doc.year, doc.base, doc.collection[0]['base_de_dados'], pdf_relative, txt_relative,
                  pdf_hash, text_hash, doc.collection[0].get('tipo_documento'), origin,
                  doc.extraction.get('metodo_extracao'), doc.cleaning.get('metodo_limpeza'),
                  int(doc.extraction['total_paginas']), len(text), doc.cleaning['score_sujeira_depois'],
                  chunker.config, signature, len(chunks), len(fact_ids), jsonb(metadata))
        document_id = conn.execute('''
            INSERT INTO tcc.dim_documento (ano_base,base_origem,base_coleta,caminho_pdf_relativo,
                caminho_txt_relativo,sha256_pdf,sha256_txt,tipo_documento,origem_documento,
                metodo_extracao,metodo_limpeza,total_paginas,total_chars,score_sujeira,
                chunk_config,assinatura_carga,num_chunks,num_obras,metadados)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (ano_base,base_origem,caminho_pdf_relativo) DO UPDATE SET
                base_coleta=EXCLUDED.base_coleta,caminho_txt_relativo=EXCLUDED.caminho_txt_relativo,
                sha256_pdf=EXCLUDED.sha256_pdf,sha256_txt=EXCLUDED.sha256_txt,
                tipo_documento=EXCLUDED.tipo_documento,origem_documento=EXCLUDED.origem_documento,
                metodo_extracao=EXCLUDED.metodo_extracao,metodo_limpeza=EXCLUDED.metodo_limpeza,
                total_paginas=EXCLUDED.total_paginas,total_chars=EXCLUDED.total_chars,
                score_sujeira=EXCLUDED.score_sujeira,chunk_config=EXCLUDED.chunk_config,
                assinatura_carga=EXCLUDED.assinatura_carga,num_chunks=EXCLUDED.num_chunks,
                num_obras=EXCLUDED.num_obras,metadados=EXCLUDED.metadados,updated_at=now()
            RETURNING id_documento
        ''', values).fetchone()[0]
        with conn.cursor() as cur:
            cur.executemany('''
                INSERT INTO tcc.dim_embedding (chave_conteudo,conteudo_chunk,token_ids,num_tokens,
                    tokenizer_name,tokenizer_revision,versao_chunking,chunk_config)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (chave_conteudo) DO NOTHING
            ''', [(key, c.text, list(c.token_ids), len(c.token_ids), chunker.name,
                   chunker.revision, chunker.version, chunker.config) for key, c in keyed])
        records = {r[0]: r[1:] for r in conn.execute('''
            SELECT chave_conteudo,id_embedding,conteudo_chunk,token_ids,chunk_config
            FROM tcc.dim_embedding WHERE chave_conteudo=ANY(%s)
        ''', ([key for key, _ in keyed],))}
        with conn.cursor().copy('''COPY tcc.ponte_documento_embedding
             (id_fato,id_documento,id_embedding,ano_base,chunk_config,posicao_chunk,
              token_inicio,token_fim,char_inicio,char_fim) FROM STDIN''') as copy:
            for key, c in keyed:
                embedding_id, stored_text, stored_ids, stored_config = records[key]
                if (stored_text, tuple(stored_ids), stored_config) != (c.text, c.token_ids, chunker.config):
                    raise DocumentError('colisao_hash_ou_conteudo_corrompido')
                for fact_id in fact_ids:
                    copy.write_row((fact_id, document_id, embedding_id, doc.year, chunker.config,
                                    c.position, c.token_start, c.token_end, c.char_start, c.char_end))
        if old_ids:
            conn.execute('''DELETE FROM tcc.dim_embedding e WHERE id_embedding=ANY(%s)
                            AND NOT EXISTS (SELECT 1 FROM tcc.ponte_documento_embedding p WHERE p.id_embedding=e.id_embedding)''', (old_ids,))
    return {'estado': 'carregado', 'chunks': len(chunks)}
