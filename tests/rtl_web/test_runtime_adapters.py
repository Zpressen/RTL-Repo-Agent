"""Adapter contract tests; no model, KG or real compiler is invoked."""

import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
import pytest
from zerorepo.rtl_web import runtime
from zerorepo.rtl_web.artifacts import Artifacts, tree_manifest, sha
from zerorepo.rtl_web.schemas import DemoError


def test_final_verdict_never_uses_exit_or_merge_success():
    assert runtime.final_verdict("{}", True) == "unverified"
    report = json.dumps(
        {
            "stdout": "Hint: Total mismatched samples is 1 out of 222 samples\nsystem_verify: FAIL"
        }
    )
    assert runtime.final_verdict(report, True) == "fail"
    report = json.dumps(
        {
            "stdout": "Hint: Total mismatched samples is 0 out of 222 samples\nsystem_verify: PASS"
        }
    )
    assert runtime.final_verdict(report, False) == "unverified"


def test_verify_uses_copy_and_selected_external_oracle(
    settings, ledger, tmp_path, monkeypatch
):
    source = tmp_path / "rtl"
    source.mkdir()
    (source / "unit.v").write_text("module unit; endmodule\n")
    art = Artifacts(settings.data, ledger)
    v = art.snapshot(source, "before", "history")
    settings.oracle = tmp_path / "oracle"
    verify = settings.verify_script
    verify.parent.mkdir(parents=True)
    verify.write_text("# trusted\n")
    (verify.parent / "e203_exu_alu_testbench.sv").write_text("// oracle\n")
    reference = settings.oracle / "e203_hbirdv2/e203_exu_alu/verification"
    reference.mkdir(parents=True)
    (reference / "ref.v").write_text("module ref;endmodule")
    spec_before = sha(settings.spec)
    oracle_before = runtime.verifier_manifest(settings)
    observed = []

    class Reviewer:
        def __init__(self, **kw):
            self.kw = kw
            observed.append(kw)

        def review(self):
            self.kw["output_dir"].mkdir(parents=True)
            assert self.kw["generated_dir"] != source
            assert self.kw["verify_script"] == verify
            return (
                True,
                0,
                json.dumps(
                    {
                        "stdout": "Hint: Total mismatched samples is 0 out of 222 samples\nsystem_verify: PASS"
                    }
                ),
            )

    fake = ModuleType("zerorepo.rtl_impl.debug_agent.system_debug_runner")
    fake.SystemSimReviewer = Reviewer
    monkeypatch.setitem(sys.modules, fake.__name__, fake)
    monkeypatch.setattr(
        runtime,
        "configure_agent",
        lambda *args: pytest.fail("verify must not enter planner or repair"),
    )
    session = ledger.create_session("x", {})
    op, _ = ledger.accept_operation(
        session["session_id"],
        "verify",
        {"kind": "verify", "context_ref": {"version_id": v["version_id"]}},
    )
    result = runtime.execute(settings, op)
    assert result["verdict"] == "pass"
    assert result["run_id"] == op["run_id"]
    assert tree_manifest(source)[0] == v["tree_sha256"]
    assert (
        sha(settings.spec) == spec_before
        and runtime.verifier_manifest(settings) == oracle_before
    )
    assert Path(result["rtl_dir"]).is_relative_to(settings.data / "runs" / op["run_id"])


def test_stage_sink_uses_real_artifacts(tmp_path):
    sink = runtime.EventSink(tmp_path)
    sink.record_stage_output(
        "stage2",
        SimpleNamespace(
            model_dump=lambda: {"modules": [{"module": "a"}, {"module": "b"}]}
        ),
        None,
    )
    row = json.loads(sink.path.read_text())
    assert row["stage"] == "architecture" and row["modules"] == [
        {"module_id": "a", "status": "planned"},
        {"module_id": "b", "status": "planned"},
    ]


