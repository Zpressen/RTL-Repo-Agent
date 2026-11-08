from __future__ import annotations

from zerorepo.rtl_impl.artifact_layout import ArtifactLayout, artifact_path, artifact_dir

import json
import re
import shutil
from pathlib import Path
from typing import Any, Iterable

from ..schemas import PlannerTaskInput


DEFINE_NOTE_MARKERS = (
    "not a synthesizable module",
    "provides constants",
    "global parameter",
    "global defines",
    "preprocessor define",
)

E203_CANONICAL_DEFINE_PROJECTS = {
    "e203_ifu": Path("e203_hbirdv2") / "e203_ifu" / "verification",
    "e203_exu_alu": Path("e203_hbirdv2") / "e203_exu_alu" / "verification",
    "e203_exu_alu_system": Path("e203_hbirdv2") / "e203_exu_alu" / "verification",
}
E203_CANONICAL_DEFINE_FILES = ("config.v", "e203_defines.v")

_DIRECTIVE_RE = re.compile(r"^\s*`(?P<directive>[A-Za-z_][A-Za-z0-9_]*)\b(?P<body>.*)$")
_MACRO_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_$]*")
_MACRO_REFERENCE_RE = re.compile(r"`?([A-Za-z_][A-Za-z0-9_$]*)")


def is_define_only_module(module_name: str, repo_skeleton: Any | None = None) -> bool:
    if module_name.endswith("_defines") or module_name in {"defines", "sd_defines"}:
        return True
    if repo_skeleton is None:
        return False
    for record in getattr(repo_skeleton, "modules", []) or []:
        if getattr(record, "module", "") != module_name:
            continue
        notes = " ".join(getattr(record, "repo_notes", []) or []).lower()
        role = str(getattr(record, "role", "") or "").lower()
        return any(marker in notes or marker in role for marker in DEFINE_NOTE_MARKERS)
    return False


def infer_realbench_project(task: PlannerTaskInput) -> str:
    for raw in task.spec_md_files:
        path = Path(raw).expanduser()
        parts = path.parts
        if "rtl_dataset" in parts:
            idx = parts.index("rtl_dataset")
            if idx + 1 < len(parts):
                return parts[idx + 1]
        if path.parent.name:
            return path.parent.name
    return task.task_id


def find_official_define_file(task: PlannerTaskInput, module_name: str) -> Path | None:
    project = infer_realbench_project(task)
    roots = [
        Path("/home/mokita/RealBench"),
        Path.home() / "RealBench",
    ]
    candidates: list[Path] = []
    for root in roots:
        candidates.extend(
            [
                root / project / module_name / f"{module_name}.v",
                root / project / module_name / "verification" / f"{module_name}.v",
                root / project / "sd_defines" / "sd_defines.v",
                root / project / "rtl" / f"{module_name}.v",
            ]
        )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return None


def copy_official_define_file(
    *,
    task: PlannerTaskInput,
    module_name: str,
    workspace_root: Path,
    output_root: Path | None = None,
) -> dict[str, Any] | None:
    source = find_official_define_file(task, module_name)
    if source is None:
        return None
    merged_dir = artifact_dir(workspace_root, "merged")
    merged_dir.mkdir(parents=True, exist_ok=True)
    target = (merged_dir / f"{module_name}.v").resolve()
    shutil.copyfile(source, target)
    entry = {
        "name": f"{module_name}.v",
        "module": module_name,
        "source": str(source),
        "workspace_path": str(target),
        "mode": "official_copy",
        "must_include": True,
    }
    write_global_defines_manifest(workspace_root=workspace_root, output_root=output_root, entries=[entry])
    return entry


