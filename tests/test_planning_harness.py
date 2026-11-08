"""Durable planning repairs, bounded execution, provenance and cost accounting."""
from __future__ import annotations

import copy
import asyncio
import json
from pathlib import Path
import re
from types import SimpleNamespace

import pytest
import httpx
import openai
from pydantic import BaseModel

from rtl_artifact_test_utils import write_artifact_text
from test_responsibility_refinement import scenario
from test_rtl_module_planner import QueueBackend, make_task_input, make_stage2_responsibility_payload
from zerorepo.rpg_gen.base.llm_client import Memory, SystemMessage, UserMessage
from zerorepo.rpg_gen.base.llm_client.errors import LLMRequestTimeoutError, LLMResponseTruncatedError
from zerorepo.rpg_gen.base.llm_client.providers.bounded_completion import create_bounded_chat_completion
from zerorepo.rpg_gen.base.llm_client.request_policy import LLMRequestOptions
from test_retrieval_request_budget import wire
from zerorepo.rtl_impl.module_planner import PlannerRunner
from zerorepo.rtl_impl.module_planner.agents.base import BaseStageAgent
from zerorepo.rtl_impl.module_planner.module_organizer import build_stage2_planning_input_from_task
from zerorepo.rtl_impl.module_planner.schemas import PlannerTaskInput, ResponsibilityLedgerOutput, LockedTopModule
from zerorepo.rtl_impl.module_planner.agents import Stage2Agent
from zerorepo.rtl_impl.module_planner.agents import Stage1Agent
from zerorepo.rtl_impl.module_planner.schemas import Stage1ContractsArtifact
from zerorepo.rtl_impl.module_planner.prompts import stage2_decomposition
from zerorepo.rtl_impl.module_planner.utils import PlannerLLMClient
from zerorepo.rtl_impl.module_planner.utils.evidence import (
    EvidenceRegistry, ResponsibilityLedgerDraft, ResponsibilityRepairAdapter, deduplicate_evidence,
)
from zerorepo.rtl_impl.module_planner.utils.execution import (
    PLANNING_POLICY_VERSION, RequestExecutor, PlanningBudgetExceeded, current_node,
)
from zerorepo.rtl_impl.module_planner.utils.local_repair import JsonRepairAdapter, ArtifactIssue
from zerorepo.rtl_impl.module_planner.utils.responsibility_planning import ledger_errors


class RaisingBackend(QueueBackend):
    def complete(self, **kwargs):
        value = super().complete(**kwargs)
        if isinstance(value, Exception):
            raise value
        return value

    def complete_with_memory(self, **kwargs):
        value = super().complete_with_memory(**kwargs)
        if isinstance(value, Exception):
            raise value
        return value


class ToyOutput(BaseModel):
    value: int


class ToyAdapter(JsonRepairAdapter):
    module = "toy"

    def __init__(self):
        super().__init__(ToyOutput, "source: value must be 1")

    def semantic_issues(self, artifact):
        return [] if artifact.value == 1 else [ArtifactIssue("value", "wrong", "must be 1")]

    def targets(self, inspection):
        return {"value": {"type": "integer"}} if inspection.candidate is not None else {"$": {"type": "ToyOutput"}}


class ToyAgent(BaseStageAgent):
    stage_name = "stage3_test"
    output_model = ToyOutput
    system_role = "Generate the specified value"


def toy(tmp_path, responses, *, resume=False, policy=None):
    task, *_ = make_task_input(tmp_path, image_count=0)
    backend = RaisingBackend(responses)
    client = PlannerLLMClient(backend=backend)
    client.configure_execution(tmp_path / "case", policy)
    client.executor.begin_run(task, resume=resume)
    return task, backend, client, ToyAgent(client)


