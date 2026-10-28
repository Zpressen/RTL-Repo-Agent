from zerorepo.rtl_impl.rtl_memory.adapter import MemoryAdapter, freeze_snapshot
from zerorepo.rtl_impl.rtl_memory.ledger import MemoryLedger
from test_rtl_memory_ledger import memory
import pytest

def test_provided_is_not_applied_and_fail_is_fail(tmp_path):
    ledger=MemoryLedger(tmp_path/'library'); m=ledger.add(memory()); ledger.review(m['revision_id'],'approved','checked',m['evidence_refs'])
    path, digest=freeze_snapshot(ledger,'e203',None,tmp_path/'inputs',{})
    adapter=MemoryAdapter(path,digest,tmp_path/'events','outer-b','inner-b')
    adapter.query(); adapter.read(m['revision_id'])
    assert not any(e['kind']=='applied' for e in adapter.events())
    adapter.declare(m['revision_id'],'apply','test',['unit.v'],[])
    adapter.observe('candidate-1', {'modified':['unit.v'],'added':[],'removed':[]}, '1'*64, 'fail')
    assert any(e['kind']=='applied' for e in adapter.events())
    assert adapter.events()[-1]['verdict']=='fail'
    adapter.disposition('candidate-1','accepted')
    assert adapter.events()[-1]['verdict']=='fail'
    adapter.final_validation('1'*64,'fail','3'*64,'4'*64)
    assert adapter.events()[-1]['validation_level']=='final_system'
    assert adapter.events()[-1]['verdict']=='fail'
    adapter.disposition('candidate-1','rolled_back')
    before=len(adapter.events())
    adapter.final_validation('1'*64,'pass','5'*64,'4'*64)
    assert len(adapter.events())==before
    restored=MemoryAdapter(path,digest,tmp_path/'events','outer-b','inner-b')
    assert len(restored.events())==len(adapter.events())
    with pytest.raises(ValueError):restored.read('foreign')
    with pytest.raises(ValueError):MemoryAdapter(path,'2'*64,tmp_path/'events','outer-b','inner-b')

def test_without_diff_never_adopted(tmp_path):
    path,digest=freeze_snapshot(None,'e203',None,tmp_path/'inputs',{})
    adapter=MemoryAdapter(path,digest,tmp_path/'events','outer-b','inner-b')
    assert adapter.query()['memories']==[]
    with pytest.raises(ValueError):adapter.declare('fake','apply','claim',['../bad'],[])

def test_query_and_declaration_budgets(tmp_path):
    path,digest=freeze_snapshot(None,'e203',None,tmp_path/'inputs',{})
    adapter=MemoryAdapter(path,digest,tmp_path/'events','outer','inner')
    for args in [{'limit':6},{'signals':'bad'},{'failure_type':'x'*241}]:
        with pytest.raises(ValueError):adapter.query(**args)


def test_native_session_records_fail_and_keeps_snapshot_on_resume(run_descriptor,tmp_path,monkeypatch):
    from test_codex_debug_mcp import FakeReviewer, EDITED_RTL
    from zerorepo.rtl_impl.codex_debug.session import CodexDebugSession
    from zerorepo.rtl_impl.codex_debug import session as session_module
    from zerorepo.rtl_impl.codex_debug.schemas import CodexDebugRunDescriptor
    ledger=MemoryLedger(tmp_path/'library');m=ledger.add(memory());ledger.review(m['revision_id'],'approved','checked',m['evidence_refs'])
    path,hash_value=freeze_snapshot(ledger,'e203',None,tmp_path/'inputs',{})
    descriptor=CodexDebugRunDescriptor.model_validate({**run_descriptor.model_dump(), 'memory_snapshot_path':path,
                'memory_snapshot_sha256':hash_value,'outer_run_id':'web-run-b','case_id':'e203'})
    monkeypatch.setattr(session_module,'check_syntax',lambda *args,**kwargs:(True,'ok'))
    session=CodexDebugSession(descriptor,reviewer=FakeReviewer(descriptor.debug_workdir))
    try:
        assert session.query_rtl_memories()['memories'][0]['revision_id']==m['revision_id']
        session.read_rtl_memory(m['revision_id'])
        with pytest.raises(ValueError):session.record_memory_application(m['revision_id'],'apply','bad',['../outside.v'])
        session.record_memory_application(m['revision_id'],'apply','test',['top.v'])
        descriptor.top_rtl.write_text(EDITED_RTL)
        result=session.validate_rtl_changes('evaluate')
        session.validate_rtl_changes('accept',candidate_id=result['candidate_id'])
        events=session.memory_adapter.events()
        assert any(e['kind']=='applied' and e['outer_run_id']=='web-run-b' and e['internal_run_id']==descriptor.run_id for e in events)
        assert events[-1]['verdict']=='fail' and events[-1]['disposition']=='accepted'
        count=len(events)
    finally:session.close()
    restored=CodexDebugSession(descriptor,reviewer=FakeReviewer(descriptor.debug_workdir))
    assert len(restored.memory_adapter.events())==count
    restored.close()
    path.write_text('{}')
    with pytest.raises(ValueError,match='snapshot changed'):
        CodexDebugRunDescriptor.model_validate(descriptor.model_dump())

from test_codex_debug_mcp import run_descriptor
