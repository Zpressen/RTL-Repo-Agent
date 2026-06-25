from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from zerorepo.rtl_impl.debug_agent.bash_tools import CommandResult

from zerorepo.rtl_impl.repo_react.journal import RepoReActJournal
from zerorepo.rtl_impl.repo_react.schemas import RepoReActInput
import zerorepo.rtl_impl.repo_react.tools as tools_module
from zerorepo.rtl_impl.repo_react.tools import RepoReActTools, RepoReActToolState, _parse_sim_metrics


def _make_tools(tmp_path: Path, *, repair_mode: str = "functional") -> RepoReActTools:
    workdir = tmp_path / "debug" / "m"
    workdir.mkdir(parents=True)
    rtl_path = workdir / "rtl.sv"
    rtl_path.write_text("module m(input clk, output y);\nassign y = clk;\nendmodule\n", encoding="utf-8")
    inp = RepoReActInput(
        module_name="m",
        repair_mode=repair_mode,  # type: ignore[arg-type]
        workspace_root=tmp_path,
        debug_workdir=workdir,
        rtl_path=rtl_path,
        merged_file=tmp_path / "merged" / "m.v",
        sim_failed_log="",
        initial_mismatch_count=1,
    )
    state = RepoReActToolState(
        input=inp,
        sim_reviewer=SimpleNamespace(),
        journal=RepoReActJournal(tmp_path / "repo_react" / "m"),
    )
    state.observed_rtl = True
    state.observed_trace_or_sim = True
    state.observed_tb_or_spec_or_kg = True
    state.observed_spec_or_stage = True
    return RepoReActTools(state)


def test_functional_apply_patch_requires_real_divergence(tmp_path: Path) -> None:
    tools = _make_tools(tmp_path, repair_mode="functional")

    result = tools.apply_patch(
        patches=[{"path": "rtl.sv", "start_line": 2, "end_line": 2, "new_text": "assign y = ~clk;"}],
        reason="try change",
        expected_effect="change output",
    )

    assert result["status"] == "rejected"
    assert "first_divergence" in result["reason"]


def test_syntax_apply_patch_does_not_require_real_divergence(tmp_path: Path) -> None:
    tools = _make_tools(tmp_path, repair_mode="syntax")

    result = tools.apply_patch(
        patches=[{"path": "rtl.sv", "start_line": 2, "end_line": 2, "new_text": "assign y = clk;"}],
        reason="syntax-only rewrite",
        expected_effect="lint remains clean",
        verify=False,
    )

    assert result["status"] == "kept_unverified"


def test_apply_patch_allows_more_than_two_ranges(tmp_path: Path) -> None:
    tools = _make_tools(tmp_path, repair_mode="syntax")

    result = tools.apply_patch(
        patches=[
            {"path": "rtl.sv", "start_line": 1, "end_line": 1, "new_text": "module m(input clk, output y);"},
            {"path": "rtl.sv", "start_line": 2, "end_line": 2, "new_text": "assign y = ~clk;"},
            {"path": "rtl.sv", "start_line": 3, "end_line": 3, "new_text": "endmodule"},
        ],
        reason="multi-range syntax rewrite",
        expected_effect="all ranges apply",
        verify=False,
    )

    assert result["status"] == "kept_unverified"
    assert "assign y = ~clk;" in tools.state.input.rtl_path.read_text(encoding="utf-8")


def test_functional_apply_patch_requires_spec_or_stage_context(tmp_path: Path) -> None:
    tools = _make_tools(tmp_path, repair_mode="functional")
    tools.state.observed_real_divergence = True
    tools.state.observed_spec_or_stage = False

    result = tools.apply_patch(
        patches=[{"path": "rtl.sv", "start_line": 2, "end_line": 2, "new_text": "assign y = ~clk;"}],
        reason="try waveform-only change",
        expected_effect="change output",
    )

    assert result["status"] == "rejected"
    assert "spec or stage" in result["reason"]


