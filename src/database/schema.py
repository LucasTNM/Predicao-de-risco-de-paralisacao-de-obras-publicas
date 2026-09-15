"""Aplica DDL e detecta alteracoes de contrato sem recriar tabelas existentes."""
from __future__ import annotations

import hashlib
import json

from src.config import ROOT_DIR
from src.database.connection import connect

DDL_PATH = ROOT_DIR / "sql" / "001_sprint3_esquema_estrela.sql"
TABLES = {"dim_obra", "fato_risco", "dim_documento", "dim_embedding", "ponte_documento_embedding"}


def signature(conn) -> str:
    """Assinatura do catalogo: colunas/tipos/defaults, constraints e indices."""
    # O catalogo representa FKs/tipos conforme a visibilidade da sessao.
    # Preservar o mesmo contexto do DDL e restaurar inclusive transacoes externas.
    with conn.transaction():
        previous = conn.execute('SHOW search_path').fetchone()[0]
        conn.execute("SELECT pg_catalog.set_config('search_path', 'tcc, public', true)")
        try:
            return _catalog_signature(conn)
        finally:
            conn.execute("SELECT pg_catalog.set_config('search_path', %s, true)", (previous,))


def _catalog_signature(conn) -> str:
    columns = conn.execute("""
        SELECT c.relname, a.attname, format_type(a.atttypid,a.atttypmod),
               a.attnotnull, a.attidentity, pg_get_expr(d.adbin,d.adrelid)
        FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        JOIN pg_attribute a ON a.attrelid=c.oid
        LEFT JOIN pg_attrdef d ON d.adrelid=c.oid AND d.adnum=a.attnum
        WHERE n.nspname='tcc' AND c.relkind='r' AND a.attnum>0 AND NOT a.attisdropped
        ORDER BY c.relname,a.attnum
    """).fetchall()
    constraints = conn.execute("""
        SELECT c.relname, k.conname, pg_get_constraintdef(k.oid), k.convalidated
        FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='tcc' ORDER BY c.relname,k.conname
    """).fetchall()
    indexes = conn.execute("SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname='tcc' ORDER BY indexname").fetchall()
    return hashlib.sha256(json.dumps([columns, constraints, indexes], sort_keys=True).encode()).hexdigest()


def validate_schema(conn) -> None:
    names = {r[0] for r in conn.execute("SELECT tablename FROM pg_tables WHERE schemaname='tcc'")}
    if names != TABLES:
        raise RuntimeError("Schema tcc incompleto ou possui tabelas inesperadas; aplicar migracao explicita.")
    marker = conn.execute("SELECT obj_description('tcc'::regnamespace, 'pg_namespace')").fetchone()[0]
    ddl_hash = hashlib.sha256(DDL_PATH.read_text(encoding='utf-8').encode('utf-8')).hexdigest()
    if marker != f"sprint3:{ddl_hash}:{signature(conn)}":
        raise RuntimeError("Contrato do schema diverge do DDL homologado. Nao apagar dados; revisar migracao.")


def apply_schema(url: str | None = None) -> dict:
    with connect(url) as conn:
        exists = conn.execute("SELECT count(*) FROM pg_tables WHERE schemaname='tcc'").fetchone()[0]
        if exists:
            validate_schema(conn)
        else:
            from psycopg import sql
            # DDL e assinatura atomicos; o arquivo mantem BEGIN/COMMIT para psql.
            ddl = DDL_PATH.read_text(encoding="utf-8").replace('BEGIN;\n', '', 1).rsplit('COMMIT;', 1)[0]
            with conn.transaction():
                conn.execute(ddl)
                marker = f"sprint3:{hashlib.sha256(DDL_PATH.read_text(encoding='utf-8').encode('utf-8')).hexdigest()}:{signature(conn)}"
                conn.execute(sql.SQL("COMMENT ON SCHEMA tcc IS {}").format(sql.Literal(marker)))
            validate_schema(conn)
        version = conn.execute("SELECT version()").fetchone()[0]
        vector = conn.execute("SELECT extversion FROM pg_extension WHERE extname='vector'").fetchone()[0]
        return {"postgresql": version, "pgvector": vector, "tabelas": sorted(TABLES)}
