"""Do not hide dependent errors or discard valid progress after fixing a parent."""
from __future__ import annotations

import copy
import json

import pytest

from test_repair_prompt_budget import expand_shared
from test_rtl_module_planner import QueueBackend
from test_stage3_obligation_repair import planned as build_planned_fixture, obligations, replace_obligations, patches
from zerorepo.rtl_impl.module_planner.agents import Stage3Agent
from zerorepo.rtl_impl.module_planner.agents.base import StageGenerationError
from zerorepo.rtl_impl.module_planner.utils import PlannerLLMClient


@pytest.fixture(scope="module")
def planned(tmp_path_factory):
    return build_planned_fixture.__wrapped__(tmp_path_factory)


def broken_parent(planned, *, kind="inst", clock=None):
    _, text, _, factory = planned
    entries, _ = obligations(text)
    extra = copy.deepcopy(entries[0])
    extra.update(obligation_id="OB_CHILD_INTEGRATION", parent_responsibility_id="C_CLOCK",
                 behavior_kind="invariant", state_accesses=[],
                 implementation_block_id="B2" if kind == "inst" else "B3", supporting_block_ids=["B1"],
                 required_effect="Coordinate child integration without duplicating child-owned resources")
    if clock:
        extra["clock_domain"] = clock
    return text, entries, extra, replace_obligations(text, [*entries, extra]), factory


@pytest.mark.parametrize("mutation,expected", [
    ("delegation", "invalid_delegation"), ("block", "invalid_implementation_block"),
    ("support", "unknown_block"), ("state", "unknown_state"),
])
def test_independent_checks_run_despite_invalid_parent(planned, mutation, expected):
    text, entries, extra, _, factory = broken_parent(planned)
    if mutation == "block": extra["implementation_block_id"] = "BAD"
    if mutation == "support": extra["supporting_block_ids"] = ["BAD"]
    if mutation == "state": extra["state_accesses"] = [{"state_id": "BAD", "role": "read"}]
    inspection = factory().inspect(replace_obligations(text, [*entries, extra]))
    issues = {i.code: i for i in inspection.issues if i.unit_id == extra["obligation_id"]}
    assert "unknown_responsibility" in issues and expected in issues
    if mutation == "delegation":
        assert issues[expected].expected["required_behavior_kind"] == "integration"


def test_parent_fix_is_retained_then_only_remaining_obligation_is_repaired(planned):
    _, entries, extra, broken, factory = broken_parent(planned)
    adapter = factory()
    old = adapter.inspect(broken)
    assert {i.code for i in old.issues} == {"unknown_responsibility", "invalid_delegation"}
    target = "Behavioral Overlay/obligation:OB_CHILD_INTEGRATION"
    fixed_parent = {**extra, "parent_responsibility_id": entries[0]["parent_responsibility_id"]}
    candidate = adapter.merge(old, patches({target: fixed_parent}), adapter.targets(old))
    progress = adapter.inspect(candidate)
    adapter.validate_transition(old, progress)
    assert [i.code for i in progress.issues] == ["invalid_delegation"]
    assert set(adapter.targets(progress)) == {target}
    final = adapter.merge(progress, patches({target: {**fixed_parent, "behavior_kind": "integration"}}), adapter.targets(progress))
    assert not adapter.inspect(final).issues
    assert obligations(final)[0][:-1] == entries


def test_correcting_parent_can_expose_unchanged_contract_error(planned):
    _, entries, extra, broken, factory = broken_parent(planned, kind="seq", clock="old_unbound_clock")
    adapter = factory()
    old = adapter.inspect(broken)
    assert [i.code for i in old.issues] == ["unknown_responsibility"]
    target = "Behavioral Overlay/obligation:OB_CHILD_INTEGRATION"
    fixed_parent = {**extra, "parent_responsibility_id": entries[0]["parent_responsibility_id"]}
    proposed = adapter.inspect(adapter.merge(old, patches({target: fixed_parent}), adapter.targets(old)))
    assert [i.code for i in proposed.issues] == ["contract_drift"]
    adapter.validate_transition(old, proposed)
    assert set(adapter.targets(proposed)) == {target + "/field:clock_domain"}


def test_parent_fix_cannot_introduce_new_bad_contract_data(planned):
    _, entries, extra, broken, factory = broken_parent(planned, kind="seq")
    adapter = factory()
    old = adapter.inspect(broken)
    target = "Behavioral Overlay/obligation:OB_CHILD_INTEGRATION"
    changed = {**extra, "parent_responsibility_id": entries[0]["parent_responsibility_id"], "clock_domain": "invented_clock"}
    proposed = adapter.inspect(adapter.merge(old, patches({target: changed}), adapter.targets(old)))
    with pytest.raises(ValueError, match="previous candidate preserved"):
        adapter.validate_transition(old, proposed)


def test_existing_access_errors_can_be_exposed_even_if_bindings_are_reordered(planned):
    text, entries, extra, _, factory = broken_parent(planned, kind="seq")
    state = entries[0]["state_accesses"][0]["state_id"]
    extra["state_accesses"] = [{"state_id": state, "role": "read"}, {"state_id": state, "role": "compute_next"}]
    adapter = factory()
    old = adapter.inspect(replace_obligations(text, [*entries, extra]))
    assert [i.code for i in old.issues] == ["unknown_responsibility"]
    fixed = {**extra, "parent_responsibility_id": entries[0]["parent_responsibility_id"],
             "state_accesses": list(reversed(extra["state_accesses"]))}
    target = "Behavioral Overlay/obligation:OB_CHILD_INTEGRATION"
    new = adapter.inspect(adapter.merge(old, patches({target: fixed}), adapter.targets(old)))
    assert {i.code for i in new.issues} == {"unauthorized_state_access"}
    adapter.validate_transition(old, new)


