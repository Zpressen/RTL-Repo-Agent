"""Bind accepted system-debug RTL to immutable generation inputs and origin."""
from zerorepo.rtl_impl.artifact_layout import ArtifactLayout, artifact_path, artifact_dir
from pathlib import Path
import json

from .artifact_store import atomic_write_json, atomic_write_text
from .local_repair import fingerprint
from .stage5_sources import json_value
from ..agents.global_defines import read_global_defines_manifest
from zerorepo.rtl_impl.codex_debug.history import tree_manifest


def generation_sources(output, workspace, inputs, task):
    output, workspace = Path(output), Path(workspace)
    names = inputs["spec_blocks"].module_order
    def text(path):
        return Path(path).read_text() if Path(path).is_file() else None
    def resolve(path):
        return Path(path) if Path(path).is_absolute() else output / path
    stage3 = inputs.get("stage3")
    stage4 = inputs.get("stage4")
    snapshots = {}
    for module in names:
        marker = json.loads(ArtifactLayout(workspace).stage5_checkpoint(module).read_text())
        snapshots[module] = [{"source": e.get("source_fingerprint", e.get("input_fingerprint")),
                              "artifact": e["artifact_fingerprint"]} for e in marker["subtasks"]]
    return {"version": "accepted_debug_generation_v1", "task_id": task.task_id,
        "source_files": {str(p): fingerprint(Path(p).read_text()) for p in task.spec_md_files},
        "stage1": json.loads(text(artifact_path(output, "contracts.json"))) if text(artifact_path(output, "contracts.json")) else None,
        "stage2": json_value(inputs.get("stage2")),
        "specs": json_value(inputs["spec_blocks"]),
        "skeletons": {r.module: text(resolve(r.doc_file)) for r in getattr(stage3, "module_records", [])},
        "plans": {r.module: json.loads(resolve(r.plan_file).read_text()) for r in getattr(stage4, "module_plan_files", [])},
        "fragments": {n: text(artifact_dir(workspace, "fragments") / f"{n}_fragments.v") for n in names},
        "contracts": {n: json.loads(ArtifactLayout(workspace).stage5_contracts(n).read_text()) for n in names},
        "checkpoints": snapshots, "defines": read_global_defines_manifest(workspace)}


def save_origin(workspace, sources, texts):
    workspace = Path(workspace).resolve()
    key = fingerprint({"sources": sources, "rtl": texts})
    directory = artifact_dir(workspace, ".debug_generations") / key
    marker = directory / "origin.json"
    if not marker.exists():
        for name, content in texts.items():
            atomic_write_text(directory / "merged" / name, content)
        atomic_write_json(marker, {"source_fingerprint": fingerprint(sources), "sources": sources,
                                   "manifest": tree_manifest(directory / "merged")})
    saved = json.loads(marker.read_text())
    if saved["source_fingerprint"] != fingerprint(sources) or saved["manifest"] != tree_manifest(directory / "merged"):
        raise ValueError("Immutable debug generation origin is corrupt")
    return directory / "merged"


def validate_origin(workspace, binding, sources):
    workspace = Path(workspace).resolve()
    origin = (workspace / binding["origin_path"]).resolve()
    if not origin.is_relative_to(artifact_dir(workspace, ".debug_generations")):
        raise ValueError("Debug origin is outside immutable generation storage")
    saved = json.loads((origin.parent / "origin.json").read_text())
    if saved["source_fingerprint"] != fingerprint(saved["sources"]) or saved["source_fingerprint"] != fingerprint(sources):
        raise ValueError("Debug generation sources changed")
    if saved["manifest"] != tree_manifest(origin):
        raise ValueError("Debug generation origin checksum mismatch")
    return origin
