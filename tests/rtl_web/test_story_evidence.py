import json
import pytest
from zerorepo.rtl_web.stories import prepare_story, publish_story, story_view, memory_digest, import_story
from story_fixtures import story_fixture
from deployment_fixtures import historical_store

def archived(store):
    data=story_fixture(); data['material_kind']='real'  # Protocol exercise only, isolated temporary Store.
    m=dict(memory_id='fixture-memory',revision_id='fixture-revision',title='Fixture lesson',lesson='Check handshake',
           applicability=['one task'],limitations=['synthetic test only'],source_run_id='history-e203',backend='fixture',
           evidence_refs=[],parent_revision_id=None,source_version_id=None,validation_level='unverified',state='approved_active')
    m['content_sha256']=memory_digest(m);data['memories']=[m]
    return prepare_story(data)

def test_archived_not_used_and_tamper(tmp_path):
    store,_=historical_store(tmp_path/'source')
    data=archived(store);publish_story(store,data,activate=True)
    assert story_view(store,'e203')['experience']['state']=='archived_only'
    broken={**data,'memories':[{**data['memories'][0],'lesson':'tampered'}]}
    with pytest.raises(ValueError):prepare_story(broken)
    with pytest.raises(Exception):story_view(store,'sdc_controller_system',data['story_id'])

def test_dry_run_has_no_active_root_and_collision_rolls_back(settings,ledger,tmp_path):
    data=prepare_story({**story_fixture(),'material_kind':'real'})
    path=tmp_path/'review.json';path.write_text(json.dumps({'story':data,'records':[],'files':[]}))
    assert import_story(settings,path,dry_run=True)['dry_run']
    assert ledger.control('story:e203') is None
    import_story(settings,path,activate=True)
    assert ledger.control('story:e203')==data['story_id']
    assert import_story(settings,path)['story_id']==data['story_id']
    value=json.loads(path.read_text());value['story']['source_fingerprint']='1'*64
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError):import_story(settings,path,activate=True)
    assert ledger.control('story:e203')==data['story_id']

def test_claimed_use_requires_objective_journal(tmp_path):
    store,_=historical_store(tmp_path/'source');data=archived(store)
    data['story_id']=None
    data['uses']=[dict(use_id='claimed',revision_id='fixture-revision',run_id='history-e203',backend='fixture',snapshot_sha256='0'*64,
                       events=[dict(event_id='invented',kind='applied',event_artifact_id='missing')])]
    with pytest.raises(Exception):publish_story(store,prepare_story(data),activate=True)

