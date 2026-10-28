import importlib.util
import json
from pathlib import Path
import pytest

def deployment():
    spec=importlib.util.spec_from_file_location('story_deployment',Path('scripts/rtl_demo/deployment.py'))
    module=importlib.util.module_from_spec(spec)
    import sys
    sys.modules[spec.name]=module;spec.loader.exec_module(module)
    return module

def test_static_story_cannot_mix_releases(tmp_path):
    module=deployment();path=tmp_path/'design/cases/e203/stories/manifest.json';path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'case_id':'e203','story_id':'story-other','fingerprint':'0'*64}))
    with pytest.raises(ValueError):module.validate_story_binding(tmp_path,{'stories':{'e203':'story-current'}},'e203')
    path.unlink()
    with pytest.raises(ValueError):module.validate_story_binding(tmp_path,{'stories':{'e203':'story-current'}},'e203')
    module.validate_story_binding(tmp_path,{},'e203')

def test_agent_target_refuses_legacy_design_activation(monkeypatch,tmp_path):
    module=deployment()
    monkeypatch.setattr(module,'_record',lambda *args:dict(state='prepared',candidate=str(tmp_path)))
    monkeypatch.setattr(module,'checked',lambda *args:dict(target_origin='https://agent.deepvalleychip.cn'))
    monkeypatch.setattr(module,'privileged',lambda:pytest.fail('must refuse before host mutation'))
    with pytest.raises(module.DeploymentError,match='legacy design activation is disabled'):
        module.activate('agent-new',dry_run=True)

def test_story_binding_check_is_stdlib_only(tmp_path):
    import hashlib,subprocess,sys
    script=Path('scripts/rtl_demo/deployment.py').resolve()
    record=dict(story_id='story-portable',source_fingerprint='1'*64)
    fingerprint=hashlib.sha256(json.dumps(record,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    path=tmp_path/'design/cases/e203/stories/manifest.json';path.parent.mkdir(parents=True)
    path.write_text(json.dumps(dict(case_id='e203',story_id='story-portable',fingerprint=fingerprint)))
    seed=dict(stories={'e203':'story-portable'},records=[dict(kind='story',id='story-portable',payload=record)])
    command="import runpy; m=runpy.run_path(%r); m['validate_story_binding'](%r,%r,'e203')"%(str(script),str(tmp_path),seed)
    result=subprocess.run([sys.executable,'-S','-c',command],cwd=tmp_path,env={'PATH':'/no-tools','PYTHONPATH':''},capture_output=True,text=True)
    assert result.returncode==0,result.stderr

def test_acceptance_model_keeps_agent_target_explicit():
    from zerorepo.rtl_web.deployment_models import AcceptanceRecord
    value=AcceptanceRecord(criterion='SC-001',release_id='agent-new',host='39.107.243.176',origin='https://agent.deepvalleychip.cn',state='not_run',evidence=[])
    assert value.origin=='https://agent.deepvalleychip.cn'
    with pytest.raises(ValueError):AcceptanceRecord.model_validate({**value.model_dump(),'origin':'https://other.invalid'})

def test_recovery_restores_only_story_roots_and_keeps_new_sessions(tmp_path):
    from zerorepo.rtl_web.store import Store
    module=deployment();store=Store(tmp_path/'state');first=store.create_session('first',{})
    store.put('story','story-old',dict(case_id='e203'))
    store.put('story','story-new',dict(case_id='e203'))
    store.control('story:e203','story-old');roots=module.story_roots(store.db)
    store.control('story:e203','story-new');store.control('unrelated','keep')
    second=store.create_session('after-upgrade',{})
    module.restore_story_roots(store.db,roots)
    assert store.control('story:e203')=='story-old' and store.control('unrelated')=='keep'
    assert store.session(second['session_id']) and store.session(first['session_id'])
    with pytest.raises(ValueError):module.restore_story_roots(store.db,{'story:e203':'missing'})
    assert store.control('story:e203')=='story-old'
