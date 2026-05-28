from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ContractIssue:
    severity: str
    path: str
    message: str


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except Exception:  # noqa: BLE001
        return None


def lint_contract_json(contract_json_text: str) -> tuple[list[ContractIssue], dict[str, Any] | None]:
    issues: list[ContractIssue] = []
    try:
        obj = json.loads(contract_json_text)
    except Exception as exc:  # noqa: BLE001
        return [ContractIssue("error", "$", f"Invalid JSON: {type(exc).__name__}: {exc}")], None

    if not isinstance(obj, dict):
        return [ContractIssue("error", "$", "Contract must be a JSON object.")], None

    module_name = obj.get("module_name")
    if not isinstance(module_name, str) or not module_name.strip():
        issues.append(ContractIssue("error", "module_name", "Missing/invalid module_name."))

    io = obj.get("io")
    if not isinstance(io, list) or not io:
        issues.append(ContractIssue("error", "io", "Missing/invalid io list."))
        return issues, obj

    seen_names: set[str] = set()
    inputs: set[str] = set()
    outputs: set[str] = set()
    for index, port in enumerate(io):
        path = f"io[{index}]"
        if not isinstance(port, dict):
            issues.append(ContractIssue("error", path, "Port entry must be an object."))
            continue
        name = port.get("name")
        direction = port.get("dir")
        width = port.get("width", 1)
        if not isinstance(name, str) or not name.strip():
            issues.append(ContractIssue("error", f"{path}.name", "Missing/invalid port name."))
            continue
        if name in seen_names:
            issues.append(ContractIssue("error", f"{path}.name", f"Duplicate port name: {name}"))
        seen_names.add(name)
        if direction not in {"input", "output", "inout"}:
            issues.append(ContractIssue("error", f"{path}.dir", f"Invalid dir for {name}: {direction!r}"))
        parsed_width = _as_int(width)
        if parsed_width is None or parsed_width <= 0:
            issues.append(ContractIssue("error", f"{path}.width", f"Invalid width for {name}: {width!r}"))
        if direction == "input":
            inputs.add(name)
        elif direction == "output":
            outputs.add(name)

    clocking = obj.get("clocking")
    if isinstance(clocking, dict) and clocking.get("is_sequential") is True:
        clock = clocking.get("clock")
        if not isinstance(clock, dict) or not isinstance(clock.get("name"), str) or not clock.get("name"):
            issues.append(ContractIssue("error", "clocking.clock", "Sequential design requires clock.name."))
        elif str(clock["name"]) not in inputs:
            issues.append(ContractIssue("warning", "clocking.clock.name", f"Clock {clock['name']} not found in input ports."))

        reset = clocking.get("reset")
        if isinstance(reset, dict) and isinstance(reset.get("name"), str) and reset.get("name"):
            if str(reset["name"]) not in inputs:
                issues.append(ContractIssue("warning", "clocking.reset.name", f"Reset {reset['name']} not found in input ports."))

    timing = obj.get("timing")
    if timing is not None and not isinstance(timing, dict):
        issues.append(ContractIssue("warning", "timing", "timing should be an object mapping output names to timing info."))
    if isinstance(timing, dict):
        for output in sorted(outputs):
            entry = timing.get(output)
            if entry is None:
                issues.append(ContractIssue("warning", f"timing.{output}", "Missing timing entry for output."))
                continue
            if not isinstance(entry, dict):
                issues.append(ContractIssue("warning", f"timing.{output}", "Timing entry should be an object."))
                continue
            latency = entry.get("latency_cycles")
            if latency is None:
                issues.append(ContractIssue("warning", f"timing.{output}.latency_cycles", "Missing latency_cycles."))
                continue
            parsed_latency = _as_int(latency)
            if parsed_latency is None or parsed_latency < 0:
                issues.append(
                    ContractIssue("error", f"timing.{output}.latency_cycles", f"Invalid latency_cycles: {latency!r}")
                )

    guidance = obj.get("guidance")
    if guidance is None or not isinstance(guidance, dict):
        issues.append(ContractIssue("warning", "guidance", "Missing guidance block."))
    else:
        for key in ["verifier", "coder", "debugger"]:
            value = guidance.get(key)
            if value is None:
                issues.append(ContractIssue("warning", f"guidance.{key}", "Missing guidance list."))
            elif not isinstance(value, list):
                issues.append(ContractIssue("warning", f"guidance.{key}", "Guidance entry should be a list of strings."))

    return issues, obj


def render_contract_issues(issues: list[ContractIssue]) -> str:
    if not issues:
        return ""
    return "\n".join(f"- [{issue.severity}] {issue.path}: {issue.message}" for issue in issues) + "\n"