def test_apply_patch_enforces_action_budget(tmp_path: Path) -> None:
    tools = _make_tools(tmp_path, repair_mode="syntax")
    tools.state.input.max_steps = 1
    tools.state.action_calls = 1

    result = tools.apply_patch(
        patches=[{"path": "rtl.sv", "start_line": 2, "end_line": 2, "new_text": "assign y = ~clk;"}],
        reason="over budget",
        expected_effect="should be blocked",
        verify=False,
    )

    assert result["status"] == "rejected"
    assert "max_steps=1" in result["reason"]


def test_parse_sim_metrics_extracts_total_and_per_signal() -> None:
    sim_log = CommandResult(
        cmd=["sim"],
        returncode=1,
        stdout=(
            "Hint: Output 'STATUS_REG' has 471 mismatches. First mismatch occurred at time 485.\n"
            "Hint: Output 'cmd_out' has 644 mismatches. First mismatch occurred at time 1155.\n"
            "Mismatches: 2473 in 5213 samples\n"
        ),
        stderr="",
    ).model_dump_json()

    metrics = _parse_sim_metrics(sim_log)

    assert metrics["total_samples_mismatch"] == 2473
    assert metrics["samples"] == 5213
    assert metrics["per_signal"]["STATUS_REG"] == {"count": 471, "first_time": 485}
    assert metrics["per_signal"]["cmd_out"] == {"count": 644, "first_time": 1155}


def test_causal_memory_filters_budget_rejections_and_builds_invariants(tmp_path: Path) -> None:
    tools = _make_tools(tmp_path, repair_mode="functional")
    tools.state.last_divergence_summary = {
        "status": "ok",
        "sampling_mode": "stable",
        "first_divergence": {"signal": "cmd_out", "time": 1155, "ref": "1", "dut": "0", "sampling_mode": "stable"},
        "suspect": {"driver_blocks": [{"id": "A7"}], "signals": ["cmd_out"]},
    }
    tools.state.journal.append_jsonl(
        "patch_journal.jsonl",
        {
            "step": 8,
            "action_type": "apply_patch",
            "target": {"path": "rtl.sv", "start_line": 223, "end_line": 223},
            "changed_signals": ["ack_out"],
            "effect": "improved",
            "hypothesis": "SETUP should not clear ack_out; hold ack_out through SETUP.",
            "lesson": "Patch improved mismatch count or first fail time; continue from this direction.",
            "patch_summary": "",
            "before": {"mismatch_count": 5393, "first_fail_time": 5},
            "after": {"mismatch_count": 5250, "first_fail_time": 5},
            "result": {"status": "improved"},
        },
    )
    tools.state.journal.append_jsonl(
        "patch_journal.jsonl",
        {
            "step": 10,
            "action_type": "replace_block",
            "block_id": "A7",
            "target": {"path": "rtl.sv", "start_line": 176, "end_line": 287, "block_id": "A7"},
            "changed_signals": ["STATUS_REG", "RESP_1_REG", "ERR_INT_REG", "NORMAL_INT_REG", "cmd_out", "settings", "req_out", "ack_out"],
            "effect": "regressed",
            "hypothesis": "broad blocking conversion",
            "lesson": "Patch worsened mismatch count or first fail time and was rolled back.",
            "patch_summary": "always @(posedge clk) begin ... end",
            "before": {"mismatch_count": 4723, "first_fail_time": 5},
            "after": {"mismatch_count": 9344, "first_fail_time": 1155},
            "result": {"status": "rollback", "rollback_reason": "mismatch_count_regressed"},
        },
    )
    tools.state.journal.append_jsonl(
        "patch_journal.jsonl",
        {
            "step": 11,
            "action_type": "apply_patch",
            "target": {},
            "changed_signals": [],
            "effect": "rejected",
            "hypothesis": "over budget",
            "lesson": "Repair action budget exhausted: max_steps=10.",
            "patch_summary": "Repair action budget exhausted: max_steps=10.",
            "result": {"status": "rejected", "reason": "Repair action budget exhausted: max_steps=10."},
        },
    )

    brief = tools.read_memory(kind="brief")["brief"]
    unsafe = tools.read_memory(kind="unsafe_directions")["unsafe_directions"]
    protected = tools.read_memory(kind="protected_invariants")["protected_invariants"]
    failed = tools.read_memory(kind="failed_directions")["directions"]

    assert "nearby" not in str(brief)
    assert any("ack_out" in item and "SETUP" in item for item in protected)
    assert any("Broad replace_block of A7" in item for item in unsafe)
    assert brief["next_local_target"]["signal"] == "cmd_out"
    assert all("budget exhausted" not in str(item).lower() for item in failed)


