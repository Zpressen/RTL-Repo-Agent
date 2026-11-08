from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from typing import Dict, List, Tuple

from ..schemas import (
    BlockBehaviorOverlay,
    BehaviorObligation,
    DecisionEntry,
    ModuleBehaviorSummary,
    ModuleSkeletonExport,
    SourceRefs,
    StructuralBlock,
)
from .local_repair import ArtifactIssue, model_issues, strict_json


_DOC_HEADER = "# MODULE_SKELETON_DOC v1"
_SECTION_PATTERN = re.compile(r"^ {0,3}##\s+(?:(\d+)\.\s+)?(.+?)\s*$")
_SUBSECTION_PATTERN = re.compile(r"^ {0,3}###\s+(.+?)\s*$")
_FIELD_BULLET_PATTERN = re.compile(r"^(?P<indent>\s*)(?:-|\*)\s+(?P<body>.+?)\s*$")


def _match_field_line(line: str, key: str) -> tuple[str, str] | None:
    match = _FIELD_BULLET_PATTERN.match(line)
    if match:
        body = match.group("body")
        member = re.fullmatch(rf"{re.escape(key)}\s*:\s*(.*)", body)
        if member:
            return match.group("indent"), member.group(1).strip()

    # LLMs commonly render mapping members under a list entry without
    # repeating the bullet marker, for example:
    #
    #   - topic: organization
    #     decision: keep related behavior together
    #     reason: preserves coupling
    #
    # This is an ordinary Markdown/YAML-style representation difference, not
    # a missing planning field.  Accept the indented and unindented mapping
    # forms so cosmetic punctuation cannot abort the planning pipeline.
    bare = re.match(
        rf"^(?P<indent>\s*){re.escape(key)}\s*:\s*(?P<value>.*?)\s*$",
        line,
    )
    if bare:
        return bare.group("indent"), bare.group("value").strip()
    return None


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
    result = inspect_module_skeleton_doc(
        doc_text, expected_module=expected_module, expected_file_path=expected_file_path, source_refs=source_refs,
    )
    if result.issues:
        raise SkeletonDocError(result)
    return result.artifact


@dataclass
class DocRegion:
    name: str
    start: int
    body_start: int
    end: int
    line: int


@dataclass
class SkeletonParseResult:
    candidate: dict
    issues: list[ArtifactIssue]
    normalized_doc: str
    artifact: ModuleSkeletonExport | None = None
    normalizations: list[str] = field(default_factory=list)
    regions: list[DocRegion] = field(default_factory=list)


class SkeletonDocError(ValueError):
    def __init__(self, result):
        self.result = result
        super().__init__("; ".join(f"{issue.path} (line {issue.line}): {issue.message}" for issue in result.issues))


def scan_doc_regions(text: str, *, level: int = 2) -> tuple[list[DocRegion], list[ArtifactIssue]]:
    """Scan headings outside CommonMark fences, retaining exact replacement ranges."""
    regions = []
    issues = []
    offset = 0
    fence = None
    for number, line in enumerate(text.splitlines(keepends=True), 1):
        stripped = line.strip()
        fence_match = re.match(r"^(`{3,}|~{3,})(.*)$", stripped)
        if fence is not None:
            if fence_match and fence_match.group(1)[0] == fence[0] and len(fence_match.group(1)) >= fence[1] and not fence_match.group(2).strip():
                fence = None
        elif fence_match:
            fence = (fence_match.group(1)[0], len(fence_match.group(1)), number)
        else:
            pattern = _SECTION_PATTERN if level == 2 else _SUBSECTION_PATTERN
            match = pattern.match(line.rstrip("\r\n"))
            if match:
                if regions:
                    regions[-1].end = offset
                name = match.group(2 if level == 2 else 1).strip()
                regions.append(DocRegion(name, offset, offset + len(line), len(text), number))
        offset += len(line)
    if fence:
        issues.append(ArtifactIssue("document", "unclosed_fence", "Unclosed code fence", line=fence[2]))
    if level == 2:
        seen = set()
        for region in regions:
            if region.name in seen:
                issues.append(ArtifactIssue(region.name, "duplicate_section", f"Duplicate section `{region.name}`", section=region.name, line=region.line))
            seen.add(region.name)
    return regions, issues