@pytest.mark.parametrize("illegal_patch", [False, True])
@pytest.mark.parametrize("retention", ["compact", "full"])
def test_timeout_resume_repairs_saved_candidate_without_regeneration(tmp_path, illegal_patch, retention):
    responses = [{"value": 0}]
    if illegal_patch:
        responses.append({"patches": [{"target": "not_allowed", "replacement": 99}]})
    responses.append(LLMRequestTimeoutError("no body", timeout_reason="first_content_timeout"))
    task, backend, client, agent = toy(tmp_path, responses)
    from zerorepo.rtl_impl.artifact_retention import ArtifactRetention
    from zerorepo.rtl_impl.artifact_layout import ArtifactLayout
    keep = ArtifactRetention(ArtifactLayout(client.output_root), retention)
    keep.initialize(task.task_id)
    with pytest.raises(LLMRequestTimeoutError):
        agent._invoke_local_repair(prompt="original generation", images=[], adapter=ToyAdapter())
    keep.compact(set())
    checkpoints = list((client.output_root / "plan/state/execution").glob("*.json"))
    saved = json.loads(checkpoints[0].read_text())
    assert saved["candidate"] == {"value": 0}
    assert saved["status"] == "failed" and saved["targets"] == {"value": {"type": "integer"}}
    # The resumed invocation has one response: a field patch, not a full object.
    resumed_backend = RaisingBackend([{"patches": [{"target": "value", "replacement": 1}]}])
    restored = PlannerLLMClient(backend=resumed_backend)
    restored.configure_execution(client.output_root)
    restored.executor.begin_run(task, resume=True)
    result = ToyAgent(restored)._invoke_local_repair(prompt="original generation", images=[], adapter=ToyAdapter())
    assert result.artifact.value == 1
    assert len(resumed_backend.calls) == 1
    assert "Repair ONLY" in resumed_backend.calls[0]["user_prompt"]
    final = json.loads(checkpoints[0].read_text())
    assert final["api_attempts"] == len(responses) + 1
    assert final["status"] == "completed"
    # Completed checkpoint is revalidated and causes zero API calls.
    restored.executor.begin_run(task, resume=True)
    ToyAgent(restored)._invoke_local_repair(prompt="original generation", images=[], adapter=ToyAdapter())
    assert len(resumed_backend.calls) == 1


@pytest.mark.parametrize("change", ["source", "template", "corruption", "force"])
def test_checkpoint_fingerprints_reject_stale_or_corrupt_candidates(tmp_path, change, monkeypatch):
    task, _, client, agent = toy(tmp_path, [{"value": 1}])
    agent._invoke_local_repair(prompt="original", images=[], adapter=ToyAdapter())
    checkpoint = next((client.output_root / "plan/state/execution").glob("*.json"))
    if change == "source":
        path = Path(task.spec_md_files[0]); write_artifact_text(path, path.read_text() + "\nchanged")
    if change == "corruption":
        value = json.loads(checkpoint.read_text()); value["candidate"] = {"value": 99}
        write_artifact_text(checkpoint, json.dumps(value))
    client.executor.begin_run(task, resume=change != "force")
    if change == "template":
        monkeypatch.setattr("zerorepo.rtl_impl.module_planner.utils.execution.template_fingerprint", lambda stage=None: "new template version")
    client.backend.responses.append({"value": 1})
    agent._invoke_local_repair(prompt="original", images=[], adapter=ToyAdapter())
    assert len(client.backend.calls) == 2


def test_api_attempt_and_time_budgets_are_shared_across_repairs(tmp_path, monkeypatch):
    _, backend, client, agent = toy(tmp_path, [{"value": 0}, {"value": 0}, {"value": 1}], policy={"max_api_attempts": 2})
    with pytest.raises(PlanningBudgetExceeded):
        agent._invoke_local_repair(prompt="budget", images=[], adapter=ToyAdapter())
    assert len(backend.calls) == 2
    metrics = json.loads((client.output_root / "plan/metrics.json").read_text())
    assert metrics["api_attempts"] == 2
    clock = [10.0]
    monkeypatch.setattr("zerorepo.rtl_impl.module_planner.utils.execution.time.monotonic", lambda: clock[0])
    executor = RequestExecutor(tmp_path / "timed", policy={"node_timeout_seconds": 3})
    with pytest.raises(PlanningBudgetExceeded), executor.node("stage3", "toy", "generation", "prompt"):
        current_node().consume()
        clock[0] = 13.1
        current_node().consume()
    def timeout_at_node_deadline():
        clock[0] += 4
        raise LLMRequestTimeoutError("total_timeout")
    # A request clamped to the node deadline must remain a hard node-budget
    # failure, including inside architecture ranking's soft fallback wrapper.
    with pytest.raises(PlanningBudgetExceeded), executor.node("stage2", "toy", "ranking", "new prompt"):
        executor.execute(timeout_at_node_deadline, {}, LLMRequestOptions(stage="stage2"))


