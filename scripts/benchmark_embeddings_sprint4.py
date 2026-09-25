"""Custo GTE estratificado pelo tokenizer efetivo; banco estritamente em leitura."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import hashlib
import heapq
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.config import LOGS_DIR
from src.database.connection import connect
from src.database.run_load import save_report
from src.embedding_model import MODEL, REVISION, CODE_REVISION, load_model, encode_checked

BOUNDS = (128, 256, 384, 512, 640, 1024, 2048, 4096, 8192)


def bucket_for(length):
    if length < 1 or length > BOUNDS[-1]:
        raise ValueError('comprimento fora do contrato; proibido truncar')
    return next(bound for bound in BOUNDS if length <= bound)


def retain_sample(heap, row, limit):
    # Os menores SHA-256, sem dependencia da ordem de leitura ou semente global.
    priority = int(hashlib.sha256(f'{row[0]}:{row[1]}'.encode()).hexdigest(), 16)
    item = (-priority, row)
    if len(heap) < limit:
        heapq.heappush(heap, item)
    elif item > heap[0]:
        heapq.heapreplace(heap, item)


def project_seconds(population, seconds_per_chunk):
    if any(n and bound not in seconds_per_chunk for bound, n in population.items()):
        raise ValueError('faixa populacional sem medicao')
    return sum(n * seconds_per_chunk[bound] for bound, n in population.items() if n)


def parse_df(output):
    lines = output.strip().splitlines()
    if len(lines) != 2 or len(lines[1].split()) < 6:
        raise ValueError('saida df invalida')
    parts = lines[1].split()
    total, used, available = map(int, parts[1:4])
    if not 0 <= available <= total or not 0 <= used <= total:
        raise ValueError('capacidade invalida')
    return dict(filesystem=parts[0], total_bytes=total, used_bytes=used,
                available_bytes=available, mount=parts[5])


def docker_space(container):
    def run(*args):
        return subprocess.run(['docker', *args], check=True, capture_output=True,
                              text=True, timeout=30).stdout.strip()
    directory = run('exec', container, 'printenv', 'PGDATA')
    mounts = json.loads(run('inspect', container, '--format', '{{json .Mounts}}'))
    mount = next((m for m in mounts if m['Destination'] == directory and m['Type'] == 'volume'), None)
    if mount is None:
        raise ValueError('PGDATA nao corresponde a volume nomeado')
    result = parse_df(run('exec', container, 'df', '-B1', '--output=source,size,used,avail,pcent,target', directory))
    result.update(container=container, pgdata=directory, volume=mount['Name'],
                  limite='Capacidade vista pelo filesystem Linux; disco virtual pode depender de espaco fisico do host.')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--por-faixa', type=int, default=8)
    parser.add_argument('--repeticoes', type=int, default=3)
    parser.add_argument('--container', required=True)
    args = parser.parse_args()
    if not 2 <= args.por_faixa <= 16 or not 2 <= args.repeticoes <= 5:
        parser.error('por-faixa deve estar em 2..16 e repeticoes em 2..5')
    import psutil
    import torch
    import transformers
    import sentence_transformers
    from transformers import AutoTokenizer
    tag = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    path = LOGS_DIR / f'sprint4_benchmark_{tag}.json'
    report = dict(status='EM_EXECUCAO', inicio=datetime.now().astimezone().isoformat(),
        modelo=MODEL, revisao=REVISION, revisao_codigo=CODE_REVISION, escrita_banco=False,
        por_faixa=args.por_faixa, repeticoes=args.repeticoes, batch_size=2,
        dispositivo='cpu', cpu_threads=torch.get_num_threads(),
        bibliotecas=dict(torch=torch.__version__, transformers=transformers.__version__,
            sentence_transformers=sentence_transformers.__version__, psutil=psutil.__version__),
        codigo_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), faixas=[])
    save_report(path, report)
    print(f'Relatorio: {path}', flush=True)
    try:
        report['volume_postgresql'] = docker_space(args.container)
        tokenizer = AutoTokenizer.from_pretrained(MODEL, revision=REVISION, trust_remote_code=False)
        population, samples = Counter(), {bound: [] for bound in BOUNDS}
        signature = hashlib.sha256()
        started = time.perf_counter()
        with connect() as conn:
            conn.read_only = True
            with conn.transaction():
                conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
                before = conn.execute('SELECT count(*),count(embedding) FROM tcc.dim_embedding').fetchone()
                report['chunks_total'], report['vetores_antes'] = before
                with conn.cursor(name='benchmark_token_scan') as cursor:
                    cursor.execute('SELECT id_embedding,chave_conteudo,conteudo_chunk FROM tcc.dim_embedding ORDER BY id_embedding')
                    while rows := cursor.fetchmany(512):
                        lengths = tokenizer([r[2] for r in rows], add_special_tokens=True,
                            truncation=False, padding=False, return_attention_mask=False,
                            return_length=True)['length']
                        for row, length in zip(rows, lengths, strict=True):
                            bound = bucket_for(length)
                            population[bound] += 1
                            retain_sample(samples[bound], (*row, int(length)), args.por_faixa)
                            signature.update(f'{row[0]}:{row[1]}\n'.encode('ascii'))
                        if sum(population.values()) % 10240 == 0:
                            print(f'Auditados: {sum(population.values())}/{before[0]}', flush=True)
        if sum(population.values()) != report['chunks_total'] or not population:
            raise ValueError('auditoria incompleta')
        report['segundos_auditoria_tokens'] = time.perf_counter()-started
        report['sha256_identidades'] = signature.hexdigest()
        report['populacao_tokens'] = dict(population)
        save_report(path, report)
        started = time.perf_counter()
        model = load_model()
        report['segundos_carregamento_modelo'] = time.perf_counter()-started
        encode_checked(model, ['Documento de obra publica para aquecimento do modelo.'])
        costs = {key: {} for key in ('min', 'mediana', 'max')}
        for bound in BOUNDS:
            rows = [item[1] for item in sorted(samples[bound])]
            if not rows:
                continue
            timings = []
            for _ in range(args.repeticoes):
                started = time.perf_counter()
                vectors, lengths = encode_checked(model, [row[2] for row in rows])
                timings.append(time.perf_counter()-started)
                if lengths != [row[3] for row in rows]:
                    raise ValueError('tokenizer da inferencia diverge da auditoria')
                del vectors
            for name, value in [('min', min(timings)), ('mediana', statistics.median(timings)), ('max', max(timings))]:
                costs[name][bound] = value/len(rows)
            report['faixas'].append(dict(limite_superior=bound, populacao=population[bound],
                amostra=[dict(id_embedding=r[0], chave_conteudo=r[1], tokens=r[3]) for r in rows],
                segundos_repeticoes=timings, segundos_por_chunk_mediana=costs['mediana'][bound]))
            save_report(path, report)
            print(f'Faixa <={bound}: n={population[bound]}, amostra={len(rows)}, mediana={statistics.median(timings):.3f}s', flush=True)
        report['projecao_inferencia_segundos'] = {name: project_seconds(population, values) for name, values in costs.items()}
        report['limites_projecao'] = ('Faixa min/max entre repeticoes, nao intervalo de confianca. '
            'Pressupoe batch 2 com agrupamento por comprimento; exclui leitura, escrita, WAL, indice e auditoria. '
            'Amostra por hash de ate 16 itens/faixa, sem validacao de qualidade semantica.')
        memory = psutil.Process().memory_info()
        report['memoria'] = dict(rss_bytes=memory.rss, pico_rss_bytes=getattr(memory, 'peak_wset', None))
        report['vetores_bytes_sem_overhead'] = report['chunks_total']*3080
        # Reserva de planejamento, nao medicao de WAL/overhead.
        report['reserva_planejamento_bytes'] = report['vetores_bytes_sem_overhead']*4
        report['volume_comporta_reserva'] = report['volume_postgresql']['available_bytes'] >= report['reserva_planejamento_bytes']
        with connect() as conn:
            conn.read_only = True
            report['vetores_depois'] = conn.execute('SELECT count(embedding) FROM tcc.dim_embedding').fetchone()[0]
        report.update(status='BENCHMARK_CONCLUIDO', fim=datetime.now().astimezone().isoformat())
        save_report(path, report)
        print(json.dumps(dict(status=report['status'], projecao=report['projecao_inferencia_segundos'],
            volume_comporta_reserva=report['volume_comporta_reserva']), ensure_ascii=False), flush=True)
        return 0
    except BaseException as exc:
        report.update(status='INTERROMPIDO', erro_fatal=type(exc).__name__)
        save_report(path, report)
        raise


if __name__ == '__main__':
    raise SystemExit(main())
