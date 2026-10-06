"""Inventario e lotes atomicos de rotulagem com proveniencia no esquema existente."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json

from psycopg.rows import dict_row

from src.labeling.policy_v2 import (SCHEMA, VERSION, RULES, CLASSES, canonical, classify,
                                 fingerprint, policy_hash, provenance_errors, validate_review)
from src.database.schema import validate_schema

SELECT = '''SELECT f.id_fato,f.id_obra,f.ano_base,o.data_base,o.base_de_dados,o.id_tcu,
    o.situacao,o.situacao_origem,o.fonte,f.causa_paralisacao,f.exec_fisica,
    f.exec_financeira,f.valor_investimento,f.valor_desbloqueado,
    f.label_risco,f.origem_rotulo,f.status_rotulagem
    FROM tcc.fato_risco f JOIN tcc.dim_obra o USING(id_obra)'''


def read_rows(conn):
    with conn.cursor(row_factory=dict_row) as cur:
        return cur.execute(SELECT + ' ORDER BY f.id_fato').fetchall()


def audit_labels(conn):
    errors, distribution = [], Counter()
    for row in read_rows(conn):
        reasons = provenance_errors(row)
        method = ('invalido' if reasons else
                  json.loads(row['origem_rotulo'])['metodo'] if row['label_risco'] is not None else 'pendente')
        distribution[(row['ano_base'], row['base_de_dados'], row['label_risco'], method)] += 1
        if reasons:
            errors.append(dict(id_fato=row['id_fato'], motivos=reasons))
    return dict(valido=not errors, erros=errors, distribuicao=[
        dict(ano=year, base=base, label_risco=label, metodo=method, total=count)
        for (year, base, label, method), count in sorted(distribution.items(), key=lambda x: str(x[0]))])


def inventory(conn):
    rows = read_rows(conn)
    causes, states, years, decisions = Counter(), Counter(), Counter(), Counter()
    queue = []
    for row in rows:
        decision = classify(row)
        years[row['ano_base']] += 1
        causes[(row['ano_base'], row['base_de_dados'], row['causa_paralisacao'])] += 1
        states[(row['ano_base'], row['situacao'], row['situacao_origem'])] += 1
        decisions[(row['ano_base'], decision['label_risco'], decision['motivo'])] += 1
        if row['ano_base'] == 2025:
            queue.append(dict(id_fato=row['id_fato'], id_obra=row['id_obra'],
                              base_de_dados=row['base_de_dados'], id_tcu=row['id_tcu'],
                              data_base=str(row['data_base']), situacao=row['situacao'],
                              situacao_origem=row['situacao_origem'], causa_paralisacao=row['causa_paralisacao'],
                              snapshot_sha256=fingerprint(row), label_atual=row['label_risco'],
                              sugestao=decision))
    return dict(total=len(rows), por_ano=dict(years), classes=CLASSES,
                versao=VERSION, politica_sha256=policy_hash(), catalogo=RULES,
                causas=[dict(ano=y, base=b, causa=c, total=n) for (y,b,c),n in causes.items()],
                situacoes=[dict(ano=y, situacao=s, situacao_origem=o, total=n) for (y,s,o),n in states.items()],
                decisoes=[dict(ano=y, label_risco=l, motivo=m, total=n) for (y,l,m),n in decisions.items()],
                fila_2025=queue)


def preservation_fingerprints(conn):
    """Inclui os vetores. Exclui somente quatro campos autorizados da fato."""
    result = {}
    for table, key in [('dim_obra', 'id_obra'), ('fato_risco', 'id_fato'),
                       ('dim_documento', 'id_documento'), ('dim_embedding', 'id_embedding'),
                       ('ponte_documento_embedding', 'id_documento,id_fato,posicao_chunk')]:
        excluded = " - 'label_risco' - 'origem_rotulo' - 'status_rotulagem' - 'updated_at'" if table == 'fato_risco' else ''
        h = hashlib.sha256()
        with conn.cursor(name='sprint5_fingerprint') as cur:
            cur.itersize = 2048
            cur.execute(f'SELECT md5((to_jsonb(t){excluded})::text) FROM tcc.{table} t ORDER BY {key}')
            for row in cur:
                h.update(row[0].encode('ascii'))
        result[table] = h.hexdigest()
    return result


def _same_decision(existing, proposed):
    # Timestamp da execucao nao transforma reuso em nova escrita.
    return all(existing.get(k) == v for k,v in proposed.items() if k != 'executado_em')


def apply_labels(conn, *, write=False, reviews=None, executor='pipeline:sprint5', check_preservation=True):
    if not isinstance(executor, str) or not executor.strip():
        raise ValueError('executor_ausente')
    if reviews is not None:
        if not isinstance(reviews, list) or not reviews:
            raise ValueError('revisoes_exigem_lista_nao_vazia')
        ids = [r.get('id_fato') if isinstance(r, dict) else None for r in reviews]
        if any(type(i) is not int for i in ids) or len(ids) != len(set(ids)):
            raise ValueError('ids_revisao_invalidos_ou_duplicados')
        review_map = dict(zip(ids, reviews))
    else:
        review_map = None
    with conn.transaction():
        # NOWAIT evita aguardar indefinidamente carga/revisao concorrente.
        conn.execute('LOCK TABLE tcc.dim_obra,tcc.fato_risco IN SHARE ROW EXCLUSIVE MODE NOWAIT')
        if write and check_preservation:
            conn.execute('LOCK TABLE tcc.dim_documento,tcc.dim_embedding,tcc.ponte_documento_embedding IN SHARE MODE NOWAIT')
        validate_schema(conn)
        rows = read_rows(conn)
        if review_map is not None and set(review_map) - {r['id_fato'] for r in rows}:
            raise ValueError('id_fato_inexistente')
        before = preservation_fingerprints(conn) if write and check_preservation else None
        timestamp = datetime.now(timezone.utc).isoformat()
        changes, reused, reasons, decisions = [], 0, Counter(), []
        # Todas as revisoes/evidencias sao validadas antes do primeiro UPDATE.
        for row in rows:
            if review_map is not None and row['id_fato'] not in review_map:
                continue
            if provenance_errors(row):
                raise ValueError(f'rotulo_preexistente_invalido:{row["id_fato"]}')
            previous = json.loads(row['origem_rotulo']) if row['label_risco'] is not None else None
            if review_map is None and previous and previous['metodo'] == 'revisao':
                reused += 1
                continue
            decision = (validate_review(row, review_map[row['id_fato']])
                        if review_map is not None else classify(row))
            label = decision['label_risco']
            if label is None:
                reasons[decision['motivo']] += 1
                continue
            origin = dict(schema=SCHEMA, versao=VERSION, politica_sha256=policy_hash(),
                          snapshot_sha256=fingerprint(row), id_fato=row['id_fato'],
                          label_risco=label, metodo=('revisao' if review_map is not None else
                              'regra_situacao' if decision['regra'] == 'R00' else 'regra'),
                          regra=decision['regra'], executor=executor, executado_em=timestamp)
            if review_map is not None:
                origin['revisao'] = decision['revisao']
            if row['label_risco'] is not None:
                if (review_map is not None and previous['metodo'] == 'revisao'
                        and previous.get('revisao') == decision['revisao']
                        and previous['label_risco'] == label):
                    reused += 1
                    continue
                # Versao antiga auditada e mesma regra/classe: reuso, nao reescrita.
                if (review_map is None and previous['label_risco'] == label
                        and previous['regra'] == decision['regra']):
                    reused += 1
                    continue
                if not _same_decision(previous, origin):
                    raise ValueError(f'decisao_divergente_sem_sobrescrita:{row["id_fato"]}')
                reused += 1
            else:
                changes.append((label, canonical(origin), row['id_fato']))
                decisions.append(origin)
        if write and changes:
            with conn.cursor() as cur:
                cur.executemany('''UPDATE tcc.fato_risco SET label_risco=%s,origem_rotulo=%s,
                    status_rotulagem='ROTULADO',updated_at=now() WHERE id_fato=%s''', changes)
        after = preservation_fingerprints(conn) if before is not None else None
        if before != after:
            raise ValueError('conteudo_nao_autorizado_alterado_rollback')
        audit = audit_labels(conn)
        if not audit['valido']:
            raise ValueError('auditoria_rotulagem_falhou_rollback')
        result = dict(modo='aplicacao' if write else 'simulacao',
                      examinados=len(rows) if review_map is None else len(review_map),
                      propostos=len(changes), atualizados=len(changes) if write else 0,
                      reutilizados=reused, motivos_sem_atribuicao=dict(reasons),
                      decisoes_novas=decisions, auditoria=audit,
                      fingerprints_antes=before, fingerprints_depois=after,
                      preservacao_verificada=before is not None and before == after)
    # Retorno somente apos commit; se checkpoint falhar, reexecucao consulta banco.
    return result
