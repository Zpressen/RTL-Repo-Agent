import json
import pytest

from zerorepo.rtl_web.artifacts import Artifacts
from zerorepo.rtl_web.import_case import import_case
from zerorepo.rtl_web.recorded_history import prepare_history, expanded_bundle
from zerorepo.rtl_web.recorded_react_history import reconstruct
from zerorepo.rtl_web.schemas import DemoError, Validation


def test_aes_actual_snapshots_counts_rollback_and_sparse_probes(settings, ledger):
    settings = settings.for_case('aes_cipher_system_hard')
    if not settings.source.is_dir():
        pytest.skip('Local AES artifacts absent')
    b = import_case(settings, ledger)
    original = json.dumps(b, sort_keys=True)
    expanded = prepare_history(settings, ledger, b)
    run, = expanded['debug_history']['runs']
    vals = {v['validation_id']: v for v in run['validations']}
    attempts = run['attempts']
    initial = vals[run['initial_validation_id']]
    assert len(attempts) == 8
    assert initial['first_failure_ticks'] == '15'
    assert initial['signal_mismatches'] == [
        {'signal': 'text_out', 'count': 287, 'first_failure_ticks': '15'},
        {'signal': 'done', 'count': 12, 'first_failure_ticks': '305'},
    ]
    assert initial['simulation_completed'] and initial['verdict'] == 'fail'
    assert initial['total_samples'] is None and initial['mismatched_samples'] is None
    assert len(initial['probe_samples']) == 90 and not initial.get('waveform_artifact_id')
    assert [a['simulation_completed'] for a in attempts] == [True, True, True, False, True, True, True, True]
    assert [a['decision'] for a in attempts] == ['accepted'] * 3 + ['rolled_back', 'accepted', 'accepted', 'rolled_back', 'accepted']
    assert attempts[4]['baseline_version_id'] == attempts[2]['candidate_version_id']
    assert attempts[7]['baseline_version_id'] == attempts[5]['candidate_version_id']
    expected = [299, 270, 123, None, 120, 3, 279]
    for a, internal in zip(attempts, expected):
        v = vals[a['validation_id']]
        assert v.get('internal_mismatch_count') == internal
        assert v['total_samples'] is None and v['mismatched_samples'] is None
        assert not v.get('waveform_artifact_id')
        Validation.model_validate(v)
    syntax = vals[attempts[3]['validation_id']]
    assert syntax['kind'] == 'syntax' and syntax['probe_samples'] == []
    assert vals[attempts[6]['validation_id']]['probe_samples']  # Rejected candidate's VCD still existed until run_check.
    accepted = vals[attempts[5]['validation_id']]
    assert any(p['time_ticks'] == '545' for p in accepted['probe_samples'])
    rejected_points = vals[attempts[6]['validation_id']]['probe_samples']
    assert any(p['signal'] == 'dcnt' and p['time_ticks'] == '545' and p['dut'] != p['reference'] for p in rejected_points)
    assert all(p['dut'] == p['reference'] for p in accepted['probe_samples'] if p['signal'] == 'dcnt' and p['time_ticks'] == '545')
    final = vals[run['final_validation_id']]
    assert final['verdict'] == 'pass' and final['waveform_sha256'] == b['validations'][-1]['waveform_sha256']
    assert final['verification_scope'] == 'saved_final_result'
    assert final['total_samples'] is None  # Never infer a sample denominator from VCD duration.
    Validation.model_validate(final)
    art = Artifacts(settings.data, ledger)
    for version in run['versions']:
        assert len(version['file_manifest']) == 3  # Partial patch snapshots restored to full three-module RTL.
        art.version_path(ledger.get('version', version['version_id']))
    assert json.dumps(ledger.get('bundle', b['bundle_id']), sort_keys=True) == original
    assert expanded_bundle(ledger, b)['debug_history'] == expanded['debug_history']
    public = json.dumps(expanded)
    assert '/home/mokita' not in public and 'repo_react/' not in public
    # ZIP keeps this exact candidate and its true accepted baseline, including sparse evidence.
    from zerorepo.rtl_web.evidence import build_package
    import zipfile
    path = settings.data / 'aes-selected.zip'
    build_package(settings, ledger, 'aes_cipher_system_hard', attempts[7]['validation_id'], attempts[7]['before_validation_id'], path)
    with zipfile.ZipFile(path) as archive:
        manifest = json.loads(archive.read('manifest.json'))
        assert manifest['selection']['before_validation_id'] == attempts[5]['validation_id']
        assert any(v.get('probe_samples') for v in manifest['validations'])
        assert not any(name.endswith('.vcd') for name in archive.namelist())


