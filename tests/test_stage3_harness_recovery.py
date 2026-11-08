"""Canonical source selection, independent transactions and progress budgets."""
from __future__ import annotations

import copy
import json

import pytest

from test_planning_harness import ToyAdapter, toy, RaisingBackend
from test_responsibility_refinement import scenario
from test_repair_prompt_budget import expand_shared
from test_rtl_module_planner import QueueBackend
from test_stage3_obligation_repair import (
    planned as build_planned_fixture, obligations, replace_obligations, patches,
)
from test_stage3_repair_progress import setup_client
from zerorepo.rpg_gen.base.llm_client.errors import LLMRequestTimeoutError
from zerorepo.rtl_impl.module_planner.agents import Stage3Agent
from zerorepo.rtl_impl.module_planner.agents.base import StageGenerationError
from zerorepo.rtl_impl.module_planner.utils.execution import PlanningBudgetExceeded
from zerorepo.rtl_impl.module_planner.utils.local_repair import ArtifactIssue, fingerprint
from zerorepo.rtl_impl.module_planner.schemas import SourceEvidence
from zerorepo.rtl_impl.module_planner.utils.responsibility_planning import verify_source


@pytest.fixture(scope='module')
def planned(tmp_path_factory):
    return build_planned_fixture.__wrapped__(tmp_path_factory)


def sources_broken(planned):
    _, text, _, factory = planned
    entries, _ = obligations(text)
    bad = copy.deepcopy(entries)
    for entry in bad:
        entry['source_refs'][0]['quote'] = 'not present in the specification'
    broken = replace_obligations(text, bad)
    adapter = factory()
    old = adapter.inspect(broken)
    targets = adapter.targets(old)
    assert len(targets) == len(entries) == 3
    return adapter, old, targets, entries, broken


def id_patch(targets):
    return {target: [next(iter(spec['source_evidence_options']))] for target, spec in targets.items()}


def test_source_repair_selects_ids_and_preserves_every_other_byte(planned):
    adapter, old, targets, entries, broken = sources_broken(planned)
    fixed = adapter.apply_response(old, patches(id_patch(targets)), targets)
    assert not fixed.issues
    assert obligations(fixed.candidate)[0] == entries
    assert fixed.candidate.split('### Behavioral Obligations')[0] == broken.split('### Behavioral Obligations')[0]
    assert all(spec['expected']['items']['enum'] for spec in targets.values())


def test_source_ids_copy_escaped_table_exactly(planned, tmp_path):
    _, text, _, factory = planned
    entries, _ = obligations(text)
    path = tmp_path / 'table.md'
    path.write_text('# Operations\n| AMOOR | `original \\| i_rs2` |\n')
    canonical = SourceEvidence(source_file=str(path), quote='| AMOOR | `original \\| i_rs2` |')
    documents = {str(path): path.read_text()}
    verify_source(canonical, documents)
    identity = entries[0]['obligation_id']
    def validate(export):
        item = next(o for o in export.behavioral_obligations if o.obligation_id == identity)
        try:
            for ref in item.source_refs:
                verify_source(ref, documents)
                if ref.model_dump() != canonical.model_dump():
                    raise ValueError('source not bound to parent')
            return []
        except ValueError as exc:
            return [ArtifactIssue('behavioral_obligations', 'invalid_source', str(exc),
                expected={'allowed_source_refs': [canonical.model_dump()]}, category='hardware',
                section='Behavioral Overlay', unit_id=identity)]
    adapter = factory(validate)
    bad = copy.deepcopy(entries)
    bad[0]['source_refs'] = [{**canonical.model_dump(), 'quote': canonical.quote.replace('\\|', '|')}]
    old = adapter.inspect(replace_obligations(text, bad))
    targets = adapter.targets(old)
    result = adapter.apply_response(old, patches(id_patch(targets)), targets)
    assert not result.issues
    actual = obligations(result.candidate)[0][0]['source_refs'][0]
    assert actual == canonical.model_dump()
    assert '\\|' in actual['quote']


