from __future__ import annotations

import re
from typing import Dict, List, Tuple

from ..schemas import (
    BlockBehaviorOverlay,
    DecisionEntry,
    DecisionLedger,
    ModuleBehaviorSummary,
    ModuleSkeletonExport,
    SemanticMode,
    SourceRefs,
    StateModelEntry,
    StructuralBlock,
)


def _validate_model(model_type, payload):
    try:
        return model_type.model_validate(payload)
    except AttributeError:
        return model_type.parse_obj(payload)


_DOC_HEADER = "# MODULE_SKELETON_DOC v1"
_SECTION_PATTERN = re.compile(r"^##\s+(?:(\d+)\.\s+)?(.+?)\s*$")
_SUBSECTION_PATTERN = re.compile(r"^###\s+(.+?)\s*$")
_FIELD_BULLET_PATTERN = re.compile(r"^(?P<indent>\s*)(?:-|\*)\s+(?P<body>.+?)\s*$")


def _match_field_line(line: str, key: str) -> tuple[str, str] | None:
    match = _FIELD_BULLET_PATTERN.match(line)
    if not match:
        return None
    body = match.group("body")
    prefix = f"{key}:"
    if not body.startswith(prefix):
        return None
    return match.group("indent"), body[len(prefix) :].strip()


def _is_nested_list_item(line: str, parent_indent: str) -> bool:
    match = _FIELD_BULLET_PATTERN.match(line)
    if not match:
        return False
    return len(match.group("indent")) > len(parent_indent)


def _nested_list_value(line: str) -> str:
    match = _FIELD_BULLET_PATTERN.match(line)
    if not match:
        return ""
    return match.group("body").strip()


def parse_module_skeleton_doc(
    doc_text: str,
    *,
    expected_module: str,
    expected_file_path: str,
    source_refs: SourceRefs,
) -> ModuleSkeletonExport:
    normalized = doc_text.strip()
    if not normalized.startswith(_DOC_HEADER):
        raise ValueError("SkeletonDoc must begin with `# MODULE_SKELETON_DOC v1`")
    section_map = _split_sections(normalized)
    required_sections = [
        "Module Identity",
        "Module Frame",
        "Structural Skeleton",
        "Behavioral Overlay",
        "Decision Ledger",
    ]
    for section_name in required_sections:
        if section_name not in section_map:
            raise ValueError(f"SkeletonDoc is missing required section `{section_name}`")

    identity = _parse_module_identity(section_map["Module Identity"])
    module_name = identity.get("module_name", "")
    file_path = identity.get("file_path", "")
    if module_name != expected_module:
        raise ValueError(f"SkeletonDoc module_name must be `{expected_module}`, got `{module_name}`")
    if file_path != expected_file_path:
        raise ValueError(f"SkeletonDoc file_path must be `{expected_file_path}`, got `{file_path}`")

    module_frame = _extract_first_fenced_block(section_map["Module Frame"], expected_language="verilog")
    structural_blocks = _parse_structural_blocks(section_map["Structural Skeleton"])
    behavior_summary, block_overlays = _parse_behavioral_overlay(section_map["Behavioral Overlay"])
    decision_ledger = _parse_decision_ledger(section_map["Decision Ledger"])

    export_payload = {
        "module": expected_module,
        "file_path": expected_file_path,
        "source_refs": source_refs,
        "planning_note": identity.get("planning_note", ""),
        "module_frame": module_frame,
        "structural_blocks": structural_blocks,
        "module_behavior": behavior_summary,
        "block_behavior_overlays": block_overlays,
        "decision_ledger": decision_ledger,
    }
    return _validate_model(ModuleSkeletonExport, export_payload)


def _split_sections(doc_text: str) -> Dict[str, str]:
    sections: Dict[str, List[str]] = {}
    current_key = ""
    for line in doc_text.splitlines():
        match = _SECTION_PATTERN.match(line)
        if match:
            current_key = match.group(2).strip()
            sections[current_key] = []
            continue
        if current_key:
            sections[current_key].append(line)
    return {key: "\n".join(value).strip() for key, value in sections.items()}


def _split_subsections(section_text: str) -> List[Tuple[str, str]]:
    subsections: List[Tuple[str, List[str]]] = []
    current_key = ""
    for line in section_text.splitlines():
        match = _SUBSECTION_PATTERN.match(line)
        if match:
            current_key = match.group(1).strip()
            subsections.append((current_key, []))
            continue
        if current_key:
            subsections[-1][1].append(line)
    return [(key, "\n".join(lines).strip()) for key, lines in subsections]


def _parse_module_identity(section_text: str) -> Dict[str, str]:
    parsed: Dict[str, str] = {}
    in_source_refs = False
    for raw_line in section_text.splitlines():
        if not raw_line.strip():
            continue
        line = raw_line.strip()
        if line.startswith("- source_refs:"):
            in_source_refs = True
            continue
        if in_source_refs and raw_line.startswith("  - "):
            continue
        in_source_refs = False
        if line.startswith("- ") and ":" in line:
            key, value = line[2:].split(":", 1)
            parsed[key.strip()] = value.strip()
    return parsed


