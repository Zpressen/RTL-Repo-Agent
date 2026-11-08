"""Stage4 first requests share inputs without changing source identity or gates."""
from __future__ import annotations

import copy
import json
from types import SimpleNamespace

import pytest

from test_repair_prompt_budget import expand_evidence, expand_shared
from test_responsibility_refinement import scenario
from test_rtl_module_planner import QueueBackend, make_task_input, make_stage4_module_plan_payload
from zerorepo.rtl_impl.module_planner.agents.stage4_module_plan_agent import Stage4ModulePlanAgent
from zerorepo.rtl_impl.module_planner.prompts import stage4_module_plan
from zerorepo.rtl_impl.module_planner.utils import PlannerLLMClient
from zerorepo.rtl_impl.module_planner.utils.codegen_repair import ModulePlanRepairAdapter
from zerorepo.rtl_impl.module_planner.utils.execution import PlanningBudgetExceeded
from zerorepo.rtl_impl.module_planner.utils.prompt_context import SHARED_INPUT_MARKER, shared_input_prompt


def restore_request(request):
    return expand_evidence(expand_shared(json.loads(request.split(SHARED_INPUT_MARKER, 1)[1])))


def make_prompt(inputs):
    def pretty(value):
        return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
    return stage4_module_plan.build_prompt(
        module_name=inputs['MODULE_NAME'], module_skeleton=inputs['MODULE_SKELETON'],
        module_spec_blocks=pretty(inputs['MODULE_SPEC_BLOCKS']),
        required_subtasks=pretty(inputs['REQUIRED_SUBTASKS']),
        planning_kg_context=pretty(inputs['PLANNING_KG_CONTEXT']),
        stage_context=pretty(inputs['STAGE_CONTEXT']),
    )


def test_structured_first_request_roundtrip_keeps_all_sections_and_instruction_rules():
    source = {'source_file': 'spec.md', 'quote': 'Exact source text\n' * 120,
              'start_line': 1, 'end_line': 120, 'content_hash': 'hash'}
    text = 'Complete unique skeleton / interface text\n' * 20
    inputs = {'MODULE_NAME': 'toy', 'REQUIRED_SUBTASKS': [{'source_refs': [source]}] * 25,
              'MODULE_SKELETON': text, 'MODULE_SPEC_BLOCKS': {'blocks': [{'text': text}] * 30},
              'PLANNING_KG_CONTEXT': {'specs': [{'text': text}] * 80, 'sources': [source]},
              'STAGE_CONTEXT': {'module': 'toy'}}
    original = copy.deepcopy(inputs)
    prompt = make_prompt(inputs)
    adapter = ModulePlanRepairAdapter(module='toy', required=[], context=inputs, source_blocks=[],
                                      validator=lambda _: [], input_sections=inputs)
    request = adapter.initial_request(prompt)
    assert restore_request(request) == original and inputs == original
    assert request.startswith(prompt.partition('\nInput:\n')[0])
    assert len(request) < len(prompt)
    assert request.count('Complete unique skeleton / interface text') == 20
    with pytest.raises(ValueError, match='instruction boundary'):
        adapter.initial_request('changed prompt without its instruction boundary')
    legacy = ModulePlanRepairAdapter(module='toy', required=[], context='', source_blocks=[], validator=lambda _: [])
    assert legacy.initial_request(prompt) == prompt


def test_small_first_request_uses_original_when_sharing_would_add_overhead():
    inputs = {'MODULE_NAME': 'toy', 'REQUIRED_SUBTASKS': [], 'MODULE_SKELETON': 'small',
              'MODULE_SPEC_BLOCKS': {}, 'PLANNING_KG_CONTEXT': {}, 'STAGE_CONTEXT': {}}
    prompt = make_prompt(inputs)
    adapter = ModulePlanRepairAdapter(module='toy', required=[], context=inputs, source_blocks=[],
                                      validator=lambda _: [], input_sections=inputs)
    assert adapter.initial_request(prompt) == prompt


def inject_large_context(runner, saved):
    def context(module, **kwargs):
        skeleton = json.loads((runner.output_root / f'plan/stage3/modules/{module}/skeleton.json').read_text())
        result = {'skeleton_artifact': skeleton, 'repeated_spec_fragments': [skeleton] * 100}
        saved[module] = copy.deepcopy(result)
        return result
    runner.stage4_module_plans.planning_context_retriever = SimpleNamespace(
        kg_service=SimpleNamespace(mode='required'), get_module_context=context,
        to_prompt_json=lambda value: json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


@pytest.mark.parametrize('retention', ['compact', 'full'])
def test_first_requests_fit_and_repair_keeps_contracts_and_final_gate(tmp_path, retention):
    def prepare(runner):
        inject_large_context(runner, {})
    _, runner, backend, _, _, result = scenario(tmp_path, before_run=prepare, artifacts={"retention":retention})
    assert len(result.completed_modules) == 2
    metrics = json.loads((runner.output_root/"plan/metrics.json").read_text())
    assert not any(stage.startswith("stage4") for stage in metrics["stages"])
    assert not backend.responses


def test_initial_overflow_resume_reuses_finished_modules_and_same_failed_node(tmp_path):
    task, runner, backend, _, _, _ = scenario(tmp_path)
    count = len(backend.calls)
    inject_large_context(runner, {})
    runner.run(task, resume=True, end_stage="stage4")
    assert len(backend.calls) == count


def test_unique_oversize_first_request_still_fails_before_api(tmp_path):
    from test_native_planning_loop import test_every_chunk_for_selected_evidence_is_kept_and_no_all_spec_fallback
    _, runner, backend, _, _, result = scenario(tmp_path)
    assert all(len(call["user_prompt"])+len(call["system_prompt"]) <= 256000 for call in backend.calls)
    assert len(result.module_plan_files) == 2
