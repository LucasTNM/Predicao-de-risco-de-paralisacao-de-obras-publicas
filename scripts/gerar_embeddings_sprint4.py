"""Gera ate 512 vetores por execucao; --write habilita commits por lote."""
import argparse
import json
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.database.connection import connect
from src.database.embedding_run import make_manifest, run_batches


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--limite', type=int)
    group.add_argument('--retomar', type=Path)
    parser.add_argument('--ano', type=int, choices=[2025, 2026])
    parser.add_argument('--origem', choices=['original', 'ficha_sintetica', 'nao_confirmada'])
    parser.add_argument('--batch-size', type=int)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    if args.retomar and any(x is not None for x in (args.ano, args.origem, args.batch_size)):
        parser.error('retomada usa a configuracao congelada')
    if args.limite is not None and not 1 <= args.limite <= 512:
        parser.error('limite deve ser 1..512')
    if args.batch_size is not None and not 1 <= args.batch_size <= 32:
        parser.error('batch-size deve ser 1..32')
    with connect() as conn:
        conn.read_only = not args.write
        if args.retomar:
            path = args.retomar
            manifest = json.loads(path.read_text(encoding='utf-8'))
        else:
            rows = conn.execute('''SELECT e.id_embedding,e.chave_conteudo,e.chunk_config
                FROM tcc.dim_embedding e WHERE e.embedding IS NULL AND EXISTS (
                SELECT 1 FROM tcc.ponte_documento_embedding p JOIN tcc.dim_documento d USING(id_documento)
                WHERE p.id_embedding=e.id_embedding AND (%s::int IS NULL OR d.ano_base=%s)
                AND (%s::text IS NULL OR d.origem_documento=%s))
                ORDER BY e.id_embedding LIMIT %s''',
                (args.ano, args.ano, args.origem, args.origem, args.limite)).fetchall()
            if not rows:
                print('Nenhum fragmento pendente para os filtros.')
                return
            manifest = make_manifest([dict(zip(['id_embedding','chave_conteudo','chunk_config'], row)) for row in rows],
                year=args.ano, origin=args.origem, batch_size=args.batch_size or 8)
            path = Path('logs') / ('sprint4_lotes_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.json')
        print(str(path), flush=True)
        run_batches(conn, manifest, path, write=args.write)
        print(manifest['status'], len(manifest['items']), flush=True)


if __name__ == '__main__':
    main()
