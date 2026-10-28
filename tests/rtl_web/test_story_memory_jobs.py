"""Trusted job snapshot contract; no subprocess or model execution."""
import json
import pytest
import yaml
from zerorepo.rtl_web.jobs import prepare_job, load_job
from zerorepo.rtl_web.schemas import DemoError
from zerorepo.rtl_impl.rtl_memory.ledger import MemoryLedger


def test_job_freezes_only_authorized_memory(settings,ledger,bundle,tmp_path,monkeypatch):
    from zerorepo.rtl_web import runtime
    monkeypatch.setattr(runtime,'verifier_manifest',lambda settings:[])
    session=ledger.create_session('snapshot-visitor',{'case_id':'e203'})
    other=ledger.create_session('other-visitor',{'case_id':'e203'})
    library=MemoryLedger(settings.memory_library)
    for owner in [session['session_id'],other['session_id']]:
        m=library.add(dict(memory_id='fixture-'+owner,case_id='e203',scope='private_session',owner=owner,
                           title='Synthetic rule',lesson='Test only',source_run_id='source-a',backend='fixture',
                           evidence_refs=[dict(kind='artifact',id='fixture-proof',sha256='0'*64)]))
        library.review(m['revision_id'],'approved','fixture review',m['evidence_refs'])
    agent=tmp_path/'agent.yaml';agent.write_text('llm: {}\n');settings.agent_config=agent
    version=bundle['versions'][0]
    op,_=ledger.accept_operation(session['session_id'],'fixture-op',dict(kind='verify',context_ref={'case_id':'e203','run_id':version['run_id'],'version_id':version['version_id']}))
    descriptor=prepare_job(settings,ledger,op);job=load_job(descriptor)
    snap=descriptor.parent/job['inputs']['memory']['path']
    value=json.loads(snap.read_text())
    assert len(value['memories'])==1
    assert value['memories'][0]['memory_id']=='fixture-'+session['session_id']
    assert 'owner' not in value['memories'][0]
    assert snap.stat().st_mode & 0o222 == 0
    child=yaml.safe_load((descriptor.parent/job['inputs']['config']).read_text())
    assert 'memory_library' not in child
    snap.chmod(0o600);snap.write_text('{}')
    with pytest.raises(DemoError,match='任务经验快照发生变化'):load_job(descriptor)