def test_parent_fix_cannot_regress_an_unrelated_obligation(planned):
    text, entries, extra, broken, factory = broken_parent(planned, kind="seq", clock="old_unbound_clock")
    adapter = factory()
    old = adapter.inspect(broken)
    extra["parent_responsibility_id"] = entries[0]["parent_responsibility_id"]
    entries[0]["clock_domain"] = "invented_unrelated_clock"
    proposed = adapter.inspect(replace_obligations(text, [*entries, extra]))
    with pytest.raises(ValueError, match="previous candidate preserved"):
        adapter.validate_transition(old, proposed)


def test_parent_fix_can_reveal_state_conflict_and_targets_only_related_entries(planned):
    text, entries, extra, _, factory = broken_parent(planned)
    extra["state_accesses"] = copy.deepcopy(entries[0]["state_accesses"])
    adapter = factory()
    old = adapter.inspect(replace_obligations(text, [*entries, extra]))
    assert "state_commit_kind" in {i.code for i in old.issues}
    target = "Behavioral Overlay/obligation:OB_CHILD_INTEGRATION"
    fixed = {**extra, "parent_responsibility_id": entries[0]["parent_responsibility_id"]}
    proposed = adapter.inspect(adapter.merge(old, patches({target: fixed}), adapter.targets(old)))
    assert "state_commit_conflict" in {i.code for i in proposed.issues}
    adapter.validate_transition(old, proposed)
    targets = adapter.targets(proposed)
    assert "Behavioral Overlay/obligations" not in targets
    assert target in targets and all("/obligation:" in key for key in targets)
    replacements = {f"Behavioral Overlay/obligation:{entry['obligation_id']}": entry for entry in entries}
    replacements[target] = {**fixed, "implementation_block_id": "B3", "behavior_kind": "state_update"}
    final = adapter.inspect(adapter.merge(proposed, patches(replacements), targets))
    assert not final.issues


def setup_client(root, task, backend, resume):
    client = PlannerLLMClient(backend=backend)
    client.configure_execution(root)
    client.executor.begin_run(task, resume=resume)
    return client


def test_resume_revalidates_saved_patch_then_requests_only_remaining_error(planned, tmp_path):
    task, *_ = planned
    _, entries, extra, broken, factory = broken_parent(planned)
    target = "Behavioral Overlay/obligation:OB_CHILD_INTEGRATION"
    fixed_parent = {**extra, "parent_responsibility_id": entries[0]["parent_responsibility_id"]}
    root = tmp_path / "case"
    old_backend = QueueBackend([broken, patches({target: fixed_parent})])
    old_adapter = factory()
    def old_guard(*args):
        raise ValueError("old guard discards the entire patch")
    old_adapter.validate_transition = old_guard
    with pytest.raises(StageGenerationError):
        Stage3Agent(setup_client(root, task, old_backend, False))._invoke_local_repair(
            prompt="same original generation", images=[], adapter=old_adapter, max_attempts=2)
    checkpoint = next((root / "plan/state/execution").glob("*.json"))
    assert json.loads(checkpoint.read_text())["candidate"] == broken
    backend = QueueBackend([patches({target: {**fixed_parent, "behavior_kind": "integration"}})])
    result = Stage3Agent(setup_client(root, task, backend, True))._invoke_local_repair(
        prompt="same original generation", images=[], adapter=factory())
    assert not result.issues and len(backend.calls) == 1
    prompt = backend.calls[0]["user_prompt"]
    bundle = json.loads(prompt.split("Targets, all diagnostics, source context, evidence and shared values:\n", 1)[1])
    inputs = expand_shared(bundle)
    assert set(inputs["targets"]) == {target}
    assert [d["code"] for d in inputs["diagnostics"]] == ["invalid_delegation"]
    assert inputs["targets"][target]["original"]["parent_responsibility_id"] == fixed_parent["parent_responsibility_id"]
    records = [json.loads(line) for line in (root / "plan/state/request_usage.jsonl").read_text().splitlines()]
    assert any(r.get("operation", "").endswith(".saved_patch") for r in records)
    state = json.loads(checkpoint.read_text())
    assert state["status"] == "completed" and state["api_attempts"] == 3


def test_resume_does_not_apply_an_unauthorized_saved_patch(planned, tmp_path):
    task, *_ = planned
    _, entries, extra, broken, factory = broken_parent(planned)
    root = tmp_path / "case"
    backend = QueueBackend([broken, patches({"Module Frame": "forbidden"})])
    with pytest.raises(StageGenerationError):
        Stage3Agent(setup_client(root, task, backend, False))._invoke_local_repair(
            prompt="same original generation", images=[], adapter=factory(), max_attempts=2)
    target = "Behavioral Overlay/obligation:OB_CHILD_INTEGRATION"
    final = {**extra, "parent_responsibility_id": entries[0]["parent_responsibility_id"], "behavior_kind": "integration"}
    backend = QueueBackend([patches({target: final})])
    result = Stage3Agent(setup_client(root, task, backend, True))._invoke_local_repair(
        prompt="same original generation", images=[], adapter=factory())
    assert not result.issues and "unknown_responsibility" in backend.calls[0]["user_prompt"]
