"""Banco descartavel compartilhado pelo runner, com rollback por teste."""
from datetime import date
import hashlib
import json
import os
from urllib.parse import urlsplit

import psycopg
import pytest

from src.database.connection import connect
from src.database.labeling import apply_labels, audit_labels, inventory, read_rows
from src.database.load_obras import load_works
from src.database.preflight import Audit, HEADERS
from src.database.schema import apply_schema
from src.database.validation import validate_data
from src.labeling.policy import fingerprint


def work(identifier='1', cause='Abandono da empresa', year=2025):
    r = dict.fromkeys(HEADERS)
    r.update({'base de dados': 'teste', 'id': identifier, 'data base': date(year, 4, 1),
              'situacao': 'Paralisada', 'situacao origem': 'PARALISADA',
              'causa da paralisacao': cause, 'valor investimento': 100})
    return r


def load(conn, row):
    return load_works(conn, Audit(row['data base'].year, {('teste', row['id']): row}, {}))


@pytest.fixture
def db():
    url = os.getenv('TEST_DATABASE_URL')
    if not url:
        pytest.skip('Use scripts/testar_sprint3.py para banco descartavel.')
    if not urlsplit(url).path.startswith('/tcc_test_'):
        raise RuntimeError('Exige banco tcc_test_.')
    apply_schema(url)
    with connect(url) as conn, conn.transaction(force_rollback=True):
        load(conn, work())
        yield conn


def test_simulation_apply_resume_and_inventory(db):
    load(db, work('2', year=2026))
    load(db, work('3', cause=None))
    before = db.execute('select * from tcc.fato_risco order by id_fato').fetchall()
    report = apply_labels(db)
    assert report['propostos'] == 1 and report['atualizados'] == 0
    assert db.execute('select * from tcc.fato_risco order by id_fato').fetchall() == before
    first = apply_labels(db, write=True)
    assert first['atualizados'] == 1 and first['preservacao_verificada']
    persisted = db.execute('select * from tcc.fato_risco order by id_fato').fetchall()
    second = apply_labels(db, write=True)
    assert second['atualizados'] == 0 and second['reutilizados'] == 1
    assert db.execute('select * from tcc.fato_risco order by id_fato').fetchall() == persisted
    assert audit_labels(db)['valido']
    assert validate_data(db)['valido']
    assert not validate_data(db, allow_labels=False)['valido']
    inv = inventory(db)
    assert inv['por_ano'] == {2025: 2, 2026: 1}
    assert len(inv['fila_2025']) == 2
    assert db.execute('select count(label_risco) from tcc.fato_risco where ano_base=2026').fetchone()[0] == 0


def review(tmp_path, row, label=0):
    path = tmp_path/'vistoria.txt'
    path.write_text('Obra regular sem apontamentos graves na vistoria.', encoding='utf-8')
    return dict(id_fato=row['id_fato'], label_risco=label, snapshot_sha256=fingerprint(row),
                revisor='Revisor de teste', justificativa='Vistoria e conflito examinados.',
                regularidade_sem_apontamentos_graves=True,
                evidencia=dict(caminho=str(path), origem='original', data='2025-03-01',
                               sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                               trecho='Obra regular sem apontamentos graves'))


def test_manual_zero_resume_and_divergence(db, tmp_path):
    row = read_rows(db)[0]
    decision = review(tmp_path, row)
    assert apply_labels(db, write=True, reviews=[decision])['atualizados'] == 1
    assert db.execute('select label_risco from tcc.fato_risco').fetchone()[0] == 0
    assert apply_labels(db, write=True, reviews=[decision])['reutilizados'] == 1
    assert apply_labels(db, write=True)['atualizados'] == 0
    with pytest.raises(ValueError, match='divergente'):
        apply_labels(db, write=True, reviews=[{**decision, 'label_risco': 2}])
    assert audit_labels(db)['valido']
    (tmp_path/'vistoria.txt').write_text('alterado', encoding='utf-8')
    assert not audit_labels(db)['valido']


def test_invalid_second_review_and_duplicates_are_atomic(db, tmp_path):
    load(db, work('2'))
    rows = read_rows(db)
    a, b = [review(tmp_path, r) for r in rows]
    b['evidencia']['sha256'] = '0'*64
    with pytest.raises(ValueError): apply_labels(db, write=True, reviews=[a,b])
    with pytest.raises(ValueError): apply_labels(db, write=True, reviews=[a,a])
    assert db.execute('select count(label_risco) from tcc.fato_risco').fetchone()[0] == 0