def _extract_first_fenced_block(section_text: str, *, expected_language: str = "") -> str:
    lines = section_text.splitlines()
    inside = False
    collected: List[str] = []
    language = ""
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            if not inside:
                inside = True
                language = stripped[3:].strip()
                continue
            break
        if inside:
            collected.append(line)
    if not collected:
        raise ValueError("Expected a fenced code block but none was found")
    if expected_language and language and language != expected_language:
        raise ValueError(f"Expected fenced block language `{expected_language}`, got `{language}`")
    return "\n".join(collected).strip()


def _parse_structural_blocks(section_text: str) -> List[StructuralBlock]:
    blocks: List[StructuralBlock] = []
    subsections = _split_subsections(section_text)
    if not subsections:
        raise ValueError("Structural Skeleton must contain at least one `### Block` subsection")
    for title, content in subsections:
        if title != "Block":
            raise ValueError(f"Structural Skeleton only allows `### Block`, got `### {title}`")
        block = {
            "block_id": _extract_scalar(content, "block_id"),
            "block_label": _extract_scalar(content, "block_label"),
            "block_kind": _extract_scalar(content, "block_kind"),
            "required": _extract_bool(content, "required"),
            "purpose": _extract_scalar(content, "purpose"),
            "code_shape": _extract_scalar(content, "code_shape"),
            "depends_on": _extract_list(content, "depends_on"),
            "placeholder": _extract_fenced_block_after_key(content, "placeholder", expected_language="verilog"),
            "must_appear": _extract_list(content, "must_appear"),
            "may_appear": _extract_list(content, "may_appear"),
            "retrieval_focus": _extract_list(content, "retrieval_focus"),
        }
        blocks.append(_validate_model(StructuralBlock, block))
    return blocks


def _parse_behavioral_overlay(section_text: str) -> tuple[ModuleBehaviorSummary, List[BlockBehaviorOverlay]]:
    subsections = _split_subsections(section_text)
    if not subsections:
        raise ValueError("Behavioral Overlay must contain subsections")
    module_summary = None
    overlays: List[BlockBehaviorOverlay] = []
    for title, content in subsections:
        if title == "Module-Level Behavioral Summary":
            if module_summary is not None:
                raise ValueError("Behavioral Overlay may only contain one module-level summary")
            module_summary = _validate_model(
                ModuleBehaviorSummary,
                {
                    "control_style": _extract_scalar(content, "control_style"),
                    "semantic_modes": [
                        _validate_model(SemanticMode, item)
                        for item in _extract_mode_list(content, "semantic_modes")
                    ],
                    "state_model": [
                        _validate_model(StateModelEntry, item)
                        for item in _extract_mapping_list(content, "state_model")
                    ],
                    "global_invariants": _extract_list(content, "global_invariants"),
                    "open_semantic_questions": _extract_list(content, "open_semantic_questions"),
                },
            )
        elif title == "Block Behavioral Overlay":
            overlay_entries = _split_overlay_entries(content) or [content]
            for overlay_content in overlay_entries:
                overlays.append(
                    _validate_model(
                        BlockBehaviorOverlay,
                        {
                            "block_id": _extract_scalar(overlay_content, "block_id"),
                            "responsibilities": _extract_list(overlay_content, "responsibilities"),
                            "timing_semantics": _extract_list(overlay_content, "timing_semantics"),
                            "touched_objects": _extract_list(overlay_content, "touched_objects"),
                            "coupling_rules": _extract_list(overlay_content, "coupling_rules"),
                            "forbidden_drift": _extract_list(overlay_content, "forbidden_drift"),
                        },
                    )
                )
        else:
            raise ValueError(f"Behavioral Overlay does not recognize subsection `### {title}`")
    if module_summary is None:
        raise ValueError("Behavioral Overlay must contain `### Module-Level Behavioral Summary`")
    return module_summary, overlays


def _parse_decision_ledger(section_text: str) -> DecisionLedger:
    chosen_decisions: List[DecisionEntry] = []
    deferred_decisions: List[str] = []
    structural_risks: List[str] = []
    behavioral_risks: List[str] = []
    subsections = _split_subsections(section_text)
    if not subsections:
        raise ValueError("Decision Ledger must contain subsections")
    for title, content in subsections:
        if title == "Chosen Decision":
            chosen_decisions.append(
                _validate_model(
                    DecisionEntry,
                    {
                        "topic": _extract_scalar(content, "topic"),
                        "decision": _extract_scalar(content, "decision"),
                        "reason": _extract_scalar(content, "reason"),
                    },
                )
            )
        elif title == "Deferred Decision":
            deferred_decisions.extend(_extract_list(content, "items"))
        elif title == "Structural Risk":
            structural_risks.extend(_extract_list(content, "items"))
        elif title == "Behavioral Risk":
            behavioral_risks.extend(_extract_list(content, "items"))
        else:
            raise ValueError(f"Decision Ledger does not recognize subsection `### {title}`")
    return _validate_model(
        DecisionLedger,
        {
            "chosen_decisions": chosen_decisions,
            "deferred_decisions": deferred_decisions,
            "structural_risks": structural_risks,
            "behavioral_risks": behavioral_risks,
        },
    )