def test_prompt_budget_rejects_without_truncating_or_calling_model(tmp_path):
    _, backend, _, agent = toy(tmp_path, [{"value": 1}], policy={"max_prompt_chars": 2})
    with pytest.raises(PlanningBudgetExceeded, match="max_prompt_chars"):
        agent._invoke_local_repair(prompt="large required evidence", images=[], adapter=ToyAdapter())
    assert not backend.calls


def test_truncated_response_is_not_a_candidate_or_a_transport_retry(tmp_path):
    _, backend, client, agent = toy(tmp_path, [LLMResponseTruncatedError("cut JSON"), {"value": 1}])
    result = agent._invoke_local_repair(prompt="original", images=[], adapter=ToyAdapter())
    assert result.artifact.value == 1 and len(backend.calls) == 2
    assert json.loads(next((client.output_root / "plan/state/execution").glob("*.json")).read_text())["candidate"] == {"value": 1}


def test_generic_stage1_quality_repair_restores_validated_shape(tmp_path):
    task, _, client, agent = toy(tmp_path, [{"value": 0}, LLMRequestTimeoutError("repair timeout")])
    agent.stage_name = "stage1_contracts"
    validator = lambda output: [] if output.value == 1 else ["value must be 1"]
    with pytest.raises(LLMRequestTimeoutError):
        agent._invoke_with_repair("round prompt", [], task, {}, quality_validator=validator)
    backend = RaisingBackend([{"value": 1}])
    restored = PlannerLLMClient(backend=backend); restored.configure_execution(client.output_root)
    restored.executor.begin_run(task, resume=True)
    agent = ToyAgent(restored); agent.stage_name = "stage1_contracts"
    result = agent._invoke_with_repair("round prompt", [], task, {}, quality_validator=validator)
    assert result.value == 1 and len(backend.calls) == 1
    assert "value must be 1" in backend.calls[0]["user_prompt"]


def test_stage1_round_prompt_is_stable_across_metadata_restore(tmp_path):
    task, *_ = make_task_input(tmp_path, image_count=0)
    first = Stage1ContractsArtifact(task_id=task.task_id)
    saved = first.model_copy(deep=True)
    saved.input_fingerprint, saved.planning_policy_version = "input digest", PLANNING_POLICY_VERSION
    agent = Stage1Agent(PlannerLLMClient(backend=QueueBackend([])))
    a, _ = agent._build_round_prompt("facts", first, {}, "source")
    b, _ = agent._build_round_prompt("facts", saved, {}, "source")
    assert a == b


@pytest.mark.parametrize("observing", [False, True])
def test_cli_and_workbench_inject_identical_request_budgets(tmp_path, monkeypatch, observing):
    class OptionsBackend:
        def complete_with_memory(self, *, memory, images=None, request_options=None):
            self.options = request_options
            return {"value": 1}
    backend = OptionsBackend()
    client = PlannerLLMClient(backend=backend)
    client.configure_execution(tmp_path)
    monkeypatch.setattr("zerorepo.rtl_impl.module_planner.agents.base.is_observing", lambda: observing)
    agent = ToyAgent(client)
    memory = Memory(); memory.add_message(SystemMessage(content="system")); memory.add_message(UserMessage(content="generate"))
    agent._complete_public(memory=memory, module="toy")
    options = backend.options
    assert options.total_timeout_seconds <= 600 and options.first_content_timeout_seconds == 240
    assert options.retry_first_content_timeout and options.retry_idle_timeout
    assert options.node_id and options.request_id


