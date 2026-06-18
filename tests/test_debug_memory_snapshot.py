from __future__ import annotations

import asyncio
import json
from pathlib import Path

from zerorepo.rtl_impl.debug_agent import rtl_editor
from zerorepo.rtl_impl.debug_agent.rtl_editor import _EditSession


class _FakeReviewer:
    def __init__(self, outcome: tuple[bool, int, str]) -> None:
        self.outcome = outcome
        self.calls = 0

    def review(self) -> tuple[bool, int, str]:
        self.calls += 1
        return self.outcome


class _CaptureAgent:
    def __init__(self, editor: rtl_editor.RTLEditor | None = None) -> None:
        self.editor = editor
        self.prompts: list[str] = []
        self.did_edit = False

    async def __call__(self, msg: object) -> None:
        text = msg.get_text_content()  # type: ignore[attr-defined]
        self.prompts.append(text or "")
        if (
            self.editor is not None
            and not self.did_edit
            and "Compact checkpoint" not in self.prompts[-1]
            and self.editor._session is not None
        ):
            self.editor._session.action_calls = 2
            self.did_edit = True


def _edit_session(tmp_path: Path, reviewer: _FakeReviewer) -> tuple[_EditSession, Path]:
    rtl_path = tmp_path / "rtl.sv"
    rtl_path.write_text("module m;\n  wire a;\n  child u(.a(a));\nendmodule\n", encoding="utf-8")
    return (
        _EditSession(
            tb_path=str(tmp_path / "tb.sv"),
            rtl_path=str(rtl_path),
            output_dir=str(tmp_path),
            last_mismatch_cnt=1,
            sim_reviewer=reviewer,  # type: ignore[arg-type]
            max_trials=2,
        ),
        rtl_path,
    )


def test_memory_snapshot_is_deterministic_and_persisted(tmp_path: Path) -> None:
    session, _rtl_path = _edit_session(tmp_path, _FakeReviewer((False, 1, "{}")))
    session.trace_report = {
        "fail_time": 7,
        "total_mismatches": 2,
        "first_failure": {"sig": "out", "expected": "1", "actual": "0"},
        "diagnostic_narrative": ["out is stuck low"],
        "fail_outputs": [],
    }
    session.source_of_truth = {"summary": "contract_json is authoritative"}
    session.repair_journal = [
        {
            "trial": 1,
            "action_type": "apply_patch_set",
            "target": {"start_line": 2, "end_line": 2},
            "patch_count": 1,
            "patch_summary": "assign out = a;",
            "changed_signals": ["out"],
            "effect": "improved",
            "lesson": "Patch improved the simulation result; continue from this direction.",
        }
    ]

    snapshot = session.persist_memory_snapshot()
    saved = json.loads((tmp_path / "debug_memory_snapshot.json").read_text(encoding="utf-8"))

    assert snapshot == saved
    assert snapshot["schema"] == "debug_memory_snapshot.v1"
    assert snapshot["current_rtl_hash"] == session.current_rtl_hash()
    assert snapshot["latest_trace_summary"]["top_diagnosis"] == "out is stuck low"
    assert snapshot["promising_directions"][0]["changed_signals"] == ["out"]


def test_read_rtl_context_is_index_and_read_lines_returns_local_range(tmp_path: Path) -> None:
    rtl_path = tmp_path / "rtl.sv"
    rtl_path.write_text(
        "\n".join(
            [
                "module m(input clk, output logic out);",
                "  logic a;",
                "  child u_child(.a(a));",
                "  assign out = a;",
                "endmodule",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    session = _EditSession(
        tb_path=str(tmp_path / "tb.sv"),
        rtl_path=str(rtl_path),
        output_dir=str(tmp_path),
        last_mismatch_cnt=1,
        sim_reviewer=_FakeReviewer((False, 1, "{}")),  # type: ignore[arg-type]
        max_trials=2,
    )

    context = session.read_rtl_context()

    assert "[module_header_declarations_instances]" in context
    assert "[block_index]" in context
    assert "2:   logic a;" in context
    assert "3:   child u_child(.a(a));" in context
    assert "4:   assign out = a;" not in context
    assert session.read_lines(4, 4) == "4:   assign out = a;\n"


def test_compact_agent_memory_writes_snapshot_and_prompt(tmp_path: Path) -> None:
    (tmp_path / "rtl.sv").write_text("module m(input clk, output out); assign out = clk; endmodule\n", encoding="utf-8")
    (tmp_path / "tb.sv").write_text("module tb;\nendmodule\n", encoding="utf-8")

    editor = object.__new__(rtl_editor.RTLEditor)
    editor._last_compacted_action_calls = 0
    capture = _CaptureAgent()
    editor._agent = capture
    editor._session = _EditSession(
        tb_path=str(tmp_path / "tb.sv"),
        rtl_path=str(tmp_path / "rtl.sv"),
        output_dir=str(tmp_path),
        last_mismatch_cnt=1,
        sim_reviewer=_FakeReviewer((False, 1, "{}")),  # type: ignore[arg-type]
        max_trials=3,
        behavior_source="spec_tb",
    )
    editor._session.action_calls = 2

    assert editor._needs_compact_checkpoint() is True
    asyncio.run(editor._compact_agent_memory())

    compact_prompts = [prompt for prompt in capture.prompts if "Compact checkpoint" in prompt]
    assert len(compact_prompts) == 1
    assert "debug_memory_snapshot_json" in compact_prompts[0]
    snapshot = json.loads((tmp_path / "debug_memory_snapshot.json").read_text(encoding="utf-8"))
    assert snapshot["action_calls"] == 2
    assert snapshot["current_rtl_hash"]
    assert editor._last_compacted_action_calls == 2


def test_compact_checkpoint_can_trigger_on_tool_result_volume(tmp_path: Path) -> None:
    session, _rtl_path = _edit_session(tmp_path, _FakeReviewer((False, 1, "{}")))
    editor = object.__new__(rtl_editor.RTLEditor)
    editor._session = session
    editor._last_compacted_action_calls = 0
    editor._tool_result_chars_since_compact = 12000

    assert editor._needs_compact_checkpoint() is True
