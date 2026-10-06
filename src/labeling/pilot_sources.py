"""Public-source pilot adapters. Retrieval produces candidates, never labels."""
import csv
from datetime import date, datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tempfile
import time
from urllib.parse import urlparse
import zipfile

import requests

from src.labeling.policy import canonical, digest, normalize

SISMOB = 'https://sismobcidadao.saude.gov.br'
OBRAS = 'https://api-publica.obrasgov.gestao.gov.br/obras'
CROSSWALK = 'https://api-publica.transferegov.gestao.gov.br/downloads/dadosgov/siconv_dados_obrasgov_geral.zip'
HOSTS = {'sismobcidadao.saude.gov.br', 'api-publica.obrasgov.gestao.gov.br',
         'api-publica.transferegov.gestao.gov.br', 'simec.mec.gov.br'}
UF_CODES = dict(zip('RO AC AM RR PA AP TO MA PI CE RN PB PE AL SE BA MG ES RJ SP PR SC RS MS MT GO DF'.split(),
                   '11 12 13 14 15 16 17 21 22 23 24 25 26 27 28 29 31 32 33 35 41 42 43 50 51 52 53'.split()))


def atomic_bytes(path, raw):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix='.tmp')
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def atomic_json(path, value):
    atomic_bytes(path, (json.dumps(value, ensure_ascii=False, indent=2, default=str)+'\n').encode('utf-8'))


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


class PublicClient:
    def __init__(self, root, session=None):
        self.root = Path(root)
        self.session = session or requests.Session()
        self.session.headers.update({'User-Agent':'TCC-CausalRecoveryPilot/1.0'})
        self.attempts = []
        self.deadline = float('inf')

    def get(self, url, params=None):
        parsed = urlparse(url)
        if parsed.scheme != 'https' or parsed.hostname not in HOSTS:
            raise ValueError('unapproved_source')
        params = params or {}
        key = digest(dict(url=url, params=params))
        meta_path, body_path = self.root/f'{key}.json', self.root/f'{key}.body'
        if meta_path.exists():
            meta = read_json(meta_path)
            raw = body_path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != meta['sha256']:
                raise ValueError('cached_response_changed')
        else:
            if time.monotonic() >= self.deadline:
                raise TimeoutError('case_budget_exceeded')
            started = time.monotonic()
            meta = dict(url=url, parametros=params, metodo='GET',
                        coletado_em=datetime.now(timezone.utc).isoformat())
            raw = b''
            try:
                with self.session.get(url, params=params, timeout=(10,20), stream=True,
                                      allow_redirects=False) as response:
                    meta.update(http_status=response.status_code, url_final=response.url,
                                content_type=response.headers.get('Content-Type',''))
                    parts, size = [], 0
                    for block in response.iter_content(65536):
                        if time.monotonic() >= self.deadline:
                            raise TimeoutError('case_budget_exceeded')
                        size += len(block)
                        if size > 25_000_000:
                            raise ValueError('response_size_limit')
                        parts.append(block)
                    raw = b''.join(parts)
                    meta['estado'] = 'recebida' if response.status_code == 200 else 'http_indisponivel'
            except (requests.RequestException, TimeoutError, ValueError) as error:
                meta.update(estado='erro_acesso', erro=type(error).__name__)
            meta.update(segundos=round(time.monotonic()-started,3),
                        sha256=hashlib.sha256(raw).hexdigest(), arquivo=str(body_path.resolve()))
            atomic_bytes(body_path, raw)
            atomic_json(meta_path, meta)
        self.attempts.append(dict(key=key, **meta))
        return raw, meta

    def json(self, url, params=None):
        raw, meta = self.get(url,params)
        if meta['estado'] != 'recebida':
            return None
        try:
            return json.loads(raw)
        except (ValueError, UnicodeError):
            return None


