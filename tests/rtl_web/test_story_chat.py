import pytest
from zerorepo.rtl_web.chat import validate_context,evidence
from zerorepo.rtl_web.schemas import DemoError
from zerorepo.rtl_web.stories import prepare_story,publish_story
from story_fixtures import story_fixture

def test_unknown_or_foreign_memory_cannot_borrow_context(ledger):
    session=ledger.create_session('one',{'case_id':'e203'})
    sid=session['session_id']
    with pytest.raises(DemoError):validate_context(ledger,sid,{'case_id':'e203','memory_revision_id':'foreign'})
    data=prepare_story({**story_fixture(),'material_kind':'real'})
    publish_story(ledger,data,activate=True)
    with pytest.raises(DemoError):validate_context(ledger,sid,{'case_id':'e203','story_id':data['story_id'],'memory_revision_id':'foreign'})
    assert ledger.session(sid)['messages']==[]

def test_no_ppa_claim_in_chat_evidence(settings,ledger,bundle):
    session=ledger.create_session('qa',{'case_id':'e203'})
    proof=evidence(settings,ledger,{'session_id':session['session_id'],'context_ref':{'case_id':'e203','view':'optimization'}})
    assert proof['page']=='optimization'
    assert proof['story_readiness']['optimization']['state']=='awaiting_data'
    assert 'selected_memory' not in proof
    assert ledger.session(session['session_id'])['messages']==[]

def test_selected_memory_has_bounded_public_evidence(settings,ledger,bundle,tmp_path):
    from zerorepo.rtl_web.artifacts import Artifacts
    from zerorepo.rtl_web.stories import memory_digest
    session=ledger.create_session('selected-memory',{'case_id':'e203'})
    path=tmp_path/'audit.json';path.write_text('{"synthetic_audit":true}')
    private=Artifacts(settings.data,ledger).add(path,'audit')
    data={**story_fixture(),'material_kind':'real'}
    memory=dict(memory_id='fixture-memory',revision_id='fixture-revision',title='Synthetic',lesson='Protocol only',applicability=['test'],limitations=['not real reuse'],
                source_run_id=bundle['source_run_id'],backend='fixture',validation_level='unverified',state='approved_active',
                evidence_refs=[dict(kind='artifact',id=bundle['spec_artifact_id']),dict(kind='artifact',id=private['artifact_id'])])
    memory['content_sha256']=memory_digest(memory);data['memories']=[memory]
    data=prepare_story(data);publish_story(ledger,data,activate=True)
    ctx=validate_context(ledger,session['session_id'],dict(case_id='e203',view='experience',story_id=data['story_id'],memory_revision_id='fixture-revision'))
    proof=evidence(settings,ledger,dict(session_id=session['session_id'],context_ref=ctx))
    assert proof['page']=='experience' and proof['selected_memory']['revision_id']=='fixture-revision'
    assert proof['memory_uses']==[] and proof['memory_summary_limits']['uses_total']==0
    assert sum(len(item['content']) for item in proof['available_artifacts'])<=64000
    assert private['artifact_id'] not in {item['artifact_id'] for item in proof['available_artifacts']}
    assert ledger.session(session['session_id'])['messages']==[]
