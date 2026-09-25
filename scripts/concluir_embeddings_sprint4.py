"""Prepara ou retoma corpus completo, preservando contratos limitados da feature008."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.database.connection import connect
from src.database.embedding_corpus import prepare_corpus, run_corpus


def main():
    p = argparse.ArgumentParser(description=__doc__)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument('--preparar', action='store_true')
    group.add_argument('--retomar', type=Path)
    p.add_argument('--device', choices=['cpu','cuda'])
    p.add_argument('--inference-batch', type=int)
    p.add_argument('--threads', type=int)
    p.add_argument('--write', action='store_true')
    args = p.parse_args()
    if args.retomar and any(v is not None for v in (args.device, args.inference_batch, args.threads)):
        p.error('retomada preserva configuracao congelada')
    if args.preparar and args.write:
        p.error('preparar somente congela a selecao; depois use --retomar --write')
    for value, maximum in ((args.inference_batch, 32), (args.threads, 16)):
        if value is not None and not 1 <= value <= maximum:
            p.error('batch/threads fora dos limites')
    with connect() as conn:
        conn.read_only = not args.write
        if args.preparar:
            path = Path('logs') / ('sprint4_corpus_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.json')
            manifest = prepare_corpus(conn, path, device=args.device or 'cpu',
                inference_batch=args.inference_batch or 2, threads=args.threads or 8)
            print(path, manifest['config']['total'], flush=True)
        else:
            manifest = json.loads(args.retomar.read_text(encoding='utf-8'))
            run_corpus(conn, manifest, args.retomar, write=args.write)


if __name__ == '__main__':
    main()
