"""Case layout, conservative retention, public manifests and debug publication."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from rtl_artifact_test_utils import write_artifact_text
from test_responsibility_refinement import scenario, report
from test_rtl_module_planner import QueueBackend
from test_system_debug_runner import _write_workspace, _write_system_oracle
from zerorepo.rtl_impl.artifact_layout import ArtifactLayout, LAYOUT_VERSION
from zerorepo.rtl_impl.artifact_retention import ArtifactRetention
from zerorepo.rtl_impl.module_planner import PlannerRunner
from zerorepo.rtl_impl.module_planner.utils.stage5_store import Stage5Store
from zerorepo.rtl_impl.module_planner.utils.local_repair import fingerprint
from zerorepo.rtl_impl.debug_agent.debug_runner import RtlDebugConfig
from zerorepo.rtl_impl.debug_agent.system_debug_runner import SystemDebugRunner


def write_json(path, value):
    write_artifact_text(path, json.dumps(value))


def test_two_module_pipeline_layout_and_zero_request_resume(tmp_path, monkeypatch):
    monkeypatch.setattr('zerorepo.rtl_impl.module_planner.planner_runner._check_single_file_syntax', lambda *a, **k: (True, 'ok'))
    monkeypatch.setattr('zerorepo.rtl_impl.module_planner.agents.stage6_merge_agent.check_syntax', lambda *a, **k: (True, 'ok'))

    def configure(runner):
        runner.stage6._ensure_toolchain_path = lambda: None
        runner.system_debug_runner.config = RtlDebugConfig(enabled=False)

    case = scenario(tmp_path, end_stage='stage6', before_run=configure)
    task, runner, backend, *_ = case
    layout = runner.layout
    assert report(case)['status'] == 'passed'
    assert layout.artifact('planning_gate_report.json').is_file()
    assert (layout.case_root / 'run.log').is_file()
    assert json.loads((layout.case_root / 'run.json').read_text())['layout_version'] == LAYOUT_VERSION
    assert not list(layout.case_root.rglob('.zerorepo'))
    assert not (layout.case_root / 'workspace').exists()
    for directory in (layout.rtl, layout.directory('fragments')):
        assert list(directory.iterdir())
        assert all(p.suffix in {'.v', '.sv', '.vh', '.svh'} for p in directory.iterdir())
    for name in ('stage5_codegen.json', 'stage6_merge.json'):
        manifest = json.loads(layout.artifact(name).read_text())
        for record in manifest['module_files']:
            for key in ('workspace_file', 'fragment_file', 'merged_file'):
                if record.get(key):
                    assert not Path(record[key]).is_absolute()
                    assert layout.resolve(record[key]).is_file()
    assert len(list((layout.case_root / 'generate/state/merge_inputs').glob('*.json'))) == 2
    initial_calls = len(backend.calls)
    result = runner.run(task, resume=True, end_stage='stage6')
    assert result.status == 'completed'
    assert len(backend.calls) == initial_calls


@pytest.mark.parametrize('mode', ['compact', 'full'])
def test_retention_mode_does_not_change_planning_or_generation_reuse(tmp_path, mode):
    case = scenario(tmp_path, end_stage='stage5', artifacts={'retention': mode})
    task, runner, *_ = case
    assert report(case)['counts']['covered_responsibilities'] == 2
    events = list((runner.output_root / 'plan/traces/events').rglob('events.jsonl'))
    assert bool(events) == (mode == 'full')
    backend = QueueBackend([])
    restored = PlannerRunner(output_root=runner.output_root, llm_backend=backend,
                             artifacts={'retention': 'full' if mode == 'compact' else 'compact'})
    result = restored.run(task, resume=True, end_stage='stage5')
    assert len(result.module_files) == 2 and backend.calls == []


def test_requests_are_removed_only_after_stage_commit_and_latest_failure_survives(tmp_path):
    layout = ArtifactLayout(tmp_path / 'case')
    retention = ArtifactRetention(layout)
    retention.initialize('task')
    stage = 'stage3_module_skeletons'
    requests = layout.traces(stage) / 'toy'
    for order, (identity, status) in enumerate([('completed', 'completed'), ('old-failure', 'failed'), ('latest-failure', 'failed'), ('current', 'running')]):
        write_json(requests / identity / 'status.json', {'status': status, 'updated_at_ns': order})
    retention.compact(set())
    assert (requests / 'completed').is_dir()
    assert not (requests / 'old-failure').exists()
    assert (requests / 'latest-failure').is_dir() and (requests / 'current').is_dir()
    retention.compact({stage})
    assert not (requests / 'completed').exists()
    assert (requests / 'latest-failure').is_dir() and (requests / 'current').is_dir()


def test_compaction_preserves_active_pending_and_history_bundles_and_restores_aliases(tmp_path):
    layout = ArtifactLayout(tmp_path / 'case')
    retention = ArtifactRetention(layout); retention.initialize('task')
    store = Stage5Store(layout.case_root)

    def bundle(text, status='completed'):
        contracts = {'contracts': []}
        return store.bundle({'module': 'toy', 'status': status,
                             'fragment_fingerprint': fingerprint(text),
                             'contracts_fingerprint': fingerprint(contracts)}, text, contracts)

    current, pending, historical, garbage = bundle('current'), bundle('pending', 'in_progress'), bundle('historical'), bundle('garbage')
    write_json(layout.stage5_checkpoint('toy'), current)
    write_json(store.candidate_file('toy', 'pending'), pending)
    write_json(layout.directory('.stage5_history') / 'toy/old.json', historical)
    write_json(store.candidate_file('toy', 'obsolete'), garbage)
    retention.compact({'stage5_codegen'})
    for marker in (current, pending, historical):
        assert store.validate(marker)
    assert not (layout.case_root / garbage['bundle_path']).exists()
    store.restore_aliases(current)
    assert layout.stage5_contracts('toy').is_file()
    assert all(p.suffix == '.v' for p in layout.directory('fragments').iterdir())


def test_corrupt_reference_graph_cannot_authorize_generation_cleanup(tmp_path):
    layout = ArtifactLayout(tmp_path / 'case')
    retention = ArtifactRetention(layout); retention.initialize('task')
    bundle = layout.directory('.stage5_generations') / 'toy/keep'
    write_artifact_text(bundle / 'snapshot.v', 'module toy; endmodule')
    write_artifact_text(layout.stage5_checkpoint('toy'), '{malformed')
    retention.compact({'stage5_codegen'})
    assert (bundle / 'snapshot.v').is_file()


def test_full_mode_and_unversioned_cases_are_not_collected(tmp_path):
    layout = ArtifactLayout(tmp_path / 'case')
    file = layout.directory('merge_drafts') / 'toy.v'
    write_artifact_text(file, 'diagnostic')
    ArtifactRetention(layout).compact({'stage6_merge'})
    assert file.is_file()
    full = ArtifactRetention(layout, 'full'); full.initialize('task'); full.compact({'stage6_merge'})
    assert file.is_file()
    with pytest.raises(ValueError, match='retention'):
        ArtifactRetention(layout, 'invalid')


def test_compaction_leaves_existing_cases_and_external_symlinks_untouched(tmp_path):
    old_file = tmp_path / 'old/.zerorepo/workspace/merged/old.inputs.json'
    write_artifact_text(old_file, 'original old case')
    layout = ArtifactLayout(tmp_path / 'new')
    retention = ArtifactRetention(layout); retention.initialize('task')
    layout.directory('merge_drafts').parent.mkdir(parents=True)
    layout.directory('merge_drafts').symlink_to(old_file.parent, target_is_directory=True)
    retention.compact({'stage6_merge'})
    assert old_file.read_text() == 'original old case'
    assert layout.directory('merge_drafts').is_symlink()


@pytest.mark.parametrize('passed', [False, True])
def test_system_fix_is_published_only_after_validation_passes(tmp_path, monkeypatch, passed):
    _write_system_oracle(tmp_path, 'top', 'def verify_system(path): return False, "FAIL"\n')
    root, records = _write_workspace(tmp_path, 'top')
    final = Path(records[0].merged_file)
    before = final.read_bytes()
    runner = SystemDebugRunner(workspace_root=root,
        config=RtlDebugConfig(oracle_root=str(tmp_path / 'oracle')))
    monkeypatch.setattr('zerorepo.rtl_impl.debug_agent.system_debug_runner.SystemSimReviewer.review', lambda *a: (False, 1, '{}'))

    def debug(**kwargs):
        write_artifact_text(kwargs['generated_dir'] / 'top.v', "module top(output y); assign y=1'b1; endmodule\n")
        return passed, 1

    monkeypatch.setattr(runner, '_run_repo_react', debug)
    result = runner.run_system(top_module='top', task=SimpleNamespace(spec_md_files=[]),
        spec_text='spec', contract_json='{}', merged_records=records)
    assert result.status == ('fixed' if passed else 'fail')
    assert (final.read_bytes() != before) == passed
    assert final.parent == ArtifactLayout(root).rtl


def test_full_mode_archives_simulation_before_reset(tmp_path):
    layout = ArtifactLayout(tmp_path / 'case')
    retention = ArtifactRetention(layout, 'full'); retention.initialize('task')
    scratch = layout.directory('debug_system') / 'top/simulation'
    write_artifact_text(scratch / 'wave.vcd', 'previous verification')
    retention.snapshot_debug_scratch(scratch)
    saved = list((scratch.parent / 'state/history').glob('simulation-*/simulation/wave.vcd'))
    assert len(saved) == 1 and saved[0].read_text() == 'previous verification'


def test_relative_paths_cannot_escape_case(tmp_path):
    with pytest.raises(ValueError, match='escapes'):
        ArtifactLayout(tmp_path).resolve('../outside.json')


def test_offline_bundle_recovery_is_read_only_until_apply_and_resume_checks_sources(tmp_path):
    from scripts.recover_planner_stage5 import recover
    task, runner, *_ = scenario(tmp_path, end_stage='stage5')
    module = 'aes_key_expand_128'
    fragments = runner.stage5._workspace_file(module)
    contracts = runner.layout.stage5_contracts(module)
    saved = fragments.read_bytes()
    fragments.unlink(); contracts.unlink()
    result = recover(runner.output_root, module)
    assert result['bundle_verified'] and not fragments.exists() and not contracts.exists()
    recover(runner.output_root, module, apply=True)
    assert fragments.read_bytes() == saved and contracts.is_file()
    backend = QueueBackend([])
    restored = PlannerRunner(output_root=runner.output_root, llm_backend=backend)
    assert restored.run(task, resume=True, end_stage='stage5').module_files
    assert backend.calls == []


def test_wave_compaction_keeps_latest_failure_and_accepted_validation(tmp_path):
    layout = ArtifactLayout(tmp_path / 'case')
    retention = ArtifactRetention(layout); retention.initialize('task')
    private = layout.directory('debug_system') / 'top/state/codex_private'
    events = []
    for identity, passed in [('old-fail', False), ('older-fail', False), ('accepted', True), ('latest-fail', False)]:
        candidate = private / 'candidates' / identity / 'revision_001'
        write_artifact_text(candidate / 'artifacts/wave.vcd', identity)
        write_artifact_text(candidate / 'merged/top.v', 'module top; endmodule')
        events.append({'event': 'evaluate', 'candidate_id': identity, 'revision': 1, 'result': {'is_pass': passed}})
        if passed:
            events.append({'event': 'accept', 'candidate_id': identity, 'candidate_revision': 1})
    write_artifact_text(private / 'journal/codex_validation_journal.jsonl', '\n'.join(json.dumps(e) for e in events))
    write_json(private / 'session_state.json', {'last_validation': {'candidate_id': 'latest-fail', 'candidate_revision': 1}})
    write_artifact_text(private / 'accepted_baseline/artifacts/wave.vcd', 'authoritative accepted baseline')
    retention.compact({'stage6_merge'})
    waves = {p.parents[2].name for p in (private / 'candidates').glob('*/revision_*/artifacts/wave.vcd')}
    assert waves == {'accepted', 'latest-fail'}
    assert len(list((private / 'candidates').glob('*/revision_001/merged/top.v'))) == 4
    assert (private / 'accepted_baseline/artifacts/wave.vcd').read_text() == 'authoritative accepted baseline'


def test_system_candidates_include_nested_headers_and_manifested_defines(tmp_path):
    from zerorepo.rtl_impl.module_planner.agents.global_defines import write_global_defines_manifest
    layout = ArtifactLayout(tmp_path / 'case')
    top = layout.rtl / 'top.v'
    header = layout.rtl / 'headers/widths.svh'
    define = layout.rtl / 'shared_defines.v'
    write_artifact_text(top, 'module top; endmodule')
    write_artifact_text(header, '`define WIDTH 8')
    write_artifact_text(define, '`define SHARED 1')
    write_global_defines_manifest(workspace_root=layout.case_root, output_root=layout.case_root,
        entries=[{'name': define.name, 'workspace_path': str(define), 'must_include': True}])
    verify = tmp_path / 'oracle'; verify.mkdir()
    script = verify / 'top_verify.py'; write_artifact_text(script, 'def verify_system(path): return True, "PASS"')
    runner = SystemDebugRunner(workspace_root=layout.case_root)
    work = runner.debug_root / 'top/simulation'
    generated = work.parent / 'candidates/generated'
    runner._prepare_workdir(planner_top_module='top', runtime_top_module='top', testbench_dut_module='top',
        workdir=work, generated_dir=generated, verify_dir=verify, verify_script=script,
        merged_records=[SimpleNamespace(module='top', merged_file=str(top))], contract_json='{}')
    assert (generated / 'headers/widths.svh').read_text() == header.read_text()
    assert (generated / 'shared_defines.v').read_text() == define.read_text()
    target = tmp_path / 'copy'
    runner._copy_rtl_tree(generated, target)
    assert (target / 'headers/widths.svh').is_file()
    write_artifact_text(generated / 'headers/widths.svh', '`define WIDTH 16')
    runner._sync_generated_to_merged(generated)
    assert header.read_text() == '`define WIDTH 16'
    assert len(list(layout.case_root.rglob('global_defines_manifest.json'))) == 1


@pytest.mark.parametrize('single_spec', [False, True])
def test_startup_script_dispatches_without_creating_legacy_or_placeholder_outputs(tmp_path, single_spec):
    import os
    import shutil
    import subprocess
    script_source = Path(__file__).resolve().parents[1] / 'scripts/run_main.sh'
    script = tmp_path / 'project/scripts/run_main.sh'
    script.parent.mkdir(parents=True)
    shutil.copyfile(script_source, script)
    binary = tmp_path / 'bin/python'
    write_artifact_text(binary, '#!/bin/sh\nprintf "%s\\n" "$@" > "$RTL_DISPATCH_ARGS"\n')
    binary.chmod(0o755)
    captured = tmp_path / 'args'
    arguments = ['bash', str(script)]
    if single_spec:
        spec = tmp_path / 'project/rtl_dataset/top.md'
        write_artifact_text(spec, '# top')
        arguments.append(str(spec))
    env = {**os.environ, 'PATH': str(binary.parent) + os.pathsep + os.environ['PATH'],
           'RTL_DISPATCH_ARGS': str(captured), 'RTL_PIPELINE_MODE': 'planner'}
    subprocess.run(arguments, env=env, check=True, capture_output=True, text=True)
    dispatched = captured.read_text().splitlines()
    assert dispatched[dispatched.index('--phase') + 1] == 'rtl_planner'
    assert '--log-file' not in dispatched
    assert not any('.zerorepo' in a or '_temp' in a for a in dispatched)
    assert not (tmp_path / 'project/rtl_outputs').exists()


def test_cli_validation_defers_planner_checkpoint_creation(tmp_path):
    from main import validate_args
    config = tmp_path / 'config.yaml'; write_artifact_text(config, '{}')
    checkpoint = tmp_path / 'unused/.zerorepo'
    assert validate_args(SimpleNamespace(config=str(config), checkpoint=str(checkpoint),
                                         repo=str(tmp_path / 'case'), phase='rtl_planner'))
    assert not checkpoint.exists()


def test_model_request_diagnostics_have_one_stage_directory(tmp_path):
    from zerorepo.rtl_impl.module_planner.utils import PlannerLLMClient
    from zerorepo.rpg_gen.base.llm_client.request_policy import RequestProgress
    root = tmp_path / 'case'
    llm = PlannerLLMClient(backend=QueueBackend([]))
    options = llm.request_options(stage='stage3_module_skeletons', module='toy', output_root=root)
    progress = RequestProgress(options, log=False)
    progress.begin_attempt()
    assert progress.directory.relative_to(root).parts[:-1] == ('plan', 'traces', 'requests', 'stage3_module_skeletons', 'toy')