def historical_events(events, cutoff):
    result = []
    for event in events:
        when = event.get('data_historico_situacao_investimento')
        cause = event.get('justificativa_cancelada_paralisada')
        try:
            valid = date.fromisoformat(when) <= date.fromisoformat(str(cutoff))
        except (ValueError, TypeError):
            valid = False
        if valid and isinstance(cause,str) and cause.strip():
            result.append(event)
    return result


def digits(value):
    return re.sub(r'\D','',str(value or ''))


def location(case):
    local = case['fonte'].get('local') or ''
    if '/' not in local:
        return '', local.upper()
    municipality, uf = local.rsplit('/',1)
    return municipality.strip(), uf.strip().upper()


def sismob(case, client):
    municipality, uf = location(case)
    target = case['id_tcu'].removeprefix('SISMOB-')
    result = dict(rota='sismob', status='identificador_insuficiente', consulta_especifica=False,
                  identidade_confirmada=False, candidatos_historicos=[])
    if uf not in UF_CODES or not municipality or not target.isdigit():
        return result
    result['consulta_especifica'] = True
    cities = client.json(SISMOB+'/api/public/endereco/municipios',
                         dict(ufIbge=UF_CODES[uf],query=municipality,pageSize=100))
    if not isinstance(cities,list):
        result['status']='acesso_indisponivel'
        return result
    matches = [c for c in cities if normalize(c.get('nome') or c.get('noMunicipio') or '')==normalize(municipality)]
    result['municipios_retornados']=cities
    if len(matches)!=1:
        result['status']='municipio_nao_resolvido'
        return result
    code=matches[0].get('ibge')
    found=[]
    for page in range(10):
        data=client.json(SISMOB+'/api/public/obras',dict(municipioIbge=code,page=page,size=100))
        if not isinstance(data,dict) or not isinstance(data.get('content'),list):
            result['status']='acesso_indisponivel'
            return result
        found.extend(r for r in data['content'] if digits(r.get('numeroProposta'))==target)
        if data.get('last') is True or page+1>=data.get('totalPages',1):
            break
    else:
        result['status']='limite_paginacao'
        return result
    if len(found)!=1:
        result['status']='proposta_nao_encontrada' if not found else 'identidade_ambigua'
        return result
    detail=client.json(SISMOB+f"/api/public/obras/{found[0]['propostaId']}")
    if not isinstance(detail,dict):
        result['status']='acesso_indisponivel'
        return result
    result['detalhe']=detail
    if (digits(detail.get('nuProposta'))!=target or detail.get('sgUf')!=uf or
        normalize(detail.get('noMunicipioAcentuado') or detail.get('noMunicipio'))!=normalize(municipality)):
        result['status']='identidade_divergente'
        return result
    result['identidade_confirmada']=True
    cause=detail.get('dsJustificativa')
    if not isinstance(cause,str) or not cause.strip():
        result['status']='identidade_confirmada_sem_causa'
        return result
    cutoff=date.fromisoformat(str(case['data_base']))
    try:
        timely=all(date.fromisoformat(detail[k])<=cutoff for k in ('dtMudancaSituacao','dtAtualizacao'))
    except (ValueError,TypeError,KeyError):
        timely=False
    result['status']='candidato_historico_requer_revisao' if timely else 'causa_sem_comprovacao_no_corte'
    if timely:
        result['candidatos_historicos']=[dict(trecho=cause,data=detail['dtMudancaSituacao'],
                                             data_atualizacao=detail['dtAtualizacao'],fonte='sismob')]
    return result


def crosswalk_rows(client):
    raw, meta=client.get(CROSSWALK)
    if meta['estado']!='recebida':
        return None
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            names=[i for i in archive.infolist() if i.filename.endswith('.csv')]
            if len(names)!=1 or names[0].file_size>30_000_000:
                return None
            return list(csv.DictReader(io.StringIO(archive.read(names[0]).decode('utf-8-sig')),delimiter=';'))
    except (zipfile.BadZipFile,UnicodeError):
        return None


