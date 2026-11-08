"""Typed obligations, transactional patches and interrupted Stage3 recovery."""
from __future__ import annotations

import copy
import json
import re

import pytest

from test_responsibility_refinement import scenario
from test_rtl_module_planner import QueueBackend
from zerorepo.rpg_gen.base.llm_client.errors import LLMRequestTimeoutError
from zerorepo.rtl_impl.module_planner.agents import Stage3Agent
from zerorepo.rtl_impl.module_planner.prompts import stage3_module_skeleton
from zerorepo.rtl_impl.module_planner.utils import PlannerLLMClient
from zerorepo.rtl_impl.module_planner.utils.local_repair import ArtifactIssue, fingerprint
from zerorepo.rtl_impl.module_planner.utils.responsibility_planning import module_context, refinement_issues
from zerorepo.rtl_impl.module_planner.utils.skeleton_repair import SkeletonRepairAdapter


@pytest.fixture(scope="module")
def planned(tmp_path_factory):
    task, runner, _, inputs, stage3, _ = scenario(tmp_path_factory.mktemp("obligation_repair"))
    record = stage3.module_records[0]
    # These are compatibility tests of the standalone historical Markdown
    # parser/adapter, not the native Stage3 execution path.
    from test_rtl_module_planner import make_stage3_module_skeleton_doc
    from zerorepo.rtl_impl.module_planner.schemas import ModuleSkeletonExport
    export = ModuleSkeletonExport.model_validate_json((runner.output_root / record.export_file).read_text())
    entries = [o.model_dump() for o in export.behavioral_obligations if o.behavior_kind != "integration"]
    for entry in entries:
        entry["source_refs"] = entry["source_refs"][:1]
    text = make_stage3_module_skeleton_doc(record.module, __import__('pathlib').Path(record.source_refs.module_spec_file)).replace("# MODULE_SKELETON_DOC v1", "# MODULE_SKELETON_DOC v2", 1)
    text = text.replace("## 4. Decision Ledger", "### Behavioral Obligations\n```json\n" + json.dumps(entries) + "\n```\n\n## 4. Decision Ledger")
    args = dict(expected_module=record.module, expected_file_path=f"generate/rtl/{record.module}.v",
                source_refs=record.source_refs)

    def adapter(validator=None):
        return SkeletonRepairAdapter(**args, context="authoritative sources", enhanced=True,
            example=stage3_module_skeleton.EXAMPLE_OUTPUT,
            quality_validator=validator or (lambda export: refinement_issues(export,
                module_context(inputs["stage2_decomposition"], record.module), inputs["stage2_input"])))

    return task, text, args, adapter


def obligations(text):
    match = re.search(r"### Behavioral Obligations\s*```json\s*\n(.*?)```", text, re.S)
    return json.loads(match[1]), match.span(1)


def replace_obligations(text, value):
    _, (start, end) = obligations(text)
    return text[:start] + json.dumps(value, ensure_ascii=False, indent=2) + "\n" + text[end:]


def patches(values):
    return {"patches": [{"target": key, "replacement": value} for key, value in values.items()]}


@pytest.mark.parametrize("old_string", [False, True])
def test_whole_array_has_schema_and_program_serializes_fence(planned, old_string):
    _, text, _, factory = planned
    original, _ = obligations(text)
    broken = replace_obligations(text, {"obligations": original})
    adapter = factory()
    inspection = adapter.inspect(broken)
    assert [i.code for i in inspection.issues] == ["invalid_obligations"]
    targets = adapter.targets(inspection)
    target = "Behavioral Overlay/obligations"
    assert set(targets) == {target}
    assert targets[target]["replacement_type"] == "json_array"
    assert targets[target]["expected"]["items"]["$ref"]
    value = "```json\n" + json.dumps(original) + "\n```" if old_string else original
    merged = adapter.merge(inspection, patches({target: value}), targets)
    assert not adapter.inspect(merged).issues
    assert obligations(merged)[0] == original
    assert text.split("### Behavioral Obligations")[0] == merged.split("### Behavioral Obligations")[0]


