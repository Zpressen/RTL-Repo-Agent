from __future__ import annotations

import asyncio
import json
import re
import shutil
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from zerorepo.rtl_impl.debug_agent.bash_tools import CommandResult
from zerorepo.rtl_impl.debug_agent.sim_reviewer import SimReviewer, check_syntax
from zerorepo.rtl_impl.debug_agent.trace_report import (
    _find_clock_signal,
    _resolve_ref_instance as _resolve_ref_instance_static,
    _vcd_time_range,
    build_first_divergence_report,
    build_trace_report,
    list_vcd_signals_query,
    resolve_vcd_signal,
    sample_vcd_signals,
)
from zerorepo.rtl_impl.debug_agent.trace_slicer import parse_rtl_blocks
from zerorepo.rtl_impl.kg_agent import kg_query_templates as kg_templates

from .journal import RepoReActJournal
from .schemas import Patch, RepoReActInput, SimSnapshot

try:
    from vcdvcd import VCDVCD  # type: ignore[import-not-found]
except Exception:  # noqa: BLE001
    VCDVCD = None  # type: ignore[assignment]


_FAIL_TIME_HINT_RE = re.compile(
    r"Hint:\s+Output\s+'[^']+'\s+has\s+\d+\s+mismatches\.\s+First mismatch occurred at time\s+(?P<t>\d+)\.",
    re.MULTILINE,
)
_FAIL_TIME_FAILED_RE = re.compile(
    r"SIMULATION FAILED - \d+\s+MISMATCHES DETECTED.*FIRST AT TIME\s+(?P<t>\d+)",
    re.IGNORECASE,
)
_SIM_HINT_RE = re.compile(
    r"Hint:\s+Output\s+'(?P<sig>[^']+)'\s+has\s+(?P<count>\d+)\s+mismatches\.\s+First mismatch occurred at time\s+(?P<time>\d+)\.",
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


def _extract_first_fail_time(sim_log_json: str) -> int | None:
    try:
        obj = json.loads(sim_log_json)
    except Exception:  # noqa: BLE001
        return None
    stdout = str(obj.get("stdout") or "")
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
    stdout = str(obj.get("stdout") or sim_log_json)
    per_signal: dict[str, dict[str, int]] = {}
    for match in _SIM_HINT_RE.finditer(stdout):
        per_signal[match.group("sig")] = {
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
        "Lint/syntax failures are handled outside this judge. For functional simulation failures, do not use a single total mismatch counter mechanically.\n"
        "Keep a patch when it is a plausible stepping stone: it fixes the target timing/value, moves the first real failure much later, preserves known good changes, or reveals a missing spec/clear condition that should be repaired next.\n"
        "Rollback a patch when it clearly destroys a protected invariant, only makes the target worse, has no plausible causal progress, or masks the original bug with unrelated behavior.\n"
        "Pay attention to conflicts between aggregate mismatch counters and per-signal deltas. Testbench metric signals named errors_* are less important than real DUT/ref outputs.\n"
        "Return only JSON with this shape:\n"
        "{\"decision\":\"keep|rollback\",\"confidence\":0.0,\"reason\":\"brief\",\"next_focus\":\"brief next repair target if kept\"}\n\n"
        "<patch_acceptance_payload_json>\n"
        f"{json.dumps(payload, indent=2, ensure_ascii=False)}\n"
        "</patch_acceptance_payload_json>\n"
    )


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
    neutral_kept: int = 0
    observed_rtl: bool = False
    observed_trace_or_sim: bool = False
    observed_tb_or_spec_or_kg: bool = False
    observed_spec_or_stage: bool = False
    observed_stage_artifact: bool = False
    observed_real_divergence: bool = False
    last_trace_summary: dict[str, Any] = field(default_factory=dict)
    last_divergence_summary: dict[str, Any] = field(default_factory=dict)


class RepoReActTools:
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
            if effect not in {"regressed", "syntax_failed"}:
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
            elif effect == "syntax_failed":
                text = f"Syntax-failed direction at step {row.get('step')}: {summary}"
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
                return {"status": "error", "error": f"Unknown stage artifact: {name}", "known": sorted(STAGE_ARTIFACTS)}
            target = self._resolve_read_path(rel)
            if target is None or not target.is_file():
                return {"status": "error", "error": f"Stage artifact not found: {name}", "path": rel}
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

    def list_vcd_signals(self, pattern: str = "", scope: str = "", limit: int = 100) -> dict[str, Any]:
        vcd = self._load_vcd()
        if vcd is None:
            return {"status": "missing_vcd", "error": "wave.vcd not found or vcdvcd unavailable"}
        self.state.observed_trace_or_sim = True
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

    def _trace_summary(self, report: dict[str, Any]) -> dict[str, Any]:
        chains = ((report.get("value_backtrace") or {}).get("chains") or [])[:3]
        return {
            "trace_report_path": str(self.state.input.debug_workdir / "trace_report.json"),
            "fail_time": report.get("fail_time"),
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

    def run_check(
        self,
        mode: Literal["lint", "module_sim", "top_sim", "trace_summary", "wave_window", "first_divergence"],
        module_name: str | None = None,
        signals: list[str] | None = None,
        time_window: tuple[int, int] | None = None,
    ) -> dict[str, Any]:
        del module_name
        if mode in {"top_sim", "wave_window"}:
            return {"status": "unsupported_in_v1", "mode": mode}
        if mode == "lint":
            ok, output = check_syntax(str(self.state.input.rtl_path), top_module=self.state.input.module_name)
            self.state.observed_trace_or_sim = True
            return {
                "status": "ok",
                "mode": mode,
                "is_pass": bool(ok),
                "output_excerpt": _summarize_command_json(output, max_chars=5000),
            }
        if mode == "module_sim":
            is_pass, mismatch_count, sim_output = self.state.sim_reviewer.review()
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
            sim_output = self.state.last_sim_output or self.state.input.sim_failed_log
            result = build_first_divergence_report(
                rtl_path=self.state.input.rtl_path,
                output_dir=self.state.input.debug_workdir,
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

    def apply_patch(
        self,
        patches: list[dict[str, Any]],
        reason: str,
        expected_effect: str,
        protected_invariants_checked: list[str] | None = None,
        preserve_plan: str | None = None,
        verify: bool = True,
        rollback_on_fail: bool = True,
        action_type: str = "apply_patch",
        block_id: str | None = None,
    ) -> dict[str, Any]:
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
        self.state.action_calls += 1
        step = self.state.action_calls

        def reject(message: str) -> dict[str, Any]:
            result = {"status": "rejected", "reason": message, "is_action_executed": False}
            entry = {
                "step": step,
                "action_type": action_type,
                "block_id": block_id,
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

        if not self.state.observed_rtl:
            return reject("Patch blocked: current RTL source has not been read in this ReAct session.")
        if not self.state.observed_trace_or_sim:
            return reject("Patch blocked: trace_report or simulation result has not been observed in this ReAct session.")
        if self.state.input.repair_mode != "syntax" and not self.state.observed_tb_or_spec_or_kg:
            return reject("Patch blocked: inspect testbench, specification, or KG before patching.")
        if self.state.input.repair_mode == "functional" and not self.state.observed_real_divergence:
            return reject(
                "Patch blocked: observe real or edge-active DUT/ref divergence with run_check(mode=\"first_divergence\") before functional RTL edits."
            )
        if self.state.input.repair_mode == "functional" and not self.state.observed_spec_or_stage:
            return reject(
                "Patch blocked: inspect original spec or stage/spec artifact before functional RTL edits."
            )
        if not isinstance(patches, list) or not patches:
            return reject("patches must be a non-empty list.")

        parsed: list[Patch] = []
        edit_paths: list[Path] = []
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
                parsed.append(patch)
                edit_paths.append(edit_path)
                if warning:
                    warnings.append(warning)
        except Exception as exc:  # noqa: BLE001
            return reject(f"Invalid patch payload: {type(exc).__name__}: {exc}")

        if len(set(edit_paths)) != 1 or edit_paths[0].resolve() != self.state.input.rtl_path.resolve():
            return reject("RepoReAct v1 can only patch the current debug RTL file.")

        rtl_path = self.state.input.rtl_path
        before_text = rtl_path.read_text(encoding="utf-8")
        before_sim = self.state.last_sim
        before_sim_output = self.state.last_sim_output
        before_summary = {
            "mismatch_count": int(before_sim.mismatch_count),
            "first_fail_time": before_sim.first_fail_time,
            "top_diagnosis": self.state.last_trace_summary.get("top_diagnosis"),
        }
        before_metrics = _parse_sim_metrics(before_sim_output)
        after_metrics_holder: dict[str, dict[str, Any]] = {"metrics": {}}

        lines = before_text.splitlines()
        for patch in parsed:
            if patch.end_line > len(lines):
                return reject(f"Invalid patch range {patch.start_line}-{patch.end_line}; RTL has {len(lines)} lines.")

        old_text_by_patch = {
            idx: "\n".join(lines[patch.start_line - 1 : patch.end_line])
            for idx, patch in enumerate(parsed)
        }
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
        target = {
            "path": str(rtl_path),
            "start_line": min(p.start_line for p in parsed),
            "end_line": max(p.end_line for p in parsed),
        }
        if block_id:
            target["block_id"] = block_id

        needs_preserve, relevant_invariants = self._patch_requires_preserve_plan(
            action_type=action_type,
            changed_signals=changed_signals,
            block_id=block_id,
        )
        if self.state.input.repair_mode == "functional" and needs_preserve:
            if not protected_invariants_checked or not str(preserve_plan or "").strip():
                return reject(
                    "Patch blocked: this edit may affect protected invariants or a high-coupling block. "
                    "Provide protected_invariants_checked and preserve_plan."
                )

        before_snapshot = self.state.journal.snapshot_files(step=step, label="before", files=[rtl_path])
        normalized = sorted(parsed, key=lambda item: item.start_line, reverse=True)
        for patch in normalized:
            replacement = patch.new_text.rstrip("\n").splitlines()
            lines[patch.start_line - 1 : patch.end_line] = replacement
        rtl_path.write_text("\n".join(lines) + ("\n" if before_text.endswith("\n") else ""), encoding="utf-8")
        after_snapshot = self.state.journal.snapshot_files(step=step, label="after", files=[rtl_path])

        result: dict[str, Any] = {
            "status": "pending",
            "is_action_executed": True,
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
                "step": step,
                "action_type": action_type,
                "block_id": block_id,
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

        if not verify:
            result["status"] = "kept_unverified"
            persist_patch_result(result)
            return result

        lint_ok, lint_output = check_syntax(str(rtl_path), top_module=self.state.input.module_name)
        result["lint_pass"] = bool(lint_ok)
        result["lint_output_excerpt"] = _summarize_command_json(lint_output, max_chars=5000)
        if not lint_ok:
            if rollback_on_fail:
                rtl_path.write_text(before_text, encoding="utf-8")
            result["status"] = "rollback"
            result["rollback_reason"] = "lint_failed"
            persist_patch_result(result)
            return result

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

        is_pass, mismatch_count, sim_output = self.state.sim_reviewer.review()
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
            rollback_reason = "module_sim_failed_without_mismatch_count"
        elif int(mismatch_count) > int(before_sim.mismatch_count):
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

        if rollback_reason and rollback_on_fail:
            result["script_rollback_recommendation"] = rollback_reason
            acceptance_payload = {
                "module": self.state.input.module_name,
                "action_type": action_type,
                "block_id": block_id,
                "target": target,
                "changed_signals": changed_signals,
                "reason": reason,
                "expected_effect": expected_effect,
                "patch_summary": patch_summary,
                "script_rollback_recommendation": rollback_reason,
                "before": before_summary,
                "after": {
                    "is_pass": bool(is_pass),
                    "mismatch_count": int(mismatch_count),
                    "first_fail_time": first_fail,
                },
                "before_metrics": before_metrics,
                "after_metrics": after_metrics_holder.get("metrics", {}),
                "metric_delta": _metric_delta(before_metrics, after_metrics_holder.get("metrics", {})),
                "mixed_signal_delta": mixed_acceptance,
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
                    mixed_acceptance=mixed_acceptance,
                )
            result["acceptance_decision"] = acceptance
            if acceptance.get("decision") == "keep":
                result["acceptance_reason"] = acceptance.get("source") or "llm_kept_functional_regression"
                rollback_reason = ""

        if rollback_reason and rollback_on_fail:
            rtl_path.write_text(before_text, encoding="utf-8")
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
                    rtl_path.write_text(before_text, encoding="utf-8")
                    self.state.last_sim = before_sim
                    self.state.last_sim_output = before_sim_output
                    if before_sim_output:
                        sim_path.write_text(before_sim_output, encoding="utf-8")
                    result["status"] = "rollback"
                    result["rollback_reason"] = "too_many_neutral_patches"

        persist_patch_result(result)
        return result

    def replace_block(
        self,
        block_id: str,
        new_code: str,
        reason: str,
        expected_effect: str,
        protected_invariants_checked: list[str] | None = None,
        preserve_plan: str | None = None,
        verify: bool = True,
        rollback_on_fail: bool = True,
    ) -> dict[str, Any]:
        max_actions = max(1, int(self.state.input.max_steps or 1))
        if int(self.state.action_calls) >= max_actions:
            return self._record_rejected_action(
                action_type="replace_block",
                step=int(self.state.action_calls) + 1,
                reason=f"Repair action budget exhausted: max_steps={max_actions}.",
                hypothesis=reason,
                block_id=block_id,
            )
        if not block_id or not isinstance(block_id, str):
            self.state.action_calls += 1
            return self._record_rejected_action(
                action_type="replace_block",
                step=self.state.action_calls,
                reason="replace_block requires a non-empty block_id.",
                hypothesis=reason,
                block_id=block_id,
            )
        if not str(new_code).strip():
            self.state.action_calls += 1
            return self._record_rejected_action(
                action_type="replace_block",
                step=self.state.action_calls,
                reason="replace_block requires non-empty new_code.",
                hypothesis=reason,
                block_id=block_id,
            )

        rtl_path = self.state.input.rtl_path
        try:
            rtl_text = rtl_path.read_text(encoding="utf-8")
        except OSError as exc:
            self.state.action_calls += 1
            return self._record_rejected_action(
                action_type="replace_block",
                step=self.state.action_calls,
                reason=f"Could not read RTL for block replacement: {exc}",
                hypothesis=reason,
                block_id=block_id,
            )

        blocks = parse_rtl_blocks(rtl_text)
        block = next((b for b in blocks if b.id == block_id), None)
        if block is None:
            self.state.action_calls += 1
            return self._record_rejected_action(
                action_type="replace_block",
                step=self.state.action_calls,
                reason=f"Block id {block_id!r} was not found in current debug RTL.",
                hypothesis=reason,
                block_id=block_id,
            )
        if block.kind not in {"always", "assign"}:
            self.state.action_calls += 1
            return self._record_rejected_action(
                action_type="replace_block",
                step=self.state.action_calls,
                reason=f"Block id {block_id!r} has unsupported kind {block.kind!r}.",
                hypothesis=reason,
                block_id=block_id,
            )

        patch = {
            "path": str(rtl_path),
            "start_line": int(block.start_line),
            "end_line": int(block.end_line),
            "new_text": str(new_code).rstrip("\n"),
        }
        return self.apply_patch(
            patches=[patch],
            reason=reason,
            expected_effect=expected_effect,
            protected_invariants_checked=protected_invariants_checked,
            preserve_plan=preserve_plan,
            verify=verify,
            rollback_on_fail=rollback_on_fail,
            action_type="replace_block",
            block_id=block_id,
        )

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
            "recent_repair_journal": self._recent_repair_entries(limit=5),
            "recent_edited_ranges": self._recent_edited_ranges(limit=5),
            "recent_replaced_blocks": self._recent_replaced_blocks(limit=5),
            "failed_directions": self._directions_by_effect({"rejected", "syntax_failed", "regressed"}, limit=5),
            "promising_directions": self._directions_by_effect({"passed", "improved"}, limit=5),
            "known_planning_corrections": self.load_known_corrections(),
            "last_sim": self.state.last_sim.model_dump(),
            "action_calls": int(self.state.action_calls),
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
            return {"status": "ok", "kind": kind, "directions": self._directions_by_effect({"rejected", "syntax_failed", "regressed"}, limit=limit)}
        return {"status": "ok", "kind": kind, "directions": self._directions_by_effect({"passed", "improved"}, limit=limit)}