def test_workbench_observer_failure_does_not_abort_request(tmp_path, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("observer disconnected")

    class OptionsBackend:
        def complete_with_memory(self, *, memory, images=None, request_options=None):
            request_options.content_callback('{"value":1}')
            request_options.progress_callback({"status": "running"})
            return {"value": 1}

    client = PlannerLLMClient(backend=OptionsBackend()); client.configure_execution(tmp_path)
    monkeypatch.setattr("zerorepo.rtl_impl.module_planner.agents.base.is_observing", lambda: True)
    monkeypatch.setattr("zerorepo.rtl_impl.module_planner.agents.base.live_report_callback", lambda *a: broken)
    monkeypatch.setattr("zerorepo.rtl_impl.public_progress.request_progress_callback", lambda *a: broken)
    memory = Memory(); memory.add_message(SystemMessage(content="system")); memory.add_message(UserMessage(content="generate"))
    assert ToyAgent(client)._complete_public(memory=memory, module="toy") == {"value": 1}


def make_draft(tmp_path):
    task, spec, *_ = make_task_input(tmp_path, image_count=0)
    inputs = build_stage2_planning_input_from_task(task_input=task)
    registry = EvidenceRegistry(inputs)
    ledger = make_stage2_responsibility_payload(spec)
    for group in ("responsibilities", "state_objects"):
        for item in ledger[group]:
            quote = item["source_refs"][0]["quote"]
            item["source_evidence_ids"] = [k for k, v in registry.entries.items() if quote in v.quote or v.quote in quote]
            assert item["source_evidence_ids"]
            item.pop("source_refs")
    return task, inputs, registry, ledger


def test_evidence_registry_resolves_ids_and_preserves_exact_provenance(tmp_path):
    _, inputs, registry, draft = make_draft(tmp_path)
    registry.save(tmp_path / "case")
    resolved = registry.resolve(ResponsibilityLedgerDraft.model_validate(draft))
    assert not ledger_errors(resolved, inputs)
    assert all(r.content_hash and r.start_line for ru in resolved.responsibilities for r in ru.source_refs)
    assert EvidenceRegistry(inputs).entries == registry.entries
    path = Path(inputs.source_specs[0].path); write_artifact_text(path, path.read_text() + "\nsource drift")
    with pytest.raises(ValueError, match="content_hash changed"):
        registry.resolve(ResponsibilityLedgerDraft.model_validate(draft))


def test_repeated_text_uses_distinct_source_intervals_and_covers_source_lines(tmp_path):
    path = tmp_path / "repeat.md"
    write_artifact_text(path, "# Spec\n\n## A\nrepeat\n\n## B\nrepeat\n\n```verilog\nx\n\ny\n```\n")
    inputs = SimpleNamespace(source_specs=[SimpleNamespace(path=str(path), markdown=path.read_text())])
    registry = EvidenceRegistry(inputs)
    repeated = [v for v in registry.entries.values() if "repeat" in v.quote]
    assert len(repeated) == 2 and repeated[0].start_line != repeated[1].start_line
    covered = {line for value in registry.entries.values() for line in range(value.start_line, value.end_line + 1)}
    assert all(not text.strip() or index in covered for index, text in enumerate(path.read_text().splitlines(), 1))
    assert any("x\n\ny" in value.quote for value in registry.entries.values())


def test_prompt_evidence_catalog_shares_metadata_without_losing_provenance(tmp_path):
    path = tmp_path / "long_specification.md"
    text = "# Hardware specification with repeated source metadata\n\n## Shared section\n\n"
    text += "\n\n".join(f"Behavior {i}: preserve the original text exactly." for i in range(60))
    path.write_text(text)
    inputs = SimpleNamespace(source_specs=[SimpleNamespace(path=str(path), markdown=text)])
    registry = EvidenceRegistry(inputs)
    original, projected = registry.catalog(), registry.prompt_catalog()
    expanded = [{"id": item["id"], "file": projected["files"][item["file_id"]],
                 "section": projected["sections"][item["section_id"]],
                 "lines": item["lines"], "text": item["text"]} for item in projected["entries"]]
    assert expanded == original
    assert len(json.dumps(projected)) < len(json.dumps(original))
    assert {item["id"] for item in projected["entries"]} == set(registry.entries)


def test_unknown_evidence_is_repaired_as_one_field_and_reduces_full_outputs(tmp_path):
    task, inputs, registry, good = make_draft(tmp_path)
    bad = copy.deepcopy(good)
    first = bad["responsibilities"][0]
    correct_ids = first["source_evidence_ids"]
    first["source_evidence_ids"] = ["EV_unknown"]
    target = f"responsibilities[{first['responsibility_id']}].source_evidence_ids"
    patch = {"patches": [{"target": target, "replacement": correct_ids}]}
    backend = RaisingBackend([bad, patch])
    client = PlannerLLMClient(backend=backend); client.configure_execution(tmp_path / "case")
    client.executor.begin_run(task, resume=False)
    adapter = ResponsibilityRepairAdapter(registry, inputs, lambda value: ledger_errors(value, inputs))
    result = ToyAgent(client)._invoke_local_repair(prompt="Extract responsibility IDs", images=[], adapter=adapter)
    assert not ledger_errors(registry.resolve(result.artifact), inputs)
    assert len(backend.calls) == 2 and target in backend.calls[1]["user_prompt"]
    # Same controlled correction: legacy emits two full canonical ledgers;
    # the new path emits one compact draft and one exact field patch.
    canonical = registry.resolve(ResponsibilityLedgerDraft.model_validate(good)).model_dump()
    legacy_output_chars = len(json.dumps(canonical)) * 2
    new_output_chars = len(json.dumps(bad)) + len(json.dumps(patch))
    assert new_output_chars < legacy_output_chars
    metrics = json.loads((client.output_root / "plan/metrics.json").read_text())
    assert metrics["api_attempts"] == 2
    assert metrics["stages"]["stage3_test"]["unknown_usage_attempts"] == 2


def test_missing_ru_field_is_repaired_by_stable_identity(tmp_path):
    _, inputs, registry, good = make_draft(tmp_path)
    bad = copy.deepcopy(good)
    description = bad["responsibilities"][0].pop("description")
    adapter = ResponsibilityRepairAdapter(registry, inputs, lambda v: ledger_errors(v, inputs))
    inspection = adapter.inspect(bad)
    target = f"responsibilities[{bad['responsibilities'][0]['responsibility_id']}].description"
    targets = adapter.targets(inspection)
    assert set(targets) == {target}
    merged = adapter.merge(inspection, {"patches": [{"target": target, "replacement": description}]}, targets)
    assert merged == good and not adapter.inspect(merged).issues


def test_evidence_projection_deduplicates_without_dropping_behavior(tmp_path):
    _, inputs, registry, draft = make_draft(tmp_path)
    ledger = registry.resolve(ResponsibilityLedgerDraft.model_validate(draft)).model_dump()
    projected = deduplicate_evidence(ledger)
    assert projected["responsibilities"][0]["dependencies"] == ledger["responsibilities"][0]["dependencies"]
    assert projected["state_objects"][0]["owner_responsibility_id"] == ledger["state_objects"][0]["owner_responsibility_id"]
    assert projected["responsibilities"][0]["source_refs"][0]["evidence_ref"] in projected["evidence"]


def test_controlled_legacy_and_draft_cost_comparison(tmp_path):
    task, inputs, registry, draft = make_draft(tmp_path)
    canonical = make_stage2_responsibility_payload(Path(task.spec_md_files[0]))
    assert not ledger_errors(ResponsibilityLedgerOutput.model_validate(canonical), inputs)
    legacy_bad = copy.deepcopy(canonical)
    legacy_bad["responsibilities"][0]["source_refs"][0]["quote"] = "invalid source"
    draft_bad = copy.deepcopy(draft)
    draft_bad["responsibilities"][0]["source_evidence_ids"] = ["EV_unknown"]
    target = f"responsibilities[{draft['responsibilities'][0]['responsibility_id']}].source_evidence_ids"
    patch = {"responsibilities": [copy.deepcopy(draft["responsibilities"][0])]}
    locked = LockedTopModule(module="aes_cipher_top", resolution_mode="deterministic")

    def client(name, responses):
        value = PlannerLLMClient(backend=RaisingBackend(responses))
        value.configure_execution(tmp_path / name)
        value.executor.begin_run(task, resume=False)
        return value

    old = client("legacy", [legacy_bad, canonical])
    old_agent = Stage2Agent(old)
    old_agent.system_role = stage2_decomposition.RESPONSIBILITY_SYSTEM_ROLE
    old_prompt = stage2_decomposition.build_responsibility_prompt(
        prompt_context_json=old_agent.to_pretty_json(old_agent._build_stage2_prompt_context(inputs)),
        locked_top_json=locked.model_dump_json())
    old_prompt += json.dumps(ResponsibilityLedgerOutput.model_json_schema())
    old_agent._invoke_with_repair(old_prompt, [], task, {"stage2_input": inputs},
        output_model=ResponsibilityLedgerOutput, quality_validator=lambda v: ledger_errors(v, inputs))
    new = client("draft", [draft_bad, patch])
    new_agent = Stage2Agent(new)
    result = new_agent._extract_responsibilities(task=task, partial_artifacts={"stage2_input": inputs},
        prompt_context=new_agent._build_stage2_prompt_context(inputs), locked_top=locked)
    assert not ledger_errors(result, inputs)
    comparison = {}
    for name, value in (("legacy_full_output", old), ("evidence_id_patch", new)):
        metrics = json.loads((value.output_root / "plan/metrics.json").read_text())
        group = metrics["stages"]["stage2_repo_skeleton"]
        comparison[name] = {key: group[key] for key in ("api_attempts", "input_chars", "output_chars", "unknown_usage_attempts")}
    comparison["legacy_full_output"]["full_ledger_responses"] = 2
    comparison["evidence_id_patch"]["full_ledger_responses"] = 1
    write_artifact_text(tmp_path / "comparison.json", json.dumps(comparison, indent=2))
    assert comparison["evidence_id_patch"]["api_attempts"] == comparison["legacy_full_output"]["api_attempts"] == 2
    assert comparison["evidence_id_patch"]["output_chars"] < comparison["legacy_full_output"]["output_chars"]


def test_usage_is_unknown_when_absent_and_deduplicated_when_reported(tmp_path):
    executor = RequestExecutor(tmp_path)
    common = {"request_id": "req", "stage": "stage2", "transport_attempt": 1,
              "input_chars": 12, "output_chars": 4, "elapsed_seconds": 2, "status": "completed"}
    executor.record({**common, "usage": None})
    executor.record({**common, "usage": {"input_tokens": 10, "output_tokens": 5, "reasoning_tokens": 3, "cache_read_input_tokens": 4}})
    metrics = json.loads((tmp_path / "plan/metrics.json").read_text())
    assert metrics["api_attempts"] == 1
    assert metrics["stages"]["stage2"]["known_total_tokens"] == 15
    assert metrics["stages"]["stage2"]["unknown_usage_attempts"] == 0


@pytest.mark.parametrize("max_attempts", [1, 2])
@pytest.mark.parametrize("timeout_kind", ["first_content", "idle"])
def test_http_transport_retries_share_node_budget_and_usage_records(tmp_path, monkeypatch, max_attempts, timeout_kind):
    from openai._base_client import platform_headers
    platform_headers(openai.__version__, platform=None)
    calls = []
    clients = []
    monkeypatch.setattr("zerorepo.rpg_gen.base.llm_client.providers.bounded_completion.random.uniform", lambda *a: 0)

    async def handler(request):
        calls.append(request)
        if len(calls) == 1:
            if timeout_kind == "first_content":
                await asyncio.sleep(2)
            else:
                class StalledBody(httpx.AsyncByteStream):
                    async def __aiter__(self):
                        yield wire("{")
                        await asyncio.sleep(2)
                return httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=StalledBody())
        return httpx.Response(200, headers={"content-type": "text/event-stream"},
            content=wire('{"value":1}', "stop") + b"data: [DONE]\n\n")

    def factory():
        client = openai.AsyncOpenAI(api_key="test", base_url="https://fake.test/v1", max_retries=0,
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
        clients.append(client)
        return client

    def request(*, request_options):
        response = create_bounded_chat_completion(factory,
            {"model": "fake", "messages": [{"role": "user", "content": "generate"}]},
            stream=True, options=request_options, log=False)
        return response.choices[0].message.content

    executor = RequestExecutor(tmp_path, policy={"max_api_attempts": max_attempts})
    options = LLMRequestOptions(stage="stage3_test", module="toy", total_timeout_seconds=3,
        first_content_timeout_seconds=0.4, idle_timeout_seconds=0.1,
        retry_first_content_timeout=True, retry_idle_timeout=True, max_retries=1)
    if max_attempts == 1:
        with pytest.raises(PlanningBudgetExceeded), executor.node("stage3_test", "toy", "generation", "input"):
            executor.execute(request, {}, options, bounded=True)
    else:
        with executor.node("stage3_test", "toy", "generation", "input"):
            assert json.loads(executor.execute(request, {}, options, bounded=True)) == {"value": 1}
    assert len(calls) == max_attempts and all(client.is_closed() for client in clients)
    metrics = json.loads((tmp_path / "plan/metrics.json").read_text())
    assert metrics["api_attempts"] == max_attempts
    assert metrics["stages"]["stage3_test"]["unknown_usage_attempts"] == max_attempts


def test_retry_after_cannot_bypass_shared_request_deadline(tmp_path, monkeypatch):
    from test_retrieval_request_budget import bounded
    calls = []
    monkeypatch.setattr("zerorepo.rpg_gen.base.llm_client.providers.bounded_completion.random.uniform", lambda *a: 0)

    async def handler(request):
        calls.append(request)
        return httpx.Response(429, headers={"retry-after": "10"}, json={"error": {"message": "rate limited"}})

    run, clients, _ = bounded(tmp_path, handler, total_timeout_seconds=0.2,
                              first_content_timeout_seconds=1, max_retries=1)
    with pytest.raises(LLMRequestTimeoutError) as error:
        run()
    assert error.value.diagnostics["timeout_reason"] == "total_timeout"
    assert len(calls) == 1 and all(client.is_closed() for client in clients)


def test_upgrade_rejects_old_planning_then_new_version_resumes(tmp_path):
    task, runner, *_ = scenario(tmp_path)
    path = runner.layout.artifact("contracts.json")
    saved = json.loads(path.read_text())
    assert saved["planning_policy_version"] == PLANNING_POLICY_VERSION
    assert runner._read_contracts_if_valid(task) is not None
    saved.pop("planning_policy_version"); write_artifact_text(path, json.dumps(saved))
    assert runner._read_contracts_if_valid(task) is None
    # No real API calls or writes to an existing RTL file were needed.
    assert not runner.layout.rtl.exists() or not list(runner.layout.rtl.glob("*.v"))


def test_two_module_gate_after_source_patch_and_repair_timeout(tmp_path, monkeypatch):
    saved={}
    def inject(runner):
        backend=runner.llm_client.backend
        ru=backend.responses[1]["responsibilities"][0]
        good=copy.deepcopy(ru)
        ru["source_evidence_ids"]=["EV_unknown"]
        backend.responses.insert(2,{"responsibilities":[good]})
        index=next(i for i,value in enumerate(backend.responses) if isinstance(value,dict) and "module_frame" in value)
        draft=backend.responses[index]
        saved["repair"]=copy.deepcopy(draft["behavioral_obligations"][0])
        draft["behavioral_obligations"][0]["implementation_block_id"]="UNKNOWN"
        backend.responses.insert(index+1,LLMRequestTimeoutError("repair interrupted"))
        runner.llm_client.backend=RaisingBackend(backend.responses)
        saved["runner"]=runner
    with pytest.raises(LLMRequestTimeoutError): scenario(tmp_path,before_run=inject)
    runner=saved["runner"]
    backend=RaisingBackend([{"behavioral_obligations":[saved["repair"]]},*runner.llm_client.backend.responses])
    restored=PlannerRunner(output_root=runner.output_root,llm_backend=backend)
    result=restored.run(runner.llm_client.executor.scope["task"],resume=True,end_stage="stage4")
    assert len(result.completed_modules)==2
    assert "VALIDATION RESULT" in backend.calls[0]["user_prompt"]
    assert json.loads(restored.layout.artifact("planning_gate_report.json").read_text())["status"]=="passed"
