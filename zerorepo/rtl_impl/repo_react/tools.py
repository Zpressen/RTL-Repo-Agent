from __future__ import annotations

import asyncio
import difflib
import json
from contextlib import nullcontext
import re
import shutil
import hashlib
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Literal

from zerorepo.rtl_impl.debug_agent.bash_tools import CommandResult
from zerorepo.rtl_impl.debug_agent.sim_reviewer import SimReviewer, check_syntax
from zerorepo.rtl_impl.debug_agent.trace_report import (
    _find_clock_signal,
    _resolve_ref_instance as _resolve_ref_instance_static,
    _vcd_time_values,
    _vcd_value_at,
    _vcd_time_range,
    build_assignment_trace_step,
    build_first_divergence_report,
    build_trace_report,
    list_vcd_signals_query,
    resolve_vcd_signal,
    sample_vcd_signals,
)
from zerorepo.rtl_impl.debug_agent.trace_slicer import parse_rtl_assignments, parse_rtl_blocks
from zerorepo.rtl_impl.kg_agent import PlanningContextRetriever
from zerorepo.rtl_impl.kg_agent import kg_query_templates as kg_templates

from zerorepo.rtl_impl.process_observer import observed

from .journal import RepoReActJournal
from .schemas import Patch, RepoReActInput, SimSnapshot

try:
    from vcdvcd import VCDVCD  # type: ignore[import-not-found]
except Exception:  # noqa: BLE001
    VCDVCD = None  # type: ignore[assignment]


_FAIL_TIME_HINT_RE = re.compile(
    r"Hint:\s+Output\s+(?:'[^']+'|[A-Za-z_][A-Za-z0-9_$]*)(?:\s+signal)?\s+has\s+\d+\s+mismatches\.\s+First(?:\s+mismatch\s+occurred)?\s+at\s+time\s+(?P<t>\d+)\b",
    re.IGNORECASE | re.MULTILINE,
)
_FAIL_TIME_FAILED_RE = re.compile(
    r"SIMULATION FAILED - \d+\s+MISMATCHES DETECTED.*FIRST AT TIME\s+(?P<t>\d+)",
    re.IGNORECASE,
)
_SIM_HINT_RE = re.compile(
    r"Hint:\s+Output\s+(?:'(?P<quoted_sig>[^']+)'|(?P<bare_sig>[A-Za-z_][A-Za-z0-9_$]*)(?:\s+signal)?)\s+has\s+(?P<count>\d+)\s+mismatches\.\s+First(?:\s+mismatch\s+occurred)?\s+at\s+time\s+(?P<time>\d+)\b",
    re.IGNORECASE,
)
_SIM_TOTAL_RE = re.compile(r"Mismatches:\s+(?P<count>\d+)\s+in\s+(?P<samples>\d+)\s+samples")


STAGE_ARTIFACTS = {
    "contracts": "contracts.json",
    "modules": "modules.json",
    "repo_skeleton": "repo_skeleton.json",
    "module_skeletons": "module_skeletons.json",
    "spec_blocks": "spec_blocks.json",
    "module_plans": "module_plans.json",
    "stage5_codegen": "stage5_codegen.json",
    "stage6_merge": "stage6_merge.json",
}


def stage_artifact_help() -> dict[str, Any]:
    special = ["global_defines_manifest", "merge_report", "stage6_merge_report"]
    return {
        "valid_artifact_names": sorted([*STAGE_ARTIFACTS.keys(), *special]),
        "common_repo_debug_artifacts": [
            "repo_skeleton",
            "stage5_codegen",
            "stage6_merge",
            "contracts",
            "modules",
        ],
        "usage": 'read_context(kind="stage_artifact", artifact_name="<one_of_valid_artifact_names>")',
    }


def stage_artifact_help_text() -> str:
    return ", ".join(stage_artifact_help()["valid_artifact_names"])


FORBIDDEN_EDIT_PARTS = {
    "spec",
    "oracle",
    "tb",
    "testbench",
    "RealBench",
    "contracts.json",
    "modules.json",
    "repo_skeleton.json",
    "module_plans.json",
    "stage5_codegen.json",
    "stage6_merge.json",
}


