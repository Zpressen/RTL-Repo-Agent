"""Positive-field, bounded public projection of the recorded E203 debug journal.

This supplements the static export; it never changes an immutable run or exposes
the journal, tool arguments, credentials, or arbitrary trace-report dictionaries.
"""
from __future__ import annotations

import hashlib
import json
import re

from .artifacts import redact, safe_path


def clean(value, limit=1800):
    if not isinstance(value, str):
        return ""
    return redact(value)[:limit]


def project_debug_trace(bundle: dict, rows: list[dict], journal_sha256: str) -> dict:
    trials = []
    known = {e.get("trial_no") for e in bundle["events"] if e.get("trial_no")}
    # A decision belongs to the preceding evaluated candidate, never the next one.
    pending = None
    for row in rows:
        if row.get("event") in {"accept", "rollback"}:
            if pending and row.get("candidate_id") == pending["candidate_id"]:
                pending["decision"] = row["event"]
            continue
        if row.get("event") != "evaluate":
            continue
        r = row.get("result", {})
        no = r.get("validation_trial")
        if no not in known:
            pending = None
            continue
        diff = r.get("diff") or {}
        trace = r.get("trace_summary") or {}
        divergence = trace.get("first_divergence") or {}
        files = []
        for kind in ("added", "modified", "deleted"):
            for path in diff.get(kind, [])[:32]:
                # Only relative RTL names, never any private filesystem path.
                if isinstance(path, str) and re.fullmatch(r"[\w./-]+\.(?:v|sv|vh|svh)", path) and not path.startswith("/") and ".." not in path.split("/"):
                    files.append({"path": path, "change": kind})
        signals = sorted({x["sig"] for x in trace.get("raw_fail_outputs", [])
                          if isinstance(x, dict) and isinstance(x.get("sig"), str)
                          and re.fullmatch(r"[\w.\[\]:$]+", x["sig"])})[:32]
        pending = {
            "trial_no": no,
            "candidate_id": clean(row.get("candidate_id"), 100),
            "intent": clean(r.get("reason") or row.get("reason")),
            "expected_effect": clean(r.get("expected_effect") or row.get("expected_effect")),
            "files": files,
            "lint_pass": r.get("lint_pass") is True,
            "simulation_completed": r.get("sim_completed") is True,
            "verdict": "pass" if r.get("is_pass") is True else "fail" if r.get("is_pass") is False or r.get("lint_pass") is False else "unverified",
            "lint_excerpt": clean(r.get("lint_output_excerpt"), 2400),
            "signals": signals,
            "alignment": "unresolved" if divergence.get("status") == "sampling_alignment_unresolved" else "unrecorded",
            "decision": "unrecorded",
        }
        # This counter is internal to the debug evaluator, not sample statistics.
        for key in ("mismatch_count", "first_fail_time"):
            value = r.get(key)
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                pending[key] = value
        trials.append(pending)
    return {
        "schema_version": "rtl-agent-debug-trace-v1",
        "case_id": bundle["case_id"], "bundle_id": bundle["bundle_id"],
        "source_run_id": bundle["source_run_id"],
        "source_fingerprint": bundle["source_fingerprint"],
        "journal_sha256": journal_sha256,
        "source": "recorded_debug_journal", "trials": trials,
    }


def export_debug_trace(settings, bundle):
    if bundle["case_id"] != "e203":
        return None
    relative = ".zerorepo/workspace/debug_system/e203_exu_alu_system/codex_private/journal/codex_validation_journal.jsonl"
    path = safe_path(settings.source, relative)
    if not path.is_file():
        return None  # A deployment with only public seed data has no journal.
    if path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("Debug journal exceeds public projection budget")
    data = path.read_bytes()
    rows = [json.loads(line) for line in data.splitlines() if line.strip()]
    # Do not attach an unrelated journal to the archive's detailed candidates.
    for v in bundle["validations"]:
        source = v.get("source_candidate") or {}
        candidate = source if isinstance(source, str) else source.get("candidate_id")
        if candidate:
            if not any(r.get("candidate_id") == candidate and r.get("result", {}).get("validation_trial") == v.get("trial_no") for r in rows):
                raise ValueError("Debug journal does not match recorded candidates")
    return project_debug_trace(bundle, rows, hashlib.sha256(data).hexdigest())