def inspect_module_skeleton_doc(doc_text: str, *, expected_module: str, expected_file_path: str, source_refs: SourceRefs) -> SkeletonParseResult:
    issues: list[ArtifactIssue] = []
    changes: list[str] = []
    positions: dict[str, int] = {}
    text = doc_text
    # Remove an enclosing Markdown fence only; leave all RTL bodies intact.
    outer = re.fullmatch(r"\s*(`{3,}|~{3,})(?:markdown|md)?\s*\n(.*)\n\1\s*", text, re.DOTALL)
    if outer:
        text = outer.group(2)
        changes.append("Removed enclosing Markdown fence")
    regions, scan_issues = scan_doc_regions(text)
    issues.extend(scan_issues)
    if not text.lstrip().splitlines() or text.lstrip().splitlines()[0].rstrip() not in {_DOC_HEADER, "# MODULE_SKELETON_DOC v2"}:
        issues.append(ArtifactIssue("document", "invalid_header", f"SkeletonDoc must begin with `{_DOC_HEADER}`", line=1))
    required = ["Module Identity", "Module Frame", "Structural Skeleton", "Behavioral Overlay", "Decision Ledger"]
    region_by_name = {r.name: r for r in regions if sum(x.name == r.name for x in regions) == 1}
    for name in required:
        if name not in {r.name for r in regions}:
            issues.append(ArtifactIssue(name, "missing_section", f"Missing required section `{name}`", section=name, line=len(text.splitlines()) + 1))
    for region in regions:
        if region.name not in required:
            issues.append(ArtifactIssue(region.name, "unknown_section", f"Unknown section `{region.name}`", section=region.name, line=region.line))

    # A plain risk/deferred list is equivalent to an items mapping. Normalize
    # only when every nonempty line is a bullet, without guessing absent content.
    ledger = region_by_name.get("Decision Ledger")
    replacements = []
    if ledger:
        body = text[ledger.body_start:ledger.end]
        subregions, _ = scan_doc_regions(body, level=3)
        for sub in subregions:
            if sub.name not in {"Deferred Decision", "Structural Risk", "Behavioral Risk"}:
                continue
            content = body[sub.body_start:sub.end]
            lines = [line for line in content.splitlines() if line.strip()]
            if lines and all(_FIELD_BULLET_PATTERN.match(line) for line in lines) and not any(_match_field_line(line, "items") for line in lines):
                # Preserve the original text, nesting it under the missing wrapper.
                value = "- items:\n" + "".join("  " + line if line.strip() else line for line in content.splitlines(keepends=True))
                replacements.append((ledger.body_start + sub.body_start, ledger.body_start + sub.end, value))
                changes.append(f"Wrapped plain {sub.name} list in items")
        for start, end, value in reversed(replacements):
            text = text[:start] + value + text[end:]
        regions, _ = scan_doc_regions(text)
        region_by_name = {r.name: r for r in regions if sum(x.name == r.name for x in regions) == 1}

    enhanced = text.lstrip().splitlines()[0].rstrip() == "# MODULE_SKELETON_DOC v2" if text.lstrip().splitlines() else False
    payload: dict[str, Any] = {"schema_version": "module_skeleton_export_v2" if enhanced else "module_skeleton_export_v1", "module": expected_module, "file_path": expected_file_path, "source_refs": source_refs.model_dump() if hasattr(source_refs, "model_dump") else source_refs}

    def collect(content, fields, path, section, line, unit=""):
        data = {}
        positions[path] = line
        for key, extractor in fields.items():
            field_line = next((line + i for i, item in enumerate(content.splitlines()) if _match_field_line(item, key)), line)
            positions[f"{path}.{key}"] = field_line
            try:
                data[key] = extractor(content, key)
            except (ValueError, TypeError) as exc:
                issues.append(ArtifactIssue(
                    f"{path}.{key}", "missing_required_field" if "Missing" in str(exc) else "invalid_field",
                    str(exc), expected=(f"Explicit {key} list; use [] when empty" if extractor in {_extract_list, _extract_mode_list, _extract_mapping_list} else f"Explicit nonempty {key}"),
                    section=section, unit_id=unit, line=field_line,
                ))
        return data

    def check(model, data, path, section, line, unit=""):
        artifact, found = model_issues(model, data, prefix=path, section=section, unit_id=unit)
        # Missing fields already have a more precise extraction diagnostic.
        existing = {issue.path for issue in issues}
        for issue in found:
            if issue.path not in existing:
                issue.line = line
                issues.append(issue)
        return artifact

    identity = region_by_name.get("Module Identity")
    if identity:
        content = text[identity.body_start:identity.end]
        data = collect(content, {"module_name": _extract_scalar, "file_path": _extract_scalar}, "identity", identity.name, identity.line + 1)
        for key, expected in (("module_name", expected_module), ("file_path", expected_file_path)):
            if key in data and data[key] != expected:
                issues.append(ArtifactIssue(f"identity.{key}", "identity_mismatch", f"{key} must be `{expected}`, got `{data[key]}`", expected, data[key], "structure", identity.name, line=identity.line))
        payload["planning_note"] = _parse_module_identity(content).get("planning_note", "")
    frame = region_by_name.get("Module Frame")
    if frame:
        try:
            payload["module_frame"] = _extract_first_fenced_block(text[frame.body_start:frame.end], expected_language="verilog")
        except ValueError as exc:
            issues.append(ArtifactIssue("module_frame", "invalid_code_fence", str(exc), section=frame.name, line=frame.line + 1))

    structural = region_by_name.get("Structural Skeleton")
    if structural:
        body = text[structural.body_start:structural.end]
        subs, _ = scan_doc_regions(body, level=3)
        payload["structural_blocks"] = []
        if not subs:
            issues.append(ArtifactIssue("structural_blocks", "missing_blocks", "Structural Skeleton must contain at least one `### Block` subsection", section=structural.name, line=structural.line))
        fields = {key: _extract_scalar for key in ("block_id", "block_label", "block_kind", "purpose", "code_shape")}
        fields.update({key: _extract_list for key in ("depends_on", "must_appear", "may_appear", "retrieval_focus")})
        fields["required"] = _extract_bool
        fields["placeholder"] = lambda c, k: _extract_fenced_block_after_key(c, k, expected_language="verilog")
        for index, sub in enumerate(subs):
            line = structural.line + sub.line
            if sub.name != "Block":
                issues.append(ArtifactIssue(f"structural_blocks[{index}]", "unknown_subsection", f"Structural Skeleton only allows `### Block`, got `### {sub.name}`", section=structural.name, line=line))
            data = collect(body[sub.body_start:sub.end], fields, f"structural_blocks[{index}]", structural.name, line + 1)
            check(StructuralBlock, data, f"structural_blocks[{index}]", structural.name, line)
            payload["structural_blocks"].append(data)

    behavioral = region_by_name.get("Behavioral Overlay")
    if behavioral:
        body = text[behavioral.body_start:behavioral.end]
        subs, _ = scan_doc_regions(body, level=3)
        payload["block_behavior_overlays"] = []
        summaries = 0
        for sub in subs:
            content = body[sub.body_start:sub.end]
            line = behavioral.line + sub.line
            if sub.name == "Module-Level Behavioral Summary":
                summaries += 1
                fields = {"control_style": _extract_scalar, "semantic_modes": _extract_list, "state_model": _extract_mapping_list, "global_invariants": _extract_list, "open_semantic_questions": _extract_list}
                data = collect(content, fields, "module_behavior", behavioral.name, line + 1)
                modes = []
                for i, mode in enumerate(data.get("semantic_modes", [])):
                    if ":" not in mode:
                        issues.append(ArtifactIssue(f"module_behavior.semantic_modes[{i}]", "ambiguous_semantic_mode", f"semantic mode entry must be `MODE: meaning`, got `{mode}`", expected="MODE: meaning", actual=mode, section=behavioral.name, line=line + 1))
                        modes.append(mode)
                    else:
                        name, meaning = mode.split(":", 1)
                        modes.append({"mode": name.strip(), "meaning": meaning.strip()})
                if "semantic_modes" in data:
                    data["semantic_modes"] = modes
                for i, state in enumerate(data.get("state_model", [])):
                    for key in ("object", "storage_kind", "representation"):
                        if not str(state.get(key, "")).strip():
                            issues.append(ArtifactIssue(f"module_behavior.state_model[{i}].{key}", "missing_required_field", f"State entry requires explicit {key}", section=behavioral.name, line=line + 1))
                check(ModuleBehaviorSummary, data, "module_behavior", behavioral.name, line)
                payload["module_behavior"] = data
            elif sub.name == "Behavioral Obligations":
                try:
                    raw = strict_json(_extract_first_fenced_block(content, expected_language="json"))
                    if not isinstance(raw, list):
                        raise ValueError("Behavioral Obligations must be a JSON array")
                    payload["behavioral_obligations"] = raw
                    for i, item in enumerate(raw):
                        unit = item.get("obligation_id", "") if isinstance(item, dict) else ""
                        check(BehaviorObligation, item, f"behavioral_obligations[{i}]", behavioral.name, line, unit)
                except (ValueError, TypeError) as exc:
                    issues.append(ArtifactIssue("behavioral_obligations", "invalid_obligations", str(exc), section=behavioral.name, line=line))
            elif sub.name == "Block Behavioral Overlay":
                starts = [i for i, value in enumerate(content.splitlines()) if _match_field_line(value, "block_id")]
                content_lines = content.splitlines()
                entries = [("\n".join(content_lines[start:starts[i + 1] if i + 1 < len(starts) else len(content_lines)]), line + 1 + start) for i, start in enumerate(starts)] or [(content, line + 1)]
                for entry, entry_line in entries:
                    index = len(payload["block_behavior_overlays"])
                    fields = {"block_id": _extract_scalar, **{key: _extract_list for key in ("responsibilities", "timing_semantics", "touched_objects", "coupling_rules", "forbidden_drift")}}
                    data = collect(entry, fields, f"block_behavior_overlays[{index}]", behavioral.name, entry_line)
                    unit = data.get("block_id", "")
                    # Carry identity for a future block-local patch, without matching by index alone.
                    for issue in issues:
                        if issue.path.startswith(f"block_behavior_overlays[{index}]"):
                            issue.unit_id = unit
                    check(BlockBehaviorOverlay, data, f"block_behavior_overlays[{index}]", behavioral.name, entry_line, unit)
                    payload["block_behavior_overlays"].append(data)
            else:
                issues.append(ArtifactIssue("module_behavior", "unknown_subsection", f"Behavioral Overlay does not recognize `### {sub.name}`", section=behavioral.name, line=line))
        if enhanced and not any(sub.name == "Behavioral Obligations" for sub in subs):
            issues.append(ArtifactIssue("behavioral_obligations", "missing_obligations", "v2 requires Behavioral Obligations JSON section", section=behavioral.name, line=behavioral.line))
        if summaries != 1:
            issues.append(ArtifactIssue("module_behavior", "summary_count", "Behavioral Overlay requires exactly one module-level summary", section=behavioral.name, line=behavioral.line))

    ledger = region_by_name.get("Decision Ledger")
    if ledger:
        body = text[ledger.body_start:ledger.end]
        subs, _ = scan_doc_regions(body, level=3)
        data = {"chosen_decisions": [], "deferred_decisions": [], "structural_risks": [], "behavioral_risks": []}
        counts = {name: 0 for name in ("Deferred Decision", "Structural Risk", "Behavioral Risk")}
        for sub in subs:
            content = body[sub.body_start:sub.end]
            line = ledger.line + sub.line
            if sub.name == "Chosen Decision":
                index = len(data["chosen_decisions"])
                path = f"decision_ledger.chosen_decisions[{index}]"
                entry = collect(content, {key: _extract_scalar for key in ("topic", "decision", "reason")}, path, ledger.name, line + 1)
                check(DecisionEntry, entry, path, ledger.name, line)
                data["chosen_decisions"].append(entry)
            elif sub.name in counts:
                counts[sub.name] += 1
                key = {"Deferred Decision": "deferred_decisions", "Structural Risk": "structural_risks", "Behavioral Risk": "behavioral_risks"}[sub.name]
                entry = collect(content, {"items": _extract_list}, f"decision_ledger.{key}", ledger.name, line + 1)
                data[key].extend(entry.get("items", []))
            else:
                issues.append(ArtifactIssue("decision_ledger", "unknown_subsection", f"Decision Ledger does not recognize `### {sub.name}`", section=ledger.name, line=line))
        if not data["chosen_decisions"]:
            issues.append(ArtifactIssue("decision_ledger.chosen_decisions", "missing_required_field", "Decision Ledger requires a Chosen Decision", section=ledger.name, line=ledger.line))
        for name, count in counts.items():
            if count != 1:
                issues.append(ArtifactIssue("decision_ledger", "subsection_count", f"Decision Ledger requires exactly one {name} subsection; use items: [] when empty", section=ledger.name, line=ledger.line))
        payload["decision_ledger"] = data

    # Reference checks run independently, so a missing decision cannot hide them.
    blocks = payload.get("structural_blocks", [])
    ids = [item.get("block_id") for item in blocks if item.get("block_id")]
    for index, block in enumerate(blocks):
        block_id = block.get("block_id")
        if block_id and ids.count(block_id) > 1:
            issues.append(ArtifactIssue(f"structural_blocks[{index}].block_id", "duplicate_block", f"Duplicate block_id `{block_id}`", category="structure", section="Structural Skeleton", line=positions.get(f"structural_blocks[{index}].block_id")))
        for dep in block.get("depends_on", []):
            if dep not in ids:
                issues.append(ArtifactIssue(f"structural_blocks[{index}].depends_on", "unknown_reference", f"Unknown block `{dep}`", category="structure", section="Structural Skeleton", line=positions.get(f"structural_blocks[{index}].depends_on")))
    overlays = payload.get("block_behavior_overlays", [])
    overlay_ids = [item.get("block_id") for item in overlays]
    for index, overlay in enumerate(overlays):
        block_id = overlay.get("block_id")
        if block_id and (block_id not in ids or overlay_ids.count(block_id) > 1):
            issues.append(ArtifactIssue(f"block_behavior_overlays[{index}].block_id", "invalid_reference", f"overlay references unknown block_id or duplicate block_id `{block_id}`", category="structure", section="Behavioral Overlay", unit_id=block_id, line=positions.get(f"block_behavior_overlays[{index}].block_id")))
    artifact = None
    if not issues:
        artifact, found = model_issues(ModuleSkeletonExport, payload)
        issues.extend(found)
    for issue in issues:
        issue.stage = "stage3_module_skeletons"
        issue.module = expected_module
    if artifact is not None and enhanced:
        from .responsibility_planning import derive_overlays
        derive_overlays(artifact)
    return SkeletonParseResult(payload, issues, text, artifact, changes, regions)