def test_update_failure_rolls_back_entire_batch(db):
    load(db, work('2'))
    last = read_rows(db)[-1]['id_fato']
    db.execute(f'''CREATE FUNCTION pg_temp.fail_sprint5() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN IF NEW.id_fato={last} THEN RAISE EXCEPTION 'falha_injetada'; END IF; RETURN NEW; END $$''')
    db.execute('CREATE TRIGGER fail_sprint5 BEFORE UPDATE ON tcc.fato_risco FOR EACH ROW EXECUTE FUNCTION pg_temp.fail_sprint5()')
    with pytest.raises(psycopg.Error): apply_labels(db, write=True)
    assert db.execute('select count(label_risco) from tcc.fato_risco').fetchone()[0] == 0


@pytest.mark.parametrize('field,value', [('situacao', 'Concluída'),
    ('situacao origem', 'REINICIADA'), ('causa da paralisacao', 'Outros'),
    ('valor investimento', 101), ('pacto', 'Sim')])
def test_reload_invalidates_all_source_changes(db, field, value):
    apply_labels(db, write=True)
    changed = work(); changed[field] = value
    load(db, changed)
    assert db.execute('select label_risco,origem_rotulo,status_rotulagem from tcc.fato_risco').fetchone() == (None,None,'PENDENTE')


def test_identical_reload_preserves_label(db):
    apply_labels(db, write=True)
    before = db.execute('select * from tcc.fato_risco').fetchall()
    load(db, work())
    assert db.execute('select * from tcc.fato_risco').fetchall() == before


def test_stale_snapshot_and_unknown_provenance_rejected(db, tmp_path):
    decision = review(tmp_path, read_rows(db)[0])
    load(db, {**work(), 'situacao': 'Concluída'})
    with pytest.raises(ValueError, match='snapshot'): apply_labels(db, write=True, reviews=[decision])
    db.execute("update tcc.fato_risco set label_risco=0,status_rotulagem='ROTULADO',origem_rotulo='legado'")
    assert not audit_labels(db)['valido']
    with pytest.raises(ValueError, match='preexistente'): apply_labels(db, write=True)


def test_other_writer_cannot_enter_batch(db):
    # O primeiro lote mantem os locks ate a transacao externa do fixture terminar.
    apply_labels(db, write=True)
    with connect(os.environ['TEST_DATABASE_URL']) as other:
        with pytest.raises(psycopg.errors.LockNotAvailable):
            apply_labels(other, write=True)


def test_v1_preserved_while_v2_adds_regular_zero(db):
    from datetime import datetime, timezone
    from src.labeling import policy as old
    row = read_rows(db)[0]
    origin = dict(schema=old.SCHEMA,versao=old.VERSION,politica_sha256=old.policy_hash(),
                  snapshot_sha256=old.fingerprint(row),id_fato=row['id_fato'],label_risco=3,
                  metodo='regra',regra='A01',executor='pipeline:sprint5',
                  executado_em=datetime.now(timezone.utc).isoformat())
    serialized=old.canonical(origin)
    db.execute("UPDATE tcc.fato_risco SET label_risco=3,status_rotulagem='ROTULADO',origem_rotulo=%s",(serialized,))
    regular=work('2',cause=None); regular.update({'situacao':'Em execução','situacao origem':'EM EXECUÇÃO'})
    load(db,regular)
    result=apply_labels(db,write=True)
    assert result['atualizados']==1 and result['reutilizados']==1
    assert db.execute('SELECT origem_rotulo FROM tcc.fato_risco WHERE id_fato=%s',(row['id_fato'],)).fetchone()[0]==serialized
    rows=read_rows(db)
    assert rows[1]['label_risco']==0
    assert json.loads(rows[1]['origem_rotulo'])['metodo']=='regra_situacao'
    assert audit_labels(db)['valido']
    assert apply_labels(db,write=True)['atualizados']==0


def test_recovery_integration_missing_cause_no_documents(db):
    from src.labeling.recovery import recovery_report
    load(db,work('2',cause=None))
    load(db,work('3',cause=None,year=2026))
    result=recovery_report(db)
    assert result['total']==1
    assert result['obras'][0]['id_tcu']=='2'
    assert result['obras'][0]['encaminhamento']=='coletar_original_sem_documentos'
    assert result['rotulos_atribuidos']==0