def test_react_tamper_rejected_before_supplement(settings, ledger, monkeypatch):
    import zerorepo.rtl_web.recorded_react_history as history
    settings = settings.for_case('aes_cipher_system_hard')
    if not settings.source.is_dir():
        pytest.skip('Local AES artifacts absent')
    b = import_case(settings, ledger)
    real_sha = history.sha
    monkeypatch.setattr(history, 'sha', lambda p: '0' * 64 if p.name == 'patch_journal.jsonl' else real_sha(p))
    with pytest.raises(DemoError, match='校验失败'):
        prepare_history(settings, ledger, b)
    assert expanded_bundle(ledger, b) == b


def test_partial_snapshots_cannot_silently_use_wrong_before_bytes():
    rows = [{'step': 1, 'result': {'status': 'improved'}}, {'step': 2, 'result': {'status': 'rollback'}}]
    with pytest.raises(DemoError, match='校验失败'):
        reconstruct({'a.v': b'accepted'}, rows, [({'a.v': b'initial'}, {'a.v': b'accepted'}),
                                                 ({'a.v': b'unrelated'}, {'a.v': b'rejected'})])


def test_inverse_aes_edits_are_unverified_until_actual_check(settings, ledger):
    settings = settings.for_case('aes_inv_cipher_top_system')
    if not settings.source.is_dir():
        pytest.skip('Local inverse AES artifacts absent')
    b = import_case(settings, ledger)
    original = json.dumps(b, sort_keys=True)
    expanded = prepare_history(settings, ledger, b)
    run, = expanded['debug_history']['runs']
    vals = {v['validation_id']: v for v in run['validations']}
    attempts = run['attempts']
    assert len(attempts) == 4
    initial = vals[run['initial_validation_id']]
    assert initial['first_failure_ticks'] == '775'
    assert initial['signal_mismatches'] == [
        {'signal': 'text_out', 'count': 37, 'first_failure_ticks': '775'},
        {'signal': 'done', 'count': 1, 'first_failure_ticks': '1015'},
    ]
    assert len(initial['probe_samples']) == 437 and not initial.get('waveform_artifact_id')
    for a in attempts[:2]:
        v = vals[a['validation_id']]
        assert a['decision'] == 'accepted' and a['lint_pass'] is None
        assert not a['simulation_completed']
        assert v['kind'] == 'edit_only' and v['verdict'] == 'unverified'
        assert v['signal_mismatches'] == [] and v['probe_samples'] == []
        assert v['first_failure_ticks'] is None and not v.get('waveform_artifact_id')
        assert a['debug']['signals'] == [] and a['debug']['lint_pass'] is None
        assert next(e for e in run['events'] if e.get('trial_no') == a['trial_no'])['stage'] == 'repair'
        Validation.model_validate(v)
    third = vals[attempts[2]['validation_id']]
    assert third['simulation_completed'] and third['verdict'] == 'fail'
    assert third['signal_mismatches'][0]['count'] == 34
    assert third['signal_mismatches'][1]['count'] == 9
    assert third['first_failure_ticks'] == '805'
    assert len(third['probe_samples']) == 14 and not third.get('waveform_artifact_id')
    assert attempts[2]['before_validation_id'] == attempts[1]['validation_id']
    assert attempts[3]['baseline_version_id'] == attempts[2]['candidate_version_id']
    final = vals[run['final_validation_id']]
    assert final['verdict'] == 'pass' and final['verification_scope'] == 'saved_final_result'
    assert final['waveform_sha256'] == b['validations'][-1]['waveform_sha256']
    assert all(v['total_samples'] is None and v['mismatched_samples'] is None for v in run['validations'])
    assert all(len(v['file_manifest']) == 5 for v in run['versions'])
    assert not any(e['stage'] == 'syntax' for e in run['events'])
    assert json.dumps(ledger.get('bundle', b['bundle_id']), sort_keys=True) == original
    assert '/home/mokita' not in json.dumps(expanded)
    from fastapi.testclient import TestClient
    from zerorepo.rtl_web.api import create_app
    with TestClient(create_app(settings), base_url='http://127.0.0.1') as client:
        r = client.post('/api/sessions', json={'case_id': 'aes_inv_cipher_top_system'}, headers={
            'Origin': 'http://127.0.0.1:5173', 'X-Demo-Request': '1', 'Idempotency-Key': 'inverse-initial',
        })
        assert r.status_code == 201, r.text[:300]
        assert r.json()['selection']['validation_id'] == initial['validation_id']
