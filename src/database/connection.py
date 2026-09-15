"""Conexao local sem expor credenciais nos erros de operacao."""
from __future__ import annotations

import os

from src.config import ROOT_DIR


def connect(url: str | None = None):
    from dotenv import load_dotenv
    import psycopg

    load_dotenv(ROOT_DIR / ".env")
    dsn = url or os.getenv("DATABASE_URL", "")
    if not dsn:
        raise RuntimeError("DATABASE_URL nao configurada no .env.")
    try:
        return psycopg.connect(dsn, connect_timeout=10, autocommit=True)
    except psycopg.OperationalError:
        raise RuntimeError(
            "Conexao PostgreSQL indisponivel. Confira Docker, porta e credenciais do .env."
        ) from None
