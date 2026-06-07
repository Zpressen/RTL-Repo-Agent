from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Literal, Tuple

from agentscope.memory import InMemoryMemory
from agentscope.message import Msg
from agentscope.tool import ToolResponse, Toolkit

from .agents import SafeReActAgent, clear_memory_safely
from .config import OpenAIConfig
from .kg_debug_reads import kg_debug_session_id
from .model import make_formatter, make_openai_model
from .sim_reviewer import SimReviewer, check_syntax
from .trace_report import (
    build_trace_report,
    compare_vcd_pairs,
    list_vcd_signals_query,
    resolve_vcd_signal,
    sample_vcd_signals,
    _find_clock_signal,
    _resolve_ref_instance as _resolve_ref_instance_static,
    _vcd_time_range,
)
from .trace_slicer import RtlBlock

try:
    from vcdvcd import VCDVCD  # type: ignore[import-not-found]
except Exception:  # noqa: BLE001
    VCDVCD = None  # type: ignore[assignment]

_FAIL_TIME_HINT_RE = re.compile(
    r"Hint:\s+Output\s+'[^']+'\s+has\s+(?P<cnt>\d+)\s+mismatches\.\s+First mismatch occurred at time\s+(?P<t>\d+)\.",
    re.MULTILINE,
)
_FAIL_TIME_FAILED_RE = re.compile(
    r"SIMULATION FAILED - \d+\s+MISMATCHES DETECTED.*FIRST AT TIME\s+(?P<t>\d+)",
    re.IGNORECASE,
)


def _extract_fail_time_from_sim_log_json(sim_log_json: str) -> int | None:
    """Best-effort earliest mismatch time from a CommandResult JSON string."""
    try:
        obj = json.loads(sim_log_json)
    except Exception:  # noqa: BLE001
        return None
    stdout = str(obj.get("stdout") or "")
    times: list[int] = []
    for m in _FAIL_TIME_HINT_RE.finditer(stdout):
        try:
            if int(m.group("cnt")) > 0:
                times.append(int(m.group("t")))
        except Exception:  # noqa: BLE001
            continue
    if times:
        return min(times)
    m2 = _FAIL_TIME_FAILED_RE.search(stdout)
    if m2:
        try:
            return int(m2.group("t"))
        except Exception:  # noqa: BLE001
            return None
    return None


def _clip_text(s: str, *, max_chars: int) -> str:
    if not isinstance(s, str):
        s = str(s)
    if max_chars <= 0 or len(s) <= max_chars:
        return s
    half = max_chars // 2
    return s[:half] + "\n...<snip>...\n" + s[-half:]


def _filter_verilator_stderr(stderr: str, *, dut_filename: str = "rtl.sv") -> str:
    """Keep only Verilator stderr lines that reference the DUT source file.

    Warnings from testbench / support files (which the agent cannot modify)
    are pure noise and are dropped.  DECLFILENAME is always noise for debug.
    """
    if not stderr.strip():
        return ""
    lines: list[str] = []
    for line in stderr.splitlines():
        stripped = line.strip()
        # Always keep %Error (actual compile failures)
        if stripped.startswith("%Error"):
            lines.append(line)
            continue
        # DECLFILENAME is always irrelevant (agent cannot rename files)
        if "DECLFILENAME" in stripped:
            continue
        # EOFNEWLINE is always irrelevant
        if "EOFNEWLINE" in stripped:
            continue
        # For other %Warning, only keep if it references the DUT file
        if "%Warning" in stripped:
            if dut_filename in stripped:
                lines.append(line)
            continue
        # Keep non-warning/error lines
        lines.append(line)
    return "\n".join(lines)


