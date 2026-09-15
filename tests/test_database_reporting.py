"""A perda do relatório não pode ser comunicada como sucesso da auditoria."""
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.database.preflight import Audit
from src.database.run_load import run_load, save_report


@pytest.fixture(autouse=True)
def isolated_fingerprints():
    # Estes testes usam auditorias sinteticas; nao devem ler o Drive.
    with patch('src.database.run_load.source_fingerprints',
               return_value={'planilha': 'a' * 64}, create=True):
        yield


def test_report_write_failure_is_visible(tmp_path):
    with patch('src.database.run_load.LOGS_DIR', tmp_path), \
         patch('src.database.run_load.audit_sources', return_value=Audit(2025, {}, {})), \
         patch.object(Path, 'replace', side_effect=PermissionError('teste')):
        with pytest.raises(OSError):
            run_load(2025, dry_run=True)


def test_report_is_replaced_atomically(tmp_path):
    replacements = []
    original = Path.replace

    def replace(source, target):
        assert source != target
        json.loads(source.read_text(encoding='utf-8'))
        replacements.append(target)
        return original(source, target)

    with patch('src.database.run_load.LOGS_DIR', tmp_path), \
         patch('src.database.run_load.audit_sources', return_value=Audit(2025, {}, {})), \
         patch.object(Path, 'replace', replace):
        report = run_load(2025, dry_run=True)
    assert replacements
    paths = list(tmp_path.glob('sprint3_*.json'))
    reports = [p for p in paths if '_elegiveis' not in p.name]
    assert len(reports) == 1
    assert json.loads(reports[0].read_text(encoding='utf-8')) == report


def test_failed_publish_preserves_previous_report(tmp_path):
    path = tmp_path / 'report.json'
    path.write_text('{"estado":"anterior"}', encoding='utf-8')
    with patch.object(Path, 'replace', side_effect=PermissionError('teste')):
        with pytest.raises(OSError):
            save_report(path, {'estado': 'novo'})
    assert json.loads(path.read_text(encoding='utf-8')) == {'estado': 'anterior'}
    assert list(tmp_path.iterdir()) == [path]


def test_interruption_preserves_completed_year_and_progress(tmp_path):
    def audit(root, drive, year, base, *, progress):
        if year == 2025:
            return Audit(2025, {}, {})
        progress(1000, 2000)
        # Checkpoint precisa existir antes da falha, nao apenas no except final.
        saved = next(p for p in tmp_path.glob('sprint3_*.json') if '_elegiveis' not in p.name)
        current = json.loads(saved.read_text(encoding='utf-8'))
        assert current['anos'][0]['ano'] == 2025
        assert current['progresso']['verificados'] == 1000
        raise KeyboardInterrupt()

    with patch('src.database.run_load.LOGS_DIR', tmp_path), \
         patch('src.database.run_load.audit_sources', side_effect=audit):
        with pytest.raises(KeyboardInterrupt):
            run_load(dry_run=True)
    saved = next(p for p in tmp_path.glob('sprint3_*.json') if '_elegiveis' not in p.name)
    report = json.loads(saved.read_text(encoding='utf-8'))
    assert report['status'] == 'INTERROMPIDO'
    assert report['progresso']['ano'] == 2026


def test_changed_manifest_blocks_before_database_connection(tmp_path):
    with patch('src.database.run_load.LOGS_DIR', tmp_path), \
         patch('src.database.run_load.audit_sources', return_value=Audit(2025, {}, {})), \
         patch('src.database.run_load.source_fingerprints', side_effect=[{'fonte':'a'}, {'fonte':'b'}], create=True), \
         patch('src.database.connection.connect') as connect:
        with pytest.raises(ValueError, match='fontes.*alteradas'):
            run_load(2025, dry_run=False)
    connect.assert_not_called()


