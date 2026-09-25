"""Auditoria readonly de integridade, cobertura, fingerprints e reproducao numerica."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.database.connection import connect
from src.database.run_load import save_report
from src.database.validation import validate_data
from src.database.schema import TABLES
from src.embedding_model import MODEL, REVISION, CODE_REVISION, load_model, encode_checked


def fingerprints(conn):
    result = {}
    for table, key in [('dim_obra','id_obra'), ('fato_risco','id_fato'),
                       ('dim_documento','id_documento'), ('dim_embedding','id_embedding'),
                       ('ponte_documento_embedding','id_documento,id_fato,posicao_chunk')]:
        excluded = " - 'embedding' - 'modelo_embedding' - 'revisao_embedding'" if table == 'dim_embedding' else ''
        h = hashlib.sha256()
        with conn.transaction(), conn.cursor(name='fingerprint') as cur:
            cur.itersize = 2048
            cur.execute(f'SELECT md5((to_jsonb(t){excluded})::text) FROM tcc.{table} t ORDER BY {key}')
            for row in cur:
                h.update(row[0].encode())
        result[table] = h.hexdigest()
    return result


def vector_stats(conn):
    row = conn.execute('''SELECT count(*),count(embedding),
        count(*) FILTER (WHERE embedding IS NOT NULL AND (
          modelo_embedding IS DISTINCT FROM %s OR revisao_embedding IS DISTINCT FROM %s
          OR vector_dims(embedding)<>768 OR vector_norm(embedding) NOT BETWEEN 0.99 AND 1.01)),
        min(vector_norm(embedding)),max(vector_norm(embedding)) FROM tcc.dim_embedding''', (MODEL, REVISION)).fetchone()
    return dict(total=row[0], preenchidos=row[1], pendentes=row[0]-row[1], invalidos=row[2], norma_min=row[3], norma_max=row[4])


def compare_baseline(report, baseline):
    if not baseline.get('valido') or set(baseline.get('fingerprints', {})) != TABLES:
        raise ValueError('baseline_incompleto_ou_reprovado')
    if any(baseline.get(key) != report.get(key) for key in ('modelo','revisao','revisao_codigo')):
        raise ValueError('baseline_de_outro_modelo')
    changed = sorted(table for table in TABLES if report['fingerprints'].get(table) != baseline['fingerprints'][table])
    counts_match = report['integridade']['contagens'] == baseline['integridade']['contagens']
    return dict(valido=not changed and counts_match, tabelas_alteradas=changed, contagens_preservadas=counts_match)


def compare_vectors(expected, actual):
    import numpy as np
    a, b = np.asarray(expected, dtype=float), np.asarray(actual, dtype=float)
    cosine = float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))
    error = float(np.max(np.abs(a-b)))
    return dict(cosine=cosine, erro_max=error, valido=bool(cosine >= 0.99999 and error <= 0.0001))


def reproduction_rows(conn, sample=None, stratified=False):
    if not stratified:
        return conn.execute('''SELECT id_embedding,conteudo_chunk,embedding::text
            FROM tcc.dim_embedding WHERE embedding IS NOT NULL ORDER BY md5(chave_conteudo),id_embedding
            LIMIT %s''', (sample,)).fetchall()
    if sample is None or sample < 1:
        raise ValueError('amostragem_estratificada_exige_limite')
    strata = conn.execute('''WITH candidates AS (
        SELECT DISTINCT e.id_embedding,e.chave_conteudo,d.ano_base,d.origem_documento,
          CASE WHEN e.num_tokens<=128 THEN 1 WHEN e.num_tokens<=256 THEN 2
               WHEN e.num_tokens<=384 THEN 3 ELSE 4 END faixa
        FROM tcc.dim_embedding e JOIN tcc.ponte_documento_embedding p USING(id_embedding)
        JOIN tcc.dim_documento d USING(id_documento) WHERE e.embedding IS NOT NULL),
        ranked AS (SELECT *,row_number() OVER(PARTITION BY ano_base,origem_documento,faixa
                   ORDER BY md5(chave_conteudo),id_embedding) rn FROM candidates)
        SELECT DISTINCT id_embedding FROM ranked WHERE rn<=2 ORDER BY id_embedding''').fetchall()
    extremes = conn.execute('''SELECT id_embedding FROM tcc.dim_embedding WHERE embedding IS NOT NULL
        ORDER BY length(conteudo_chunk) DESC,id_embedding LIMIT 8''').fetchall()
    ids = sorted({row[0] for row in strata+extremes})
    if len(ids) > sample:
        raise ValueError('limite_insuficiente_para_todos_estratos_e_extremos')
    fill = conn.execute('''SELECT id_embedding FROM tcc.dim_embedding WHERE embedding IS NOT NULL
        AND NOT (id_embedding=ANY(%s)) ORDER BY md5(chave_conteudo),id_embedding LIMIT %s''',
        (ids, sample-len(ids))).fetchall()
    ids.extend(row[0] for row in fill)
    return conn.execute('''SELECT id_embedding,conteudo_chunk,embedding::text FROM tcc.dim_embedding
        WHERE id_embedding=ANY(%s) ORDER BY id_embedding''', (ids,)).fetchall()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recompute', action='store_true')
    parser.add_argument('--sample', type=int)
    parser.add_argument('--stratified', action='store_true')
    parser.add_argument('--device', choices=['cpu','cuda'], default='cpu')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--baseline', type=Path)
    args = parser.parse_args()
    if args.sample is not None and args.sample < 1:
        parser.error('sample deve ser positivo')
    if args.stratified and (not args.recompute or args.sample is None):
        parser.error('stratified exige recompute e sample')
    start = time.monotonic()
    report = dict(modelo=MODEL, revisao=REVISION, revisao_codigo=CODE_REVISION, device=args.device)
    with connect() as conn:
        conn.read_only = True
        report['integridade'] = validate_data(conn)
        report['vetores'] = vector_stats(conn)
        report['fingerprints'] = fingerprints(conn)
        save_report(args.output, report)
        print(json.dumps(report['vetores']), flush=True)
        if args.recompute:
            rows = reproduction_rows(conn, args.sample, args.stratified)
            report['amostragem_reproducao'] = ('ano_origem_faixa_bertimbau_extremos_textuais' if args.stratified
                                               else 'integral' if args.sample is None else 'hash_deterministico')
            model = load_model(args.device)
            checks = []
            for start_idx in range(0, len(rows), 8):
                batch = rows[start_idx:start_idx+8]
                values, lengths = encode_checked(model, [r[1] for r in batch], batch_size=2)
                checks.extend(dict(id_embedding=r[0], tokens=n, **compare_vectors(json.loads(r[2]), v))
                              for r, v, n in zip(batch, values, lengths))
            report['reproducao'] = checks
            report['reproducao_valida'] = all(c['valido'] for c in checks)
    report['duracao_segundos'] = time.monotonic()-start
    report['valido'] = report['integridade']['valido'] and report['vetores']['invalidos'] == 0 and report.get('reproducao_valida', True)
    if args.baseline:
        baseline = json.loads(args.baseline.read_text(encoding='utf-8'))
        report['comparacao_baseline'] = compare_baseline(report, baseline)
        report['valido'] = report['valido'] and report['comparacao_baseline']['valido']
    save_report(args.output, report)
    print(json.dumps({k: v for k, v in report.items() if k not in ('reproducao','integridade')}), flush=True)
    return 0 if report['valido'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
