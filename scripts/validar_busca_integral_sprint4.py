"""Autocorrespondencia, isolamento de filtros e latencia; nao simula revisao humana."""
import argparse
import json
from pathlib import Path
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.database.connection import connect
from src.database.run_load import save_report
from src.database.vector_search import search_embeddings
from src.embedding_model import MODEL, REVISION, load_model
from scripts.buscar_embeddings_sprint4 import query_text


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--device', choices=['cpu','cuda'], default='cpu')
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    report = dict(modo='exato', homologacao_humana=False, autocorrespondencia=[], consultas=[])
    durations = []
    with connect() as conn:
        conn.read_only = True
        model = load_model(args.device)
        rows = conn.execute('''WITH candidates AS (
          SELECT DISTINCT e.id_embedding,e.chave_conteudo,d.ano_base,d.origem_documento
          FROM tcc.dim_embedding e JOIN tcc.ponte_documento_embedding p USING(id_embedding)
          JOIN tcc.dim_documento d USING(id_documento) WHERE e.embedding IS NOT NULL),
          ranked AS (SELECT *,row_number() OVER(PARTITION BY ano_base,origem_documento
                     ORDER BY md5(chave_conteudo),id_embedding) rn FROM candidates)
          SELECT id_embedding,ano_base,origem_documento FROM ranked WHERE rn<=2
          ORDER BY ano_base,origem_documento,id_embedding''').fetchall()
        for identity, year, origin in rows:
            vector_text, content = conn.execute('SELECT embedding::text,conteudo_chunk FROM tcc.dim_embedding WHERE id_embedding=%s', (identity,)).fetchone()
            vector = json.loads(vector_text)
            started = time.monotonic()
            results = search_embeddings(conn, vector, model=MODEL, revision=REVISION, year=year, origin=origin)
            elapsed = time.monotonic()-started
            durations.append(elapsed)
            isolated = all(o['ano']==year and o['origem']==origin for r in results for o in r['ocorrencias'])
            textual = query_text(conn, model, content, year=year, origin=origin)
            textual_hits = textual['resultados']
            textual_present = identity in [r['id_embedding'] for r in textual_hits]
            textual_isolated = all(o['ano']==year and o['origem']==origin for r in textual_hits for o in r['ocorrencias'])
            durations.append(textual['busca_segundos'])
            report['autocorrespondencia'].append(dict(id_embedding=identity, ano=year, origem=origin,
                presente_no_top5=identity in [r['id_embedding'] for r in results],
                distancia_min=results[0]['distancia'] if results else None,
                texto_presente_no_top5=textual_present,
                texto_distancia_min=textual_hits[0]['distancia'] if textual_hits else None,
                texto_busca_segundos=textual['busca_segundos'],
                texto_filtros_corretos=textual_isolated,
                valido=bool(results and abs(results[0]['distancia'])<=1e-5 and isolated and textual_present
                            and textual_isolated and abs(textual_hits[0]['distancia'])<=1e-5),
                filtros_corretos=isolated, segundos=elapsed, ids=[r['id_embedding'] for r in results]))
        for year in (2025,2026):
            for text in ('Atraso da obra por falta de recursos financeiros e pagamentos.',
                         'Falhas tecnicas na execucao da obra e no projeto.',
                         'Construcao de escolas e creches publicas.'):
                result = query_text(conn, model, text, year=year)
                durations.append(result['busca_segundos'])
                report['consultas'].append(result)
        for origin in ('original','ficha_sintetica','nao_confirmada'):
            result = query_text(conn, model, 'Obra publica', year=2025, origin=origin)
            report['consultas'].append(result)
            durations.append(result['busca_segundos'])
        report['valido'] = bool(rows) and all(r['valido'] for r in report['autocorrespondencia']) and all(
            all(o['ano']==r['ano'] and (r['origem'] is None or o['origem']==r['origem'])
                for hit in r['resultados'] for o in hit['ocorrencias']) for r in report['consultas'])
        report['latencia_mediana_segundos'] = statistics.median(durations)
        report['latencia_p95_segundos'] = sorted(durations)[min(len(durations)-1, int(len(durations)*0.95))]
        report['decisao_indice'] = 'manter_busca_exata' if report['latencia_mediana_segundos']<=5 else 'investigar_otimizacao'
        report['nota'] = 'Autocorrespondencia admite empate numerico entre vetores; nao mede relevancia humana nem recall semantico.'
    save_report(args.output, report)
    print(json.dumps({k:v for k,v in report.items() if k not in ('consultas','autocorrespondencia')}, ensure_ascii=False))
    return 0 if report['valido'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
