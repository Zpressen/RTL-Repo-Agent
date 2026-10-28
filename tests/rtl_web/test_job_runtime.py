import json
from pathlib import Path
import pytest
from zerorepo.rtl_web.jobs import load_job,prepare_job
from zerorepo.rtl_web.schemas import DemoError
from deployment_fixtures import historical_store


def test_job_is_current_input_only_and_detects_tampering(tmp_path,settings):
    store,bundles=historical_store(settings.data)
    cfg=tmp_path/'agent.yaml';cfg.write_text('llm: {}\n')
    settings.agent_config=cfg
    # A real oracle is not required for this portable preparation test.
    import zerorepo.rtl_web.runtime as runtime
    from unittest.mock import patch
    sid=store.create_session('job',{'case_id':'e203'})['session_id']
    op={'operation_id':'op-test','run_id':'run-test','session_id':sid,'kind':'verify',
        'context_ref':{'case_id':'e203','run_id':'history-e203','version_id':'e203-v1'}}
    with patch.object(runtime,'verifier_manifest',return_value=[]):
        path=prepare_job(settings,store,op)
    data=load_job(path)
    assert data['run_id']=='run-test'
    assert 'session.key' not in path.read_text()
    assert 'state.sqlite3' not in path.read_text()
    assert op['session_id'] not in path.read_text()
    assert data['kg_partition']=='web-run-test'
    spec=path.parent/'job_inputs/spec.md';spec.chmod(0o600);spec.write_text('tampered')
    with pytest.raises(DemoError,match='输入'):load_job(path)


def test_job_cli_does_not_open_shared_store(tmp_path,settings,monkeypatch):
    import zerorepo.rtl_web.runtime as runtime
    store,bundles=historical_store(settings.data)
    cfg=tmp_path/'agent.yaml';cfg.write_text('llm: {}\n');settings.agent_config=cfg
    sid=store.create_session('execute-job',{'case_id':'e203'})['session_id']
    op={'operation_id':'op-run','run_id':'run-ledger-free','session_id':sid,'kind':'verify',
        'context_ref':{'case_id':'e203','run_id':'history-e203','version_id':'e203-v1'}}
    monkeypatch.setattr(runtime,'verifier_manifest',lambda s: [])
    path=prepare_job(settings,store,op)
    monkeypatch.setenv('ZEROREPO_RTL_KG_PARTITION','test-original')
    monkeypatch.setenv('ZEROREPO_WEB_JOB','0')
    monkeypatch.setattr(runtime,'Store',lambda *a,**kw:pytest.fail('Runtime opened shared ledger'))
    monkeypatch.setattr(runtime,'verify_only',lambda s,merged,out:{'verdict':'pass','rtl_dir':str(merged)})
    result=runtime.execute_job(path)
    assert result['operation_id']=='op-run'
    assert result['release_id']==settings.release_id
    assert (path.parent/'result.json').is_file()


def test_missing_archived_contract_is_truthful(tmp_path,settings):
    from zerorepo.rtl_web.jobs import contracts_for
    store,bundles=historical_store(settings.data)
    with store.connect(True) as c:
        c.execute('INSERT INTO historical_inputs VALUES(?,?,?,?)',
                  ('e203','history-e203','contracts',json.dumps({'status':'missing'})))
    with pytest.raises(DemoError) as error:contracts_for(settings,store,'history-e203',None)
    assert error.value.code=='contracts_missing'
