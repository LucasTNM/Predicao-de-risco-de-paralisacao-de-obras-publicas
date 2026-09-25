"""Audita o comprimento E5 dos chunks canônicos sem alterar o banco.

O relatório é um checkpoint local, não uma autorização automática para gerar
embeddings. Nenhum texto do corpus é incluído no JSON publicado.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import LOGS_DIR  # noqa: E402
from src.database.connection import connect  # noqa: E402
from src.database.run_load import save_report  # noqa: E402

CANDIDATES = {
    'e5': ('intfloat/multilingual-e5-base',
           'd128750597153bb5987e10b1c3493a34e5a4502a', 'passage: ', 512),
    'gte': ('Alibaba-NLP/gte-multilingual-base',
            '9bbca17d9273fd0d03d5725c7a4b0f6b45142062', '', 8192),
}
BATCH = 256


def quantile(values: list[int], fraction: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[int((len(ordered) - 1) * fraction)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit', type=int, help='Limite apenas para diagnostico; nao conclui o gate.')
    parser.add_argument('--candidato', choices=tuple(CANDIDATES), default='e5')
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error('--limit deve ser positivo')

    import tokenizers
    import transformers
    from transformers import AutoTokenizer

    model, revision, prefix, token_limit = CANDIDATES[args.candidato]
    tokenizer = AutoTokenizer.from_pretrained(model, revision=revision, use_fast=True,
                                              trust_remote_code=False)
    if args.candidato == 'e5' and tokenizer.model_max_length != token_limit:
        raise RuntimeError(f'Janela inesperada do tokenizer: {tokenizer.model_max_length}')
    tag = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    path = LOGS_DIR / f'sprint4_tokens_{args.candidato}_{tag}.json'
    report = {
        'inicio': datetime.now().astimezone().isoformat(),
        'status': 'EM_EXECUCAO',
        'modelo': model,
        'revisao': revision,
        'tokenizer': type(tokenizer).__name__,
        'transformers': transformers.__version__,
        'tokenizers': tokenizers.__version__,
        'prefixo': prefix,
        'limite_tokens': token_limit,
        'limite_diagnostico': args.limit,
        'codigo_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'processados': 0,
        'excedentes': [],
    }
    save_report(path, report)
    print(f'Relatorio: {path}', flush=True)
    lengths: list[int] = []
    buckets: Counter[str] = Counter()
    source_hash = hashlib.sha256()
    try:
        with connect() as conn:
            conn.read_only = True
            with conn.transaction():
                total = conn.execute('SELECT count(*) FROM tcc.dim_embedding').fetchone()[0]
                report['total_banco'] = total
                with conn.cursor(name='sprint4_token_audit') as cursor:
                    cursor.execute('''SELECT id_embedding,chave_conteudo,conteudo_chunk
                                      FROM tcc.dim_embedding ORDER BY id_embedding''')
                    while True:
                        rows = cursor.fetchmany(BATCH)
                        if not rows:
                            break
                        if args.limit is not None:
                            rows = rows[:max(0, args.limit - report['processados'])]
                        if not rows:
                            break
                        payload = [prefix + row[2] for row in rows]
                        encoded = tokenizer(payload, add_special_tokens=True,
                                            truncation=False, padding=False,
                                            return_attention_mask=False,
                                            return_length=True)
                        for (identity, key, _), length in zip(rows, encoded['length'], strict=True):
                            n = int(length)
                            lengths.append(n)
                            source_hash.update(f'{identity}:{key}\n'.encode('ascii'))
                            label = ('<=128' if n <= 128 else '<=256' if n <= 256 else
                                     '<=384' if n <= 384 else '<=512' if n <= 512 else
                                     '<=640' if n <= 640 else '>640')
                            buckets[label] += 1
                            if n > token_limit:
                                report['excedentes'].append({'id_embedding': identity,
                                                              'chave_conteudo': key,
                                                              'tokens': n})
                        report['processados'] += len(rows)
                        if report['processados'] % 5120 == 0 or report['processados'] == total:
                            report['faixas'] = dict(buckets)
                            save_report(path, report)
                            print(f"[tokens] {report['processados']}/{total}; excedentes={len(report['excedentes'])}",
                                  flush=True)
                        if args.limit is not None and report['processados'] >= args.limit:
                            break
        report['faixas'] = dict(buckets)
        report['estatisticas'] = {'min': min(lengths, default=None),
                                  'p50': quantile(lengths, .5),
                                  'p95': quantile(lengths, .95),
                                  'p99': quantile(lengths, .99),
                                  'max': max(lengths, default=None)}
        report['sha256_identidades'] = source_hash.hexdigest()
        report['status'] = 'CONCLUIDO' if args.limit is None and len(lengths) == total else 'AMOSTRA'
        report['fim'] = datetime.now().astimezone().isoformat()
        save_report(path, report)
        print(json.dumps({'status': report['status'], 'processados': report['processados'],
                          'total': report['total_banco'],
                          'excedentes': len(report['excedentes']),
                          'estatisticas': report['estatisticas']}, ensure_ascii=False), flush=True)
        return 0 if report['status'] == 'CONCLUIDO' else 2
    except BaseException as exc:
        report['status'] = 'INTERROMPIDO'
        report['erro_fatal'] = type(exc).__name__
        report['fim'] = datetime.now().astimezone().isoformat()
        save_report(path, report)
        raise


if __name__ == '__main__':
    raise SystemExit(main())
