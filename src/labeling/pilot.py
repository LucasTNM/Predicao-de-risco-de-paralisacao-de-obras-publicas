"""Bounded causal recovery pilot; no database mutations or inferred labels."""
from collections import Counter, defaultdict
import hashlib
from pathlib import Path
import random

from src.labeling.policy import canonical, digest, fingerprint, in_scope, normalize
from src.labeling.recovery import eligible, recovery_report

QUOTAS = {'sismob': 24, 'simec': 16, 'funasa': 5, 'dnit': 5, 'caixa': 4,
          'sesu': 2, 'setec': 2, 'simec-outros': 1, 'midr': 1}


def select_cases(rows, legacy_ids, quotas=None, seed=42):
    quotas = QUOTAS if quotas is None else quotas
    if len({r['id_fato'] for r in rows}) != len(rows):
        raise ValueError('duplicate_fact')
    if not legacy_ids <= {r['id_fato'] for r in rows}:
        raise ValueError('missing_legacy')
    selected = [dict(r, coorte='legado') for r in rows if r['id_fato'] in legacy_ids]
    rng = random.Random(seed)
    for base, count in sorted(quotas.items()):
        groups = defaultdict(list)
        for row in sorted(rows, key=lambda r: (r['id_tcu'], r['id_fato'])):
            if row['base_de_dados'] == base and row['id_fato'] not in legacy_ids:
                groups[row.get('situacao_origem') or 'NAO_INFORMADA'].append(row)
        if sum(map(len, groups.values())) < count:
            raise ValueError(f'insufficient_population:{base}')
        # Round-robin shuffled strata gives rare administrative states a chance.
        # This is a feasibility sample, not a proportional prevalence estimator.
        names = sorted(groups)
        rng.shuffle(names)
        for group in groups.values():
            rng.shuffle(group)
        while count:
            for name in names:
                if groups[name] and count:
                    selected.append(dict(groups[name].pop(), coorte='novo'))
                    count -= 1
    return sorted(selected, key=lambda r: (r['coorte'], r['base_de_dados'], r['id_tcu'], r['id_fato']))


def split_identity(base, identity):
    key = f'42|{base}|{identity}'.encode('utf-8')
    return 'reserva_avaliacao' if int(hashlib.sha256(key).hexdigest(), 16) % 5 == 0 else 'desenvolvimento'


def prepare(conn):
    from src.database.labeling import read_rows, audit_labels
    rows = read_rows(conn)
    recovery = recovery_report(conn)
    recovered = {r['id_fato']: r for r in recovery['obras']}
    candidates = []
    legacy_ids = set()
    for row in rows:
        if not eligible(row) or row['label_risco'] is not None:
            continue
        record = dict(row, **{k: recovered[row['id_fato']][k]
                            for k in ('documentos', 'trechos_candidatos', 'encaminhamento')})
        record['snapshot_sha256'] = fingerprint(row)
        candidates.append(record)
        if any(d['origem_documento'] in ('original', 'nao_confirmada') for d in record['documentos']):
            legacy_ids.add(row['id_fato'])
    cases = select_cases(candidates, legacy_ids)
    if len(legacy_ids) != 22 or len(cases) != 82:
        raise ValueError('population_changed_reassess_pilot')
    manifest = dict(schema='recuperacao-piloto/v1', seed=42, quotas=QUOTAS,
                    population_sha256=digest([fingerprint(r) for r in sorted(rows, key=lambda x:x['id_fato'])]),
                    legacy_count=22, new_count=60, casos=cases)
    return manifest, rows, audit_labels(conn)


def audit_legacy(cases, text_root):
    records = []
    for case in cases:
        if case['coorte'] != 'legado':
            continue
        docs = []
        for doc in case['documentos']:
            path = Path(text_root) / doc['caminho_txt_relativo']
            entry = dict(id_documento=doc['id_documento'], caminho=str(path),
                         origem=doc['origem_documento'], sha256_esperado=doc['sha256_txt'],
                         status='quarentena_identidade_nao_confirmada',
                         motivo='Vinculo legado derivado de sequencia local; requer verificacao independente.')
            if path.is_file():
                raw = path.read_bytes()
                entry['sha256_lido'] = hashlib.sha256(raw).hexdigest()
                # Canonical chunks use LF; preserve raw and canonical hashes.
                text = raw.decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n')
                entry['sha256_canonico'] = hashlib.sha256(text.encode('utf-8')).hexdigest()
                entry['texto_integral'] = text
                entry['trecho_identidade'] = text[:2000]
                entry['hash_confere'] = doc['sha256_txt'] in (entry['sha256_lido'], entry['sha256_canonico'])
                if not entry['hash_confere']:
                    entry['status'] = 'quarentena_hash_divergente'
            else:
                entry['status'] = 'arquivo_indisponivel'
            docs.append(entry)
        records.append(dict(id_fato=case['id_fato'], id_tcu=case['id_tcu'],
                            fonte=case['fonte'], documentos=docs,
                            revisor='assistente:Codex', homologacao_humana=False,
                            label_risco=None))
    return records


