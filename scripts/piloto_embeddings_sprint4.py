"""Piloto estratificado do Card 8; por padrao faz apenas inferencia em leitura."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import LOGS_DIR  # noqa: E402
from src.database.connection import connect  # noqa: E402
from src.database.embeddings import persist_embedding, validate_vector  # noqa: E402
from src.database.run_load import save_report  # noqa: E402
from src.database.validation import validate_data  # noqa: E402
from src.embedding_model import MODEL, REVISION, CODE_REVISION, load_model, encode_checked  # noqa: E402

def select_sample(conn, per_stratum=1):
    """Uma amostra deterministica por ano/base/origem, mais borda do E5."""
    rows = conn.execute('''
        WITH unique_rows AS (SELECT DISTINCT
            e.id_embedding,e.chave_conteudo,e.conteudo_chunk,
            d.ano_base,d.base_origem,d.origem_documento
        FROM tcc.dim_embedding e
        JOIN tcc.ponte_documento_embedding p USING (id_embedding)
        JOIN tcc.dim_documento d USING (id_documento)
        ), ranked AS (SELECT *, row_number() OVER (
            PARTITION BY ano_base,base_origem,origem_documento
            ORDER BY md5(chave_conteudo),id_embedding) AS position FROM unique_rows)
        SELECT id_embedding,chave_conteudo,conteudo_chunk,ano_base,base_origem,origem_documento
        FROM ranked WHERE position <= %s
        ORDER BY ano_base,base_origem,origem_documento,position
    ''', (per_stratum,)).fetchall()
    edge = conn.execute('''SELECT e.id_embedding,e.chave_conteudo,e.conteudo_chunk,
                                 d.ano_base,d.base_origem,d.origem_documento
                           FROM tcc.dim_embedding e
                           JOIN tcc.ponte_documento_embedding p USING (id_embedding)
                           JOIN tcc.dim_documento d USING (id_documento)
                           WHERE e.id_embedding=5674 LIMIT 1''').fetchone()
    if edge is not None:
        rows.append(edge)
    return list({row[0]: row for row in rows}.values())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true', help='Grava somente o piloto no banco.')
    parser.add_argument('--por-estrato', type=int, default=1,
                        help='Chunks por ano/base/origem, entre 1 e 16 (piloto limitado).')
    args = parser.parse_args()
    if not 1 <= args.por_estrato <= 16:
        parser.error('--por-estrato deve estar entre 1 e 16')
    import numpy as np
    import torch
    import sentence_transformers
    import transformers

    tag = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    path = LOGS_DIR / f'sprint4_piloto_{tag}.json'
    report = {'inicio': datetime.now().astimezone().isoformat(),
              'status': 'EM_EXECUCAO', 'escrita': args.write,
              'modelo': MODEL, 'revisao': REVISION,
              'revisao_codigo_externo': CODE_REVISION,
              'bibliotecas': {'torch': torch.__version__,
                              'sentence_transformers': sentence_transformers.__version__,
                              'transformers': transformers.__version__},
              'dispositivo': 'cpu', 'normalizacao': 'L2',
              'prefixo': '', 'batch_size': 2, 'por_estrato': args.por_estrato,
              'codigo_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'fragmentos': []}
    save_report(path, report)
    print(f'Relatorio: {path}', flush=True)
    try:
        with connect() as conn:
            conn.read_only = True
            with conn.transaction():
                report['baseline'] = validate_data(conn)
                rows = select_sample(conn, args.por_estrato)
                report['vetores_antes'] = conn.execute('''SELECT count(*) FROM tcc.dim_embedding
                    WHERE embedding IS NOT NULL''').fetchone()[0]
        if not report['baseline']['valido'] or not rows:
            raise RuntimeError('Banco invalido ou sem amostra elegivel.')
        model = load_model()
        started = time.monotonic()
        vectors, token_lengths = encode_checked(model, [row[2] for row in rows])
        report['segundos_inferencia'] = round(time.monotonic() - started, 3)
        report['chunks_por_segundo'] = len(rows) / (time.monotonic() - started)
        import psutil
        memory = psutil.Process().memory_info()
        report['memoria'] = {'rss_bytes': memory.rss,
            'pico_rss_bytes': getattr(memory, 'peak_wset', None)}
        report['projecao_inferencia_segundos'] = (
            report['baseline']['contagens']['dim_embedding'] / report['chunks_por_segundo'])
        report['limite_projecao'] = 'Extrapolacao exploratoria; amostra nao ponderada por comprimento.'
        for row, length, vector in zip(rows, token_lengths, vectors, strict=True):
            validate_vector(vector)
            item = {'id_embedding': row[0], 'chave_conteudo': row[1],
                    'ano': row[3], 'base': row[4], 'origem': row[5],
                    'tokens_modelo': int(length),
                    'norma': round(float(np.linalg.norm(vector)), 6),
                    'estado': 'inferido'}
            if args.write:
                with connect() as conn:
                    item['estado'] = persist_embedding(conn, identity=row[0], key=row[1],
                        text=row[2], values=vector, model=MODEL, revision=REVISION)
            report['fragmentos'].append(item)
            save_report(path, report)
        with connect() as conn:
            conn.read_only = True
            with conn.transaction():
                report['validacao_depois'] = validate_data(conn)
                report['vetores_depois'] = conn.execute('''SELECT count(*) FROM tcc.dim_embedding
                    WHERE embedding IS NOT NULL''').fetchone()[0]
        if not report['validacao_depois']['valido']:
            raise RuntimeError('Integridade do banco reprovada apos o piloto.')
        report['status'] = 'PILOTO_GRAVADO' if args.write else 'INFERENCIA_VALIDADA'
        report['fim'] = datetime.now().astimezone().isoformat()
        save_report(path, report)
        print(json.dumps({'status': report['status'], 'fragmentos': len(rows),
            'vetores_antes': report['vetores_antes'], 'vetores_depois': report['vetores_depois'],
            'segundos_inferencia': report['segundos_inferencia'],
            'validacao': report['validacao_depois']['valido']}, ensure_ascii=False), flush=True)
        return 0
    except BaseException as exc:
        report['status'] = 'INTERROMPIDO'
        report['erro_fatal'] = type(exc).__name__
        report['fim'] = datetime.now().astimezone().isoformat()
        save_report(path, report)
        raise


if __name__ == '__main__':
    raise SystemExit(main())