@pytest.mark.parametrize('verdict',['pass','fail'])
def test_actual_journal_version_binding_and_static_projection(tmp_path,verdict):
    """Protocol fixtures only: no real repair or model use is claimed."""
    from zerorepo.rtl_web.artifacts import Artifacts
    from zerorepo.rtl_web.stories import export_story_static, digest
    from zerorepo.rtl_web.settings import Settings
    from test_seed import config
    store,_=historical_store(tmp_path/'source');data=archived(store);data['story_id']=None
    art=Artifacts(store.root,store);src=tmp_path/'candidate';src.mkdir()
    (src/'dut.v').write_text('module dut; endmodule\n')
    baseline=art.snapshot(src,'fixture-b-before','fixture-b')
    (src/'dut.v').write_text('module dut; wire changed; endmodule\n')
    candidate=art.snapshot(src,'fixture-b-candidate','fixture-b',parent=baseline['version_id'])
    report=tmp_path/'candidate-report.json';report.write_text(json.dumps({'stdout':'Summary:\n system_verify: '+verdict.upper()+'\n'}))
    report=art.add(report,'report',display=True)
    val=dict(validation_id='fixture-b-check',run_id='fixture-b',version_id=candidate['version_id'],kind='final_system',verdict=verdict,
             simulation_completed=True,report_artifact_id=report['artifact_id'])
    store.put('validation',val['validation_id'],val,immutable=True)
    store.put('run','fixture-b',dict(run_id='fixture-b',case_id='e203',origin='historical',versions=[candidate['version_id']],validations=[val['validation_id']]),immutable=True)
    events=[]
    for sequence,kind in enumerate(['provided','applied','validation_observed'],1):
        proof=dict(sequence=sequence,kind=kind,revision_id='fixture-revision',outer_run_id='fixture-b',snapshot_sha256='1'*64)
        event=dict(event_id='fixture-event-'+kind,kind=kind)
        if kind=='applied':
            proof.update(tree_sha256=candidate['tree_sha256'],target_files=['dut.v'],diff_sha256=digest({'modified':['dut.v'],'added':[],'removed':[]}))
            event['candidate_version_id']=candidate['version_id']
        if kind=='validation_observed':
            proof.update(tree_sha256=candidate['tree_sha256'],verdict=verdict,report_sha256=report['sha256'])
            event['validation_id']=val['validation_id']
        path=tmp_path/(kind+'.json');path.write_text(json.dumps(proof));artifact=art.add(path,'memory_event')
        event['event_artifact_id']=artifact['artifact_id'];events.append(event)
    data['uses']=[dict(use_id='fixture-use',revision_id='fixture-revision',run_id='fixture-b',backend='fixture',snapshot_sha256='1'*64,events=events)]
    conditions={k:'same' for k in ['input','spec','model','profile','verifier','resources','budget']}
    data['comparisons']=[dict(comparison_id='fixture-comparison',with_memory_run_id='fixture-b',without_memory_run_id='history-e203',with_conditions=conditions,without_conditions={**conditions,'model':'different'},limitations=['Synthetic single observation'])]
    data=prepare_story(data);publish_story(store,data,activate=True)
    view=story_view(store,'e203')
    assert view['experience']['state']=='partial'
    assert view['experience']['comparisons'][0]['state']=='not_attributable'
    assert 'cost' not in view['experience']['comparisons'][0]
    assert next(r for r in view['runs'] if r['run_id']=='fixture-b')['validations'][0]['verdict']==verdict
    settings=Settings(config(tmp_path,store.root));out=tmp_path/'static'
    exported=export_story_static(settings,store,'e203',out)
    assert exported['story_id']==data['story_id']
    assert exported['content_urls'] and exported['waveform_urls']
    assert not any('memory_event' in p.read_text() for p in out.rglob('*.json'))
    broken={**data,'story_id':None,'uses':[{**data['uses'][0],'run_id':'history-e203'}]}
    with pytest.raises(ValueError):publish_story(store,prepare_story(broken))

def test_review_memory_dry_run_and_retirement(tmp_path):
    from zerorepo.rtl_web.stories import review_memory
    from zerorepo.rtl_web.settings import Settings
    from zerorepo.rtl_impl.rtl_memory.ledger import MemoryLedger
    from test_seed import config
    store,_=historical_store(tmp_path/'source');settings=Settings(config(tmp_path,store.root))
    report=store.get('artifact',store.get('validation','e203-check')['report_artifact_id'])
    refs=[dict(kind='artifact',id=report['artifact_id'],sha256=report['sha256'])]
    value=dict(schema_version='rtl-memory-review-v1',reviewer='test-maintainer',decision='approved',reason='Protocol test',evidence_refs=refs,
               revision=dict(memory_id='synthetic-review',case_id='e203',scope='public_reviewed',owner=None,
                             title='Synthetic',lesson='Protocol only',source_run_id='history-e203',backend='fixture',evidence_refs=refs))
    path=tmp_path/'review.json';path.write_text(json.dumps(value))
    assert review_memory(settings,path,True)['dry_run']
    library=MemoryLedger(settings.memory_library)
    assert not library.state()['revisions']
    result=review_memory(settings,path)
    assert library.approved('e203',None)[0]['revision_id']==result['revision_id']
    value['decision']='retired';value['reason']='Synthetic retirement evidence';path.write_text(json.dumps(value))
    review_memory(settings,path)
    assert not library.approved('e203',None)
    value['decision']='approved';path.write_text(json.dumps(value))
    with pytest.raises(ValueError,match='Retired'):review_memory(settings,path,True)
    with pytest.raises(ValueError,match='Retired'):review_memory(settings,path)
