import pytest
from zerorepo.rtl_impl.rtl_memory.ledger import MemoryLedger

def memory():
    return dict(memory_id='synthetic-rule', case_id='e203', scope='public_reviewed', owner=None,
                title='握手', lesson='检查 backpressure 下的保持条件', applicability=['ready/valid'], limitations=['有限仿真'],
                source_run_id='source-a', backend='test', evidence_refs=[{'kind':'artifact','id':'source-log','sha256':'0'*64}])

def test_revisions_and_retirement(tmp_path):
    ledger=MemoryLedger(tmp_path/'memory')
    first=ledger.add(memory())
    assert ledger.add(memory()) == first
    assert ledger.approved('e203', None) == []
    ledger.review(first['revision_id'], 'approved', 'source checked', first['evidence_refs'])
    assert len(ledger.approved('e203', None)) == 1
    second=ledger.add({**memory(),'lesson':'同时检查复位边界','parent_revision_id':first['revision_id']})
    ledger.review(first['revision_id'], 'superseded', 'new boundary evidence', first['evidence_refs'], second['revision_id'])
    assert ledger.get(first['revision_id'])['lesson'] == memory()['lesson']
    assert not ledger.approved('e203',None)
    ledger.review(second['revision_id'],'approved','checked',first['evidence_refs'])
    assert ledger.approved('e203',None)[0]['revision_id'] == second['revision_id']

def test_scope_and_tamper(tmp_path):
    ledger=MemoryLedger(tmp_path/'memory')
    m=ledger.add({**memory(),'scope':'private_session','owner':'visitor-a'})
    ledger.review(m['revision_id'],'approved','checked',m['evidence_refs'])
    assert not ledger.approved('e203','visitor-b')
    assert ledger.approved('e203','visitor-a')
    with pytest.raises(ValueError):ledger.get('../escape')

def test_legacy_projection_keeps_prior_content_without_extra_headers(tmp_path):
    import json
    from zerorepo.rtl_impl.rtl_memory.store import RTLMemoryStore
    from zerorepo.rtl_impl.rtl_memory.schemas import RTLMemoryHeader
    store=RTLMemoryStore(tmp_path/'legacy')
    header=RTLMemoryHeader(memory_id='fixture',type='repair_outcome',stage='debug')
    path=store.upsert_memory(header,'First content')
    store.upsert_memory(header,'Revised content')
    assert 'Revised content' in path.read_text()
    saved=[json.loads(p.read_text())['content'] for p in (store.root/'legacy_revisions').glob('*.json')]
    assert any('First content' in content for content in saved)
    assert len(store.scan_headers())==1
