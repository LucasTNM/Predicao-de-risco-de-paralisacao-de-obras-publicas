"""Conexao local sem expor credenciais nos erros de operacao."""
from __future__ import annotations

import os

from src.config import ROOT_DIR
from src.docker_runtime import ensure_postgres, managed_local, local_port_ready


def connect(url: str | None = None):
    from dotenv import load_dotenv
    import psycopg

    load_dotenv(ROOT_DIR / ".env")
    dsn = url or os.getenv("DATABASE_URL", "")
    if not dsn:
        raise RuntimeError("DATABASE_URL nao configurada no .env.")
    try:
        return psycopg.connect(dsn, connect_timeout=10, autocommit=True)
    except psycopg.OperationalError as error:
        auth_error = (getattr(error, 'sqlstate', '') or '').startswith('28')
        if (url is None and not auth_error and managed_local(dsn) and not local_port_ready(dsn)):
            ensure_postgres(ROOT_DIR)
            try:
                return psycopg.connect(dsn, connect_timeout=10, autocommit=True)
            except psycopg.OperationalError:
                raise RuntimeError(
                    'Docker/PostgreSQL prontos, mas conexao falhou. Confira credenciais e DATABASE_URL local.'
                ) from None
        raise RuntimeError(
            "Conexao PostgreSQL indisponivel. Confira Docker, porta e credenciais do .env."
        ) from None
