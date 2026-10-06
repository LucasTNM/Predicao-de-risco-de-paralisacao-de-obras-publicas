from types import SimpleNamespace
import pytest

from src.docker_runtime import DockerRuntimeError, ensure_postgres


class Clock:
    def __init__(self): self.now=0
    def __call__(self): return self.now
    def sleep(self,seconds): self.now+=seconds


class Runner:
    def __init__(self, engines=(True,), states=('healthy',), start_code=0):
        self.engines=list(engines); self.states=list(states); self.calls=[]; self.start_code=start_code
    def __call__(self,args,**kwargs):
        self.calls.append((args,kwargs))
        if 'inspect' in args: return SimpleNamespace(returncode=0,stdout='"npipe:////./pipe/dockerDesktopLinuxEngine"')
        if 'info' in args:
            value=self.engines.pop(0) if len(self.engines)>1 else self.engines[0]
            return SimpleNamespace(returncode=0 if value else 1,stdout='"29.0"' if value else '')
        if 'desktop' in args: return SimpleNamespace(returncode=self.start_code,stdout='')
        if 'ps' in args:
            value=self.states.pop(0) if len(self.states)>1 else self.states[0]
            state='running' if value=='healthy' else 'exited'
            text='[]' if value=='absent' else f'[{{"Service":"postgres","State":"{state}","Health":"{value}"}}]'
            return SimpleNamespace(returncode=0,stdout=text)
        return SimpleNamespace(returncode=0,stdout='')


def ensure(tmp_path,runner,timeout=20):
    (tmp_path/'compose.yaml').write_text('services: {}')
    clock=Clock()
    return ensure_postgres(tmp_path,runner=runner,clock=clock,sleep=clock.sleep,
                           timeout=timeout,windows=True,docker='docker')


def test_healthy_environment_never_started(tmp_path):
    runner=Runner()
    result=ensure(tmp_path,runner)
    assert not result['engine_iniciado'] and not result['servico_iniciado']
    assert all('start' not in cmd and 'up' not in cmd for cmd,_ in runner.calls)


def test_closed_desktop_started_once_then_waited(tmp_path):
    runner=Runner(engines=(False,False,True),states=('exited','healthy'))
    result=ensure(tmp_path,runner)
    assert result['engine_iniciado'] and result['servico_iniciado']
    starts=[cmd for cmd,_ in runner.calls if 'desktop' in cmd]
    assert len(starts)==1 and starts[0][-2:]==['start','--detach']
    assert any('compose' in cmd and 'start' in cmd for cmd,_ in runner.calls)
    assert all('stop' not in cmd and 'restart' not in cmd for cmd,_ in runner.calls)


def test_engine_timeout_bounded(tmp_path):
    runner=Runner(engines=(False,))
    with pytest.raises(DockerRuntimeError,match='aguardar_engine'):
        ensure(tmp_path,runner,timeout=5)
    assert len([cmd for cmd,_ in runner.calls if 'desktop' in cmd])==1
    assert all(0<opts['timeout']<=5 for _,opts in runner.calls)


def test_start_failure_specific_and_no_sensitive_output(tmp_path):
    runner=Runner(engines=(False,),start_code=1)
    with pytest.raises(DockerRuntimeError,match='iniciar_desktop') as err:
        ensure(tmp_path,runner)
    assert 'password' not in str(err.value)


def test_absent_container_up_no_recreate(tmp_path):
    runner=Runner(states=('absent','healthy'))
    ensure(tmp_path,runner)
    command=next(cmd for cmd,_ in runner.calls if 'up' in cmd)
    assert '--no-recreate' in command and command[-1]=='postgres'


def test_remote_context_rejected(tmp_path):
    runner=Runner()
    original=runner.__call__
    def remote(args,**kwargs):
        if 'inspect' in args: return SimpleNamespace(returncode=0,stdout='"ssh://remote"')
        return original(args,**kwargs)
    with pytest.raises(DockerRuntimeError,match='contexto_remoto'):
        ensure(tmp_path,remote)


def test_remote_named_pipe_rejected(tmp_path):
    runner=Runner()
    def remote(args,**kwargs):
        if 'inspect' in args:
            return SimpleNamespace(returncode=0,stdout='"npipe:////remote-host/pipe/docker_engine"')
        return runner(args,**kwargs)
    with pytest.raises(DockerRuntimeError,match='contexto_remoto'):
        ensure(tmp_path,remote)


def test_service_timeout(tmp_path):
    with pytest.raises(DockerRuntimeError,match='aguardar_postgres'):
        ensure(tmp_path,Runner(states=('unhealthy',)),timeout=5)


@pytest.mark.parametrize('timeout',[0,-1,float('nan'),float('inf')])
def test_timeout_must_be_positive_and_finite(tmp_path,timeout):
    with pytest.raises(ValueError,match='timeout_deve_ser_positivo'):
        ensure(tmp_path,Runner(),timeout=timeout)


def test_engine_probe_timeout_is_retried_within_budget(tmp_path):
    import subprocess
    runner=Runner(engines=(False,True))
    count=0
    def probe(args,**kwargs):
        nonlocal count
        if 'info' in args:
            count+=1
            if count==1:
                raise subprocess.TimeoutExpired(args,kwargs['timeout'])
        return runner(args,**kwargs)
    assert ensure(tmp_path,probe)['engine_iniciado']
