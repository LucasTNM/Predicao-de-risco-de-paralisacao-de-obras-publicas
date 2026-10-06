from datetime import date
import hashlib
import json

import pytest

from src.labeling.policy import classify, fingerprint, validate_review, policy_hash


def snapshot(**changes):
    row = dict(id_fato=1, id_obra=1, ano_base=2025, data_base=date(2025, 4, 1),
               base_de_dados='teste', id_tcu='001', situacao='Paralisada',
               situacao_origem='PARALISADA', causa_paralisacao='Abandono da empresa',
               fonte={'causa da paralisacao': 'Abandono da empresa'},
               exec_fisica=None, exec_financeira=None, valor_investimento=None,
               valor_desbloqueado=None, label_risco=None, origem_rotulo=None,
               status_rotulagem='PENDENTE')
    row.update(changes)
    return row


@pytest.mark.parametrize('cause,label', [
    ('Dificuldade técnica do Tomador', 1), (' Deficiência   do Projeto ', 1),
    ('LICENCIAMENTO AMBIENTAL', 1), ('Problemas técnicos da obra', 1),
    ('Falta de aporte de contrapartida', 2), ('Atraso no Pagamento Construtora', 2),
    ('Paralisação por falta de pagamento à empresa executora', 2),
    ('ORCAMENTARIA/FINANCEIRA UNIAO', 2), ('Orçamentário/Financeiro', 2),
    ('Abandono da empresa', 3), ('Abandono pela empresa', 3),
    ('ABANDONO POR PARTE DA CONTRATADA', 3),
    ('PEDIDO DE DISTRATO AMIGAVÉL POR PARTE DA CONTRATADA (RECISÃO).', 3),
])
def test_exact_rules(cause, label):
    assert classify(snapshot(causa_paralisacao=cause))['label_risco'] == label


@pytest.mark.parametrize('cause', [None, '', '-', 'Não informado', 'Outros',
    'Não houve abandono da empresa', 'Contrato Rescindido',
    'Dificuldade financeira da empresa executora', 'Dificuldade técnica da empresa executora',
    'Problemas técnicos da obra, Abandono pela empresa', 'Judicial', 'Deficiência do Orçamento'])
def test_no_guess_for_missing_unknown_or_ambiguous(cause):
    assert classify(snapshot(causa_paralisacao=cause))['label_risco'] is None


def test_temporal_conflict_and_zero():
    assert classify(snapshot(ano_base=2026, data_base=date(2026, 4, 1)))['motivo'] == 'fora_corte_2025'
    assert classify(snapshot(situacao='Concluída'))['motivo'] == 'conflito_situacao_causa'
    assert classify(snapshot(situacao='Concluída', causa_paralisacao=None))['label_risco'] is None
    assert classify(snapshot(data_base=date(2026, 1, 1)))['label_risco'] is None


def test_fingerprint_covers_source_not_label():
    row = snapshot()
    assert fingerprint(row) == fingerprint({**row, 'label_risco': 3, 'origem_rotulo': 'x'})
    assert fingerprint(row) != fingerprint({**row, 'situacao': 'Concluída'})
    assert fingerprint(row) != fingerprint({**row, 'fonte': {'novo': 1}})
    assert len(policy_hash()) == 64


def review(tmp_path, row=None, label=0):
    row = row or snapshot()
    evidence = tmp_path/'original.txt'
    evidence.write_text('Vistoria: execução regular sem apontamentos graves.', encoding='utf-8')
    return dict(id_fato=row['id_fato'], snapshot_sha256=fingerprint(row), label_risco=label,
                revisor='Pesquisador de teste', justificativa='Vistoria original examinada e conflito resolvido.',
                regularidade_sem_apontamentos_graves=True,
                evidencia=dict(caminho=str(evidence), sha256=hashlib.sha256(evidence.read_bytes()).hexdigest(),
                               data='2025-03-01', trecho='execução regular sem apontamentos graves.', origem='original'))


@pytest.mark.parametrize('label', [0, 1, 2, 3])
def test_review_all_classes(tmp_path, label):
    r = review(tmp_path, label=label)
    assert validate_review(snapshot(), r)['label_risco'] == label


@pytest.mark.parametrize('field,value', [('label_risco', True), ('label_risco', 4),
    ('label_risco', '0'), ('revisor', ''), ('justificativa', ''), ('snapshot_sha256', 'x'),
    ('regularidade_sem_apontamentos_graves', False)])
def test_review_invalid_fields(tmp_path, field, value):
    r = review(tmp_path); r[field] = value
    with pytest.raises(ValueError): validate_review(snapshot(), r)


@pytest.mark.parametrize('field,value', [('sha256', '0'*64), ('data', '2025-04-02'),
    ('data', '2026-01-01'), ('data', 'invalida'), ('trecho', 'inventado'), ('trecho', ''),
    ('origem', 'ficha_sintetica'), ('origem', 'nao_confirmada'), ('caminho', 'ausente.txt')])
def test_review_invalid_evidence(tmp_path, field, value):
    r = review(tmp_path); r['evidencia'][field] = value
    with pytest.raises(ValueError): validate_review(snapshot(), r)


def test_review_temporal_and_modified_file(tmp_path):
    row = snapshot(ano_base=2026, data_base=date(2026, 4, 1))
    with pytest.raises(ValueError): validate_review(row, review(tmp_path, row))
    r = review(tmp_path)
    (tmp_path/'original.txt').write_text('alterada', encoding='utf-8')
    with pytest.raises(ValueError): validate_review(snapshot(), r)


def test_cli_output_is_atomic_exclusive_and_lock_released(tmp_path):
    from scripts.rotular_sprint5 import reserve_output, publish
    path = tmp_path/'report.json'
    with pytest.raises(ValueError):
        with reserve_output(path):
            raise ValueError('falha antes de publicar')
    assert not path.exists() and not path.with_suffix('.json.lock').exists()
    with reserve_output(path):
        publish(path, {'conteudo': 'acentuação'})
    assert json.loads(path.read_text(encoding='utf-8')) == {'conteudo': 'acentuação'}
    with pytest.raises(ValueError):
        with reserve_output(path): pass
    with pytest.raises(FileExistsError): publish(path, {'sobrescrita': True})
    assert not path.with_suffix('.json.lock').exists()
    assert not list(tmp_path.glob('*.tmp'))


def test_cli_review_relative_evidence_path(tmp_path):
    from scripts.rotular_sprint5 import load_reviews
    r = review(tmp_path)
    r['evidencia']['caminho'] = 'original.txt'
    path = tmp_path/'decisoes.json'
    path.write_text(json.dumps({'decisoes': [r]}), encoding='utf-8')
    parsed = load_reviews(path)
    assert validate_review(snapshot(), parsed[0])['label_risco'] == 0