def copy_e203_canonical_define_files(
    *,
    top_module: str,
    oracle_root: str | Path,
    workspace_root: Path,
    output_root: Path | None = None,
) -> list[dict[str, Any]]:
    """Copy the canonical E203 configuration headers for supported system tasks.

    The operation is intentionally scoped to the two system-level E203 tasks
    whose verification environments declare these headers.  Both files are
    manifested, but only ``e203_defines.v`` is a direct include because it
    already includes ``config.v`` and neither official file has an include
    guard.
    """

    relative_dir = E203_CANONICAL_DEFINE_PROJECTS.get(str(top_module).strip())
    if relative_dir is None:
        return []

    verification_dir = (Path(oracle_root).expanduser() / relative_dir).resolve()
    sources = {
        name: (verification_dir / name).resolve()
        for name in E203_CANONICAL_DEFINE_FILES
    }
    missing = [str(path) for path in sources.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            f"Canonical E203 define file(s) missing for {top_module}: {', '.join(missing)}"
        )

    merged_dir = artifact_dir(workspace_root, "merged")
    merged_dir.mkdir(parents=True, exist_ok=True)
    targets = {name: (merged_dir / name).resolve() for name in sources}
    for name, source in sources.items():
        shutil.copyfile(source, targets[name])

    entries = [
        {
            "name": "config.v",
            "module": "config",
            "source": str(sources["config.v"]),
            "workspace_path": str(targets["config.v"]),
            "mode": "official_header_copy",
            "must_include": False,
            "included_by": ["e203_defines.v"],
        },
        {
            "name": "e203_defines.v",
            "module": "e203_defines",
            "source": str(sources["e203_defines.v"]),
            "workspace_path": str(targets["e203_defines.v"]),
            "mode": "official_header_copy",
            "must_include": True,
        },
    ]
    write_global_defines_manifest(
        workspace_root=workspace_root,
        output_root=output_root,
        entries=entries,
    )
    return entries


def write_global_defines_manifest(
    *,
    workspace_root: Path,
    output_root: Path | None,
    entries: list[dict[str, Any]],
) -> dict[str, Any]:
    workspace_root.mkdir(parents=True, exist_ok=True)
    manifest_path = artifact_path(workspace_root, "global_defines_manifest.json")
    existing: dict[str, Any] = {"schema_version": "global_defines_manifest_v1", "global_define_files": []}
    if manifest_path.exists():
        try:
            existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            existing = {"schema_version": "global_defines_manifest_v1", "global_define_files": []}
    by_name = {
        str(item.get("name") or item.get("module") or ""): item
        for item in existing.get("global_define_files", [])
        if isinstance(item, dict)
    }
    for entry in entries:
        by_name[str(entry.get("name") or entry.get("module"))] = entry
    payload = {
        "schema_version": "global_defines_manifest_v1",
        "global_define_files": list(by_name.values()),
    }
    from ..utils.artifact_store import atomic_write_json
    atomic_write_json(manifest_path, ArtifactLayout(workspace_root).paths(payload))
    return payload


def read_global_defines_manifest(workspace_root: Path) -> dict[str, Any]:
    path = artifact_path(workspace_root, "global_defines_manifest.json")
    if not path.exists():
        return {"schema_version": "global_defines_manifest_v1", "global_define_files": []}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"schema_version": "global_defines_manifest_v1", "global_define_files": []}
    if not isinstance(obj, dict):
        return {"schema_version": "global_defines_manifest_v1", "global_define_files": []}
    obj.setdefault("schema_version", "global_defines_manifest_v1")
    obj.setdefault("global_define_files", [])
    return ArtifactLayout(workspace_root).paths(obj, absolute=True)


def build_global_defines_context(workspace_root: Path, max_chars: int = 60000) -> str:
    """Build authoritative prompt context from every manifested define file."""

    manifest = read_global_defines_manifest(workspace_root)
    entries = [
        item
        for item in manifest.get("global_define_files", []) or []
        if isinstance(item, dict)
    ]
    if not entries:
        return ""

    chunks = [
        "Official global macro definitions are available for this task.",
        "Use these files as the authoritative compile-time context.",
        "Do not redefine these macros; the merge stage owns final include placement.",
        "",
    ]
    for entry in entries:
        name = str(entry.get("name") or entry.get("module") or "global_defines")
        path = Path(str(entry.get("workspace_path") or ""))
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n").strip()
        if not content:
            continue
        chunks.extend(
            [
                f"## {name}",
                f"- source: {entry.get('source', '')}",
                f"- workspace_path: {path}",
                f"- must_include: {bool(entry.get('must_include'))}",
                "```verilog",
                content,
                "```",
                "",
            ]
        )

    text = "\n".join(chunks).strip()
    if not text or text.count("```verilog") == 0:
        return ""
    if len(text) > max_chars:
        return text[:max_chars].rstrip() + "\n...<global defines truncated>..."
    return text