def test_dry_run_records_inventory_and_does_not_connect(tmp_path):
    from src.database.preflight import Document
    doc = Document(2025, 'dnit', 'a.pdf', 'a.txt', [('dnit','1')], [],
                   {'sha256_pdf': 'a'*64}, {}, text_hash='b'*64)
    audit = Audit(2025, {('dnit','1'):{}}, {}, [doc], source_texts=1)
    with patch('src.database.run_load.LOGS_DIR', tmp_path), \
         patch('src.database.run_load.audit_sources', return_value=audit), \
         patch('src.database.connection.connect') as connect:
        report = run_load(2025, dry_run=True)
    connect.assert_not_called()
    year = report['anos'][0]
    assert year['prontidao'] == 'APTO'
    assert year['fontes_estaveis'] is True
    inventory = json.loads(Path(year['inventario_elegiveis']['arquivo']).read_text(encoding='utf-8'))
    assert inventory[0]['sha256_txt'] == 'b'*64
    assert inventory[0]['obras'] == [['dnit','1']]
    assert report['fim']


@pytest.mark.parametrize('state,expected', [('quarentena','BLOQUEADO'),
                                          ('excluido','APTO_COM_EXCLUSOES')])
def test_issue_readiness_with_eligible_document(tmp_path, state, expected):
    from src.database.preflight import Document
    doc = Document(2025, 'dnit', 'a.pdf', 'a.txt', [('dnit','1')], [],
                   {'sha256_pdf': 'a'*64}, {}, text_hash='b'*64)
    audit = Audit(2025, {('dnit','1'):{}}, {}, [doc], source_texts=2)
    audit.reject('dnit','x.txt','coleta_ausente', state)
    with patch('src.database.run_load.LOGS_DIR', tmp_path), \
         patch('src.database.run_load.audit_sources', return_value=audit):
        report = run_load(2025, dry_run=True)
    assert report['status'] == 'PREFLIGHT'
    assert report['prontidao'] == expected
    assert report['anos'][0]['detalhes'][0]['estado'] == state


def test_quarantine_blocks_write_connection_without_explicit_exclusion(tmp_path):
    from src.database.preflight import Document
    doc = Document(2025, 'dnit', 'a.pdf', 'a.txt', [('dnit','1')], [],
                   {'sha256_pdf': 'a'*64}, {}, text_hash='b'*64)
    audit = Audit(2025, {('dnit','1'):{}}, {}, [doc], source_texts=2)
    audit.reject('dnit','x.txt','coleta_ausente')
    with patch('src.database.run_load.LOGS_DIR', tmp_path), \
         patch('src.database.run_load.audit_sources', return_value=audit), \
         patch('src.database.connection.connect') as connect:
        with pytest.raises(ValueError, match='quarentena'):
            run_load(2025)
    connect.assert_not_called()


def test_explicit_exclusion_never_passes_quarantined_document_to_loader(tmp_path):
    from src.database.preflight import Document
    doc = Document(2025, 'dnit', 'a.pdf', 'a.txt', [('dnit','1')], [],
                   {'sha256_pdf': 'a'*64}, {}, text_hash='b'*64)
    audit = Audit(2025, {('dnit','1'):{}}, {}, [doc], source_texts=2)
    audit.reject('dnit','x.txt','coleta_ausente')
    with patch('src.database.run_load.LOGS_DIR', tmp_path), \
         patch('src.database.run_load.audit_sources', return_value=audit), \
         patch('src.database.connection.connect'), \
         patch('src.database.schema.validate_schema'), \
         patch('src.database.load_obras.load_works', return_value={('dnit','1'):1}), \
         patch('src.database.load_documentos.load_document', return_value={'estado':'carregado','chunks':1}) as loader, \
         patch('src.database.validation.validate_data', return_value={'valido':True}), \
         patch('src.parsers.chunker.load_chunker'):
        report = run_load(2025, exclude_quarantine=True)
    assert loader.call_count == 1
    assert loader.call_args.args[1] is doc
    assert report['excluir_quarentena'] is True
    assert report['status'] == 'PARCIAL'
