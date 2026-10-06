from datetime import date
import pytest
from src.labeling.pilot import select_cases, split_identity
from src.labeling.pilot_sources import atomic_json, read_json, historical_events

def row(i, base='sismob', status='PARALISADA'):
    return dict(id_fato=i, id_tcu=f'{base}-{i}', base_de_dados=base,
                situacao_origem=status, documentos=[])

def test_selection_order_independent_no_overlap_and_status_coverage():
    rows = [row(i, status='CANCELADA' if i<10 else 'PARALISADA') for i in range(20)]
    legacy=[row(30)]
    a=select_cases(rows+legacy, {30}, {'sismob': 6})
    b=select_cases(list(reversed(rows+legacy)), {30}, {'sismob': 6})
    assert a==b
    assert len(a)==7
    assert len({r['id_fato'] for r in a})==7
    assert {r['situacao_origem'] for r in a if r['coorte']=='novo'} == {'CANCELADA','PARALISADA'}

def test_short_population_fails_not_silent_smaller_pilot():
    with pytest.raises(ValueError): select_cases([row(1)], set(), {'sismob': 2})

def test_same_identity_same_partition():
    assert split_identity('simec','SIMEC-42') == split_identity('simec','SIMEC-42')
    assert split_identity('simec','SIMEC-42') in ('reserva_avaliacao','desenvolvimento')

def test_atomic_unicode(tmp_path):
    path=tmp_path/'r.json'
    atomic_json(path, {'causa':'paralisação'})
    assert read_json(path)=={'causa':'paralisação'}

def test_historical_cause_uses_event_date_not_current_status():
    events=[{'data_historico_situacao_investimento':'2024-11-21','justificativa_cancelada_paralisada':'Falta de pagamento'},
            {'data_historico_situacao_investimento':'2026-01-01','justificativa_cancelada_paralisada':'Abandono'},
            {'data_historico_situacao_investimento':None,'justificativa_cancelada_paralisada':'Técnica'}]
    result=historical_events(events, '2025-04-01')
    assert len(result)==1
    assert result[0]['justificativa_cancelada_paralisada']=='Falta de pagamento'


class HTTPResponse:
    status_code=200
    headers={'Content-Type':'application/json'}
    url='https://sismobcidadao.saude.gov.br/api/public/obras/1'
    def __init__(self, body=b'{"ok":true}'):
        self.body=body
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def iter_content(self,size): yield self.body


class HTTPSession:
    def __init__(self): self.headers={}; self.calls=0
    def get(self,*args,**kwargs):
        self.calls+=1
        return HTTPResponse()


def test_cache_resume_and_tampering(tmp_path):
    from src.labeling.pilot_sources import PublicClient
    from pathlib import Path
    session=HTTPSession()
    client=PublicClient(tmp_path,session)
    url=HTTPResponse.url
    body,meta=client.get(url)
    assert client.get(url)[0]==body
    assert session.calls==1
    Path(meta['arquivo']).write_bytes(b'changed')
    with pytest.raises(ValueError,match='cached_response_changed'): client.get(url)


def test_network_failure_is_not_no_cause(tmp_path):
    from src.labeling.pilot_sources import PublicClient
    import requests
    session=HTTPSession()
    def fail(*args,**kwargs): raise requests.Timeout()
    session.get=fail
    client=PublicClient(tmp_path,session)
    assert client.json(HTTPResponse.url) is None
    assert client.attempts[0]['estado']=='erro_acesso'


class SismobClient:
    def __init__(self, detail): self.detail=detail; self.params=[]
    def json(self,url,params=None):
        self.params.append(params)
        if url.endswith('/municipios'): return [{'nome':'São Paulo','ibge':'355030'}]
        if url.endswith('/obras'): return {'content':[{'numeroProposta':'12345','propostaId':1}], 'last':True}
        return self.detail


def test_sismob_current_cause_not_historical_and_exact_identity_required():
    from src.labeling.pilot_sources import sismob
    case=dict(id_tcu='SISMOB-12345',data_base='2025-04-01',fonte={'local':'São Paulo/SP'})
    detail=dict(nuProposta='12345',sgUf='SP',noMunicipioAcentuado='São Paulo',
                dsJustificativa='Falta de pagamento',dtMudancaSituacao='2024-01-01',dtAtualizacao='2026-01-01')
    client=SismobClient(detail)
    result=sismob(case,client)
    assert result['identidade_confirmada']
    assert not result['candidatos_historicos']
    assert result['status']=='causa_sem_comprovacao_no_corte'
    assert client.params[1]['municipioIbge']=='355030'
    detail['dtAtualizacao']='2024-01-01'
    assert len(sismob(case,client)['candidatos_historicos'])==1
    detail['nuProposta']='99999'
    assert sismob(case,client)['status']=='identidade_divergente'


def test_review_handles_crlf_and_rejects_changed_original(tmp_path):
    import hashlib
    from src.labeling.pilot import apply_identity_reviews
    path=tmp_path/'legacy.txt'
    raw=b'Contrato\r\nObjeto administrativo\r\n'
    path.write_bytes(raw)
    sha=hashlib.sha256(raw).hexdigest()
    docs=[dict(id_documento=1,caminho=str(path),hash_confere=True,sha256_esperado=sha,
               texto_integral='Contrato\nObjeto administrativo\n')]
    results=[dict(id_fato=1,coorte='legado')]
    audits=[dict(id_fato=1,documentos=docs)]
    reviews=[dict(id_fato=1,revisor='assistente:teste',justificativa='Objeto incompatível',
                  decisao='vinculo_incompativel',evidencias=[dict(id_documento=1,sha256=sha,trecho='Objeto administrativo')])]
    updated,_=apply_identity_reviews(results,audits,reviews)
    assert updated[0]['status']=='quarentena_vinculo_incompativel'
    assert 'status' not in results[0]
    path.write_bytes(raw+b'alterado')
    with pytest.raises(ValueError,match='review_original_changed'):
        apply_identity_reviews(results,audits,reviews)


def test_resume_refuses_other_implementation():
    from scripts.piloto_recuperacao import check_resume
    result=dict(manifesto_sha256='source',implementacao_sha256='v1',tentativas=[])
    check_resume(result,'source','v1')
    with pytest.raises(ValueError,match='implementacao_alterada'):
        check_resume(result,'source','v2')
