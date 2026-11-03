from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from .bash_tools import CommandResult
from .kg_debug_reads import DebugReadsMaterializer, kg_debug_session_id, kg_dynamic_slice
from .trace_slicer import RtlAssignment, RtlBlock, build_driver_map, dynamic_slice, parse_rtl_assignments, parse_rtl_blocks

try:  # optional dependency
    from vcdvcd import VCDVCD  # type: ignore[import-not-found]
except Exception:  # noqa: BLE001
    VCDVCD = None  # type: ignore[assignment]


_HINT_RE = re.compile(
    r"Hint:\s+Output\s+'(?P<sig>[^']+)'\s+has\s+(?P<cnt>\d+)\s+mismatches\.\s+First mismatch occurred at time\s+(?P<t>\d+)\.",
)
_HINT_RE_ALT = re.compile(
    r"(?:Hint:\s+Output\s+)?'?(?P<sig>[A-Za-z_][A-Za-z0-9_]*)'?(?:\s+signal)?\s+has\s+(?P<cnt>\d+)\s+mismatches\.\s+First(?: mismatch occurred)? at time\s+(?P<t>\d+)",
)
_FAILED_RE = re.compile(r"SIMULATION FAILED - (?P<cnt>\d+)\s+MISMATCHES DETECTED.*FIRST AT TIME\s+(?P<t>\d+)", re.IGNORECASE)
_MISMATCHES_RE = re.compile(r"^Mismatches:\s*(?P<cnt>\d+)\s*in\s*(?P<samples>\d+)\s*samples$", re.MULTILINE)


def _extract_fail_signals_and_time(stdout: str) -> tuple[int | None, list[dict[str, Any]]]:
    fail_outputs: list[dict[str, Any]] = []
    times: list[int] = []
    for m in _HINT_RE.finditer(stdout):
        cnt = int(m.group("cnt"))
        sig = m.group("sig")
        t = int(m.group("t"))
        if cnt > 0:
            fail_outputs.append({"sig": sig, "mismatches": cnt, "time": t})
            times.append(t)

    for m in _HINT_RE_ALT.finditer(stdout):
        cnt = int(m.group("cnt"))
        sig = m.group("sig")
        t = int(m.group("t"))
        if cnt > 0 and not any(item.get("sig") == sig and item.get("time") == t for item in fail_outputs):
            fail_outputs.append({"sig": sig, "mismatches": cnt, "time": t})
            times.append(t)

    if times:
        return min(times), fail_outputs

    m2 = _FAILED_RE.search(stdout)
    if m2:
        t = int(m2.group("t"))
        return t, [{"sig": None, "mismatches": int(m2.group("cnt")), "time": t}]

    return None, []


def _extract_total_mismatches(stdout: str) -> int | None:
    m = _MISMATCHES_RE.search(stdout)
    if m:
        return int(m.group("cnt"))
    return None