def test_task_spec_preserves_content_and_resolves_registered_oracle(
    settings, tmp_path, monkeypatch
):
    settings = settings.for_case("aes_inv_cipher_top_system")
    settings.oracle = tmp_path / "oracle"
    monkeypatch.setattr(runtime, "load_agent", lambda s: ({}, None))
    for module, attrs in {
        "zerorepo.rtl_impl.debug_agent.adapters": {
            "debug_openai_config_from_planner_config": lambda llm: None
        },
        "zerorepo.rtl_impl.debug_agent.debug_runner": {
            "RtlDebugConfig": SimpleNamespace(from_mapping=lambda *args, **kw: None)
        },
        "zerorepo.rtl_impl.module_planner": {
            "PlannerTaskInput": lambda **kw: SimpleNamespace(**kw)
        },
    }.items():
        fake = ModuleType(module)
        fake.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, module, fake)
    *_, task, kg = runtime.configure_agent(
        settings, tmp_path / "run", tmp_path / "merged"
    )
    spec = Path(task.spec_md_files[0])
    assert spec.read_bytes() == settings.spec.read_bytes()
    assert spec.parent.name == settings.case["project_hint"]
    assert spec.is_relative_to(tmp_path / "run") and kg is None


@pytest.mark.parametrize("kind", ["generate_and_verify", "fix"])
def test_generation_and_fix_delegate_existing_runners(
    settings, ledger, bundle, tmp_path, monkeypatch, kind
):
    # These are adapter tests, not successful RTL generation evidence.
    fake = ModuleType("zerorepo.rtl_impl.module_planner")
    calls = []

    class Planner:
        def __init__(self, **kw):
            calls.append(("planner", kw))
            self.kw = kw

        def run(self, task, **kwargs):
            calls.append(("generate", kwargs))
            merged = self.kw["checkpoint_dir"] / "workspace/merged"
            (merged / "unit.v").write_text("module unit;endmodule")
            return SimpleNamespace(status="completed")

    fake.PlannerRunner = Planner
    monkeypatch.setitem(sys.modules, fake.__name__, fake)
    fake = ModuleType("zerorepo.rtl_impl.debug_agent.system_debug_runner")

    class Debugger:
        def __init__(self, **kw):
            calls.append(("debugger", kw))

        def run_system(self, **kw):
            calls.append(("fix", kw))
            return SimpleNamespace(status="fixed")

    fake.SystemDebugRunner = Debugger
    monkeypatch.setitem(sys.modules, fake.__name__, fake)
    fake = ModuleType("zerorepo.rtl_impl.debug_agent.adapters")
    fake.build_debug_contract_json = lambda **kw: json.dumps(kw)
    monkeypatch.setitem(sys.modules, fake.__name__, fake)
    monkeypatch.setattr(
        runtime,
        "configure_agent",
        lambda *args: (
            {"rtl_module_planner": {}},
            None,
            SimpleNamespace(backend="codex"),
            SimpleNamespace(task_id="e203"),
            None,
        ),
    )
    monkeypatch.setattr(
        runtime, "verifier_manifest", lambda s: [{"path": "trusted", "sha256": "fixed"}]
    )

    def verify(s, rtl, out):
        calls.append(("final_verify", rtl))
        return {"verdict": "fail", "rtl_dir": str(rtl)}

    monkeypatch.setattr(runtime, "verify_only", verify)
    sid = ledger.create_session("adapter-" + kind, {})["session_id"]
    v = bundle["versions"][0]
    op, _ = ledger.accept_operation(
        sid,
        kind,
        {
            "kind": kind,
            "context_ref": {"version_id": v["version_id"], "run_id": v["run_id"]},
        },
    )
    result = runtime.execute(settings, op)
    assert result["verdict"] == "fail" and calls[-1][0] == "final_verify"
    assert (
        calls[0][1]["checkpoint_dir"]
        == settings.data / "runs" / op["run_id"] / ".zerorepo"
        if kind == "generate_and_verify"
        else calls[0][1]["workspace_root"]
        == settings.data / "runs" / op["run_id"] / ".zerorepo/workspace"
    )
    if kind == "fix":
        assert json.loads(calls[1][1]["contract_json"])["stage1_contracts"][
            "interface_contracts"
        ]