def _clip(value: Any, *, max_chars: int = 12000) -> str:
    text = value if isinstance(value, str) else str(value)
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    half = max(1, max_chars // 2)
    return text[:half] + "\n...<snip>...\n" + text[-half:]


def _json_attrs(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {"raw": value}
        return dict(parsed) if isinstance(parsed, dict) else {"raw": parsed}
    return {}


def _signal_leaf(value: str) -> str:
    leaf = str(value or "").strip().split(".")[-1]
    return re.sub(r"\s*\[[^\]]+\]\s*$", "", leaf)


def _expression_mentions_signal(expression: str, signal_name: str) -> bool:
    return bool(re.search(rf"(?<![A-Za-z0-9_$]){re.escape(signal_name)}(?![A-Za-z0-9_$])", expression))


def _simple_connection_signal(expression: str) -> str | None:
    match = re.fullmatch(
        r"\s*([A-Za-z_][A-Za-z0-9_$]*)(?:\s*\[[^\]]+\])?\s*",
        str(expression or ""),
    )
    return match.group(1) if match else None


def _clip_nested_strings(value: Any, *, max_chars: int) -> Any:
    if isinstance(value, str):
        return _clip(value, max_chars=max_chars)
    if isinstance(value, list):
        return [_clip_nested_strings(item, max_chars=max_chars) for item in value]
    if isinstance(value, dict):
        return {key: _clip_nested_strings(item, max_chars=max_chars) for key, item in value.items()}
    return value


def _budget_json_items(items: list[Any], *, max_chars: int) -> tuple[list[Any], bool]:
    if not items:
        return [], False
    per_string = max(200, min(1600, max_chars // max(1, len(items))))
    output: list[Any] = []
    used = 2
    content_clipped = False
    for item in items:
        clipped = _clip_nested_strings(item, max_chars=per_string)
        content_clipped = content_clipped or clipped != item
        size = len(json.dumps(clipped, ensure_ascii=False, default=str))
        if output and used + size > max_chars:
            break
        if not output and size > max_chars:
            clipped = _clip_nested_strings(item, max_chars=max(100, max_chars // 8))
            content_clipped = True
            size = len(json.dumps(clipped, ensure_ascii=False, default=str))
        if not output and size > max_chars:
            identity = {}
            if isinstance(item, dict):
                for key in ("id", "block_id", "block_label", "target", "source_file"):
                    if item.get(key) not in (None, ""):
                        identity[key] = item.get(key)
            clipped = {
                **identity,
                "content_excerpt": _clip(
                    json.dumps(item, ensure_ascii=False, default=str),
                    max_chars=max(100, max_chars - 200),
                ),
            }
            content_clipped = True
            size = len(json.dumps(clipped, ensure_ascii=False, default=str))
        output.append(clipped)
        used += size + 1
        if used >= max_chars:
            break
    return output, content_clipped or len(output) < len(items)


def _extract_first_fail_time(sim_log_json: str) -> int | None:
    try:
        obj = json.loads(sim_log_json)
    except Exception:  # noqa: BLE001
        return None
    stdout = str(obj.get("stdout") or obj.get("diagnostic_excerpt") or "")
    times = [int(m.group("t")) for m in _FAIL_TIME_HINT_RE.finditer(stdout)]
    if times:
        return min(times)
    m = _FAIL_TIME_FAILED_RE.search(stdout)
    if not m:
        return None
    return int(m.group("t"))


def _parse_sim_metrics(sim_log_json: str | None) -> dict[str, Any]:
    if not sim_log_json:
        return {"total_samples_mismatch": None, "samples": None, "per_signal": {}}
    try:
        obj = json.loads(sim_log_json)
    except Exception:  # noqa: BLE001
        obj = {}
    stdout = str(obj.get("stdout") or obj.get("diagnostic_excerpt") or sim_log_json)
    per_signal: dict[str, dict[str, int]] = {}
    for match in _SIM_HINT_RE.finditer(stdout):
        sig = (match.group("quoted_sig") or match.group("bare_sig") or "").strip()
        if not sig:
            continue
        per_signal[sig] = {
            "count": int(match.group("count")),
            "first_time": int(match.group("time")),
        }
    total_match = _SIM_TOTAL_RE.search(stdout)
    return {
        "total_samples_mismatch": int(total_match.group("count")) if total_match else None,
        "samples": int(total_match.group("samples")) if total_match else None,
        "per_signal": per_signal,
    }


def _metric_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_total = before.get("total_samples_mismatch")
    after_total = after.get("total_samples_mismatch")
    per_signal_delta: dict[str, dict[str, Any]] = {}
    before_signals = before.get("per_signal") if isinstance(before.get("per_signal"), dict) else {}
    after_signals = after.get("per_signal") if isinstance(after.get("per_signal"), dict) else {}
    for sig in sorted(set(before_signals) | set(after_signals)):
        b = before_signals.get(sig) or {}
        a = after_signals.get(sig) or {}
        b_count = b.get("count")
        a_count = a.get("count")
        if b_count is None and isinstance(a_count, int):
            b_count = 0
        if a_count is None and isinstance(b_count, int):
            a_count = 0
        direction = "unknown"
        if isinstance(b_count, int) and isinstance(a_count, int):
            if a_count < b_count:
                direction = "improved"
            elif a_count > b_count:
                direction = "regressed"
            else:
                direction = "unchanged"
        per_signal_delta[sig] = {
            "before": b_count,
            "after": a_count,
            "first_time_before": b.get("first_time"),
            "first_time_after": a.get("first_time"),
            "direction": direction,
        }
    return {
        "total_samples_mismatch": (
            f"{before_total} -> {after_total}"
            if before_total is not None or after_total is not None
            else None
        ),
        "per_signal": per_signal_delta,
    }


def _is_tb_metric_signal(sig: str) -> bool:
    return sig.startswith("errors_")


def _promising_mixed_signal_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any] | None:
    before_signals = before.get("per_signal") if isinstance(before.get("per_signal"), dict) else {}
    after_signals = after.get("per_signal") if isinstance(after.get("per_signal"), dict) else {}
    if not before_signals or not after_signals:
        return None
    delta = _metric_delta(before, after)
    per_signal = delta.get("per_signal") if isinstance(delta.get("per_signal"), dict) else {}
    improved: list[dict[str, Any]] = []
    regressed: list[dict[str, Any]] = []
    ignored_tb: list[str] = []
    for sig, item in per_signal.items():
        if _is_tb_metric_signal(str(sig)):
            if item.get("direction") in {"improved", "regressed"}:
                ignored_tb.append(str(sig))
            continue
        before_count = item.get("before")
        after_count = item.get("after")
        if not isinstance(before_count, int) or not isinstance(after_count, int):
            continue
        change = before_count - after_count
        row = {
            "signal": sig,
            "before": before_count,
            "after": after_count,
            "abs_delta": abs(change),
        }
        if change > 0:
            row["reduction_ratio"] = change / max(1, before_count)
            improved.append(row)
        elif change < 0:
            row["growth_ratio"] = (-change) / max(1, before_count)
            regressed.append(row)

    if not improved:
        return None

    improvement_sum = sum(int(item["before"]) - int(item["after"]) for item in improved)
    regression_sum = sum(int(item["after"]) - int(item["before"]) for item in regressed)
    best_improvement = max(improved, key=lambda item: int(item["abs_delta"]))
    if improvement_sum < 10:
        return None
    if float(best_improvement.get("reduction_ratio") or 0.0) < 0.5:
        return None
    if improvement_sum < max(1, regression_sum):
        return None

    return {
        "reason": "promising_mixed_signal_delta",
        "improvement_sum": improvement_sum,
        "regression_sum": regression_sum,
        "improved_signals": improved,
        "regressed_signals": regressed,
        "ignored_tb_metric_signals": ignored_tb,
    }


def _build_patch_acceptance_prompt(payload: dict[str, Any]) -> str:
    return (
        "You are judging whether an RTL repair patch should be kept as the new debugging baseline or rolled back.\n"
        "The authoritative spec and testbench context outrank the patch author's explanation. The fields reason, expected_effect, and preserve_plan are hypotheses, not independent evidence.\n"
        "Lint/syntax failures are handled outside this judge. For functional simulation failures, do not use a single total mismatch counter mechanically.\n"
        "Keep a patch when it is a plausible stepping stone: it fixes the target timing/value, moves the first real failure much later, preserves known good changes, or reveals a missing spec/clear condition that should be repaired next.\n"
        "Rollback a patch when it clearly destroys a protected invariant, only makes the target worse, has no plausible causal progress, or masks the original bug with unrelated behavior.\n"
        "Base the decision on patch_diff, rtl_surrounding_context, authoritative_context, metrics/trace, and recent_repair_ledger. Pay attention to conflicts between aggregate mismatch counters and per-signal deltas. Testbench metric signals named errors_* are less important than real DUT/ref outputs.\n"
        "Return only JSON with this shape:\n"
        "{\"decision\":\"keep|rollback\",\"confidence\":0.0,\"reason\":\"brief\",\"next_focus\":\"brief next repair target if kept\",\"evidence_refs\":[\"brief references to payload evidence\"]}\n\n"
        "<patch_acceptance_payload_json>\n"
        f"{json.dumps(payload, indent=2, ensure_ascii=False)}\n"
        "</patch_acceptance_payload_json>\n"
    )


def _complete_patch_diff(path: Path, patch: Patch, old_text: str) -> str:
    """Build an untruncated unified diff for one replaced patch range."""
    old_lines = old_text.splitlines()
    new_lines = patch.new_text.rstrip("\n").splitlines()
    context = max(len(old_lines), len(new_lines), 1)
    rows = list(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"{path}:before",
            tofile=f"{path}:candidate",
            n=context,
            lineterm="",
        )
    )
    for idx, row in enumerate(rows):
        if row.startswith("@@"):
            rows[idx] = (
                f"@@ -{patch.start_line},{len(old_lines)} "
                f"+{patch.start_line},{len(new_lines)} @@"
            )
            break
    return "\n".join(rows)


def _numbered_lines(lines: list[str], start_index: int, end_index: int) -> str:
    lo = max(0, int(start_index))
    hi = min(len(lines), max(lo, int(end_index)))
    return "\n".join(f"{idx + 1}: {lines[idx]}" for idx in range(lo, hi))


def _patch_surrounding_context(
    path: Path,
    patch: Patch,
    baseline_lines: list[str],
    *,
    context_lines: int = 20,
) -> dict[str, Any]:
    start_idx = max(0, int(patch.start_line) - 1)
    end_idx = min(len(baseline_lines), int(patch.end_line))
    window = max(0, int(context_lines))
    return {
        "path": str(path),
        "target_start_line": int(patch.start_line),
        "target_end_line": int(patch.end_line),
        "context_lines": window,
        "above": _numbered_lines(baseline_lines, start_idx - window, start_idx),
        "below": _numbered_lines(baseline_lines, end_idx, end_idx + window),
    }


def _bounded_authoritative_excerpt(
    text: str,
    *,
    keywords: list[str],
    max_chars: int = 6000,
    context_lines: int = 3,
) -> dict[str, Any]:
    """Return full short text or deterministic keyword windows for long sources."""
    value = str(text or "")
    limit = max(1, int(max_chars))
    if len(value) <= limit:
        return {"content": value, "truncated": False, "selection": "full"}

    lines = value.splitlines()
    normalized: list[str] = []
    seen_keywords: set[str] = set()
    for keyword in keywords:
        item = str(keyword or "").strip().lower()
        if not item or item in seen_keywords:
            continue
        seen_keywords.add(item)
        normalized.append(item)

    hit_indexes: set[int] = set()
    radius = max(0, int(context_lines))
    for keyword in normalized:
        identifier_pattern = None
        if re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_$]*", keyword):
            identifier_pattern = re.compile(
                rf"(?<![a-zA-Z0-9_$]){re.escape(keyword)}(?![a-zA-Z0-9_$])",
                re.IGNORECASE,
            )
        for idx, line in enumerate(lines):
            matched = bool(identifier_pattern.search(line)) if identifier_pattern else keyword in line.lower()
            if not matched:
                continue
            hit_indexes.update(range(max(0, idx - radius), min(len(lines), idx + radius + 1)))

    selection = "keyword_windows" if hit_indexes else "head_tail"
    if hit_indexes:
        indexes = sorted(hit_indexes)
    else:
        edge_count = min(40, max(1, len(lines) // 2))
        indexes = sorted(set(range(edge_count)) | set(range(max(0, len(lines) - edge_count), len(lines))))

    rendered: list[str] = []
    used = 0
    previous: int | None = None
    for idx in indexes:
        prefix = "...\n" if previous is not None and idx > previous + 1 else ""
        row = f"{idx + 1}: {lines[idx]}\n"
        addition = prefix + row
        if used + len(addition) > limit:
            remaining = limit - used
            if remaining > 0:
                rendered.append(addition[:remaining])
            break
        rendered.append(addition)
        used += len(addition)
        previous = idx
    return {"content": "".join(rendered).rstrip("\n"), "truncated": True, "selection": selection}


def _summarize_command_json(command_json: str, *, max_chars: int = 4000) -> str:
    try:
        obj = CommandResult.model_validate_json(command_json)
        text = "\n".join(part for part in [obj.stdout, obj.stderr] if part)
    except Exception:  # noqa: BLE001
        text = command_json
    interesting = []
    for line in text.splitlines():
        if (
            "SIMULATION" in line
            or "Mismatches:" in line
            or "Hint:" in line
            or "%Error" in line
            or "Timeout" in line
        ):
            interesting.append(line)
    return _clip("\n".join(interesting).strip() or text.strip(), max_chars=max_chars)


def _extract_syntax_errors(command_json: str, *, limit: int = 20) -> list[dict[str, Any]]:
    """Extract structured Verilator errors while retaining raw output as fallback."""
    try:
        obj = CommandResult.model_validate_json(command_json)
        text = "\n".join(part for part in [obj.stdout, obj.stderr] if part)
    except Exception:  # noqa: BLE001
        text = str(command_json or "")
    pattern = re.compile(
        r"^%?Error(?:-[^:]+)?:\s+(?P<path>.*?):(?P<line>\d+):(?P<column>\d+):\s*(?P<message>.*)$",
        re.MULTILINE,
    )
    errors: list[dict[str, Any]] = []
    seen: set[tuple[str, int, int, str]] = set()
    for match in pattern.finditer(text):
        item = (
            match.group("path").strip(),
            int(match.group("line")),
            int(match.group("column")),
            match.group("message").strip(),
        )
        if item in seen:
            continue
        seen.add(item)
        errors.append({"path": item[0], "line": item[1], "column": item[2], "message": item[3]})
        if len(errors) >= max(1, int(limit)):
            break
    return errors


@dataclass
class RepoReActToolState:
    input: RepoReActInput
    sim_reviewer: SimReviewer
    journal: RepoReActJournal
    kg_service: Any | None = None
    model_cfg: Any | None = None
    logger: Any | None = None
    last_sim: SimSnapshot = field(default_factory=SimSnapshot)
    last_sim_output: str = ""
    action_calls: int = 0
    patch_attempt_id: int = 0
    syntax_candidates: dict[str, dict[str, Any]] = field(default_factory=dict)
    neutral_kept: int = 0
    observed_rtl: bool = False
    observed_trace_or_sim: bool = False
    observed_tb_or_spec_or_kg: bool = False
    observed_spec_or_stage: bool = False
    observed_stage_artifact: bool = False
    observed_real_divergence: bool = False
    last_trace_summary: dict[str, Any] = field(default_factory=dict)
    last_divergence_summary: dict[str, Any] = field(default_factory=dict)
    last_signal_trace: dict[str, Any] = field(default_factory=dict)
    last_signal_trace_action_calls: int = -1
    pending_post_patch_trace: dict[str, Any] = field(default_factory=dict)


class RepoReActTools:
    def _scoped_syntax(self,*args,**kwargs):
        factory=getattr(self.state.sim_reviewer,'verification_context',None)
        with factory() if callable(factory) else nullcontext():
            return check_syntax(*args,**kwargs)

    def _review_current(self):
        from zerorepo.rtl_impl.debug_agent.system_debug_runner import bind_reviewer
        reviewer=bind_reviewer(self.state.sim_reviewer,self.state.input.rtl_root or self.state.input.rtl_path.parent,self.state.input.debug_workdir)
        return reviewer.review()

    def __init__(self, state: RepoReActToolState) -> None:
        self.state = state

    def _run_async(self, coroutine: Any) -> Any:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coroutine)
        import threading

        result: dict[str, Any] = {}

        def runner() -> None:
            try:
                result["value"] = asyncio.run(coroutine)
            except BaseException as exc:  # noqa: BLE001
                result["error"] = exc

        thread = threading.Thread(target=runner)
        thread.start()
        thread.join()
        if "error" in result:
            raise result["error"]
        return result.get("value")

    def _parse_acceptance_decision(self, text: str) -> dict[str, Any] | None:
        try:
            start = text.find("{")
            end = text.rfind("}")
            payload = json.loads(text[start : end + 1] if start >= 0 and end >= start else text)
        except Exception:  # noqa: BLE001
            return None
        if not isinstance(payload, dict):
            return None
        decision = str(payload.get("decision") or "").strip().lower()
        if decision not in {"keep", "rollback"}:
            return None
        out = {
            "decision": decision,
            "confidence": payload.get("confidence"),
            "reason": str(payload.get("reason") or ""),
            "next_focus": str(payload.get("next_focus") or ""),
        }
        evidence_refs = payload.get("evidence_refs")
        if isinstance(evidence_refs, list):
            out["evidence_refs"] = [str(item) for item in evidence_refs if str(item).strip()][:12]
        return out

    def _llm_patch_acceptance_decision(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        cfg = self.state.model_cfg
        if cfg is None or not getattr(cfg, "api_key", ""):
            return None
        try:
            from agentscope.memory import InMemoryMemory
            from agentscope.message import Msg
            from zerorepo.rtl_impl.debug_agent.agents import SafeReActAgent, clear_memory_safely, close_model_safely
            from zerorepo.rtl_impl.debug_agent.model import make_formatter, make_openai_model
        except Exception:  # noqa: BLE001
            return None

        agent = SafeReActAgent(
            name="RepoReActPatchAcceptanceJudge",
            sys_prompt="You decide whether to keep or rollback an RTL patch after functional simulation. Return JSON only.",
            model=make_openai_model(cfg),
            formatter=make_formatter(getattr(cfg, "model", None), getattr(cfg, "base_url", None)),
            memory=InMemoryMemory(),
            max_iters=2,
        )

        async def run_agent_once() -> Any:
            try:
                return await agent(Msg("user", _build_patch_acceptance_prompt(payload), role="user"))
            finally:
                await close_model_safely(agent)

        try:
            text = self._run_async(run_agent_once()).get_text_content() or ""
        except Exception as exc:  # noqa: BLE001
            if self.state.logger is not None:
                self.state.logger.debug("Patch acceptance judge failed, using fallback: %s", exc)
            return None
        finally:
            try:
                clear_memory_safely(agent)
            except Exception:  # noqa: BLE001
                pass
        return self._parse_acceptance_decision(text)

    def _fallback_acceptance_decision(
        self,
        *,
        before_sim: SimSnapshot,
        first_fail: int | None,
        before_metrics: dict[str, Any],
        after_metrics: dict[str, Any],
        mixed_acceptance: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if mixed_acceptance:
            return {
                "decision": "keep",
                "confidence": 0.55,
                "reason": "Fallback kept patch because real per-signal improvements outweigh real per-signal regressions.",
                "next_focus": "Repair regressed signals from mixed_signal_delta.",
                "source": "promising_mixed_signal_delta",
            }
        if before_sim.first_fail_time is not None and first_fail is not None:
            moved_by = int(first_fail) - int(before_sim.first_fail_time)
            if moved_by >= 100:
                return {
                    "decision": "keep",
                    "confidence": 0.52,
                    "reason": f"Fallback kept patch because first failure moved later by {moved_by} time units.",
                    "next_focus": "Find the new later failure/clear condition before broad rollback.",
                    "source": "script_fallback_first_fail_moved_much_later",
                }
        delta = _metric_delta(before_metrics, after_metrics)
        per_signal = delta.get("per_signal") if isinstance(delta.get("per_signal"), dict) else {}
        real_directions = [
            item.get("direction")
            for sig, item in per_signal.items()
            if not _is_tb_metric_signal(str(sig)) and item.get("direction") != "unchanged"
        ]
        before_total = before_metrics.get("total_samples_mismatch")
        after_total = after_metrics.get("total_samples_mismatch")
        if (
            isinstance(before_total, int)
            and isinstance(after_total, int)
            and after_total < before_total
            and "regressed" not in real_directions
        ):
            return {
                "decision": "keep",
                "confidence": 0.5,
                "reason": "Fallback kept patch because total sample mismatches improved and no real output signal regressed.",
                "next_focus": "Continue from the improved baseline.",
                "source": "script_fallback_clean_total_improvement",
            }
        return {
            "decision": "rollback",
            "confidence": 0.5,
            "reason": "Fallback rolled back because no LLM judge was available and no conservative keep heuristic matched.",
            "next_focus": "Retry with stronger evidence or enable model-based acceptance judging.",
            "source": "script_fallback_conservative_rollback",
        }

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def _allowed_read_roots(self) -> list[Path]:
        inp = self.state.input
        roots = [
            inp.debug_workdir,
            inp.workspace_root,
            inp.output_root,
            inp.repo_root,
            inp.rtl_root,
            inp.verify_dir,
        ]
        return [p.resolve() for p in roots if p is not None]

    def _is_under(self, path: Path, root: Path) -> bool:
        try:
            path.resolve().relative_to(root.resolve())
            return True
        except ValueError:
            return False

    def _resolve_read_path(self, raw_path: str | None) -> Path | None:
        if not raw_path:
            return None
        path = Path(raw_path).expanduser()
        if path.is_absolute():
            resolved = path.resolve()
            if any(self._is_under(resolved, root) for root in self._allowed_read_roots()):
                return resolved
            return None
        candidates = [
            self.state.input.debug_workdir / path,
            (self.state.input.rtl_root / path) if self.state.input.rtl_root else None,
            self.state.input.workspace_root / path,
            (self.state.input.output_root / path) if self.state.input.output_root else None,
            (self.state.input.repo_root / path) if self.state.input.repo_root else None,
        ]
        for candidate in candidates:
            if candidate is None:
                continue
            resolved = candidate.resolve()
            if resolved.exists() and any(self._is_under(resolved, root) for root in self._allowed_read_roots()):
                return resolved
        fallback = (self.state.input.debug_workdir / path).resolve()
        if any(self._is_under(fallback, root) for root in self._allowed_read_roots()):
            return fallback
        return None

    def _resolve_edit_path(self, raw_path: str) -> tuple[Path | None, str]:
        path = self._resolve_read_path(raw_path)
        if path is None:
            return None, f"Path is outside allowed roots or cannot be resolved: {raw_path}"
        inp = self.state.input
        rtl = inp.rtl_path.resolve()
        merged = inp.merged_file.resolve()
        if inp.repair_scope == "repo":
            rtl_root = (inp.rtl_root or inp.rtl_path.parent).resolve()
            if self._is_under(path, rtl_root):
                return path.resolve(), ""
            if path == merged:
                mapped = (rtl_root / merged.name).resolve()
                if mapped.is_file():
                    return mapped, f"Mapped merged RTL path {merged} to generated repo RTL {mapped} for verified patching."
            return None, (
                "RepoReAct repo-scope patches may only edit generated RTL under "
                f"{rtl_root}. Requested path: {path}"
            )
        if path == rtl:
            return rtl, ""
        if path == merged:
            return rtl, f"Mapped merged RTL path {merged} to current debug RTL {rtl} for verified patching."
        if path.name == rtl.name and self._is_under(path, inp.debug_workdir):
            return rtl, f"Mapped debug RTL-like path {path} to {rtl}."
        return None, (
            "RepoReAct v1 only patches the current module debug RTL. "
            f"Requested path: {path}"
        )

    def _authoritative_context_for_acceptance(self, keywords: list[str]) -> dict[str, Any]:
        inp = self.state.input
        spec_chunks: list[str] = []
        spec_sources: list[str] = []
        seen_paths: set[Path] = set()
        for raw_path in [inp.spec_source_path, *inp.spec_paths]:
            if not raw_path:
                continue
            resolved = self._resolve_read_path(raw_path)
            if resolved is None or not resolved.is_file() or resolved in seen_paths:
                continue
            seen_paths.add(resolved)
            try:
                spec_body = resolved.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            spec_sources.append(str(resolved))
            spec_chunks.append(f"// spec source: {resolved}\n" + spec_body)
        if spec_chunks:
            spec_text = "\n\n".join(spec_chunks)
            spec_source: str | list[str] = spec_sources
        else:
            spec_text = inp.spec_text
            spec_source = "spec_text" if spec_text else "unavailable"
        spec_excerpt = _bounded_authoritative_excerpt(
            spec_text,
            keywords=keywords,
            max_chars=6000,
        )
        spec_context = {
            "available": bool(spec_text),
            "source": spec_source,
            **spec_excerpt,
        }

        tb_path = inp.debug_workdir / "tb.sv"
        tb_available = False
        if tb_path.is_file():
            try:
                tb_text = tb_path.read_text(encoding="utf-8", errors="replace")
                tb_available = True
            except OSError:
                tb_text = ""
        else:
            tb_text = ""
        if tb_available:
            tb_excerpt = _bounded_authoritative_excerpt(
                tb_text,
                keywords=keywords,
                max_chars=6000,
            )
            tb_context = {
                "available": tb_available,
                "path": str(tb_path),
                **tb_excerpt,
            }
        else:
            tb_context = {
                "available": False,
                "path": str(tb_path),
                "content": "",
                "truncated": False,
                "selection": "unavailable",
            }
        return {"spec": spec_context, "testbench": tb_context}

    def _forbidden_edit_reason(self, path: Path) -> str:
        parts = set(path.parts)
        name = path.name
        lowered = str(path).lower()
        for token in FORBIDDEN_EDIT_PARTS:
            if token in parts or token == name:
                return f"Editing forbidden path token '{token}' is not allowed: {path}"
            # Only match the token as a whole path segment, not as a substring
            # inside a longer directory name (e.g. "spec" in "aes_unified_functional_spec").
            token_lower = token.lower()
            if f"/{token_lower}/" in lowered or lowered.startswith(f"{token_lower}/") or lowered.endswith(f"/{token_lower}"):
                return f"Editing forbidden path token '{token}' is not allowed: {path}"
        if path.suffix.lower() not in {".v", ".sv"}:
            return f"Only .v/.sv RTL files may be patched, got: {path}"
        return ""

    def _current_rtl_hash(self) -> str:
        try:
            return hashlib.sha256(self.state.input.rtl_path.read_bytes()).hexdigest()
        except OSError:
            return ""

    def _resolve_long_term_memory_path(self, raw_path: str) -> tuple[Path | None, str]:
        memory_root = (self.state.input.workspace_root / "rtl_memory").resolve()
        path = Path(str(raw_path or "")).expanduser()
        if not str(path):
            return None, "Memory path is required."
        resolved = path.resolve() if path.is_absolute() else (memory_root / path).resolve()
        try:
            rel = resolved.relative_to(memory_root)
        except ValueError:
            return None, f"Path is outside rtl_memory root: {raw_path}"
        if resolved.suffix.lower() != ".md":
            return None, f"Only .md long-term memory files may be read: {raw_path}"
        if not resolved.is_file():
            return None, f"Long-term memory file not found: {raw_path}"
        if rel.parts and rel.parts[0] not in {"cases", "patterns", "corrections", "rules"}:
            return None, f"Unsupported long-term memory directory: {rel.parts[0]}"
        return resolved, ""

    def read_long_term_memory(self, path: str, max_chars: int = 8000) -> dict[str, Any]:
        resolved, error = self._resolve_long_term_memory_path(path)
        if resolved is None:
            return {"status": "error", "path": path, "error": error}
        memory_root = (self.state.input.workspace_root / "rtl_memory").resolve()
        text = resolved.read_text(encoding="utf-8", errors="replace")
        rel = resolved.relative_to(memory_root).as_posix()
        return {
            "status": "ok",
            "path": rel,
            "absolute_path": str(resolved),
            "content": _clip(text, max_chars=max(1000, int(max_chars))),
            "truncated": len(text) > max(1000, int(max_chars)),
        }

    def _read_jsonl(self, name: str) -> list[dict[str, Any]]:
        path = self.state.journal.root / name
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                obj = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            if isinstance(obj, dict):
                rows.append(obj)
        return rows

    def _record_patch_entry(self, entry: dict[str, Any]) -> None:
        self.state.journal.append_jsonl("patch_journal.jsonl", entry)
        self.persist_memory_snapshot()
        try:
            from zerorepo.rtl_impl.rtl_memory import RTLMemoryDistiller

            RTLMemoryDistiller(
                self.state.input.workspace_root,
                logger=self.state.logger,
            ).distill_patch_entry(
                module=self.state.input.module_name,
                entry=entry,
                debug_workdir=self.state.input.debug_workdir,
                repo_react_root=self.state.journal.root,
            )
        except Exception as exc:  # noqa: BLE001
            if self.state.logger is not None:
                self.state.logger.warning("Failed to distill patch entry into RTL memory: %s", exc)

    def _summarize_code(self, text: str, *, max_chars: int = 180) -> str:
        compact = " ".join(line.strip() for line in str(text).splitlines() if line.strip())
        return _clip(compact, max_chars=max_chars)

    def _changed_signals_for_patch(self, text: str) -> list[str]:
        writes: set[str] = set()
        for m in re.finditer(r"\b([a-zA-Z_][a-zA-Z0-9_$]*)\b\s*(?:\[[^\]]+\])?\s*<=", text):
            writes.add(m.group(1))
        for m in re.finditer(r"\b(?:assign\s+)?([a-zA-Z_][a-zA-Z0-9_$]*)\b\s*(?:\[[^\]]+\])?\s*(?<![=!<>])=(?![=])", text):
            lhs = m.group(1)
            if lhs not in {"if", "for", "while", "case"}:
                writes.add(lhs)
        return sorted(writes)

    def _classify_effect(
        self,
        before: SimSnapshot,
        result: dict[str, Any],
        before_metrics: dict[str, Any] | None = None,
        after_metrics: dict[str, Any] | None = None,
    ) -> str:
        status = str(result.get("status") or "")
        if status in {"syntax_retry_required", "syntax_retry_exhausted"}:
            return "syntax_failed"
        if status == "pass" or (result.get("is_pass") and int(result.get("mismatch_count") or 0) == 0):
            return "passed"
        if status == "improved":
            return "improved"
        acceptance = result.get("acceptance_decision") if isinstance(result.get("acceptance_decision"), dict) else {}
        if acceptance.get("decision") == "keep":
            return "improved"
        if status == "rollback":
            reason = str(result.get("rollback_reason") or "")
            if "lint" in reason:
                return "syntax_failed"
            if "regress" in reason:
                return "regressed"
            return "rejected"
        if status == "rejected":
            return "rejected"
        after_mismatches = int(result.get("mismatch_count") or before.mismatch_count)
        after_fail_time = result.get("first_fail_time")
        if after_mismatches < int(before.mismatch_count):
            return "improved"
        if isinstance(before.first_fail_time, int) and isinstance(after_fail_time, int):
            if after_fail_time > before.first_fail_time:
                return "improved"
            if after_fail_time < before.first_fail_time:
                return "regressed"
        if after_mismatches > int(before.mismatch_count):
            return "regressed"
        # 逐信号 delta 检查：当全局 mismatch 总量不变时，
        # 若某个信号的 mismatch 减少且没有信号恶化，仍应算作 improved。
        # 这避免了「修复了信号 A 但被信号 B 的 mismatch 淹没 → 误判 neutral」。
        if before_metrics and after_metrics:
            delta = _metric_delta(before_metrics, after_metrics)
            per_signal = delta.get("per_signal") if isinstance(delta, dict) else {}
            if per_signal:
                directions = {v.get("direction") for v in per_signal.values()}
                if "improved" in directions and "regressed" not in directions:
                    return "improved"
        return "neutral"

    def _lesson_for_effect(self, effect: str, result: dict[str, Any]) -> str:
        if effect == "passed":
            return "Patch fixed all observed mismatches."
        if effect == "improved":
            acceptance = result.get("acceptance_decision") if isinstance(result.get("acceptance_decision"), dict) else {}
            if acceptance.get("decision") == "keep":
                return f"Patch was kept by acceptance judge: {acceptance.get('reason') or 'continue from this functional stepping stone.'}"
            if result.get("acceptance_reason") == "promising_mixed_signal_delta":
                return "Patch had higher total mismatch but strong per-signal improvement; keep this direction and repair regressed signals next."
            return "Patch improved mismatch count or first fail time; continue from this direction."
        if effect == "neutral":
            return "Patch was accepted but did not clearly improve tracked metrics."
        if effect == "regressed":
            return "Patch worsened mismatch count or first fail time and was rolled back."
        if effect == "syntax_failed":
            return "Patch failed lint and was rolled back; fix syntax before retrying this idea."
        return str(result.get("reason") or result.get("rollback_reason") or "Patch was rejected or rolled back.")

    def _recent_repair_entries(self, limit: int = 5) -> list[dict[str, Any]]:
        rows = self._read_jsonl("patch_journal.jsonl")
        return rows[-max(1, int(limit)) :]

    def _slim_repair_entry(self, row: dict[str, Any]) -> dict[str, Any]:
        changed_signals = row.get("changed_signals")
        if not isinstance(changed_signals, list):
            changed_signals = []
        return {
            "step": row.get("step"),
            "action_type": row.get("action_type"),
            "block_id": row.get("block_id"),
            "effect": row.get("effect"),
            "lesson": _clip(str(row.get("lesson") or ""), max_chars=500),
            "patch_summary": _clip(str(row.get("patch_summary") or ""), max_chars=500),
            "before": row.get("before") if isinstance(row.get("before"), dict) else {},
            "after": row.get("after") if isinstance(row.get("after"), dict) else {},
            "metric_delta": self._row_metric_delta(row),
            "changed_signals": changed_signals[:12],
            "target": row.get("target") if isinstance(row.get("target"), dict) else {},
        }

    def _recent_repair_entries_slim(self, limit: int = 3) -> list[dict[str, Any]]:
        rows = self._recent_repair_entries(limit=limit)
        return [self._slim_repair_entry(row) for row in rows]

    def _directions_by_effect(self, effects: set[str], limit: int = 5) -> list[dict[str, Any]]:
        directions: list[dict[str, Any]] = []
        for row in reversed(self._read_jsonl("patch_journal.jsonl")):
            effect = str(row.get("effect") or (row.get("result") or {}).get("effect") or "")
            if effect not in effects:
                continue
            if self._is_non_repair_rejection(row):
                continue
            directions.append(
                {
                    "step": row.get("step"),
                    "effect": effect,
                    "hypothesis": row.get("hypothesis"),
                    "lesson": row.get("lesson"),
                    "changed_signals": row.get("changed_signals") or [],
                    "target": row.get("target"),
                    "patch_summary": row.get("patch_summary"),
                }
            )
            if len(directions) >= max(1, int(limit)):
                break
        return list(reversed(directions))

    def _recent_edited_ranges(self, limit: int = 5) -> list[dict[str, Any]]:
        ranges: list[dict[str, Any]] = []
        for row in reversed(self._read_jsonl("patch_journal.jsonl")):
            if self._is_non_repair_rejection(row):
                continue
            target = row.get("target")
            if isinstance(target, dict) and any(target.get(k) is not None for k in ("path", "start_line", "end_line", "block_id")):
                ranges.append(
                    {
                        "step": row.get("step"),
                        "path": target.get("path"),
                        "start_line": target.get("start_line"),
                        "end_line": target.get("end_line"),
                        "effect": row.get("effect"),
                        "changed_signals": row.get("changed_signals") or [],
                    }
                )
            if len(ranges) >= max(1, int(limit)):
                break
        return list(reversed(ranges))

    def _is_non_repair_rejection(self, row: dict[str, Any]) -> bool:
        result = row.get("result") if isinstance(row.get("result"), dict) else {}
        text = " ".join(
            str(item or "")
            for item in (
                row.get("patch_summary"),
                row.get("lesson"),
                result.get("reason") if isinstance(result, dict) else "",
                result.get("rollback_reason") if isinstance(result, dict) else "",
            )
        ).lower()
        return any(
            marker in text
            for marker in (
                "repair action budget exhausted",
                "observation_budget_exhausted",
                "payload",
                "non-empty",
                "has not been read",
                "inspect original spec or stage",
                "observe real or edge-active",
                "patch blocked",
            )
        )

    def _row_metric_delta(self, row: dict[str, Any]) -> dict[str, Any]:
        if isinstance(row.get("metric_delta"), dict):
            return row["metric_delta"]
        before_metrics = row.get("before_metrics") if isinstance(row.get("before_metrics"), dict) else {}
        after_metrics = row.get("after_metrics") if isinstance(row.get("after_metrics"), dict) else {}
        if before_metrics or after_metrics:
            return _metric_delta(before_metrics, after_metrics)
        before = row.get("before") if isinstance(row.get("before"), dict) else {}
        after = row.get("after") if isinstance(row.get("after"), dict) else {}
        before_count = before.get("mismatch_count")
        after_count = after.get("mismatch_count")
        first_before = before.get("first_fail_time")
        first_after = after.get("first_fail_time")
        return {
            "total_mismatch": (
                f"{before_count} -> {after_count}"
                if before_count is not None or after_count is not None
                else None
            ),
            "first_fail_time": (
                f"{first_before} -> {first_after}"
                if first_before is not None or first_after is not None
                else None
            ),
            "per_signal": {},
        }

    def _protected_invariants_for_row(self, row: dict[str, Any]) -> list[str]:
        effect = str(row.get("effect") or "")
        if effect not in {"improved", "passed"}:
            return []
        text = " ".join(
            str(item or "")
            for item in (
                row.get("hypothesis"),
                row.get("patch_summary"),
                row.get("lesson"),
                row.get("changed_signals"),
                row.get("target"),
            )
        ).lower()
        invariants: list[str] = []
        if "ack_out" in text and "setup" in text:
            invariants.append("Do not clear ack_out in SETUP; preserve ack_out hold-through-SETUP behavior.")
        if "status_reg" in text and ("6" in text or "5" in text or "mirror" in text or "leak" in text):
            invariants.append("Do not reintroduce STATUS_REG[6:5] mirror/leak from internal status.")
        if "req_out" in text and "timeout" in text:
            invariants.append("Preserve timeout req_out behavior from improved timeout/handshake patch.")
        if "watchdog" in text or "timeout_reg" in text:
            invariants.append("Preserve corrected watchdog timeout boundary behavior.")
        if "new_cmd" in text or "new_cmd_sample" in text:
            invariants.append("Preserve New_CMD sampling/reset-release timing behavior.")
        if "normal_int_reg" in text and ("card" in text or "absent" in text):
            invariants.append("Preserve NORMAL_INT_REG card-present/card-absent visible behavior.")
        if not invariants:
            signals = [str(s) for s in (row.get("changed_signals") or []) if s]
            if signals:
                invariants.append(f"Preserve improved behavior for signals: {', '.join(signals[:8])}.")
        return invariants

    def _protected_invariants(self, limit: int = 12) -> list[str]:
        seen: set[str] = set()
        invariants: list[str] = []
        for row in self._read_jsonl("patch_journal.jsonl"):
            for invariant in self._protected_invariants_for_row(row):
                if invariant not in seen:
                    seen.add(invariant)
                    invariants.append(invariant)
                if len(invariants) >= limit:
                    return invariants
        return invariants

    def _repair_ledger(self, limit: int = 10) -> list[dict[str, Any]]:
        ledger: list[dict[str, Any]] = []
        for row in self._read_jsonl("patch_journal.jsonl"):
            if self._is_non_repair_rejection(row):
                continue
            if str(row.get("effect") or "") == "syntax_failed":
                continue
            target = row.get("target") if isinstance(row.get("target"), dict) else {}
            if not target and str(row.get("effect")) == "rejected":
                continue
            ledger.append(
                {
                    "step": row.get("step"),
                    "action_type": row.get("action_type"),
                    "block_id": row.get("block_id"),
                    "target": target,
                    "affected_signals": row.get("changed_signals") or [],
                    "effect": row.get("effect"),
                    "metric_delta": self._row_metric_delta(row),
                    "lesson": row.get("lesson"),
                    "hypothesis": _clip(str(row.get("hypothesis") or ""), max_chars=800),
                    "patch_summary": _clip(str(row.get("patch_summary") or ""), max_chars=500),
                    "protect": self._protected_invariants_for_row(row),
                }
            )
        return ledger[-max(1, int(limit)) :]

    def _unsafe_directions(self, limit: int = 8) -> list[str]:
        directions: list[str] = []
        seen: set[str] = set()
        for row in self._read_jsonl("patch_journal.jsonl"):
            if self._is_non_repair_rejection(row):
                continue
            effect = str(row.get("effect") or "")
            if effect != "regressed":
                continue
            delta = self._row_metric_delta(row)
            total = delta.get("total_mismatch") or delta.get("total_samples_mismatch")
            action = str(row.get("action_type") or "patch")
            block_id = row.get("block_id")
            summary = _clip(str(row.get("patch_summary") or row.get("hypothesis") or ""), max_chars=180)
            if action == "replace_block" and block_id:
                text = (
                    f"replace_block of {block_id} regressed mismatch {total}; "
                    "do not repeat this block-level edit without new evidence and a preservation plan."
                )
            else:
                text = f"Regressed direction at step {row.get('step')} changed {row.get('changed_signals') or []}: {summary}"
            if text not in seen:
                seen.add(text)
                directions.append(text)
            if len(directions) >= max(1, int(limit)):
                break
        return directions

    def _high_coupling_blocks(self, limit: int = 8) -> list[dict[str, Any]]:
        blocks: dict[str, dict[str, Any]] = {}
        for row in self._read_jsonl("patch_journal.jsonl"):
            target = row.get("target") if isinstance(row.get("target"), dict) else {}
            block_id = row.get("block_id") or target.get("block_id")
            signals = row.get("changed_signals") or []
            if not block_id or len(signals) < 6:
                continue
            entry = blocks.setdefault(
                str(block_id),
                {
                    "block_id": str(block_id),
                    "signals": set(),
                    "regressed_replace": False,
                    "lessons": [],
                    "target": target,
                },
            )
            entry["signals"].update(str(sig) for sig in signals)
            if row.get("action_type") == "replace_block" and row.get("effect") == "regressed":
                entry["regressed_replace"] = True
            if row.get("lesson"):
                entry["lessons"].append(row.get("lesson"))
        out: list[dict[str, Any]] = []
        for entry in blocks.values():
            out.append(
                {
                    "block_id": entry["block_id"],
                    "signals": sorted(entry["signals"])[:20],
                    "regressed_replace": bool(entry["regressed_replace"]),
                    "target": entry["target"],
                    "guidance": "Choose edit scope from the current diagnosis; for high-coupling edits, preserve already-improved invariants.",
                    "lessons": entry["lessons"][-3:],
                }
            )
        return out[: max(1, int(limit))]

    def _next_local_target(self, protected_invariants: list[str]) -> dict[str, Any]:
        div = self.state.last_divergence_summary or {}
        first = div.get("first_divergence") if isinstance(div.get("first_divergence"), dict) else {}
        suspect = div.get("suspect") if isinstance(div.get("suspect"), dict) else {}
        driver_blocks = suspect.get("driver_blocks") if isinstance(suspect.get("driver_blocks"), list) else []
        signal = first.get("signal")
        sampling_mode = first.get("sampling_mode") or div.get("sampling_mode")
        status = div.get("status")
        if status == "stable_values_match_but_tb_edge_mismatch":
            symptom = "DUT/ref match after settling but mismatch at testbench edge-active sampling."
        elif signal:
            symptom = "DUT/ref stable value mismatch."
        else:
            symptom = "No current DUT/ref divergence target available."
        return {
            "signal": signal,
            "time": first.get("time"),
            "sampling_mode": sampling_mode,
            "status": status,
            "classification": first.get("classification"),
            "ref": first.get("ref"),
            "dut": first.get("dut"),
            "symptom": symptom,
            "suspect_blocks": [b.get("id") for b in driver_blocks if isinstance(b, dict) and b.get("id")],
            "must_preserve": protected_invariants[:8],
        }

    def _protected_signal_names(self, invariants: list[str]) -> set[str]:
        names: set[str] = set()
        known = {
            "STATUS_REG",
            "RESP_1_REG",
            "ERR_INT_REG",
            "NORMAL_INT_REG",
            "settings",
            "go_idle_o",
            "cmd_out",
            "req_out",
            "ack_out",
            "Watchdog_Cnt",
            "New_CMD_sample",
            "state",
        }
        for invariant in invariants:
            for name in known:
                if name.lower() in invariant.lower():
                    names.add(name)
        return names

    def _patch_requires_preserve_plan(
        self,
        *,
        action_type: str,
        changed_signals: list[str],
        block_id: str | None,
    ) -> tuple[bool, list[str]]:
        invariants = self._protected_invariants()
        protected_names = self._protected_signal_names(invariants)
        changed = set(changed_signals)
        relevant = [inv for inv in invariants if any(name.lower() in inv.lower() for name in changed | protected_names)]
        high_blocks = {
            str(item.get("block_id"))
            for item in self._high_coupling_blocks(limit=20)
            if item.get("block_id")
        }
        if action_type == "replace_block" and block_id in high_blocks:
            if not relevant:
                relevant = invariants[:8]
            return True, relevant
        if action_type == "replace_block" and len(changed_signals) >= 6:
            return True, relevant or invariants[:8] or [
                "High-coupling block replacement touches many signals; preserve already-improved handshake/status/timing behavior."
            ]
        if changed & protected_names:
            return True, relevant or invariants[:8]
        return False, []

    def _causal_memory_brief(self, snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
        snapshot = snapshot or {}
        latest_trace = snapshot.get("latest_trace_summary") or self.state.last_trace_summary or {}
        last_div = snapshot.get("last_divergence_summary") or self.state.last_divergence_summary or {}
        protected = self._protected_invariants()
        return {
            "schema": "repo_react_memory_brief.v1",
            "module": self.state.input.module_name,
            "current_rtl_hash": self._current_rtl_hash(),
            "last_sim": self.state.last_sim.model_dump(),
            "latest_trace_summary": {
                "fail_time": latest_trace.get("fail_time"),
                "total_mismatches": latest_trace.get("total_mismatches"),
                "root_failure": latest_trace.get("root_failure"),
                "edge_active_failure": latest_trace.get("edge_active_failure"),
                "required_next_tool": latest_trace.get("required_next_tool"),
                "suspect_blocks": latest_trace.get("suspect_blocks"),
                "timing_hints": latest_trace.get("timing_hints"),
                "alignment_diagnosis": latest_trace.get("alignment_diagnosis"),
            },
            "last_divergence_summary": {
                "status": last_div.get("status"),
                "sampling_mode": last_div.get("sampling_mode"),
                "edge": last_div.get("edge"),
                "driver_assignment_kind": last_div.get("driver_assignment_kind"),
                "first_divergence": last_div.get("first_divergence"),
                "candidate_signals": last_div.get("candidate_signals"),
                "ignored_tb_metrics": last_div.get("ignored_tb_metrics"),
                "suspect": {
                    "driver_blocks": ((last_div.get("suspect") or {}).get("driver_blocks") or [])[:8],
                    "signals": ((last_div.get("suspect") or {}).get("signals") or [])[:12],
                    "hint": (last_div.get("suspect") or {}).get("hint"),
                },
            },
            "repair_ledger": self._repair_ledger(limit=10),
            "promising_directions": self._directions_by_effect({"passed", "improved"}, limit=5),
            "protected_invariants": protected,
            "unsafe_directions": self._unsafe_directions(limit=8),
            "next_local_target": self._next_local_target(protected),
            "high_coupling_blocks": self._high_coupling_blocks(limit=8),
            "known_planning_corrections": self.load_known_corrections(),
            "action_calls": int(self.state.action_calls),
            "patch_attempts": int(self.state.patch_attempt_id),
            "pending_syntax_candidates": [
                {
                    "candidate_id": candidate_id,
                    "action_type": candidate.get("action_type"),
                    "target_signature": candidate.get("target_signature"),
                    "retries_used": int(candidate.get("retries_used") or 0),
                    "last_syntax_errors": candidate.get("last_syntax_errors") or [],
                }
                for candidate_id, candidate in self.state.syntax_candidates.items()
                if candidate.get("status") == "pending"
            ],
            "max_steps": int(self.state.input.max_steps),
        }

    def _recent_replaced_blocks(self, limit: int = 5) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = []
        for row in reversed(self._read_jsonl("patch_journal.jsonl")):
            if row.get("action_type") != "replace_block":
                continue
            target = row.get("target")
            blocks.append(
                {
                    "step": row.get("step"),
                    "block_id": row.get("block_id"),
                    "target": target,
                    "effect": row.get("effect"),
                    "changed_signals": row.get("changed_signals") or [],
                    "lesson": row.get("lesson"),
                }
            )
            if len(blocks) >= max(1, int(limit)):
                break
        return list(reversed(blocks))

    def _record_rejected_action(
        self,
        *,
        action_type: str,
        step: int,
        reason: str,
        hypothesis: str,
        patches: list[dict[str, Any]] | None = None,
        block_id: str | None = None,
    ) -> dict[str, Any]:
        result = {"status": "rejected", "reason": reason, "is_action_executed": False}
        entry = {
            "step": step,
            "action_type": action_type,
            "block_id": block_id,
            "target": {},
            "patch_count": 0,
            "patch_summary": reason,
            "hypothesis": hypothesis or reason,
            "evidence": {
                "latest_trace_summary": self.state.last_trace_summary,
                "last_divergence_summary": self.state.last_divergence_summary,
            },
            "changed_signals": [],
            "before": {
                "mismatch_count": int(self.state.last_sim.mismatch_count),
                "first_fail_time": self.state.last_sim.first_fail_time,
            },
            "after": {"status": "rejected", "reason": reason},
            "effect": "rejected",
            "lesson": reason,
            "patches": patches or [],
            "result": result,
        }
        self._record_patch_entry(entry)
        return result

    # ------------------------------------------------------------------
    # Read/search/KG tools
    # ------------------------------------------------------------------

    @observed("tool", "读取本轮局部上下文", stage="diagnose")
    def read_context(
        self,
        kind: Literal[
            "repo_tree",
            "file",
            "lines",
            "spec",
            "testbench",
            "stage_artifact",
            "trace_report",
            "repair_journal",
        ],
        path: str | None = None,
        start: int | None = None,
        end: int | None = None,
        artifact_name: str | None = None,
        max_chars: int = 12000,
    ) -> dict[str, Any]:
        inp = self.state.input
        if kind == "repo_tree":
            roots = {
                "debug_workdir": inp.debug_workdir,
                "rtl_root": inp.rtl_root,
                "verify_dir": inp.verify_dir,
                "workspace_root": inp.workspace_root,
                "output_root": inp.output_root,
            }
            tree: dict[str, Any] = {}
            for label, root in roots.items():
                if root is None or not root.exists():
                    continue
                entries = []
                for item in sorted(root.rglob("*")):
                    rel = item.relative_to(root)
                    if len(rel.parts) > 4:
                        continue
                    if any(part in {".git", "__pycache__", "obj_dir"} for part in rel.parts):
                        continue
                    entries.append(("/" if item.is_dir() else "") + str(rel))
                    if len(entries) >= 200:
                        entries.append("...<snip>...")
                        break
                tree[label] = {"root": str(root), "entries": entries}
            return {"status": "ok", "kind": kind, "tree": tree}

        target: Path | None = None
        if kind == "spec":
            if path:
                target = self._resolve_read_path(path)
            elif inp.spec_source_path:
                target = self._resolve_read_path(inp.spec_source_path)
            if target and target.exists():
                text = target.read_text(encoding="utf-8", errors="replace")
            else:
                text = inp.spec_text
            self.state.observed_tb_or_spec_or_kg = True
            self.state.observed_spec_or_stage = True
            return {"status": "ok", "kind": kind, "path": str(target or ""), "content": _clip(text, max_chars=max_chars)}

        if kind == "testbench":
            target = self._resolve_read_path(path or "tb.sv")
            if target is None or not target.is_file():
                return {"status": "error", "error": "testbench not found", "path": path or "tb.sv"}
            self.state.observed_tb_or_spec_or_kg = True
            text = target.read_text(encoding="utf-8", errors="replace")
            return {"status": "ok", "kind": kind, "path": str(target), "content": _clip(text, max_chars=max_chars)}

        if kind == "stage_artifact":
            name = artifact_name or path or ""
            if name == "global_defines_manifest":
                candidates = [
                    inp.workspace_root / "merged" / "global_defines_manifest.json",
                    (inp.output_root / "global_defines_manifest.json") if inp.output_root else None,
                ]
                target = next((candidate for candidate in candidates if candidate is not None and candidate.is_file()), None)
                if target is None:
                    return {"status": "error", "error": "global_defines_manifest.json not found"}
                self.state.observed_stage_artifact = True
                self.state.observed_spec_or_stage = True
                text = target.read_text(encoding="utf-8", errors="replace")
                return {"status": "ok", "kind": kind, "artifact_name": name, "path": str(target), "content": _clip(text, max_chars=max_chars)}
            if name in {"merge_report", "stage6_merge_report"}:
                candidates = [
                    inp.workspace_root / "merge_reports" / f"{inp.module_name}_merge_report.json",
                    (inp.output_root / "merge_reports" / f"{inp.module_name}_merge_report.json") if inp.output_root else None,
                ]
                target = next((candidate for candidate in candidates if candidate is not None and candidate.is_file()), None)
                if target is None:
                    return {"status": "error", "error": f"Stage6 merge report not found for {inp.module_name}"}
                self.state.observed_stage_artifact = True
                self.state.observed_spec_or_stage = True
                text = target.read_text(encoding="utf-8", errors="replace")
                return {"status": "ok", "kind": kind, "artifact_name": name, "path": str(target), "content": _clip(text, max_chars=max_chars)}
            rel = inp.stage_artifacts.get(name) or STAGE_ARTIFACTS.get(name)
            if not rel:
                return {
                    "status": "error",
                    "error": f"Unknown stage artifact: {name}",
                    **stage_artifact_help(),
                }
            target = self._resolve_read_path(rel)
            if target is None or not target.is_file():
                return {
                    "status": "error",
                    "error": f"Stage artifact not found: {name}",
                    "path": rel,
                    **stage_artifact_help(),
                }
            self.state.observed_stage_artifact = True
            self.state.observed_spec_or_stage = True
            text = target.read_text(encoding="utf-8", errors="replace")
            return {"status": "ok", "kind": kind, "artifact_name": name, "path": str(target), "content": _clip(text, max_chars=max_chars)}

        if kind == "trace_report":
            target = self._resolve_read_path(path or "trace_report.json")
            if target is None or not target.is_file():
                target = inp.debug_workdir / "trace_report.json"
            if not target.is_file():
                return {"status": "error", "error": "trace_report.json not found"}
            self.state.observed_trace_or_sim = True
            text = target.read_text(encoding="utf-8", errors="replace")
            return {"status": "ok", "kind": kind, "path": str(target), "content": _clip(text, max_chars=max_chars)}

        if kind == "repair_journal":
            target = self._resolve_read_path(path or "repair_journal.json")
            if target is None or not target.is_file():
                target = inp.debug_workdir / "repair_journal.json"
            if not target.is_file():
                return {"status": "missing", "kind": kind, "path": str(target)}
            text = target.read_text(encoding="utf-8", errors="replace")
            return {"status": "ok", "kind": kind, "path": str(target), "content": _clip(text, max_chars=max_chars)}

        target = self._resolve_read_path(path)
        if target is None or not target.is_file():
            return {"status": "error", "error": f"File not found or not readable: {path}"}
        text = target.read_text(encoding="utf-8", errors="replace")
        if target.resolve() == inp.rtl_path.resolve() or target.suffix.lower() in {".v", ".sv"}:
            self.state.observed_rtl = True
        if kind == "lines":
            lines = text.splitlines()
            s = int(start or 1)
            e = int(end or min(len(lines), s + 120))
            if s < 1 or e < s or e > len(lines):
                return {"status": "error", "error": f"Invalid line range {s}-{e}; file has {len(lines)} lines"}
            selected = "\n".join(f"{idx}: {lines[idx - 1]}" for idx in range(s, e + 1))
            return {"status": "ok", "kind": kind, "path": str(target), "start": s, "end": e, "content": _clip(selected, max_chars=max_chars)}
        return {"status": "ok", "kind": kind, "path": str(target), "content": _clip(text, max_chars=max_chars)}

    @observed("tool", "检索本轮材料", stage="diagnose")
    def search_context(
        self,
        pattern: str,
        scope: Literal["rtl", "tb", "spec", "all"] = "all",
        file_glob: str = "**/*",
        max_results: int = 50,
        context_lines: int = 2,
    ) -> dict[str, Any]:
        if not pattern:
            return {"status": "error", "error": "pattern is required"}
        try:
            regex = re.compile(pattern)
        except re.error as exc:
            return {"status": "error", "error": f"invalid regex: {exc}"}

        inp = self.state.input
        files: list[Path] = []
        if scope in {"rtl", "all"}:
            files.append(inp.rtl_path)
            if inp.rtl_root and inp.rtl_root.exists():
                files.extend(p for p in inp.rtl_root.rglob("*") if p.suffix.lower() in {".v", ".sv"})
            merged_root = inp.workspace_root / "merged"
            if merged_root.exists():
                files.extend(p for p in merged_root.rglob("*") if p.suffix.lower() in {".v", ".sv"})
        if scope in {"tb", "all"}:
            files.extend(p for p in inp.debug_workdir.glob("*") if "tb" in p.name.lower() and p.suffix.lower() in {".v", ".sv"})
        if scope in {"spec", "all"}:
            for item in [inp.spec_source_path, *inp.spec_paths]:
                if item:
                    resolved = self._resolve_read_path(item)
                    if resolved and resolved.is_file():
                        files.append(resolved)
        if scope == "all" and inp.output_root and inp.output_root.exists():
            for p in inp.output_root.glob(file_glob):
                if p.is_file() and p.suffix.lower() in {".json", ".md", ".txt", ".v", ".sv"}:
                    files.append(p)

        seen: set[Path] = set()
        results: list[dict[str, Any]] = []
        for file_path in files:
            resolved = file_path.resolve()
            if resolved in seen or not resolved.is_file():
                continue
            seen.add(resolved)
            if any(part in {".git", "__pycache__", "obj_dir", "snapshots"} for part in resolved.parts):
                continue
            try:
                lines = resolved.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for idx, line in enumerate(lines, start=1):
                if regex.search(line):
                    lo = max(1, idx - int(context_lines))
                    hi = min(len(lines), idx + int(context_lines))
                    excerpt = "\n".join(f"{i}: {lines[i - 1]}" for i in range(lo, hi + 1))
                    results.append({"path": str(resolved), "line": idx, "excerpt": excerpt})
                    if len(results) >= max(1, int(max_results)):
                        self.state.observed_tb_or_spec_or_kg = self.state.observed_tb_or_spec_or_kg or scope in {"tb", "spec", "all"}
                        self.state.observed_spec_or_stage = self.state.observed_spec_or_stage or scope in {"spec", "all"}
                        return {"status": "ok", "pattern": pattern, "scope": scope, "results": results, "truncated": True}
        self.state.observed_tb_or_spec_or_kg = self.state.observed_tb_or_spec_or_kg or scope in {"tb", "spec", "all"}
        self.state.observed_spec_or_stage = self.state.observed_spec_or_stage or scope in {"spec", "all"}
        return {"status": "ok", "pattern": pattern, "scope": scope, "results": results, "truncated": False}

    @observed("tool", "读取需求规格", stage="diagnose")
    def read_spec(
        self,
        module_name: str | None = None,
        path: str | None = None,
        max_chars: int = 12000,
    ) -> dict[str, Any]:
        del module_name
        inp = self.state.input
        target = self._resolve_read_path(path) if path else None
        if target is None and inp.spec_source_path:
            target = self._resolve_read_path(inp.spec_source_path)
        if target is not None and target.is_file():
            text = target.read_text(encoding="utf-8", errors="replace")
            source = str(target)
        elif inp.spec_paths:
            chunks: list[str] = []
            for item in inp.spec_paths:
                spec_path = self._resolve_read_path(item)
                if spec_path and spec_path.is_file():
                    chunks.append(f"// spec source: {spec_path}\n{spec_path.read_text(encoding='utf-8', errors='replace')}")
            text = "\n\n".join(chunks) if chunks else inp.spec_text
            source = "spec_paths" if chunks else "spec_text"
        else:
            text = inp.spec_text
            source = "spec_text"
        self.state.observed_tb_or_spec_or_kg = True
        self.state.observed_spec_or_stage = True
        return {"status": "ok", "source": source, "content": _clip(text, max_chars=max_chars)}

    @observed("tool", "读取规格片段", stage="diagnose")
    def retrieve_spec_block(
        self,
        module_name: str,
        query: str | None = None,
        block_id: str | None = None,
        max_results: int = 8,
    ) -> dict[str, Any]:
        inp = self.state.input
        spec_blocks_path = self._resolve_read_path(inp.stage_artifacts.get("spec_blocks") or STAGE_ARTIFACTS["spec_blocks"])
        if spec_blocks_path is None or not spec_blocks_path.is_file():
            return {"status": "error", "error": "spec_blocks.json not found"}
        try:
            obj = json.loads(spec_blocks_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            return {"status": "error", "error": f"Failed to parse spec_blocks.json: {type(exc).__name__}: {exc}"}
        modules = obj.get("modules") if isinstance(obj, dict) else []
        matches: list[dict[str, Any]] = []
        query_re = re.compile(re.escape(query), re.IGNORECASE) if query else None
        for mod in modules or []:
            if not isinstance(mod, dict) or str(mod.get("module") or "") != module_name:
                continue
            for block in mod.get("blocks") or []:
                if not isinstance(block, dict):
                    continue
                bid = str(block.get("block_id") or block.get("id") or "")
                text = str(block.get("text") or block.get("content") or "")
                if block_id and bid != block_id:
                    continue
                if query_re and not (query_re.search(bid) or query_re.search(text)):
                    continue
                matches.append({"block_id": bid, "text": _clip(text, max_chars=4000), "raw_keys": sorted(block.keys())})
                if len(matches) >= max(1, int(max_results)):
                    break
        self.state.observed_tb_or_spec_or_kg = True
        self.state.observed_stage_artifact = True
        self.state.observed_spec_or_stage = True
        return {
            "status": "ok",
            "path": str(spec_blocks_path),
            "module_name": module_name,
            "query": query,
            "block_id": block_id,
            "matches": matches,
            "truncated": len(matches) >= max(1, int(max_results)),
        }

    def _planning_output_root(self) -> Path | None:
        inp = self.state.input
        candidates: list[Path] = []
        if inp.output_root is not None:
            candidates.append(inp.output_root)
        for key in ("module_skeletons", "module_plans", "spec_blocks", "repo_skeleton"):
            raw = inp.stage_artifacts.get(key)
            resolved = self._resolve_read_path(raw) if raw else None
            if resolved is not None and resolved.is_file():
                candidates.append(resolved.parent)
        for candidate in candidates:
            resolved = candidate.resolve()
            if resolved.is_dir() and any(self._is_under(resolved, root) for root in self._allowed_read_roots()):
                return resolved
        return None

    @staticmethod
    def _read_json_file(path: Path) -> dict[str, Any] | None:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return None
        return value if isinstance(value, dict) else None

    def _load_sidecar_module_semantics(self, module_name: str, sections: set[str]) -> dict[str, Any]:
        root = self._planning_output_root()
        result: dict[str, Any] = {
            "module": {"name": module_name},
            "specs": [],
            "skeleton_artifact": None,
            "plan_artifact": None,
            "code_interface": [],
            "artifact_paths": {},
        }
        if root is None:
            return result

        paths = {
            "spec": root / "module_spec_context_json" / f"{module_name}.json",
            "skeleton": root / "module_skeleton_json" / f"{module_name}.json",
            "plan": root / "module_plan_json" / f"{module_name}.json",
        }
        if "spec" in sections:
            artifact = self._read_json_file(paths["spec"])
            if artifact is not None:
                result["artifact_paths"]["spec"] = str(paths["spec"])
                result["specs"] = [
                    {
                        "fragment": {
                            **block,
                            "text_preview": _clip(str(block.get("text") or ""), max_chars=500),
                        },
                        "relation": {
                            "local_ref": str(block.get("block_id") or ""),
                            "artifact_path": str(paths["spec"]),
                        },
                    }
                    for block in artifact.get("blocks") or []
                    if isinstance(block, dict)
                ]
        if "skeleton" in sections:
            result["skeleton_artifact"] = self._read_json_file(paths["skeleton"])
            if result["skeleton_artifact"] is not None:
                result["artifact_paths"]["skeleton"] = str(paths["skeleton"])
        if "plan" in sections:
            result["plan_artifact"] = self._read_json_file(paths["plan"])
            if result["plan_artifact"] is not None:
                result["artifact_paths"]["plan"] = str(paths["plan"])

        repo_skeleton = self._read_json_file(root / STAGE_ARTIFACTS["repo_skeleton"])
        if repo_skeleton is not None:
            for module in repo_skeleton.get("modules") or []:
                if isinstance(module, dict) and str(module.get("module") or module.get("name") or "") == module_name:
                    result["module"] = {**module, "name": module_name}
                    break
        return result

    @staticmethod
    def _semantic_item_matches(item: Any, terms: list[str]) -> bool:
        if not terms:
            return True
        haystack = json.dumps(item, ensure_ascii=False, default=str).lower()
        return any(
            re.search(rf"(?<![a-z0-9_$]){re.escape(term)}(?![a-z0-9_$])", haystack)
            for term in terms
        )

    def _module_neighbors(self, module_name: str, module: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
        warnings: list[str] = []
        kg = self.state.kg_service
        if kg is not None and getattr(kg, "is_enabled", lambda: False)():
            try:
                result = kg.query(
                    kg_templates.GET_MODULE_NEIGHBORS,
                    {"module_name": module_name},
                    limit=100,
                )
                rows = [
                    {
                        "relation": str(row.get("relation") or ""),
                        "module": str(row.get("related_module") or ""),
                        "instance_name": str(row.get("instance_name") or ""),
                        "instance_path": str(row.get("instance_path") or ""),
                        "semantics_included": False,
                    }
                    for row in result.get("rows") or []
                    if row.get("related_module")
                ]
                if rows:
                    return rows, warnings
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"KG neighbor lookup failed: {type(exc).__name__}: {exc}")

        rows = []
        for relation, key, fallback_key in (
            ("parent", "planned_parents", "parents"),
            ("child", "planned_children", "children"),
        ):
            for related in module.get(key) or module.get(fallback_key) or []:
                rows.append(
                    {
                        "relation": relation,
                        "module": str(related),
                        "instance_name": "",
                        "instance_path": "",
                        "semantics_included": False,
                        "source": "planned_hierarchy",
                    }
                )
        return rows, warnings

    @observed("tool", "读取模块与规划关系", stage="diagnose")
    def read_module_semantics(
        self,
        module_name: str,
        sections: list[str] | None = None,
        focus_signals: list[str] | None = None,
        focus_blocks: list[str] | None = None,
        max_chars: int = 12000,
    ) -> dict[str, Any]:
        requested = {str(item).strip().lower() for item in (sections or ["spec", "skeleton", "plan"])}
        invalid = sorted(requested - {"spec", "skeleton", "plan"})
        if invalid:
            return {"status": "error", "error": f"Unsupported sections: {invalid}"}
        if not module_name.strip():
            return {"status": "error", "error": "module_name is required"}

        warnings: list[str] = []
        source = "planning_kg"
        context: dict[str, Any] | None = None
        kg = self.state.kg_service
        output_root = self._planning_output_root()
        if kg is not None and getattr(kg, "is_enabled", lambda: False)():
            try:
                context = PlanningContextRetriever(kg, output_root, self.state.logger).get_module_context(
                    module_name,
                    require_spec="spec" in requested,
                    require_skeleton="skeleton" in requested,
                    require_plan="plan" in requested,
                    include_code_interface=True,
                )
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"Planning KG context unavailable or stale: {type(exc).__name__}: {exc}")
        else:
            warnings.append("Planning KG is disabled or unavailable.")
        if context is None:
            source = "sidecar_fallback"
            context = self._load_sidecar_module_semantics(module_name, requested)

        module = dict(context.get("module") or {"name": module_name})
        specs = list(context.get("specs") or []) if "spec" in requested else []
        skeleton_metadata = context.get("skeleton") if isinstance(context.get("skeleton"), dict) else {}
        plan_metadata = context.get("plan") if isinstance(context.get("plan"), dict) else {}
        skeleton = context.get("skeleton_artifact") or skeleton_metadata or {}
        plan = context.get("plan_artifact") or plan_metadata or {}
        skeleton = skeleton if isinstance(skeleton, dict) and "skeleton" in requested else {}
        plan = plan if isinstance(plan, dict) and "plan" in requested else {}

        focus_signal_terms = [_signal_leaf(item).lower() for item in (focus_signals or []) if str(item).strip()]
        focus_block_terms = [str(item).strip().lower() for item in (focus_blocks or []) if str(item).strip()]
        terms = list(dict.fromkeys([*focus_signal_terms, *focus_block_terms]))
        focused = bool(terms)

        selected_specs = [item for item in specs if self._semantic_item_matches(item, terms)]
        if focused and specs and not selected_specs:
            selected_specs = specs[:4]
            warnings.append("No exact focus match in SpecFragments; returning a compact module-level fallback.")
        selected_specs = selected_specs[:12]
        spec_refs = {
            str((item.get("relation") or {}).get("local_ref") or (item.get("fragment") or {}).get("block_id") or "")
            for item in selected_specs
            if isinstance(item, dict)
        }

        all_blocks = [item for item in skeleton.get("structural_blocks") or [] if isinstance(item, dict)]
        selected_blocks = [item for item in all_blocks if self._semantic_item_matches(item, terms)]
        if focused and all_blocks and not selected_blocks:
            selected_blocks = all_blocks[:6]
            warnings.append("No exact focus match in Skeleton blocks; returning a compact structural fallback.")
        selected_blocks = [
            {
                **item,
                "planning_block_id": item.get("planning_block_id")
                or item.get("block_id")
                or item.get("block_label"),
            }
            for item in selected_blocks[:16]
        ]
        selected_block_ids = {
            str(
                item.get("planning_block_id")
                or item.get("block_id")
                or item.get("block_label")
                or ""
            ).lower()
            for item in selected_blocks
        }

        all_subtasks = [item for item in plan.get("subtasks") or [] if isinstance(item, dict)]
        selected_subtasks = []
        for item in all_subtasks:
            refs = {str(ref) for ref in item.get("spec_refs") or []}
            target = str(item.get("target") or item.get("id") or "").lower()
            if (
                not focused
                or self._semantic_item_matches(item, terms)
                or bool(refs & spec_refs)
                or any(block_id and block_id in target for block_id in selected_block_ids)
            ):
                selected_subtasks.append(item)
        if focused and all_subtasks and not selected_subtasks:
            selected_subtasks = all_subtasks[:6]
            warnings.append("No exact focus match in ModulePlan subtasks; returning a compact plan fallback.")
        selected_subtasks = selected_subtasks[:16]

        editable_rtl_blocks: list[dict[str, Any]] = []
        block_alignment: list[dict[str, Any]] = []
        rtl_path, _rtl_metadata, rtl_warnings = self._resolve_module_rtl_path(module_name)
        warnings.extend(rtl_warnings)
        if rtl_path is not None:
            try:
                rtl_text = rtl_path.read_text(encoding="utf-8", errors="replace")
                module_text, line_offset = self._extract_module_source(rtl_text, module_name)
                parsed_blocks = parse_rtl_blocks(module_text)
                if line_offset:
                    parsed_blocks = [
                        replace(
                            block,
                            start_line=block.start_line + line_offset,
                            end_line=block.end_line + line_offset,
                        )
                        for block in parsed_blocks
                    ]
                focus_signal_set = set(focus_signal_terms)
                focus_rtl_id_set = {
                    term
                    for term in focus_block_terms
                    if any(str(block.id).lower() == term for block in parsed_blocks)
                }

                def rtl_relevance(block: Any) -> tuple[int, int, str]:
                    symbols = {
                        str(item).lower()
                        for item in (*block.writes, *block.reads)
                    }
                    return (
                        1 if str(block.id).lower() in focus_rtl_id_set else 0,
                        len(symbols & focus_signal_set),
                        str(block.id),
                    )

                ranked_blocks = sorted(
                    parsed_blocks,
                    key=lambda block: (
                        -rtl_relevance(block)[0],
                        -rtl_relevance(block)[1],
                        rtl_relevance(block)[2],
                    ),
                )
                if focused:
                    relevant_blocks = [
                        block
                        for block in ranked_blocks
                        if str(block.id).lower() in focus_rtl_id_set
                        or bool(
                            {
                                str(item).lower()
                                for item in (*block.writes, *block.reads)
                            }
                            & focus_signal_set
                        )
                    ]
                else:
                    relevant_blocks = ranked_blocks
                editable_rtl_blocks = [
                    self._rtl_block_payload(module_name, rtl_path, block)
                    for block in relevant_blocks[:16]
                ]

                for planning_block in selected_blocks:
                    planning_block_id = str(
                        planning_block.get("planning_block_id") or ""
                    )
                    planning_text = json.dumps(
                        planning_block,
                        ensure_ascii=False,
                        default=str,
                    ).lower()
                    aligned: list[dict[str, Any]] = []
                    basis: list[str] = []
                    for rtl_block in editable_rtl_blocks:
                        symbols = [
                            str(item)
                            for item in [
                                *(rtl_block.get("writes") or []),
                                *(rtl_block.get("reads") or []),
                            ]
                            if str(item)
                        ]
                        overlap = sorted(
                            {
                                symbol
                                for symbol in symbols
                                if re.search(
                                    rf"\b{re.escape(symbol.lower())}\b",
                                    planning_text,
                                )
                            }
                        )
                        focus_overlap = sorted(
                            set(symbol.lower() for symbol in symbols)
                            & focus_signal_set
                        )
                        if overlap or (
                            focus_overlap
                            and self._semantic_item_matches(
                                planning_block,
                                list(focus_signal_set),
                            )
                        ):
                            aligned.append(rtl_block)
                            basis.extend(
                                f"shared signal: {signal}"
                                for signal in (overlap or focus_overlap)
                            )
                    if aligned:
                        block_alignment.append(
                            {
                                "planning_block_id": planning_block_id,
                                "rtl_block_ids": [
                                    item["rtl_block_id"] for item in aligned
                                ],
                                "rtl_block_refs": [
                                    item["rtl_block_ref"] for item in aligned
                                ],
                                "basis": list(dict.fromkeys(basis))[:8],
                                "confidence": 0.85 if basis else 0.6,
                                "authoritative_for_editing": False,
                            }
                        )
            except OSError as exc:
                warnings.append(
                    f"RTL block identity projection failed: {type(exc).__name__}: {exc}"
                )

        per_text_budget = max(500, min(4000, max(1, int(max_chars)) // 5))
        spec_fragments = []
        for item in selected_specs:
            fragment = dict(item.get("fragment") or {})
            relation = dict(item.get("relation") or {})
            spec_fragments.append(
                {
                    "block_id": relation.get("local_ref") or fragment.get("block_id"),
                    "text": _clip(fragment.get("text") or fragment.get("text_preview") or "", max_chars=per_text_budget),
                    "source_file": fragment.get("source_file"),
                    "source_chunk_ids": fragment.get("source_chunk_ids") or [],
                    "confidence": fragment.get("confidence"),
                    "content_hash": fragment.get("content_hash"),
                    "input_fingerprint": relation.get("input_fingerprint"),
                }
            )
        list_budget = max(500, max(1, int(max_chars)) // 5)
        spec_fragments, specs_budget_truncated = _budget_json_items(spec_fragments, max_chars=list_budget)
        skeleton_blocks, skeleton_budget_truncated = _budget_json_items(selected_blocks, max_chars=list_budget)
        plan_subtasks, plan_budget_truncated = _budget_json_items(selected_subtasks, max_chars=list_budget)
        semantic_invariants_items, invariants_budget_truncated = _budget_json_items(
            [
                {
                    "planning_note": skeleton.get("planning_note"),
                    "module_behavior": skeleton.get("module_behavior") or {},
                    "block_behavior_overlays": skeleton.get("block_behavior_overlays") or [],
                    "plan_timing_obligations": plan.get("timing_obligations") or [],
                }
            ],
            max_chars=list_budget,
        )
        semantic_invariants = semantic_invariants_items[0] if semantic_invariants_items else {}

        neighbors, neighbor_warnings = self._module_neighbors(module_name, module)
        warnings.extend(neighbor_warnings)
        provenance = {
            "source": source,
            "output_root": str(output_root) if output_root else "",
            "artifact_paths": context.get("artifact_paths") or {
                "spec": [str((item.get("relation") or {}).get("artifact_path") or "") for item in selected_specs],
                "skeleton": skeleton.get("artifact_path"),
                "plan": plan.get("artifact_path"),
            },
            "fingerprints": {
                "stage2": module.get("stage2_fingerprint"),
                "skeleton_input": skeleton_metadata.get("input_fingerprint") or skeleton.get("input_fingerprint"),
                "skeleton_content": skeleton_metadata.get("content_hash") or skeleton.get("content_hash"),
                "plan_input": plan_metadata.get("input_fingerprint") or plan.get("input_fingerprint"),
                "plan_skeleton_content": (
                    plan_metadata.get("skeleton_content_hash") or plan.get("skeleton_content_hash")
                ),
            },
        }
        payload = {
            "status": "ok",
            "source": source,
            "module": module,
            "spec_fragments": spec_fragments,
            "skeleton_blocks": skeleton_blocks,
            "plan_subtasks": plan_subtasks,
            "interface": context.get("code_interface") or [],
            "semantic_invariants": semantic_invariants,
            "editable_rtl_blocks": editable_rtl_blocks,
            "block_alignment": block_alignment,
            "neighbors": neighbors,
            "provenance": provenance,
            "focus_applied": {
                "signals": list(focus_signals or []),
                "rtl_block_ids": [
                    item["rtl_block_id"]
                    for item in editable_rtl_blocks
                    if str(item["rtl_block_id"]).lower()
                    in set(focus_block_terms)
                ],
                "planning_block_ids": [
                    item.get("planning_block_id")
                    for item in skeleton_blocks
                    if item.get("planning_block_id")
                ],
            },
            "warnings": warnings,
            "truncated": (
                len(specs) > len(selected_specs)
                or len(all_blocks) > len(selected_blocks)
                or len(all_subtasks) > len(selected_subtasks)
                or specs_budget_truncated
                or skeleton_budget_truncated
                or plan_budget_truncated
                or invariants_budget_truncated
            ),
        }
        self.state.observed_tb_or_spec_or_kg = True
        self.state.observed_spec_or_stage = True
        self.state.observed_stage_artifact = True
        return payload

    def _load_vcd(self) -> Any:
        if VCDVCD is None:
            return None
        vcd_path = self.state.input.debug_workdir / "wave.vcd"
        if not vcd_path.exists():
            return None
        try:
            return VCDVCD(str(vcd_path), store_tvs=True)  # type: ignore[operator]
        except Exception:
            return None

    def _vcd_context(self, vcd: Any) -> dict[str, str | None]:
        dut = None
        report_path = self.state.input.debug_workdir / "trace_report.json"
        if report_path.exists():
            try:
                report = json.loads(report_path.read_text(encoding="utf-8"))
                dut = report.get("dut_instance")
            except Exception:  # noqa: BLE001
                dut = None
        return {"dut": dut, "ref": _resolve_ref_instance_static(vcd)}

    @observed("tool", "列出本轮波形信号", stage="diagnose")
    def list_vcd_signals(self, pattern: str = "", scope: str = "", limit: int = 100) -> dict[str, Any]:
        vcd = self._load_vcd()
        if vcd is None:
            return {"status": "missing_vcd", "error": "wave.vcd not found or vcdvcd unavailable"}
        self.state.observed_trace_or_sim = True
        return list_vcd_signals_query(vcd, pattern=pattern, scope=scope, limit=limit)

    @observed("tool", "查看本轮波形采样", stage="diagnose")
    def probe_vcd(
        self,
        signals: list[str],
        time: int | None = None,
        time_range: list[int] | None = None,
        edge: str | None = None,
        mode: str = "sample",
        max_rows: int = 80,
    ) -> dict[str, Any]:
        vcd = self._load_vcd()
        if vcd is None:
            return {"status": "missing_vcd", "error": "wave.vcd not found or vcdvcd unavailable"}
        if not signals:
            return {"status": "too_many_signals", "error": "No signals provided"}
        ctx = self._vcd_context(vcd)
        resolved: list[str] = []
        for sig in signals:
            item = resolve_vcd_signal(vcd, sig, dut_instance=ctx.get("dut"), ref_instance=ctx.get("ref"))
            if item.get("status") != "ok":
                return item
            resolved.append(str(item["full_path"]))

        times: list[int] | None = None
        t_range: tuple[int, int] | None = None
        clock_name: str | None = None
        edge_filter: str | None = None
        if time is not None:
            times = [int(time)]
        elif time_range is not None and len(time_range) == 2:
            t_range = (int(time_range[0]), int(time_range[1]))
        else:
            detected = _vcd_time_range(vcd)
            if detected is not None:
                t_range = detected
        if t_range is not None and edge:
            edge_parts = edge.strip().split()
            edge_filter = edge_parts[0] if edge_parts else None
            clk_hint = edge_parts[1] if len(edge_parts) > 1 else None
            clock_name = _find_clock_signal(vcd, preferred_name=clk_hint)
            if clock_name is None:
                return {"status": "missing_vcd", "error": f"Clock signal not found (hint: {clk_hint})"}
        self.state.observed_trace_or_sim = True
        return sample_vcd_signals(
            vcd,
            resolved,
            times=times,
            time_range=t_range,
            clock_name=clock_name,
            edge_filter=edge_filter,
            mode=mode,
            max_rows=max_rows,
        )

    def _resolve_module_rtl_path(self, module_name: str) -> tuple[Path | None, dict[str, Any], list[str]]:
        warnings: list[str] = []
        kg_metadata: dict[str, Any] = {}
        kg = self.state.kg_service
        if kg is not None and getattr(kg, "is_enabled", lambda: False)():
            try:
                result = kg.query(
                    kg_templates.GET_MODULE_SOURCE,
                    {"module_name": module_name},
                    limit=5,
                )
                rows = list(result.get("rows") or [])
                if rows:
                    kg_metadata = dict(rows[0])
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"KG module source lookup failed: {type(exc).__name__}: {exc}")

        inp = self.state.input
        candidates: list[Path] = []
        if module_name in {inp.module_name, inp.top_module}:
            candidates.extend([inp.rtl_path, inp.merged_file])
        for raw in (kg_metadata.get("actual_path"), kg_metadata.get("path")):
            if raw:
                if inp.rtl_root is not None:
                    candidates.append(inp.rtl_root / Path(str(raw)).name)
                resolved = self._resolve_read_path(str(raw))
                if resolved is not None:
                    candidates.append(resolved)

        checked: set[Path] = set()
        module_re = re.compile(rf"\bmodule\s+(?:automatic\s+)?{re.escape(module_name)}\b")
        for candidate in candidates:
            resolved = candidate.resolve()
            if resolved in checked or not resolved.is_file():
                continue
            checked.add(resolved)
            try:
                if module_re.search(resolved.read_text(encoding="utf-8", errors="replace")):
                    return resolved, kg_metadata, warnings
            except OSError:
                continue

        roots = [item for item in (inp.rtl_root, inp.rtl_path.parent) if item is not None and item.exists()]
        for root in roots:
            for candidate in sorted(
                path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in {".v", ".sv"}
            ):
                resolved = candidate.resolve()
                if resolved in checked:
                    continue
                checked.add(resolved)
                try:
                    if module_re.search(resolved.read_text(encoding="utf-8", errors="replace")):
                        return resolved, kg_metadata, warnings
                except OSError:
                    continue
        warnings.append(f"RTL source for module `{module_name}` was not found.")
        return None, kg_metadata, warnings

    @staticmethod
    def _extract_module_source(rtl_text: str, module_name: str) -> tuple[str, int]:
        start_match = re.search(
            rf"\bmodule\s+(?:automatic\s+)?{re.escape(module_name)}\b",
            rtl_text,
        )
        if start_match is None:
            return rtl_text, 0
        end_match = re.search(r"\bendmodule\b", rtl_text[start_match.end() :])
        if end_match is None:
            return rtl_text, 0
        start = start_match.start()
        end = start_match.end() + end_match.end()
        line_offset = rtl_text[:start].count("\n")
        return rtl_text[start:end], line_offset

    @staticmethod
    def _rtl_block_payload(module_name: str, rtl_path: Path, block: Any) -> dict[str, Any]:
        rtl_block_id = str(block.id)
        return {
            "module_name": module_name,
            "rtl_block_id": rtl_block_id,
            "rtl_block_ref": f"{module_name}:{rtl_block_id}",
            "path": str(rtl_path),
            "kind": str(block.kind),
            "clocking": str(block.clocking),
            "start_line": int(block.start_line),
            "end_line": int(block.end_line),
            "writes": list(block.writes),
            "reads": list(block.reads),
            "source_hash": hashlib.sha256(str(block.code).encode("utf-8")).hexdigest(),
        }

    @staticmethod
    def _frontier_recommended_call(
        item: dict[str, Any],
        *,
        trace_time: int | None,
    ) -> dict[str, Any]:
        args: dict[str, Any] = {
            "module_name": str(item.get("module") or ""),
            "signal_name": str(item.get("signal") or ""),
        }
        if trace_time is not None:
            args["time"] = int(trace_time)
        return {
            "tool": "trace_signal_cause",
            "args": args,
            "candidate_id": item.get("candidate_id"),
            "reason": item.get("reason") or "Continue one-hop causal tracing.",
        }

    @staticmethod
    def _select_frontier_candidates(
        candidates: list[dict[str, Any]],
        *,
        limit: int = 12,
    ) -> tuple[list[dict[str, Any]], bool]:
        """Select a stable frontier while reserving room for RHS and boundaries."""
        limit = max(1, int(limit))
        deduped: dict[tuple[str, str, str], dict[str, Any]] = {}
        for item in candidates:
            key = (
                str(item.get("module") or ""),
                str(item.get("signal") or ""),
                str(item.get("relation") or ""),
            )
            existing = deduped.get(key)
            if existing is None or int(item.get("priority") or 0) > int(existing.get("priority") or 0):
                deduped[key] = dict(item)
        ordered = sorted(
            deduped.values(),
            key=lambda item: (
                -int(item.get("priority") or 0),
                str(item.get("module") or ""),
                str(item.get("signal") or ""),
                str(item.get("relation") or ""),
            ),
        )

        selected: list[dict[str, Any]] = []
        selected_keys: set[tuple[str, str, str]] = set()

        def add(items: list[dict[str, Any]], quota: int) -> None:
            for item in items:
                if quota <= 0 or len(selected) >= limit:
                    break
                key = (
                    str(item.get("module") or ""),
                    str(item.get("signal") or ""),
                    str(item.get("relation") or ""),
                )
                if key in selected_keys:
                    continue
                selected_keys.add(key)
                selected.append(item)
                quota -= 1

        add([item for item in ordered if item.get("boundary")], 2)
        add([item for item in ordered if item.get("relation") == "local_rhs"], 4)
        add(ordered, limit)
        selected.sort(
            key=lambda item: (
                -int(item.get("priority") or 0),
                str(item.get("module") or ""),
                str(item.get("signal") or ""),
            )
        )
        selected = selected[:limit]
        for index, item in enumerate(selected, start=1):
            item["candidate_id"] = f"F{index}"
        return selected, len(ordered) > len(selected)

    def _trace_time_and_expected(
        self,
        signal_name: str,
        time: int | None,
        expected_value: str | None,
    ) -> tuple[int | None, str | None]:
        div = self.state.last_divergence_summary or {}
        first = div.get("first_divergence") if isinstance(div.get("first_divergence"), dict) else {}
        if time is None:
            candidate = first.get("time") if isinstance(first, dict) else None
            candidate = candidate if candidate is not None else div.get("time")
            candidate = candidate if candidate is not None else self.state.last_sim.first_fail_time
            candidate = candidate if candidate is not None else _extract_first_fail_time(self.state.input.sim_failed_log)
            time = int(candidate) if candidate is not None else None
        if expected_value is None and isinstance(first, dict):
            first_signal = _signal_leaf(str(first.get("signal") or ""))
            if not first_signal or first_signal == _signal_leaf(signal_name):
                expected_value = first.get("ref") or first.get("expected")
        return time, str(expected_value) if expected_value is not None else None

    def _signal_boundary_mappings(
        self,
        module_name: str,
        signals: list[str],
    ) -> tuple[list[dict[str, Any]], list[str]]:
        kg = self.state.kg_service
        if kg is None or not getattr(kg, "is_enabled", lambda: False)():
            return [], ["KG unavailable; Instance/Port boundary mapping was skipped."]
        try:
            result = kg.query(
                kg_templates.GET_SIGNAL_BOUNDARY_MAPPINGS,
                {"module_name": module_name},
                limit=500,
            )
        except Exception as exc:  # noqa: BLE001
            return [], [f"KG boundary mapping failed: {type(exc).__name__}: {exc}"]

        wanted = {_signal_leaf(item) for item in signals if str(item).strip()}
        mappings: list[dict[str, Any]] = []
        seen: set[tuple[str, ...]] = set()
        for row in result.get("rows") or []:
            direction = str(row.get("mapping_direction") or "")
            child_port = _signal_leaf(str(row.get("child_port") or ""))
            target_name = _signal_leaf(str(row.get("target_name") or ""))
            expression = str(
                row.get("connection_expression")
                or (row.get("connection") or {}).get("x")
                or target_name
            )
            matched_signal = ""
            if direction == "parent_to_child":
                for signal in wanted:
                    if target_name == signal or _expression_mentions_signal(expression, signal):
                        matched_signal = signal
                        break
            elif direction == "child_to_parent" and child_port in wanted:
                matched_signal = child_port
            if not matched_signal:
                continue

            attrs = _json_attrs(row.get("child_port_attrs"))
            item = {
                "matched_signal": matched_signal,
                "mapping_direction": direction,
                "parent_module": str(row.get("parent_module") or ""),
                "parent_actual_signal": target_name or _simple_connection_signal(expression),
                "connection_expression": expression,
                "connection_target_kind": str(row.get("target_kind") or ""),
                "instance_name": str(row.get("instance_name") or ""),
                "instance_path": str(row.get("instance_path") or ""),
                "child_module": str(row.get("child_module") or ""),
                "child_port": child_port,
                "child_port_path": str(row.get("child_port_path") or ""),
                "direction": str(attrs.get("dir") or attrs.get("direction") or ""),
                "width": str(attrs.get("width_expr") or attrs.get("width") or ""),
                "connection": dict(row.get("connection") or {}),
            }
            key = tuple(
                str(item.get(name) or "")
                for name in (
                    "mapping_direction",
                    "parent_module",
                    "instance_name",
                    "child_module",
                    "child_port",
                    "connection_expression",
                    "matched_signal",
                )
            )
            if key not in seen:
                seen.add(key)
                mappings.append(item)
        return mappings, []

    @observed("tool", "沿信号关系检查失败线索", stage="diagnose")
    def trace_signal_cause(
        self,
        module_name: str,
        signal_name: str,
        time: int | None = None,
        expected_value: str | None = None,
        max_candidates: int = 5,
    ) -> dict[str, Any]:
        if not module_name.strip() or not signal_name.strip():
            return {"status": "error", "error": "module_name and signal_name are required"}
        max_candidates = max(1, min(int(max_candidates), 20))
        leaf = _signal_leaf(signal_name)
        trace_time, expected = self._trace_time_and_expected(signal_name, time, expected_value)
        rtl_path, module_metadata, warnings = self._resolve_module_rtl_path(module_name)
        if rtl_path is None:
            return {
                "status": "error",
                "module": module_name,
                "signal": leaf,
                "error": f"RTL source for module `{module_name}` was not found",
                "warnings": warnings,
            }

        rtl_text = rtl_path.read_text(encoding="utf-8", errors="replace")
        module_text, line_offset = self._extract_module_source(rtl_text, module_name)
        blocks = parse_rtl_blocks(module_text)
        if line_offset:
            blocks = [
                replace(block, start_line=block.start_line + line_offset, end_line=block.end_line + line_offset)
                for block in blocks
            ]
        assignments = parse_rtl_assignments(module_text, blocks)
        direct_drivers = [item for item in assignments if _signal_leaf(item.lhs) == leaf]

        vcd = self._load_vcd()
        resolved_paths: dict[str, str] = {}
        sample_cache: dict[str, str | None] = {}
        vcd_ctx = self._vcd_context(vcd) if vcd is not None else {"dut": None, "ref": None}

        def sample_signal(*, leaf: str, t: int, prefer_dut: bool = True) -> str | None:
            del prefer_dut
            cache_key = f"{leaf}@{t}"
            if cache_key in sample_cache:
                return sample_cache[cache_key]
            if vcd is None:
                sample_cache[cache_key] = None
                return None
            alias = f"dut.{leaf}" if vcd_ctx.get("dut") else leaf
            resolved = resolve_vcd_signal(
                vcd,
                alias,
                dut_instance=vcd_ctx.get("dut"),
                ref_instance=vcd_ctx.get("ref"),
            )
            if resolved.get("status") != "ok":
                sample_cache[cache_key] = None
                return None
            full_path = str(resolved["full_path"])
            resolved_paths[leaf] = full_path
            tv = _vcd_time_values(vcd, full_path)
            value = _vcd_value_at(tv, t, inclusive=True) if tv is not None else None
            sample_cache[cache_key] = value
            return value

        actual = sample_signal(leaf=leaf, t=trace_time, prefer_dut=True) if trace_time is not None else None
        driver_candidates: list[dict[str, Any]] = []
        for assignment in direct_drivers[:max_candidates]:
            step = build_assignment_trace_step(
                signal=leaf,
                expected=expected,
                actual=actual,
                fail_time=trace_time or 0,
                assignment=assignment,
                sample_signal=sample_signal,
            )
            if vcd is None or trace_time is None:
                if step["classification"] != "constant_assignment":
                    step["classification"] = "static_dependency"
                    step["reason"] = "Static one-hop dependency found; waveform evidence is unavailable."
            if assignment.clocking in {"seq", "latch"} or assignment.kind == "nonblocking":
                step["needs_edge_probe"] = True
                step["sampling_note"] = (
                    "Same-time values do not prove a sequential transfer; inspect the relevant clock edge if needed."
                )
            driver_candidates.append(step)

        kg_drivers: list[dict[str, Any]] = []
        kg = self.state.kg_service
        if kg is not None and getattr(kg, "is_enabled", lambda: False)():
            try:
                result = kg.query(
                    kg_templates.GET_SIGNAL_DEBUG_CONTEXT,
                    {"module_name": module_name, "signal_name": leaf},
                    limit=100,
                )
                for row in result.get("rows") or []:
                    kg_drivers.extend(item for item in row.get("drivers") or [] if isinstance(item, dict))
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"KG driver enrichment failed: {type(exc).__name__}: {exc}")
        for candidate in driver_candidates:
            assignment = candidate.get("assignment") or {}
            start_line = int(assignment.get("start_line") or 0)
            candidate["kg_drivers"] = [
                item
                for item in kg_drivers
                if not item.get("sl")
                or int(item.get("sl") or 0) <= start_line <= int(item.get("el") or item.get("sl") or 0)
            ] or kg_drivers[:5]

        frontier_candidates_all: list[dict[str, Any]] = []
        for candidate in driver_candidates:
            assignment = candidate.get("assignment") or {}
            classification = str(candidate.get("classification") or "")
            assignment_id = str(candidate.get("assignment_id") or assignment.get("id") or "")
            if classification == "condition_blocks_update":
                condition_priority = 110
                rhs_priority = 80
            elif classification in {
                "lhs_matches_rhs_continue_upstream",
                "missing_vcd_signal",
                "static_dependency",
                "source_matches_expected_mux_wrong",
                "rhs_matches_expected_lhs_stale",
            }:
                condition_priority = 50
                rhs_priority = 100
            else:
                condition_priority = 60
                rhs_priority = 80
            for condition, value in (candidate.get("condition_values") or {}).items():
                frontier_candidates_all.append(
                    {
                        "module": module_name,
                        "signal": condition,
                        "value": value,
                        "relation": "local_condition",
                        "source_assignment_id": assignment_id,
                        "source_driver_classification": classification,
                        "priority": condition_priority,
                        "traceable": True,
                        "boundary": False,
                        "reason": (
                            "Condition participates in selecting or enabling the direct assignment"
                            + (
                                " and appears to block this branch."
                                if classification == "condition_blocks_update"
                                else "."
                            )
                        ),
                    }
                )
            for rhs, value in (candidate.get("rhs_observed_values") or {}).items():
                frontier_candidates_all.append(
                    {
                        "module": module_name,
                        "signal": rhs,
                        "value": value,
                        "relation": "local_rhs",
                        "source_assignment_id": assignment_id,
                        "source_driver_classification": classification,
                        "priority": rhs_priority,
                        "traceable": True,
                        "boundary": False,
                        "reason": candidate.get("reason"),
                    }
                )

        boundary_signals = [leaf, *[item["signal"] for item in frontier_candidates_all]]
        boundary_mappings, boundary_warnings = self._signal_boundary_mappings(module_name, boundary_signals)
        warnings.extend(boundary_warnings)
        context_candidates: list[dict[str, Any]] = []
        for mapping in boundary_mappings:
            port_direction = mapping.get("direction")
            direction = mapping.get("mapping_direction")
            if direction == "parent_to_child" and port_direction in {"output", "inout"}:
                frontier = {
                    "module": mapping.get("child_module"),
                    "signal": mapping.get("child_port"),
                    "relation": "child_output_boundary",
                    "source_assignment_id": next(
                        (
                            item.get("source_assignment_id")
                            for item in frontier_candidates_all
                            if item.get("signal") == mapping.get("matched_signal")
                        ),
                        None,
                    ),
                    "source_driver_classification": "instance_output_boundary",
                    "priority": 130,
                    "traceable": True,
                    "boundary": True,
                    "reason": (
                        f"{mapping.get('matched_signal')} is driven through instance "
                        f"{mapping.get('instance_name')}.{mapping.get('child_port')}."
                    ),
                }
            elif direction == "child_to_parent" and port_direction in {"input", "inout"}:
                parent_signal = _simple_connection_signal(str(mapping.get("connection_expression") or ""))
                if not parent_signal:
                    continue
                frontier = {
                    "module": mapping.get("parent_module"),
                    "signal": parent_signal,
                    "relation": "parent_input_boundary",
                    "source_assignment_id": None,
                    "source_driver_classification": "instance_input_boundary",
                    "priority": 130,
                    "traceable": True,
                    "boundary": True,
                    "reason": (
                        f"Child input {mapping.get('child_port')} is connected from "
                        f"{mapping.get('parent_module')}.{mapping.get('connection_expression')}."
                    ),
                }
            else:
                continue
            frontier_candidates_all.append(frontier)
            context_candidates.append(
                {
                    "module": frontier["module"],
                    "relation": frontier["relation"],
                    "reason": frontier["reason"],
                    "semantics_included": False,
                }
            )

        deduped_frontier, frontier_truncated = self._select_frontier_candidates(
            frontier_candidates_all,
            limit=12,
        )
        for item in deduped_frontier:
            item["recommended_call"] = self._frontier_recommended_call(
                item,
                trace_time=trace_time,
            )

        if not direct_drivers:
            stop_reason = "no_assignment_driver"
        elif len(direct_drivers) > max_candidates:
            stop_reason = "candidate_limit_reached"
        else:
            stop_reason = "one_hop_complete"
        status = "ok" if vcd is not None and trace_time is not None else "static_only"
        self.state.observed_rtl = True
        self.state.observed_trace_or_sim = self.state.observed_trace_or_sim or vcd is not None
        self.state.observed_tb_or_spec_or_kg = self.state.observed_tb_or_spec_or_kg or bool(kg_drivers or boundary_mappings)
        driver_block_ids = list(
            dict.fromkeys(
                str(candidate.get("driver_block_id") or "")
                for candidate in driver_candidates
                if candidate.get("driver_block_id")
            )
        )
        block_by_id = {block.id: block for block in blocks}
        editable_rtl_blocks = [
            self._rtl_block_payload(module_name, rtl_path, block_by_id[block_id])
            for block_id in driver_block_ids
            if block_id in block_by_id
        ]
        focus_context = {
            "signals": [leaf],
            "rtl_block_ids": driver_block_ids,
            "rtl_block_refs": [
                str(item["rtl_block_ref"]) for item in editable_rtl_blocks
            ],
        }
        recommended_next_calls: list[dict[str, Any]] = []
        recommended_next_call: dict[str, Any] | None = None
        traceable_frontier = [
            item for item in deduped_frontier if item.get("traceable") and item.get("recommended_call")
        ]
        if traceable_frontier:
            recommended_next_call = dict(traceable_frontier[0]["recommended_call"])
            recommended_next_calls.append(recommended_next_call)
        if driver_candidates:
            focused_blocks = [
                block_by_id[block_id]
                for block_id in driver_block_ids
                if block_id in block_by_id
            ]
            recommended_next_calls.append(
                {
                    "tool": "read_context",
                    "args": {
                        "kind": "lines",
                        "path": str(rtl_path),
                        "start": (
                            min(block.start_line for block in focused_blocks)
                            if focused_blocks
                            else min(
                                int((candidate.get("assignment") or {}).get("start_line") or 1)
                                for candidate in driver_candidates
                            )
                        ),
                        "end": (
                            max(block.end_line for block in focused_blocks)
                            if focused_blocks
                            else max(
                                int((candidate.get("assignment") or {}).get("end_line") or 1)
                                for candidate in driver_candidates
                            )
                        ),
                    },
                }
            )
        recommended_next_calls.append(
            {
                "tool": "read_module_semantics",
                "args": {
                    "module_name": module_name,
                    "sections": ["spec", "skeleton", "plan"],
                    "focus_signals": [leaf],
                    "focus_blocks": driver_block_ids,
                },
            }
        )
        payload = {
            "status": status,
            "module": module_name,
            "signal": leaf,
            "resolved_vcd_path": resolved_paths.get(leaf),
            "time": trace_time,
            "observed_value": actual,
            "expected_value": expected,
            "rtl_path": str(rtl_path),
            "driver_candidates": driver_candidates,
            "next_frontier": deduped_frontier,
            "frontier_candidates": deduped_frontier,
            "frontier_truncated": frontier_truncated,
            "boundary_mappings": boundary_mappings,
            "context_escalation_candidates": context_candidates,
            "editable_rtl_blocks": editable_rtl_blocks,
            "focus_context": focus_context,
            "recommended_next_call": recommended_next_call,
            "recommended_next_calls": recommended_next_calls,
            "stop_reason": stop_reason,
            "warnings": warnings,
            "provenance": {
                "module_uid": module_metadata.get("module_uid"),
                "module_start_line": module_metadata.get("module_start_line"),
                "module_end_line": module_metadata.get("module_end_line"),
                "kg_driver_count": len(kg_drivers),
                "assignment_count": len(direct_drivers),
                "vcd_available": vcd is not None,
                "one_hop_only": True,
            },
        }
        self.state.last_signal_trace = payload
        self.state.last_signal_trace_action_calls = int(self.state.action_calls)
        return payload

    @observed("tool", "查询本轮知识图谱", stage="diagnose")
    def query_rtl_kg(
        self,
        query_type: Literal[
            "module_interface",
            "module_instances",
            "instance_connections",
            "signal_drivers",
        ],
        module_name: str,
        signal_name: str | None = None,
        instance_name: str | None = None,
    ) -> dict[str, Any]:
        kg = self.state.kg_service
        if kg is None or not getattr(kg, "is_enabled", lambda: False)():
            return {"status": "kg_unavailable", "query_type": query_type}
        try:
            if query_type == "module_interface":
                result = kg.query(kg_templates.GET_MODULE_INTERFACE, {"module_name": module_name}, limit=50)
            elif query_type == "module_instances":
                result = kg.query(kg_templates.GET_CHILD_MODULE_CONTEXT, {"parent_module": module_name}, limit=100)
            elif query_type == "instance_connections":
                result = kg.query(
                    kg_templates.GET_INSTANCE_CONTEXT,
                    {"parent_module": module_name, "child_module": "", "instance_name": instance_name or ""},
                    limit=100,
                )
            else:
                if not signal_name:
                    return {"status": "error", "error": "signal_name is required for signal_drivers"}
                result = kg.query(
                    kg_templates.GET_SIGNAL_DEBUG_CONTEXT,
                    {"module_name": module_name, "signal_name": signal_name},
                    limit=100,
                )
            self.state.observed_tb_or_spec_or_kg = True
            return {"status": "ok", "query_type": query_type, "result": result}
        except Exception as exc:  # noqa: BLE001
            return {"status": "error", "query_type": query_type, "error": f"{type(exc).__name__}: {exc}"}

    # ------------------------------------------------------------------
    # Check / patch / correction tools
    # ------------------------------------------------------------------

    def _refresh_trace(self, sim_output: str) -> dict[str, Any]:
        report, _blocks = build_trace_report(
            rtl_path=self.state.input.rtl_path,
            sim_log_json=sim_output,
            output_dir=self.state.input.debug_workdir,
            planner_module_name=self.state.input.module_name,
            runtime_top_module=self.state.input.top_module or self.state.input.module_name,
            kg_service=self.state.kg_service,
            kg_hop_depth=self.state.input.kg_hop_depth,
        )
        path = self.state.input.debug_workdir / "trace_report.json"
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self.state.last_trace_summary = self._trace_summary(report)
        divergence = report.get("first_divergence")
        if isinstance(divergence, dict):
            self.state.last_divergence_summary = divergence
            if divergence.get("status") == "ok" and divergence.get("first_divergence"):
                self.state.observed_real_divergence = True
        return report

    def _trace_payload_for_sim(self, sim_output: str) -> dict[str, Any]:
        try:
            report, _blocks = build_trace_report(
                rtl_path=self.state.input.rtl_path,
                sim_log_json=sim_output,
                output_dir=self.state.input.debug_workdir,
                planner_module_name=self.state.input.module_name,
                runtime_top_module=self.state.input.top_module or self.state.input.module_name,
                kg_service=self.state.kg_service,
                kg_hop_depth=self.state.input.kg_hop_depth,
            )
        except Exception as exc:  # noqa: BLE001
            if self.state.logger is not None:
                self.state.logger.debug("Could not build after-patch trace payload for acceptance judge: %s", exc)
            return {"trace_summary": None, "divergence_summary": None, "error": f"{type(exc).__name__}: {exc}"}
        divergence = report.get("first_divergence")
        return {
            "trace_summary": self._trace_summary(report),
            "divergence_summary": divergence if isinstance(divergence, dict) else None,
            "error": None,
        }

    def _trace_summary(self, report: dict[str, Any]) -> dict[str, Any]:
        chains = ((report.get("value_backtrace") or {}).get("chains") or [])[:3]
        return {
            "trace_report_path": str(self.state.input.debug_workdir / "trace_report.json"),
            "fail_time": report.get("fail_time"),
            "planner_module_name": report.get("planner_module_name") or self.state.input.module_name,
            "runtime_top_module": report.get("runtime_top_module") or self.state.input.top_module or self.state.input.module_name,
            "dut_instance": report.get("dut_instance"),
            "runtime_rtl_path": report.get("runtime_rtl_path") or str(self.state.input.rtl_path),
            "sampling_event": report.get("sampling_event"),
            "total_mismatches": report.get("total_mismatches"),
            "first_failure": report.get("first_failure"),
            "root_failure": report.get("root_failure"),
            "edge_active_failure": report.get("edge_active_failure"),
            "first_divergence": report.get("first_divergence"),
            "required_next_tool": report.get("required_next_tool"),
            "ignored_tb_metrics": report.get("ignored_tb_metrics"),
            "raw_fail_outputs": report.get("raw_fail_outputs"),
            "top_diagnosis": (report.get("diagnostic_narrative") or [None])[0],
            "fail_outputs": report.get("fail_outputs"),
            "suspect_blocks": (report.get("suspect_blocks") or [])[:8],
            "timing_hints": report.get("timing_hints"),
            "alignment_diagnosis": report.get("alignment_diagnosis"),
            "value_backtrace_summary": [
                {
                    "sig": chain.get("sig"),
                    "expected": chain.get("expected"),
                    "actual": chain.get("actual"),
                    "steps": [
                        {
                            "signal": step.get("signal"),
                            "driver_block_id": step.get("driver_block_id"),
                            "classification": step.get("classification"),
                            "reason": step.get("reason"),
                            "rhs_observed_values": step.get("rhs_observed_values"),
                            "condition_values": step.get("condition_values"),
                        }
                        for step in (chain.get("chain") or [])[:4]
                        if isinstance(step, dict)
                    ],
                }
                for chain in chains
                if isinstance(chain, dict)
            ],
            "vcd_available": report.get("vcd_available"),
        }

    @observed("tool", "检查当前设计候选", stage="repair")
    def run_check(
        self,
        mode: Literal["lint", "module_sim", "top_sim", "trace_summary", "wave_window", "first_divergence"],
        module_name: str | None = None,
        signals: list[str] | None = None,
        time_window: tuple[int, int] | None = None,
    ) -> dict[str, Any]:
        del module_name
        if mode == "wave_window":
            return {"status": "unsupported_in_v1", "mode": mode}
        if mode == "lint":
            ok, output = self._scoped_syntax(
                str(self.state.input.rtl_path),
                top_module=self.state.input.top_module or self.state.input.module_name,
            )
            self.state.observed_trace_or_sim = True
            return {
                "status": "ok",
                "mode": mode,
                "is_pass": bool(ok),
                "output_excerpt": _summarize_command_json(output, max_chars=5000),
            }
        if mode in {"module_sim", "top_sim"}:
            if mode == "module_sim" and self.state.input.repair_scope == "repo":
                mode = "top_sim"
            is_pass, mismatch_count, sim_output = self._review_current()
            sim_path = self.state.input.debug_workdir / "debug_sim_output.json"
            sim_path.write_text(sim_output, encoding="utf-8")
            first_fail = _extract_first_fail_time(sim_output)
            self.state.last_sim = SimSnapshot(
                is_pass=bool(is_pass),
                mismatch_count=int(mismatch_count),
                first_fail_time=first_fail,
                sim_output_path=str(sim_path),
            )
            self.state.last_sim_output = sim_output
            trace_summary = None
            if not is_pass and int(mismatch_count) > 0:
                trace_summary = self._trace_summary(self._refresh_trace(sim_output))
                self.state.last_trace_summary = trace_summary
            self.state.observed_trace_or_sim = True
            return {
                "status": "ok",
                "mode": mode,
                "is_pass": bool(is_pass),
                "mismatch_count": int(mismatch_count),
                "first_fail_time": first_fail,
                "sim_output_path": str(sim_path),
                "sim_output_excerpt": _summarize_command_json(sim_output),
                "trace_summary": trace_summary,
            }
        if mode == "first_divergence":
            if (
                signals is None
                and time_window is None
                and self.state.last_signal_trace
                and int(self.state.last_signal_trace_action_calls) == int(self.state.action_calls)
            ):
                divergence = self.state.last_divergence_summary or {}
                first = (
                    divergence.get("first_divergence")
                    if isinstance(divergence.get("first_divergence"), dict)
                    else {}
                )
                return {
                    "status": "ok",
                    "mode": mode,
                    "cached": True,
                    "first_divergence": {
                        "status": divergence.get("status") or "ok",
                        "sampling_event": divergence.get("sampling_event"),
                        "first_divergence": first,
                        "trace_report_path": str(self.state.input.debug_workdir / "trace_report.json"),
                    },
                }
            sim_output = self.state.last_sim_output or self.state.input.sim_failed_log
            result = build_first_divergence_report(
                rtl_path=self.state.input.rtl_path,
                output_dir=self.state.input.debug_workdir,
                runtime_top_module=self.state.input.top_module or self.state.input.module_name,
                sim_log_json=sim_output,
                signals=signals,
                time_window=tuple(time_window) if time_window is not None else None,
                sampling_mode="auto",
            )
            self.state.observed_trace_or_sim = True
            self.state.last_divergence_summary = result
            if result.get("status") in {"ok", "stable_values_match_but_tb_edge_mismatch"} and result.get("first_divergence"):
                self.state.observed_real_divergence = True
            return {"status": result.get("status", "ok"), "mode": mode, "first_divergence": result}
        report_path = self.state.input.debug_workdir / "trace_report.json"
        if report_path.exists():
            report = json.loads(report_path.read_text(encoding="utf-8"))
        elif self.state.last_sim_output:
            report = self._refresh_trace(self.state.last_sim_output)
        else:
            report = self._refresh_trace(self.state.input.sim_failed_log)
        self.state.observed_trace_or_sim = True
        summary = self._trace_summary(report)
        self.state.last_trace_summary = summary
        return {"status": "ok", "mode": mode, "trace_summary": summary}

    @observed("tool", "尝试修改当前设计", stage="repair")
    def apply_patch(
        self,
        patches: list[dict[str, Any]],
        reason: str,
        expected_effect: str,
        protected_invariants_checked: list[str] | None = None,
        preserve_plan: str | None = None,
        syntax_retry_of: str | None = None,
        verify: bool = True,
        rollback_on_fail: bool = True,
        action_type: str = "apply_patch",
        block_id: str | None = None,
    ) -> dict[str, Any]:
        def reject(message: str) -> dict[str, Any]:
            step = int(self.state.patch_attempt_id) + 1
            result = {"status": "rejected", "reason": message, "is_action_executed": False}
            entry = {
                "step": step,
                "patch_attempt_id": None,
                "action_step": None,
                "action_type": action_type,
                "block_id": block_id,
                "candidate_id": syntax_retry_of,
                "target": {},
                "patch_count": 0,
                "patch_summary": message,
                "hypothesis": reason or message,
                "evidence": {
                    "latest_trace_summary": self.state.last_trace_summary,
                    "last_divergence_summary": self.state.last_divergence_summary,
                },
                "changed_signals": [],
                "before": {
                    "mismatch_count": int(self.state.last_sim.mismatch_count),
                    "first_fail_time": self.state.last_sim.first_fail_time,
                },
                "after": {"status": "rejected", "reason": message},
                "effect": "rejected",
                "lesson": message,
                "patches": patches,
                "result": result,
            }
            self._record_patch_entry(entry)
            return result

        if not isinstance(patches, list) or not patches:
            return reject("patches must be a non-empty list.")

        parsed_items: list[tuple[Patch, Path]] = []
        warnings: list[str] = []
        try:
            for item in patches:
                patch = Patch.model_validate(item)
                if patch.end_line < patch.start_line:
                    return reject(f"Invalid patch range {patch.start_line}-{patch.end_line}.")
                edit_path, warning = self._resolve_edit_path(patch.path)
                if edit_path is None:
                    return reject(warning)
                forbidden = self._forbidden_edit_reason(edit_path)
                if forbidden:
                    return reject(forbidden)
                parsed_items.append((patch, edit_path.resolve()))
                if warning:
                    warnings.append(warning)
        except Exception as exc:  # noqa: BLE001
            return reject(f"Invalid patch payload: {type(exc).__name__}: {exc}")

        grouped: dict[Path, list[tuple[int, Patch]]] = {}
        edited_paths: list[Path] = []
        for idx, (patch, edit_path) in enumerate(parsed_items):
            if self.state.input.repair_scope != "repo" and edit_path != self.state.input.rtl_path.resolve():
                return reject("RepoReAct module-scope can only patch the current debug RTL file.")
            grouped.setdefault(edit_path, []).append((idx, patch))
            if edit_path not in edited_paths:
                edited_paths.append(edit_path)

        before_text_by_path: dict[Path, str] = {}
        lines_by_path: dict[Path, list[str]] = {}
        old_text_by_patch: dict[int, str] = {}
        try:
            for path in edited_paths:
                before_text = path.read_text(encoding="utf-8")
                before_text_by_path[path] = before_text
                lines = before_text.splitlines()
                lines_by_path[path] = lines
                ranges = sorted((patch.start_line, patch.end_line) for _, patch in grouped[path])
                for pos, (start_line, end_line) in enumerate(ranges):
                    if end_line > len(lines):
                        return reject(f"Invalid patch range {start_line}-{end_line}; RTL has {len(lines)} lines: {path}")
                    if pos > 0 and start_line <= ranges[pos - 1][1]:
                        return reject(f"Overlapping patch ranges in {path}: {ranges[pos - 1][0]}-{ranges[pos - 1][1]} and {start_line}-{end_line}.")
                for idx, patch in grouped[path]:
                    old_text_by_patch[idx] = "\n".join(lines[patch.start_line - 1 : patch.end_line])
        except OSError as exc:
            return reject(f"Could not read RTL for patching: {exc}")

        max_actions = max(1, int(self.state.input.max_steps or 1))
        if int(self.state.action_calls) >= max_actions:
            return self._record_rejected_action(
                action_type=action_type,
                step=int(self.state.action_calls) + 1,
                reason=f"Repair action budget exhausted: max_steps={max_actions}.",
                hypothesis=reason,
                patches=patches,
                block_id=block_id,
            )

        before_sim = self.state.last_sim
        before_sim_output = self.state.last_sim_output
        before_summary = {
            "mismatch_count": int(before_sim.mismatch_count),
            "first_fail_time": before_sim.first_fail_time,
            "top_diagnosis": self.state.last_trace_summary.get("top_diagnosis"),
        }
        before_metrics = _parse_sim_metrics(before_sim_output)
        after_metrics_holder: dict[str, dict[str, Any]] = {"metrics": {}}

        parsed = [patch for patch, _path in parsed_items]
        patch_summary = "; ".join(self._summarize_code(patch.new_text) for patch in parsed)
        changed_signals = sorted(
            {
                sig
                for idx, patch in enumerate(parsed)
                for sig in (
                    self._changed_signals_for_patch(old_text_by_patch[idx])
                    + self._changed_signals_for_patch(patch.new_text)
                )
            }
        )
        file_targets = [
            {
                "path": str(path),
                "start_line": min(patch.start_line for _idx, patch in grouped[path]),
                "end_line": max(patch.end_line for _idx, patch in grouped[path]),
            }
            for path in edited_paths
        ]
        legacy_target = file_targets[0] if file_targets else {"path": "", "start_line": None, "end_line": None}
        target = {
            "path": legacy_target["path"],
            "start_line": legacy_target["start_line"],
            "end_line": legacy_target["end_line"],
            "files": file_targets,
        }
        if block_id:
            target["block_id"] = block_id

        patch_diff: list[dict[str, Any]] = []
        rtl_surrounding_context: list[dict[str, Any]] = []
        for idx, (patch, edit_path) in enumerate(parsed_items):
            old_text = old_text_by_patch[idx]
            new_text = patch.new_text.rstrip("\n")
            new_line_count = len(new_text.splitlines())
            patch_diff.append(
                {
                    "path": str(edit_path),
                    "original_start_line": int(patch.start_line),
                    "original_end_line": int(patch.end_line),
                    "candidate_start_line": int(patch.start_line),
                    "candidate_end_line": int(patch.start_line) + new_line_count - 1,
                    "old_text": old_text,
                    "new_text": new_text,
                    "unified_diff": _complete_patch_diff(edit_path, patch, old_text),
                }
            )
            rtl_surrounding_context.append(
                _patch_surrounding_context(
                    edit_path,
                    patch,
                    lines_by_path[edit_path],
                    context_lines=20,
                )
            )

        target_signature = {
            "action_type": action_type,
            "block_id": block_id,
            "files": sorted(
                (
                    str(item["path"]),
                    int(item["start_line"]),
                    int(item["end_line"]),
                )
                for item in file_targets
            ),
        }
        syntax_candidate: dict[str, Any] | None = None
        retry_ordinal = 0
        if syntax_retry_of:
            syntax_candidate = self.state.syntax_candidates.get(str(syntax_retry_of))
            if syntax_candidate is None:
                return reject(f"Unknown syntax retry candidate: {syntax_retry_of}.")
            if syntax_candidate.get("status") != "pending":
                return reject(
                    f"Syntax retry candidate {syntax_retry_of} is not pending "
                    f"(status={syntax_candidate.get('status')})."
                )
            if syntax_candidate.get("target_signature") != target_signature:
                return reject(
                    f"Syntax retry candidate {syntax_retry_of} must keep the same action type and target ranges."
                )
            retries_used = int(syntax_candidate.get("retries_used") or 0)
            if retries_used >= 2:
                syntax_candidate["status"] = "exhausted"
                return reject(f"Syntax retry candidate {syntax_retry_of} exhausted its two retries.")
            retry_ordinal = retries_used + 1

        needs_preserve, relevant_invariants = self._patch_requires_preserve_plan(
            action_type=action_type,
            changed_signals=changed_signals,
            block_id=block_id,
        )

        consume=getattr(self.state.sim_reviewer,'consume_candidate',None)
        if callable(consume):
            try:consume()
            except ValueError:return reject('Candidate budget exhausted; no further HDL edit is allowed.')
            verify=True
        self.state.patch_attempt_id += 1
        patch_attempt_id = int(self.state.patch_attempt_id)
        candidate_id = str(syntax_retry_of or f"syntax_candidate_{patch_attempt_id:04d}")
        action_step: int | None = None

        before_snapshot = self.state.journal.snapshot_files(
            step=patch_attempt_id,
            label="before",
            files=edited_paths,
        )
        for path in edited_paths:
            lines = list(lines_by_path[path])
            for _idx, patch in sorted(grouped[path], key=lambda item: item[1].start_line, reverse=True):
                replacement = patch.new_text.rstrip("\n").splitlines()
                lines[patch.start_line - 1 : patch.end_line] = replacement
            original = before_text_by_path[path]
            path.write_text("\n".join(lines) + ("\n" if original.endswith("\n") else ""), encoding="utf-8")
        after_snapshot = self.state.journal.snapshot_files(
            step=patch_attempt_id,
            label="after",
            files=edited_paths,
        )

        def restore_edited_files() -> None:
            for path, text in before_text_by_path.items():
                path.write_text(text, encoding="utf-8")

        result: dict[str, Any] = {
            "status": "pending",
            "is_action_executed": True,
            "committed": False,
            "candidate_id": candidate_id,
            "patch_attempt_id": patch_attempt_id,
            "action_step": None,
            "syntax_retries_used": retry_ordinal,
            "syntax_retries_remaining": max(0, 2 - retry_ordinal),
            "reason": reason,
            "expected_effect": expected_effect,
            "warnings": warnings,
            "before_snapshot": before_snapshot,
            "after_snapshot": after_snapshot,
        }

        def persist_patch_result(final_result: dict[str, Any]) -> None:
            effect = self._classify_effect(
                before_sim,
                final_result,
                before_metrics=before_metrics,
                after_metrics=after_metrics_holder.get("metrics", {}),
            )
            entry = {
                "step": action_step if action_step is not None else patch_attempt_id,
                "patch_attempt_id": patch_attempt_id,
                "action_step": action_step,
                "action_type": action_type,
                "block_id": block_id,
                "candidate_id": candidate_id,
                "target": target,
                "patch_count": len(parsed),
                "patch_summary": patch_summary,
                "hypothesis": f"{reason} Expected effect: {expected_effect}",
                "evidence": {
                    "before": before_summary,
                    "latest_trace_summary": self.state.last_trace_summary,
                    "last_divergence_summary": self.state.last_divergence_summary,
                },
                "changed_signals": changed_signals,
                "protected_invariants_checked": protected_invariants_checked or [],
                "preserve_plan": preserve_plan,
                "relevant_protected_invariants": relevant_invariants,
                "before": before_summary,
                "before_metrics": before_metrics,
                "after": {
                    "status": final_result.get("status"),
                    "is_pass": bool(final_result.get("is_pass")),
                    "mismatch_count": final_result.get("mismatch_count"),
                    "first_fail_time": final_result.get("first_fail_time"),
                    "rollback_reason": final_result.get("rollback_reason"),
                },
                "after_metrics": after_metrics_holder.get("metrics", {}),
                "metric_delta": _metric_delta(before_metrics, after_metrics_holder.get("metrics", {})),
                "effect": effect,
                "lesson": self._lesson_for_effect(effect, final_result),
                "patches": patches,
                "result": final_result,
            }
            self._record_patch_entry(entry)

        def commit_functional_action() -> None:
            nonlocal action_step
            self.state.action_calls += 1
            action_step = int(self.state.action_calls)
            result["action_step"] = action_step
            result["committed"] = True
            if syntax_candidate is not None:
                syntax_candidate["status"] = "resolved"
                syntax_candidate["retries_used"] = retry_ordinal
                syntax_candidate["resolved_attempt_id"] = patch_attempt_id

        if not verify:
            commit_functional_action()
            result["status"] = "kept_unverified"
            persist_patch_result(result)
            return result

        lint_ok, lint_output = self._scoped_syntax(
            str(self.state.input.rtl_path),
            top_module=self.state.input.top_module or self.state.input.module_name,
        )
        result["lint_pass"] = bool(lint_ok)
        result["lint_output_excerpt"] = _summarize_command_json(lint_output, max_chars=5000)
        if not lint_ok:
            restore_edited_files()
            syntax_errors = _extract_syntax_errors(lint_output)
            if syntax_candidate is None:
                syntax_candidate = {
                    "candidate_id": candidate_id,
                    "status": "pending",
                    "action_type": action_type,
                    "block_id": block_id,
                    "target_signature": target_signature,
                    "retries_used": 0,
                    "initial_attempt_id": patch_attempt_id,
                }
                self.state.syntax_candidates[candidate_id] = syntax_candidate
            else:
                syntax_candidate["retries_used"] = retry_ordinal
            syntax_candidate["last_attempt_id"] = patch_attempt_id
            syntax_candidate["last_syntax_errors"] = syntax_errors
            syntax_candidate["last_lint_output_excerpt"] = result["lint_output_excerpt"]
            retries_used = int(syntax_candidate.get("retries_used") or 0)
            retries_remaining = max(0, 2 - retries_used)
            if retries_remaining == 0:
                syntax_candidate["status"] = "exhausted"
                result["status"] = "syntax_retry_exhausted"
            else:
                result["status"] = "syntax_retry_required"
            result["is_action_executed"] = False
            result["syntax_errors"] = syntax_errors
            result["syntax_retries_used"] = retries_used
            result["syntax_retries_remaining"] = retries_remaining
            result["rollback_reason"] = "lint_failed"
            persist_patch_result(result)
            return result

        commit_functional_action()

        if self.state.input.repair_mode == "syntax":
            result["status"] = "pass"
            result["is_pass"] = True
            result["mismatch_count"] = 0
            result["first_fail_time"] = None
            result["success_condition"] = "lint_passed"
            self.state.last_sim = SimSnapshot(
                is_pass=True,
                mismatch_count=0,
                first_fail_time=None,
                sim_output_path="",
            )
            persist_patch_result(result)
            return result

        is_pass, mismatch_count, sim_output = self._review_current()
        after_metrics_holder["metrics"] = _parse_sim_metrics(sim_output)
        sim_path = self.state.input.debug_workdir / "debug_sim_output.json"
        sim_path.write_text(sim_output, encoding="utf-8")
        first_fail = _extract_first_fail_time(sim_output)
        result.update(
            {
                "is_pass": bool(is_pass),
                "mismatch_count": int(mismatch_count),
                "first_fail_time": first_fail,
                "sim_output_path": str(sim_path),
                "sim_output_excerpt": _summarize_command_json(sim_output),
            }
        )

        rollback_reason = ""
        if not is_pass and int(mismatch_count) == 0:
            rollback_reason = "top_sim_failed_without_mismatch_count" if self.state.input.repair_scope == "repo" else "module_sim_failed_without_mismatch_count"
        elif int(before_sim.mismatch_count) > 0 and int(mismatch_count) > int(before_sim.mismatch_count):
            rollback_reason = "mismatch_count_regressed"
        elif (
            before_sim.first_fail_time is not None
            and first_fail is not None
            and int(first_fail) < int(before_sim.first_fail_time)
        ):
            rollback_reason = "first_fail_time_regressed"

        mixed_acceptance = None
        if rollback_reason == "mismatch_count_regressed":
            mixed_acceptance = _promising_mixed_signal_delta(before_metrics, after_metrics_holder.get("metrics", {}))
            if mixed_acceptance:
                result["mixed_signal_delta"] = mixed_acceptance

        after_trace_payload: dict[str, Any] = {"trace_summary": None, "divergence_summary": None, "error": None}
        if rollback_reason and rollback_on_fail and int(mismatch_count) > 0:
            after_trace_payload = self._trace_payload_for_sim(sim_output)
            result["after_trace_summary"] = after_trace_payload.get("trace_summary")
            result["after_divergence_summary"] = after_trace_payload.get("divergence_summary")
            if after_trace_payload.get("error"):
                result["after_trace_error"] = after_trace_payload.get("error")

        def judge_rollback_candidate(candidate_reason: str, candidate_mixed_acceptance: dict[str, Any] | None) -> str:
            result["script_rollback_recommendation"] = candidate_reason
            evidence_keywords = list(changed_signals)
            evidence_keywords.extend(
                str(signal)
                for metrics in (before_metrics, after_metrics_holder.get("metrics", {}))
                for signal in ((metrics.get("per_signal") or {}).keys())
            )
            for trace in (
                self.state.last_trace_summary,
                self.state.last_divergence_summary,
                after_trace_payload.get("trace_summary"),
                after_trace_payload.get("divergence_summary"),
            ):
                if not isinstance(trace, dict):
                    continue
                for key in ("signal", "root_signal", "output"):
                    if trace.get(key):
                        evidence_keywords.append(str(trace[key]))
                for section_name in ("first_failure", "root_failure", "edge_active_failure", "first_divergence"):
                    section = trace.get(section_name)
                    if isinstance(section, dict):
                        for key in ("signal", "root_signal", "output"):
                            if section.get(key):
                                evidence_keywords.append(str(section[key]))
            evidence_keywords.extend(
                [
                    self.state.input.module_name,
                    self.state.input.top_module,
                    "posedge",
                    "negedge",
                    "sampling",
                    "mismatch",
                    "assert",
                    "done",
                    "reset",
                    "rst",
                    "clk",
                ]
            )
            acceptance_payload = {
                "module": self.state.input.module_name,
                "action_type": action_type,
                "block_id": block_id,
                "target": target,
                "changed_signals": changed_signals,
                "reason": reason,
                "expected_effect": expected_effect,
                "patch_summary": patch_summary,
                "patch_diff": patch_diff,
                "rtl_surrounding_context": rtl_surrounding_context,
                "authoritative_context": self._authoritative_context_for_acceptance(evidence_keywords),
                "recent_repair_ledger": self._repair_ledger(limit=5),
                "script_rollback_recommendation": candidate_reason,
                "before": before_summary,
                "after": {
                    "is_pass": bool(is_pass),
                    "mismatch_count": int(mismatch_count),
                    "first_fail_time": first_fail,
                },
                "after_sim_output_excerpt": result.get("sim_output_excerpt"),
                "before_metrics": before_metrics,
                "after_metrics": after_metrics_holder.get("metrics", {}),
                "metric_delta": _metric_delta(before_metrics, after_metrics_holder.get("metrics", {})),
                "mixed_signal_delta": candidate_mixed_acceptance,
                "before_trace_summary": self.state.last_trace_summary,
                "before_divergence_summary": self.state.last_divergence_summary,
                "after_trace_summary": after_trace_payload.get("trace_summary"),
                "after_divergence_summary": after_trace_payload.get("divergence_summary"),
                "after_trace_error": after_trace_payload.get("error"),
                "latest_trace_summary": self.state.last_trace_summary,
                "last_divergence_summary": self.state.last_divergence_summary,
                "protected_invariants_checked": protected_invariants_checked or [],
                "preserve_plan": preserve_plan,
                "relevant_protected_invariants": relevant_invariants,
            }
            acceptance = self._llm_patch_acceptance_decision(acceptance_payload)
            if acceptance is None:
                acceptance = self._fallback_acceptance_decision(
                    before_sim=before_sim,
                    first_fail=first_fail,
                    before_metrics=before_metrics,
                    after_metrics=after_metrics_holder.get("metrics", {}),
                    mixed_acceptance=candidate_mixed_acceptance,
                )
            result["acceptance_decision"] = acceptance
            if acceptance.get("decision") == "keep":
                result["acceptance_reason"] = acceptance.get("source") or "llm_kept_functional_regression"
                return ""
            return candidate_reason

        if rollback_reason and rollback_on_fail:
            rollback_reason = judge_rollback_candidate(rollback_reason, mixed_acceptance)

        if rollback_reason and rollback_on_fail:
            restore_edited_files()
            self.state.last_sim = before_sim
            self.state.last_sim_output = before_sim_output
            if before_sim_output:
                sim_path.write_text(before_sim_output, encoding="utf-8")
            result["status"] = "rollback"
            result["rollback_reason"] = rollback_reason
            persist_patch_result(result)
            return result

        self.state.last_sim = SimSnapshot(
            is_pass=bool(is_pass),
            mismatch_count=int(mismatch_count),
            first_fail_time=first_fail,
            sim_output_path=str(sim_path),
        )
        self.state.last_sim_output = sim_output

        if is_pass and int(mismatch_count) == 0:
            result["status"] = "pass"
            self.state.neutral_kept = 0
        else:
            report = self._refresh_trace(sim_output) if int(mismatch_count) > 0 else {}
            result["trace_summary"] = self._trace_summary(report) if report else None
            if result["trace_summary"]:
                self.state.last_trace_summary = result["trace_summary"]
            improved = int(mismatch_count) < int(before_sim.mismatch_count)
            fail_moved_later = (
                before_sim.first_fail_time is not None
                and first_fail is not None
                and int(first_fail) > int(before_sim.first_fail_time)
            )
            acceptance = result.get("acceptance_decision") if isinstance(result.get("acceptance_decision"), dict) else {}
            accepted_keep = acceptance.get("decision") == "keep"
            if improved or fail_moved_later or mixed_acceptance or accepted_keep:
                result["status"] = "improved"
                self.state.neutral_kept = 0
            else:
                self.state.neutral_kept += 1
                result["status"] = "neutral"
                if self.state.neutral_kept > 2 and rollback_on_fail:
                    neutral_rollback_reason = judge_rollback_candidate("too_many_neutral_patches", None)
                    if neutral_rollback_reason:
                        restore_edited_files()
                        self.state.last_sim = before_sim
                        self.state.last_sim_output = before_sim_output
                        if before_sim_output:
                            sim_path.write_text(before_sim_output, encoding="utf-8")
                        result["status"] = "rollback"
                        result["rollback_reason"] = neutral_rollback_reason
                        persist_patch_result(result)
                        return result
                    result["status"] = "improved"
                    self.state.neutral_kept = 0

        persist_patch_result(result)
        return result

    def _planning_block_ids(self, module_name: str) -> tuple[set[str], dict[str, dict[str, Any]]]:
        context = self._load_sidecar_module_semantics(module_name, {"skeleton"})
        skeleton = context.get("skeleton_artifact")
        if not isinstance(skeleton, dict):
            return set(), {}
        by_id: dict[str, dict[str, Any]] = {}
        for item in skeleton.get("structural_blocks") or []:
            if not isinstance(item, dict):
                continue
            planning_block_id = str(
                item.get("planning_block_id")
                or item.get("block_id")
                or item.get("block_label")
                or ""
            )
            if planning_block_id:
                by_id[planning_block_id] = item
        return set(by_id), by_id

    def _rank_editable_block_candidates(
        self,
        *,
        module_name: str,
        rtl_path: Path,
        blocks: list[Any],
        planning_block: dict[str, Any] | None = None,
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        last_trace = self.state.last_signal_trace or {}
        recent_ids: list[str] = []
        focus_signals: set[str] = set()
        if str(last_trace.get("module") or "") == module_name:
            recent_ids = [
                str(item.get("rtl_block_id") or "")
                for item in last_trace.get("editable_rtl_blocks") or []
                if isinstance(item, dict) and item.get("rtl_block_id")
            ]
            focus = (
                last_trace.get("focus_context")
                if isinstance(last_trace.get("focus_context"), dict)
                else {}
            )
            focus_signals = {
                _signal_leaf(str(item)).lower()
                for item in focus.get("signals") or []
                if str(item)
            }

        planning_text = (
            json.dumps(planning_block, ensure_ascii=False, default=str).lower()
            if isinstance(planning_block, dict)
            else ""
        )

        def score(block: Any) -> tuple[int, int, int, str]:
            symbols = {
                str(item).lower()
                for item in (*block.writes, *block.reads)
            }
            planning_overlap = sum(
                1
                for signal in symbols
                if planning_text
                and re.search(
                    rf"\b{re.escape(signal)}\b",
                    planning_text,
                )
            )
            return (
                1 if str(block.id) in recent_ids else 0,
                planning_overlap,
                len(symbols & focus_signals),
                str(block.id),
            )

        ranked = sorted(
            blocks,
            key=lambda block: (
                -score(block)[0],
                -score(block)[1],
                -score(block)[2],
                score(block)[3],
            ),
        )
        return [
            self._rtl_block_payload(module_name, rtl_path, block)
            for block in ranked[: max(1, int(limit))]
        ]

    @observed("tool", "替换选定代码块", stage="repair")
    def replace_block(
        self,
        block_id: str | None,
        new_code: str,
        reason: str,
        expected_effect: str,
        protected_invariants_checked: list[str] | None = None,
        preserve_plan: str | None = None,
        syntax_retry_of: str | None = None,
        verify: bool = True,
        rollback_on_fail: bool = True,
        module_name: str | None = None,
        rtl_block_id: str | None = None,
    ) -> dict[str, Any]:
        if block_id and rtl_block_id and str(block_id) != str(rtl_block_id):
            return {
                "status": "conflicting_block_ids",
                "is_action_executed": False,
                "block_id": str(block_id),
                "rtl_block_id": str(rtl_block_id),
                "message": "block_id and rtl_block_id must identify the same RTL parser block.",
            }
        selected_rtl_block_id = str(rtl_block_id or block_id or "")
        target_module = str(module_name or self.state.input.module_name)
        legacy_call = module_name is None or rtl_block_id is None
        max_actions = max(1, int(self.state.input.max_steps or 1))
        if int(self.state.action_calls) >= max_actions:
            return self._record_rejected_action(
                action_type="replace_block",
                step=int(self.state.action_calls) + 1,
                reason=f"Repair action budget exhausted: max_steps={max_actions}.",
                hypothesis=reason,
                block_id=selected_rtl_block_id,
            )
        if not selected_rtl_block_id:
            return self._record_rejected_action(
                action_type="replace_block",
                step=int(self.state.action_calls) + 1,
                reason="replace_block requires a non-empty rtl_block_id.",
                hypothesis=reason,
                block_id=selected_rtl_block_id,
            )
        if not str(new_code).strip():
            return self._record_rejected_action(
                action_type="replace_block",
                step=int(self.state.action_calls) + 1,
                reason="replace_block requires non-empty new_code.",
                hypothesis=reason,
                block_id=selected_rtl_block_id,
            )

        rtl_path, _module_metadata, path_warnings = self._resolve_module_rtl_path(
            target_module
        )
        if rtl_path is None:
            result = self._record_rejected_action(
                action_type="replace_block",
                step=int(self.state.action_calls) + 1,
                reason=f"RTL source for module {target_module!r} was not found.",
                hypothesis=reason,
                block_id=selected_rtl_block_id,
            )
            result["module_name"] = target_module
            result["rtl_block_id"] = selected_rtl_block_id
            result["rtl_block_ref"] = f"{target_module}:{selected_rtl_block_id}"
            result["warnings"] = path_warnings
            return result
        try:
            rtl_text = rtl_path.read_text(encoding="utf-8")
        except OSError as exc:
            return self._record_rejected_action(
                action_type="replace_block",
                step=int(self.state.action_calls) + 1,
                reason=f"Could not read RTL for block replacement: {exc}",
                hypothesis=reason,
                block_id=selected_rtl_block_id,
            )

        module_text, line_offset = self._extract_module_source(rtl_text, target_module)
        blocks = parse_rtl_blocks(module_text)
        if line_offset:
            blocks = [
                replace(
                    item,
                    start_line=item.start_line + line_offset,
                    end_line=item.end_line + line_offset,
                )
                for item in blocks
            ]
        block = next(
            (item for item in blocks if item.id == selected_rtl_block_id),
            None,
        )
        if block is None:
            planning_ids, planning_by_id = self._planning_block_ids(target_module)
            detected_namespace = (
                "planning_block_id"
                if selected_rtl_block_id in planning_ids
                else "unknown_rtl_block_id"
            )
            valid_blocks = self._rank_editable_block_candidates(
                module_name=target_module,
                rtl_path=rtl_path,
                blocks=blocks,
                planning_block=planning_by_id.get(selected_rtl_block_id),
                limit=8,
            )
            result = self._record_rejected_action(
                action_type="replace_block",
                step=int(self.state.action_calls) + 1,
                reason=(
                    f"{selected_rtl_block_id!r} is a planning block id and cannot be edited directly."
                    if detected_namespace == "planning_block_id"
                    else f"RTL block id {selected_rtl_block_id!r} was not found in module {target_module!r}."
                ),
                hypothesis=reason,
                block_id=selected_rtl_block_id,
            )
            result.update(
                {
                    "status": "invalid_rtl_block_id",
                    "module_name": target_module,
                    "provided": selected_rtl_block_id,
                    "rtl_block_id": selected_rtl_block_id,
                    "rtl_block_ref": f"{target_module}:{selected_rtl_block_id}",
                    "detected_namespace": detected_namespace,
                    "message": (
                        f"{selected_rtl_block_id} is a ModuleSkeleton planning block and cannot be edited directly."
                        if detected_namespace == "planning_block_id"
                        else "Use one of the current RTL parser block ids returned in valid_editable_blocks."
                    ),
                    "valid_editable_blocks": valid_blocks,
                    "warnings": path_warnings,
                }
            )
            return result
        if block.kind not in {"always", "assign"}:
            return self._record_rejected_action(
                action_type="replace_block",
                step=int(self.state.action_calls) + 1,
                reason=f"RTL block id {selected_rtl_block_id!r} has unsupported kind {block.kind!r}.",
                hypothesis=reason,
                block_id=selected_rtl_block_id,
            )

        patch = {
            "path": str(rtl_path),
            "start_line": int(block.start_line),
            "end_line": int(block.end_line),
            "new_text": str(new_code).rstrip("\n"),
        }
        result = self.apply_patch(
            patches=[patch],
            reason=reason,
            expected_effect=expected_effect,
            protected_invariants_checked=protected_invariants_checked,
            preserve_plan=preserve_plan,
            syntax_retry_of=syntax_retry_of,
            verify=verify,
            rollback_on_fail=rollback_on_fail,
            action_type="replace_block",
            block_id=selected_rtl_block_id,
        )
        result = dict(result)
        result["module_name"] = target_module
        result["rtl_block_id"] = selected_rtl_block_id
        result["rtl_block_ref"] = f"{target_module}:{selected_rtl_block_id}"
        result["warnings"] = [
            *(result.get("warnings") or []),
            *path_warnings,
            *(
                [
                    "Deprecated replace_block compatibility path used; pass module_name and rtl_block_id."
                ]
                if legacy_call
                else []
            ),
        ]
        return result

    def record_correction(
        self,
        correction_type: Literal[
            "wrong_contract",
            "wrong_module_plan",
            "wrong_interface",
            "wrong_timing",
            "wrong_dependency",
            "wrong_retrieval",
        ],
        module_name: str,
        original_artifact: str,
        problem: str,
        evidence: list[str],
        override: dict[str, Any],
    ) -> dict[str, Any]:
        if not self.state.observed_stage_artifact:
            return {
                "status": "rejected",
                "reason": "record_correction blocked: read the relevant stage_artifact first.",
            }
        output_root = self.state.input.output_root or (self.state.input.workspace_root.parent / "outputs")
        root = output_root / "planning_corrections"
        root.mkdir(parents=True, exist_ok=True)
        payload = {
            "step": self.state.action_calls,
            "module": module_name,
            "correction_type": correction_type,
            "original_artifact": original_artifact,
            "problem": problem,
            "evidence": evidence,
            "override": override,
        }
        with open(root / "correction_journal.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
        target_by_type = {
            "wrong_contract": "plan_overrides.json",
            "wrong_module_plan": "plan_overrides.json",
            "wrong_interface": "interface_overrides.json",
            "wrong_timing": "timing_overrides.json",
            "wrong_dependency": "dependency_overrides.json",
            "wrong_retrieval": "plan_overrides.json",
        }
        target = root / target_by_type[correction_type]
        data: dict[str, Any] = {}
        if target.exists():
            try:
                data = json.loads(target.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                data = {}
        data.setdefault(module_name, []).append(payload)
        target.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self.state.journal.append_jsonl("correction_journal.jsonl", payload)
        self.persist_memory_snapshot()
        return {"status": "ok", "path": str(target), "correction": payload}

    def load_known_corrections(self) -> list[dict[str, Any]]:
        output_root = self.state.input.output_root
        if output_root is None:
            return []
        path = output_root / "planning_corrections" / "correction_journal.jsonl"
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                obj = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            if obj.get("module") == self.state.input.module_name:
                rows.append(obj)
        return rows[-10:]

    def memory_snapshot(self) -> dict[str, Any]:
        snapshot = {
            "schema": "repo_react_memory_snapshot.v1",
            "module": self.state.input.module_name,
            "paths": {
                "rtl": str(self.state.input.rtl_path),
                "merged_file": str(self.state.input.merged_file),
                "debug_workdir": str(self.state.input.debug_workdir),
                "repo_react_root": str(self.state.journal.root),
                "trace_report": str(self.state.input.debug_workdir / "trace_report.json"),
            },
            "current_rtl_hash": self._current_rtl_hash(),
            "latest_trace_summary": self.state.last_trace_summary,
            "last_divergence_summary": self.state.last_divergence_summary,
            "last_signal_trace": self.state.last_signal_trace,
            "pending_post_patch_trace": self.state.pending_post_patch_trace,
            "recent_repair_journal": self._recent_repair_entries_slim(limit=3),
            "recent_edited_ranges": self._recent_edited_ranges(limit=5),
            "recent_replaced_blocks": self._recent_replaced_blocks(limit=5),
            "failed_directions": self._directions_by_effect({"rejected", "regressed"}, limit=5),
            "promising_directions": self._directions_by_effect({"passed", "improved"}, limit=5),
            "known_planning_corrections": self.load_known_corrections(),
            "last_sim": self.state.last_sim.model_dump(),
            "action_calls": int(self.state.action_calls),
            "patch_attempts": int(self.state.patch_attempt_id),
            "pending_syntax_candidates": [
                {
                    "candidate_id": candidate_id,
                    "action_type": candidate.get("action_type"),
                    "target_signature": candidate.get("target_signature"),
                    "retries_used": int(candidate.get("retries_used") or 0),
                    "last_syntax_errors": candidate.get("last_syntax_errors") or [],
                }
                for candidate_id, candidate in self.state.syntax_candidates.items()
                if candidate.get("status") == "pending"
            ],
            "max_steps": int(self.state.input.max_steps),
            "observed_context": {
                "rtl": bool(self.state.observed_rtl),
                "trace_or_sim": bool(self.state.observed_trace_or_sim),
                "tb_spec_or_kg": bool(self.state.observed_tb_or_spec_or_kg),
                "spec_or_stage": bool(self.state.observed_spec_or_stage),
                "stage_artifact": bool(self.state.observed_stage_artifact),
                "real_divergence": bool(self.state.observed_real_divergence),
            },
        }
        snapshot["repair_ledger"] = self._repair_ledger(limit=10)
        snapshot["protected_invariants"] = self._protected_invariants()
        snapshot["unsafe_directions"] = self._unsafe_directions(limit=8)
        snapshot["next_local_target"] = self._next_local_target(snapshot["protected_invariants"])
        snapshot["high_coupling_blocks"] = self._high_coupling_blocks(limit=8)
        snapshot["causal_memory_brief"] = self._causal_memory_brief(snapshot)
        return snapshot

    def persist_memory_snapshot(self) -> dict[str, Any]:
        snapshot = self.memory_snapshot()
        self.state.journal.write_json("repo_react_memory_snapshot.json", snapshot)
        debug_dir = self.state.input.debug_workdir
        debug_dir.mkdir(parents=True, exist_ok=True)
        text = json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n"
        (debug_dir / "repo_react_memory_snapshot.json").write_text(text, encoding="utf-8")
        # Backward-compatible name used by the previous RTLEditor debug loop.
        (debug_dir / "debug_memory_snapshot.json").write_text(text, encoding="utf-8")
        return snapshot

    def read_memory(
        self,
        kind: Literal[
            "snapshot",
            "brief",
            "repair_journal",
            "repair_ledger",
            "protected_invariants",
            "unsafe_directions",
            "failed_directions",
            "promising_directions",
            "next_target",
            "raw_snapshot",
        ] = "snapshot",
        limit: int = 5,
    ) -> dict[str, Any]:
        snapshot = self.persist_memory_snapshot()
        brief = snapshot.get("causal_memory_brief") or self._causal_memory_brief(snapshot)
        if kind in {"snapshot", "brief"}:
            return {"status": "ok", "kind": kind, "brief": brief}
        if kind == "raw_snapshot":
            return {"status": "ok", "kind": kind, "snapshot": snapshot}
        if kind == "repair_journal":
            return {"status": "ok", "kind": kind, "entries": self._recent_repair_entries(limit=limit)}
        if kind == "repair_ledger":
            return {"status": "ok", "kind": kind, "ledger": self._repair_ledger(limit=limit)}
        if kind == "protected_invariants":
            return {"status": "ok", "kind": kind, "protected_invariants": self._protected_invariants(limit=limit)}
        if kind == "unsafe_directions":
            return {"status": "ok", "kind": kind, "unsafe_directions": self._unsafe_directions(limit=limit)}
        if kind == "next_target":
            return {"status": "ok", "kind": kind, "next_local_target": brief.get("next_local_target")}
        if kind == "failed_directions":
            return {"status": "ok", "kind": kind, "directions": self._directions_by_effect({"rejected", "regressed"}, limit=limit)}
        return {"status": "ok", "kind": kind, "directions": self._directions_by_effect({"passed", "improved"}, limit=limit)}
