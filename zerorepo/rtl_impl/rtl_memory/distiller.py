from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .schemas import RTLMemoryHeader
from .store import RTLMemoryStore


def _slug(text: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.$-]+", "_", str(text).strip())
    value = re.sub(r"_+", "_", value).strip("_")
    return value[:80] or "memory"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}
    return obj if isinstance(obj, dict) else {}


def _artifact_rel(path: str | Path, root: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(root.resolve()).as_posix())
    except Exception:  # noqa: BLE001
        return str(path)


def _module_family(module: str) -> str:
    parts = [p for p in re.split(r"[_.$-]+", module) if p]
    if not parts:
        return ""
    if parts[0] in {"sd", "sdc"}:
        return "sdc"
    if parts[0] in {"wb", "wishbone"}:
        return "wishbone"
    return parts[0]


class RTLMemoryDistiller:
    """Rule-based distiller for causal RTL memory markdown files."""

    def __init__(self, workspace_root: str | Path, *, logger: Any | None = None) -> None:
        self.workspace_root = Path(workspace_root)
        self.store = RTLMemoryStore.from_workspace(self.workspace_root)
        self.logger = logger

    def distill_codex_result(self, *, module: str, result: dict, binding: dict) -> Path:
        """Preserve an objective draft, not a fabricated legacy patch entry."""
        from .ledger import atomic, digest
        draft = dict(schema_version='rtl-memory-codex-draft-v1', status='draft', module=module,
                     candidate_id=result['candidate_id'], reason=result.get('reason',''),
                     changed_files=result.get('diff',{}), lint_pass=result.get('lint_pass'),
                     simulation_completed=bool(result.get('sim_completed')),
                     verdict='pass' if result.get('sim_completed') and result.get('is_pass') else 'fail' if result.get('sim_completed') or result.get('lint_pass') is False else 'unverified',
                     evidence_binding=binding, limitations=['待维护者核对适用条件与来源，不能自动公开或认定收益'])
        path=self.workspace_root/'memory_drafts'/(digest(draft)+'.json')
        if not path.exists(): atomic(path,draft)
        return path

    def distill_patch_entry(
        self,
        *,
        module: str,
        entry: dict[str, Any],
        debug_workdir: str | Path,
        repo_react_root: str | Path,
    ) -> Path | None:
        effect = str(entry.get("effect") or "")
        if effect not in {"passed", "improved", "regressed", "syntax_failed"}:
            return None
        evidence = entry.get("evidence") if isinstance(entry.get("evidence"), dict) else {}
        trace = evidence.get("latest_trace_summary") if isinstance(evidence.get("latest_trace_summary"), dict) else {}
        divergence = evidence.get("last_divergence_summary") if isinstance(evidence.get("last_divergence_summary"), dict) else {}
        first_div = divergence.get("first_divergence") if isinstance(divergence.get("first_divergence"), dict) else {}
        changed_signals = [str(s) for s in (entry.get("changed_signals") or []) if s]
        signal = str(first_div.get("signal") or "")
        if not signal:
            first_failure = trace.get("first_failure") if isinstance(trace.get("first_failure"), dict) else {}
            signal = str(first_failure.get("sig") or first_failure.get("signal") or "")
        signals = sorted(set(([signal] if signal else []) + changed_signals))[:12]
        if len([x for x in [trace, divergence, entry.get("before_metrics"), entry.get("after_metrics")] if x]) < 2:
            return None

        memory_type = "repair_outcome" if effect in {"passed", "improved"} else "negative_direction"
        outcome = "pass" if effect == "passed" else effect
        alignment = str(first_div.get("classification") or trace.get("alignment") or "")
        failure_type = self._infer_failure_type(entry, trace, divergence)
        family = _module_family(module)
        suffix = _slug("_".join([module, signal or "rtl", outcome, str(entry.get("step") or "")]))
        prefix = "debug" if memory_type == "repair_outcome" else "avoid"
        memory_id = f"{prefix}_{suffix}"
        description = self._description_for_patch(module, signal, effect, entry)
        header = RTLMemoryHeader(
            memory_id=memory_id,
            type=memory_type,  # type: ignore[arg-type]
            stage="debug",
            module=module,
            module_family=family,
            signals=signals,
            failure_type=failure_type,
            alignment=alignment,
            outcome=outcome,
            confidence=0.9 if effect == "passed" else 0.72 if effect == "improved" else 0.68,
            verified_by=(["lint"] if evidence.get('lint_pass') is True else [])
                        + (["module_sim"] if evidence.get('module_sim_pass') is True else [])
                        + (["trace"] if trace or divergence else []),
            source_artifacts=[
                _artifact_rel(Path(debug_workdir) / "trace_report.json", self.workspace_root),
                _artifact_rel(Path(repo_react_root) / "patch_journal.jsonl", self.workspace_root),
            ],
            description=description,
            trigger_signals=signals,
            trigger_failure_type=failure_type,
            trigger_alignment=alignment,
            risk_signals=changed_signals,
            patch_pattern=str(entry.get("patch_summary") or entry.get("hypothesis") or "")[:180],
            anti_trigger=(
                "Do not reuse when current first divergence, affected signals, or timing alignment differ."
                if memory_type == "repair_outcome"
                else "Avoid this direction unless new evidence distinguishes the current failure."
            ),
        )
        body = self._patch_body(module=module, signal=signal, effect=effect, entry=entry, trace=trace, divergence=divergence)
        return self.store.upsert_memory(header, body)

    def distill_correction(
        self,
        *,
        correction: dict[str, Any],
        source_path: str | Path,
    ) -> Path | None:
        module = str(correction.get("module") or correction.get("module_name") or "")
        correction_type = str(correction.get("correction_type") or "")
        problem = str(correction.get("problem") or "")
        if not module or not correction_type or not problem:
            return None
        memory_id = f"correction_{_slug(module)}_{_slug(correction_type)}"
        description = f"{module}: {problem[:140]}"
        header = RTLMemoryHeader(
            memory_id=memory_id,
            type="planning_correction",
            stage="planning",
            module=module,
            module_family=_module_family(module),
            failure_type="plan_bug",
            outcome="correction",
            confidence=0.62,
            verified_by=["record_correction"],
            source_artifacts=[_artifact_rel(source_path, self.workspace_root)],
            description=description,
        )
        evidence = correction.get("evidence") if isinstance(correction.get("evidence"), list) else []
        body = (
            "## Problem\n\n"
            f"{problem}\n\n"
            "## Evidence\n\n"
            + "\n".join(f"- {item}" for item in evidence[:8])
            + "\n\n## Corrective Rule\n\n"
            f"{json.dumps(correction.get('override') or {}, indent=2, ensure_ascii=False)}\n"
        )
        return self.store.upsert_memory(header, body)

    def distill_merge_report(self, *, report_path: str | Path) -> Path | None:
        path = Path(report_path)
        report = _read_json(path)
        module = str(report.get("module") or path.stem.replace("_merge_report", ""))
        if not module:
            return None
        static_summary = report.get("static_check_summary") if isinstance(report.get("static_check_summary"), dict) else {}
        lint_summary = report.get("lint_summary") if isinstance(report.get("lint_summary"), dict) else {}
        warnings = [str(x) for x in (static_summary.get("warnings") or [])]
        errors = [str(x) for x in (static_summary.get("errors") or [])]
        ownership = report.get("signal_ownership") if isinstance(report.get("signal_ownership"), dict) else {}
        required_includes = [str(x) for x in (report.get("required_includes") or [])]
        lint_pass = bool(lint_summary.get("is_pass"))
        if not (lint_pass or warnings or errors or required_includes or ownership):
            return None

        signals = [sig for sig, info in ownership.items() if isinstance(info, dict) and len(info.get("drivers") or []) > 1][:12]
        if not signals:
            signals = list(ownership.keys())[:12]
        outcome = "lint_pass" if lint_pass else "merge_check_issue"
        memory_id = f"merge_{_slug(module)}_{_slug(outcome)}"
        description = self._description_for_merge(module, lint_pass, warnings, errors, required_includes)
        header = RTLMemoryHeader(
            memory_id=memory_id,
            type="merge_rule",
            stage="stage6_merge",
            module=module,
            module_family=_module_family(module),
            signals=signals,
            outcome=outcome,
            confidence=0.72 if lint_pass else 0.58,
            verified_by=["stage6_static_check", "lint"] if lint_pass else ["stage6_static_check"],
            source_artifacts=[_artifact_rel(path, self.workspace_root)],
            description=description,
        )
        body = self._merge_body(module, lint_pass, warnings, errors, required_includes, signals)
        return self.store.upsert_memory(header, body)

    def _infer_failure_type(self, entry: dict[str, Any], trace: dict[str, Any], divergence: dict[str, Any]) -> str:
        text = " ".join(
            str(x or "")
            for x in [
                entry.get("hypothesis"),
                entry.get("lesson"),
                trace.get("top_diagnosis"),
                divergence.get("status"),
                divergence.get("sampling_mode"),
            ]
        ).lower()
        if "timing" in text or "late" in text or "early" in text or "edge" in text or "lag" in text or "lead" in text:
            return "timing_bug"
        if "interface" in text or "port" in text or "connection" in text:
            return "interface_bug"
        if "plan" in text or "stage" in text:
            return "plan_bug"
        if "logic" in text or "value" in text:
            return "local_logic_bug"
        return "unknown"

    def _description_for_patch(self, module: str, signal: str, effect: str, entry: dict[str, Any]) -> str:
        lesson = str(entry.get("lesson") or "").strip()
        target = signal or ", ".join(str(s) for s in (entry.get("changed_signals") or [])[:3])
        if lesson:
            return f"{module}: {target} {effect}; {lesson[:120]}"
        return f"{module}: {target} patch outcome was {effect}."

    def _patch_body(
        self,
        *,
        module: str,
        signal: str,
        effect: str,
        entry: dict[str, Any],
        trace: dict[str, Any],
        divergence: dict[str, Any],
    ) -> str:
        before = entry.get("before") if isinstance(entry.get("before"), dict) else {}
        after = entry.get("after") if isinstance(entry.get("after"), dict) else {}
        metric_delta = entry.get("metric_delta") if isinstance(entry.get("metric_delta"), dict) else {}
        return (
            "## 触发条件\n\n"
            f"- Module: `{module}`\n"
            f"- Signal: `{signal or 'targeted RTL'}`\n"
            f"- Effect: `{effect}`\n"
            f"- First divergence: `{json.dumps(divergence.get('first_divergence') or {}, ensure_ascii=False)}`\n\n"
            "## 不适用条件\n\n"
            "- Do not reuse if affected signals, timing alignment, or spec intent differ.\n"
            "- Do not reuse without reading current RTL/spec evidence.\n\n"
            "## 补丁模式\n\n"
            f"{entry.get('patch_summary') or entry.get('hypothesis') or ''}\n\n"
            "## 验证特征\n\n"
            f"- Before mismatch count: `{before.get('mismatch_count')}`\n"
            f"- After mismatch count: `{after.get('mismatch_count')}`\n"
            f"- Metric delta: `{json.dumps(metric_delta, ensure_ascii=False)}`\n\n"
            "## 复用约束\n\n"
            f"{entry.get('lesson') or 'Reuse only when the current trace evidence matches this failure pattern.'}\n\n"
            "## Problem\n\n"
            f"`{module}` showed a debug failure around `{signal or 'targeted RTL'}`.\n\n"
            "## Evidence\n\n"
            f"- Effect: `{effect}`\n"
            f"- Before mismatch count: `{before.get('mismatch_count')}`\n"
            f"- After mismatch count: `{after.get('mismatch_count')}`\n"
            f"- First divergence: `{json.dumps(divergence.get('first_divergence') or {}, ensure_ascii=False)}`\n"
            f"- Trace root failure: `{json.dumps(trace.get('root_failure') or trace.get('first_failure') or {}, ensure_ascii=False)}`\n"
            f"- Metric delta: `{json.dumps(metric_delta, ensure_ascii=False)}`\n\n"
            "## Patch Summary\n\n"
            f"{entry.get('patch_summary') or entry.get('hypothesis') or ''}\n\n"
            "## Lesson\n\n"
            f"{entry.get('lesson') or 'Reuse only when the current trace evidence matches this failure pattern.'}\n\n"
            "## Reuse Constraints\n\n"
            "- Read current RTL/spec evidence before applying a similar patch.\n"
            "- Do not reuse if affected signals or timing alignment differ.\n"
        )

    def _description_for_merge(
        self,
        module: str,
        lint_pass: bool,
        warnings: list[str],
        errors: list[str],
        required_includes: list[str],
    ) -> str:
        if errors:
            return f"{module}: Stage6 merge issue; first static error: {errors[0][:120]}"
        if warnings:
            return f"{module}: Stage6 merge warning; {warnings[0][:120]}"
        if required_includes:
            return f"{module}: include required global defines: {', '.join(required_includes[:4])}."
        if lint_pass:
            return f"{module}: successful Stage6 merge pattern with lint/static checks passing."
        return f"{module}: Stage6 merge rule."

    def _merge_body(
        self,
        module: str,
        lint_pass: bool,
        warnings: list[str],
        errors: list[str],
        required_includes: list[str],
        signals: list[str],
    ) -> str:
        return (
            "## Pattern\n\n"
            f"Stage6 merge for `{module}` produced outcome `{'lint_pass' if lint_pass else 'merge_check_issue'}`.\n\n"
            "## Evidence\n\n"
            + "\n".join(f"- Static error: {item}" for item in errors[:5])
            + ("\n" if errors else "")
            + "\n".join(f"- Static warning: {item}" for item in warnings[:5])
            + ("\n" if warnings else "")
            + "\n".join(f"- Required include: `{item}`" for item in required_includes[:8])
            + ("\n" if required_includes else "")
            + "\n".join(f"- Ownership signal: `{item}`" for item in signals[:8])
            + "\n\n## How To Use\n\n"
            "- Read fragments, fragment contracts, spec, global defines, and KG child context before drafting.\n"
            "- Preserve single-owner semantics for status/control outputs when possible.\n"
            "- Re-run static structure checks and lint before commit.\n"
        )


__all__ = ["RTLMemoryDistiller"]