@pytest.mark.parametrize('invalid', ['unknown', 'duplicate', 'empty', 'mixed'])
def test_bad_source_id_selection_does_not_modify_candidate(planned, invalid):
    adapter, old, targets, _, _ = sources_broken(planned)
    target = next(iter(targets))
    value = id_patch(targets)[target]
    bad = {'unknown': ['SRC_unknown'], 'duplicate': value * 2, 'empty': [], 'mixed': [*value, {}]}[invalid]
    with pytest.raises((ValueError, TypeError)):
        adapter.apply_response(old, patches({target: bad}), {target: targets[target]})
    assert adapter.inspect(old.candidate).candidate == old.candidate


def test_mixed_response_keeps_two_valid_groups_and_rejects_bad_source(planned):
    adapter, old, targets, entries, _ = sources_broken(planned)
    values = id_patch(targets)
    last = list(values)[-1]
    values[last] = [{**entries[-1]['source_refs'][0], 'quote': 'a different invented source'}]
    partial = adapter.apply_response(old, patches(values), targets)
    actual, _ = obligations(partial.candidate)
    assert actual[:2] == entries[:2]
    assert actual[-1] == obligations(old.candidate)[0][-1]
    assert len(partial.issues) < len(old.issues)
    assert len(adapter.last_patch_rejections) == 1
    remaining = adapter.targets(partial)
    assert set(remaining) == {last}
    assert not adapter.apply_response(partial, patches(id_patch(remaining)), remaining).issues


def test_fields_of_one_obligation_remain_atomic(planned):
    adapter, old, _, entries, broken = sources_broken(planned)
    bad, _ = obligations(broken)
    bad[0]['clock_domain'] = 'wrong_clock'
    old = adapter.inspect(replace_obligations(broken, bad))
    targets = adapter.targets(old)
    values = {target: ([next(iter(spec['source_evidence_options']))] if target.endswith('source_refs') else 123)
              for target, spec in targets.items()}
    partial = adapter.apply_response(old, patches(values), targets)
    actual, _ = obligations(partial.candidate)
    assert actual[0] == bad[0]
    assert actual[1:] == entries[1:]
    assert any(i.code == 'contract_drift' for i in partial.issues)


@pytest.mark.parametrize('mode', ['extra', 'duplicate', 'missing'])
def test_invalid_patch_envelope_cannot_salvage_any_group(planned, mode):
    adapter, old, targets, _, _ = sources_broken(planned)
    response = patches(id_patch(targets))
    if mode == 'extra':
        response['patches'].append({'target': 'Module Frame', 'replacement': 'forbidden'})
    if mode == 'duplicate':
        response['patches'].append(response['patches'][0])
    if mode == 'missing':
        response['patches'].pop()
    with pytest.raises(ValueError):
        adapter.apply_response(old, response, targets)
    assert adapter.inspect(old.candidate).candidate == old.candidate


@pytest.mark.parametrize('legacy_rejection', [False, True])
def test_restart_keeps_independent_repairs_and_requests_only_remaining_source(planned, tmp_path, legacy_rejection):
    task, _, _, factory = planned
    _, _, targets, entries, broken = sources_broken(planned)
    values = {target: entries[index]['source_refs'] for index, target in enumerate(targets)}
    last = list(values)[-1]
    values[last] = [{**entries[-1]['source_refs'][0], 'quote': 'invalid patch quote'}]
    root = tmp_path / 'case'
    backend = RaisingBackend([broken, patches(values), LLMRequestTimeoutError('repair interrupted')])
    adapter = factory()
    if legacy_rejection:
        def reject(previous, response, targets):
            raise ValueError('old all-or-nothing guard')
        adapter.apply_response = reject
    agent = Stage3Agent(setup_client(root, task, backend, False))
    if legacy_rejection:
        with pytest.raises(StageGenerationError):
            agent._invoke_local_repair(prompt='same logical prompt', images=[], adapter=adapter, max_attempts=2)
    else:
        with pytest.raises(LLMRequestTimeoutError):
            agent._invoke_local_repair(prompt='same logical prompt', images=[], adapter=adapter, max_attempts=3)
    resumed = QueueBackend([patches({last: id_patch(targets)[last]})])
    result = Stage3Agent(setup_client(root, task, resumed, True))._invoke_local_repair(
        prompt='same logical prompt', images=[], adapter=factory())
    assert not result.issues and len(resumed.calls) == 1
    request = resumed.calls[0]['user_prompt']
    bundle = json.loads(request.split('Targets, all diagnostics, source context, evidence and shared values:\n', 1)[1])
    assert set(expand_shared(bundle)['targets']) == {last}
    assert obligations(result.candidate)[0] == entries