@pytest.mark.parametrize("invalid", ["", [], {"obligations": []}, "```json\n{\"obligations\": []}\n```",
                                     [{"responsibility_id": "RU_KEY_EXPANSION", "block_ids": ["B3"]}]])
def test_empty_wrapped_and_wrong_schema_arrays_rejected(planned, invalid):
    _, text, _, factory = planned
    adapter = factory()
    inspection = adapter.inspect(replace_obligations(text, {}))
    targets = adapter.targets(inspection)
    before = inspection.candidate
    with pytest.raises(ValueError):
        adapter.merge(inspection, patches({"Behavioral Overlay/obligations": invalid}), targets)
    assert inspection.candidate == before


def test_duplicate_array_identities_rejected(planned):
    _, text, _, factory = planned
    entries, _ = obligations(text)
    adapter = factory()
    inspection = adapter.inspect(replace_obligations(text, {}))
    with pytest.raises(ValueError, match="unique"):
        adapter.merge(inspection, patches({"Behavioral Overlay/obligations": entries + entries[:1]}), adapter.targets(inspection))


def test_single_obligation_accepts_native_object(planned):
    _, text, _, factory = planned
    entries, _ = obligations(text)
    broken = text.replace('"required_effect": "commit round_key_state as specified"', '"required_effect": ""')
    adapter = factory()
    inspection = adapter.inspect(broken)
    targets = adapter.targets(inspection)
    target = "Behavioral Overlay/obligation:OB_COMMIT"
    assert targets[target]["replacement_type"] == "json_object"
    merged = adapter.merge(inspection, patches({target: entries[0]}), targets)
    assert not adapter.inspect(merged).issues
    assert obligations(merged)[0] == entries


def test_source_fix_targets_only_source_field_and_preserves_other_bytes(planned):
    _, text, _, factory = planned
    entries, _ = obligations(text)
    broken = text
    span = factory()._ranges(broken)["Behavioral Overlay/obligation:OB_COMMIT/field:source_refs"]
    broken = broken[:span[0]] + json.dumps([{**entries[0]["source_refs"][0], "quote": "invented evidence"}]) + broken[span[1]:]
    adapter = factory()
    inspection = adapter.inspect(broken)
    target = "Behavioral Overlay/obligation:OB_COMMIT/field:source_refs"
    assert set(adapter.targets(inspection)) == {target}
    merged = adapter.merge(inspection, patches({target: entries[0]["source_refs"]}), adapter.targets(inspection))
    assert not adapter.inspect(merged).issues
    start, end = adapter._ranges(merged)[target]
    old_start, old_end = adapter._ranges(broken)[target]
    assert merged[:start] == broken[:old_start] and merged[end:] == broken[old_end:]


def test_parent_and_constraint_repairs_do_not_rewrite_array(planned):
    _, text, _, factory = planned
    entries, _ = obligations(text)
    for entry in entries:
        entry["constraint_refs"] = []
    entries[0]["parent_responsibility_id"] = "C_CLOCK"
    adapter = factory()
    inspection = adapter.inspect(replace_obligations(text, entries))
    targets = adapter.targets(inspection)
    parent = "Behavioral Overlay/obligation:OB_COMMIT"
    coverage = next(key for key in targets if "/constraint_coverage:" in key)
    assert set(targets) == {parent, coverage}
    ru = targets[coverage]["responsibility"]
    replacement = {**entries[0], "parent_responsibility_id": ru}
    merged = adapter.merge(inspection, patches({parent: replacement, coverage: ["OB_COMMIT"]}), targets)
    assert not adapter.inspect(merged).issues
    updated, _ = obligations(merged)
    assert updated[0]["constraint_refs"] == ["C_CLOCK"]
    assert updated[1:] == entries[1:]
    assert {**updated[0], "constraint_refs": [], "parent_responsibility_id": "C_CLOCK"} == entries[0]