def build_stage5_global_defines_summary(
    workspace_root: Path,
    relevant_texts: Iterable[str],
    max_chars: int = 6000,
) -> str:
    """Build a bounded, subtask-specific view of effective global macros.

    Stage 5 only needs the macro values referenced by the current fragment and
    their value dependencies.  Stage 6 deliberately continues to use
    :func:`build_global_defines_context`, which exposes the complete canonical
    files for include placement and linting.
    """

    if max_chars <= 0:
        return ""
    manifest = read_global_defines_manifest(workspace_root)
    entries = [
        item
        for item in manifest.get("global_define_files", []) or []
        if isinstance(item, dict) and Path(str(item.get("workspace_path") or "")).is_file()
    ]
    if not entries:
        return ""

    roots = [item for item in entries if item.get("must_include")]
    if not roots:
        roots = entries
    include_dirs = sorted(
        {Path(str(item["workspace_path"])).resolve().parent for item in entries},
        key=str,
    )
    known: dict[str, dict[str, Any]] = {}
    for entry in entries:
        _scan_known_macros(Path(str(entry["workspace_path"])).resolve(), known)

    effective: dict[str, dict[str, Any]] = {}
    for entry in roots:
        _evaluate_define_file(
            Path(str(entry["workspace_path"])).resolve(),
            include_dirs=include_dirs,
            macros=effective,
            include_stack=[],
        )

    corpus = "\n".join(str(item or "") for item in relevant_texts)
    direct = {
        match.group(1)
        for match in _MACRO_REFERENCE_RE.finditer(corpus)
        if match.group(1) in known
    }
    dependencies: set[str] = set()
    pending = list(sorted(direct))
    while pending:
        name = pending.pop()
        record = effective.get(name)
        if not record:
            continue
        for match in _MACRO_REFERENCE_RE.finditer(str(record.get("value") or "")):
            dependency = match.group(1)
            if dependency in known and dependency not in direct and dependency not in dependencies:
                dependencies.add(dependency)
                pending.append(dependency)

    header = [
        "Official effective global macro summary for this Stage 5 subtask.",
        "This is a bounded generation aid, not a replacement for the canonical files.",
        "Do not define, undefine, or create fallback values for these macros.",
        "Stage 6 owns the canonical includes and lint configuration.",
        "",
    ]
    records: list[tuple[str, str]] = []
    for name in sorted(direct):
        records.append((name, _format_macro_summary_line(name, effective, known, "direct")))
    for name in sorted(dependencies):
        records.append((name, _format_macro_summary_line(name, effective, known, "dependency")))

    # Preserve the historical behavior for genuinely small, generic define
    # files whose prose asks for "global constants" without naming them.
    if not direct:
        fallback = [
            (name, _format_macro_summary_line(name, effective, known, "small-manifest fallback"))
            for name in sorted(effective)
        ]
        fallback_text = "\n".join(line for _, line in fallback)
        if len("\n".join(header)) + len(fallback_text) + 1 <= max_chars:
            records = fallback

    selected: list[str] = []
    omitted = 0
    base = "\n".join(header).rstrip()
    for _, line in records:
        candidate = f"{base}\n" + ("\n".join(selected) + "\n" if selected else "") + line
        if len(candidate) <= max_chars:
            selected.append(line)
        else:
            omitted += 1

    result = base
    if selected:
        result += "\n" + "\n".join(selected)
    elif direct:
        result += "\nRelevant macro entries exceeded the configured summary budget."
    else:
        result += "\nNo explicitly referenced official macros were found for this subtask."
    if omitted:
        suffix = f"\n... {omitted} complete macro entr{'y' if omitted == 1 else 'ies'} omitted by the {max_chars}-character limit."
        if len(result) + len(suffix) <= max_chars:
            result += suffix
    return result[:max_chars]


def _scan_known_macros(path: Path, known: dict[str, dict[str, Any]]) -> None:
    for line_number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        match = _DIRECTIVE_RE.match(line)
        disabled = False
        if not match:
            commented = re.match(r"^\s*//\s*(`.*)$", line)
            match = _DIRECTIVE_RE.match(commented.group(1)) if commented else None
            disabled = match is not None
        if not match:
            continue
        directive = match.group("directive").lower()
        if directive == "define":
            parsed = _parse_macro_body(match.group("body"))
            if parsed is None:
                continue
            name, value = parsed
        elif directive in {"undef", "ifdef", "ifndef", "elsif"}:
            name = _first_macro_name(match.group("body"))
            value = ""
            if not name:
                continue
        else:
            continue
        known.setdefault(
            name,
            {
                "value": value,
                "source": str(path),
                "line": line_number,
                "disabled_declaration": disabled,
            },
        )