def _extract_scalar(content: str, key: str) -> str:
    for line in content.splitlines():
        matched = _match_field_line(line, key)
        if matched is not None:
            _, value = matched
            if value:
                return value
            break
    raise ValueError(f"Missing scalar field `{key}`")


def _extract_bool(content: str, key: str) -> bool:
    value = _extract_scalar(content, key).lower()
    if value not in {"true", "false"}:
        raise ValueError(f"Boolean field `{key}` must be `true` or `false`, got `{value}`")
    return value == "true"


def _extract_list(content: str, key: str) -> List[str]:
    lines = content.splitlines()
    for index, line in enumerate(lines):
        matched = _match_field_line(line, key)
        if matched is None:
            continue
        parent_indent, tail = matched
        if tail:
            if tail == "[]":
                return []
            if tail.startswith("[") and tail.endswith("]"):
                inner = tail[1:-1].strip()
                if not inner:
                    return []
                return [item.strip().strip('"').strip("'") for item in inner.split(",") if item.strip()]
            return [tail]
        items: List[str] = []
        cursor = index + 1
        while cursor < len(lines):
            nested = lines[cursor]
            if _is_nested_list_item(nested, parent_indent):
                items.append(_nested_list_value(nested))
                cursor += 1
                continue
            if nested.strip() == "":
                cursor += 1
                continue
            break
        return items
    raise ValueError(f"Missing list field `{key}`")


def _extract_mapping_list(content: str, key: str) -> List[dict]:
    lines = content.splitlines()
    start = -1
    parent_indent = ""
    for index, line in enumerate(lines):
        matched = _match_field_line(line, key)
        if matched is not None:
            start = index + 1
            parent_indent = matched[0]
            break
    if start < 0:
        raise ValueError(f"Missing mapping list field `{key}`")
    items: List[dict] = []
    current: dict | None = None
    cursor = start
    while cursor < len(lines):
        line = lines[cursor]
        if _is_nested_list_item(line, parent_indent):
            if current is not None:
                items.append(current)
            nested_value = _nested_list_value(line)
            if ":" not in nested_value:
                # Tolerate free-form entries (e.g. "No registers; fully combinational")
                items.append({"_note": nested_value.strip()})
                cursor += 1
                continue
            key_name, value = nested_value.split(":", 1)
            current = {key_name.strip(): value.strip()}
            cursor += 1
            while cursor < len(lines):
                nested = lines[cursor]
                nested_match = _FIELD_BULLET_PATTERN.match(nested)
                if nested_match and len(nested_match.group("indent")) > len(parent_indent) + 1 and ":" in nested_match.group("body"):
                    nested_key, nested_value = nested_match.group("body").split(":", 1)
                    current[nested_key.strip()] = nested_value.strip()
                    cursor += 1
                    continue
                if len(nested) - len(nested.lstrip(" ")) > len(parent_indent) + 1 and ":" in nested.strip():
                    nested_key, nested_value = nested.strip().split(":", 1)
                    current[nested_key.strip()] = nested_value.strip()
                    cursor += 1
                    continue
                if nested.strip() == "":
                    cursor += 1
                    continue
                break
            continue
        if line.strip() == "":
            cursor += 1
            continue
        break
    if current is not None:
        items.append(current)
    return items


def _extract_mode_list(content: str, key: str) -> List[dict]:
    items = _extract_list(content, key)
    parsed: List[dict] = []
    for item in items:
        if ":" not in item:
            raise ValueError(f"semantic mode entry must be `MODE: meaning`, got `{item}`")
        mode, meaning = item.split(":", 1)
        parsed.append({"mode": mode.strip(), "meaning": meaning.strip()})
    return parsed


def _extract_fenced_block_after_key(content: str, key: str, *, expected_language: str = "") -> str:
    lines = content.splitlines()
    start = -1
    for index, line in enumerate(lines):
        if _match_field_line(line, key) is not None:
            start = index + 1
            break
    if start < 0:
        raise ValueError(f"Missing fenced block field `{key}`")
    block_lines: List[str] = []
    inside = False
    language = ""
    for line in lines[start:]:
        stripped = line.strip()
        if stripped.startswith("```"):
            if not inside:
                inside = True
                language = stripped[3:].strip()
                continue
            break
        if inside:
            block_lines.append(line)
        elif stripped:
            continue
    if not block_lines:
        raise ValueError(f"Field `{key}` must contain a fenced code block")
    if expected_language and language and language != expected_language:
        raise ValueError(f"Field `{key}` must use fenced block language `{expected_language}`, got `{language}`")
    return "\n".join(block_lines).strip()


def _split_overlay_entries(content: str) -> List[str]:
    entries: List[List[str]] = []
    current: List[str] = []
    for line in content.splitlines():
        matched = _match_field_line(line, "block_id")
        if matched is not None:
            if current:
                entries.append(current)
            current = [line]
            continue
        if current:
            current.append(line)
    if current:
        entries.append(current)
    return ["\n".join(item).strip() for item in entries if any(line.strip() for line in item)]
