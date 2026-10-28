from pathlib import Path
import pytest
from zerorepo.rtl_web.schemas import DemoError


def test_disk_budget_rejects_without_deleting_evidence(tmp_path):
    from zerorepo.rtl_web import budgets
    evidence=tmp_path/'report';evidence.write_text('immutable')
    with pytest.raises(DemoError):budgets.disk_admission(tmp_path,min_free_bytes=2**62)
    assert evidence.read_text()=='immutable'


def test_single_job_limit_is_bounded(tmp_path):
    from zerorepo.rtl_web import budgets
    (tmp_path/'output').write_bytes(b'x'*64)
    with pytest.raises(DemoError):budgets.job_usage(tmp_path,32)
    assert (tmp_path/'output').is_file()


@pytest.mark.parametrize('access_mode',['ssh_tunnel','public'])
def test_bounded_chat_uses_incremental_memory_without_enabling_native_jobs(settings,tmp_path,monkeypatch,access_mode):
    import json
    import yaml
    from types import SimpleNamespace
    from zerorepo.rtl_web.settings import Settings
    from zerorepo.rtl_web import budgets,sandbox
    cfg=dict(settings.raw);agent=tmp_path/'agent.yaml';agent.write_text('llm: {}\n')
    cfg.update(development=False,access_mode='ssh_tunnel',allowed_origins=['http://127.0.0.1:18173'])
    cfg['runtime']={**cfg.get('runtime',{}),'agent_config':str(agent),'python':__import__('sys').executable}
    if access_mode=='public':
        cfg.update(access_mode='public',allowed_origins=['https://design.deepvalleychip.cn'])
        cfg['runtime']['bounded_chat']=True
    settings.config_path.write_text(yaml.safe_dump(cfg));selected=Settings(settings.config_path)
    checks={'memory_budget':False,'disk_space':True,'job_volume':False,'cgroup_memory':False,'cgroup_cpu':False,'cgroup_tasks':False}
    monkeypatch.setattr(budgets,'production_checks',lambda s:checks)
    monkeypatch.setattr(sandbox,'native_probe',lambda:True)
    monkeypatch.setattr('zerorepo.rtl_web.settings.subprocess.run',lambda *a,**k:SimpleNamespace(
        returncode=0,stdout=json.dumps({'chat_import':True,'model_credentials':True})))
    monkeypatch.setattr(budgets,'host_memory',lambda:{'total':2*1024**3,'available':800*1024**2})
    result=selected.preflight(probe_runtime=True)
    assert result['capabilities']['chat']['available']
    assert not result['checks']['memory_budget']
    assert all(not result['capabilities'][k]['available'] for k in ['verify','generate','fix'])
    monkeypatch.setattr(budgets,'host_memory',lambda:{'total':2*1024**3,'available':500*1024**2})
    assert 'chat_memory_budget' in selected.preflight()['capabilities']['chat']['missing']


def test_production_worker_refuses_queued_job_when_resource_boundary_is_missing(settings,tmp_path,monkeypatch):
    from zerorepo.rtl_web.worker import Worker
    from zerorepo.rtl_web import budgets,sandbox,jobs
    settings.development=False
    settings.agent_config=tmp_path/'agent.yaml';settings.agent_config.write_text('llm: {}\n')
    worker=Worker(settings);worker.heartbeat()
    sid=worker.store.create_session('resource-gate',{})['session_id']
    operation,_=worker.store.accept_operation(sid,'queued',{'kind':'verify','context_ref':{'case_id':'e203','version_id':'synthetic'}})
    operation=worker.store.claim()
    monkeypatch.setattr(budgets,'production_checks',lambda s:{'memory_budget':True,'disk_space':True,
        'job_volume':False,'cgroup_memory':False,'cgroup_cpu':False,'cgroup_tasks':False})
    monkeypatch.setattr(sandbox,'native_probe',lambda:True)
    monkeypatch.setattr(jobs,'prepare_job',lambda *a,**k:pytest.fail('Unbounded worker prepared a job'))
    worker.execute(operation)
    result=worker.store.operation(operation['operation_id'])
    assert result['state']=='failed'
    assert result['error_code']=='dependency_unavailable'
    assert '执行内存限制未生效' in result['error']