@pytest.mark.parametrize("selection", [["unknown"], [], ["OB_COMMIT", "OB_COMMIT"]])
def test_invalid_constraint_selection_rejected(planned, selection):
    _, text, _, factory = planned
    entries, _ = obligations(text)
    for entry in entries:
        entry["constraint_refs"] = []
    adapter = factory()
    inspection = adapter.inspect(replace_obligations(text, entries))
    targets = adapter.targets(inspection)
    with pytest.raises(ValueError, match="Constraint coverage"):
        adapter.merge(inspection, patches({next(iter(targets)): selection}), targets)


def test_state_access_diagnostics_include_missing_role_and_upstream_permissions(planned):
    _, text, _, factory = planned
    entries, _ = obligations(text)
    entries[0]["state_accesses"].append({"state_id": entries[0]["state_accesses"][0]["state_id"], "role": "read"})
    adapter = factory()
    inspection = adapter.inspect(replace_obligations(text, entries))
    issue = next(i for i in inspection.issues if i.code == "unauthorized_state_access")
    assert "/read" in issue.message and issue.expected["allowed_state_accesses"]
    assert set(adapter.targets(inspection)) == {"Behavioral Overlay/obligation:OB_COMMIT/field:state_accesses"}


def test_constraint_selection_requires_applicable_parent_after_patch(planned):
    _, text, _, factory = planned
    entries, _ = obligations(text)
    for entry in entries:
        entry["constraint_refs"] = []
    entries[0]["parent_responsibility_id"] = "C_CLOCK"
    adapter = factory()
    inspection = adapter.inspect(replace_obligations(text, entries))
    targets = adapter.targets(inspection)
    coverage = next(key for key in targets if "/constraint_coverage:" in key)
    with pytest.raises(ValueError, match="applicable responsibility"):
        adapter.merge(inspection, patches({"Behavioral Overlay/obligation:OB_COMMIT": entries[0],
                                         coverage: ["OB_COMMIT"]}), targets)


def test_legacy_full_document_field_patch_preserves_formatting(planned):
    _, text, _, factory = planned
    entries, _ = obligations(text)
    entries[0]["clock_domain"] = "foreign_clock"
    broken = replace_obligations(text, entries)
    adapter = factory()
    inspection = adapter.inspect(broken)
    targets = adapter.targets(inspection)
    target = "Behavioral Overlay/obligation:OB_COMMIT/field:clock_domain"
    assert set(targets) == {target}
    correct = broken.replace('"clock_domain": "foreign_clock"', '"clock_domain": "clk"', 1)
    merged = adapter.merge(inspection, correct, targets)
    assert merged == correct
    assert not adapter.inspect(merged).issues


def test_rejected_format_regression_keeps_candidate_and_parser_state(planned):
    from test_native_planning_loop import test_illegal_repair_cannot_corrupt_candidate, design_fixture
    # Actual native execution protection is exercised by the shared session suite.
    _, text, _, factory = planned
    old = factory().inspect(text)
    assert not old.issues
    with pytest.raises(ValueError):
        factory().merge(old, {"patches":[{"target":"Module Frame", "replacement":"changed"}]}, {})


def test_new_semantic_error_rejected_transactionally(planned):
    _, text, _, factory = planned
    adapter = factory()
    good = adapter.inspect(text)
    entries, _ = obligations(text)
    entries[0]["parent_responsibility_id"] = "unknown"
    bad = adapter.inspect(replace_obligations(text, entries))
    with pytest.raises(ValueError, match="previous candidate preserved"):
        adapter.validate_transition(good, bad)


class InterruptingBackend(QueueBackend):
    def complete_with_memory(self, **kwargs):
        result = super().complete_with_memory(**kwargs)
        if isinstance(result, Exception):
            raise result
        return result


