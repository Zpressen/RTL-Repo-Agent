import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


def resolve_rtl_sidecar_path(repo_data: Optional[Dict[str, Any]], path_value: str) -> Optional[Path]:
    raw_path = str(path_value or "").strip()
    if not raw_path:
        return None

    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate if candidate.exists() else None

    repo_data = repo_data or {}
    repo_data_path_value = str(repo_data.get("_repo_data_path", "")).strip()
    repo_data_path = Path(repo_data_path_value) if repo_data_path_value else None
    repo_data_dir_value = str(repo_data.get("_repo_data_dir", "")).strip()
    repo_data_dir = Path(repo_data_dir_value) if repo_data_dir_value else None

    candidates: List[Path] = []
    if repo_data_path is not None:
        candidates.append(repo_data_path.parent / raw_path)
        candidates.append(repo_data_path.parent.parent / raw_path)
    if repo_data_dir is not None:
        candidates.append(repo_data_dir / raw_path)
        candidates.append(repo_data_dir.parent / raw_path)
    candidates.append(Path.cwd() / raw_path)

    for item in candidates:
        if item.exists():
            return item
    return None


def load_rtl_spec_facts(repo_data: Optional[Dict[str, Any]], logger: Optional[logging.Logger] = None) -> Dict[str, Any]:
    repo_data = repo_data or {}
    rtl_metadata = repo_data.get("rtl_metadata", {}) or {}
    source_paths = rtl_metadata.get("source_paths", {}) or {}
    spec_path = resolve_rtl_sidecar_path(repo_data, str(source_paths.get("spec_facts", "")).strip())
    if spec_path is None:
        return {}

    try:
        with open(spec_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception as exc:
        if logger is not None:
            logger.warning(f"[rtl_trace] Failed to load spec facts from {spec_path}: {exc}")
        return {}

    return payload if isinstance(payload, dict) else {}


def build_rtl_trace_catalog(spec_facts: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    spec_facts = spec_facts or {}
    catalog: Dict[str, Dict[str, Any]] = {}

    for item in spec_facts.get("requirement_specs", []) or []:
        if not isinstance(item, dict):
            continue
        trace_id = str(item.get("req_id", "")).strip()
        if not trace_id:
            continue
        corner_cases = [str(val).strip() for val in (item.get("corner_cases", []) or []) if str(val).strip()]
        verify_refs = [str(val).strip() for val in (item.get("verify_refs", []) or []) if str(val).strip()]
        catalog[trace_id] = {
            "id": trace_id,
            "kind": "requirement",
            "priority": str(item.get("priority", "")).strip(),
            "summary": str(item.get("statement", "")).strip(),
            "details": {
                "statement": str(item.get("statement", "")).strip(),
                "corner_cases": corner_cases,
                "verify_refs": verify_refs,
                "related_code_anchor_ids": [
                    str(val).strip() for val in (item.get("related_code_anchor_ids", []) or []) if str(val).strip()
                ],
            },
        }

    for item in spec_facts.get("test_specs_v2", []) or []:
        if not isinstance(item, dict):
            continue
        trace_id = str(item.get("test_id", "")).strip()
        if not trace_id:
            continue
        checks = [str(val).strip() for val in (item.get("checks", []) or []) if str(val).strip()]
        driver_tasks = [str(val).strip() for val in (item.get("driver_tasks", []) or []) if str(val).strip()]
        catalog[trace_id] = {
            "id": trace_id,
            "kind": "test",
            "summary": str(item.get("purpose", "")).strip(),
            "details": {
                "purpose": str(item.get("purpose", "")).strip(),
                "steps": [str(val).strip() for val in (item.get("steps", []) or []) if str(val).strip()],
                "checks": checks,
                "driver_tasks": driver_tasks,
                "related_req_ids": [
                    str(val).strip() for val in (item.get("related_req_ids", []) or []) if str(val).strip()
                ],
                "related_code_anchor_ids": [
                    str(val).strip() for val in (item.get("related_code_anchor_ids", []) or []) if str(val).strip()
                ],
            },
        }

    for item in spec_facts.get("property_specs", []) or []:
        if not isinstance(item, dict):
            continue
        trace_id = str(item.get("prop_id", "")).strip()
        if not trace_id:
            continue
        catalog[trace_id] = {
            "id": trace_id,
            "kind": "property",
            "summary": str(item.get("statement", "")).strip(),
            "details": {
                "statement": str(item.get("statement", "")).strip(),
                "intent": str(item.get("intent", "")).strip(),
                "related_req_ids": [
                    str(val).strip() for val in (item.get("related_req_ids", []) or []) if str(val).strip()
                ],
                "related_code_anchor_ids": [
                    str(val).strip() for val in (item.get("related_code_anchor_ids", []) or []) if str(val).strip()
                ],
            },
        }

    return catalog


def _normalize_context_id(value: Any) -> str:
    return str(value or "").strip().upper()


def _normalize_str_list(values: Optional[Iterable[Any]]) -> List[str]:
    return [str(item).strip() for item in (values or []) if str(item).strip()]


def build_implementation_node_catalog(spec_facts: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    spec_facts = spec_facts or {}
    catalog: Dict[str, Dict[str, Any]] = {}
    for item in spec_facts.get("implementation_nodes", []) or []:
        if not isinstance(item, dict):
            continue
        node_id = str(item.get("node_id", "")).strip()
        if not node_id:
            continue
        catalog[_normalize_context_id(node_id)] = {
            "node_id": node_id,
            "goal": str(item.get("goal", "")).strip(),
            "deliverables": _normalize_str_list(item.get("deliverables", [])),
            "gates": _normalize_str_list(item.get("gates", [])),
            "related_modules": _normalize_str_list(item.get("related_modules", [])),
            "related_files": _normalize_str_list(item.get("related_files", [])),
            "related_req_ids": _normalize_str_list(item.get("related_req_ids", [])),
            "unlock_tests": _normalize_str_list(item.get("unlock_tests", [])),
            "related_code_anchor_ids": _normalize_str_list(item.get("related_code_anchor_ids", [])),
        }
    return catalog


def build_code_anchor_catalog(spec_facts: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    spec_facts = spec_facts or {}
    catalog: Dict[str, Dict[str, Any]] = {}
    for item in spec_facts.get("code_anchors", []) or []:
        if not isinstance(item, dict):
            continue
        anchor_id = str(item.get("anchor_id", "")).strip()
        if not anchor_id:
            continue
        catalog[_normalize_context_id(anchor_id)] = {
            "anchor_id": anchor_id,
            "section": str(item.get("section", "")).strip(),
            "anchor_type": str(item.get("anchor_type", "")).strip(),
            "language": str(item.get("language", "")).strip(),
            "purpose": str(item.get("purpose", "")).strip(),
            "code": str(item.get("code", "")).strip(),
            "target_modules": _normalize_str_list(item.get("target_modules", [])),
            "target_registers": _normalize_str_list(item.get("target_registers", [])),
            "target_requirements": _normalize_str_list(item.get("target_requirements", [])),
            "target_tests": _normalize_str_list(item.get("target_tests", [])),
            "target_nodes": _normalize_str_list(item.get("target_nodes", [])),
        }
    return catalog


def build_implementation_hint_catalog(spec_facts: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    spec_facts = spec_facts or {}
    catalog: Dict[str, Dict[str, Any]] = {}
    for item in spec_facts.get("implementation_hints", []) or []:
        if not isinstance(item, dict):
            continue
        hint_id = str(item.get("hint_id", "")).strip()
        if not hint_id:
            continue
        catalog[_normalize_context_id(hint_id)] = {
            "hint_id": hint_id,
            "section": str(item.get("section", "")).strip(),
            "hint_type": str(item.get("hint_type", "")).strip(),
            "statement": str(item.get("statement", "")).strip(),
            "target_modules": _normalize_str_list(item.get("target_modules", [])),
            "target_tests": _normalize_str_list(item.get("target_tests", [])),
            "target_nodes": _normalize_str_list(item.get("target_nodes", [])),
        }
    return catalog


def build_file_implementation_context_by_path(
    file_specs: Optional[List[Dict[str, Any]]],
    node_catalog: Optional[Dict[str, Dict[str, Any]]],
    anchor_catalog: Optional[Dict[str, Dict[str, Any]]],
    hint_catalog: Optional[Dict[str, Dict[str, Any]]],
) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    contexts: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
    node_catalog = node_catalog or {}
    anchor_catalog = anchor_catalog or {}
    hint_catalog = hint_catalog or {}

    for spec in file_specs or []:
        if not isinstance(spec, dict):
            continue
        file_path = str(spec.get("file_path", "")).strip()
        if not file_path:
            continue
        contexts[file_path] = {
            "nodes": [
                node_catalog[node_id]
                for node_id in (_normalize_context_id(item) for item in (spec.get("related_node_ids", []) or []))
                if node_id in node_catalog
            ],
            "anchors": [
                anchor_catalog[anchor_id]
                for anchor_id in (_normalize_context_id(item) for item in (spec.get("related_code_anchor_ids", []) or []))
                if anchor_id in anchor_catalog
            ],
            "hints": [
                hint_catalog[hint_id]
                for hint_id in (_normalize_context_id(item) for item in (spec.get("related_hint_ids", []) or []))
                if hint_id in hint_catalog
            ],
        }
    return contexts


def _filter_context_by_module(
    items: List[Dict[str, Any]],
    module_name: str,
    target_key: str,
) -> List[Dict[str, Any]]:
    if not module_name:
        return list(items)

    filtered: List[Dict[str, Any]] = []
    normalized_module = str(module_name).strip()
    for item in items:
        targets = _normalize_str_list(item.get(target_key, []))
        if not targets or normalized_module in targets:
            filtered.append(item)
    return filtered


def build_unit_implementation_context(
    file_path: str,
    unit_kind: str,
    module_name: str,
    file_implementation_context_by_path: Optional[Dict[str, Dict[str, List[Dict[str, Any]]]]],
) -> Dict[str, List[Dict[str, Any]]]:
    file_context = dict((file_implementation_context_by_path or {}).get(file_path, {}) or {})
    nodes = list(file_context.get("nodes", []) or [])
    anchors = list(file_context.get("anchors", []) or [])
    hints = list(file_context.get("hints", []) or [])

    if unit_kind in {"rtl_module", "rtl_top_module"}:
        nodes = _filter_context_by_module(nodes, module_name, "related_modules")
        anchors = _filter_context_by_module(anchors, module_name, "target_modules")
        hints = _filter_context_by_module(hints, module_name, "target_modules")

    return {
        "nodes": nodes,
        "anchors": anchors,
        "hints": hints,
    }


def clip_implementation_code(code: str, max_lines: int = 20, max_chars: int = 800) -> str:
    text = str(code or "").strip()
    if not text:
        return ""
    lines = text.splitlines()
    clipped = "\n".join(lines[:max_lines])
    if len(clipped) > max_chars:
        clipped = clipped[:max_chars].rstrip()
    if clipped != text:
        clipped = clipped.rstrip() + "\n..."
    return clipped


def format_implementation_context(
    implementation_context: Optional[Dict[str, List[Dict[str, Any]]]],
    include_code: bool = True,
    max_anchor_lines: int = 20,
    max_anchor_chars: int = 800,
) -> str:
    implementation_context = implementation_context or {}
    nodes = implementation_context.get("nodes", []) or []
    anchors = implementation_context.get("anchors", []) or []
    hints = implementation_context.get("hints", []) or []

    if not nodes and not anchors and not hints:
        return "- No implementation context."

    blocks: List[str] = []

    if nodes:
        node_lines = []
        for item in nodes:
            node_lines.append(
                f"- {item.get('node_id', '')}: goal={item.get('goal', '-')}, "
                f"deliverables={item.get('deliverables', [])}, gates={item.get('gates', [])}"
            )
        blocks.append("nodes:\n" + "\n".join(node_lines))

    if anchors:
        anchor_lines = []
        for item in anchors:
            anchor_lines.append(
                f"- {item.get('anchor_id', '')}: type={item.get('anchor_type', '')}, purpose={item.get('purpose', '-')}"
            )
            if include_code:
                clipped_code = clip_implementation_code(
                    item.get("code", ""),
                    max_lines=max_anchor_lines,
                    max_chars=max_anchor_chars,
                )
                if clipped_code:
                    anchor_lines.append(f"  code:\n{clipped_code}")
        blocks.append("anchors:\n" + "\n".join(anchor_lines))

    if hints:
        hint_lines = []
        for item in hints:
            hint_lines.append(
                f"- {item.get('hint_id', '')}: type={item.get('hint_type', '')}, statement={item.get('statement', '-')}"
            )
        blocks.append("hints:\n" + "\n".join(hint_lines))

    return "\n\n".join(blocks)


def build_trace_context(trace_ids: List[str], trace_catalog: Optional[Dict[str, Dict[str, Any]]]) -> List[Dict[str, Any]]:
    context: List[Dict[str, Any]] = []
    trace_catalog = trace_catalog or {}
    for trace_id in trace_ids:
        value = str(trace_id).strip()
        if not value:
            continue
        if value in trace_catalog:
            context.append(trace_catalog[value])
        else:
            context.append(
                {
                    "id": value,
                    "kind": "unknown",
                    "summary": "",
                    "details": {},
                }
            )
    return context


def format_trace_context(trace_context: List[Dict[str, Any]], include_details: bool = True) -> str:
    if not trace_context:
        return "- No canonical trace context."

    lines: List[str] = []
    for item in trace_context:
        if not isinstance(item, dict):
            continue
        trace_id = str(item.get("id", "")).strip()
        kind = str(item.get("kind", "")).strip()
        summary = str(item.get("summary", "")).strip()
        lines.append(f"- {trace_id} ({kind}): {summary or '-'}")
        if not include_details:
            continue
        details = item.get("details", {}) or {}
        if kind == "requirement":
            corner_cases = ", ".join(details.get("corner_cases", []) or []) or "-"
            verify_refs = ", ".join(details.get("verify_refs", []) or []) or "-"
            lines.append(f"  corner_cases: {corner_cases}")
            lines.append(f"  verify_refs: {verify_refs}")
        elif kind == "test":
            checks = ", ".join(details.get("checks", []) or []) or "-"
            driver_tasks = ", ".join(details.get("driver_tasks", []) or []) or "-"
            lines.append(f"  checks: {checks}")
            lines.append(f"  driver_tasks: {driver_tasks}")
        elif kind == "property":
            intent = str(details.get("intent", "")).strip() or "-"
            lines.append(f"  intent: {intent}")
    return "\n".join(lines)
