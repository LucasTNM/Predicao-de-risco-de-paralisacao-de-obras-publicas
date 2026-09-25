"""Busca exata e pacote local de revisao; nunca altera dados nem homologa relevancia."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import LOGS_DIR
from src.database.connection import connect
from src.database.run_load import save_report
from src.database.vector_search import search_embeddings, retrieval_metrics
from src.embedding_model import MODEL, REVISION, CODE_REVISION, load_model, encode_checked

QUERIES = [
    'Quais documentos tratam de falta de recursos ou atraso de pagamentos da obra?',
    'Quais documentos tratam de falhas de projeto e problemas tecnicos na execucao?',
    'Quais documentos tratam de abandono da obra ou descumprimento pela contratada?',
    'Quais documentos descrevem prazos e condicoes de execucao de obras rodoviarias?',
    'Quais documentos descrevem construcao ou reforma de unidades de saude?',
    'Quais documentos descrevem obras em escolas ou creches?',
]


def score_review(review, *, corpus_hash, universe, queries, rankings, k):
    if review.get('tipo_revisao') not in ('humana', 'assistida_ia'):
        raise ValueError('tipo de revisao deve ser explicito')
    if review.get('corpus_sha256') != corpus_hash:
        raise ValueError('universo de revisao mudou')
    items = review.get('consultas', [])
    if len(items) != len(queries):
        raise ValueError('consultas da revisao divergentes')
    scores = []
    for item, query, ranked in zip(items, queries, rankings, strict=True):
        if (item.get('consulta') != query or not str(item.get('revisado_por') or '').strip()
                or item.get('universo_revisado_integralmente') is not True):
            raise ValueError('revisao integral pendente')
        relevant = item.get('relevantes')
        if (not isinstance(relevant, list) or any(type(i) is not int for i in relevant)
                or len(set(relevant)) != len(relevant) or not set(relevant) <= set(universe)):
            raise ValueError('relevantes invalidos')
        scores.append(retrieval_metrics(ranked, relevant, k) if relevant else
                      {'precision_at_k': 0.0, 'recall_at_k': None,
                       'reciprocal_rank_at_k': 0.0, 'sem_relevante_no_piloto': True})
    return scores


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--consulta')
    parser.add_argument('--ano', type=int, choices=(2025, 2026), default=2025)
    parser.add_argument('--origem', choices=('original', 'ficha_sintetica', 'nao_confirmada'))
    parser.add_argument('--k', type=int, default=5)
    parser.add_argument('--julgamentos', type=Path)
    args = parser.parse_args()
    if not 1 <= args.k <= 100:
        parser.error('--k deve estar entre 1 e 100')
    queries = [args.consulta] if args.consulta else QUERIES
    tag = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    path = LOGS_DIR / f'sprint4_busca_{tag}.json'
    packet_path = LOGS_DIR / f'sprint4_revisao_{tag}.json'
    report = dict(status='EM_EXECUCAO', modelo=MODEL, revisao=REVISION,
        revisao_codigo=CODE_REVISION, ano=args.ano, origem=args.origem, k=args.k,
        inicio=datetime.now().astimezone().isoformat(), consultas=[])
    save_report(path, report)
    try:
        started = time.perf_counter()
        model = load_model()
        report['segundos_carregamento_modelo'] = time.perf_counter()-started
        started = time.perf_counter()
        vectors, lengths = encode_checked(model, queries)
        report['segundos_embedding_consultas'] = time.perf_counter()-started
        with connect() as conn:
            conn.read_only = True
            with conn.transaction():
                conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
                universe = conn.execute('''SELECT e.id_embedding,e.chave_conteudo,e.conteudo_chunk
                    FROM tcc.dim_embedding e WHERE embedding IS NOT NULL
                    AND modelo_embedding=%s AND revisao_embedding=%s
                    AND EXISTS (SELECT 1 FROM tcc.ponte_documento_embedding p
                        JOIN tcc.dim_documento d USING(id_documento)
                        WHERE p.id_embedding=e.id_embedding AND d.ano_base=%s
                        AND (%s::text IS NULL OR d.origem_documento=%s)) ORDER BY e.id_embedding''',
                    (MODEL, REVISION, args.ano, args.origem, args.origem)).fetchall()
                if not universe:
                    raise ValueError('nenhum vetor compativel no recorte')
                signature = [MODEL, REVISION, args.ano, args.origem,
                             [(row[0], row[1]) for row in universe]]
                corpus_hash = hashlib.sha256(json.dumps(signature).encode()).hexdigest()
                report['corpus_sha256'] = corpus_hash
                report['universo_vetorizado'] = len(universe)
                size = conn.execute('''SELECT count(*),count(embedding),
                    coalesce(avg(pg_column_size(embedding)),0)::float8,
                    pg_total_relation_size('tcc.dim_embedding') FROM tcc.dim_embedding''').fetchone()
                report['armazenamento'] = dict(zip(('chunks_total', 'vetores_total',
                    'bytes_medios_vetor', 'bytes_relacao_com_indices_toast'), size))
                report['armazenamento']['projecao_bytes_vetores_sem_overhead'] = size[0]*3080
                timings, rankings, review_queries = [], [], []
                for query, vector, length in zip(queries, vectors, lengths, strict=True):
                    started = time.perf_counter()
                    results = search_embeddings(conn, vector, model=MODEL, revision=REVISION,
                        k=args.k, year=args.ano, origin=args.origem)
                    elapsed = time.perf_counter()-started
                    timings.append(elapsed)
                    rankings.append([r['id_embedding'] for r in results])
                    report['consultas'].append(dict(consulta=query, tokens=length,
                        segundos_busca=elapsed, resultados=[{key: value for key, value in r.items()
                            if key != 'conteudo_chunk'} for r in results]))
                    review_queries.append(dict(consulta=query, revisado_por=None,
                        universo_revisado_integralmente=False, relevantes=None, resultados=results))
                report['latencia_mediana_ms'] = statistics.median(timings)*1000
                report['latencia_max_ms'] = max(timings)*1000
                # Plano local sem literal do vetor no relatorio.
                literal = '[' + ','.join(map(str, vectors[0])) + ']'
                plan = conn.execute('''EXPLAIN (ANALYZE, FORMAT JSON)
                    WITH candidates AS MATERIALIZED (SELECT embedding FROM tcc.dim_embedding e
                    WHERE embedding IS NOT NULL AND modelo_embedding=%s AND revisao_embedding=%s
                    AND EXISTS (SELECT 1 FROM tcc.ponte_documento_embedding p
                      JOIN tcc.dim_documento d USING(id_documento)
                      WHERE p.id_embedding=e.id_embedding AND d.ano_base=%s
                      AND (%s::text IS NULL OR d.origem_documento=%s)))
                    SELECT embedding <=> %s::vector AS distance FROM candidates
                    ORDER BY distance LIMIT %s''',
                    (MODEL, REVISION, args.ano, args.origem, args.origem, literal, args.k)).fetchone()[0][0]
                report['plano_execucao_ms'] = plan['Execution Time']
        save_report(packet_path, dict(corpus_sha256=corpus_hash, modelo=MODEL, revisao=REVISION,
            tipo_revisao=None,
            aviso='Revisar todo o universo local. Relevancia de busca nao e label_risco.',
            universo=[dict(id_embedding=r[0], chave_conteudo=r[1], conteudo_chunk=r[2]) for r in universe],
            consultas=review_queries))
        report['pacote_revisao_local'] = str(packet_path)
        if args.julgamentos:
            review = json.loads(args.julgamentos.read_text(encoding='utf-8'))
            report['metricas'] = score_review(review, corpus_hash=corpus_hash,
                universe=[r[0] for r in universe], queries=queries, rankings=rankings, k=args.k)
            report['julgamentos_sha256'] = hashlib.sha256(args.julgamentos.read_bytes()).hexdigest()
            report['tipo_revisao'] = review['tipo_revisao']
            report['status'] = ('AVALIADO_ASSISTIDO_IA' if review['tipo_revisao'] == 'assistida_ia'
                                else 'AVALIADO_COM_JULGAMENTOS')
        else:
            report['status'] = 'AGUARDANDO_REVISAO_SEMANTICA'
        report['decisao'] = 'Manter piloto e busca exata; este script nao autoriza carga integral ou HNSW.'
        report['fim'] = datetime.now().astimezone().isoformat()
        save_report(path, report)
        print(json.dumps(dict(relatorio=str(path), status=report['status'],
            universo=len(universe), latencia_mediana_ms=report['latencia_mediana_ms']), ensure_ascii=False))
        return 0
    except BaseException as exc:
        report.update(status='INTERROMPIDO', erro_fatal=type(exc).__name__)
        save_report(path, report)
        raise


if __name__ == '__main__':
    raise SystemExit(main())