def _split_sections(doc_text: str) -> Dict[str, str]:
    regions, issues = scan_doc_regions(doc_text)
    if issues:
        raise ValueError("; ".join(issue.message for issue in issues))
    return {region.name: doc_text[region.body_start:region.end].strip() for region in regions}


def _split_subsections(section_text: str) -> List[Tuple[str, str]]:
    regions, issues = scan_doc_regions(section_text, level=3)
    if issues:
        raise ValueError("; ".join(issue.message for issue in issues))
    return [(region.name, section_text[region.body_start:region.end].strip()) for region in regions]


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
        match = _FIELD_BULLET_PATTERN.match(raw_line)
        if match and ":" in match.group("body"):
            key, value = match.group("body").split(":", 1)
            parsed[key.strip()] = value.strip()
    return parsed


def _extract_first_fenced_block(section_text: str, *, expected_language: str = "") -> str:
    lines = section_text.splitlines()
    inside = False
    collected: List[str] = []
    language = ""
    fence = None
    closed = False
    for line in lines:
        stripped = line.strip()
        match = re.fullmatch(r"(`{3,}|~{3,})(.*)", stripped)
        if match:
            if not inside:
                inside = True
                fence = match.group(1)
                language = match.group(2).strip().lower()
                continue
            if match.group(1)[0] == fence[0] and len(match.group(1)) >= len(fence) and not match.group(2).strip():
                closed = True
                break
        if inside:
            collected.append(line)
    if not collected or not closed:
        raise ValueError("Expected a fenced code block but none was found")
    if expected_language and language and language != expected_language:
        raise ValueError(f"Expected fenced block language `{expected_language}`, got `{language}`")
    return "\n".join(collected).strip()


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
        if not items:
            raise ValueError(f"List field `{key}` requires explicit items or []")
        return items
    raise ValueError(f"Missing list field `{key}`")


def _extract_mapping_list(content: str, key: str) -> List[dict]:
    lines = content.splitlines()
    start = -1
    parent_indent = ""
    for index, line in enumerate(lines):
        matched = _match_field_line(line, key)
        if matched is not None:
            if matched[1] == "[]":
                return []
            if matched[1]:
                raise ValueError(f"Mapping list `{key}` requires nested mappings or []")
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
                current = None
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
    if not items:
        raise ValueError(f"Mapping list `{key}` requires explicit mappings or []")
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
    return _extract_first_fenced_block("\n".join(lines[start:]), expected_language=expected_language)


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
