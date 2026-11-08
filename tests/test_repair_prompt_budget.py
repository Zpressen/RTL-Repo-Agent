"""Lossless repair contexts, precise request limits and saved-candidate recovery."""
from __future__ import annotations

import copy
import json
import re

import pytest

from test_planning_harness import RaisingBackend, ToyAdapter
from test_responsibility_refinement import scenario
from test_rtl_module_planner import QueueBackend, make_task_input
from zerorepo.rtl_impl.module_planner.agents import Stage3Agent
from zerorepo.rtl_impl.module_planner.utils import PlannerLLMClient
from zerorepo.rtl_impl.module_planner.utils.execution import PlanningBudgetExceeded
from zerorepo.rtl_impl.module_planner.utils.local_repair import ArtifactIssue, repair_prompt
from zerorepo.rtl_impl.module_planner.utils.prompt_context import share_repair_context, native_target_originals


def expand_shared(bundle):
    def expand(item):
        if isinstance(item, dict):
            if set(item) == {"context_ref"}:
                return expand(bundle["shared_values"][item["context_ref"]])
            return {k: expand(v) for k, v in item.items()}
        return [expand(v) for v in item] if isinstance(item, list) else item
    return expand(bundle["inputs"])


def expand_evidence(projected):
    def visit(item):
        if isinstance(item, dict):
            if set(item) == {"evidence_ref"}:
                return projected["evidence"][item["evidence_ref"]]
            return {k: visit(v) for k, v in item.items()}
        return [visit(v) for v in item] if isinstance(item, list) else item
    return visit({k: v for k, v in projected.items() if k != "evidence"})


def test_sharing_roundtrip_retains_every_value_and_does_not_mutate_inputs():
    source = {"source_file": "spec.md", "quote": "Exact text\n" * 200, "start_line": 2, "end_line": 201,
              "content_hash": "hash", "section_path": "Spec > State"}
    repeated = {"source_refs": [source], "effects": ["must preserve reset and hold " * 30]}
    inputs = {"targets": {"a": repeated, "b": repeated}, "context": {"responsibilities": [repeated] * 12}}
    original = copy.deepcopy(inputs)
    packed = share_repair_context(inputs)
    assert packed["shared_values"]
    assert expand_evidence(expand_shared(packed)) == original
    assert inputs == original
    assert json.dumps(packed).count("Exact text") == 200


def test_equal_quotes_at_different_source_locations_remain_distinct():
    a = {"source_file": "spec.md", "quote": "repeated", "start_line": 1, "end_line": 1, "content_hash": "a"}
    b = {**a, "start_line": 8, "end_line": 8}
    inputs = {"sources": [a, b, a], "other": {"same": b}}
    packed = expand_shared(share_repair_context(inputs))
    assert len(packed["evidence"]) == 2
    assert expand_evidence(packed) == inputs


def test_native_original_projection_keeps_malformed_text_and_target_identity():
    targets = {"obj": {"replacement_type": "json_object", "original": '{"quote":"a\\nb"}'},
               "list": {"replacement_type": "json_array", "original": '```json\n[1,2]\n```'},
               "malformed": {"replacement_type": "json_array", "original": '```json\n[{"a":1'},
               "markdown": {"replacement_type": "markdown", "original": "```json\n[1,2]\n```"}}
    original = copy.deepcopy(targets)
    projected = native_target_originals(targets)
    assert projected["obj"]["original"] == {"quote": "a\nb"}
    assert projected["list"]["original"] == [1, 2]
    assert projected["malformed"] == original["malformed"]
    assert projected["markdown"] == original["markdown"]
    assert targets == original