def _evaluate_define_file(
    path: Path,
    *,
    include_dirs: list[Path],
    macros: dict[str, dict[str, Any]],
    include_stack: list[Path],
) -> None:
    path = path.resolve()
    if path in include_stack:
        chain = " -> ".join(str(item) for item in [*include_stack, path])
        raise ValueError(f"Recursive global define include: {chain}")
    include_stack.append(path)
    conditional_stack: list[dict[str, bool]] = []
    active = True
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for line_number, line in enumerate(lines, 1):
            match = _DIRECTIVE_RE.match(line)
            if not match:
                continue
            directive = match.group("directive").lower()
            body = match.group("body").strip()
            if directive in {"ifdef", "ifndef"}:
                name = _first_macro_name(body)
                condition = bool(name and name in macros)
                if directive == "ifndef":
                    condition = not condition
                frame = {
                    "parent_active": active,
                    "branch_taken": condition,
                    "active": active and condition,
                }
                conditional_stack.append(frame)
                active = frame["active"]
                continue
            if directive == "elsif":
                if not conditional_stack:
                    raise ValueError(f"Unexpected `elsif in {path}:{line_number}")
                frame = conditional_stack[-1]
                condition = bool((_first_macro_name(body) or "") in macros)
                take = frame["parent_active"] and not frame["branch_taken"] and condition
                frame["active"] = take
                frame["branch_taken"] = frame["branch_taken"] or condition
                active = take
                continue
            if directive == "else":
                if not conditional_stack:
                    raise ValueError(f"Unexpected `else in {path}:{line_number}")
                frame = conditional_stack[-1]
                take = frame["parent_active"] and not frame["branch_taken"]
                frame["active"] = take
                frame["branch_taken"] = True
                active = take
                continue
            if directive == "endif":
                if not conditional_stack:
                    raise ValueError(f"Unexpected `endif in {path}:{line_number}")
                conditional_stack.pop()
                active = conditional_stack[-1]["active"] if conditional_stack else True
                continue
            if not active:
                continue
            if directive == "include":
                include_match = re.match(r'["<]([^">]+)[">]', body)
                if not include_match:
                    continue
                include_name = include_match.group(1)
                candidates = [path.parent / include_name, *[directory / include_name for directory in include_dirs]]
                include_path = next((candidate.resolve() for candidate in candidates if candidate.is_file()), None)
                if include_path is None:
                    raise FileNotFoundError(f"Global define include not found from {path}: {include_name}")
                _evaluate_define_file(
                    include_path,
                    include_dirs=include_dirs,
                    macros=macros,
                    include_stack=include_stack,
                )
                continue
            if directive == "define":
                parsed = _parse_macro_body(body)
                if parsed is None:
                    continue
                name, value = parsed
                macros[name] = {
                    "value": value,
                    "source": str(path),
                    "line": line_number,
                }
                continue
            if directive == "undef":
                name = _first_macro_name(body)
                if name:
                    macros.pop(name, None)
        if conditional_stack:
            raise ValueError(f"Unterminated preprocessor conditional in {path}")
    finally:
        include_stack.pop()


def _parse_macro_body(body: str) -> tuple[str, str] | None:
    match = _MACRO_NAME_RE.match(body.lstrip())
    if not match:
        return None
    name = match.group(0)
    remainder = body.lstrip()[match.end():]
    # Keep function-like arguments with the value for faithful reporting while
    # indexing the macro by its Verilog preprocessor name.
    value = re.split(r"//", remainder, maxsplit=1)[0].strip()
    return name, value


def _first_macro_name(text: str) -> str | None:
    match = _MACRO_NAME_RE.search(text)
    return match.group(0) if match else None


def _format_macro_summary_line(
    name: str,
    effective: dict[str, dict[str, Any]],
    known: dict[str, dict[str, Any]],
    relevance: str,
) -> str:
    record = effective.get(name)
    declaration = record or known.get(name) or {}
    source = Path(str(declaration.get("source") or "<unknown>"))
    location = f"{source.name}:{declaration.get('line') or '?'}"
    if record is None:
        return f"- undefined `{name}` (known official macro; source {location}; relevance: {relevance})"
    value = str(record.get("value") or "")
    directive = f"`define {name}" + (f" {value}" if value else "")
    return f"- defined: {directive} (source {location}; relevance: {relevance})"
