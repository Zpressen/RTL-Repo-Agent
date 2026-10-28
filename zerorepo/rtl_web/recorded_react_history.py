"""Import reviewed ReAct repairs, including partial snapshots and missing waves.

Rebuild full RTL trees only from recorded before/after bytes and the pinned final
tree. Never execute simulation, infer total sample counts, or reuse overwritten VCDs.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import tempfile

from .artifacts import Artifacts, atomic_json, safe_path, sha, tree_manifest
from .agent_trace import clean
from .schemas import DemoError
from .store import dump


def require(condition):
    if not condition:
        raise DemoError('history_mismatch', '修复日志、快照或验证来源校验失败。', 409)


def reconstruct(final, rows, snapshots):
    """Undo accepted patches then replay all trials, checking every saved byte."""
    current = dict(final)
    for row, (before, after) in reversed(list(zip(rows, snapshots, strict=True))):
        require(before.keys() == after.keys())
        if row['result']['status'] != 'rollback':
            require(all(current.get(name) == value for name, value in after.items()))
            current.update(before)
    initial = dict(current)
    trials = []
    baseline = 0
    for row, (before, after) in zip(rows, snapshots, strict=True):
        require(all(current.get(name) == value for name, value in before.items()))
        candidate = {**current, **after}
        trials.append((dict(current), candidate, baseline))
        if row['result']['status'] != 'rollback':
            current, baseline = candidate, row['step']
    require(current == final)
    return initial, trials


def signal_counts(text):
    return [{'signal': name, 'count': int(count), 'first_failure_ticks': time}
            for name, count, time in re.findall(
                r'Output\s+(\w+)\s+(?:signal\s+)?has\s+(\d+)\s+mismatches\.\s+First at time\s+(\d+)', text)]


PAIRS = [
    ('text_out', ['tb.text_out_ref', 'tb.good1.text_out'], ['tb.text_out_dut', 'tb.top_module1.text_out']),
    ('done', ['tb.done_ref', 'tb.good1.done'], ['tb.done_dut', 'tb.top_module1.done']),
    ('dcnt', ['tb.good1.dcnt'], ['tb.top_module1.dcnt']),
    ('key_w0', ['tb.good1.w0'], ['tb.top_module1.key_w0']),
    ('sa00', ['tb.good1.sa00'], ['tb.top_module1.sa_00']),
]


def project_probes(trace, rows):
    """Bind each probe to the last simulated candidate, even after a rollback.

    Rollback restores RTL but does not restore the overwritten VCD. A subsequent
    successful top_sim run_check is the point at which probes return to baseline.
    """
    result = {i: [] for i in range(len(rows) + 1)}
    wave, baseline, action = 0, 0, 0
    for entry in trace:
        if entry.get('role') != 'tool':
            continue
        name, obs = entry.get('tool_name'), entry.get('tool_result') or {}
        if name in {'apply_patch', 'replace_block'} and obs.get('is_action_executed'):
            require(action < len(rows))
            row = rows[action]; action += 1
            require(obs == row['result'])
            if obs.get('lint_pass') and isinstance(obs.get('is_pass'), bool):
                wave = row['step']
            if obs.get('status') != 'rollback':
                baseline = row['step']
        elif name == 'run_check' and obs.get('mode') == 'top_sim' and isinstance(obs.get('is_pass'), bool):
            expected = rows[baseline - 1]['result'] if baseline else None
            require(expected is not None and obs.get('mismatch_count') == expected.get('mismatch_count'))
            wave = baseline
        elif name == 'probe_vcd' and obs.get('status') == 'ok':
            for point in obs.get('rows', []):
                t = point.get('t')
                if not isinstance(t, int) or isinstance(t, bool) or t < 0:
                    continue
                fields = {re.sub(r'\[\d+(?::\d+)?\]$', '', key): (key, value)
                          for key, value in point.items() if isinstance(value, str) and re.fullmatch('[01xXzZ]+', value)}
                for signal, refs, duts in PAIRS:
                    ref = next((fields[k] for k in refs if k in fields), None)
                    dut = next((fields[k] for k in duts if k in fields), None)
                    if ref and dut:
                        result[wave].append({'time_ticks': str(t), 'signal': signal,
                                             'reference': ref[1], 'dut': dut[1],
                                             'reference_path': ref[0], 'dut_path': dut[0]})
    require(action == len(rows))
    return {i: sorted({dump(p): p for p in samples}.values(), key=lambda p: (int(p['time_ticks']), p['signal']))[:1024]
            for i, samples in result.items()}


def prepare_react_history(settings, store, bundle):
    from .recorded_history import SUFFIX, expanded_bundle
    from .import_case import public, publish_validation

    base = safe_path(settings.source, '.zerorepo/workspace')
    if not base.is_dir():
        return expanded_bundle(store, bundle)
    name = {'aes_cipher_system_hard': 'rtl_demo_aes_cipher.history.json',
            'aes_inv_cipher_top_system': 'rtl_demo_aes_inverse.history.json'}[bundle['case_id']]
    config = json.loads((settings.repo / 'configs' / name).read_text())
    require(config['case_id'] == bundle['case_id'])

    def checked(item, tree=False):
        path = safe_path(base, item['path'])
        require((tree_manifest(path)[0] if tree else sha(path)) == item['sha256'])
        return path

    rows = [json.loads(line) for line in checked(config['journal']).read_text().splitlines() if line.strip()]
    trace = [json.loads(line) for line in checked(config['trace']).read_text().splitlines() if line.strip()]
    require([r['step'] for r in rows] == list(range(1, len(config['candidates']) + 1)))
    final_root = checked(config['final']['rtl'], True)
    final = {f['path']: safe_path(final_root, f['path']).read_bytes() for f in tree_manifest(final_root)[1]}
    snapshots = []
    for row, spec in zip(rows, config['candidates'], strict=True):
        require(row['step'] == spec['step'])
        before, after = checked(spec['before'], True), checked(spec['after'], True)
        snapshots.append(tuple({f['path']: safe_path(root, f['path']).read_bytes()
                                for f in tree_manifest(root)[1]} for root in (before, after)))
    initial, trees = reconstruct(final, rows, snapshots)
    touched = {name for before, after in snapshots for name in before | after}
    for name in final.keys() - touched:
        # Unchanged modules are anchored to their original generation draft too,
        # rather than assuming the final file existed unchanged at startup.
        path = Path(name)
        pinned = config.get('unchanged_sources', {}).get(name)
        draft = checked(pinned) if pinned else safe_path(base, 'merge_drafts/' + path.stem + '_draft' + path.suffix)
        require(draft.is_file() and draft.read_bytes() == final[name])
    probes = project_probes(trace, rows)
    initial_report = checked(config['initial_report'])
    final_report, final_wave = checked(config['final']['report']), checked(config['final']['wave'])
    # Require the same final input binding already reviewed by the catalog importer.
    require(config['final']['rtl']['sha256'] == bundle['versions'][-1]['tree_sha256'])
    require(config['final']['wave']['sha256'] == bundle['validations'][-1]['waveform_sha256'])
    require({c['signal']: {'count': c['count'], 'first_time': int(c['first_failure_ticks'])}
             for c in signal_counts(initial_report.read_text())} == rows[0]['before_metrics']['per_signal'])
    art = Artifacts(settings.data, store)
    run_id = bundle['source_run_id'] + '-react-v1'
    versions, validations, attempts = [], [], []

    def snapshot(files, ident, parent=None):
        with tempfile.TemporaryDirectory(prefix='react-history-', dir=settings.data) as folder:
            root = Path(folder)
            for name, value in files.items():
                target = safe_path(root, name); target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(value)
            version = art.snapshot(root, ident, run_id, parent=parent)
        versions.append(version)
        return version

    def recorded_validation(version, ident, kind, text, no, simulated, verdict, internal=None):
        path = settings.data / 'indexes' / (ident + '-report.json')
        atomic_json(path, {'stdout': text, 'stderr': ''})
        report = art.add(path, 'report', display=True)
        counts = signal_counts(text) if simulated else []
        times = [int(c['first_failure_ticks']) for c in counts]
        val = {'validation_id': ident, 'run_id': run_id, 'version_id': version['version_id'],
               'kind': kind, 'verdict': verdict, 'simulation_completed': simulated,
               'total_samples': None, 'mismatched_samples': None,
               'first_failure_ticks': str(min(times)) if times else None,
               'report_artifact_id': report['artifact_id'], 'marker_status': 'unsupported',
               'binding_level': 'recorded_partial_snapshots', 'verifier_fingerprint': bundle['verifier_fingerprint'],
               'signal_names': settings.case['signals'], 'signal_mismatches': counts,
               'probe_samples': probes.get(no, []) if simulated else [],
               'probe_source_sha256': config['trace']['sha256'],
               'waveform_note': '本版本完整VCD未留存；下方仅为当时工具记录的离散探针，不代表完整波形。' if simulated else
                                '本次修改未单独运行检查；没有本版验证结果或波形。' if kind == 'edit_only' else '语法失败，未运行新仿真。',
               'report_scope': 'recorded_tool_excerpt' if kind == 'candidate' else 'recorded_edit_status' if kind == 'edit_only' else 'recorded_report'}
        if internal is not None:
            val['internal_mismatch_count'] = internal
        if no:
            val['trial_no'] = no
        store.put('validation', ident, val, immutable=True); validations.append(val)
        return val

    initial_version = snapshot(initial, run_id + '-initial')
    initial_val = recorded_validation(initial_version, run_id + '-initial-check', 'initial_system',
                                      initial_report.read_text(), 0, True, 'fail')
    base_versions, base_vals = {0: initial_version}, {0: initial_val}
    for row, (_, candidate, baseline) in zip(rows, trees, strict=True):
        no, result = row['step'], row['result']
        version = snapshot(candidate, f'{run_id}-trial-{no}', base_versions[baseline]['version_id'])
        simulated = result.get('lint_pass') is True and isinstance(result.get('is_pass'), bool)
        if result.get('is_pass') is True:
            require(candidate == final and no == len(rows))
            val = publish_validation(settings, store, art, version, final_report, final_wave,
                                     bundle['stats_fields'], f'{run_id}-check-{no}', 'candidate', trial_no=no,
                                     binding_level='recorded_partial_snapshots', verifier_fingerprint=bundle['verifier_fingerprint'])
            validations.append(val)
        else:
            unchecked = result.get('status') == 'kept_unverified'
            require(simulated or unchecked or result.get('lint_pass') is False)
            val = recorded_validation(version, f'{run_id}-check-{no}', 'candidate' if simulated else 'edit_only' if unchecked else 'syntax',
                                      result.get('sim_output_excerpt', '') if simulated else
                                      '原始工具状态：kept_unverified。修改已保留，本次未单独执行语法或仿真检查。' if unchecked else result.get('lint_output_excerpt', ''),
                                      no, simulated, 'unverified' if unchecked else 'fail', result.get('mismatch_count'))
        changed = [{'path': name, 'change': 'modified'} for name, value in candidate.items()
                   if value != trees[no - 1][0].get(name)]
        signals = [c['signal'] for c in val.get('signal_mismatches', [])]
        debug = {'trial_no': no, 'candidate_id': f'react-step-{no}', 'intent': clean(result.get('reason')),
                 'expected_effect': clean(result.get('expected_effect')), 'files': changed,
                 'lint_pass': result.get('lint_pass'), 'simulation_completed': simulated,
                 'verdict': val['verdict'], 'lint_excerpt': clean(result.get('lint_output_excerpt'), 2400),
                 'signals': signals, 'alignment': 'unrecorded',
                 'decision': 'rollback' if result['status'] == 'rollback' else 'accept'}
        attempts.append({'trial_no': no, 'candidate_revision': 1, 'candidate_id': f'react-step-{no}',
                         'candidate_version_id': version['version_id'], 'baseline_version_id': base_versions[baseline]['version_id'],
                         'before_validation_id': base_vals[baseline]['validation_id'], 'validation_id': val['validation_id'],
                         'decision': 'rolled_back' if result['status'] == 'rollback' else 'accepted',
                         'lint_pass': result.get('lint_pass'), 'simulation_completed': simulated, 'debug': debug})
        base_versions[no], base_vals[no] = version, val
    final_val = publish_validation(settings, store, art, versions[-1], final_report, final_wave, bundle['stats_fields'],
                                   run_id + '-final-check', 'final_system', binding_level='recorded_partial_snapshots',
                                   verifier_fingerprint=bundle['verifier_fingerprint'], verification_scope='saved_final_result')
    validations.append(final_val)
    events = []

    def event(stage, text, **refs):
        events.append({'sequence': len(events) + 1, 'stage': stage, 'text': text,
                       'observed_at': None, 'replay_delay_ms': 1400, **refs})
    event('spec', '读取AES加密规格' if bundle['case_id'] == 'aes_cipher_system_hard' else '读取AES解密规格', artifact_id=bundle['spec_artifact_id'])
    event('architecture', f"规划 {len(bundle['modules'])} 个RTL模块", artifact_id=bundle['planner_artifact_id'])
    event('rtl', '初始RTL快照', version_id=initial_version['version_id'])
    event('verify', '初始系统验证未通过', validation_id=initial_val['validation_id'])
    for attempt in attempts:
        event('syntax' if attempt['lint_pass'] is False else 'repair',
              (f"候选修改 {attempt['trial_no']} · " if attempt['lint_pass'] is None else f"候选验证 {attempt['trial_no']} · ") + ('修改已保留，未单独验证' if attempt['lint_pass'] is None else '语法检查失败' if not attempt['lint_pass'] else '仿真通过' if attempt['debug']['verdict'] == 'pass' else '仿真存在差异'),
              trial_no=attempt['trial_no'], validation_id=attempt['validation_id'], version_id=attempt['candidate_version_id'])
    event('complete', '最终保存的系统验证通过', validation_id=final_val['validation_id'])
    run = {'run_id': run_id, 'source_run_id': bundle['source_run_id'], 'case_id': bundle['case_id'],
           'origin': 'historical', 'round_no': 1, 'label': '完整修复过程', 'modules': bundle['modules'],
           'initial_validation_id': initial_val['validation_id'], 'final_validation_id': final_val['validation_id'],
           'journal_sha256': config['journal']['sha256'], 'events': events,
           'versions': public(versions), 'validations': public(validations), 'attempts': attempts}
    store.put('run', run_id, run, immutable=True)
    artifacts = {a['artifact_id']: a for a in bundle['artifacts']}
    for version in versions:
        for module in version['modules']:
            ident = module['artifact_id']; artifacts[ident] = public(store.get('artifact', ident))
    for val in validations:
        for key in ['report_artifact_id', 'waveform_artifact_id', 'waveform_index_artifact_id']:
            if val.get(key):
                ident = val[key]; artifacts[ident] = public(store.get('artifact', ident))
        for ident in val.get('waveform_tile_artifact_ids', []):
            artifacts[ident] = public(store.get('artifact', ident))
    extra = {**bundle, 'bundle_id': bundle['bundle_id'] + SUFFIX, 'base_bundle_id': bundle['bundle_id'],
             'versions': bundle['versions'] + public(versions), 'validations': bundle['validations'] + public(validations),
             'artifacts': list(artifacts.values()),
             'binding_note': '依据真实ReAct修复日志、前后局部快照和最终受测RTL还原完整版本；中间VCD未保存，离散探针与最终完整波形分别标注。',
             'debug_history': {'schema_version': 'rtl-debug-history-v1', 'source_fingerprint': bundle['source_fingerprint'],
                               'history_fingerprint': hashlib.sha256(dump({'projection': 1, 'sources': config}).encode()).hexdigest(),
                               'runs': [run]}}
    store.put('bundle', extra['bundle_id'], extra, immutable=True)
    return expanded_bundle(store, bundle)
