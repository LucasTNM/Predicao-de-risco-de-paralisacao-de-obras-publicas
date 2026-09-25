"""Consulta textual por cosseno no PostgreSQL, com filtros e proveniencia."""
import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.database.connection import connect
from src.database.vector_search import search_embeddings
from src.embedding_model import MODEL, REVISION, load_model, encode_checked


def query_text(conn, model, text, *, k=5, year=None, origin=None):
    started = time.monotonic()
    vectors, lengths = encode_checked(model, [text], batch_size=1)
    inference = time.monotonic()-started
    started = time.monotonic()
    results = search_embeddings(conn, vectors[0], model=MODEL, revision=REVISION, k=k, year=year, origin=origin)
    return dict(consulta=text, ano=year, origem=origin, k=k, modelo=MODEL, revisao=REVISION,
                tokens=lengths[0], inferencia_segundos=inference, busca_segundos=time.monotonic()-started,
                resultados=results)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--consulta', required=True)
    p.add_argument('--ano', type=int, choices=[2025,2026])
    p.add_argument('--origem', choices=['original','ficha_sintetica','nao_confirmada'])
    p.add_argument('--k', type=int, default=5)
    p.add_argument('--device', choices=['cpu','cuda'], default='cpu')
    args = p.parse_args()
    if not args.consulta.strip() or not 1 <= args.k <= 100:
        p.error('consulta vazia ou k fora de 1..100')
    model = load_model(args.device)
    with connect() as conn:
        conn.read_only = True
        result = query_text(conn, model, args.consulta, k=args.k, year=args.ano, origin=args.origem)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
