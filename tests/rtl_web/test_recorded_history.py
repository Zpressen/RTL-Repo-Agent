import json
import pytest
from zerorepo.rtl_web.recorded_history import prepare_history, expanded_bundle
from zerorepo.rtl_web.schemas import DemoError
from zerorepo.rtl_web.artifacts import Artifacts

def test_two_runs_baselines_reports_and_no_inherited_wave(settings, ledger, bundle):
    original = json.dumps(bundle, sort_keys=True)
    b = prepare_history(settings, ledger, bundle)
    first, second = b['debug_history']['runs']
    assert [len(r['attempts']) for r in [first,second]] == [30,9]
    for run in [first,second]:
        vals={v['validation_id']:v for v in run['validations']}
        initial=vals[run['initial_validation_id']]
        assert initial['marker_status']=='verified'
        for a in run['attempts']:
            val=vals[a['validation_id']]
            ver=next(v for v in run['versions'] if v['version_id']==a['candidate_version_id'])
            assert ver['parent_version_id']==a['baseline_version_id']
            assert val['version_id']==a['candidate_version_id'] and val['run_id']==run['run_id']
            if not a['simulation_completed']:
                assert val['kind']=='syntax' and not val.get('waveform_artifact_id')
                assert val['total_samples'] is None
            else:
                assert val['marker_status']=='verified'
    assert first['validations'][0]['mismatched_samples']==222
    assert first['validations'][-1]['mismatched_samples']==2
    assert second['validations'][0]['mismatched_samples']==2
    assert second['validations'][-1]['mismatched_samples']==0
    assert all(a['baseline_version_id'].endswith('-trial-5') for a in second['attempts'][5:])
    assert second['attempts'][8]['debug']['signals']==[]  # No inherited failure diagnosis on PASS.
    assert first['attempts'][21]['candidate_revision']==2
    assert first['attempts'][20]['decision']=='superseded'
    assert [a['trial_no'] for a in first['attempts'] if not a['simulation_completed']]==[1,11,17]
    assert json.dumps(ledger.get('bundle',bundle['bundle_id']),sort_keys=True)==original
    assert expanded_bundle(ledger,bundle)['debug_history']['runs'][0]['run_id']==first['run_id']
    from zerorepo.rtl_web.seed import _references, _strings
    assert ('run', first['source_run_id']) not in set(_references(first))
    assert first['source_run_id'] not in set(_strings(first))
    public=json.dumps(b)
    assert '/home/mokita' not in public and 'codex_private' not in public
    # All published wave JSONs retain their own candidate/version binding.
    art=Artifacts(settings.data,ledger)
    for run in [first,second]:
        for v in run['validations']:
            if v.get('waveform_index_artifact_id'):
                w=json.loads(art.file(ledger.get('artifact',v['waveform_index_artifact_id'])).read_text())
                assert (w['validation_id'],w['version_id'],w['waveform_sha256'])==(v['validation_id'],v['version_id'],v['waveform_sha256'])
    # An online fresh visitor must see the same original failure as static browsing.
    from fastapi.testclient import TestClient
    from zerorepo.rtl_web.api import create_app
    with TestClient(create_app(settings), base_url='http://127.0.0.1') as client:
        response = client.post('/api/sessions', json={'case_id': 'e203'}, headers={
            'Origin': 'http://127.0.0.1:5173', 'Idempotency-Key': 'original-history-session',
            'X-Demo-Request': '1',
        })
        assert response.status_code == 201, response.text[:300]
        selection = response.json()['selection']
        assert selection['validation_id'] == first['initial_validation_id']
        assert selection['run_id'] == first['run_id']
        assert selection['workspace_panel'] == 'verify'

def test_tampered_history_journal_fails_before_publication(settings,ledger,bundle,monkeypatch):
    import zerorepo.rtl_web.recorded_history as history
    real_sha=history.sha
    monkeypatch.setattr(history,'sha',lambda path:'0'*64 if path.name=='codex_validation_journal.jsonl' else real_sha(path))
    with pytest.raises(DemoError,match='校验失败'):
        prepare_history(settings,ledger,bundle)
    assert expanded_bundle(ledger,bundle)==bundle