def _extract_topmodule_ports(rtl_text: str) -> dict[str, list[str]]:
    # Very small parser: extract ports from the first "module ... ( ... );".
    # Supports both ANSI declarations in the port list and common non-ANSI
    # declarations in the module body.
    m = re.search(r"\bmodule\b\s+[a-zA-Z_][a-zA-Z0-9_]*\s*\(", rtl_text)
    if not m:
        return {"inputs": [], "outputs": []}

    start = m.end()
    end = rtl_text.find(");", start)
    if end == -1:
        return {"inputs": [], "outputs": []}

    portlist = rtl_text[start:end]
    ports: list[tuple[str, str]] = []
    for seg in portlist.split(","):
        seg = seg.strip().strip("()").strip()
        if not seg:
            continue
        mdir = re.search(r"\b(input|output|inout)\b", seg)
        if not mdir:
            continue
        direction = mdir.group(1)
        names = re.findall(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b", seg)
        names = [
            n
            for n in names
            if n
            not in {
                "input",
                "output",
                "inout",
                "wire",
                "logic",
                "reg",
                "bit",
                "signed",
                "unsigned",
                "integer",
                "int",
            }
        ]
        if names:
            ports.append((direction, names[-1]))

    inputs = {name for d, name in ports if d == "input"}
    outputs = {name for d, name in ports if d == "output"}

    body = rtl_text[end + 2 :]
    body_end = body.find("endmodule")
    if body_end != -1:
        body = body[:body_end]
    decl_re = re.compile(
        r"^\s*(input|output|inout)\b\s*(?:wire|logic|reg|signed|unsigned|\s)*"
        r"(?:\[[^\]]+\]\s*)?(?P<names>[^;]+);",
        re.MULTILINE,
    )
    for dm in decl_re.finditer(body):
        direction = dm.group(1)
        names_text = dm.group("names")
        for raw_name in names_text.split(","):
            name_m = re.search(r"\b([A-Za-z_][A-Za-z0-9_]*)\b", raw_name.strip())
            if not name_m:
                continue
            name = name_m.group(1)
            if direction == "input":
                inputs.add(name)
            elif direction == "output":
                outputs.add(name)

    inputs = sorted(inputs)
    outputs = sorted(outputs)
    return {"inputs": inputs, "outputs": outputs}


def _signal_role(sig: str | None, *, module_outputs: Iterable[str] = ()) -> str:
    if not sig:
        return "unknown"
    leaf = sig.split(".")[-1]
    base = re.sub(r"\[[^\]]+\]$", "", leaf)
    if (
        base.startswith("errors_")
        or base.startswith("errortime_")
        or base.startswith("stats")
        or base.startswith("tb_match")
        or base.startswith("wavedrom")
    ):
        return "tb_metric"
    if base.endswith("_dut") or base.endswith("_ref"):
        return "dut_ref_pair"
    if base in set(module_outputs):
        return "module_output"
    return "unknown"


def _filter_root_fail_outputs(
    fail_outputs: list[dict[str, Any]],
    *,
    module_outputs: Iterable[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    real: list[dict[str, Any]] = []
    ignored: list[dict[str, Any]] = []
    outputs = set(module_outputs)
    for item in fail_outputs:
        sig = item.get("sig")
        role = _signal_role(str(sig) if sig else None, module_outputs=outputs)
        enriched = dict(item)
        enriched["signal_role"] = role
        if role == "tb_metric":
            ignored.append(enriched)
        else:
            real.append(enriched)
    return real, ignored
_ATTR_PREFIX = r"(?:\(\*.*?\*\)\s*)*"


def _extract_module_name_from_rtl(rtl_text: str) -> str | None:
    m = re.search(rf"^\s*{_ATTR_PREFIX}module\s+([a-zA-Z_][a-zA-Z0-9_]*)\b", rtl_text, re.MULTILINE)
    if not m:
        return None
    return m.group(1)


def _extract_module_name_from_contract(output_dir: Path) -> str | None:
    p = output_dir / "contract.json"
    if not p.exists():
        return None
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(obj, dict):
        return None
    name = obj.get("module_name")
    if not isinstance(name, str) or not name.strip():
        return None
    return name.strip()


def _find_clock_from_contract(output_dir: Path) -> str | None:
    """Extract the clock signal name from contract.json clocking section."""
    p = output_dir / "contract.json"
    if not p.exists():
        return None
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(obj, dict):
        return None
    clocking = obj.get("clocking")
    if not isinstance(clocking, dict):
        return None
    clock = clocking.get("clock")
    if isinstance(clock, dict):
        name = clock.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
    return None


_CLOCK_CANDIDATES: tuple[str, ...] = ("clk", "wclk", "rclk", "clock", "clk_i", "sys_clk")


def _find_clock_signal(vcd: Any, *, preferred_name: str | None = None) -> str | None:
    """Find a clock signal in *vcd* by trying common clock leaf names.

    Tries *preferred_name* first (e.g. from contract), then the common
    candidates in ``_CLOCK_CANDIDATES``.
    """
    candidates: list[str] = []
    if preferred_name:
        candidates.append(preferred_name)
    candidates.extend(_CLOCK_CANDIDATES)
    seen: set[str] = set()
    for name in candidates:
        if name in seen:
            continue
        seen.add(name)
        sig = _vcd_find_signal(vcd, name)
        if sig is not None:
            return sig
    return None


def _extract_dut_instance_name(tb_text: str, *, module_name: str) -> str | None:
    # Best-effort: match `<module_name> <inst>(` in the testbench.
    m = re.search(rf"\b{re.escape(module_name)}\b\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", tb_text)
    if m:
        return m.group(1)

    # Fallback: in non-golden mode we usually instantiate as `<something> dut ( ... )`.
    if re.search(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b\s+dut\s*\(", tb_text):
        return "dut"
    return None


def _extract_tb_sampling_event(tb_text: str) -> dict[str, str] | None:
    """Find the clock edge used by the testbench mismatch counter."""
    clocked_always = re.compile(
        r"\balways\s*@\(\s*(?P<edge>posedge|negedge)\s+"
        r"(?P<clock>[A-Za-z_][A-Za-z0-9_]*)\s*\)\s*begin(?P<body>.*?)\bend\b",
        re.DOTALL,
    )
    for match in clocked_always.finditer(tb_text):
        event = {
            "edge": match.group("edge"),
            "clock": match.group("clock"),
            "source": "tb_checker",
        }
        if re.search(
            r"\b(?:tb_match\w*|mismatch\w*|errors?\w*|fail\w*)\b",
            match.group("body"),
            re.IGNORECASE,
        ):
            return event
    return None


def _vcd_signal_names(vcd: Any) -> list[str]:
    signals: list[str] = []
    seen: set[str] = set()
    get_signals = getattr(vcd, "get_signals", None)
    method_signals = get_signals() if callable(get_signals) else []
    for source in (
        getattr(vcd, "signals", []),
        getattr(vcd, "_signals", []),
        getattr(vcd, "references_to_ids", {}),
        method_signals,
    ):
        items = source.keys() if isinstance(source, dict) else source
        try:
            for signal in items:
                if isinstance(signal, str) and signal not in seen:
                    seen.add(signal)
                    signals.append(signal)
        except TypeError:
            continue
    return signals


def _vcd_time_values(vcd: Any, signal: str) -> list[tuple[int, str]] | None:
    def time_values(value: Any) -> list[tuple[int, str]] | None:
        tv = value.get("tv") if isinstance(value, dict) else getattr(value, "tv", None)
        return tv if isinstance(tv, list) else None

    value = None
    try:
        value = vcd[signal]  # type: ignore[index]
    except (KeyError, TypeError, AttributeError):
        pass
    tv = time_values(value)
    if tv is not None:
        return tv

    private_signals = getattr(vcd, "_signals", None)
    if isinstance(private_signals, dict):
        tv = time_values(private_signals.get(signal))
        if tv is not None:
            return tv

    data_sources: list[Any] = [getattr(vcd, "data", None), getattr(vcd, "_data", None)]
    get_data = getattr(vcd, "get_data", None)
    if callable(get_data):
        data_sources.append(get_data())

    references_to_ids = getattr(vcd, "references_to_ids", {})
    for data in data_sources:
        if isinstance(data, dict):
            value = data.get(signal)
            if value is None:
                identifier = references_to_ids.get(signal) if isinstance(references_to_ids, dict) else None
                if identifier is not None:
                    value = data.get(identifier)
            tv = time_values(value)
            if tv is not None:
                return tv
            for entry in data.values():
                if isinstance(entry, dict) and signal in (entry.get("references") or []):
                    tv = time_values(entry)
                    if tv is not None:
                        return tv
    return None


def _vcd_find_signal(vcd: Any, leaf: str, *, prefer_substrings: list[str] | None = None) -> str | None:
    leaf = leaf.strip()
    candidates: list[str] = []
    for s in _vcd_signal_names(vcd):
        last = s.split(".")[-1]
        if last == leaf or last.startswith(f"{leaf}["):
            candidates.append(s)
    if not candidates:
        return None
    # Prefer the closest-to-top match to reduce ambiguity (e.g., prefer tb.clk over tb.stim1.clk).
    def rank(sig: str) -> tuple[int, int, str]:
        return (sig.count("."), len(sig), sig)

    if prefer_substrings:
        preferred = [s for s in candidates if any(sub in s for sub in prefer_substrings)]
        if preferred:
            return sorted(preferred, key=rank)[0]
    return sorted(candidates, key=rank)[0]


def _vcd_value_at(tv: list[tuple[int, str]], t: int, *, inclusive: bool = True) -> str | None:
    last: str | None = None
    for tt, vv in tv:
        if tt < t or (inclusive and tt == t):
            last = vv
        else:
            break
    return last


def _normalize_vcd_value(val: str | None) -> str | None:
    if val is None:
        return None
    val = val.strip()
    if not val:
        return None
    # vcdvcd may prefix vectors with 'b'
    if (val.startswith("b") or val.startswith("B")) and len(val) > 1:
        val = val[1:]
    return val.lower()


def _wildcard_match(expected: str | None, actual: str | None) -> bool:
    """Approximate VerilogEval tb_match semantics: X/Z in expected are wildcards."""
    exp = _normalize_vcd_value(expected)
    act = _normalize_vcd_value(actual)
    if exp is None or act is None:
        return False

    n = max(len(exp), len(act))
    exp = exp.rjust(n, "0")
    act = act.rjust(n, "0")

    for e, a in zip(exp, act):
        if e in {"x", "z"}:
            continue
        if a != e:
            return False
    return True


def _vcd_truthy(value: str | None) -> bool | None:
    norm = _normalize_vcd_value(value)
    if norm is None:
        return None
    if any(ch in {"x", "z"} for ch in norm):
        return None
    return any(ch == "1" for ch in norm)


def _condition_blocks_update(exprs: Iterable[str], values: dict[str, str | None]) -> bool:
    """Best-effort check for simple Verilog if expressions such as rd && !empty."""
    for expr in exprs:
        for signal, value in values.items():
            truth = _vcd_truthy(value)
            if truth is None:
                continue
            negated = re.search(rf"(?<![A-Za-z0-9_])!\s*{re.escape(signal)}\b", expr) is not None
            positive = re.search(rf"(?<![!A-Za-z0-9_]){re.escape(signal)}\b", expr) is not None
            if negated and truth:
                return True
            if positive and not truth:
                return True
    return False


def _assignment_to_report(assignment: RtlAssignment) -> dict[str, Any]:
    snippet = assignment.code_snippet
    if len(snippet) > 1200:
        snippet = snippet[:1200] + "\n...<snip>..."
    return {
        "id": assignment.id,
        "block_id": assignment.block_id,
        "lhs": assignment.lhs,
        "rhs_signals": list(assignment.rhs_signals),
        "condition_signals": list(assignment.condition_signals),
        "kind": assignment.kind,
        "clocking": assignment.clocking,
        "start_line": assignment.start_line,
        "end_line": assignment.end_line,
        "code_snippet": snippet,
        "rhs_expression": assignment.rhs_expression,
        "condition_expressions": list(assignment.condition_exprs),
    }


def build_assignment_trace_step(
    *,
    signal: str,
    expected: str | None,
    actual: str | None,
    fail_time: int,
    assignment: RtlAssignment,
    sample_signal: Any,
) -> dict[str, Any]:
    """Classify one assignment-level cause without recursively following it."""
    lhs_value = actual if actual is not None else sample_signal(leaf=signal, t=fail_time, prefer_dut=True)
    rhs_values = {
        rhs: sample_signal(leaf=rhs, t=fail_time, prefer_dut=True)
        for rhs in assignment.rhs_signals
    }
    condition_values = {
        cond: sample_signal(leaf=cond, t=fail_time, prefer_dut=True)
        for cond in assignment.condition_signals
    }

    rhs_present = bool(rhs_values)
    missing_rhs = rhs_present and any(value is None for value in rhs_values.values())
    rhs_matches_expected = expected is not None and any(
        _wildcard_match(expected, value) for value in rhs_values.values() if value is not None
    )
    rhs_matches_actual = lhs_value is not None and any(
        _wildcard_match(lhs_value, value) for value in rhs_values.values() if value is not None
    )
    lhs_matches_expected = expected is not None and lhs_value is not None and _wildcard_match(expected, lhs_value)
    condition_blocks = _condition_blocks_update(assignment.condition_exprs, condition_values)

    classification = "missing_vcd_signal" if missing_rhs else "lhs_matches_rhs_continue_upstream"
    reason = "Assignment reflects an observed RHS value; continue upstream."
    if condition_blocks:
        classification = "condition_blocks_update"
        reason = "Observed condition values appear to block this assignment update."
    elif not rhs_present:
        classification = "constant_assignment"
        reason = "The selected assignment is driven only by a Verilog constant expression."
    elif missing_rhs:
        reason = "At least one RHS signal was not present in the VCD."
    elif rhs_matches_expected and not lhs_matches_expected:
        if assignment.clocking == "comb" or assignment.kind == "continuous":
            classification = "source_matches_expected_mux_wrong"
            reason = "A source value matches expected, but the combinational/continuous output does not."
        else:
            classification = "rhs_matches_expected_lhs_stale"
            reason = "RHS already matches expected, but LHS/output still has the failing value."
    elif rhs_matches_actual and not lhs_matches_expected:
        classification = "lhs_matches_rhs_continue_upstream"
        reason = "LHS matches the current RHS value, so the error likely originates upstream."

    return {
        "signal": signal,
        "driver_block_id": assignment.block_id,
        "assignment_id": assignment.id,
        "assignment": _assignment_to_report(assignment),
        "lhs_value": lhs_value,
        "expected": expected,
        "actual": actual,
        "rhs_observed_values": rhs_values,
        "condition_values": condition_values,
        "classification": classification,
        "reason": reason,
    }


def build_value_backtrace(
    *,
    fail_outputs: list[dict[str, Any]],
    fail_time: int | None,
    assignments: list[RtlAssignment],
    sample_signal: Any,
    max_depth: int = 3,
) -> dict[str, Any]:
    """Build a VCD-grounded assignment chain from failed outputs back through drivers."""
    if fail_time is None:
        return {"chains": [], "fallback_reason": "missing_fail_time"}
    if not assignments:
        return {"chains": [], "fallback_reason": "no_assignments_extracted"}

    by_lhs: dict[str, list[RtlAssignment]] = {}
    for assignment in assignments:
        by_lhs.setdefault(assignment.lhs, []).append(assignment)

    chains: list[dict[str, Any]] = []

    def trace_one(signal: str, expected: str | None, actual: str | None, depth: int, seen: set[str]) -> list[dict[str, Any]]:
        drivers = by_lhs.get(signal, [])
        if not drivers:
            return [
                {
                    "signal": signal,
                    "expected": expected,
                    "actual": actual,
                    "lhs_value": actual,
                    "classification": "missing_vcd_signal",
                    "reason": f"No assignment-level driver found for '{signal}'.",
                }
            ]
        if len(drivers) > 1:
            driver_blocks = {driver.block_id for driver in drivers}
            if len(driver_blocks) == 1:
                scored: list[tuple[int, RtlAssignment]] = []
                for candidate in drivers:
                    candidate_rhs_values = {
                        rhs: sample_signal(leaf=rhs, t=fail_time, prefer_dut=True)
                        for rhs in candidate.rhs_signals
                    }
                    score = 0
                    if expected is not None and any(
                        _wildcard_match(expected, value) for value in candidate_rhs_values.values() if value is not None
                    ):
                        score += 2
                    if actual is not None and any(
                        _wildcard_match(actual, value) for value in candidate_rhs_values.values() if value is not None
                    ):
                        score += 1
                    scored.append((score, candidate))
                drivers = [max(scored, key=lambda item: item[0])[1]]
            else:
                return [
                    {
                        "signal": signal,
                        "expected": expected,
                        "actual": actual,
                        "lhs_value": actual,
                        "classification": "ambiguous_multi_driver",
                        "reason": f"Multiple assignment-level drivers found for '{signal}'.",
                        "candidate_assignments": [_assignment_to_report(a) for a in drivers[:5]],
                    }
                ]

        assignment = drivers[0]
        step = build_assignment_trace_step(
            signal=signal,
            expected=expected,
            actual=actual,
            fail_time=fail_time,
            assignment=assignment,
            sample_signal=sample_signal,
        )
        lhs_value = step["lhs_value"]
        rhs_values = step["rhs_observed_values"]
        classification = step["classification"]
        steps = [step]

        if (
            classification == "lhs_matches_rhs_continue_upstream"
            and depth + 1 < max_depth
            and signal not in seen
        ):
            next_signal = None
            for rhs, value in rhs_values.items():
                if lhs_value is not None and value is not None and _wildcard_match(lhs_value, value):
                    next_signal = rhs
                    break
            if next_signal:
                steps.extend(trace_one(next_signal, expected, rhs_values.get(next_signal), depth + 1, seen | {signal}))
        return steps

    for fail in fail_outputs:
        sig = fail.get("sig") if isinstance(fail, dict) else None
        if not sig:
            continue
        expected = fail.get("expected") if isinstance(fail, dict) else None
        actual = fail.get("actual") if isinstance(fail, dict) else None
        if actual is None:
            actual = sample_signal(leaf=str(sig), t=fail_time, prefer_dut=True)
        chain = trace_one(str(sig), expected, actual, 0, set())
        chains.append({"sig": sig, "expected": expected, "actual": actual, "chain": chain})

    return {"chains": chains, "fallback_reason": ""}


def _build_diagnostic_narrative(value_backtrace: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for idx, chain_info in enumerate(value_backtrace.get("chains") or []):
        sig = chain_info.get("sig")
        expected = chain_info.get("expected")
        actual = chain_info.get("actual")
        chain = chain_info.get("chain") or []
        if not chain:
            continue
        top = chain[0]
        if not isinstance(top, dict):
            continue
        block = top.get("driver_block_id") or "unknown driver"
        classification = top.get("classification")
        reason = top.get("reason")
        prefix = "FIRST FAILURE: " if idx == 0 else ""
        lines.append(
            f"{prefix}{sig} failed: expected={expected}, actual={actual}. "
            f"Direct driver {block} classified as {classification}: {reason}"
        )
    fallback = value_backtrace.get("fallback_reason")
    if fallback and not lines:
        lines.append(f"Value backtrace unavailable: {fallback}.")
    return lines


def _build_window_times(vcd: Any, *, t_star: int, k_edges: int = 10, clock_name_hint: str | None = None) -> list[int]:
    clk_sig = _find_clock_signal(vcd, preferred_name=clock_name_hint)
    if clk_sig:
        tv = _vcd_time_values(vcd, clk_sig)
        if tv is not None:
            edges: list[int] = []
            prev = None
            for tt, vv in tv:
                if prev is not None and vv != prev:
                    edges.append(tt)
                prev = vv
            edges = [t for t in edges if t <= t_star]
            if edges:
                keep = edges[-min(len(edges), k_edges) :]
                if t_star not in keep:
                    keep.append(t_star)
                return keep

    # Fallback: pick latest change times in the window from all signals.
    times = {t_star}
    for s in _vcd_signal_names(vcd)[:200]:
        tv = _vcd_time_values(vcd, s)
        if tv is None:
            continue
        for tt, _vv in tv:
            if tt <= t_star:
                times.add(tt)
    return sorted(times)[-min(len(times), k_edges + 2) :]


# ---------------------------------------------------------------------------
# VCD probe helpers — reusable by rtl_editor for interactive signal queries
# ---------------------------------------------------------------------------

_REF_INSTANCE_CANDIDATES: tuple[str, ...] = ("good1", "ref", "golden", "reference")


def _resolve_ref_instance(vcd: Any) -> str | None:
    """Find a reference instance name in the VCD signal tree."""
    sigs = _vcd_signal_names(vcd)
    # Prefer shorter paths containing a candidate sub-instance
    best: str | None = None
    best_rank = (99999, 99999)
    for sig in sigs:
        parts = sig.split(".")
        for i, part in enumerate(parts):
            if part in _REF_INSTANCE_CANDIDATES:
                rank = (i, sig.count("."), len(sig))
                if rank < best_rank:
                    best_rank = rank
                    best = part
    return best


def resolve_vcd_signal(
    vcd: Any,
    name: str,
    *,
    dut_instance: str | None = None,
    ref_instance: str | None = None,
) -> dict[str, Any]:
    """Resolve a user-facing signal name to a full VCD path.

    Supported forms:
      - ``tb.dut.adr_i``      exact full path
      - ``adr_i``             leaf name (returns shortest match)
      - ``dut.adr_i``         alias prefixed with DUT instance
      - ``ref.adr_i``         alias prefixed with reference instance
    """
    name = name.strip()

    # If the name looks like a full VCD path (contains dots), try it
    # directly first — avoids leaf-name ambiguity when LLM already knows
    # the exact path from list_vcd_signals.
    if "." in name:
        if _vcd_time_values(vcd, name) is not None:
            return {"status": "ok", "name": name, "full_path": name}

    prefer_substrings: list[str] | None = None

    # Alias resolution
    if name.startswith("dut.") and dut_instance:
        leaf = name[4:]
        prefer_substrings = [f".{dut_instance}."]
    elif name.startswith("ref.") and ref_instance:
        leaf = name[4:]
        prefer_substrings = [f".{ref_instance}."]
    else:
        leaf = name

    all_sig_names = _vcd_signal_names(vcd)
    candidates: list[dict[str, Any]] = []
    for s in all_sig_names:
        last = s.split(".")[-1]
        if s == name or last == leaf or last.startswith(f"{leaf}["):
            candidates.append({"full_path": s, "depth": s.count("."), "length": len(s)})

    if not candidates:
        return {"status": "signal_not_found", "name": name, "leaf": leaf, "total_signals": len(all_sig_names)}

    if prefer_substrings:
        candidates = [c for c in candidates if any(sub in c["full_path"] for sub in prefer_substrings)]
        if not candidates:
            return {"status": "signal_not_found", "name": name, "leaf": leaf, "reason": "dut/ref scope not found"}

    # Sort by depth; validate each candidate until one works in _vcd_time_values
    candidates.sort(key=lambda c: (c["depth"], c["length"], c["full_path"]))
    for c in candidates:
        if _vcd_time_values(vcd, c["full_path"]) is not None:
            return {"status": "ok", "name": name, "full_path": c["full_path"]}

    # None of the candidates are readable by _vcd_time_values
    return {
        "status": "signal_not_found",
        "name": name,
        "leaf": leaf,
        "total_signals": len(all_sig_names),
        "candidates_tried": [c["full_path"] for c in candidates[:5]],
        "reason": "candidates found by name but none readable via _vcd_time_values (VCD key format mismatch)",
    }


def _find_clock_edges(
    vcd: Any,
    clock_name: str,
    time_range: tuple[int, int],
) -> list[dict[str, Any]]:
    """Return posedge/negedge times for *clock_name* within *time_range*."""
    tv = _vcd_time_values(vcd, clock_name)
    if tv is None:
        return []
    lo, hi = time_range
    edges: list[dict[str, Any]] = []
    prev_val: str | None = None
    for tt, vv in tv:
        if tt < lo:
            prev_val = vv
            continue
        if tt > hi:
            break
        if prev_val is not None and vv != prev_val:
            if prev_val != "1" and vv == "1":
                edge_type = "posedge"
            elif prev_val == "1" and vv != "1":
                edge_type = "negedge"
            else:
                edge_type = "edge"
            edges.append({"t": tt, "edge": edge_type})
        prev_val = vv
    return edges


def sample_vcd_signals(
    vcd: Any,
    signals: list[str],
    *,
    times: list[int] | None = None,
    time_range: tuple[int, int] | None = None,
    clock_name: str | None = None,
    edge_filter: str | None = None,
    mode: str = "sample",
    max_rows: int = 80,
) -> dict[str, Any]:
    """Sample VCD signals and return compact rows.

    Args:
        signals: List of full VCD paths (already resolved).
        times: Explicit list of times to sample.
        time_range: (lo, hi) to build sampling points.
        clock_name: Clock signal to derive edge-based sampling points.
        edge_filter: If set, only include rows at matching edges (posedge/negedge).
        mode: ``"sample"`` → values at every sampling point.
              ``"changes"`` → only return rows where at least one signal changed.
        max_rows: Hard row limit.
    """
    if not signals:
        return {"status": "too_many_signals", "error": "No signals provided"}
    if len(signals) > 16:
        return {"status": "too_many_signals", "error": f"At most 16 signals allowed, got {len(signals)}"}

    # Resolve time-value lists for all signals
    sig_tvs: dict[str, list[tuple[int, str]]] = {}
    for sig in signals:
        tv = _vcd_time_values(vcd, sig)
        if tv is None:
            return {"status": "signal_not_found", "signal": sig}
        sig_tvs[sig] = tv

    # Build sampling time points
    if times is not None:
        sample_times = sorted(set(times))
    elif time_range is not None and clock_name is not None:
        # Get clock edges in range, optionally filtered
        all_edges = _find_clock_edges(vcd, clock_name, time_range)
        if edge_filter:
            all_edges = [e for e in all_edges if e["edge"] == edge_filter]
        sample_times = [e["t"] for e in all_edges]
        # Add range boundaries for context
        if sample_times:
            if sample_times[0] > time_range[0]:
                sample_times.insert(0, time_range[0])
            if sample_times[-1] < time_range[1]:
                sample_times.append(time_range[1])
    elif time_range is not None:
        # Simple: collect all change times in range
        all_ts: set[int] = set()
        for tv in sig_tvs.values():
            for tt, _vv in tv:
                if time_range[0] <= tt <= time_range[1]:
                    all_ts.add(tt)
        sample_times = sorted(all_ts)
    else:
        return {"status": "missing_time_range", "error": "Provide times, time_range, or time_range+clock_name"}

    if len(sample_times) > max_rows * 2:
        # Downsample: take first N and last N
        half = max_rows
        sample_times = sample_times[:half] + sample_times[-half:]

    # Build rows
    rows: list[dict[str, Any]] = []
    prev_values: dict[str, str | None] = {}
    for t in sample_times:
        row: dict[str, Any] = {"t": t}
        changed = False
        for sig in signals:
            val = _vcd_value_at(sig_tvs[sig], t, inclusive=True)
            norm = _normalize_vcd_value(val)
            row[sig] = norm
            if norm != prev_values.get(sig):
                changed = True
            prev_values[sig] = norm
        if mode == "changes" and not changed:
            continue
        rows.append(row)
        if len(rows) >= max_rows:
            break

    truncated = len(rows) >= max_rows or len(sample_times) > max_rows * 2
    return {
        "status": "ok",
        "rows": rows,
        "row_count": len(rows),
        "truncated": truncated,
        "mode": mode,
    }


def compare_vcd_pairs(
    vcd: Any,
    pairs: list[list[str]],
    *,
    times: list[int] | None = None,
    time_range: tuple[int, int] | None = None,
    clock_name: str | None = None,
    edge_filter: str | None = None,
    first_diff_only: bool = True,
    max_rows: int = 80,
) -> dict[str, Any]:
    """Compare resolved signal pairs and find the first difference.

    Each pair is ``[path_a, path_b]`` (both already resolved full VCD paths).
    """
    if not pairs:
        return {"status": "too_many_signals", "error": "No pairs provided"}
    if len(pairs) > 8:
        return {"status": "too_many_signals", "error": f"At most 8 pairs allowed, got {len(pairs)}"}

    # Collect all signals from pairs
    all_sigs: list[str] = []
    for pair in pairs:
        all_sigs.extend(pair)
    all_sigs = sorted(set(all_sigs))

    # Sample all signals
    sample_result = sample_vcd_signals(
        vcd, all_sigs,
        times=times, time_range=time_range, clock_name=clock_name,
        edge_filter=edge_filter, mode="sample", max_rows=max(200, max_rows * 2),
    )
    if sample_result["status"] != "ok":
        return sample_result

    rows = sample_result["rows"]

    # Compare each pair row by row
    diffs: list[dict[str, Any]] = []
    first_diff_time: int | None = None
    for row in rows:
        t = row["t"]
        row_diffs: list[dict[str, Any]] = []
        for idx, (a_path, b_path) in enumerate(pairs):
            va = row.get(a_path)
            vb = row.get(b_path)
            if va is None or vb is None:
                continue
            if not _wildcard_match(va, vb):
                row_diffs.append({
                    "pair_index": idx,
                    "a": a_path,
                    "a_value": va,
                    "b": b_path,
                    "b_value": vb,
                })
        if row_diffs:
            if first_diff_time is None:
                first_diff_time = t
            diffs.append({"t": t, "diffs": row_diffs})
            if first_diff_only:
                break

    if first_diff_only and first_diff_time is not None and diffs:
        # Include a few rows of context before the first diff
        context_before: list[dict[str, Any]] = []
        for row in rows:
            if row["t"] >= first_diff_time:
                break
            context_before.append(row)
        context_before = context_before[-3:]  # last 3 before

        context_after: list[dict[str, Any]] = []
        found_first = False
        for row in rows:
            if row["t"] == first_diff_time:
                found_first = True
                continue
            if found_first:
                context_after.append(row)
                if len(context_after) >= 3:
                    break

        return {
            "status": "ok",
            "first_diff_time": first_diff_time,
            "first_diff": diffs[0] if diffs else None,
            "context_before": context_before,
            "context_after": context_after,
        }

    return {
        "status": "ok",
        "diffs": diffs[:max_rows],
        "diff_count": len(diffs),
        "first_diff_time": first_diff_time,
        "truncated": len(diffs) > max_rows,
    }


def _vcd_time_range(vcd: Any) -> tuple[int, int] | None:
    """Return (min_time, max_time) across all signals in the VCD."""
    t_min: int | None = None
    t_max: int | None = None
    for sig in _vcd_signal_names(vcd)[:50]:  # sample first 50 signals
        tv = _vcd_time_values(vcd, sig)
        if tv is None:
            continue
        for tt, _vv in tv:
            if t_min is None or tt < t_min:
                t_min = tt
            if t_max is None or tt > t_max:
                t_max = tt
    if t_min is not None and t_max is not None:
        return (t_min, t_max)
    return None


def list_vcd_signals_query(
    vcd: Any,
    pattern: str = "",
    scope: str = "",
    limit: int = 100,
) -> dict[str, Any]:
    """List VCD signal names matching *pattern* optionally scoped to *scope*."""
    import fnmatch
    all_sigs = _vcd_signal_names(vcd)
    result: list[str] = []
    for sig in all_sigs:
        if scope and not sig.startswith(scope):
            continue
        if pattern and not fnmatch.fnmatch(sig, f"*{pattern}*"):
            continue
        result.append(sig)
        if len(result) >= limit:
            break
    return {
        "status": "ok",
        "signals": result,
        "count": len(result),
        "truncated": len(result) >= limit,
        "total_in_vcd": len(all_sigs),
    }


def _resolve_dut_ref_signal_pair(
    vcd: Any,
    signal: str,
    *,
    dut_instance: str | None,
    ref_instance: str | None,
) -> dict[str, Any] | None:
    ref_aliases = [f"{signal}_ref"]
    dut_aliases = [f"{signal}_dut"]
    if ref_instance:
        ref_aliases.append(f"ref.{signal}")
    if dut_instance:
        dut_aliases.append(f"dut.{signal}")

    ref_path = None
    dut_path = None
    for alias in ref_aliases:
        resolved = resolve_vcd_signal(vcd, alias, dut_instance=dut_instance, ref_instance=ref_instance)
        if resolved.get("status") == "ok":
            ref_path = str(resolved["full_path"])
            break
    for alias in dut_aliases:
        resolved = resolve_vcd_signal(vcd, alias, dut_instance=dut_instance, ref_instance=ref_instance)
        if resolved.get("status") == "ok":
            dut_path = str(resolved["full_path"])
            break
    if not ref_path or not dut_path:
        return None
    ref_tv = _vcd_time_values(vcd, ref_path)
    dut_tv = _vcd_time_values(vcd, dut_path)
    if ref_tv is None or dut_tv is None:
        return None
    return {"signal": signal, "ref_path": ref_path, "dut_path": dut_path, "ref_tv": ref_tv, "dut_tv": dut_tv}


def _sample_pair(pair: dict[str, Any], t: int) -> tuple[str | None, str | None]:
    return (
        _vcd_value_at(pair["ref_tv"], t, inclusive=True),
        _vcd_value_at(pair["dut_tv"], t, inclusive=True),
    )


def _driver_assignment_kind(signal: str, assignments: list[RtlAssignment]) -> str:
    kinds = [a.kind for a in assignments if a.lhs == signal]
    if "nonblocking" in kinds:
        return "nonblocking"
    if "blocking" in kinds:
        return "blocking"
    if "continuous" in kinds:
        return "continuous"
    return "unknown"


def _sample_pair_with_mode(
    pair: dict[str, Any],
    t: int,
    *,
    sampling_mode: str,
    driver_assignment_kind: str,
) -> tuple[str | None, str | None]:
    dut_inclusive = not (sampling_mode == "edge_active" and driver_assignment_kind == "nonblocking")
    return (
        _vcd_value_at(pair["ref_tv"], t, inclusive=True),
        _vcd_value_at(pair["dut_tv"], t, inclusive=dut_inclusive),
    )


def _classify_divergence(
    *,
    pair: dict[str, Any],
    time_points: list[int],
    idx: int,
    ref_value: str | None,
    dut_value: str | None,
    sampling_mode: str = "stable",
    driver_assignment_kind: str = "unknown",
) -> str:
    if idx <= 0:
        return "unknown"
    prev_ref, prev_dut = _sample_pair_with_mode(
        pair,
        time_points[idx - 1],
        sampling_mode=sampling_mode,
        driver_assignment_kind=driver_assignment_kind,
    )
    if _wildcard_match(prev_ref, dut_value):
        return "dut_late"
    if _wildcard_match(ref_value, prev_dut):
        return "dut_early"
    if ref_value is not None and dut_value is not None:
        return "wrong_value"
    return "unknown"


def _build_divergence_time_points(
    vcd: Any,
    pairs: list[dict[str, Any]],
    *,
    output_dir: Path,
    time_window: tuple[int, int] | None,
) -> list[int]:
    if time_window is None:
        time_window = _vcd_time_range(vcd)
    if time_window is None:
        return []

    lo, hi = time_window
    points: set[int] = {lo, hi}
    clock_name = _find_clock_signal(vcd, preferred_name=_find_clock_from_contract(output_dir))
    if clock_name:
        for edge in _find_clock_edges(vcd, clock_name, time_window):
            t = edge.get("t")
            if isinstance(t, int):
                points.add(t)

    # Add ref/dut change times as a fallback and to catch #1 delayed updates.
    for pair in pairs:
        for tv_key in ("ref_tv", "dut_tv"):
            for tt, _vv in pair[tv_key]:
                if lo <= tt <= hi:
                    points.add(int(tt))
    return sorted(points)


def _build_edge_active_time_points(
    vcd: Any,
    *,
    output_dir: Path,
    time_window: tuple[int, int] | None,
    sampling_event: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    if time_window is None:
        time_window = _vcd_time_range(vcd)
    if time_window is None:
        return []
    preferred_clock = (sampling_event or {}).get("clock") or _find_clock_from_contract(output_dir)
    clock_name = _find_clock_signal(vcd, preferred_name=preferred_clock)
    if not clock_name:
        return []
    edges = _find_clock_edges(vcd, clock_name, time_window)
    required_edge = (sampling_event or {}).get("edge")
    if required_edge:
        edges = [item for item in edges if item.get("edge") == required_edge]
    return edges


def _sample_named_signal(
    vcd: Any,
    name: str,
    t: int,
    *,
    dut_instance: str | None,
    ref_instance: str | None,
) -> str | None:
    resolved = resolve_vcd_signal(vcd, name, dut_instance=dut_instance, ref_instance=ref_instance)
    if resolved.get("status") != "ok":
        return None
    tv = _vcd_time_values(vcd, str(resolved["full_path"]))
    if tv is None:
        return None
    return _vcd_value_at(tv, t, inclusive=True)


def build_first_divergence_report(
    *,
    rtl_path: Path,
    output_dir: Path,
    vcd: Any | None = None,
    sim_log_json: str | None = None,
    signals: list[str] | None = None,
    time_window: tuple[int, int] | None = None,
    sampling_mode: str = "auto",
    context_cycles: int = 3,
    max_signals: int = 24,
    runtime_top_module: str | None = None,
) -> dict[str, Any]:
    """Find the first real DUT/ref output divergence in the current VCD.

    This intentionally ignores testbench bookkeeping metrics such as
    ``errors_*`` and returns a compact causal slice suitable for an LLM patch
    decision.
    """
    vcd_path = output_dir / "wave.vcd"
    if vcd is None and (not vcd_path.exists() or VCDVCD is None):
        return {"status": "missing_vcd", "error": "wave.vcd not found or vcdvcd unavailable"}

    rtl_text = rtl_path.read_text(encoding="utf-8")
    ports = _extract_topmodule_ports(rtl_text)
    module_name = (
        str(runtime_top_module or "").strip()
        or _extract_module_name_from_contract(output_dir)
        or _extract_module_name_from_rtl(rtl_text)
        or "TopModule"
    )
    tb_path = output_dir / "tb.sv"
    dut_instance = None
    sampling_event: dict[str, str] | None = None
    if tb_path.exists():
        try:
            tb_text = tb_path.read_text(encoding="utf-8")
            dut_instance = _extract_dut_instance_name(tb_text, module_name=module_name)
            sampling_event = _extract_tb_sampling_event(tb_text)
        except Exception:  # noqa: BLE001
            dut_instance = None

    ignored_tb_metrics: list[dict[str, Any]] = []
    raw_fail_outputs: list[dict[str, Any]] = []
    real_fail_outputs: list[dict[str, Any]] = []
    if sim_log_json:
        try:
            sim = CommandResult.model_validate_json(sim_log_json)
            _fail_time, raw_fail_outputs = _extract_fail_signals_and_time(sim.stdout or "")
            real_fail_outputs, ignored_tb_metrics = _filter_root_fail_outputs(
                raw_fail_outputs,
                module_outputs=ports["outputs"],
            )
        except Exception:  # noqa: BLE001
            raw_fail_outputs = []
            real_fail_outputs = []

    if vcd is None:
        vcd = VCDVCD(str(vcd_path), store_tvs=True)  # type: ignore[operator]
    ref_instance = _resolve_ref_instance(vcd)
    candidate_signals = signals or ports["outputs"]
    candidate_signals = [
        s for s in candidate_signals
        if s and _signal_role(s, module_outputs=ports["outputs"]) != "tb_metric"
    ][:max_signals]

    pairs: list[dict[str, Any]] = []
    for sig in candidate_signals:
        pair = _resolve_dut_ref_signal_pair(
            vcd,
            sig,
            dut_instance=dut_instance,
            ref_instance=ref_instance,
        )
        if pair is not None:
            pairs.append(pair)
    if not pairs:
        return {
            "status": "no_pair_found",
            "runtime_top_module": module_name,
            "candidate_signals": candidate_signals,
            "dut_instance": dut_instance,
            "ref_instance": ref_instance,
            "ignored_tb_metrics": ignored_tb_metrics,
            "raw_fail_outputs": raw_fail_outputs,
        }

    blocks = parse_rtl_blocks(rtl_text)
    assignments = parse_rtl_assignments(rtl_text, blocks)

    authoritative_fail_time = min(
        (int(item["time"]) for item in real_fail_outputs if isinstance(item.get("time"), int)),
        default=None,
    )

    def scan(mode: str, *, not_before: int | None = None) -> dict[str, Any]:
        if mode == "edge_active":
            edge_points = _build_edge_active_time_points(
                vcd,
                output_dir=output_dir,
                time_window=time_window,
                sampling_event=sampling_event,
            )
            time_points = [int(edge["t"]) for edge in edge_points if isinstance(edge.get("t"), int)]
            edge_by_time = {int(edge["t"]): edge.get("edge") for edge in edge_points if isinstance(edge.get("t"), int)}
            active_region_model = (
                "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, "
                "edge settled value for blocking/continuous drivers"
            )
        else:
            time_points = _build_divergence_time_points(vcd, pairs, output_dir=output_dir, time_window=time_window)
            edge_by_time = {}
            active_region_model = "settled VCD ref/dut values at sample/change times"
        if not time_points:
            return {"status": "missing_time_range", "sampling_mode": mode, "pairs": [p["signal"] for p in pairs]}

        first: dict[str, Any] | None = None
        first_idx = -1
        first_pair: dict[str, Any] | None = None
        for idx, t in enumerate(time_points):
            if not_before is not None and t < not_before:
                continue
            for pair in pairs:
                driver_kind = _driver_assignment_kind(str(pair["signal"]), assignments)
                ref_value, dut_value = _sample_pair_with_mode(
                    pair,
                    t,
                    sampling_mode=mode,
                    driver_assignment_kind=driver_kind,
                )
                if ref_value is None or dut_value is None:
                    continue
                if not _wildcard_match(ref_value, dut_value):
                    first = {
                        "signal": pair["signal"],
                        "time": t,
                        "ref": ref_value,
                        "dut": dut_value,
                        "classification": _classify_divergence(
                            pair=pair,
                            time_points=time_points,
                            idx=idx,
                            ref_value=ref_value,
                            dut_value=dut_value,
                            sampling_mode=mode,
                            driver_assignment_kind=driver_kind,
                        ),
                        "ref_path": pair["ref_path"],
                        "dut_path": pair["dut_path"],
                        "sampling_mode": mode,
                        "edge": edge_by_time.get(t),
                        "driver_assignment_kind": driver_kind,
                        "active_region_model": active_region_model,
                    }
                    first_idx = idx
                    first_pair = pair
                    break
            if first is not None:
                break

        if first is None or first_pair is None:
            return {
                "status": "no_divergence",
                "sampling_mode": mode,
                "candidate_signals": [p["signal"] for p in pairs],
                "ignored_tb_metrics": ignored_tb_metrics,
                "raw_fail_outputs": raw_fail_outputs,
            }
        return {
            "status": "ok",
            "sampling_mode": mode,
            "time_points": time_points,
            "first": first,
            "first_idx": first_idx,
            "first_pair": first_pair,
        }

    requested_mode = sampling_mode if sampling_mode in {"stable", "edge_active", "auto"} else "auto"
    stable_scan = scan("stable")
    selected = stable_scan
    if requested_mode == "edge_active":
        selected = scan("edge_active")
    elif requested_mode == "auto" and authoritative_fail_time is not None:
        stable_authoritative = scan("stable", not_before=authoritative_fail_time)
        edge_authoritative = scan("edge_active", not_before=authoritative_fail_time)
        edge_first = edge_authoritative.get("first") if isinstance(edge_authoritative.get("first"), dict) else {}
        stable_first = stable_authoritative.get("first") if isinstance(stable_authoritative.get("first"), dict) else {}
        if (
            sampling_event is not None
            and edge_authoritative.get("status") == "ok"
            and edge_first.get("time") == authoritative_fail_time
        ):
            selected = edge_authoritative
            if stable_scan.get("status") == "no_divergence":
                selected = dict(selected)
                selected["status"] = "stable_values_match_but_tb_edge_mismatch"
                selected["stable_result"] = {
                    "status": stable_scan.get("status"),
                    "sampling_mode": stable_scan.get("sampling_mode"),
                    "candidate_signals": stable_scan.get("candidate_signals"),
                }
        elif stable_authoritative.get("status") == "ok" and stable_first.get("time") == authoritative_fail_time:
            selected = stable_authoritative
        else:
            selected = {
                "status": "sampling_alignment_unresolved",
                "sampling_mode": "auto",
                "authoritative_fail_time": authoritative_fail_time,
                "sampling_event": sampling_event,
                "stable_candidate": stable_authoritative.get("first"),
                "edge_active_candidate": edge_authoritative.get("first"),
                "candidate_signals": [p["signal"] for p in pairs],
                "ignored_tb_metrics": ignored_tb_metrics,
                "raw_fail_outputs": raw_fail_outputs,
            }
    elif requested_mode == "auto" and stable_scan.get("status") == "no_divergence":
        total_mismatches = None
        if sim_log_json:
            try:
                sim = CommandResult.model_validate_json(sim_log_json)
                total_mismatches = _extract_total_mismatches(sim.stdout or "")
            except Exception:  # noqa: BLE001
                total_mismatches = None
        if total_mismatches is not None and total_mismatches > 0:
            edge_scan = scan("edge_active")
            if edge_scan.get("status") == "ok":
                edge_scan["status"] = "stable_values_match_but_tb_edge_mismatch"
                edge_scan["stable_result"] = {
                    "status": stable_scan.get("status"),
                    "sampling_mode": stable_scan.get("sampling_mode"),
                    "candidate_signals": stable_scan.get("candidate_signals"),
                }
                selected = edge_scan

    if requested_mode == "auto" and authoritative_fail_time is not None:
        selected.setdefault("authoritative_fail_time", authoritative_fail_time)
        selected.setdefault("sampling_event", sampling_event)
        stable_first = stable_scan.get("first") if isinstance(stable_scan.get("first"), dict) else None
        stable_pair = stable_scan.get("first_pair") if isinstance(stable_scan.get("first_pair"), dict) else None
        stable_times = stable_scan.get("time_points") if isinstance(stable_scan.get("time_points"), list) else []
        recovered_before_sample = False
        if stable_first and stable_pair and isinstance(stable_first.get("time"), int):
            for t in stable_times:
                if not isinstance(t, int) or not (stable_first["time"] < t < authoritative_fail_time):
                    continue
                ref_value, dut_value = _sample_pair_with_mode(
                    stable_pair,
                    t,
                    sampling_mode="stable",
                    driver_assignment_kind=_driver_assignment_kind(str(stable_pair["signal"]), assignments),
                )
                if ref_value is not None and dut_value is not None and _wildcard_match(ref_value, dut_value):
                    recovered_before_sample = True
                    break
        if stable_first and recovered_before_sample:
            selected.setdefault(
                "pre_sample_transients",
                [{**stable_first, "classification": "pre_sample_transient"}],
            )

    if selected.get("status") in {"missing_time_range", "no_divergence", "sampling_alignment_unresolved"}:
        selected.setdefault("runtime_top_module", module_name)
        selected.setdefault("dut_instance", dut_instance)
        selected.setdefault("ref_instance", ref_instance)
        selected.setdefault("candidate_signals", [p["signal"] for p in pairs])
        selected.setdefault("ignored_tb_metrics", ignored_tb_metrics)
        selected.setdefault("raw_fail_outputs", raw_fail_outputs)
        return selected
    if selected.get("status") not in {"ok", "stable_values_match_but_tb_edge_mismatch"}:
        return selected

    time_points = list(selected["time_points"])
    first = dict(selected["first"])
    first_idx = int(selected["first_idx"])
    first_pair = selected["first_pair"]

    lo = max(0, first_idx - max(1, int(context_cycles)))
    hi = min(len(time_points), first_idx + max(1, int(context_cycles)) + 1)
    context_times = time_points[lo:hi]
    related_outputs = [first_pair["signal"]]
    for item in raw_fail_outputs:
        sig = item.get("sig")
        if isinstance(sig, str) and sig in ports["outputs"] and sig not in related_outputs:
            related_outputs.append(sig)
    related_outputs.extend([p["signal"] for p in pairs if p["signal"] not in related_outputs][:4])
    related_outputs = related_outputs[:8]

    rows: list[dict[str, Any]] = []
    for t in context_times:
        row: dict[str, Any] = {"t": t}
        for name in ports["inputs"][:12]:
            val = _sample_named_signal(vcd, name, t, dut_instance=dut_instance, ref_instance=ref_instance)
            if val is not None:
                row[name] = val
        for name in ("state", "next_state"):
            ref_val = _sample_named_signal(vcd, f"ref.{name}", t, dut_instance=dut_instance, ref_instance=ref_instance)
            dut_val = _sample_named_signal(vcd, f"dut.{name}", t, dut_instance=dut_instance, ref_instance=ref_instance)
            if ref_val is not None:
                row[f"ref_{name}"] = ref_val
            if dut_val is not None:
                row[f"dut_{name}"] = dut_val
        for name in related_outputs:
            pair = next((p for p in pairs if p["signal"] == name), None)
            if pair is None:
                continue
            driver_kind = _driver_assignment_kind(str(pair["signal"]), assignments)
            ref_val, dut_val = _sample_pair_with_mode(
                pair,
                t,
                sampling_mode=str(first.get("sampling_mode") or "stable"),
                driver_assignment_kind=driver_kind,
            )
            row[f"{name}_ref"] = ref_val
            row[f"{name}_dut"] = dut_val
        rows.append(row)

    drivers = build_driver_map(blocks)
    suspects = dynamic_slice(fail_signals=[str(first["signal"])], drivers=drivers, max_depth=3)
    suspect_blocks = [
        {
            "id": b.id,
            "kind": b.kind,
            "clocking": b.clocking,
            "writes": list(b.writes),
            "start_line": b.start_line,
            "end_line": b.end_line,
        }
        for b in suspects[:8]
    ]

    return {
        "status": selected.get("status", "ok"),
        "authoritative_fail_time": authoritative_fail_time,
        "sampling_event": sampling_event,
        "pre_sample_transients": selected.get("pre_sample_transients") or [],
        "runtime_top_module": module_name,
        "sampling_mode": first.get("sampling_mode"),
        "edge": first.get("edge"),
        "driver_assignment_kind": first.get("driver_assignment_kind"),
        "active_region_model": first.get("active_region_model"),
        "first_divergence": first,
        "nearby": {
            "times": context_times,
            "rows": rows,
        },
        "suspect": {
            "driver_blocks": suspect_blocks,
            "signals": sorted({str(first["signal"]), *related_outputs}),
            "hint": "First DUT/ref divergence aligned to the authoritative testbench sampling event.",
        },
        "candidate_signals": [p["signal"] for p in pairs],
        "ignored_tb_metrics": ignored_tb_metrics,
        "raw_fail_outputs": raw_fail_outputs,
        "dut_instance": dut_instance,
        "ref_instance": ref_instance,
    }


def build_trace_report(
    *,
    rtl_path: Path,
    sim_log_json: str,
    output_dir: Path,
    max_depth: int = 3,
    kg_service: Any | None = None,
    kg_session_id: str = "",
    kg_hop_depth: int = 2,
    window_cycles: int = 10,
    diag_edges: int = 200,
    planner_module_name: str = "",
    runtime_top_module: str | None = None,
) -> tuple[dict[str, Any], list[RtlBlock]]:
    """Build a structured bug report (waveform + coarse RTL slice)."""
    observation=json.loads(sim_log_json)
    native=observation if isinstance(observation,dict) and observation.get('scope') in {'syntax','compile','functional'} and 'checks_executed' in observation else None
    sim = CommandResult(stdout=str(native.get('diagnostic_excerpt') or ''),stderr=str(native.get('error') or '')) if native is not None else CommandResult.model_validate(observation)
    stdout = sim.stdout or ""

    rtl_text = rtl_path.read_text(encoding="utf-8")
    ports = _extract_topmodule_ports(rtl_text)
    module_name = (
        str(runtime_top_module or "").strip()
        or _extract_module_name_from_contract(output_dir)
        or _extract_module_name_from_rtl(rtl_text)
        or "TopModule"
    )
    logical_module_name = str(planner_module_name or "").strip() or module_name

    fail_time, raw_fail_outputs = _extract_fail_signals_and_time(stdout)
    total_mismatches = _extract_total_mismatches(stdout)
    if total_mismatches is None and native is not None and type(native.get('failures')) is int:
        total_mismatches=native['failures']

    blocks = parse_rtl_blocks(rtl_text)
    if not blocks:
        # Last-resort fallback: allow the debugger to edit something even if
        # the RTL parser fails (e.g., malformed output). This keeps the tool
        # contract stable: debug can always get at least one block_id.
        lines = rtl_text.splitlines()
        if lines:
            code = rtl_text if rtl_text.endswith("\n") else rtl_text + "\n"
            blocks = [
                RtlBlock(
                    id="A1",
                    kind="always",
                    start_line=1,
                    end_line=len(lines),
                    clocking="unknown",
                    code=code,
                    writes=tuple(ports["outputs"]),
                    reads=tuple(ports["inputs"]),
                )
            ]

    drivers = build_driver_map(blocks)
    assignments = parse_rtl_assignments(rtl_text, blocks)

    fail_outputs, ignored_tb_metrics = _filter_root_fail_outputs(raw_fail_outputs, module_outputs=ports["outputs"])
    fail_signal_names: list[str] = [fo["sig"] for fo in fail_outputs if fo.get("sig")]
    if not fail_signal_names:
        fail_signal_names = ports["outputs"]

    local_suspect_blocks = dynamic_slice(
        fail_signals=fail_signal_names,
        drivers=drivers,
        max_depth=max_depth,
    )

    kg_slice_source = "local"
    kg_fallback_reason = ""
    suspect_blocks = local_suspect_blocks

    if kg_service is not None:
        session_id = kg_session_id or kg_debug_session_id(logical_module_name)
        try:
            materializer = DebugReadsMaterializer(kg_service)
            materialized = materializer.materialize(
                module_name=logical_module_name,
                session_id=session_id,
                hop_depth=kg_hop_depth,
                current_rtl_path=rtl_path,
                current_blocks=blocks,
            )
            kg_slice = kg_dynamic_slice(
                kg_service=kg_service,
                module_name=logical_module_name,
                fail_signals=fail_signal_names,
                session_id=session_id,
                max_depth=max_depth,
            )
            uid_to_local_key = {uid: key for key, uid in materialized.current_uid_by_key.items()}
            local_by_key = {
                (block.kind, int(block.start_line), int(block.end_line)): block
                for block in blocks
            }
            kg_selected: list[RtlBlock] = []
            for uid in kg_slice.block_uids:
                key = uid_to_local_key.get(uid)
                block = local_by_key.get(key) if key else None
                if block is not None and block not in kg_selected:
                    kg_selected.append(block)
            if kg_selected:
                suspect_blocks = kg_selected
                kg_slice_source = "kg"
            else:
                kg_fallback_reason = materialized.fallback_reason or (
                    "KG slicing returned no editable blocks for the current debug RTL."
                )
        except Exception as exc:  # noqa: BLE001
            kg_fallback_reason = f"{type(exc).__name__}: {exc}"

    if not suspect_blocks and blocks:
        suspect_blocks = blocks

    vcd_path = output_dir / "wave.vcd"
    vcd_available = vcd_path.exists() and VCDVCD is not None
    dut_instance: str | None = None
    tb_path = output_dir / "tb.sv"
    if tb_path.exists():
        try:
            dut_instance = _extract_dut_instance_name(tb_path.read_text(encoding="utf-8"), module_name=module_name)
        except Exception:  # noqa: BLE001
            dut_instance = None

    first_divergence_report: dict[str, Any] | None = None
    vcd: Any | None = None
    if vcd_available:
        try:
            vcd = VCDVCD(str(vcd_path), store_tvs=True)  # type: ignore[operator]
            first_divergence_report = build_first_divergence_report(
                rtl_path=rtl_path,
                output_dir=output_dir,
                vcd=vcd,
                sim_log_json=sim_log_json,
                signals=ports["outputs"],
                context_cycles=3,
                runtime_top_module=module_name,
            )
        except Exception as exc:  # noqa: BLE001
            first_divergence_report = {"status": "error", "error": f"{type(exc).__name__}: {exc}"}

    fail_time_star = fail_time
    aligned_divergence = (
        first_divergence_report.get("first_divergence")
        if isinstance(first_divergence_report, dict)
        and first_divergence_report.get("status") in {"ok", "stable_values_match_but_tb_edge_mismatch"}
        and isinstance(first_divergence_report.get("first_divergence"), dict)
        else None
    )
    if isinstance(aligned_divergence, dict) and isinstance(aligned_divergence.get("time"), int):
        fail_time_star = int(aligned_divergence["time"])
    selected_sampling_mode = (
        str(aligned_divergence.get("sampling_mode"))
        if isinstance(aligned_divergence, dict) and aligned_divergence.get("sampling_mode") in {"stable", "edge_active"}
        else ""
    )
    sampling_alignment_unresolved = (
        isinstance(first_divergence_report, dict)
        and first_divergence_report.get("status") == "sampling_alignment_unresolved"
    )
    fail_details: list[dict[str, Any]] = []
    active_failures: list[dict[str, Any]] = []
    ordered_fail_outputs: list[dict[str, Any]] = []
    input_window: list[dict[str, Any]] = []
    timing_hints: dict[str, Any] = {}
    alignment_diagnosis: dict[str, Any] = {}
    value_backtrace: dict[str, Any] = {"chains": [], "fallback_reason": "vcd_unavailable"}
    diagnostic_narrative: list[str] = []

    if vcd is not None and fail_time_star is not None:
        # Resolve the clock signal name from contract or common candidates.
        clock_name_from_contract = _find_clock_from_contract(output_dir)
        times = _build_window_times(
            vcd, t_star=fail_time_star, k_edges=window_cycles, clock_name_hint=clock_name_from_contract,
        )

        # Classify clock edges for the window.
        edge_at_time: dict[int, str] = {}
        edge_idx_at_time: dict[int, int] = {}
        edges_in_order: list[tuple[int, str]] = []
        clk_full = _find_clock_signal(vcd, preferred_name=clock_name_from_contract)
        clk_leaf: str | None = clk_full.split(".")[-1] if clk_full else None
        if clk_full:
            tv = _vcd_time_values(vcd, clk_full)
            if tv is not None:
                prev = None
                for tt, vv in tv:
                    if prev is not None and vv != prev:
                        if prev != "1" and vv == "1":
                            edge_at_time[tt] = "posedge"
                        elif prev == "1" and vv != "1":
                            edge_at_time[tt] = "negedge"
                        else:
                            edge_at_time[tt] = "edge"
                        edge_idx_at_time[tt] = len(edges_in_order)
                        edges_in_order.append((tt, edge_at_time[tt]))
                    prev = vv

        key_signals: list[str] = []
        # include top-level inputs
        key_signals.extend(ports["inputs"])
        # include ref/dut for failing outputs if present
        for sig in fail_signal_names:
            key_signals.append(f"{sig}_ref")
            key_signals.append(f"{sig}_dut")

        # Include likely internal signals (best-effort, only if present in VCD).
        internal_candidates: list[str] = []
        for b in suspect_blocks:
            internal_candidates.extend(list(b.writes))
            internal_candidates.extend(list(b.reads))
        internal_candidates = [
            s
            for s in sorted(set(internal_candidates))
            if s and s not in ports["inputs"] and s not in ports["outputs"]
        ]
        key_signals.extend(internal_candidates[:20])
        internal_candidate_set = set(internal_candidates[:20])

        key_signals = sorted({s for s in key_signals if s})

        def sample_signal(*, leaf: str, t: int, prefer_dut: bool = False) -> str | None:
            prefer_substrings = None
            if dut_instance and (prefer_dut or leaf in internal_candidate_set):
                prefer_substrings = [f".{dut_instance}."]
            full = _vcd_find_signal(vcd, leaf, prefer_substrings=prefer_substrings)
            if not full:
                return None
            inclusive = (clk_leaf is not None and leaf == clk_leaf) or (t == 0)
            if selected_sampling_mode == "stable" and t == fail_time_star:
                inclusive = True
            elif selected_sampling_mode == "edge_active" and t == fail_time_star:
                if leaf.endswith("_ref"):
                    inclusive = True
                elif leaf.endswith("_dut"):
                    output_name = leaf[:-4]
                    inclusive = _driver_assignment_kind(output_name, assignments) != "nonblocking"
            tv = _vcd_time_values(vcd, full)
            if tv is None:
                return None
            return _vcd_value_at(tv, t, inclusive=inclusive)

        # fail output expected/actual at t*
        for sig in fail_signal_names:
            exp = sample_signal(leaf=f"{sig}_ref", t=fail_time_star)
            act = sample_signal(leaf=f"{sig}_dut", t=fail_time_star)
            fail_details.append({"sig": sig, "expected": exp, "actual": act, "signal_role": _signal_role(sig, module_outputs=ports["outputs"])})

        # Only show actually-mismatched signals in fail_outputs.
        # Signals that still match at fail_time (fail later due to cascading)
        # are kept for backtrace but not shown to the LLM as active failures.
        _mismatched_sigs = {
            f["sig"] for f in fail_details
            if not _wildcard_match(f.get("expected"), f.get("actual"))
        }
        active_failures = [f for f in fail_details if f["sig"] in _mismatched_sigs]
        inactive_failures = [f for f in fail_details if f["sig"] not in _mismatched_sigs]
        # Reorder so actually-mismatched signals dominate the diagnostic narrative
        ordered_fail_outputs = active_failures + inactive_failures

        # input window values
        for window_idx, t in enumerate(times):
            edge = edge_at_time.get(t)
            row: Dict[str, Any] = {
                "t": t,
                "edge": edge,
                "event": f"@({edge} {clk_leaf})" if (edge in {"posedge", "negedge"} and clk_leaf) else None,
                "sample_idx": edge_idx_at_time.get(t),
                "window_idx": window_idx,
            }
            for s in key_signals:
                val = sample_signal(leaf=s, t=t)
                if val is not None:
                    row[s] = val
            input_window.append(row)

        # Simple timing hints: detect 1-edge latency between expected and actual.
        rows_by_t = {row["t"]: row for row in input_window if isinstance(row.get("t"), int)}
        if times and fail_time_star in rows_by_t:
            idx = times.index(fail_time_star) if fail_time_star in times else -1
            if idx > 0:
                prev_t = times[idx - 1]
                cur = rows_by_t.get(fail_time_star, {})
                prev = rows_by_t.get(prev_t, {})
                for sig in fail_signal_names:
                    exp_k = f"{sig}_ref"
                    act_k = f"{sig}_dut"
                    exp = cur.get(exp_k)
                    act = cur.get(act_k)
                    exp_prev = prev.get(exp_k)
                    act_prev = prev.get(act_k)
                    hint: dict[str, Any] = {}
                    if exp is not None and act is not None and exp_prev is not None and act_prev is not None:
                        if _wildcard_match(exp_prev, act) and not _wildcard_match(exp, act):
                            hint["actual_matches_prev_expected"] = True
                        if _wildcard_match(exp, act_prev) and not _wildcard_match(exp_prev, act_prev):
                            hint["prev_actual_matches_current_expected"] = True
                    if hint:
                        hint["prev_t"] = prev_t
                        hint["t"] = fail_time_star
                        timing_hints[sig] = hint

        # Alignment diagnosis over a wider (but bounded) window of edge samples.
        if edges_in_order:
            diag_candidates = [e for e in edges_in_order if e[0] <= fail_time_star]
            diag_candidates = diag_candidates[-min(len(diag_candidates), max(20, diag_edges)) :]

            for sig in fail_signal_names:
                exp_leaf = f"{sig}_ref"
                act_leaf = f"{sig}_dut"
                seq: list[dict[str, Any]] = []
                for tt, et in diag_candidates:
                    seq.append(
                        {
                            "t": tt,
                            "edge": et,
                            "exp": sample_signal(leaf=exp_leaf, t=tt),
                            "act": sample_signal(leaf=act_leaf, t=tt),
                        }
                    )

                def rate(pairs: list[tuple[str | None, str | None]]) -> float | None:
                    total = 0
                    ok = 0
                    for e, a in pairs:
                        if e is None or a is None:
                            continue
                        total += 1
                        if _wildcard_match(e, a):
                            ok += 1
                    return (ok / total) if total else None

                exp_seq = [r["exp"] for r in seq]
                act_seq = [r["act"] for r in seq]

                cur_rate = rate(list(zip(exp_seq, act_seq)))
                lag_rate = rate(list(zip(exp_seq[1:], act_seq[:-1])))
                lead_rate = rate(list(zip(exp_seq[:-1], act_seq[1:])))

                pos_rate = rate(
                    [(r["exp"], r["act"]) for r in seq if r.get("edge") == "posedge"]
                )
                neg_rate = rate(
                    [(r["exp"], r["act"]) for r in seq if r.get("edge") == "negedge"]
                )

                choices = {
                    "current": cur_rate,
                    "dut_lag1": lag_rate,
                    "dut_lead1": lead_rate,
                }
                best = max(choices.items(), key=lambda kv: (-1.0 if kv[1] is None else kv[1]))
                alignment_diagnosis[sig] = {
                    "best_alignment": best[0] if best[1] is not None else None,
                    "match_rate_dut_lag1": lag_rate,
                }

        if sampling_alignment_unresolved:
            value_backtrace = {"chains": [], "fallback_reason": "sampling_alignment_unresolved"}
        else:
            value_backtrace = build_value_backtrace(
                fail_outputs=ordered_fail_outputs or fail_outputs,
                fail_time=fail_time_star,
                assignments=assignments,
                sample_signal=sample_signal,
                max_depth=max_depth,
            )
            value_backtrace["sampling_mode"] = selected_sampling_mode or "stable"
            diagnostic_narrative = _build_diagnostic_narrative(value_backtrace)

    elif fail_time_star is None:
        value_backtrace = {"chains": [], "fallback_reason": "missing_fail_time"}

    # ---- Build suspect_blocks from value_backtrace chains (causal order) ----
    # Only use dynamic_slice as a fallback when backtrace is unavailable.
    _backtrace_block_ids: list[str] = []
    if value_backtrace.get("chains"):
        _seen_bids: set[str] = set()
        for chain_info in value_backtrace["chains"]:
            for step in chain_info.get("chain") or []:
                if not isinstance(step, dict):
                    continue
                bid = step.get("driver_block_id")
                if bid and bid not in _seen_bids:
                    _seen_bids.add(bid)
                    _backtrace_block_ids.append(str(bid))
    _block_by_id = {b.id: b for b in blocks}
    if _backtrace_block_ids:
        sorted_suspect_blocks = [
            _block_by_id[bid] for bid in _backtrace_block_ids if bid in _block_by_id
        ]
    else:
        sorted_suspect_blocks = sorted(
            suspect_blocks,
            key=lambda b: (b.start_line, b.id),
        )

    root_failure = None
    has_real_divergence = (
        isinstance(first_divergence_report, dict)
        and first_divergence_report.get("status") in {"ok", "stable_values_match_but_tb_edge_mismatch"}
    )
    if has_real_divergence:
        root_failure = first_divergence_report.get("first_divergence")
    elif not sampling_alignment_unresolved and active_failures:
        root_failure = active_failures[0]

    visible_fail_outputs = active_failures
    if not visible_fail_outputs and fail_details and fail_outputs:
        visible_fail_outputs = fail_details

    report: dict[str, Any] = {
        'verification_ref':{key:native.get(key) for key in ('check_id','version_id','tree_sha256','verification_spec_id','testset_sha256','checks_executed','failures')} if native is not None else None,
        "fail_time": fail_time_star,
        "planner_module_name": logical_module_name,
        "runtime_top_module": module_name,
        "runtime_rtl_path": str(rtl_path),
        "total_mismatches": total_mismatches,
        "raw_fail_outputs": raw_fail_outputs,
        "ignored_tb_metrics": ignored_tb_metrics,
        "fail_outputs": visible_fail_outputs,
        "first_failure": root_failure,
        "root_failure": root_failure,
        "first_divergence": first_divergence_report,
        "edge_active_failure": (
            first_divergence_report.get("first_divergence")
            if isinstance(first_divergence_report, dict)
            and first_divergence_report.get("sampling_mode") == "edge_active"
            else None
        ),
        "required_next_tool": (
            "run_check(first_divergence)"
            if (not root_failure and ignored_tb_metrics)
            else None
        ),
        "alignment_diagnosis": alignment_diagnosis,
        "value_backtrace": value_backtrace,
        "diagnostic_narrative": diagnostic_narrative,
        "suspect_blocks": [
            {
                "id": b.id,
                "kind": b.kind,
                "clocking": b.clocking,
                "writes": list(b.writes),
                "start_line": b.start_line,
                "end_line": b.end_line,
            }
            for b in sorted_suspect_blocks
        ],
        "vcd_available": bool(vcd_available),
        "dut_instance": dut_instance,
        "sampling_event": (
            first_divergence_report.get("sampling_event")
            if isinstance(first_divergence_report, dict)
            else None
        ),
        "timing_hints": timing_hints,
    }

    return report, suspect_blocks