def test_protected_invariant_gate_requires_preserve_plan(tmp_path: Path) -> None:
    tools = _make_tools(tmp_path, repair_mode="functional")
    tools.state.observed_real_divergence = True
    tools.state.journal.append_jsonl(
        "patch_journal.jsonl",
        {
            "step": 1,
            "action_type": "apply_patch",
            "target": {"path": "rtl.sv", "start_line": 2, "end_line": 2},
            "changed_signals": ["ack_out"],
            "effect": "improved",
            "hypothesis": "SETUP should hold ack_out; do not clear ack_out in SETUP.",
            "lesson": "Patch improved mismatch count or first fail time; continue from this direction.",
            "patch_summary": "ack_out hold through SETUP",
            "before": {"mismatch_count": 10, "first_fail_time": 5},
            "after": {"mismatch_count": 8, "first_fail_time": 5},
            "result": {"status": "improved"},
        },
    )

    blocked = tools.apply_patch(
        patches=[{"path": "rtl.sv", "start_line": 2, "end_line": 2, "new_text": "assign ack_out = clk;"}],
        reason="touch protected ack_out",
        expected_effect="test gate",
        verify=False,
    )
    allowed = tools.apply_patch(
        patches=[{"path": "rtl.sv", "start_line": 2, "end_line": 2, "new_text": "assign ack_out = clk;"}],
        reason="touch protected ack_out",
        expected_effect="test gate",
        protected_invariants_checked=["Do not clear ack_out in SETUP"],
        preserve_plan="This edit is outside SETUP and preserves ack_out hold-through behavior.",
        verify=False,
    )

    assert blocked["status"] == "rejected"
    assert "protected_invariants_checked" in blocked["reason"]
    assert allowed["status"] == "kept_unverified"


def test_replace_block_requires_real_divergence_in_functional_mode(tmp_path: Path) -> None:
    tools = _make_tools(tmp_path, repair_mode="functional")

    result = tools.replace_block(
        block_id="C1",
        new_code="assign y = ~clk;",
        reason="try full assign replacement",
        expected_effect="change output",
        verify=False,
    )

    assert result["status"] == "rejected"
    assert "first_divergence" in result["reason"]


def test_replace_block_replaces_complete_assign_block_when_verified_false(tmp_path: Path) -> None:
    tools = _make_tools(tmp_path, repair_mode="functional")
    tools.state.observed_real_divergence = True

    result = tools.replace_block(
        block_id="C1",
        new_code="assign y = ~clk;",
        reason="replace continuous assignment",
        expected_effect="invert output",
        verify=False,
    )

    rtl = tools.state.input.rtl_path.read_text(encoding="utf-8")
    assert result["status"] == "kept_unverified"
    assert "assign y = ~clk;" in rtl
    rows = tools._read_jsonl("patch_journal.jsonl")
    assert rows[-1]["action_type"] == "replace_block"
    assert rows[-1]["block_id"] == "C1"
    assert tools.memory_snapshot()["recent_replaced_blocks"][-1]["block_id"] == "C1"


def test_replace_block_lint_fail_rolls_back(tmp_path: Path, monkeypatch: object) -> None:
    tools = _make_tools(tmp_path, repair_mode="syntax")
    before = tools.state.input.rtl_path.read_text(encoding="utf-8")

    def fake_check_syntax(_path: str, top_module: str | None = None) -> tuple[bool, str]:
        del top_module
        return False, "lint failed"

    monkeypatch.setattr(tools_module, "check_syntax", fake_check_syntax)
    result = tools.replace_block(
        block_id="C1",
        new_code="assign y = ;",
        reason="broken replace",
        expected_effect="lint should catch it",
    )

    assert result["status"] == "rollback"
    assert result["rollback_reason"] == "lint_failed"
    assert tools.state.input.rtl_path.read_text(encoding="utf-8") == before
