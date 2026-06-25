from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from ..schemas import PlannerTaskInput


DEFINE_NOTE_MARKERS = (
    "not a synthesizable module",
    "provides constants",
    "global parameter",
    "global defines",
    "preprocessor define",
)


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
    merged_dir = workspace_root / "merged"
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


def write_global_defines_manifest(
    *,
    workspace_root: Path,
    output_root: Path | None,
    entries: list[dict[str, Any]],
) -> dict[str, Any]:
    workspace_root.mkdir(parents=True, exist_ok=True)
    manifest_path = workspace_root / "global_defines_manifest.json"
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
    manifest_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if output_root is not None:
        out_path = output_root / "global_defines_manifest.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def read_global_defines_manifest(workspace_root: Path) -> dict[str, Any]:
    path = workspace_root / "global_defines_manifest.json"
    if not path.exists():
        legacy_path = workspace_root / "merged" / "global_defines_manifest.json"
        if legacy_path.exists():
            path = legacy_path
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
    return obj