def test_many_source_errors_fit_without_losing_any_diagnostic_or_evidence():
    refs = [{"source_file": "spec.md", "quote": f"paragraph {i}\n" + "verbatim source text " * 150,
             "start_line": i, "content_hash": "hash"} for i in range(30)]
    issues = [ArtifactIssue("behavioral_obligations", "unbound_source", "Must inherit canonical sources",
                           expected={"allowed_source_refs": refs}, unit_id=f"OB_{i}") for i in range(20)]
    targets = {f"obligation:{i}/source_refs": {"original": refs[:1], "expected": {"type": "array"}} for i in range(20)}
    context = {"responsibilities": [{"source_refs": refs, "description": "Do all specified behaviors"}] * 10}
    raw = repair_prompt(targets=targets, issues=issues, context=context)
    packed = repair_prompt(targets=targets, issues=issues, context=context, compact=True)
    assert len(raw) > 256000 and len(packed) < 256000
    bundle = json.loads(packed.split("Targets, all diagnostics, source context, evidence and shared values:\n", 1)[1])
    restored = expand_evidence(expand_shared(bundle))
    assert restored == {"targets": targets, "diagnostics": [x.to_dict() for x in issues], "context": context}


@pytest.mark.parametrize("retention", ["compact", "full"])
def test_two_module_gate_with_over_limit_repeated_repair_context(tmp_path, retention):
    from copy import deepcopy
    def prepare(runner):
        backend=runner.llm_client.backend
        index=next(i for i,value in enumerate(backend.responses) if isinstance(value,dict) and "module_frame" in value)
        good=deepcopy(backend.responses[index]["behavioral_obligations"][0])
        backend.responses[index]["behavioral_obligations"][0]["source_evidence_ids"]=["EV_unknown"]
        backend.responses.insert(index+1,{"behavioral_obligations":[good]})
    _, runner, backend, _, _, result=scenario(tmp_path,before_run=prepare,artifacts={"retention":retention})
    repairs=[call["user_prompt"] for call in backend.calls if "VALIDATION RESULT" in call["user_prompt"]]
    assert len(repairs)==1 and len(repairs[0])<256000
    assert len(result.module_plan_files)==2
    assert json.loads(runner.layout.artifact("planning_gate_report.json").read_text())["status"]=="passed"


def test_genuine_overflow_keeps_candidate_and_measured_budget_then_resumes(tmp_path):
    task, *_ = make_task_input(tmp_path, image_count=0)
    root = tmp_path / "case"
    initial = RaisingBackend([{"value": 0}, RuntimeError("interrupted")])
    client = PlannerLLMClient(backend=initial)
    client.configure_execution(root)
    client.executor.begin_run(task, resume=False)
    with pytest.raises(RuntimeError, match="interrupted"):
        Stage3Agent(client)._invoke_local_repair(prompt="original", images=[], adapter=ToyAdapter())
    backend = QueueBackend([])
    limited = PlannerLLMClient(backend=backend)
    limited.configure_execution(root, {"max_prompt_chars": 100})
    limited.executor.begin_run(task, resume=True)
    with pytest.raises(PlanningBudgetExceeded, match="no API attempt started"):
        Stage3Agent(limited)._invoke_local_repair(prompt="original", images=[], adapter=ToyAdapter())
    assert not backend.calls
    checkpoint = next((root / "plan/state/execution").glob("*.json"))
    state = json.loads(checkpoint.read_text())
    assert state["candidate"] == {"value": 0}
    assert not state["prompt_budget"]["fits"] and state["prompt_budget"]["candidate_retained"]
    assert state["prompt_budget"]["input_chars"] == sum(m["chars"] for m in state["prompt_budget"]["message_chars"])
    resumed = QueueBackend([{"patches": [{"target": "value", "replacement": 1}]}])
    client = PlannerLLMClient(backend=resumed)
    client.configure_execution(root)
    client.executor.begin_run(task, resume=True)
    result = Stage3Agent(client)._invoke_local_repair(prompt="original", images=[], adapter=ToyAdapter())
    assert result.artifact.value == 1 and len(resumed.calls) == 1
    assert "Repair ONLY" in resumed.calls[0]["user_prompt"]