def obrasgov(case, client, crosswalk):
    result=dict(rota='transferegov_obrasgov', status='identificador_insuficiente',
                consulta_especifica=False,identidade_confirmada=False,candidatos_historicos=[])
    instrument=str(case['fonte'].get('num. instrumento') or '').strip()
    # Only a plain agreement number or an explicit number/year; no concatenation.
    match=re.fullmatch(r'(\d{5,7})(?:/\d{4})?',instrument)
    if not match:
        return result
    if crosswalk is None:
        result['status']='crosswalk_indisponivel'
        return result
    result['consulta_especifica']=True
    matches=[r for r in crosswalk if r['nr_instrumento']==match[1]]
    ids=sorted({r['id_projeto_investimento'] for r in matches})
    result['crosswalk_matches']=matches
    if len(ids)!=1:
        result['status']='instrumento_sem_cipi' if not ids else 'identidade_ambigua'
        return result
    cipi=ids[0]
    data=client.json(OBRAS+'/projeto-investimento',dict(id_projeto_investimento=cipi))
    if not isinstance(data,dict) or len(data.get('data',[]))!=1:
        result['status']='projeto_indisponivel'
        return result
    project=data['data'][0]
    result['projeto']=project
    _,uf=location(case)
    # Crosswalk provides exact ID, object + UF corroborate. Similarity alone never accepts.
    identity=(project.get('id_projeto_investimento')==cipi and project.get('uf_principal')==uf and
              normalize(case['fonte'].get('empreendimento')) in
              (normalize(project.get('desc_nome')),normalize(project.get('desc_projeto'))))
    result['identidade_confirmada']=identity
    data=client.json(OBRAS+'/historico-situacao-cancelada-paralisada',
                     dict(id_projeto_investimento=cipi,tamanho_da_pagina=200,pagina=1))
    if not isinstance(data,dict):
        result['status']='historico_indisponivel'
        return result
    result['historico']=data
    if data.get('total_pages',1)>1:
        result['status']='historico_incompleto'
        return result
    candidates=historical_events([e for e in data.get('data',[]) if e.get('id_projeto_investimento')==cipi],case['data_base'])
    result['candidatos_historicos']=candidates if identity else []
    result['status']=('identidade_requer_revisao' if not identity else
                      'candidato_historico_requer_revisao' if candidates else 'identidade_confirmada_sem_causa')
    return result


def collect_case(case, client, crosswalk):
    start=time.monotonic()
    client.deadline=start+900
    client.attempts=[]
    routes=[]
    if case['base_de_dados']=='sismob':
        routes.append(sismob(case,client))
    elif case['base_de_dados']=='simec':
        _,uf=location(case)
        raw,meta=client.get('https://simec.mec.gov.br/painelObras/lista.php',dict(estuf=uf))
        # Detect barrier. Do not forge a request around CAPTCHA.
        captcha=b'recaptcha' in raw.lower()
        routes.append(dict(rota='simec',status='consulta_bloqueada_captcha' if captcha else 'formulario_sem_consulta_individual',
                           consulta_especifica=False,identificador_alvo=case['id_tcu'],
                           identidade_confirmada=False,candidatos_historicos=[]))
    routes.append(obrasgov(case,client,crosswalk))
    if len(routes)>2:
        raise ValueError('route_budget_exceeded')
    candidates=[candidate for route in routes for candidate in route['candidatos_historicos']]
    identity=any(r['identidade_confirmada'] for r in routes)
    status=('candidato_historico_requer_revisao' if candidates else
            'identidade_confirmada_sem_causa' if identity else routes[0]['status'])
    return dict(id_fato=case['id_fato'],id_tcu=case['id_tcu'],base_de_dados=case['base_de_dados'],
                coorte=case['coorte'],status=status,rotas=routes,tentativas=client.attempts,
                consulta_especifica=any(r['consulta_especifica'] for r in routes),
                identidade_confirmada=identity,candidatos_historicos=candidates,causa_homologada=False,
                label_risco=None,segundos=round(time.monotonic()-start,3),
                revisor='assistente:Codex',homologacao_humana=False)
