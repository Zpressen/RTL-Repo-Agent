"""Relational ledger errors must target the entity containing the broken field."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from test_planning_harness import make_draft, RaisingBackend
from test_responsibility_refinement import scenario, report
from zerorepo.rpg_gen.base.llm_client.errors import LLMRequestTimeoutError
from zerorepo.rtl_impl.module_planner.agents import Stage2Agent
from zerorepo.rtl_impl.module_planner.agents.base import StageGenerationError
from zerorepo.rtl_impl.module_planner.schemas import LockedTopModule
from zerorepo.rtl_impl.module_planner.utils import PlannerLLMClient
from zerorepo.rtl_impl.module_planner.utils.evidence import ResponsibilityLedgerDraft
from zerorepo.rtl_impl.module_planner.utils.local_repair import ArtifactIssue
from zerorepo.rtl_impl.module_planner.utils.planning_session import ledger_scope, merge_entities
from zerorepo.rtl_impl.module_planner.utils.responsibility_planning import ledger_issues, ledger_errors


def extract(root, task, inputs, responses, *, resume=False):
    backend = RaisingBackend(responses)
    client = PlannerLLMClient(backend=backend)
    client.configure_execution(root)
    client.executor.begin_run(task, resume=resume)
    agent = Stage2Agent(client)
    locked = LockedTopModule(module="aes_cipher_top", resolution_mode="deterministic")
    def run():
        return agent._extract_responsibilities(
            task=task, partial_artifacts={"stage2_input": inputs},
            prompt_context=agent._build_stage2_prompt_context(inputs), locked_top=locked)
    return backend, run


def test_missing_commits_target_owners_and_keep_state_table_locked(tmp_path):
    _, inputs, registry, good = make_draft(tmp_path)
    bad = deepcopy(good)
    for ru in bad["responsibilities"]:
        ru.pop("state_accesses")  # Exactly the omission in the captured E203 response.
    issues = ledger_issues(registry.resolve(ResponsibilityLedgerDraft.model_validate(bad)), inputs)
    assert len(issues) == len(good["state_objects"])
    for issue, state in zip(issues, good["state_objects"]):
        assert issue.code == "missing_state_commit"
        assert issue.unit_id == state["owner_responsibility_id"]
        assert issue.path == f"responsibilities[{issue.unit_id}].state_accesses"
        assert issue.expected["required_access"] == {"state_id": state["state_id"], "role": "commit"}
    scope = ledger_scope(bad, issues + issues)
    assert scope == {"entities": {"responsibilities": {
        "identity": "responsibility_id", "ids": [r["responsibility_id"] for r in good["responsibilities"]]}}}
    repaired = merge_entities(bad, {"responsibilities": good["responsibilities"]}, scope)
    assert repaired == good
    assert not ledger_errors(registry.resolve(ResponsibilityLedgerDraft.model_validate(repaired)), inputs)
    changed = deepcopy(good["state_objects"])
    changed[0]["owner_responsibility_id"] = good["responsibilities"][1]["responsibility_id"]
    with pytest.raises(ValueError, match="Untargeted ledger section"):
        merge_entities(bad, {"state_objects": changed}, scope)


@pytest.mark.parametrize("path,unit_id,message,group,identity", [
    ("responsibilities[R1].dependencies", "R1", "R1 invalid dependency to R2", "responsibilities", "R1"),
    ("state_objects[S1].owner_responsibility_id", "S1", "state S1 invalid owner R1", "state_objects", "S1"),
    ("responsibilities[0].state_accesses[0].role", "", "state S1 has a bad role", "responsibilities", "R1"),
])
def test_explicit_error_location_takes_precedence_over_references(path, unit_id, message, group, identity):
    candidate = {"responsibilities": [{"responsibility_id": "R1"}, {"responsibility_id": "R2"}],
                 "state_objects": [{"state_id": "S1", "owner_responsibility_id": "R1"}]}
    scope = ledger_scope(candidate, [ArtifactIssue(path, "bad", message, unit_id=unit_id)])
    key = "responsibility_id" if group == "responsibilities" else "state_id"
    assert scope == {"entities": {group: {"identity": key, "ids": [identity]}}}


def test_resume_revalidates_bad_scope_and_drops_stale_rejection(tmp_path, monkeypatch):
    task, inputs, registry, good = make_draft(tmp_path)
    bad = deepcopy(good)
    for ru in bad["responsibilities"]:
        ru.pop("state_accesses")
    repair = {"state_objects": good["state_objects"], "responsibilities": good["responsibilities"]}
    root = tmp_path / "case"
    # Reproduce the old harness: it rejected the correct owning-RU response.
    def wrong_scope(candidate, issues):
        if not candidate:
            return {"full": True}
        return {"entities": {"state_objects": {"identity": "state_id", "ids": [s["state_id"] for s in candidate["state_objects"]]}}}
    with monkeypatch.context() as old:
        old.setattr("zerorepo.rtl_impl.module_planner.utils.planning_session.ledger_scope", wrong_scope)
        backend, run = extract(root, task, inputs, [bad, repair, repair])
        with pytest.raises(StageGenerationError, match="Untargeted ledger section: responsibilities"):
            run()
        assert len(backend.calls) == 3
    checkpoint = next((root / "plan/state/execution").glob("*.json"))
    saved = json.loads(checkpoint.read_text())
    assert saved["candidate"] == bad
    assert saved["feedback"][0]["message"] == "Untargeted ledger section: responsibilities"
    backend, resume = extract(root, task, inputs, [repair], resume=True)
    result = resume()
    assert len(backend.calls) == 1
    prompt = backend.calls[0]["user_prompt"]
    assert "Untargeted ledger section: responsibilities" not in prompt
    feedback = json.loads(prompt.split("\nVALIDATION RESULT:\n")[1].split("\nReturn only")[0])
    assert set(feedback["repair_scope"]["entities"]) == {"responsibilities"}
    assert all(issue["stage"] == "stage2_repo_skeleton" for issue in feedback["issues"])
    assert not ledger_errors(result, inputs)
    assert result == registry.resolve(ResponsibilityLedgerDraft.model_validate(good))
    saved = json.loads(checkpoint.read_text())
    assert saved["status"] == "completed" and saved["api_attempts"] == 4
    assert saved["candidate"]["state_objects"] == bad["state_objects"]


def test_owner_repair_timeout_resumes_without_regenerating_ledger(tmp_path):
    task, inputs, _, good = make_draft(tmp_path)
    bad = deepcopy(good)
    bad["responsibilities"][0].pop("state_accesses")
    root = tmp_path / "case"
    _, run = extract(root, task, inputs, [bad, LLMRequestTimeoutError("repair interrupted")])
    with pytest.raises(LLMRequestTimeoutError):
        run()
    backend, resume = extract(root, task, inputs, [{"responsibilities": [good["responsibilities"][0]]}], resume=True)
    result = resume()
    assert len(backend.calls) == 1 and not ledger_errors(result, inputs)
    assert "required_access" in backend.calls[0]["user_prompt"]


def test_source_repair_projects_embedded_context_and_keeps_checkpoint_identity(tmp_path):
    task, inputs, registry, good = make_draft(tmp_path)
    bad = deepcopy(good)
    for ru in bad["responsibilities"]:
        ru.pop("source_evidence_ids")
    bad["state_objects"][0]["source_evidence_ids"] = ["EV_UNKNOWN"]
    root = tmp_path / "case"
    backend = RaisingBackend([bad, LLMRequestTimeoutError("repair interrupted")])
    client = PlannerLLMClient(backend=backend)
    client.configure_execution(root)
    client.executor.begin_run(task, resume=False)
    agent = Stage2Agent(client)
    context = agent._build_stage2_prompt_context(inputs)
    # Large derived prose models IFU's Stage1 ledger, independently of the
    # mandatory originals in the evidence catalog.
    context["responsibility_facts"] = [{"fact_id": "F_LARGE", "description": "derived prose " * 9000}]
    locked = LockedTopModule(module="aes_cipher_top", resolution_mode="deterministic")
    def invoke():
        return agent._extract_responsibilities(task=task, partial_artifacts={"stage2_input": inputs},
            prompt_context=context, locked_top=locked)
    with pytest.raises(LLMRequestTimeoutError):
        invoke()
    checkpoint = next((root / "plan/state/execution").glob("*.json"))
    saved = json.loads(checkpoint.read_text())
    assert saved["candidate"] == bad
    initial, repair = (call["user_prompt"] for call in backend.calls)
    assert "derived prose " * 9000 not in initial
    assert '"fact_ids":["F_LARGE"]' in initial
    assert "Return exactly one JSON object with:" not in initial
    assert "derived prose " * 9000 not in repair
    assert '"fact_ids":["F_LARGE"]' in repair
    assert "canonical_fact_fingerprint" in repair
    for identity, ref in registry.entries.items():
        assert identity in repair
        assert json.dumps(ref.quote, ensure_ascii=False) in repair
    feedback = json.loads(repair.split("\nVALIDATION RESULT:\n")[1].split("\nReturn only")[0])
    assert feedback["candidate"] == bad
    assert all(i["expected"] == {"allowed_evidence_ids_from": "evidence_catalog.entries[].id"}
               for i in feedback["issues"])
    assert len(initial) < 20000 and len(repair) < 25000
    # Resume uses exactly the original node: only requested entities are sent
    # back and the valid state table is kept, not regenerated as a full ledger.
    backend.responses = [{"responsibilities": good["responsibilities"],
                          "state_objects": [good["state_objects"][0]]}]
    client.executor.begin_run(task, resume=True)
    result = invoke()
    assert not ledger_errors(result, inputs)
    complete = json.loads(checkpoint.read_text())
    assert complete["input_fingerprint"] == saved["input_fingerprint"]
    assert complete["status"] == "completed" and complete["api_attempts"] == 3
    assert sum(complete["prompt_budget"]["components"].values()) == complete["prompt_budget"]["input_chars"]
    assert len(list((root / "plan/state/execution").glob("*.json"))) == 1
    # Changes to omitted derived prose still invalidate the full input identity.
    context["responsibility_facts"][0]["description"] += " changed"
    backend.responses = [good]
    client.executor.begin_run(task, resume=True)
    invoke()
    assert len(list((root / "plan/state/execution").glob("*.json"))) == 2


def test_duplicate_evidence_error_identifies_only_repeated_ids(tmp_path):
    _, _, registry, good = make_draft(tmp_path)
    identity = good["responsibilities"][0]["source_evidence_ids"][0]
    with pytest.raises(ValueError, match="repeated IDs") as error:
        registry.expand([identity, identity])
    assert str(error.value).count(identity) == 1


def test_native_fact_scope_does_not_create_a_required_module(tmp_path):
    from test_rtl_module_planner import make_stage1_contract_artifact
    from zerorepo.rtl_impl.module_planner.module_organizer import build_stage2_planning_input
    from zerorepo.rtl_impl.module_planner.schemas import ExtractedFact
    task, _, _, _ = make_draft(tmp_path)
    stage1 = make_stage1_contract_artifact(Path(task.spec_md_files[0]), [])
    stage1.structure_contract.modules.append("filename_system")
    stage1.fact_ledger.facts.append(ExtractedFact(fact_id="CONCEPT", module="filename_system",
        category="module_identity", subject="fetching target", predicate="is_address_region",
        object={"definition": "an address region from which instructions may be read"}))
    inputs = build_stage2_planning_input(stage1_artifact=stage1, task_input=task)
    agent = Stage2Agent(PlannerLLMClient(backend=RaisingBackend([])))
    required = agent._explicit_module_names(inputs, "aes_cipher_top")
    assert required == {"aes_cipher_top", "aes_key_expand_128"}
    # A real declaration must still become a hard requirement, including when
    # the declared child is present only as a subject/name in a native fact.
    inputs.fact_ledger.facts.append(ExtractedFact(fact_id="CHILD", module="aes_cipher_top",
        category="module_identity", subject="explicit_child", predicate="defines_module",
        object={"name": "explicit_child"}))
    assert "explicit_child" in agent._explicit_module_names(inputs, "aes_cipher_top")
    inputs.fact_ledger.facts = []
    assert "filename_system" in agent._explicit_module_names(inputs, "aes_cipher_top")


def test_duplicate_ledger_identity_cannot_authorize_ambiguous_entity_repair():
    bad = {"responsibilities": [{"responsibility_id": "R1"}, {"responsibility_id": "R1"}], "state_objects": []}
    assert ledger_scope(bad, [ArtifactIssue("responsibilities[R1]", "bad", "bad")]) == {"full": True}


def test_unknown_explicit_target_does_not_authorize_editing_a_referenced_state():
    bad = {"responsibilities": [{"responsibility_id": "R1"}], "state_objects": [{"state_id": "S1"}]}
    issue = ArtifactIssue("responsibilities[UNKNOWN]", "bad", "access to S1", unit_id="UNKNOWN")
    assert ledger_scope(bad, [issue]) == {"full": True}


def test_missing_commit_repair_continues_through_two_module_planning_gate(tmp_path):
    def inject(runner):
        responses = runner.llm_client.backend.responses
        good = responses[1]
        bad = deepcopy(good)
        for ru in bad["responsibilities"]:
            ru.pop("state_accesses", None)
        owners = [r for r in good["responsibilities"] if r["owned_state"]]
        responses[1:2] = [bad, {"responsibilities": owners}]
    case = scenario(tmp_path, before_run=inject)
    assert report(case)["status"] == "passed"
    _, runner, backend, inputs, _, _ = case
    assert len(inputs["stage2_decomposition"].state_objects) == 2
    assert not backend.responses
    # compact retention may remove the completed execution journal after the
    # authoritative ledger is persisted; verify the actual request sequence.
    requests = [c for c in backend.calls if "OUTPUT OVERRIDE: Return ResponsibilityLedgerDraft" in c["user_prompt"]]
    assert len(requests) == 2
    assert "missing_state_commit" in requests[1]["user_prompt"]
