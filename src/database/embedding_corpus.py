"""Orquestracao integral com submanifestos limitados e retomada pelo banco."""
from datetime import datetime
import json
import hashlib
from pathlib import Path
import shutil
import time

from src.database.embedding_run import make_manifest, validate_manifest, signature, run_batches
from src.database.run_load import save_report
from src.embedding_model import MODEL, REVISION, CODE_REVISION, load_model


def prepare_corpus(conn, path, *, device, inference_batch, threads):
    if device not in ('cpu', 'cuda') or not 1 <= inference_batch <= 32 or not 1 <= threads <= 16:
        raise ValueError('configuracao_invalida')
    path = Path(path)
    if path.exists() or path.with_suffix('').exists():
        raise FileExistsError('manifesto_ou_partes_existentes')
    rows = conn.execute('''SELECT id_embedding,chave_conteudo,chunk_config
        FROM tcc.dim_embedding ORDER BY id_embedding''').fetchall()
    if not rows:
        raise ValueError('corpus_vazio')
    directory = path.with_suffix('')
    directory.mkdir(parents=True)
    parts = []
    for start in range(0, len(rows), 512):
        selection = [dict(zip(('id_embedding','chave_conteudo','chunk_config'), row)) for row in rows[start:start+512]]
        child = make_manifest(selection, year=None, origin=None, batch_size=32)
        child_path = directory / f'part_{start//512:04d}.json'
        save_report(child_path, child)
        parts.append(dict(file=child_path.relative_to(path.parent).as_posix(), checksum=child['checksum'], count=len(selection)))
    config = dict(version=1, model=MODEL, revision=REVISION, code_revision=CODE_REVISION,
                  device=device, dtype='float32', tf32=False, inference_batch=inference_batch,
                  threads=threads, total=len(rows), parts=parts)
    manifest = dict(config=config, checksum=signature(config), status='PREPARADO',
                    created=datetime.now().astimezone().isoformat(), completed=0)
    save_report(path, manifest)
    return manifest


def part_path(path, part):
    root = Path(path).parent.resolve()
    result = (root / part['file']).resolve()
    if not result.is_relative_to(root):
        raise ValueError('caminho_de_parte_invalido')
    return result


def validate_corpus(manifest, path):
    config = manifest['config']
    if manifest['checksum'] != signature(config):
        raise ValueError('manifesto_integral_alterado')
    if (config['version'], config['model'], config['revision'], config['code_revision'], config['dtype'], config['tf32']) != (1, MODEL, REVISION, CODE_REVISION, 'float32', False):
        raise ValueError('contrato_integral_incompativel')
    if config['device'] not in ('cpu','cuda') or not 1 <= config['inference_batch'] <= 32 or not 1 <= config['threads'] <= 16:
        raise ValueError('configuracao_integral_invalida')
    identities = set()
    for part in config['parts']:
        child = json.loads(part_path(path, part).read_text(encoding='utf-8'))
        validate_manifest(child)
        if child['checksum'] != part['checksum'] or len(child['selection']) != part['count']:
            raise ValueError('submanifesto_alterado')
        for item in child['selection']:
            if item['id_embedding'] in identities:
                raise ValueError('identidade_repetida')
            identities.add(item['id_embedding'])
    if len(identities) != config['total'] or not identities:
        raise ValueError('populacao_divergente')


def run_corpus(conn, manifest, path, *, write, loader=load_model):
    validate_corpus(manifest, path)
    if shutil.disk_usage(Path(path).resolve().parent).free < 5*1024**3:
        raise ValueError('disco_livre_menor_5GiB')
    # Um unico produtor integral; leitores e pilotos continuam protegidos pelos locks de linha.
    lock = 90420260923
    if not conn.execute('SELECT pg_try_advisory_lock(%s)', (lock,)).fetchone()[0]:
        raise ValueError('outra_carga_integral_ativa')
    config = manifest['config']
    model = None
    def cached_loader():
        nonlocal model
        if model is None:
            model = loader(config['device'], config['threads'])
        return model
    started = time.monotonic()
    try:
        manifest['status'] = 'EM_EXECUCAO'
        manifest['completed'] = 0
        manifest.pop('error', None)
        attempt = dict(started=datetime.now().astimezone().isoformat(), write=write, reused=0, written=0,
                       code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
        manifest.setdefault('attempts', []).append(attempt)
        save_report(path, manifest)
        for part in config['parts']:
            if shutil.disk_usage(Path(path).resolve().parent).free < 5*1024**3:
                raise ValueError('disco_livre_menor_5GiB')
            child_path = part_path(path, part)
            child = json.loads(child_path.read_text(encoding='utf-8'))
            run_batches(conn, child, child_path, write=write, loader=cached_loader,
                        device=config['device'], inference_batch_size=config['inference_batch'])
            attempt['reused'] += sum(i['estado'] == 'reutilizado' for i in child['items'])
            attempt['written'] += sum(i['estado'] == 'gravado' for i in child['items'])
            manifest['completed'] += len(child['items'])
            attempt['seconds'] = time.monotonic()-started
            if model is not None:
                try:
                    import psutil
                    attempt['rss_bytes'] = psutil.Process().memory_info().rss
                except ImportError:
                    attempt['rss_bytes'] = None
                if config['device'] == 'cuda':
                    import torch
                    attempt['gpu_peak_bytes'] = torch.cuda.max_memory_allocated()
            save_report(path, manifest)
            print(json.dumps(dict(completed=manifest['completed'], total=config['total'],
                                  seconds=round(attempt['seconds'], 2))), flush=True)
        manifest['status'] = 'CONCLUIDO' if write else 'INFERIDO'
        save_report(path, manifest)
    except BaseException as exc:
        manifest['status'] = 'INTERROMPIDO'
        manifest['error'] = type(exc).__name__
        save_report(path, manifest)
        raise
    finally:
        conn.execute('SELECT pg_advisory_unlock(%s)', (lock,))
