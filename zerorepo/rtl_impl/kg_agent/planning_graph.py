from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional
from zerorepo.rtl_impl.process_observer import observed


PLANNING_SCHEMA_VERSION = "planning_kg_projection_v2_harness"
PLANNING_RELATIONSHIPS = frozenset({"SPECIFIES", "HAS_SKELETON", "HAS_PLAN"})


def _payload(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    raise TypeError(f"Unsupported planning artifact type: {type(value).__name__}")


def _fingerprint(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _module_uid(repo_uid: str, module_name: str) -> str:
    name = str(module_name).strip()
    if not name:
        raise ValueError("module name must not be empty")
    return f"{repo_uid}:module:{name}"


def _edge(rel: str, source: str, target: str, **props: Any) -> Dict[str, Any]:
    if rel not in PLANNING_RELATIONSHIPS:
        raise ValueError(f"Unsupported planning relationship: {rel}")
    uid = f"{source}:{rel}:{target}"
    return {"uid": uid, "eid": uid, "type": rel, "source": source, "target": target, **props}


class PlanningGraphWriter:
    """Maintain the reconstructable planning projection and mirror it to Neo4j."""

    def __init__(self, kg_service: Any, output_root: str | Path, logger: Any = None):
        self.kg_service = kg_service
        self.output_root = Path(output_root)
        self.logger = logger or logging.getLogger(__name__)
        self.projection_path = Path(kg_service.planning_projection_path)
        self._synced_fingerprint: Optional[str] = None

    def begin_run(self) -> None:
        # An on-disk projection cannot prove the database still contains it.
        # Each run resynchronizes once, including after a database reset.
        self._synced_fingerprint = None

    @property
    def enabled(self) -> bool:
        return bool(self.kg_service and self.kg_service.is_enabled())

    def upsert_module_anchors(self, task: Any, repo_skeleton: Any, *, sync: bool = True) -> None:
        if not self.enabled:
            return
        task_data = _payload(task)
        data = _payload(repo_skeleton)
        modules = list(data.get("modules") or [])
        names = [str(item.get("module") or "").strip() for item in modules]
        duplicates = sorted({name for name in names if name and names.count(name) > 1})
        if duplicates:
            raise ValueError(f"Duplicate Module definitions in planning input: {duplicates}")
        rank = {name: index for index, name in enumerate(data.get("module_order") or [])}
        stage2_fp = str(data.get("input_fingerprint") or _fingerprint(data))
        projection = self._load()
        previous_stage2 = {
            str(item.get("stage2_fingerprint") or "")
            for item in projection["nodes"]
            if item.get("kind") == "Module" and item.get("stage2_fingerprint")
        }
        if previous_stage2 and previous_stage2 != {stage2_fp}:
            projection["nodes"] = [
                item
                for item in projection["nodes"]
                if item.get("kind") not in {"SpecFragment", "ModuleSkeleton", "ModulePlan"}
            ]
            projection["edges"] = [
                item for item in projection["edges"] if item.get("type") not in PLANNING_RELATIONSHIPS
            ]
        current_names = {name for name in names if name}
        projection["nodes"] = [
            item
            for item in projection["nodes"]
            if item.get("kind") != "Module" or str(item.get("name") or "") in current_names
        ]
        for item in modules:
            name = str(item.get("module") or "").strip()
            if not name:
                continue
            uid = _module_uid(self.kg_service.repo_uid, name)
            previous = self._node_map(projection).get(uid, {})
            node = {
                **previous,
                "uid": uid,
                "repo_uid": self.kg_service.repo_uid,
                "kind": "Module",
                "name": name,
                "expected_path": str(item.get("file_path") or ""),
                "role": str(item.get("role") or ""),
                "module_kind": str(item.get("kind") or ""),
                "is_top": name == str(data.get("top_module") or ""),
                "generation_rank": int(rank.get(name, len(rank))),
                "planned_parents": list(item.get("parents") or []),
                "planned_children": list(item.get("children") or []),
                "stage2_fingerprint": stage2_fp,
                "planning_task_id": str(task_data.get("task_id") or data.get("task_id") or ""),
                "implementation_status": str(previous.get("implementation_status") or "planned"),
            }
            self._replace_node(projection, node)
        self._commit(projection, sync=sync)

    def upsert_spec_fragments(
        self,
        task: Any,
        module: str,
        spec_context: Any,
        *,
        artifact_path: str = "",
        input_fingerprint: str = "",
        sync: bool = True,
    ) -> None:
        if not self.enabled:
            return
        task_data = _payload(task)
        data = _payload(spec_context)
        target_uid = _module_uid(self.kg_service.repo_uid, module)
        projection = self._load()
        projection["edges"] = [
            item
            for item in projection["edges"]
            if not (item.get("type") == "SPECIFIES" and item.get("target") == target_uid)
        ]
        for block in data.get("blocks") or []:
            text = str(block.get("text") or "")
            source_file = str(block.get("source_file") or "")
            source_chunks = [str(item) for item in block.get("source_chunk_ids") or []]
            text_hash = _content_hash(text)
            identity = _fingerprint(
                {"source_file": source_file, "source_chunk_ids": source_chunks, "content_hash": text_hash}
            )
            fragment_uid = f"{self.kg_service.repo_uid}:spec_fragment:{identity}"
            self._replace_node(
                projection,
                {
                    "uid": fragment_uid,
                    "repo_uid": self.kg_service.repo_uid,
                    "kind": "SpecFragment",
                    "source_file": source_file,
                    "source_chunk_ids": source_chunks,
                    "content_hash": text_hash,
                    "text_preview": text[:1000],
                    "artifact_path": artifact_path,
                    "confidence": str(block.get("confidence") or ""),
                    "planning_task_id": str(task_data.get("task_id") or data.get("task_id") or ""),
                },
            )
            projection["edges"].append(
                _edge(
                    "SPECIFIES",
                    fragment_uid,
                    target_uid,
                    local_ref=str(block.get("block_id") or ""),
                    confidence=str(block.get("confidence") or ""),
                    relevance_reason=list(block.get("relevance_reason") or []),
                    input_fingerprint=input_fingerprint,
                    artifact_path=artifact_path,
                )
            )
        referenced = {
            str(item.get("source"))
            for item in projection["edges"]
            if item.get("type") == "SPECIFIES"
        }
        projection["nodes"] = [
            item
            for item in projection["nodes"]
            if item.get("kind") != "SpecFragment" or item.get("uid") in referenced
        ]
        self._commit(projection, sync=sync)

    def upsert_module_skeleton(
        self,
        task: Any,
        module: str,
        skeleton_export: Any,
        *,
        artifact_path: str = "",
        input_fingerprint: str = "",
        spec_context_fingerprint: str = "",
        sync: bool = True,
    ) -> None:
        if not self.enabled:
            return
        task_data = _payload(task)
        data = _payload(skeleton_export)
        module_uid = _module_uid(self.kg_service.repo_uid, module)
        uid = f"{self.kg_service.repo_uid}:module_skeleton:{module}"
        content_hash = _fingerprint(data)
        blocks = list(data.get("structural_blocks") or [])
        behavior = data.get("module_behavior") or {}
        projection = self._load()
        self._replace_node(
            projection,
            {
                "uid": uid,
                "repo_uid": self.kg_service.repo_uid,
                "kind": "ModuleSkeleton",
                "name": module,
                "module": module,
                "schema_version": str(data.get("schema_version") or ""),
                "input_fingerprint": input_fingerprint,
                "content_hash": content_hash,
                "artifact_path": artifact_path,
                "block_ids": [str(item.get("block_id") or "") for item in blocks],
                "block_kinds": [str(item.get("block_kind") or "") for item in blocks],
                "control_style": str(behavior.get("control_style") or ""),
                "spec_context_fingerprint": spec_context_fingerprint,
                "planning_task_id": str(task_data.get("task_id") or ""),
            },
        )
        self._replace_edge(projection, _edge("HAS_SKELETON", module_uid, uid))
        self._commit(projection, sync=sync)

    def upsert_module_plan(
        self,
        task: Any,
        module: str,
        module_plan: Any,
        *,
        artifact_path: str = "",
        input_fingerprint: str = "",
        sync: bool = True,
    ) -> None:
        if not self.enabled:
            return
        task_data = _payload(task)
        data = _payload(module_plan)
        module_uid = _module_uid(self.kg_service.repo_uid, module)
        uid = f"{self.kg_service.repo_uid}:module_plan:{module}"
        projection = self._load()
        skeleton = self._node_map(projection).get(
            f"{self.kg_service.repo_uid}:module_skeleton:{module}", {}
        )
        subtasks = list(data.get("subtasks") or [])
        self._replace_node(
            projection,
            {
                "uid": uid,
                "repo_uid": self.kg_service.repo_uid,
                "kind": "ModulePlan",
                "name": module,
                "module": module,
                "schema_version": str(data.get("schema_version") or ""),
                "input_fingerprint": input_fingerprint,
                "content_hash": _fingerprint(data),
                "artifact_path": artifact_path,
                "skeleton_content_hash": str(skeleton.get("content_hash") or ""),
                "subtask_ids": [str(item.get("id") or "") for item in subtasks],
                "spec_refs": sorted({str(ref) for item in subtasks for ref in item.get("spec_refs") or []}),
                "timing_obligation_ids": sorted(
                    {str(ref) for item in subtasks for ref in item.get("timing_obligation_ids") or []}
                ),
                "planning_task_id": str(task_data.get("task_id") or ""),
            },
        )
        self._replace_edge(projection, _edge("HAS_PLAN", module_uid, uid))
        self._commit(projection, sync=sync)

    def ensure_projection(
        self,
        task: Any,
        repo_skeleton: Any,
        module_skeletons: Any = None,
        module_plans: Any = None,
    ) -> None:
        """Rebuild from sidecars, persisting locally and syncing one snapshot."""
        if not self.enabled:
            return
        self.upsert_module_anchors(task, repo_skeleton, sync=False)
        skeleton_manifest = _payload(module_skeletons)
        for record in skeleton_manifest.get("module_records") or []:
            module = str(record.get("module") or "")
            spec_rel = str(record.get("spec_context_file") or "")
            export_rel = str(record.get("export_file") or "")
            if spec_rel and (self.output_root / spec_rel).exists():
                self.upsert_spec_fragments(
                    task,
                    module,
                    self._read_json(self.output_root / spec_rel),
                    artifact_path=spec_rel,
                    input_fingerprint=str(skeleton_manifest.get("input_fingerprint") or ""),
                    sync=False,
                )
            if export_rel and (self.output_root / export_rel).exists():
                self.upsert_module_skeleton(
                    task,
                    module,
                    self._read_json(self.output_root / export_rel),
                    artifact_path=export_rel,
                    input_fingerprint=str(skeleton_manifest.get("input_fingerprint") or ""),
                    spec_context_fingerprint=self._module_spec_fingerprint(module),
                    sync=False,
                )
        plan_manifest = _payload(module_plans)
        for record in plan_manifest.get("module_plan_files") or []:
            module = str(record.get("module") or "")
            rel = str(record.get("plan_file") or "")
            if rel and (self.output_root / rel).exists():
                self.upsert_module_plan(
                    task,
                    module,
                    self._read_json(self.output_root / rel),
                    artifact_path=rel,
                    input_fingerprint=str(plan_manifest.get("input_fingerprint") or ""),
                    sync=False,
                )
        self._sync(self._load())

    def _module_spec_fingerprint(self, module: str) -> str:
        target = _module_uid(self.kg_service.repo_uid, module)
        projection = self._load()
        rows = sorted(
            (
                str(edge.get("source")),
                str(edge.get("local_ref") or ""),
                str(self._node_map(projection).get(str(edge.get("source")), {}).get("content_hash") or ""),
            )
            for edge in projection["edges"]
            if edge.get("type") == "SPECIFIES" and edge.get("target") == target
        )
        return _fingerprint(rows)

    def _load(self) -> Dict[str, Any]:
        if self.projection_path.exists():
            data = self._read_json(self.projection_path)
            if data.get("repo_uid") == self.kg_service.repo_uid and data.get("schema_version") == PLANNING_SCHEMA_VERSION:
                data.setdefault("nodes", [])
                data.setdefault("edges", [])
                return data
        return {
            "schema_version": PLANNING_SCHEMA_VERSION,
            "repo_uid": self.kg_service.repo_uid,
            "nodes": [],
            "edges": [],
        }

    @staticmethod
    def _read_json(path: Path) -> Dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _node_map(projection: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
        return {str(item.get("uid")): item for item in projection.get("nodes", []) if item.get("uid")}

    @staticmethod
    def _replace_node(projection: Dict[str, Any], node: Dict[str, Any]) -> None:
        projection["nodes"] = [item for item in projection["nodes"] if item.get("uid") != node["uid"]]
        projection["nodes"].append(node)

    @staticmethod
    def _replace_edge(projection: Dict[str, Any], edge: Dict[str, Any]) -> None:
        projection["edges"] = [item for item in projection["edges"] if item.get("uid") != edge["uid"]]
        projection["edges"].append(edge)

    def _commit(self, projection: Dict[str, Any], *, sync: bool = True) -> None:
        projection["schema_version"] = PLANNING_SCHEMA_VERSION
        projection["repo_uid"] = self.kg_service.repo_uid
        projection["nodes"] = sorted(projection["nodes"], key=lambda item: str(item.get("uid") or ""))
        projection["edges"] = sorted(projection["edges"], key=lambda item: str(item.get("uid") or ""))
        previous = self._read_json(self.projection_path) if self.projection_path.exists() else None
        if previous != projection:
            from zerorepo.rtl_impl.module_planner.utils.artifact_store import atomic_write_json
            atomic_write_json(self.projection_path, projection)
        if sync:
            self._sync(projection)

    def _sync(self, projection: Dict[str, Any]) -> None:
        content_fingerprint = _fingerprint(projection)
        if content_fingerprint == self._synced_fingerprint:
            self.logger.debug("[planning_kg] Skipped unchanged projection already synced this run")
            return
        # A failed upsert can partially alter Neo4j. Invalidate the previous
        # acknowledgement too, so even a local rollback must synchronize again.
        self._synced_fingerprint = None
        try:
            self.kg_service.upsert_planning_projection(projection["nodes"], projection["edges"])
            self._synced_fingerprint = content_fingerprint
            self.logger.info("[planning_kg] Synced projection: %d nodes, %d edges",
                             len(projection["nodes"]), len(projection["edges"]))
        except Exception as exc:
            if str(getattr(self.kg_service, "mode", "required")) == "required":
                raise
            self.logger.warning(
                "[planning_kg] Neo4j projection update failed; sidecars remain authoritative: %s",
                exc,
            )


class PlanningContextRetriever:
    """Read the Module-centred planning view and enforce current-artifact bindings."""

    def __init__(self, kg_service: Any, output_root: str | Path | None = None, logger: Any = None):
        self.kg_service = kg_service
        self.output_root = Path(output_root) if output_root is not None else None
        self.logger = logger or logging.getLogger(__name__)

    @observed('tool', '查询模块规划图谱及材料绑定', tool='query_rtl_kg',
              summarize=lambda r: f'返回{len(r.get("specs") or [])}个规格片段、{int(bool(r.get("skeleton")))}份骨架、{int(bool(r.get("plan")))}份计划；已检查请求的材料绑定。')
    def get_module_context(
        self,
        module_name: str,
        require_spec: bool = False,
        require_skeleton: bool = False,
        require_plan: bool = False,
        include_code_interface: bool = False,
        expected_fingerprints: Optional[Mapping[str, str]] = None,
    ) -> Dict[str, Any]:
        result = self.kg_service.query(
            """
            MATCH (m:Module {repo_uid: $repo_uid, name: $module_name})
            OPTIONAL MATCH (sf:SpecFragment)-[sr:SPECIFIES]->(m)
            OPTIONAL MATCH (m)-[:HAS_SKELETON]->(sk:ModuleSkeleton)
            OPTIONAL MATCH (m)-[:HAS_PLAN]->(mp:ModulePlan)
            RETURN properties(m) AS module,
                   collect(DISTINCT {fragment: properties(sf), relation: properties(sr)}) AS specs,
                   properties(sk) AS skeleton,
                   properties(mp) AS plan
            """,
            {"repo_uid": self.kg_service.repo_uid, "module_name": module_name},
            limit=5,
        )
        rows = list(result.get("rows") or [])
        if not rows:
            raise ValueError(f"Planning KG has no Module anchor for `{module_name}`")
        row = dict(rows[0])
        row["specs"] = [item for item in row.get("specs") or [] if item.get("fragment")]
        self._hydrate_spec_text(row["specs"])
        self._hydrate_artifact(row, "skeleton")
        self._hydrate_artifact(row, "plan")
        if require_spec and not row["specs"]:
            raise ValueError(f"Planning KG has no SpecFragment for `{module_name}`")
        if require_skeleton and not row.get("skeleton"):
            raise ValueError(f"Planning KG has no ModuleSkeleton for `{module_name}`")
        if require_plan and not row.get("plan"):
            raise ValueError(f"Planning KG has no ModulePlan for `{module_name}`")
        expected = dict(expected_fingerprints or {})
        checks = {
            "stage2": (row.get("module") or {}).get("stage2_fingerprint"),
            "skeleton": (row.get("skeleton") or {}).get("input_fingerprint"),
            "plan": (row.get("plan") or {}).get("input_fingerprint"),
        }
        if expected.get("spec_context"):
            found = {
                str((item.get("relation") or {}).get("input_fingerprint") or "")
                for item in row["specs"]
            }
            if found != {str(expected["spec_context"])}:
                raise ValueError(
                    f"Planning KG fingerprint mismatch for {module_name}/spec_context: "
                    f"expected {expected['spec_context']}, got {sorted(found)}"
                )
        for key, wanted in expected.items():
            if wanted and key in checks and str(checks[key] or "") != str(wanted):
                raise ValueError(
                    f"Planning KG fingerprint mismatch for {module_name}/{key}: "
                    f"expected {wanted}, got {checks[key] or '<missing>'}"
                )
        plan = row.get("plan") or {}
        skeleton = row.get("skeleton") or {}
        if require_plan and plan and skeleton and plan.get("skeleton_content_hash") != skeleton.get("content_hash"):
            raise ValueError(f"ModulePlan for `{module_name}` is bound to a stale ModuleSkeleton")
        if include_code_interface:
            interface = self.kg_service.query(
                """
                MATCH (m:Module {repo_uid: $repo_uid, name: $module_name})-[:HAS]->(p:Port)
                RETURN p.name AS name, p.attrs AS attrs, p.path AS path
                ORDER BY name
                """,
                {"repo_uid": self.kg_service.repo_uid, "module_name": module_name},
                limit=100,
            )
            normalized_ports = []
            for port in interface.get("rows") or []:
                attrs = port.get("attrs") or {}
                if isinstance(attrs, str):
                    try:
                        attrs = json.loads(attrs)
                    except json.JSONDecodeError:
                        attrs = {"raw": attrs}
                normalized_ports.append(
                    {
                        "name": str(port.get("name") or ""),
                        "direction": str(attrs.get("dir") or attrs.get("direction") or ""),
                        "width": str(attrs.get("width_expr") or attrs.get("width") or ""),
                        "path": str(port.get("path") or ""),
                    }
                )
            row["code_interface"] = normalized_ports
            children = self.kg_service.query(
                """
                MATCH (m:Module {repo_uid: $repo_uid, name: $module_name})
                UNWIND coalesce(m.planned_children, []) AS child_name
                MATCH (child:Module {repo_uid: $repo_uid, name: child_name})
                OPTIONAL MATCH (child)-[:HAS]->(p:Port)
                RETURN child.name AS module, child.actual_path AS actual_path,
                       child.implementation_status AS implementation_status,
                       collect(DISTINCT {name: p.name, attrs: p.attrs, path: p.path}) AS ports
                ORDER BY module
                """,
                {"repo_uid": self.kg_service.repo_uid, "module_name": module_name},
                limit=100,
            )
            child_interfaces = []
            for child in children.get("rows") or []:
                ports = []
                for port in child.get("ports") or []:
                    if not port.get("name"):
                        continue
                    attrs = port.get("attrs") or {}
                    if isinstance(attrs, str):
                        try:
                            attrs = json.loads(attrs)
                        except json.JSONDecodeError:
                            attrs = {"raw": attrs}
                    ports.append(
                        {
                            "name": str(port.get("name") or ""),
                            "direction": str(attrs.get("dir") or attrs.get("direction") or ""),
                            "width": str(attrs.get("width_expr") or attrs.get("width") or ""),
                        }
                    )
                child_interfaces.append(
                    {
                        "module": str(child.get("module") or ""),
                        "actual_path": str(child.get("actual_path") or ""),
                        "implementation_status": str(child.get("implementation_status") or ""),
                        "ports": ports,
                    }
                )
            row["child_code_interfaces"] = child_interfaces
        return row

    def _hydrate_artifact(self, context: Dict[str, Any], key: str) -> None:
        if self.output_root is None or not context.get(key):
            return
        artifact = str(context[key].get("artifact_path") or "")
        if not artifact:
            return
        try:
            context[f"{key}_artifact"] = json.loads(
                (self.output_root / artifact).read_text(encoding="utf-8")
            )
        except Exception:
            return

    def _hydrate_spec_text(self, specs: Iterable[Dict[str, Any]]) -> None:
        if self.output_root is None:
            return
        cache: Dict[str, Dict[str, Any]] = {}
        for item in specs:
            fragment = item.get("fragment") or {}
            relation = item.get("relation") or {}
            artifact = str(relation.get("artifact_path") or fragment.get("artifact_path") or "")
            if not artifact:
                continue
            path = self.output_root / artifact
            try:
                data = cache.setdefault(artifact, json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                continue
            local_ref = str(relation.get("local_ref") or "")
            for block in data.get("blocks") or []:
                if str(block.get("block_id") or "") != local_ref:
                    continue
                text = str(block.get("text") or "")
                if _content_hash(text) == str(fragment.get("content_hash") or ""):
                    fragment["text"] = text
                break

    @staticmethod
    def to_prompt_json(context: Mapping[str, Any]) -> str:
        return json.dumps(context, ensure_ascii=False, indent=2, sort_keys=True)

    @staticmethod
    def to_stage5_prompt_json(
        context: Mapping[str, Any],
        spec_refs: Iterable[str],
        max_chars: int = 12000,
    ) -> str:
        """Serialize only planning facts that are unique and relevant to a subtask.

        The full hydrated context remains available to callers for fingerprint
        validation.  Stage 5 already receives the current spec blocks,
        skeleton, and plan separately, so duplicating those artifact bodies in
        its prompt is both expensive and a source of conflicting emphasis.
        """

        if max_chars <= 0:
            return ""
        wanted_refs = {str(item) for item in spec_refs if str(item)}
        module = context.get("module") or {}
        skeleton = context.get("skeleton") or {}
        plan = context.get("plan") or {}

        def select(source: Mapping[str, Any], keys: Iterable[str]) -> Dict[str, Any]:
            return {
                key: source[key]
                for key in keys
                if key in source and source[key] not in (None, "", [], {})
            }

        payload: Dict[str, Any] = {
            "schema_version": "stage5_planning_context_v1",
            "module": select(
                module,
                (
                    "name",
                    "role",
                    "module_kind",
                    "expected_path",
                    "actual_path",
                    "implementation_status",
                    "is_top",
                    "planned_parents",
                    "planned_children",
                    "stage2_fingerprint",
                ),
            ),
            "bindings": {
                "skeleton": select(
                    skeleton,
                    (
                        "artifact_path",
                        "schema_version",
                        "content_hash",
                        "input_fingerprint",
                        "spec_context_fingerprint",
                    ),
                ),
                "plan": select(
                    plan,
                    (
                        "artifact_path",
                        "schema_version",
                        "content_hash",
                        "input_fingerprint",
                        "skeleton_content_hash",
                    ),
                ),
            },
            "selected_spec_links": [],
            "code_interface": [],
            "child_code_interfaces": [],
        }

        for item in context.get("specs") or []:
            relation = item.get("relation") or {}
            local_ref = str(relation.get("local_ref") or "")
            if local_ref not in wanted_refs:
                continue
            fragment = item.get("fragment") or {}
            payload["selected_spec_links"].append(
                {
                    **select(
                        relation,
                        ("local_ref", "confidence", "relevance_reason", "input_fingerprint"),
                    ),
                    **select(fragment, ("content_hash", "source_file")),
                }
            )
        payload["selected_spec_links"].sort(key=lambda item: str(item.get("local_ref") or ""))

        payload["code_interface"] = [
            select(port, ("name", "direction", "width", "path"))
            for port in context.get("code_interface") or []
            if isinstance(port, Mapping)
        ]
        planned_children = {
            str(item) for item in module.get("planned_children") or [] if str(item)
        }
        payload["child_code_interfaces"] = [
            {
                **select(child, ("module", "actual_path", "implementation_status")),
                "ports": [
                    select(port, ("name", "direction", "width"))
                    for port in child.get("ports") or []
                    if isinstance(port, Mapping)
                ],
            }
            for child in context.get("child_code_interfaces") or []
            if isinstance(child, Mapping)
            and (not planned_children or str(child.get("module") or "") in planned_children)
        ]

        omitted: Dict[str, int] = {}

        def render() -> str:
            if omitted:
                payload["truncated"] = True
                payload["omitted_count"] = dict(sorted(omitted.items()))
            return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

        text = render()
        if len(text) <= max_chars:
            return text

        for link in payload["selected_spec_links"]:
            if link.pop("relevance_reason", None) is not None:
                omitted["spec_relevance_reason"] = omitted.get("spec_relevance_reason", 0) + 1
        for port in payload["code_interface"]:
            if port.pop("path", None) is not None:
                omitted["port_path"] = omitted.get("port_path", 0) + 1
        text = render()
        if len(text) <= max_chars:
            return text

        # Preserve module identity, bindings, selected links, and the beginning
        # of each deterministic interface list.  Every removal is represented
        # structurally rather than by slicing serialized JSON.
        while len(text) > max_chars and payload["child_code_interfaces"]:
            child = payload["child_code_interfaces"][-1]
            if child.get("ports"):
                child["ports"].pop()
                omitted["child_ports"] = omitted.get("child_ports", 0) + 1
            else:
                payload["child_code_interfaces"].pop()
                omitted["child_interfaces"] = omitted.get("child_interfaces", 0) + 1
            text = render()
        while len(text) > max_chars and payload["code_interface"]:
            payload["code_interface"].pop()
            omitted["module_ports"] = omitted.get("module_ports", 0) + 1
            text = render()
        while len(text) > max_chars and payload["selected_spec_links"]:
            payload["selected_spec_links"].pop()
            omitted["selected_spec_links"] = omitted.get("selected_spec_links", 0) + 1
            text = render()
        if len(text) <= max_chars:
            return text

        minimal = {
            "schema_version": "stage5_planning_context_v1",
            "module": select(module, ("name", "stage2_fingerprint")),
            "truncated": True,
            "omitted_count": {"context": 1},
        }
        text = json.dumps(minimal, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return text if len(text) <= max_chars else ""

    @staticmethod
    def spec_markdown(context: Mapping[str, Any]) -> str:
        sections = []
        for item in context.get("specs") or []:
            fragment = item.get("fragment") or {}
            relation = item.get("relation") or {}
            sections.append(
                f"## {relation.get('local_ref') or 'SpecFragment'}\n"
                f"Source: {fragment.get('source_file') or '<unknown>'}\n\n"
                f"{fragment.get('text') or fragment.get('text_preview') or ''}"
            )
        return "\n\n".join(sections).strip()
