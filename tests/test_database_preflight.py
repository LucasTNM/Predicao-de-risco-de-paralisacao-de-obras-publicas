import csv
import hashlib
from datetime import datetime
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest

from openpyxl import Workbook

from src.database.preflight import HEADERS, audit_sources, load_works, number, geography


class TestPreflight(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.year = 2025
        self.base = 'sesu'
        w = Workbook()
        w.active.title = 'Export'
        w.active.append(HEADERS)
        self.work = [datetime(2025,4,1), 'SESU', 'Teste', '00042', 'Paralisada', 'Brasília/DF',
                     0.5, 1.1, 100, 110, 'Educação', 'MEC', None, None, None, 'SESU-0001', 'Paralisada']
        w.active.append(self.work)
        w.active.append(['Total'])
        w.active.append(['Filtros aplicados: data base'])
        w.save(self.root / 'data_2025.xlsx')
        self.pdf = 'SIMEC_SESU-0001_FichaTecnica_FNDE.pdf'
        self.txt = self.pdf.replace('.pdf','.txt')
        self.collected = [dict(base_de_dados='SIMEC', id_obra='SESU-0001', nome_arquivo=self.pdf,
                               status_validacao='VALIDADO')]
        pdf = self.root / '2025_Dados_brutos/sesu' / self.pdf
        pdf.parent.mkdir(parents=True)
        pdf.write_bytes(b'%PDF-1.4 fixture')
        self.extracted = [dict(ano_base='2025',base_de_dados='sesu',nome_pdf=self.pdf,nome_txt=self.txt,
                               status='OK',sha256_pdf=hashlib.sha256(pdf.read_bytes()).hexdigest(),
                               total_paginas='1')]
        self.cleaned = [dict(ano_base='2025',base_de_dados='sesu',nome_txt_entrada=self.txt,
                             nome_txt_saida=self.txt,status='OK',score_sujeira_depois='0',
                             total_chars_depois='4')]
        target = self.root / '2025_Textos_Limpos/sesu' / self.txt
        target.parent.mkdir(parents=True)
        target.write_text('obra', encoding='utf-8')

    def write_logs(self):
        for folder, name, rows in [('Dados_brutos','coleta',self.collected),
                                  ('Textos_extraidos','extracao',self.extracted),
                                  ('Textos_Limpos','higienizacao',self.cleaned)]:
            path = self.root / f'2025_{folder}/log_{name}.csv'
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('w', newline='', encoding='utf-8') as stream:
                writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)

    def test_alias_and_footer(self):
        self.write_logs()
        audit = audit_sources(self.root, self.root, self.year)
        self.assertEqual(len(audit.works), 1)
        self.assertEqual(audit.ignored_rows['rodape'], 2)
        self.assertEqual(audit.documents[0].works, [('sesu','SESU-0001')])
        self.assertEqual(audit.works['sesu','SESU-0001']['num. instrumento'], '00042')

    def test_latest_rejection_wins(self):
        self.collected.append(dict(self.collected[0], status_validacao='REJEITADO'))
        self.write_logs()
        audit = audit_sources(self.root, self.root, self.year)
        self.assertEqual(len(audit.documents), 0)
        self.assertEqual(audit.issues[0]['motivo'], 'coleta_nao_aceita')

    def test_unknown_work_is_not_inferred_from_filename(self):
        self.collected[0]['id_obra'] = 'DESCONHECIDA'
        self.write_logs()
        audit = audit_sources(self.root, self.root, self.year)
        self.assertEqual(audit.issues[0]['motivo'], 'obra_nao_encontrada')

    def test_bad_quality_and_unmanifested_file(self):
        self.cleaned[0]['score_sujeira_depois'] = '0.9'
        (self.root / '2025_Textos_Limpos/sesu/extra.txt').write_text('extra')
        self.write_logs()
        audit = audit_sources(self.root, self.root, self.year)
        self.assertEqual({i['motivo'] for i in audit.issues}, {'qualidade_residual','txt_sem_manifesto'})

    def test_numbers_keep_missing_and_ratios_above_one(self):
        self.assertIsNone(number(None))
        self.assertEqual(number(0), 0)
        self.assertEqual(number('110%'), Decimal('1.1'))
        self.assertEqual(number('R$ 1.234,50'), Decimal('1234.50'))
        self.assertEqual(geography('Brasília/DF'), ('DF','Brasília'))
        with self.assertRaises(ValueError):
            number('NaN')

    def test_pdf_missing_or_changed_is_quarantined_before_load(self):
        pdf = self.root / '2025_Dados_brutos/sesu' / self.pdf
        for content, reason in ((b'changed', 'hash_pdf_diverge_manifesto'),
                                (None, 'arquivo_fonte_ausente')):
            with self.subTest(reason=reason):
                if content is None:
                    pdf.unlink()
                else:
                    pdf.write_bytes(content)
                self.write_logs()
                audit = audit_sources(self.root, self.root, self.year)
                self.assertEqual(audit.documents, [])
                self.assertEqual(audit.issues[0]['motivo'], reason)

    def test_invalid_text_and_metadata_are_quarantined(self):
        txt = self.root / '2025_Textos_Limpos/sesu' / self.txt
        for content, chars, score in ((b'\xff', '4', '0'), (b'outro', '4', '0'),
                                      (b'obra', '4', 'NaN'), (b'obra', 'x', '0')):
            with self.subTest(content=content, chars=chars, score=score):
                txt.write_bytes(content)
                self.cleaned[0].update(total_chars_depois=chars, score_sujeira_depois=score)
                self.write_logs()
                audit = audit_sources(self.root, self.root, self.year)
                self.assertEqual(audit.documents, [])
                self.assertEqual(len(audit.issues), 1)

    def test_preflight_records_observed_text_hash(self):
        self.write_logs()
        audit = audit_sources(self.root, self.root, self.year)
        self.assertEqual(audit.documents[0].text_hash, hashlib.sha256(b'obra').hexdigest())

    def test_parallel_audit_matches_serial_with_failure_and_order_preserved(self):
        for i in range(12):
            name = f'fonte_{i:02d}'
            pdf, txt = name + '.pdf', name + '.txt'
            self.collected.append(dict(self.collected[0], nome_arquivo=pdf))
            self.extracted.append(dict(self.extracted[0], nome_pdf=pdf, nome_txt=txt))
            self.cleaned.append(dict(self.cleaned[0], nome_txt_entrada=txt, nome_txt_saida=txt))
            (self.root / '2025_Dados_brutos/sesu' / pdf).write_bytes(b'%PDF-1.4 fixture')
            (self.root / '2025_Textos_Limpos/sesu' / txt).write_bytes(b'obra' if i != 5 else b'\xff')
        self.write_logs()
        serial = audit_sources(self.root, self.root, self.year, workers=1)
        progress = []
        parallel = audit_sources(self.root, self.root, self.year, workers=5,
                                 progress=lambda done, total: progress.append((done, total)))
        self.assertEqual(serial, parallel)
        self.assertEqual(len(parallel.documents), 12)
        self.assertEqual(len(parallel.issues), 1)
        self.assertEqual(progress, [(13, 13)])
