"""Regressao + PostgreSQL real em banco temporario criado e removido por este script."""
from pathlib import Path
import os
import sys
from urllib.parse import urlsplit, urlunsplit
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    import psycopg
    from psycopg import sql
    from dotenv import dotenv_values
    import pytest

    settings = dotenv_values(ROOT / '.env')
    source = urlsplit(settings['DATABASE_URL'])
    if source.hostname not in ('127.0.0.1', 'localhost'):
        raise RuntimeError('Este runner so provisiona testes no PostgreSQL local.')
    database = 'tcc_test_' + uuid.uuid4().hex
    with psycopg.connect(host=source.hostname, port=source.port or 5432, user='postgres',
                         password=settings['POSTGRES_PASSWORD'], dbname='postgres', autocommit=True,
                         connect_timeout=10) as admin:
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(database)))
        try:
            with psycopg.connect(host=source.hostname,port=source.port or 5432,user='postgres',
                                 password=settings['POSTGRES_PASSWORD'],dbname=database,autocommit=True) as setup:
                setup.execute('CREATE EXTENSION vector; CREATE SCHEMA tcc AUTHORIZATION tcc_app; REVOKE CREATE ON SCHEMA public FROM PUBLIC;')
            previous = os.environ.get('TEST_DATABASE_URL')
            os.environ['TEST_DATABASE_URL'] = urlunsplit(source._replace(path='/' + database))
            try:
                return int(pytest.main([str(ROOT / 'tests'), '-q']))
            finally:
                if previous is None:
                    os.environ.pop('TEST_DATABASE_URL', None)
                else:
                    os.environ['TEST_DATABASE_URL'] = previous
        finally:
            # Alvo e exclusivamente o banco de UUID criado acima por esta execucao.
            admin.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(database)))


if __name__ == '__main__':
    raise SystemExit(main())
