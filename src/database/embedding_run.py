"""Execucoes limitadas, com selecao congelada e retomada pelo estado do banco."""
import hashlib
import json
from datetime import datetime
from importlib.metadata import version, PackageNotFoundError
from pathlib import Path

from src.database.embeddings import persist_embedding, validate_vector
from src.database.run_load import save_report
from src.embedding_model import MODEL, REVISION, CODE_REVISION, load_model, encode_checked
from src.parsers.chunker import digest


def signature(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def make_manifest(selection, *, year, origin, batch_size):
    config = dict(version=1, model=MODEL, revision=REVISION, code_revision=CODE_REVISION,
                  normalization='L2', year=year, origin=origin, batch_size=batch_size,
                  selection=selection)
    result = dict(config=config, selection=selection, checksum=signature(config),
                  status='PREPARADO', items=[], created=datetime.now().astimezone().isoformat())
    validate_manifest(result)
    return result


def validate_manifest(manifest):
    config = manifest['config']
    selection = manifest['selection']
    if signature(config) != manifest['checksum'] or selection != config['selection']:
        raise ValueError('manifesto_alterado')
    if (config['version'], config['model'], config['revision'], config['code_revision'],
            config['normalization']) != (1, MODEL, REVISION, CODE_REVISION, 'L2'):
        raise ValueError('configuracao_incompativel')
    ids = [item['id_embedding'] for item in selection]
    if not 1 <= len(ids) <= 512 or len(ids) != len(set(ids)) or not 1 <= config['batch_size'] <= 32:
        raise ValueError('selecao_ou_lote_invalido')


def read_items(conn, selection):
    rows = conn.execute('''SELECT id_embedding,chave_conteudo,conteudo_chunk,token_ids,
        chunk_config,embedding::text,modelo_embedding,revisao_embedding
        FROM tcc.dim_embedding WHERE id_embedding=ANY(%s) ORDER BY id_embedding''',
        ([item['id_embedding'] for item in selection],)).fetchall()
    expected = {item['id_embedding']: item for item in selection}
    if len(rows) != len(expected):
        raise ValueError('fragmento_ausente')
    result = []
    for identity, key, text, tokens, config, vector, model, revision in rows:
        item = expected[identity]
        if key != item['chave_conteudo'] or config != item['chunk_config'] or digest([text, tokens, config]) != key:
            raise ValueError('fragmento_alterado')
        if vector is not None:
            if (model, revision) != (MODEL, REVISION):
                raise ValueError('modelo_existente_incompativel')
            validate_vector(json.loads(vector))
        result.append(dict(item, text=text, done=vector is not None))
    return result


def persist_batch(conn, items, vectors):
    if len(items) != len(vectors):
        raise ValueError('quantidade_vetores_invalida')
    with conn.transaction():
        conn.execute('''SELECT id_embedding FROM tcc.dim_embedding
            WHERE id_embedding=ANY(%s) ORDER BY id_embedding FOR UPDATE''',
            ([item['id_embedding'] for item in items],)).fetchall()
        read_items(conn, items)
        return [persist_embedding(conn, identity=item['id_embedding'], key=item['chave_conteudo'],
                    text=item['text'], values=vector, model=MODEL, revision=REVISION)
                for item, vector in zip(items, vectors)]


def run_batches(conn, manifest, path, *, write=False, loader=load_model, encoder=encode_checked,
                device='cpu', inference_batch_size=2):
    if device not in ('cpu', 'cuda') or not 1 <= inference_batch_size <= 32:
        raise ValueError('dispositivo_ou_batch_invalido')
    validate_manifest(manifest)
    lock = int(manifest['checksum'][:15], 16)
    if not conn.execute('SELECT pg_try_advisory_lock(%s)', (lock,)).fetchone()[0]:
        raise ValueError('execucao_em_andamento')
    try:
        libraries = {}
        for name in ('torch', 'sentence-transformers', 'transformers', 'psycopg', 'tokenizers'):
            try:
                libraries[name] = version(name)
            except PackageNotFoundError:
                libraries[name] = None
        root = Path(__file__).resolve().parents[2]
        code = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in (
            'src/database/embedding_run.py', 'src/database/embeddings.py', 'src/embedding_model.py')}
        manifest.setdefault('attempts', []).append(dict(started=datetime.now().astimezone().isoformat(),
            libraries=libraries, code_sha256=code, device=device, inference_batch_size=inference_batch_size))
        manifest.pop('erro', None)
        items = read_items(conn, manifest['selection'])
        manifest['items'] = [dict(id_embedding=i['id_embedding'], estado='reutilizado') for i in items if i['done']]
        manifest['status'] = 'EM_EXECUCAO'
        manifest['write'] = write
        save_report(path, manifest)
        pending = [i for i in items if not i['done']]
        model = loader() if pending else None
        size = manifest['config']['batch_size']
        for start in range(0, len(pending), size):
            batch = pending[start:start+size]
            vectors, lengths = encoder(model, [i['text'] for i in batch], batch_size=inference_batch_size)
            states = persist_batch(conn, batch, vectors) if write else ['inferido'] * len(batch)
            manifest['items'].extend(dict(id_embedding=i['id_embedding'], estado=state, tokens=n)
                                     for i, state, n in zip(batch, states, lengths))
            save_report(path, manifest)
        manifest['status'] = 'CONCLUIDO' if write else 'INFERIDO'
        save_report(path, manifest)
    except Exception as exc:
        manifest['status'] = 'INTERROMPIDO'
        manifest['erro'] = type(exc).__name__
        save_report(path, manifest)
        raise
    finally:
        conn.execute('SELECT pg_advisory_unlock(%s)', (lock,))
