"""Stable generation inputs and verifiable evidence for legacy checkpoints."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import re

from pydantic import BaseModel
from zerorepo.rtl_impl.port_contracts import ansi_module_ports, normalize_width

from .local_repair import fingerprint


SOURCE_VERSION = "stage5_source_v2"


def json_value(value):
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return copy.deepcopy(value)


def stable_planning_context(context):
    value = copy.deepcopy(context or {})
    module = value.get("module", {})
    for key in ("actual_path", "implementation_status"):
        module.pop(key, None)
    value["code_interface"] = []
    children = []
    for child in value.get("child_code_interfaces") or []:
        ports = [{"name": port.get("name"), "direction": port.get("direction"),
                  "width": normalize_width(str(port.get("width") or "1"))}
                 for port in child.get("ports") or []]
        children.append({"module": child.get("module"), "ports": sorted(ports, key=lambda p: p.get("name", ""))})
    value["child_code_interfaces"] = sorted(children, key=lambda c: c.get("module") or "")
    return value


def stage5_prompt_context(context):
    """Keep unique KG relationships; authoritative spec bodies live in sidecars.

    Do this before the renderer budgets interfaces, so redundant provenance and
    relevance prose do not displace child ports. The original KG stays intact
    for legacy evidence; v2 fingerprints use complete structured sources.
    """
    value = stable_planning_context(context)
    for item in value.get("specs") or []:
        relation = item.get("relation") or {}
        item["relation"] = {"local_ref": relation["local_ref"]} if "local_ref" in relation else {}
        item["fragment"] = {}
    return value


def compact_stage5_interfaces(prompt_json, child_interfaces):
    """Encode complete authoritative ports compactly, without dropping names."""
    if not prompt_json:
        return ""
    try:
        payload = json.loads(prompt_json)
    except (TypeError, ValueError):
        return prompt_json  # Preserve injected custom renderers' existing format.
    if not isinstance(payload, dict) or payload.get("schema_version") != "stage5_planning_context_v1":
        return prompt_json
    payload["schema_version"] = "stage5_planning_context_v2"
    payload["port_fields"] = ["name", "direction", "width"]
    payload["child_code_interfaces"] = [{"module": child["module"],
        "ports": [[p["name"], p["direction"], p["width"]] for p in child["ports"]]}
        for child in child_interfaces]
    omitted = dict(payload.get("omitted_count") or {})
    for key in ("child_ports", "child_interfaces"):
        omitted.pop(key, None)  # These are restored from complete source contracts.
    if omitted:
        payload["omitted_count"] = omitted
    else:
        payload.pop("omitted_count", None)
        payload.pop("truncated", None)
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def source_snapshot(*, legacy, responsibility, child_interfaces, skeleton_document=None):
    return {"fingerprint_version": SOURCE_VERSION,
            **{key: json_value(value) for key, value in legacy.items() if key != "planning_kg"},
            "responsibility": json_value(responsibility), "child_interfaces": json_value(child_interfaces),
            **({"skeleton_document": fingerprint(skeleton_document)} if skeleton_document is not None else {})}


def changed_components(before, after):
    return sorted(key for key in set(before or {}) | set(after) if (before or {}).get(key) != after.get(key))


class Stage5LogEvidence:
    """Read-only source evidence; never treats a partial response as an artifact."""

    def __init__(self, path):
        self.path = Path(path)
        self.records = {}
        self._child_evidence = {}
        if not self.path.is_file():
            return
        text = self.path.read_text(encoding="utf-8")
        pattern = r"========== stage5_codegen INPUT ==========(.*?)========== END stage5_codegen INPUT =========="
        for match in re.finditer(pattern, text, re.S):
            fields = {m.group(1): m.group(2).strip() for m in re.finditer(
                r"^\[([A-Z_]+)\]\n(.*?)(?=^\[[A-Z_]+\]\n|\Z)", match.group(1), re.M | re.S)}
            try:
                task = json.loads(fields["CURRENT_SUBTASK"])
                metadata = json.loads(fields["STAGE_CONTEXT"])
            except (ValueError, KeyError):
                continue
            self.records.setdefault((metadata.get("module"), task.get("id")), []).append(fields)

    def proves_legacy(self, entry, legacy, responsibility, child_interfaces):
        # Recompute the *old* hash with today's exact authoritative inputs.
        # Historical KG is usable only if its planning facts still match.
        contexts = [legacy.get("planning_kg", "")]
        contexts.extend(fields.get("PLANNING_KG_CONTEXT", "") for fields in
                        self.records.get((legacy["module"], entry.get("subtask_id")), []))
        for context in contexts:
            if context == "None":
                context = ""
            try:
                kg = json.loads(context) if context else {}
            except ValueError:
                continue
            historical_module = kg.get("module") or {}
            if responsibility.get("role") and historical_module.get("role") != responsibility["role"]:
                continue
            historical_children = stable_planning_context(kg).get("child_code_interfaces", [])
            if historical_children != child_interfaces:
                # Old prompts could truncate dependency ports. A historical
                # RTL tree is usable only when the old parent Stage6 hash binds
                # it to this exact source, and its full ports match today.
                if self._verified_stage6_children(legacy["module"]) != child_interfaces:
                    continue
            if fingerprint({**legacy, "planning_kg": context}) == entry.get("input_fingerprint"):
                return {"kind": "legacy_hash_verified", "log": str(self.path),
                        "legacy_input_fingerprint": entry["input_fingerprint"]}
        return None

    def proves_full_skeleton(self, module):
        from ..schemas import Stage4SpecBlocksArtifact
        root = self.path.parent
        output = root / "module_planner" / "outputs"
        workspace = root / "workspace"
        try:
            specs = Stage4SpecBlocksArtifact.model_validate_json((output / "spec_blocks.json").read_text())
            spec = next(s for s in specs.modules if s.module == module)
            repo = json.loads((output / "repo_skeleton.json").read_text())
            children = next(s for s in repo["modules"] if s["module"] == module).get("children", [])
            stage3 = json.loads((output / "module_skeletons.json").read_text())
            doc = next(s for s in stage3["module_records"] if s["module"] == module)["doc_file"]
            key = fingerprint({"policy": "local_repair_v1", "module": module,
                "fragments": (workspace / "fragments" / f"{module}_fragments.v").read_text(),
                "skeleton": (output / doc).read_text(), "spec": spec,
                "children": {child: (workspace / "merged" / f"{child}.v").read_text() for child in children}})
            stamp = json.loads((workspace / "merged" / f"{module}.inputs.json").read_text())
            return key == stamp["input_fingerprint"] or self._verified_stage6_children(module) is not None
        except (OSError, ValueError, KeyError, TypeError, StopIteration):
            return False

    def _verified_stage6_children(self, module):
        if module in self._child_evidence:
            return self._child_evidence[module]
        self._child_evidence[module] = None
        from ..schemas import Stage4SpecBlocksArtifact
        root = self.path.parent
        workspace = root / "workspace"
        output = root / "module_planner" / "outputs"
        try:
            specs = Stage4SpecBlocksArtifact.model_validate_json((output / "spec_blocks.json").read_text())
            spec = next(s for s in specs.modules if s.module == module)
            repo = json.loads((output / "repo_skeleton.json").read_text())
            children = next(s for s in repo["modules"] if s["module"] == module).get("children", [])
            stage3 = json.loads((output / "module_skeletons.json").read_text())
            doc = next(s for s in stage3["module_records"] if s["module"] == module)["doc_file"]
            skeleton = (output / doc).read_text()
            fragments = (workspace / "fragments" / f"{module}_fragments.v").read_text()
            stamp = json.loads((workspace / "merged" / f"{module}.inputs.json").read_text())
            allowed_keys = {stamp["input_fingerprint"]}
            for archived in (output / ".repair_cache" / "stage6_history").glob(f"{module}_*.json"):
                try:
                    allowed_keys.add(json.loads(archived.read_text())["input_fingerprint"])
                except (OSError, ValueError, KeyError, TypeError):
                    continue
            roots = list((workspace / "debug_system").glob("*/codex_private"))
            roots.extend((workspace / "debug_system").glob("*/history/*/codex_private"))
            for private in roots:
                try:
                    state = json.loads((private / "session_state.json").read_text())
                    baseline = private / "accepted_baseline" / "merged"
                    texts = {child: (baseline / f"{child}.v").read_text() for child in children}
                    import hashlib
                    if any(hashlib.sha256((baseline / f"{child}.v").read_bytes()).hexdigest() != state["accepted_manifest"].get(f"{child}.v") for child in children):
                        continue
                except (OSError, ValueError, KeyError, TypeError):
                    continue
                key = fingerprint({"policy": "local_repair_v1", "module": module, "fragments": fragments,
                                   "skeleton": skeleton, "spec": spec, "children": texts})
                if key not in allowed_keys:
                    continue
                interfaces = [{"module": child, "ports": sorted([
                    {"name": p.name, "direction": p.direction, "width": p.width} for p in ansi_module_ports(texts[child])],
                    key=lambda p: p["name"])} for child in sorted(children)]
                self._child_evidence[module] = interfaces
                return interfaces
        except (OSError, ValueError, KeyError, TypeError, StopIteration):
            return None
        return None
