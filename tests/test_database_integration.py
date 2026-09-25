"""Requer TEST_DATABASE_URL apontando a banco descartavel, nunca usa DATABASE_URL."""
from datetime import date
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

import psycopg

from src.database.connection import connect
from src.database.load_obras import load_works
from src.database.load_documentos import load_document, DocumentError
from src.database.embeddings import persist_embedding, EmbeddingError
from src.database.vector_search import search_embeddings
from src.database.preflight import Audit, Document, HEADERS
from src.database.schema import apply_schema, validate_schema
from src.database.validation import validate_data
from src.parsers.chunker import load_chunker


class TestPostgres(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.url = os.getenv('TEST_DATABASE_URL')
        if not cls.url:
            raise unittest.SkipTest('Execute scripts/testar_sprint3.py para criar banco de teste isolado.')
        if not urlsplit(cls.url).path.startswith('/tcc_test_'):
            raise RuntimeError('Banco de testes deve ter prefixo tcc_test_.')
        apply_schema(cls.url)
        cls.chunker = load_chunker()

    def setUp(self):
        self.conn = connect(self.url)
        self.tx = self.conn.transaction(force_rollback=True)
        self.tx.__enter__()
        self.addCleanup(self.conn.close)
        self.addCleanup(self.tx.__exit__, None, None, None)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.drive = Path(self.temp.name)
        r = dict.fromkeys(HEADERS)
        r.update({'base de dados':'dnit','id':'0001','data base':date(2025,4,1),
                  'empreendimento':'Obra de teste', 'exec. fisica':0.5, 'valor investimento':100})
        self.audit = Audit(2025, {('dnit','0001'):r}, {})
        self.facts = load_works(self.conn, self.audit)
        self.pdf = self.drive / '2025_Dados_brutos/dnit/teste.pdf'
        self.txt = self.drive / '2025_Textos_Limpos/dnit/teste.txt'
        self.pdf.parent.mkdir(parents=True)
        self.txt.parent.mkdir(parents=True)
        self.pdf.write_bytes(b'%PDF-1.4 fonte sintetica de teste')
        text = 'obra ' * 1000
        self.txt.write_text(text, encoding='utf-8')
        self.doc = Document(2025,'dnit','teste.pdf','teste.txt',[('dnit','0001')],
                            [{'base_de_dados':'DNIT','tipo_documento':'EDITAL'}],
                            {'sha256_pdf':hashlib.sha256(self.pdf.read_bytes()).hexdigest(),
                             'total_paginas':'1','metodo_extracao':'NATIVO'},
                            {'total_chars_depois':str(len(text)),'score_sujeira_depois':'0','metodo_limpeza':'NLP'})

    def test_load_and_idempotence(self):
        first = load_document(self.conn, self.doc, self.drive, self.facts, self.chunker)
        self.assertEqual(first['estado'], 'carregado')
        before = validate_data(self.conn)
        self.assertTrue(before['valido'], before)
        self.assertEqual(load_document(self.conn,self.doc,self.drive,self.facts,self.chunker)['estado'], 'reutilizado')
        self.assertEqual(load_works(self.conn, self.audit), self.facts)
        self.assertEqual(validate_data(self.conn), before)

    def test_audit_stratified_sample_covers_loaded_chunks(self):
        from scripts.auditar_embeddings_sprint4 import reproduction_rows, fingerprints
        from src.embedding_model import MODEL, REVISION
        load_document(self.conn, self.doc, self.drive, self.facts, self.chunker)
        before = fingerprints(self.conn)
        rows = self.conn.execute('SELECT id_embedding,chave_conteudo,conteudo_chunk FROM tcc.dim_embedding').fetchall()
        for identity, key, text in rows:
            persist_embedding(self.conn, identity=identity, key=key, text=text, values=[1.0]+[0.0]*767,
                              model=MODEL, revision=REVISION)
        self.assertEqual(fingerprints(self.conn), before)
        sampled = reproduction_rows(self.conn, sample=64, stratified=True)
        self.assertEqual({r[0] for r in sampled}, {r[0] for r in rows})
        with self.assertRaisesRegex(ValueError, 'limite_insuficiente'):
            reproduction_rows(self.conn, sample=1, stratified=True)

    def test_corpus_complete_resume_uses_no_model(self):
        import json
        from unittest.mock import Mock
        from src.database.embedding_corpus import prepare_corpus, run_corpus
        from src.database.embedding_run import run_batches
        load_document(self.conn, self.doc, self.drive, self.facts, self.chunker)
        path = self.drive/'corpus.json'
        manifest = prepare_corpus(self.conn, path, device='cpu', inference_batch=2, threads=8)
        def batch_runner(*args, **kwargs):
            def encoder(model, texts, **options):
                return [[1.0]+[0.0]*767 for _ in texts], [2]*len(texts)
            return run_batches(*args, encoder=encoder, **kwargs)
        with patch('src.database.embedding_corpus.run_batches', side_effect=batch_runner):
            first_loader = Mock()
            run_corpus(self.conn, manifest, path, write=True, loader=first_loader)
            first_loader.assert_called_once_with('cpu', 8)
            total = manifest['config']['total']
            self.assertEqual(manifest['attempts'][-1]['written'], total)
            manifest = json.loads(path.read_text(encoding='utf-8'))
            second_loader = Mock()
            run_corpus(self.conn, manifest, path, write=True, loader=second_loader)
            second_loader.assert_not_called()
            self.assertEqual(manifest['attempts'][-1]['written'], 0)
            self.assertEqual(manifest['attempts'][-1]['reused'], total)
            self.assertTrue(validate_data(self.conn)['valido'])

    def test_schema_rejects_embedding_without_revision(self):
        load_document(self.conn, self.doc, self.drive, self.facts, self.chunker)
        with self.assertRaises(psycopg.errors.CheckViolation):
            with self.conn.transaction():
                self.conn.execute('''UPDATE tcc.dim_embedding SET embedding=%s::vector,
                    modelo_embedding='modelo',revisao_embedding=NULL''',
                    ('['+','.join(map(str, [1.0]+[0.0]*767))+']',))
        self.assertTrue(validate_data(self.conn)['valido'])

    def test_embedding_batch_rollback_and_resume_after_checkpoint_failure(self):
        from unittest.mock import Mock
        from src.database.embedding_run import make_manifest, read_items, persist_batch, run_batches
        from src.database.run_load import save_report
        load_document(self.conn, self.doc, self.drive, self.facts, self.chunker)
        rows = self.conn.execute('''SELECT id_embedding,chave_conteudo,chunk_config
            FROM tcc.dim_embedding ORDER BY id_embedding LIMIT 2''').fetchall()
        self.assertEqual(len(rows), 2)
        manifest = make_manifest([dict(zip(['id_embedding','chave_conteudo','chunk_config'], row)) for row in rows],
                                 year=2025, origin=None, batch_size=2)
        items = read_items(self.conn, manifest['selection'])
        vector = [1.0] + [0.0] * 767
        with self.assertRaises(EmbeddingError):
            persist_batch(self.conn, items, [vector, [0.0] * 768])
        self.assertEqual(self.conn.execute('SELECT count(embedding) FROM tcc.dim_embedding').fetchone()[0], 0)
        calls = 0
        def failing_checkpoint(path, report):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError('checkpoint indisponivel depois do commit')
            save_report(path, report)
        path = self.drive / 'execution.json'
        with patch('src.database.embedding_run.save_report', side_effect=failing_checkpoint):
            with self.assertRaises(OSError):
                run_batches(self.conn, manifest, path, write=True, loader=Mock(),
                            encoder=Mock(return_value=([vector, vector], [2, 2])))
        self.assertEqual(self.conn.execute('SELECT count(embedding) FROM tcc.dim_embedding').fetchone()[0], 2)
        loader, encoder = Mock(), Mock()
        run_batches(self.conn, manifest, path, write=True, loader=loader, encoder=encoder)
        loader.assert_not_called()
        encoder.assert_not_called()
        self.assertEqual([i['estado'] for i in manifest['items']], ['reutilizado', 'reutilizado'])
        self.assertTrue(validate_data(self.conn)['valido'])

    def test_embedding_rejects_token_drift_before_inference(self):
        from src.database.embedding_run import read_items
        load_document(self.conn, self.doc, self.drive, self.facts, self.chunker)
        row = self.conn.execute('''SELECT id_embedding,chave_conteudo,chunk_config
            FROM tcc.dim_embedding ORDER BY id_embedding LIMIT 1''').fetchone()
        selection = [dict(zip(['id_embedding','chave_conteudo','chunk_config'], row))]
        self.conn.execute('UPDATE tcc.dim_embedding SET token_ids[1]=token_ids[1]+1 WHERE id_embedding=%s', (row[0],))
        with self.assertRaisesRegex(ValueError, 'fragmento_alterado'):
            read_items(self.conn, selection)

    def test_embedding_pilot_atomic_reuse_and_mismatch(self):
        load_document(self.conn, self.doc, self.drive, self.facts, self.chunker)
        identity, key, text = self.conn.execute('''SELECT id_embedding,chave_conteudo,conteudo_chunk
            FROM tcc.dim_embedding ORDER BY id_embedding LIMIT 1''').fetchone()
        vector = [1.0] + [0.0] * 767
        revision = 'a' * 40
        args = dict(identity=identity, key=key, text=text, values=vector,
                    model='modelo-teste', revision=revision)
        self.assertEqual(persist_embedding(self.conn, **args), 'gravado')
        self.assertEqual(persist_embedding(self.conn, **args), 'reutilizado')
        with self.assertRaisesRegex(EmbeddingError, 'outro_modelo'):
            persist_embedding(self.conn, **{**args, 'model': 'outro'})
        with self.assertRaisesRegex(EmbeddingError, 'fragmento_alterado'):
            persist_embedding(self.conn, **{**args, 'text': text + ' alterado'})
        self.assertEqual(self.conn.execute('''SELECT modelo_embedding,revisao_embedding
            FROM tcc.dim_embedding WHERE id_embedding=%s''', (identity,)).fetchone(),
                         ('modelo-teste', revision))
        self.assertTrue(validate_data(self.conn)['valido'])
        self.assertEqual(validate_data(self.conn, allow_embeddings=False)
                         ['inconsistencias']['vetor_preenchido_antes_card8'], 1)

    def test_embedding_rejects_bad_vector_before_write(self):
        load_document(self.conn, self.doc, self.drive, self.facts, self.chunker)
        identity, key, text = self.conn.execute('''SELECT id_embedding,chave_conteudo,conteudo_chunk
            FROM tcc.dim_embedding ORDER BY id_embedding LIMIT 1''').fetchone()
        with self.assertRaisesRegex(EmbeddingError, 'finitude'):
            persist_embedding(self.conn, identity=identity, key=key, text=text,
                              values=[float('nan')] * 768, model='teste', revision='a' * 40)
        self.assertIsNone(self.conn.execute('''SELECT embedding FROM tcc.dim_embedding
            WHERE id_embedding=%s''', (identity,)).fetchone()[0])

    def test_vector_search_exact_order_filters_and_provenance(self):
        load_document(self.conn, self.doc, self.drive, self.facts, self.chunker)
        rows = self.conn.execute('''SELECT id_embedding,chave_conteudo,conteudo_chunk
            FROM tcc.dim_embedding ORDER BY id_embedding''').fetchall()
        self.assertGreaterEqual(len(rows), 2)
        for index, (identity, key, text) in enumerate(rows[:2]):
            vector = [0.0]*768
            vector[index] = 1.0
            persist_embedding(self.conn, identity=identity, key=key, text=text,
                              values=vector, model='teste', revision='a'*40)
        kwargs = dict(model='teste', revision='a'*40, k=10, year=2025)
        results = search_embeddings(self.conn, [0.0, 1.0]+[0.0]*766, **kwargs)
        self.assertEqual([r['id_embedding'] for r in results], [rows[1][0], rows[0][0]])
        self.assertAlmostEqual(results[0]['distancia'], 0)
        self.assertAlmostEqual(results[1]['distancia'], 1)
        self.assertTrue(results[0]['ocorrencias'])
        self.assertEqual(results[0]['ocorrencias'][0]['ano'], 2025)
        self.assertEqual(search_embeddings(self.conn, [1.0]+[0.0]*767,
                         **{**kwargs, 'year': 2026}), [])
        self.assertEqual(search_embeddings(self.conn, [1.0]+[0.0]*767,
                         **{**kwargs, 'revision': 'b'*40}), [])
        self.assertEqual(search_embeddings(self.conn, [1.0]+[0.0]*767,
                         **{**kwargs, 'origin': 'ficha_sintetica'}), [])

    def test_pilot_sample_deduplicates_shared_occurrences(self):
        from scripts.piloto_embeddings_sprint4 import select_sample
        second = dict(self.audit.works['dnit','0001'], id='0002')
        self.audit.works['dnit','0002'] = second
        self.facts = load_works(self.conn, self.audit)
        self.doc.works.append(('dnit', '0002'))
        load_document(self.conn, self.doc, self.drive, self.facts, self.chunker)
        sample = select_sample(self.conn, 2)
        self.assertEqual(len(sample), 2)
        self.assertEqual(len({r[0] for r in sample}), 2)

    def test_rollback_mid_document(self):
        with patch('src.database.load_documentos.jsonb', side_effect=RuntimeError('falha simulada')):
            with self.assertRaises(RuntimeError):
                load_document(self.conn,self.doc,self.drive,self.facts,self.chunker)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM tcc.dim_documento').fetchone()[0], 0)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM tcc.dim_embedding').fetchone()[0], 0)

    def test_changed_text_requires_force_and_replaces_old_links(self):
        load_document(self.conn,self.doc,self.drive,self.facts,self.chunker)
        text = 'fiscalizacao ' * 600
        self.txt.write_text(text, encoding='utf-8')
        self.doc.cleaning['total_chars_depois'] = str(len(text))
        with self.assertRaises(DocumentError):
            load_document(self.conn,self.doc,self.drive,self.facts,self.chunker)
        self.assertEqual(load_document(self.conn,self.doc,self.drive,self.facts,self.chunker,force=True)['estado'], 'carregado')
        self.assertTrue(validate_data(self.conn)['valido'])
        self.assertEqual(self.conn.execute('SELECT count(*) FROM tcc.dim_documento').fetchone()[0], 1)

    def test_pdf_hash_mismatch(self):
        self.pdf.write_bytes(b'PDF alterado')
        with self.assertRaisesRegex(DocumentError, 'hash_pdf'):
            load_document(self.conn,self.doc,self.drive,self.facts,self.chunker)

    def test_confirmed_shared_document_does_not_duplicate_fact_measures(self):
        second = dict(self.audit.works['dnit','0001'], id='0002')
        self.audit.works['dnit','0002'] = second
        self.facts = load_works(self.conn, self.audit)
        self.doc.works.append(('dnit','0002'))
        result = load_document(self.conn,self.doc,self.drive,self.facts,self.chunker)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM tcc.ponte_documento_embedding').fetchone()[0], result['chunks']*2)
        self.assertEqual(self.conn.execute('SELECT sum(valor_investimento) FROM tcc.fato_risco').fetchone()[0], 200)
        self.assertTrue(validate_data(self.conn)['valido'])

    def test_constraints_and_schema_drift(self):
        fact = next(iter(self.facts.values()))
        with self.assertRaises(psycopg.errors.CheckViolation), self.conn.transaction():
            self.conn.execute("UPDATE tcc.fato_risco SET label_risco=4 WHERE id_fato=%s", (fact,))
        with self.assertRaises(psycopg.errors.ForeignKeyViolation), self.conn.transaction():
            self.conn.execute('INSERT INTO tcc.fato_risco (id_obra,ano_base) VALUES (999999,2025)')
        with self.conn.transaction(force_rollback=True):
            self.conn.execute('ALTER TABLE tcc.dim_obra ADD COLUMN coluna_indevida text')
            with self.assertRaises(RuntimeError):
                validate_schema(self.conn)
        validate_schema(self.conn)

    def test_reuse_rejects_corrupt_content_with_same_length(self):
        load_document(self.conn,self.doc,self.drive,self.facts,self.chunker)
        self.conn.execute("UPDATE tcc.dim_embedding SET conteudo_chunk=overlay(conteudo_chunk placing 'X' from 1 for 1)")
        self.assertFalse(validate_data(self.conn)['valido'])
        with self.assertRaises(DocumentError):
            load_document(self.conn,self.doc,self.drive,self.facts,self.chunker)

    def test_reuse_rejects_wrong_fact_with_same_link_count(self):
        second = dict(self.audit.works['dnit','0001'], id='0002')
        self.audit.works['dnit','0002'] = second
        self.facts = load_works(self.conn, self.audit)
        load_document(self.conn,self.doc,self.drive,self.facts,self.chunker)
        self.conn.execute('UPDATE tcc.ponte_documento_embedding SET id_fato=%s',
                          (self.facts['dnit','0002'],))
        with self.assertRaises(DocumentError):
            load_document(self.conn,self.doc,self.drive,self.facts,self.chunker)
        load_document(self.conn,self.doc,self.drive,self.facts,self.chunker,force=True)
        ids = self.conn.execute('SELECT DISTINCT id_fato FROM tcc.ponte_documento_embedding').fetchall()
        self.assertEqual(ids, [(self.facts['dnit','0001'],)])

    def test_shifted_offsets_are_not_valid_or_reusable(self):
        load_document(self.conn,self.doc,self.drive,self.facts,self.chunker)
        self.conn.execute('UPDATE tcc.ponte_documento_embedding SET token_inicio=token_inicio+1,token_fim=token_fim+1')
        self.assertFalse(validate_data(self.conn)['valido'])
        with self.assertRaises(DocumentError):
            load_document(self.conn,self.doc,self.drive,self.facts,self.chunker)

    def test_text_change_after_preflight_even_same_size_requires_new_audit(self):
        self.doc.text_hash = hashlib.sha256(self.txt.read_bytes()).hexdigest()
        self.txt.write_text('outro' * 1000, encoding='utf-8')
        with self.assertRaisesRegex(DocumentError, 'texto_alterado_apos_preflight'):
            load_document(self.conn,self.doc,self.drive,self.facts,self.chunker,force=True)

    def test_schema_signature_is_independent_of_search_path(self):
        self.conn.execute('SET LOCAL search_path TO pg_catalog,public')
        before = self.conn.execute('SHOW search_path').fetchone()[0]
        validate_schema(self.conn)
        self.assertEqual(self.conn.execute('SHOW search_path').fetchone()[0], before)

    def test_changed_token_ids_are_detected(self):
        load_document(self.conn,self.doc,self.drive,self.facts,self.chunker)
        self.conn.execute('UPDATE tcc.dim_embedding SET token_ids[1]=token_ids[1]+1')
        self.assertGreater(validate_data(self.conn)['inconsistencias']['conteudo_hash_inconsistente'], 0)
        with self.assertRaises(DocumentError):
            load_document(self.conn,self.doc,self.drive,self.facts,self.chunker)

    def test_rollback_after_copy_started(self):
        # Colisao forçada: primeiro chunk entra no COPY; a cauda tem outro conteudo.
        with patch('src.database.load_documentos.digest', return_value='a'*64):
            with self.assertRaisesRegex(DocumentError, 'colisao_hash'):
                load_document(self.conn,self.doc,self.drive,self.facts,self.chunker)
        for table in ('dim_documento', 'dim_embedding', 'ponte_documento_embedding'):
            self.assertEqual(self.conn.execute(f'SELECT count(*) FROM tcc.{table}').fetchone()[0], 0)
