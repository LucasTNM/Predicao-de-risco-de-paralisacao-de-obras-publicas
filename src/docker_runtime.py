"""Prepare local Docker/PostgreSQL through the supported Desktop lifecycle CLI."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time

_LOCK = threading.Lock()


class DockerRuntimeError(RuntimeError):
    pass


def managed_local(dsn, *, windows=None):
    """Only the configured Windows development database is managed automatically."""
    from psycopg.conninfo import conninfo_to_dict
    from psycopg import ProgrammingError
    if not (os.name == 'nt' if windows is None else windows):
        return False
    try:
        info = conninfo_to_dict(dsn)
        port = int(info.get('port') or 5432)
        configured = int(os.getenv('POSTGRES_PORT') or 5432)
    except (ValueError, TypeError, ProgrammingError):
        # Invalid connection strings must be handled by the connection layer.
        return False
    return (info.get('host') in ('localhost','127.0.0.1','::1') and
            port == configured and info.get('dbname') == 'tcc_obras')


def local_port_ready(dsn):
    from psycopg.conninfo import conninfo_to_dict
    try:
        info = conninfo_to_dict(dsn)
        with socket.create_connection((info['host'],int(info.get('port') or 5432)),timeout=1):
            return True
    except (OSError, ValueError, KeyError):
        return False


def progress(message):
    print(f'[Docker] {message}',file=sys.stderr,flush=True)


def _run(args, *, cwd, timeout):
    return subprocess.run(args,cwd=cwd,timeout=timeout,capture_output=True,
                          text=True,encoding='utf-8',errors='replace',
                          creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)


def _services(text):
    text = text.strip()
    if not text:
        return []
    try:
        value=json.loads(text)
        return value if isinstance(value,list) else [value]
    except ValueError:
        try:
            return [json.loads(line) for line in text.splitlines() if line.strip()]
        except ValueError:
            raise DockerRuntimeError('verificar_postgres: resposta Compose invalida.') from None


def ensure_postgres(root=None, *, timeout=240, progress=progress, runner=_run,
                    clock=time.monotonic, sleep=time.sleep, windows=None, docker='docker'):
    """Start at most once, wait for the Linux engine, then this project's healthcheck.

    Never changes the global context or restarts a running environment. Raw
    subprocess errors are withheld because Compose output can contain secrets.
    """
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('timeout_deve_ser_positivo')
    root = Path(root or Path(__file__).resolve().parents[1]).resolve()
    if not (root/'compose.yaml').is_file():
        raise DockerRuntimeError('configuracao: compose.yaml ausente.')
    windows = os.name=='nt' if windows is None else windows
    context = 'desktop-linux' if windows else 'default'
    started = clock()
    deadline = started+timeout
    if not _LOCK.acquire(timeout=timeout):
        raise DockerRuntimeError('concorrencia: prazo para preparar Docker esgotado.')
    try:
        def command(args,stage,limit=5,tolerate_timeout=False):
            left = deadline-clock()
            if left <= 0:
                raise DockerRuntimeError(f'{stage}: prazo de {timeout:g}s esgotado.')
            try:
                return runner([docker,*args],cwd=root,timeout=min(limit,left))
            except FileNotFoundError:
                raise DockerRuntimeError(f'{stage}: CLI Docker ausente do PATH.') from None
            except subprocess.TimeoutExpired:
                if tolerate_timeout and clock()<deadline:
                    return subprocess.CompletedProcess(args,124,stdout='',stderr='')
                raise DockerRuntimeError(f'{stage}: comando Docker excedeu o prazo.') from None
            except OSError:
                raise DockerRuntimeError(f'{stage}: nao foi possivel executar Docker.') from None

        result = dict(contexto=context,engine_iniciado=False,servico_iniciado=False)
        if progress:
            progress('Verificando engine local.')
        endpoint = command(['context','inspect',context,'--format','{{json .Endpoints.docker.Host}}'],
                           'verificar_contexto')
        if endpoint.returncode != 0:
            raise DockerRuntimeError(f'verificar_contexto: contexto local {context} indisponivel.')
        try:
            host = json.loads(endpoint.stdout)
        except ValueError:
            raise DockerRuntimeError('verificar_contexto: endpoint invalido.') from None
        if not isinstance(host,str) or not host.startswith(('npipe:////./pipe/','npipe://./pipe/','unix:///')):
            raise DockerRuntimeError('contexto_remoto: preparo automatico exige engine local.')
        prefix=['--context',context]

        def engine_ready():
            return command([*prefix,'info','--format','{{json .ServerVersion}}'],
                           'aguardar_engine',tolerate_timeout=True).returncode == 0

        if not engine_ready():
            if not windows:
                raise DockerRuntimeError('verificar_engine: inicie o engine local neste sistema.')
            if progress:
                progress('Solicitando inicio do Docker Desktop pela CLI oficial.')
            request = command(['desktop','start','--detach'],'iniciar_desktop',15)
            if request.returncode != 0:
                raise DockerRuntimeError('iniciar_desktop: CLI recusou inicio. Consulte docker desktop logs.')
            result['engine_iniciado']=True
            last_progress=clock()
            while not engine_ready():
                if clock()-last_progress>=10 and progress:
                    progress('Aguardando engine; inicializacao em andamento.')
                    last_progress=clock()
                sleep(min(2,max(0,deadline-clock())))
        compose=[*prefix,'compose','--project-directory',str(root),'-f',str(root/'compose.yaml')]

        def service():
            response=command([*compose,'ps','-a','--format','json','postgres'],'verificar_postgres')
            if response.returncode != 0:
                raise DockerRuntimeError('verificar_postgres: consulta Compose falhou.')
            found=[s for s in _services(response.stdout) if isinstance(s,dict) and s.get('Service')=='postgres']
            if len(found)>1:
                raise DockerRuntimeError('verificar_postgres: mais de um container para o servico.')
            return found[0] if found else None

        state=service()
        if state is None or state.get('State')!='running':
            if progress:
                progress('Iniciando PostgreSQL do projeto.')
            args=['start','postgres'] if state else ['up','-d','--no-recreate','postgres']
            response=command([*compose,*args],'iniciar_postgres',30)
            if response.returncode != 0:
                raise DockerRuntimeError('iniciar_postgres: Compose falhou; confira configuracao local.')
            result['servico_iniciado']=True
        last_progress=clock()
        while state is None or state.get('State')!='running' or state.get('Health')!='healthy':
            if clock()>=deadline:
                raise DockerRuntimeError(f'aguardar_postgres: prazo de {timeout:g}s esgotado.')
            if clock()-last_progress>=10 and progress:
                progress('Aguardando healthcheck do PostgreSQL.')
                last_progress=clock()
            sleep(min(2,max(0,deadline-clock())))
            if clock()>=deadline:
                raise DockerRuntimeError(f'aguardar_postgres: prazo de {timeout:g}s esgotado.')
            state=service()
        result['segundos']=round(clock()-started,3)
        if progress:
            progress('Engine e PostgreSQL saudaveis.')
        return result
    finally:
        _LOCK.release()
