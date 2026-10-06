from datetime import date
import pytest

from tests.test_labeling import snapshot
from src.labeling.policy_v2 import classify
from src.labeling.recovery import build_recovery


@pytest.mark.parametrize('status', ['Em execução', 'Concluída'])
@pytest.mark.parametrize('cause', [None, '', '-', 'Não informado'])
def test_regular_zero(status, cause):
    result = classify(snapshot(situacao=status, situacao_origem=status, causa_paralisacao=cause))
    assert result['label_risco'] == 0 and result['regra'] == 'R00'


@pytest.mark.parametrize('origin', ['RESCINDIDO', 'OBRA CANCELADA', 'PARALISADA',
    'CONCLUÍDA COM ETAPA ÚTIL E COM PENDÊNCIA', 'EM EXECUÇÃO - REINICIADA', 'INACABADA'])
def test_origin_contradictions(origin):
    assert classify(snapshot(situacao='Concluída', situacao_origem=origin, causa_paralisacao=None))['label_risco'] is None


def test_sem_pendencia_is_not_com_pendencia():
    assert classify(snapshot(situacao='Concluída', situacao_origem='CONCLUÍDA COM ETAPA ÚTIL E SEM PENDÊNCIA', causa_paralisacao=None))['label_risco'] == 0


def test_cause_conflict_unknown_status_temporal_and_stopped():
    assert classify(snapshot(situacao='Em execução', situacao_origem='ATIVO'))['label_risco'] is None
    assert classify(snapshot(situacao='Cancelada', causa_paralisacao=None))['label_risco'] is None
    assert classify(snapshot(ano_base=2026, data_base=date(2026,4,1), situacao='Concluída', causa_paralisacao=None))['label_risco'] is None
    assert classify(snapshot(causa_paralisacao=None))['motivo'] == 'paralisada_sem_causa_recuperar_evidencia'
    assert classify(snapshot())['label_risco'] == 3


def doc(fact=1, identity=10, origin='nao_confirmada'):
    return dict(id_fato=fact, id_documento=identity, origem_documento=origin, num_obras=1)


def chunk(fact=1, document=10, identity=20):
    return dict(id_fato=fact, id_documento=document, id_embedding=identity, posicao_chunk=0,
                char_inicio=0, char_fim=53, conteudo_chunk='Paralisada por falta de pagamento à empresa executora.')


def test_recovery_never_uses_synthetic_or_other_work():
    row = snapshot(causa_paralisacao=None)
    docs = [doc(origin='ficha_sintetica'), doc(fact=2, identity=11, origin='original')]
    result = build_recovery([row], docs, [chunk(),chunk(fact=2, document=11)])
    item = result['obras'][0]
    assert item['encaminhamento'] == 'coletar_original_so_ficha_sintetica'
    assert item['trechos_candidatos'] == []
    assert len(item['documentos']) == 1


def test_recovery_has_all_missing_works_and_bounded_excerpts():
    a=snapshot(causa_paralisacao=None)
    b=snapshot(id_fato=2, causa_paralisacao='-')
    c=snapshot(id_fato=3, situacao='Concluída', causa_paralisacao=None)
    chunks=[chunk(identity=i) for i in range(10)]
    result=build_recovery([a,b,c], [doc()], chunks)
    assert result['total'] == 2
    first, second=result['obras']
    assert first['encaminhamento'] == 'confirmar_vinculo_origem_data_e_causa'
    assert len(first['trechos_candidatos']) == 3
    assert all('label_risco' not in s for s in first['trechos_candidatos'])
    assert second['encaminhamento'] == 'coletar_original_sem_documentos'