def _summarize_sim_log_json(sim_log_json: str, *, max_chars: int = 4000) -> str:
    """Return a compact excerpt from a CommandResult JSON string."""
    stdout = ""
    stderr = ""
    try:
        obj = json.loads(sim_log_json)
        stdout = str(obj.get("stdout") or "")
        stderr = str(obj.get("stderr") or "")
    except Exception:  # noqa: BLE001
        return _clip_text(sim_log_json, max_chars=max_chars)

    # Keep the most informative bits: mismatch banner + hints + summary.
    interesting: list[str] = []
    for line in stdout.splitlines():
        if (
            "=== MISMATCH DETECTED" in line
            or "Hint:" in line
            or line.startswith("Mismatches:")
            or "SIMULATION FAILED" in line
            or "SIMULATION PASSED" in line
            or line.strip() == "TIMEOUT"
        ):
            interesting.append(line)
    out = "\n".join(interesting).strip()
    if not out:
        out = _clip_text(stdout, max_chars=max_chars)

    stderr_filtered = _filter_verilator_stderr(stderr)
    if stderr_filtered.strip():
        out = out + "\n\n[stderr excerpt]\n" + _clip_text(stderr_filtered, max_chars=max(800, max_chars // 3))
    return _clip_text(out, max_chars=max_chars)


def _parse_patch_line_number(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value.strip()
        if re.fullmatch(r"[0-9]+", text):
            return int(text)
    return None


SYSTEM_PROMPT = r"""
You are Debugger, an expert in RTL debugging.

Goal: use the supplied authoritative repair context and tool calls to minimally edit and
re-simulate SystemVerilog RTL until it passes the fixed verification testbench.

Toolchain note:
- Simulation is run with Verilator; errors/warnings in logs may follow Verilator formatting.

Rules:
1. Do not modify the testbench. Only modify the RTL code.
2. Do not try to change or define RefModule. There is RefModule defined elsewhere if needed.
3. Always respect the simulation result. Keep debugging as long as mismatches exist.
4. Prefer small, targeted edits.
5. Preserve the top-level interface and externally observable behavior required by the
   authoritative context for this session.
6. Diagnostic helper output is advisory; do not let it override the authoritative context or trace.

When you are done (simulation passes), finish by calling:
  generate_response(response="...brief summary...")
The `response` argument MUST be a plain string (not JSON, not a dict, not a list).
"""


CONTRACT_INIT_EDITION_PROMPT = r"""
The information below is given to help your work:
1. The Architect contract (JSON) that both TB and RTL MUST follow (SOURCE OF TRUTH);
2. The generated testbench (fixed; you must not modify it);
3. The simulation failure log excerpt (ground truth about mismatches; full log is saved on disk).
4. The input_spec is included only as background; it must NOT override the Architect contract.
<input_spec>
{input_spec}
</input_spec>
<contract_json>
{contract_json}
</contract_json>
<generated_tb>
{generated_tb}
</generated_tb>
<sim_failed_log_excerpt>
{sim_failed_log_excerpt}
</sim_failed_log_excerpt>
{kmap_hint}
"""

SPEC_TB_INIT_EDITION_PROMPT = r"""
The information below is given to help your work:
1. The original module specification is the design source of truth.
2. The visible testbench is fixed; do not modify it. Use it to understand externally visible
   driving and checking behavior.
3. The simulation failure log excerpt and trace report are ground truth for observed failures.

<original_module_spec>
{input_spec}
</original_module_spec>
<visible_testbench>
{generated_tb}
</visible_testbench>
<sim_failed_log_excerpt>
{sim_failed_log_excerpt}
</sim_failed_log_excerpt>
{kmap_hint}
"""

KMAP_DEBUG_HINT_PROMPT = r"""
[K-map hint (only if the problem involves Karnaugh maps / K-maps)]:
- Use mismatch inputs from the sim log/trace to identify wrong minterms.
- Fix one mismatch class at a time while preserving all other truth-table entries.
"""

CONTRACT_EXTRA_ORDER_PROMPT = r"""
Workflow (repeat until pass):
1) Use the contract + trace report to find the most likely root cause.
2) Check `trace_summary.top_diagnosis` and `trace_summary.value_backtrace_summary` first.
   - If value_backtrace explains the failure, keep edits within the suspect scope it identifies.
   - Do not modify the testbench or unrelated upstream datapath when the VCD-backed chain already identifies a direct gate/reset/edge/select issue.
3) Then check `trace_summary.alignment_diagnosis`:
   - If it suggests a 1-cycle shift or wrong sampling edge, fix timing/reset/edge issues before changing core logic.
   - Otherwise focus on combinational correctness in the suspect block(s).
4) Call read_block(block_id) for the most relevant suspect block from trace_summary.first_failure or value_backtrace_summary.
5) Make one small change via replace_block(block_id, new_code).
   - If the root cause is a declaration, port type, or instance connection, call read_rtl_context()
     and use apply_patch_set(patches) with up to 10 line-range replacements.
6) Immediately call run_simulation() and iterate based on the new trace summary.

Rules:
- Do not modify the testbench. Only modify the RTL code.
- Preserve the contract's timing assumptions and top-level interface; you may correct an RTL
  port declaration only when it does not change the contract-defined name, direction, or width.
- Keep RTL synthesizable and Verilator-compatible (avoid fancy SVA, no delays).
- Do not bundle independent semantic fixes. One simulation trial should test one repair hypothesis only.
- apply_patch_set(patches) accepts up to 10 line-range patches; split larger sets into separate trials.

You will also receive a structured trace-grounded bug report (JSON) that includes:
1) earliest mismatch time, 2) (expected vs actual) values when available, 3) a short input window,
4) a VCD-backed value backtrace, 5) dynamically sliced suspect blocks.

Use tools:
- read_block(block_id)
- replace_block(block_id, new_code)
- read_rtl_context()
- apply_patch_set(patches)
- run_simulation()

When simulation passes, end with:
  generate_response(response="...brief summary...")
"""

SPEC_TB_EXTRA_ORDER_PROMPT = r"""
Workflow (repeat until pass):
1) Use the original module specification, visible testbench, and trace report to identify the
   most likely root cause.
2) Check `trace_summary.top_diagnosis` and `trace_summary.value_backtrace_summary` first.
   - If value_backtrace explains the failure, keep edits within the suspect scope it identifies.
   - Do not modify the testbench or unrelated upstream datapath when the VCD-backed chain already identifies a direct gate/reset/edge/select issue.
3) Then check `trace_summary.alignment_diagnosis`:
   - If it suggests a 1-cycle shift or wrong sampling edge, examine reset/load/output protocol
     behavior before changing datapath logic.
   - Otherwise focus on combinational correctness in the suspect block(s).
4) Call read_block(block_id) for the most relevant suspect block from trace_summary.first_failure or value_backtrace_summary.
5) Make one small change via replace_block(block_id, new_code).
   - If the root cause is a declaration, port type, or instance connection, call read_rtl_context()
     and use apply_patch_set(patches) with up to 10 line-range replacements.
6) Immediately call run_simulation() and iterate based on the new trace summary.

Rules:
- Do not modify the testbench. Only modify the RTL code.
- Preserve the top-level interface defined by the original module specification and exercised
  by the visible testbench.
- Keep RTL synthesizable and Verilator-compatible (avoid fancy SVA, no delays).
- Do not bundle independent semantic fixes. One simulation trial should test one repair hypothesis only.
- apply_patch_set(patches) accepts up to 10 line-range patches; split larger sets into separate trials.

You will also receive a structured trace-grounded bug report (JSON) that includes:
1) earliest mismatch time, 2) (expected vs actual) values when available, 3) a short input window,
4) a VCD-backed value backtrace, 5) dynamically sliced suspect blocks.

Use tools:
- read_block(block_id)
- replace_block(block_id, new_code)
- read_rtl_context()
- apply_patch_set(patches)
- run_simulation()

When simulation passes, end with:
  generate_response(response="...brief summary...")
"""


@dataclass
class _EditSession:
    tb_path: str
    rtl_path: str
    output_dir: str
    last_mismatch_cnt: int
    sim_reviewer: SimReviewer
    max_trials: int
    kg_service: Any | None = None
    kg_session_id: str = ""
    kg_hop_depth: int = 3

    is_done: bool = False
    action_calls: int = 0
    trace_report: Dict[str, Any] | None = None
    blocks_by_id: Dict[str, RtlBlock] | None = None
    last_fail_time: int | None = None
    repair_journal: list[dict[str, Any]] = field(default_factory=list)

    def read_rtl(self) -> str:
        with open(self.rtl_path, "r", encoding="utf-8") as f:
            return f.read()

    def read_rtl_with_lineno(self) -> str:
        lines = self.read_rtl().splitlines()
        return "\n".join(f"{i+1}: {line}" for i, line in enumerate(lines)) + "\n"

    def write_rtl(self, content: str) -> None:
        with open(self.rtl_path, "w", encoding="utf-8") as f:
            f.write(content)

    def run_simulation(self) -> Dict[str, Any]:
        is_sim_pass, sim_mismatch_cnt, sim_output = self.sim_reviewer.review()
        # Persist full sim output for human inspection; provide excerpt to the agent.
        try:
            Path(self.output_dir, "debug_sim_output.json").write_text(sim_output, encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
        return {
            "is_sim_pass": is_sim_pass,
            "sim_mismatch_cnt": sim_mismatch_cnt,
            "sim_output_excerpt": _summarize_sim_log_json(sim_output),
            "sim_output_path": str(Path(self.output_dir, "debug_sim_output.json")),
        }

    def list_suspect_blocks(self) -> list[dict[str, Any]]:
        if not self.trace_report:
            return []
        return list(self.trace_report.get("suspect_blocks") or [])

    def read_block(self, block_id: str) -> str:
        if not self.blocks_by_id or block_id not in self.blocks_by_id:
            return f"ERROR: Unknown block_id '{block_id}'."
        block = self.blocks_by_id[block_id]
        lines = block.code.splitlines()
        return "\n".join(f"{block.start_line + i}: {line}" for i, line in enumerate(lines)) + "\n"

    def read_rtl_context(self) -> str:
        return self.read_rtl_with_lineno()

    # ------------------------------------------------------------------
    # VCD probe helpers
    # ------------------------------------------------------------------

    def _load_vcd(self) -> Any:
        """Load the VCD file. Returns None if not available."""
        if VCDVCD is None:
            return None
        vcd_path = Path(self.output_dir) / "wave.vcd"
        if not vcd_path.exists():
            return None
        try:
            return VCDVCD(str(vcd_path), store_tvs=True)
        except Exception:
            return None

    def _get_vcd_context(self) -> dict[str, str | None]:
        """Resolve dut/ref instance names from the current trace_report."""
        tr = self.trace_report or {}
        dut = tr.get("dut_instance")
        # ref instance is resolved on-the-fly from the VCD
        return {"dut": dut, "ref": None}

    def list_vcd_signals(
        self, pattern: str = "", scope: str = "", limit: int = 100
    ) -> dict[str, Any]:
        """List VCD signal names matching *pattern*."""
        vcd = self._load_vcd()
        if vcd is None:
            return {"status": "missing_vcd", "error": "wave.vcd not found; run_simulation first"}
        return list_vcd_signals_query(vcd, pattern=pattern, scope=scope, limit=limit)

    def probe_vcd(
        self,
        signals: list[str],
        time: int | None = None,
        time_range: list[int] | None = None,
        edge: str | None = None,
        mode: str = "sample",
        max_rows: int = 80,
    ) -> dict[str, Any]:
        """Sample VCD signals at a single time or over a range."""
        vcd = self._load_vcd()
        if vcd is None:
            return {"status": "missing_vcd", "error": "wave.vcd not found; run_simulation first"}
        if not signals:
            return {"status": "too_many_signals", "error": "No signals provided"}

        ctx = self._get_vcd_context()
        dut = ctx["dut"]
        ref = ctx["ref"] or _resolve_ref_instance_static(vcd)

        # Resolve all signal names
        resolved: list[str] = []
        for name in signals:
            r = resolve_vcd_signal(vcd, name, dut_instance=dut, ref_instance=ref)
            if r["status"] != "ok":
                return r
            resolved.append(r["full_path"])

        # Build time points
        times: list[int] | None = None
        t_range: tuple[int, int] | None = None
        clock_name: str | None = None

        if time is not None:
            times = [time]
        elif time_range is not None and len(time_range) == 2:
            t_range = (int(time_range[0]), int(time_range[1]))
        else:
            # Auto-detect full simulation time range
            detected = _vcd_time_range(vcd)
            if detected is not None:
                t_range = detected

        if t_range is not None and edge:
            edge_parts = edge.strip().split()
            clk_hint = edge_parts[1] if len(edge_parts) > 1 else None
            clock_full = _find_clock_signal(vcd, preferred_name=clk_hint)
            if clock_full is None:
                return {"status": "missing_vcd", "error": f"Clock signal not found in VCD (hint: {clk_hint})"}
            clock_name = clock_full

        if times is None and t_range is None:
            return {"status": "missing_time_range", "error": "Provide time, time_range, or ensure VCD has data"}

        return sample_vcd_signals(
            vcd, resolved,
            times=times, time_range=t_range, clock_name=clock_name,
            edge_filter=edge.split()[0] if edge else None,
            mode=mode, max_rows=max_rows,
        )

    def probe_compare(
        self,
        pairs: list[list[str]],
        time_range: list[int] | None = None,
        edge: str | None = None,
        first_diff_only: bool = True,
        max_rows: int = 80,
    ) -> dict[str, Any]:
        """Compare signal pairs and return the first difference."""
        vcd = self._load_vcd()
        if vcd is None:
            return {"status": "missing_vcd", "error": "wave.vcd not found; run_simulation first"}
        if not pairs:
            return {"status": "too_many_signals", "error": "No pairs provided"}

        ctx = self._get_vcd_context()
        dut = ctx["dut"]
        ref = ctx["ref"] or _resolve_ref_instance_static(vcd)

        # Resolve pairs
        resolved_pairs: list[list[str]] = []
        for pair in pairs:
            if len(pair) != 2:
                return {"status": "too_many_signals", "error": f"Each pair must have exactly 2 signals, got {pair}"}
            resolved_pair: list[str] = []
            for name in pair:
                r = resolve_vcd_signal(vcd, name, dut_instance=dut, ref_instance=ref)
                if r["status"] != "ok":
                    return r
                resolved_pair.append(r["full_path"])
            resolved_pairs.append(resolved_pair)

        # Build time range — auto-detect full simulation range if not provided
        t_range: tuple[int, int] | None = None
        times: list[int] | None = None
        clock_name: str | None = None
        edge_filter: str | None = None

        if time_range is not None and len(time_range) == 2:
            t_range = (int(time_range[0]), int(time_range[1]))
        elif time_range is None:
            detected = _vcd_time_range(vcd)
            if detected is None:
                return {"status": "missing_vcd", "error": "Cannot determine VCD time range; provide time_range explicitly"}
            t_range = detected

        if t_range is not None and edge:
            edge_parts = edge.strip().split()
            edge_filter = edge_parts[0] if edge_parts else None
            clk_hint = edge_parts[1] if len(edge_parts) > 1 else None
            clock_full = _find_clock_signal(vcd, preferred_name=clk_hint)
            if clock_full is None:
                return {"status": "missing_vcd", "error": f"Clock signal not found (hint: {clk_hint})"}
            clock_name = clock_full

        if t_range is None:
            return {"status": "missing_time_range", "error": "Provide time_range or ensure VCD is available"}

        return compare_vcd_pairs(
            vcd, resolved_pairs,
            times=times, time_range=t_range, clock_name=clock_name,
            edge_filter=edge_filter, first_diff_only=first_diff_only,
            max_rows=max_rows,
        )

    def _refresh_trace(self, *, sim_log_json: str) -> None:
        report, suspect_blocks = build_trace_report(
            rtl_path=Path(self.rtl_path),
            sim_log_json=sim_log_json,
            output_dir=Path(self.output_dir),
            kg_service=self.kg_service,
            kg_session_id=self.kg_session_id,
            kg_hop_depth=self.kg_hop_depth,
        )
        self.trace_report = report
        self.blocks_by_id = {b.id: b for b in suspect_blocks} if suspect_blocks else None
        ft = report.get("fail_time")
        self.last_fail_time = int(ft) if isinstance(ft, int) else None
        (Path(self.output_dir) / "trace_report.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def trace_report_path(self) -> str:
        return str(Path(self.output_dir) / "trace_report.json")

    def trace_summary(self) -> Dict[str, Any]:
        tr = self.trace_report or {}
        suspects = tr.get("suspect_blocks") or []
        fail_outputs = tr.get("fail_outputs") or []
        alignment = tr.get("alignment_diagnosis") or {}
        timing_hints = tr.get("timing_hints") or {}
        diagnostic_narrative = tr.get("diagnostic_narrative") or []
        value_backtrace = tr.get("value_backtrace") or {}

        # Compact alignment summary: keep only the best_alignment and a couple of rates per output.
        alignment_compact: Dict[str, Any] = {}
        if isinstance(alignment, dict):
            for sig, info in alignment.items():
                if not isinstance(info, dict):
                    continue
                alignment_compact[str(sig)] = {
                    "best_alignment": info.get("best_alignment"),
                    "match_rate_dut_lag1": info.get("match_rate_dut_lag1"),
                }

        return {
            "trace_report_path": self.trace_report_path(),
            "fail_time": tr.get("fail_time"),
            "total_mismatches": tr.get("total_mismatches"),
            "first_failure": tr.get("first_failure"),
            "top_diagnosis": diagnostic_narrative[0] if isinstance(diagnostic_narrative, list) and diagnostic_narrative else None,
            "value_backtrace_summary": [
                {
                    "sig": chain.get("sig"),
                    "expected": chain.get("expected"),
                    "actual": chain.get("actual"),
                    "steps": [
                        {
                            "signal": step.get("signal"),
                            "driver_block_id": step.get("driver_block_id"),
                            "assignment_id": step.get("assignment_id"),
                            "classification": step.get("classification"),
                            "reason": step.get("reason"),
                            "rhs_observed_values": step.get("rhs_observed_values"),
                            "condition_values": step.get("condition_values"),
                        }
                        for step in (chain.get("chain") or [])[:4]
                        if isinstance(step, dict)
                    ],
                }
                for chain in (value_backtrace.get("chains") or [])[:3]
                if isinstance(chain, dict)
            ],
            "repair_journal_summary": self.repair_journal_summary(),
            "fail_outputs": [
                {"sig": fo.get("sig"), "expected": fo.get("expected"), "actual": fo.get("actual")}
                for fo in fail_outputs
                if isinstance(fo, dict)
            ][:5],
            "suspect_blocks": [
                {
                    "id": b.get("id"),
                    "clocking": b.get("clocking"),
                    "start_line": b.get("start_line"),
                    "end_line": b.get("end_line"),
                    "writes": b.get("writes"),
                }
                for b in suspects
                if isinstance(b, dict)
            ][:8],
            "alignment_diagnosis": alignment_compact,
            "timing_hints": timing_hints,
            "dut_instance": tr.get("dut_instance"),
            "vcd_available": tr.get("vcd_available"),
        }

    def repair_journal_summary(self, limit: int = 5) -> list[dict[str, Any]]:
        summary: list[dict[str, Any]] = []
        for entry in self.repair_journal[-max(1, int(limit)) :]:
            summary.append(
                {
                    "trial": entry.get("trial"),
                    "action_type": entry.get("action_type"),
                    "target": entry.get("target"),
                    "patch_count": entry.get("patch_count"),
                    "patch_summary": entry.get("patch_summary"),
                    "effect": entry.get("effect"),
                    "lesson": entry.get("lesson"),
                    "before": entry.get("before"),
                    "after": entry.get("after"),
                }
            )
        return summary

    def _top_diagnosis(self) -> Any:
        tr = self.trace_report or {}
        diagnostic_narrative = tr.get("diagnostic_narrative") or []
        if isinstance(diagnostic_narrative, list) and diagnostic_narrative:
            return diagnostic_narrative[0]
        return None

    def _journal_before(self) -> dict[str, Any]:
        return {
            "mismatch_cnt": int(self.last_mismatch_cnt),
            "fail_time": self.last_fail_time,
            "top_diagnosis": self._top_diagnosis(),
        }

    def _summarize_code(self, code: str, *, max_chars: int = 160) -> str:
        text = " ".join(line.strip() for line in code.strip().splitlines() if line.strip())
        if len(text) > max_chars:
            return text[: max_chars - 3] + "..."
        return text

    def _classify_repair_effect(self, *, before: dict[str, Any], result: dict[str, Any]) -> str:
        if result.get("is_sim_pass") and int(result.get("sim_mismatch_cnt") or 0) == 0:
            return "passed"
        if result.get("is_syntax_correct") is False and result.get("syntax_output"):
            return "syntax_failed"
        if not result.get("is_action_executed"):
            return "rejected"

        before_mismatches = int(before.get("mismatch_cnt") or 0)
        after_mismatches = int(result.get("sim_mismatch_cnt") or 0)
        before_fail_time = before.get("fail_time")
        after_fail_time = result.get("new_fail_time")

        if after_mismatches < before_mismatches:
            return "improved"
        if isinstance(before_fail_time, int) and isinstance(after_fail_time, int):
            if after_fail_time > before_fail_time:
                return "improved"
            if after_fail_time < before_fail_time:
                return "regressed"
        if after_mismatches > before_mismatches:
            return "regressed"
        return "neutral"

    def _lesson_for_effect(self, *, effect: str, result: dict[str, Any]) -> str:
        if effect == "passed":
            return "Patch fixed all observed mismatches."
        if effect == "improved":
            return "Patch improved the simulation result; continue from this direction."
        if effect == "neutral":
            return "Patch was accepted but did not clearly improve mismatch count or first fail time."
        if effect == "regressed":
            return "Patch was accepted but worsened a tracked metric; avoid broadening this direction without new evidence."
        if effect == "syntax_failed":
            return "Patch failed syntax and was rolled back; fix syntax before retrying this idea."
        error_msg = str(result.get("error_msg") or "")
        if "at most 10 patches" in error_msg:
            return "Too many patches in one call; split into smaller groups of up to 10 patches each."
        if "rolled back" in error_msg:
            return "Patch was rolled back; avoid retrying this exact change without new evidence."
        return "Patch was rejected; choose a smaller evidence-backed edit."

    def _persist_repair_journal(self) -> None:
        try:
            Path(self.output_dir, "repair_journal.json").write_text(
                json.dumps(self.repair_journal, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except Exception:  # noqa: BLE001
            pass

    def _record_repair_journal_entry(
        self,
        *,
        action_type: str,
        target: dict[str, Any],
        patch_count: int,
        patch_summary: str,
        before: dict[str, Any],
        result: dict[str, Any],
    ) -> None:
        effect = self._classify_repair_effect(before=before, result=result)
        after = {
            "accepted": bool(result.get("is_action_executed")),
            "is_sim_pass": bool(result.get("is_sim_pass")),
            "mismatch_cnt": result.get("sim_mismatch_cnt"),
            "fail_time": result.get("new_fail_time"),
            "error_msg": result.get("error_msg") or "",
        }
        entry = {
            "trial": len(self.repair_journal) + 1,
            "action_type": action_type,
            "target": target,
            "patch_count": int(patch_count),
            "patch_summary": patch_summary,
            "before": before,
            "after": after,
            "effect": effect,
            "lesson": self._lesson_for_effect(effect=effect, result=result),
        }
        self.repair_journal.append(entry)
        self._persist_repair_journal()

    def _attach_repair_journal_summary(self, result: dict[str, Any]) -> dict[str, Any]:
        result["repair_journal_summary"] = self.repair_journal_summary()
        return result

    def _base_result(self) -> Dict[str, Any]:
        return {
            "is_action_executed": False,
            "is_syntax_correct": False,
            "syntax_output": "",
            "is_sim_pass": False,
            "sim_mismatch_cnt": 0,
            "sim_output": "",
            "error_msg": "",
        }

    def _judge_replace_action_execution(self, *, old_file_content: str) -> Dict[str, Any]:
        result = self._base_result()
        prev_mismatch_cnt = int(self.last_mismatch_cnt)
        prev_fail_time = self.last_fail_time
        is_syntax_correct, syntax_output_raw = check_syntax(self.rtl_path)
        result["is_syntax_correct"] = is_syntax_correct
        if not is_syntax_correct:
            # Filter stderr to only show DUT-relevant warnings/errors
            try:
                syntax_obj = json.loads(syntax_output_raw)
                syntax_obj["stderr"] = _filter_verilator_stderr(
                    str(syntax_obj.get("stderr") or "")
                )
                result["syntax_output"] = json.dumps(syntax_obj)
            except Exception:  # noqa: BLE001
                result["syntax_output"] = syntax_output_raw
            self.write_rtl(old_file_content)
            result["error_msg"] = "Syntax error. Action rolled back."
            return result

        is_sim_pass, sim_mismatch_cnt, sim_output = self.sim_reviewer.review()
        result["is_sim_pass"] = is_sim_pass
        result["sim_mismatch_cnt"] = sim_mismatch_cnt
        try:
            Path(self.output_dir, "debug_sim_output.json").write_text(sim_output, encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
        result["sim_output_excerpt"] = _summarize_sim_log_json(sim_output)
        result["sim_output_path"] = str(Path(self.output_dir, "debug_sim_output.json"))
        result["prev_mismatch_cnt"] = prev_mismatch_cnt
        result["prev_fail_time"] = prev_fail_time
        new_fail_time = _extract_fail_time_from_sim_log_json(sim_output)
        result["new_fail_time"] = new_fail_time

        if sim_mismatch_cnt > prev_mismatch_cnt:
            increase = int(sim_mismatch_cnt) - int(prev_mismatch_cnt)
            max_increase = max(5, int(0.05 * max(1, int(prev_mismatch_cnt))))
            if increase > max_increase:
                self.write_rtl(old_file_content)
                result["error_msg"] = (
                    "Mismatch_cnt increased significantly after replacement. Action rolled back. "
                    f"(prev={prev_mismatch_cnt}, new={sim_mismatch_cnt}, increase={increase}, max_allowed={max_increase})"
                )
                return result
            result["accept_reason"] = (
                "Accepted despite slight mismatch increase "
                f"(+{increase} mismatches, within tolerance of {max_increase})."
            )

        if sim_mismatch_cnt == 0 and not is_sim_pass:
            self.write_rtl(old_file_content)
            result["error_msg"] = "Mismatch_cnt is 0 but simulation failed. Action rolled back."
            return result

        # Accept.
        self.last_mismatch_cnt = sim_mismatch_cnt
        if new_fail_time is not None:
            self.last_fail_time = int(new_fail_time)
        result["is_action_executed"] = True
        if is_sim_pass and sim_mismatch_cnt == 0:
            self.is_done = True
        else:
            self._refresh_trace(sim_log_json=sim_output)
            result["trace_summary"] = self.trace_summary()
        return result

    def replace_block(self, block_id: str, new_code: str) -> Dict[str, Any]:
        if not self.blocks_by_id or block_id not in self.blocks_by_id:
            return {
                "is_action_executed": False,
                "error_msg": f"Unknown block_id '{block_id}'. Use list_suspect_blocks() first.",
            }

        old_file_content = self.read_rtl()
        old_lines = old_file_content.splitlines()
        block = self.blocks_by_id[block_id]
        start = block.start_line - 1
        end = block.end_line - 1
        if start < 0 or end >= len(old_lines) or start > end:
            return {
                "is_action_executed": False,
                "error_msg": f"Invalid block range for {block_id}: {block.start_line}-{block.end_line}.",
            }

        before = self._journal_before()
        self.action_calls += 1
        if self.action_calls > self.max_trials:
            result = {
                "is_action_executed": False,
                "error_msg": "Reached maximum debug trials; refusing further edits.",
            }
            self._record_repair_journal_entry(
                action_type="replace_block",
                target={"block_id": block_id, "start_line": block.start_line, "end_line": block.end_line},
                patch_count=1,
                patch_summary=self._summarize_code(new_code),
                before=before,
                result=result,
            )
            return self._attach_repair_journal_summary(result)

        new_block_lines = new_code.rstrip("\n").splitlines()
        new_lines = old_lines[:start] + new_block_lines + old_lines[end + 1 :]
        self.write_rtl("\n".join(new_lines) + ("\n" if old_file_content.endswith("\n") else ""))

        result = self._judge_replace_action_execution(old_file_content=old_file_content)
        self._record_repair_journal_entry(
            action_type="replace_block",
            target={"block_id": block_id, "start_line": block.start_line, "end_line": block.end_line},
            patch_count=1,
            patch_summary=self._summarize_code(new_code),
            before=before,
            result=result,
        )
        return self._attach_repair_journal_summary(result)

    def apply_patch_set(self, patches: list[dict[str, Any]]) -> Dict[str, Any]:
        before = self._journal_before()

        def reject_without_edit(error_msg: str, *, patch_count: int = 0) -> Dict[str, Any]:
            result = self._base_result()
            result["error_msg"] = error_msg
            self._record_repair_journal_entry(
                action_type="apply_patch_set",
                target={"patches": patch_count},
                patch_count=patch_count,
                patch_summary=error_msg,
                before=before,
                result=result,
            )
            return self._attach_repair_journal_summary(result)

        if not isinstance(patches, list) or not patches:
            return reject_without_edit("patches must contain exactly one line-range replacement.")

        if len(patches) > 10:
            return reject_without_edit(
                f"apply_patch_set accepts at most 10 patches per trial (got {len(patches)}); "
                "split independent edits across multiple apply_patch_set calls.",
                patch_count=len(patches),
            )

        old_file_content = self.read_rtl()
        old_lines = old_file_content.splitlines()
        normalized: list[tuple[int, int, str]] = []
        for index, patch in enumerate(patches):
            if not isinstance(patch, dict):
                return reject_without_edit(f"Invalid patch at index {index}: expected an object.", patch_count=1)
            # Tool-call compatibility: older prompts / other agents sometimes use
            # line_start/line_end instead of start_line/end_line.
            start_line = _parse_patch_line_number(
                patch.get("start_line") if "start_line" in patch else patch.get("line_start")
            )
            end_line = _parse_patch_line_number(
                patch.get("end_line") if "end_line" in patch else patch.get("line_end")
            )
            # Tool-call compatibility: some agents use new_line instead of new_code.
            new_code = patch.get("new_code") if "new_code" in patch else patch.get("new_line")
            if start_line is None or end_line is None or not isinstance(new_code, str):
                return reject_without_edit(
                    (
                        f"Invalid patch at index {index}: require integer or decimal-string "
                        "start_line/end_line and string new_code."
                    ),
                    patch_count=1,
                )
            if start_line < 1 or end_line < start_line or end_line > len(old_lines):
                return reject_without_edit(
                    f"Invalid patch range at index {index}: {start_line}-{end_line}.",
                    patch_count=1,
                )
            normalized.append((start_line - 1, end_line - 1, new_code))

        normalized.sort(key=lambda item: item[0])
        for previous, current in zip(normalized, normalized[1:]):
            if current[0] <= previous[1]:
                return reject_without_edit("Patch ranges must not overlap.", patch_count=len(normalized))

        self.action_calls += 1
        if self.action_calls > self.max_trials:
            result = {
                "is_action_executed": False,
                "error_msg": "Reached maximum debug trials; refusing further edits.",
            }
            patch = patches[0] if patches and isinstance(patches[0], dict) else {}
            self._record_repair_journal_entry(
                action_type="apply_patch_set",
                target={"patch": patch},
                patch_count=1,
                patch_summary=self._summarize_code(str(patch)),
                before=before,
                result=result,
            )
            return self._attach_repair_journal_summary(result)

        new_lines = list(old_lines)
        for start, end, new_code in reversed(normalized):
            replacement = new_code.rstrip("\n").splitlines()
            new_lines[start : end + 1] = replacement
        self.write_rtl("\n".join(new_lines) + ("\n" if old_file_content.endswith("\n") else ""))

        start, end, new_code = normalized[0]
        result = self._judge_replace_action_execution(old_file_content=old_file_content)
        self._record_repair_journal_entry(
            action_type="apply_patch_set",
            target={"start_line": start + 1, "end_line": end + 1},
            patch_count=1,
            patch_summary=self._summarize_code(new_code),
            before=before,
            result=result,
        )
        return self._attach_repair_journal_summary(result)


class RTLEditor:
    def __init__(
        self,
        cfg: OpenAIConfig,
        *,
        sim_reviewer: SimReviewer,
        max_trials: int = 10,
        kg_service: Any | None = None,
        kg_hop_depth: int = 3,
    ) -> None:
        self._cfg = cfg
        self.sim_reviewer = sim_reviewer
        self.max_trials = int(max_trials)
        self.kg_service = kg_service
        self.kg_hop_depth = int(kg_hop_depth)
        self._session: _EditSession | None = None

        toolkit = Toolkit()
        toolkit.register_tool_function(self._tool_list_suspect_blocks)
        toolkit.register_tool_function(self._tool_read_block)
        toolkit.register_tool_function(self._tool_replace_block)
        toolkit.register_tool_function(self._tool_read_rtl_context)
        toolkit.register_tool_function(
            self._tool_apply_patch_set,
            json_schema={
                "type": "function",
                "function": {
                    "name": "_tool_apply_patch_set",
                    "description": "Apply exactly one RTL line-range replacement as one validated semantic patch.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "patches": {
                                "type": "array",
                                "minItems": 1,
                                "maxItems": 1,
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "start_line": {
                                            "type": "string",
                                            "description": "First line number to replace (1-based, integer or decimal-string). Alias: line_start.",
                                        },
                                        "end_line": {
                                            "type": "string",
                                            "description": "Last line number to replace (1-based, integer or decimal-string). Alias: line_end.",
                                        },
                                        "new_code": {
                                            "type": "string",
                                            "description": "The replacement code to insert in place of lines start_line..end_line. Alias: new_line.",
                                        },
                                    },
                                    "required": ["start_line", "end_line", "new_code"],
                                },
                            }
                        },
                        "required": ["patches"],
                    },
                },
            },
        )
        toolkit.register_tool_function(self._tool_run_simulation)
        toolkit.register_tool_function(self._tool_list_vcd_signals)
        toolkit.register_tool_function(self._tool_probe_vcd)
        toolkit.register_tool_function(self._tool_probe_compare)

        self._agent = SafeReActAgent(
            name="Debugger",
            sys_prompt=SYSTEM_PROMPT,
            model=make_openai_model(cfg),
            formatter=make_formatter(cfg.model, cfg.base_url),
            toolkit=toolkit,
            memory=InMemoryMemory(),
            max_iters=10,
        )

    def _log_message(self, role: str, content: str) -> None:
        """Log a prompt/response/tool-result to stdout and to the JSONL file.

        Uses ``print()`` so output appears inline in the captured log alongside
        AgentScope ``Debugger(thinking)`` lines.
        """
        # Print to stdout for inline log readability.
        print(f"Debugger({role}):\n{content}", flush=True)

        # Also persist to JSONL for later programmatic consumption.
        if self._session is not None:
            try:
                path = Path(self._session.output_dir) / "debugger_messages.jsonl"
                entry: dict[str, object] = {"role": role, "content": content}
                with open(path, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
            except Exception:  # noqa: BLE001
                pass

    def _tool_response(self, tool_name: str, text: str) -> ToolResponse:
        """Return a ToolResponse and log its content to the session message log."""
        self._log_message("tool_result", f"[{tool_name}]\n{text}")
        return ToolResponse(content=[{"type": "text", "text": text}])

    def reset(self) -> None:
        clear_memory_safely(self._agent)
        self._session = None

    async def _tool_list_suspect_blocks(self) -> ToolResponse:
        """List dynamically sliced suspect blocks (always/assign)."""
        if self._session is None:
            return ToolResponse(content=[{"type": "text", "text": "ERROR: No active edit session."}])
        blocks = self._session.list_suspect_blocks()
        return self._tool_response("list_suspect_blocks", json.dumps(blocks, indent=2))

    async def _tool_read_block(self, block_id: str) -> ToolResponse:
        """Read a suspect block by id with line numbers."""
        if self._session is None:
            return ToolResponse(content=[{"type": "text", "text": "ERROR: No active edit session."}])
        return self._tool_response("read_block", self._session.read_block(block_id))

    async def _tool_run_simulation(self) -> ToolResponse:
        """Run simulation for current rtl.sv + tb.sv; returns pass/fail and mismatch count."""
        if self._session is None:
            return ToolResponse(content=[{"type": "text", "text": "ERROR: No active edit session."}])
        result = await asyncio.to_thread(self._session.run_simulation)
        # Keep trace_report.json in sync even when the model triggers standalone re-simulations.
        try:
            if (not result.get("is_sim_pass")) and int(result.get("sim_mismatch_cnt") or 0) > 0:
                sim_output_path = result.get("sim_output_path")
                sim_output = ""
                if isinstance(sim_output_path, str) and sim_output_path.strip():
                    sim_output = await asyncio.to_thread(Path(sim_output_path).read_text, encoding="utf-8")
                if sim_output.strip():
                    await asyncio.to_thread(self._session._refresh_trace, sim_log_json=sim_output)
            if self._session.trace_report:
                result["trace_summary"] = self._session.trace_summary()
        except Exception:  # noqa: BLE001
            # Tooling should never crash due to trace refresh; keep sim result.
            pass
        return self._tool_response("run_simulation", json.dumps(result, indent=4))

    async def _tool_replace_block(self, block_id: str, new_code: str) -> ToolResponse:
        """Replace a suspect block by id, then syntax-check + simulate (rollback if mismatch increases)."""
        if self._session is None:
            return ToolResponse(content=[{"type": "text", "text": "ERROR: No active edit session."}])
        result = await asyncio.to_thread(self._session.replace_block, block_id, new_code)
        # Even if the action was rolled back, return the latest available trace pointer/summary
        # so the agent can re-ground itself quickly.
        if self._session.trace_report:
            result.setdefault("trace_summary", self._session.trace_summary())
        return self._tool_response("replace_block", json.dumps(result, indent=4))

    async def _tool_read_rtl_context(self) -> ToolResponse:
        """Read the complete RTL file with line numbers for declaration or wiring diagnosis."""
        if self._session is None:
            return ToolResponse(content=[{"type": "text", "text": "ERROR: No active edit session."}])
        return self._tool_response("read_rtl_context", self._session.read_rtl_context())

    async def _tool_apply_patch_set(self, patches: list[dict[str, Any]]) -> ToolResponse:
        """Apply exactly one RTL line-range replacement as one validated semantic patch."""
        if self._session is None:
            return ToolResponse(content=[{"type": "text", "text": "ERROR: No active edit session."}])
        result = await asyncio.to_thread(self._session.apply_patch_set, patches)
        if self._session.trace_report:
            result.setdefault("trace_summary", self._session.trace_summary())
        return self._tool_response("apply_patch_set", json.dumps(result, indent=4))

    async def _tool_list_vcd_signals(
        self, pattern: str = "", scope: str = "", limit: int = 100
    ) -> ToolResponse:
        """List VCD signal names optionally filtered by pattern and scope."""
        if self._session is None:
            return ToolResponse(content=[{"type": "text", "text": "ERROR: No active edit session."}])
        result = await asyncio.to_thread(
            self._session.list_vcd_signals, pattern=pattern, scope=scope, limit=limit
        )
        return self._tool_response("list_vcd_signals", json.dumps(result, indent=2))

    async def _tool_probe_vcd(
        self,
        signals: list[str],
        time: int | None = None,
        time_range: list[int] | None = None,
        edge: str | None = None,
        mode: str = "sample",
        max_rows: int = 80,
    ) -> ToolResponse:
        """Sample VCD signals at a single time or over a range with optional edge filter."""
        if self._session is None:
            return ToolResponse(content=[{"type": "text", "text": "ERROR: No active edit session."}])
        result = await asyncio.to_thread(
            self._session.probe_vcd,
            signals=signals, time=time, time_range=time_range,
            edge=edge, mode=mode, max_rows=max_rows,
        )
        return self._tool_response("probe_vcd", json.dumps(result, indent=2))

    async def _tool_probe_compare(
        self,
        pairs: list[list[str]],
        time_range: list[int] | None = None,
        edge: str | None = None,
        first_diff_only: bool = True,
        max_rows: int = 80,
    ) -> ToolResponse:
        """Compare VCD signal pairs to find the first difference time."""
        if self._session is None:
            return ToolResponse(content=[{"type": "text", "text": "ERROR: No active edit session."}])
        result = await asyncio.to_thread(
            self._session.probe_compare,
            pairs=pairs, time_range=time_range, edge=edge,
            first_diff_only=first_diff_only, max_rows=max_rows,
        )
        return self._tool_response("probe_compare", json.dumps(result, indent=2))

    async def chat(
        self,
        *,
        spec: str,
        output_dir_per_run: str,
        sim_failed_log: str,
        sim_mismatch_cnt: int,
        contract_json: str,
        behavior_source: Literal["contract", "spec_tb"] = "contract",
        max_trials: int | None = None,
    ) -> Tuple[bool, str, int]:
        self.reset()
        if behavior_source not in {"contract", "spec_tb"}:
            raise ValueError(f"Unsupported behavior_source: {behavior_source!r}")
        tb_path = f"{output_dir_per_run}/tb.sv"
        rtl_path = f"{output_dir_per_run}/rtl.sv"
        session_max_trials = int(max_trials) if max_trials is not None else int(self.max_trials)
        if session_max_trials < 0:
            session_max_trials = 0
        kg_module_name = Path(rtl_path).stem
        try:
            contract_obj = json.loads(contract_json)
            if isinstance(contract_obj, dict) and isinstance(contract_obj.get("module_name"), str):
                kg_module_name = str(contract_obj["module_name"]).strip() or kg_module_name
        except Exception:  # noqa: BLE001
            pass
        kg_session_id = kg_debug_session_id(kg_module_name)

        self._session = _EditSession(
            tb_path=tb_path,
            rtl_path=rtl_path,
            output_dir=output_dir_per_run,
            last_mismatch_cnt=sim_mismatch_cnt,
            sim_reviewer=self.sim_reviewer,
            max_trials=session_max_trials,
            kg_service=self.kg_service,
            kg_session_id=kg_session_id,
            kg_hop_depth=self.kg_hop_depth,
        )

        with open(tb_path, "r", encoding="utf-8") as f:
            generated_tb = f.read()

        # Save full failed log for inspection, but only send a short excerpt to the agent.
        try:
            (Path(output_dir_per_run) / "sim_failed_log.json").write_text(sim_failed_log, encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
        sim_failed_log_excerpt = _summarize_sim_log_json(sim_failed_log)

        kmap_source = f"{spec}\n{contract_json}" if behavior_source == "contract" else spec
        needs_kmap_hint = any(k in kmap_source.lower() for k in ["kmap", "k-map", "karnaugh"])
        if behavior_source == "spec_tb":
            continue_source_context = (
                "<original_module_spec>\n"
                f"{spec}\n"
                "</original_module_spec>\n"
                "The original module specification above remains the design source of truth for this repair session."
            )
        else:
            continue_source_context = (
                "<input_spec>\n"
                f"{spec}\n"
                "</input_spec>\n"
                "<contract_json>\n"
                f"{contract_json}\n"
                "</contract_json>\n"
                "The contract_json above remains the repair source of truth; input_spec is background only."
            )
        if behavior_source == "spec_tb":
            init = SPEC_TB_INIT_EDITION_PROMPT.format(
                input_spec=spec,
                generated_tb=generated_tb,
                sim_failed_log_excerpt=sim_failed_log_excerpt,
                kmap_hint=(KMAP_DEBUG_HINT_PROMPT if needs_kmap_hint else ""),
            )
            order_prompt = SPEC_TB_EXTRA_ORDER_PROMPT
            continue_prompt = (
                f"{continue_source_context}\n\n"
                "Continue debugging. Preserve the original specification's top-level interface and observed "
                "testbench behavior. If mismatches remain, use read_block(block_id) and "
                "replace_block(block_id, new_code), or read_rtl_context() and apply_patch_set(patches) "
                "with exactly one line-range replacement for declaration or wiring fixes, then run_simulation()."
            )
        else:
            init = CONTRACT_INIT_EDITION_PROMPT.format(
                input_spec=spec,
                contract_json=contract_json,
                generated_tb=_clip_text(generated_tb, max_chars=8000),
                sim_failed_log_excerpt=sim_failed_log_excerpt,
                kmap_hint=(KMAP_DEBUG_HINT_PROMPT if needs_kmap_hint else ""),
            )
            order_prompt = CONTRACT_EXTRA_ORDER_PROMPT
            continue_prompt = (
                f"{continue_source_context}\n\n"
                "Continue debugging. Preserve the contract-defined module interface. If mismatches remain, "
                "use read_block(block_id) and replace_block(block_id, new_code), or read_rtl_context() and "
                "apply_patch_set(patches) with exactly one line-range replacement for declaration or wiring fixes, "
                "then run_simulation()."
            )
        # Build a trace-grounded report to guide minimal patching.
        report, suspect_blocks = build_trace_report(
            rtl_path=Path(rtl_path),
            sim_log_json=sim_failed_log,
            output_dir=Path(output_dir_per_run),
            kg_service=self.kg_service,
            kg_session_id=kg_session_id,
            kg_hop_depth=self.kg_hop_depth,
        )
        (Path(output_dir_per_run) / "trace_report.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        self._session.trace_report = report
        self._session.blocks_by_id = {b.id: b for b in suspect_blocks} if suspect_blocks else None
        ft0 = report.get("fail_time")
        self._session.last_fail_time = int(ft0) if isinstance(ft0, int) else None

        # Build a compact trace summary (not the full report JSON) for the LLM prompt.
        trace_summary_for_prompt = json.dumps(
            {
                "first_failure": report.get("first_failure"),
                "fail_time": report.get("fail_time"),
                "total_mismatches": report.get("total_mismatches"),
                "fail_outputs": report.get("fail_outputs"),
                "top_diagnosis": (report.get("diagnostic_narrative") or [None])[0],
                "value_backtrace_summary": [
                    {
                        "sig": c.get("sig"),
                        "expected": c.get("expected"),
                        "actual": c.get("actual"),
                        "steps": [
                            {
                                "signal": s.get("signal"),
                                "driver_block_id": s.get("driver_block_id"),
                                "classification": s.get("classification"),
                                "reason": s.get("reason"),
                                "rhs_observed_values": s.get("rhs_observed_values"),
                                "condition_values": s.get("condition_values"),
                            }
                            for s in (c.get("chain") or [])[:4]
                            if isinstance(s, dict)
                        ],
                    }
                    for c in (report.get("value_backtrace", {}).get("chains") or [])[:3]
                    if isinstance(c, dict)
                ],
                "suspect_blocks": report.get("suspect_blocks"),
                "alignment_diagnosis": report.get("alignment_diagnosis"),
                "vcd_available": report.get("vcd_available"),
            },
            indent=2, ensure_ascii=False,
        )

        vcd_probe_instructions = (
            "VCD PROBE TOOLS (use BEFORE patching when root cause is unclear):\n"
            "- list_vcd_signals(pattern=\"...\", scope=\"\", limit=100) — discover internal signal names in the VCD.\n"
            "- probe_vcd(signals=[...], time=N) — sample signal values at a single simulation time.\n"
            "- probe_vcd(signals=[...], time_range=[0, N], edge=\"posedge rclk\", mode=\"changes\") — sample over a range.\n"
            "- probe_compare(pairs=[[\"ref.q\", \"dut.q\"]], time_range=[0, N], edge=\"posedge rclk\") — find the first diff between two signals.\n"
            "  Use dut.<sig> and ref.<sig> aliases for automatic scope resolution.\n"
            "  Write a one-sentence causal diagnosis (e.g., \"empty=0 because adr_i already changed in write domain before the synchronizer updated\") BEFORE calling replace_block.\n"
        ) if report.get("vcd_available") else ""

        first_prompt = (
            f"{init}\n\n<trace_summary>\n{trace_summary_for_prompt}\n</trace_summary>\n\n"
            f"{vcd_probe_instructions}\n"
            f"{order_prompt}\n\n"
            "Start by checking first_failure and top_diagnosis above. "
            "If the root cause is not obvious, use probe_vcd or probe_compare to inspect internal signals "
            "before making a patch. Write a causal diagnosis BEFORE each replace_block. "
            "Use replace_block(block_id, new_code), or read_rtl_context() and apply_patch_set(patches) "
            "with up to 10 line-range replacements; finally call run_simulation()."
        )
        try:
            (Path(output_dir_per_run) / "debugger_prompt.txt").write_text(first_prompt + "\n", encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
        self._log_message("user", first_prompt)
        await self._agent(Msg("user", first_prompt, role="user"))

        for trial_idx in range(session_max_trials):
            if self._session.is_done:
                break

            # Stop sending continue_prompt when the edit budget is exhausted.
            if self._session.action_calls >= session_max_trials:
                budget_msg = (
                    "Edit budget exhausted (max_trials reached). "
                    "No further RTL edits can be accepted. "
                    "Call generate_response(response=\"...\") with a brief summary of the current state."
                )
                self._log_message("user", budget_msg)
                await self._agent(Msg("user", budget_msg, role="user"))
                break

            self._log_message("user", continue_prompt)
            await self._agent(
                Msg(
                    "user",
                    continue_prompt,
                    role="user",
                )
            )

        with open(rtl_path, "r", encoding="utf-8") as f:
            rtl_code = f.read()
        used = int(getattr(self._session, "action_calls", 0) or 0)
        return self._session.is_done, rtl_code, used
