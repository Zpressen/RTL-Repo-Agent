import json
import pytest

from zerorepo.rtl_web.artifacts import Artifacts, parse_report, signal_mismatches
from zerorepo.rtl_web.import_case import import_case
from zerorepo.rtl_web.recorded_history import prepare_history, expanded_bundle
from zerorepo.rtl_web.schemas import DemoError, Validation


def test_quoted_per_output_counts_are_not_sample_totals():
    text = "Hint: Output 'wb_dat_o' has 23729 mismatches. First mismatch occurred at time 100.\nSummary:\n  system_verify: FAIL\n"
    assert signal_mismatches(text) == [{'signal': 'wb_dat_o', 'count': 23729, 'first_failure_ticks': '100'}]
    stats = parse_report(text)
    assert stats['total_samples'] is None and stats['mismatched_samples'] is None
    assert not stats['simulation_completed']  # Generic parser remains conservative.


def test_sdc_journal_binding_tamper_rejected_before_publication(settings, ledger, monkeypatch):
    import zerorepo.rtl_web.recorded_history as history
    settings = settings.for_case('sdc_controller_system')
    if not settings.source.is_dir():
        pytest.skip('Local SDC artifacts absent')
    real_sha = history.sha
    monkeypatch.setattr(history, 'sha', lambda p: '0' * 64 if p.name == 'run_record.json' else real_sha(p))
    with pytest.raises(DemoError, match='校验失败'):
        prepare_history(settings, ledger, {'case_id': 'sdc_controller_system', 'artifacts': []})
    assert ledger.list_records('validation') == []


def test_sdc_actual_17_trials_wave_counts_and_true_baselines(settings, ledger):
    settings = settings.for_case('sdc_controller_system')
    if not settings.source.is_dir():
        pytest.skip('Local SDC artifacts absent')
    b = import_case(settings, ledger)
    original = json.dumps(b, sort_keys=True)
    expanded = prepare_history(settings, ledger, b)
    run, = expanded['debug_history']['runs']
    vals = {v['validation_id']: v for v in run['validations']}
    attempts = run['attempts']
    initial = vals[run['initial_validation_id']]
    assert len(attempts) == 17
    assert initial['simulation_completed'] and initial['verdict'] == 'fail'
    assert initial['first_failure_ticks'] == '5'
    assert len(initial['signal_mismatches']) == 7 and not initial.get('waveform_artifact_id')
    assert initial['signal_mismatches'][0] == {'signal': 'wb_dat_o', 'count': 23729, 'first_failure_ticks': '100'}
    assert [a['trial_no'] for a in attempts if a['decision'] == 'rolled_back'] == [1, 2, 8, 15]
    assert attempts[2]['baseline_version_id'] == initial['version_id']
    assert attempts[8]['baseline_version_id'] == attempts[6]['candidate_version_id']
    assert attempts[15]['baseline_version_id'] == attempts[13]['candidate_version_id']
    assert attempts[16]['baseline_version_id'] == attempts[15]['candidate_version_id']
    art = Artifacts(settings.data, ledger)
    for a in attempts:
        v = vals[a['validation_id']]
        assert a['lint_pass'] and a['simulation_completed'] and v['simulation_completed']
        assert v['waveform_artifact_id'] and v['marker_status'] == 'verified'
        assert v['signal_counter_status'] == 'verified'
        assert v['total_samples'] is None and v['mismatched_samples'] is None
        assert 'sd_cmd_oe_o_dut' in v['signal_names'] and 'int_a_ref' in v['signal_names']
        Validation.model_validate(v)
        index = json.loads(art.file(ledger.get('artifact', v['waveform_index_artifact_id'])).read_text())
        assert (index['validation_id'], index['version_id'], index['waveform_sha256']) == (v['validation_id'], v['version_id'], v['waveform_sha256'])
    before = vals[attempts[15]['validation_id']]
    assert before['signal_mismatches'] == [{'signal': 'sd_dat_out_o', 'count': 998, 'first_failure_ticks': '40'}]
    final = vals[run['final_validation_id']]
    assert final['verdict'] == 'pass' and final['signal_counter_status'] == 'verified'
    assert final['waveform_sha256'] == b['validations'][-1]['waveform_sha256']
    assert final['signal_mismatches'] == [] and attempts[-1]['debug']['signals'] == []
    assert final['version_id'] == attempts[-1]['candidate_version_id']
    assert json.dumps(ledger.get('bundle', b['bundle_id']), sort_keys=True) == original
    assert expanded_bundle(ledger, b)['debug_history'] == expanded['debug_history']
    assert '/home/mokita' not in json.dumps(expanded) and 'codex_private' not in json.dumps(expanded)
    from zerorepo.rtl_web.waveform import read_vcd, verify_signal_counters
    wave = ledger.get('artifact', before['waveform_artifact_id'])
    parsed = read_vcd(str(art.file(wave)), wave['sha256'])
    with pytest.raises(DemoError, match='计数不一致'):
        verify_signal_counters(parsed, b['stats_fields'], [{'signal': 'sd_dat_out_o', 'count': 999, 'first_failure_ticks': '40'}], 'fail')
    with pytest.raises(DemoError, match='时刻不一致'):
        verify_signal_counters(parsed, b['stats_fields'], [{'signal': 'sd_dat_out_o', 'count': 998, 'first_failure_ticks': '41'}], 'fail')