class StepsAdapter(ToyAdapter):
    def semantic_issues(self, artifact):
        return [ArtifactIssue(f'requirements[{i}]', 'uncovered', 'required behavior missing', unit_id=str(i))
                for i in range(artifact.value, 4)]


def steps(values):
    return [{'value': values[0]}, *[patches({'value': v}) for v in values[1:]]]


def test_progress_extends_content_repairs_within_node_budget(tmp_path):
    _, backend, _, agent = toy(tmp_path, steps([0, 1, 2, 3, 4]))
    result = agent._invoke_local_repair(prompt='four requirements', images=[], adapter=StepsAdapter(),
                                      max_attempts=3, allow_progress_extension=True)
    assert result.artifact.value == 4 and len(backend.calls) == 5


def test_two_stalled_repairs_stop_extension_and_keep_progress(tmp_path):
    _, backend, client, agent = toy(tmp_path, steps([0, 1, 1, 1, 4]))
    with pytest.raises(StageGenerationError, match='after 4 attempts'):
        agent._invoke_local_repair(prompt='four requirements', images=[], adapter=StepsAdapter(),
                                  max_attempts=3, allow_progress_extension=True)
    assert len(backend.calls) == 4
    saved = json.loads(next((client.output_root / 'plan/state/execution').glob('*.json')).read_text())
    assert saved['candidate'] == {'value': 1}


def test_node_api_budget_still_stops_progress_and_retains_candidate(tmp_path):
    _, backend, client, agent = toy(tmp_path, steps([0, 1, 2, 3, 4]), policy={'max_api_attempts': 4})
    with pytest.raises(PlanningBudgetExceeded, match='progress retained'):
        agent._invoke_local_repair(prompt='four requirements', images=[], adapter=StepsAdapter(),
                                  max_attempts=3, allow_progress_extension=True)
    assert len(backend.calls) == 4
    saved = json.loads(next((client.output_root / 'plan/state/execution').glob('*.json')).read_text())
    assert saved['candidate'] == {'value': 3} and saved['api_attempts'] == 4


def test_explicit_content_limit_remains_strict_without_opt_in(tmp_path):
    _, backend, _, agent = toy(tmp_path, steps([0, 1, 2, 3, 4]))
    with pytest.raises(StageGenerationError, match='after 3 attempts'):
        agent._invoke_local_repair(prompt='four requirements', images=[], adapter=StepsAdapter(), max_attempts=3)
    assert len(backend.calls) == 3


@pytest.mark.parametrize('retention', ['compact', 'full'])
def test_two_module_gate_after_three_incremental_source_repairs(tmp_path, retention):
    def prepare(runner):
        responses=runner.llm_client.backend.responses
        index=next(i for i,value in enumerate(responses) if isinstance(value,dict) and "module_frame" in value)
        draft=responses[index]
        good=copy.deepcopy(draft["behavioral_obligations"][:3])
        for obligation in draft["behavioral_obligations"][:3]: obligation["source_evidence_ids"]=["EV_unknown"]
        responses[index+1:index+1]=[{"behavioral_obligations":[obligation]} for obligation in good]
    _, runner, backend, _, stage3, stage4=scenario(tmp_path,before_run=prepare,artifacts={"retention":retention})
    repairs=[c for c in backend.calls if "VALIDATION RESULT" in c["user_prompt"]]
    assert len(repairs)==3
    assert len(stage3.completed_modules)==len(stage4.completed_modules)==2
    assert json.loads(runner.layout.artifact("planning_gate_report.json").read_text())["status"]=="passed"
