import pytest
from evidence_fixtures import example_bundle
from zerorepo.rtl_web.chat import evidence

@pytest.mark.parametrize('panel',['spec','architecture','code','verify','repair'])
def test_workspace_evidence_does_not_depend_on_story(settings,ledger,monkeypatch,panel):
    b=example_bundle(settings,ledger)
    session=ledger.create_session('fixture-session',{'case_id':'e203'})['session_id']
    def broken(*a,**k):raise AssertionError('workspace must not load a story')
    monkeypatch.setattr('zerorepo.rtl_web.stories.story_view',broken)
    payload=evidence(settings,ledger,{'session_id':session,'context_ref':{'case_id':'e203','view':'workspace','workspace_panel':panel,'validation_id':'fixture-check2','version_id':'fixture-v2'}})
    assert payload['context_ref']['workspace_panel']==panel
    assert 'story_readiness' not in payload
    assert payload['validation']['version_id']=='fixture-v2'