def dataset_registry(rows):
    return [dict(id_fato=r['id_fato'], id_tcu=r['id_tcu'], base=r['base_de_dados'],
                 data_base=str(r['data_base']), situacao=r['situacao'],
                 situacao_origem=r['situacao_origem'], label_risco=r['label_risco'],
                 motivo_pendencia=('sem_causa_utilizavel' if eligible(r) else 'causa_ou_situacao_requer_revisao')
                    if r['label_risco'] is None else None,
                 particao=split_identity(r['base_de_dados'],r['id_tcu']),
                 gold_homologado=False, snapshot_sha256=fingerprint(r))
            for r in rows if in_scope(r)]


def summarize(results):
    groups = defaultdict(list)
    for result in results:
        groups[(result['coorte'],result['base_de_dados'])].append(result)
    report = []
    for (cohort,base), items in sorted(groups.items()):
        identities = sum(r.get('identidade_confirmada',False) for r in items)
        causal = sum(r.get('causa_homologada',False) for r in items)
        attempted = sum(r.get('consulta_especifica',False) for r in items)
        decision = ('quarentena_sem_extrapolar_ao_corpus' if cohort=='legado' else
                    'avaliar_segundo_lote' if attempted>=10 and causal/attempted>=0.2
                    else 'diagnostico_adicional_amostra_pequena' if attempted<10
                    else 'nao_expandir_rota_sem_evidencia_causal')
        report.append(dict(coorte=cohort, base=base, casos=len(items), consultas_especificas=attempted,
                           identidades_confirmadas=identities, causas_homologadas=causal,
                           candidatos_historicos=sum(len(r.get('candidatos_historicos',[])) for r in items),
                           estados=dict(Counter(r['status'] for r in items)), decisao=decision,
                           segundos_processamento=round(sum(r.get('segundos',0) for r in items),3),
                           tempo_revisao_manual='nao_cronometrado'))
    return dict(total=len(results), grupos=report, rotulos_atribuidos=0,
                aviso='Taxas de viabilidade, nao estimativas populacionais; legado e novo separados.')


def apply_identity_reviews(results, audits, reviews):
    """Apply declared identity reviews to reports only, with verifiable excerpts."""
    import copy
    results, audits = copy.deepcopy(results), copy.deepcopy(audits)
    indexed = {r['id_fato']: r for r in results}
    legacy = {r['id_fato']: r for r in audits}
    seen = set()
    for review in reviews:
        fact = review['id_fato']
        if fact in seen or fact not in indexed:
            raise ValueError('review_identity_invalid')
        seen.add(fact)
        if not review.get('revisor') or not review.get('justificativa'):
            raise ValueError('review_author_missing')
        result = indexed[fact]
        evidence = review.get('evidencias',[])
        if not evidence:
            raise ValueError('review_evidence_missing')
        if result['coorte']=='legado':
            docs={d['id_documento']:d for d in legacy[fact]['documentos']}
            if {e['id_documento'] for e in evidence} != set(docs):
                raise ValueError('review_documents_incomplete')
            for item in evidence:
                doc=docs[item['id_documento']]
                if not doc.get('hash_confere') or item['sha256']!=doc['sha256_esperado']:
                    raise ValueError('review_hash_divergent')
                if not item.get('trecho') or item['trecho'] not in doc['texto_integral']:
                    raise ValueError('review_excerpt_missing')
                # Recheck original file, not just the exported text.
                raw=Path(doc['caminho']).read_bytes()
                text=raw.decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n')
                hashes=(hashlib.sha256(raw).hexdigest(),hashlib.sha256(text.encode('utf-8')).hexdigest())
                if item['sha256'] not in hashes or item['trecho'] not in text:
                    raise ValueError('review_original_changed')
                doc.update(status='quarentena_vinculo_incompativel', revisao=review['justificativa'],
                           trecho_decisao=item['trecho'], revisor=review['revisor'])
            result['status']='quarentena_vinculo_incompativel'
        else:
            for item in evidence:
                if not any(t['arquivo']==item['caminho'] and t['sha256']==item['sha256']
                           for t in result['tentativas']):
                    raise ValueError('review_response_not_in_case')
                raw=Path(item['caminho']).read_bytes()
                if hashlib.sha256(raw).hexdigest()!=item['sha256']:
                    raise ValueError('review_response_changed')
                if not item.get('trecho') or item['trecho'] not in raw.decode('utf-8'):
                    raise ValueError('review_excerpt_missing')
            if review.get('decisao')!='identidade_confirmada':
                raise ValueError('unsupported_identity_review')
            result['identidade_confirmada']=True
            result['status']='identidade_confirmada_sem_causa'
        result['revisao_identidade']=review
    return results,audits