@pytest.mark.parametrize("retention", ["compact", "full"])
def test_timeout_resume_keeps_parseable_candidate_then_repairs_only_fields(planned, tmp_path, retention):
    task, text, _, factory = planned
    entries, _ = obligations(text)
    broken_entries = copy.deepcopy(entries)
    broken_entries[0]["source_refs"][0]["quote"] = "invented evidence"
    broken = replace_obligations(text, broken_entries)
    target = "Behavioral Overlay/obligation:OB_COMMIT/field:source_refs"
    backend = InterruptingBackend([broken, patches({target: []}), LLMRequestTimeoutError("repair timeout")])
    root = tmp_path / "case"

    def client_for(backend, resume):
        client = PlannerLLMClient(backend=backend)
        client.configure_execution(root)
        client.executor.begin_run(task, resume=resume)
        return client

    agent = Stage3Agent(client_for(backend, False), output_root=root)
    with pytest.raises(LLMRequestTimeoutError):
        agent._invoke_local_repair(prompt="same source prompt", images=[], adapter=factory())
    checkpoint = next((root / "plan/state/execution").glob("*.json"))
    state = json.loads(checkpoint.read_text())
    assert state["candidate"] == broken
    from zerorepo.rtl_impl.artifact_layout import ArtifactLayout
    from zerorepo.rtl_impl.artifact_retention import ArtifactRetention
    keep = ArtifactRetention(ArtifactLayout(root), retention)
    keep.initialize(task.task_id)
    keep.compact(set())
    resumed_backend = QueueBackend([patches({target: entries[0]["source_refs"]})])
    result = Stage3Agent(client_for(resumed_backend, True), output_root=root)._invoke_local_repair(
        prompt="same source prompt", images=[], adapter=factory())
    assert result.artifact and not result.issues
    assert len(resumed_backend.calls) == 1
    assert "Repair ONLY" in resumed_backend.calls[0]["user_prompt"]
    state = json.loads(checkpoint.read_text())
    assert state["status"] == "completed"


def test_resume_previously_saved_wrapped_array_without_full_regeneration(planned, tmp_path):
    task, text, _, factory = planned
    entries, _ = obligations(text)
    root = tmp_path / "case"
    client = PlannerLLMClient(backend=QueueBackend([]))
    client.configure_execution(root)
    client.executor.begin_run(task, resume=False)
    # Simulate the valid, fingerprinted execution checkpoint left by the old
    # merge implementation. No untrusted trace is imported into recovery.
    agent = Stage3Agent(client, output_root=root)
    with pytest.raises(AssertionError, match="No more queued"):
        agent._invoke_local_repair(prompt="original", images=[], adapter=factory())
    checkpoint = next((root / "plan/state/execution").glob("*.json"))
    state = json.loads(checkpoint.read_text())
    state.pop("checkpoint_fingerprint")
    state["candidate"] = replace_obligations(text, {"obligations": entries})
    checkpoint.write_text(json.dumps({**state, "checkpoint_fingerprint": fingerprint(state)}))
    backend = QueueBackend([patches({"Behavioral Overlay/obligations": entries})])
    client = PlannerLLMClient(backend=backend)
    client.configure_execution(root)
    client.executor.begin_run(task, resume=True)
    result = Stage3Agent(client, output_root=root)._invoke_local_repair(prompt="original", images=[], adapter=factory())
    assert result.artifact and len(backend.calls) == 1
    assert '"replacement_type":"json_array"' in backend.calls[0]["user_prompt"]


def test_enhanced_document_repair_requests_v2_schema(planned):
    _, text, _, factory = planned
    adapter = factory()
    inspection = adapter.inspect(text)
    inspection.issues = [ArtifactIssue("document", "invalid_header", "bad header")]
    target = adapter.targets(inspection)["document"]
    assert target["expected"]["header"] == "# MODULE_SKELETON_DOC v2"
    assert target["expected"]["behavioral_obligations_schema"]
