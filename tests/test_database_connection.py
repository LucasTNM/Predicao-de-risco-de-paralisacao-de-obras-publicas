import pytest
import psycopg
from src.database import connection


def test_default_local_unreachable_prepares_and_retries(monkeypatch):
    monkeypatch.setenv('DATABASE_URL','postgresql://user:secret@localhost:5432/tcc_obras')
    monkeypatch.setattr(connection,'managed_local',lambda *args:True)
    monkeypatch.setattr(connection,'local_port_ready',lambda *args:False)
    calls=[]
    def connect(*args,**kwargs):
        calls.append('connect')
        if len(calls)==1: raise psycopg.OperationalError('unavailable')
        return 'connection'
    monkeypatch.setattr(psycopg,'connect',connect)
    monkeypatch.setattr(connection,'ensure_postgres',lambda *args,**kwargs:calls.append('prepare'))
    assert connection.connect()=='connection'
    assert calls==['connect','prepare','connect']


def test_explicit_url_does_not_prepare(monkeypatch):
    monkeypatch.setattr(connection,'ensure_postgres',lambda *args,**kwargs:pytest.fail('unexpected startup'))
    monkeypatch.setattr(psycopg,'connect',lambda *args,**kwargs:(_ for _ in ()).throw(psycopg.OperationalError('secret')))
    with pytest.raises(RuntimeError) as err: connection.connect('postgresql://user:secret@localhost/db')
    assert 'secret' not in str(err.value)


def test_auth_failure_never_prepares(monkeypatch):
    monkeypatch.setenv('DATABASE_URL','postgresql://user:secret@localhost:5432/tcc_obras')
    monkeypatch.setattr(connection,'managed_local',lambda *args:True)
    monkeypatch.setattr(connection,'ensure_postgres',lambda *args,**kwargs:pytest.fail('unexpected startup'))
    monkeypatch.setattr(psycopg,'connect',lambda *args,**kwargs:(_ for _ in ()).throw(psycopg.errors.InvalidPassword('secret')))
    with pytest.raises(RuntimeError) as err: connection.connect()
    assert 'secret' not in str(err.value)


def test_managed_scope(monkeypatch):
    from src.docker_runtime import managed_local
    monkeypatch.setenv('POSTGRES_PORT','5432')
    assert not managed_local('postgresql://user@remote:5432/tcc_obras',windows=True)
    assert not managed_local('postgresql://user@localhost:5433/tcc_obras',windows=True)
    assert not managed_local('postgresql://user@localhost:5432/tcc_test_fixture',windows=True)
    assert managed_local('postgresql://user@localhost:5432/tcc_obras',windows=True)
    assert not managed_local('postgresql://user@localhost:5432/tcc_obras',windows=False)
