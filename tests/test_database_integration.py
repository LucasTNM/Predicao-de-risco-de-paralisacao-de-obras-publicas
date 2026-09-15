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
