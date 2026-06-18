from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional, Set, Tuple

from pydantic import BaseModel, Field

from zerorepo.rtl_impl.debug_agent.trace_slicer import parse_rtl_blocks
from zerorepo.rtl_impl.rtl_kg import (
    KnowledgeGraphRTL,
    Neo4jConnection,
    RTLNeo4jIngestor,
    compute_repo_uid,
)
from zerorepo.config.checkpoint_config import CheckpointManager
from zerorepo.rpg_gen.base.tools import Tool, ToolCallArguments, ToolExecResult


_WRITE_KEYWORDS = re.compile(
    r"\b(create|merge|set|delete|detach\s+delete|remove|drop|load\s+csv)\b",
    flags=re.IGNORECASE,
)
_CALL_DB = re.compile(r"\bcall\s+db\.", flags=re.IGNORECASE)
_NODE_PATTERN = re.compile(
    r"\((?P<var>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*(?P<label>[A-Za-z_][A-Za-z0-9_]*)(?P<props>\s*\{[^()]*\})?\)"
)
_RTL_ATTR_PREFIX = r"(?:\(\*.*?\*\)\s*)*"


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9_+-]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return text.strip()


def _strip_cypher_comments(text: str) -> str:
    return re.sub(r"(?m)//.*?$", "", text).strip()


def _truncate_text(value: str, limit: int = 2000) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."



class RTLKgService:
    """Service wrapper around the RTL knowledge graph implementation.

    Boundary:
    - Neo4j must be started before using this service (e.g. via
      ``docker compose -f zerorepo/rtl_impl/rtl_kg/docker-compose.dev.yml up -d``).
    - This service connects to an already-running Neo4j instance.
    - Pipeline code writes KG snapshots at fixed stages.
    - Agents only receive read-only Cypher query capability through QueryRtlKgTool.
    """

    def __init__(
        self,
        repo_path: Path,
        checkpoint_manager: CheckpointManager,
        repo_data: Optional[Dict[str, Any]],
        config: Optional[Dict[str, Any]],
        logger: Optional[logging.Logger] = None,
    ):
        self.repo_path = Path(repo_path)
        self.checkpoint_manager = checkpoint_manager
        self.repo_data = repo_data or {}
        self.config = dict(config or {})
        self.logger = logger or logging.getLogger(__name__)

        self.enabled = bool(self.config.get("enabled", False))
        self.mode = str(self.config.get("mode", "required")).strip().lower() or "required"
        # Default kg_root is the rtl_kg package directory (relative to this file).
        # Config can override this with an absolute path if needed.
        _default_kg_root = Path(__file__).resolve().parent / "rtl_kg"
        self.kg_root = Path(
            self.config.get("rtl_agent_root", str(_default_kg_root))
        )
        self.batch_size = int(self.config.get("batch_size", 2000) or 2000)
        self.default_query_limit = int(self.config.get("default_query_limit", 25) or 25)
        self.max_query_rows = int(self.config.get("max_query_rows", 100) or 100)

        neo4j_cfg = self.config.get("neo4j", {}) or {}
        self.neo4j_uri = str(neo4j_cfg.get("uri", "bolt://localhost:7687")).strip()
        self.neo4j_user = str(neo4j_cfg.get("user", "neo4j")).strip()
        self.neo4j_pass = str(neo4j_cfg.get("password", "neo4j123456")).strip()

        self._ingestor: Optional[Any] = None
        self._repo_uid: Optional[str] = None
        self._initialized = False

    @property
    def repo_uid(self) -> str:
        if not self._repo_uid:
            self._repo_uid = compute_repo_uid(self.repo_path)
        return self._repo_uid

    @property
    def state_path(self) -> Path:
        return self.checkpoint_manager.get_path("rtl_kg_state")

    @property
    def manifest_path(self) -> Path:
        return self.checkpoint_manager.get_path("rtl_kg_manifest")

    def is_enabled(self) -> bool:
        return self.enabled

    def initialize(self) -> None:
        if not self.enabled:
            return
        if self._initialized:
            return

        try:
            import neo4j  # noqa: F401
        except Exception as exc:  # pragma: no cover - environment dependent
            raise RuntimeError(
                "RTL KG requires the Python package 'neo4j' to be installed."
            ) from exc

        self._repo_uid = compute_repo_uid(self.repo_path)
        conn = Neo4jConnection(
            uri=self.neo4j_uri,
            user=self.neo4j_user,
            password=self.neo4j_pass,
        )
        self._ingestor = RTLNeo4jIngestor(
            conn=conn,
            batch_size=self.batch_size,
            logger=self.logger.info,
        )

        try:
            with conn.driver() as driver:
                with driver.session() as session:
                    session.run("RETURN 1 AS ok").single()
        except Exception as exc:  # pragma: no cover - environment dependent
            raise RuntimeError(
                f"Failed to connect to Neo4j at {self.neo4j_uri} for RTL KG."
            ) from exc

        self._initialized = True
        self._save_state(
            {
                "enabled": self.enabled,
                "mode": self.mode,
                "repo_uid": self.repo_uid,
                "neo4j_uri": self.neo4j_uri,
                "kg_root": str(self.kg_root),
                "initialized": True,
            }
        )

    def sync_plan_snapshot(
        self,
        stage: str = "post_skeleton",
        filter_to_planned_skeleton: bool = True,
    ) -> Dict[str, Any]:
        """Write a fixed pipeline snapshot after skeleton planning/materialization."""
        self.initialize()
        nodes, edges = self._build_augmented_snapshot(
            stage=stage,
            filter_to_planned_skeleton=filter_to_planned_skeleton,
        )
        self._ingestor.ingest(nodes=nodes, edges=edges, mode="full", repo_uid=self.repo_uid)
        payload = {
            "stage": stage,
            "repo_uid": self.repo_uid,
            "nodes": len(nodes),
            "edges": len(edges),
            "changed_paths": [],
            "filter_to_planned_skeleton": filter_to_planned_skeleton,
        }
        self._append_manifest(payload)
        return payload

    def refresh_repo_files(
        self,
        changed_paths: Optional[List[str]] = None,
        stage: str = "post_graph",
        filter_to_planned_skeleton: bool = True,
    ) -> Dict[str, Any]:
        """Refresh KG from on-disk repository files at a fixed pipeline stage."""
        self.initialize()
        nodes, edges = self._build_augmented_snapshot(
            stage=stage,
            filter_to_planned_skeleton=filter_to_planned_skeleton,
        )
        self._ingestor.ingest(nodes=nodes, edges=edges, mode="full", repo_uid=self.repo_uid)
        payload = {
            "stage": stage,
            "repo_uid": self.repo_uid,
            "nodes": len(nodes),
            "edges": len(edges),
            "changed_paths": list(changed_paths or []),
            "filter_to_planned_skeleton": filter_to_planned_skeleton,
        }
        self._append_manifest(payload)
        return payload

    def query(
        self,
        cypher: str,
        params: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        self.initialize()
        limit_value = max(1, min(int(limit or self.default_query_limit), self.max_query_rows))
        prepared_cypher, prepared_params = self._prepare_readonly_query(
            cypher=cypher,
            params=params or {},
            limit=limit_value,
        )

        conn = self._ingestor.conn
        with conn.driver() as driver:
            with driver.session() as session:
                result = session.run(prepared_cypher, **prepared_params)
                rows = [self._serialize_record(record.data()) for record in result]

        preview_rows = rows[: min(len(rows), 10)]
        preview_json = json.dumps(preview_rows, ensure_ascii=False, indent=2)
        summary = (
            f"Returned {len(rows)} row(s) for repo_uid={self.repo_uid}.\n"
            f"Query Preview:\n{_truncate_text(preview_json, 4000)}"
        )
        return {
            "cypher": prepared_cypher,
            "params": prepared_params,
            "row_count": len(rows),
            "rows": rows,
            "summary": summary,
        }

    def build_batch_context(self, batch: Any) -> str:
        if not self.enabled:
            return ""
        file_path = str(getattr(batch, "file_path", "") or "").strip()
        if not file_path or (file_path.startswith("<") and file_path.endswith(">")):
            return ""

        sections: List[str] = []
        try:
            file_meta = self.query(
                """
                MATCH (f:File {path: $file_path, repo_uid: $repo_uid})
                RETURN f.path AS file_path,
                       f.file_kind AS file_kind,
                       f.implementation_status AS implementation_status,
                       f.responsibility AS responsibility,
                       f.implementation_summary AS implementation_summary,
                       f.target_unit_names AS target_unit_names,
                       f.depends_on_files AS depends_on_files
                """,
                {"file_path": file_path, "repo_uid": self.repo_uid},
                limit=5,
            )
            if file_meta["rows"]:
                sections.append("=== RTL KG File Context ===")
                sections.append(json.dumps(file_meta["rows"], ensure_ascii=False, indent=2))
        except Exception as exc:
            sections.append(f"=== RTL KG File Context Error ===\n{exc}")

        try:
            module_meta = self.query(
                """
                MATCH (f:File {path: $file_path, repo_uid: $repo_uid})-[:DEFINES]->(m:Module)
                OPTIONAL MATCH (m)-[:HAS_PORT]->(p:Port)
                WITH m, collect(DISTINCT p.name) AS ports
                RETURN m.name AS module_name, m.path AS path, ports
                ORDER BY module_name
                """,
                {"file_path": file_path, "repo_uid": self.repo_uid},
                limit=10,
            )
            if module_meta["rows"]:
                sections.append("=== RTL KG Modules In File ===")
                sections.append(json.dumps(module_meta["rows"], ensure_ascii=False, indent=2))
        except Exception as exc:
            sections.append(f"=== RTL KG Modules Error ===\n{exc}")

        try:
            instance_meta = self.query(
                """
                MATCH (f:File {path: $file_path, repo_uid: $repo_uid})-[:DEFINES]->(m:Module)-[:INSTANTIATES]->(i:Instance)
                OPTIONAL MATCH (i)-[:OF_MODULE]->(target:Module)
                RETURN m.name AS owner_module,
                       i.name AS instance_name,
                       target.name AS target_module,
                       target.path AS target_path
                ORDER BY owner_module, instance_name
                """,
                {"file_path": file_path, "repo_uid": self.repo_uid},
                limit=20,
            )
            if instance_meta["rows"]:
                sections.append("=== RTL KG Instance Relationships ===")
                sections.append(json.dumps(instance_meta["rows"], ensure_ascii=False, indent=2))
        except Exception as exc:
            sections.append(f"=== RTL KG Instance Error ===\n{exc}")

        return "\n".join(sections).strip()

    def _build_augmented_snapshot(
        self,
        stage: str,
        filter_to_planned_skeleton: bool = True,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        kg = KnowledgeGraphRTL.build(self.repo_path)
        nodes = list(kg.neo4j_nodes())
        edges = list(kg.neo4j_edges())
        nodes, edges = self._augment_snapshot_with_text_fallback(nodes, edges)
        if filter_to_planned_skeleton:
            nodes, edges = self._filter_snapshot_to_planned_skeleton(nodes, edges)
        file_specs = {
            str(item.get("file_path", "")).strip(): item
            for item in (
                (self.repo_data.get("rtl_metadata", {}) or {}).get("file_specs", []) or []
            )
            if isinstance(item, dict) and str(item.get("file_path", "")).strip()
        }

        for node in nodes:
            kind = str(node.get("kind", "")).strip()
            if kind == "Repo":
                attrs = node.get("attrs", {}) if isinstance(node.get("attrs"), dict) else {}
                attrs["sync_stage"] = stage
                attrs["repo_root"] = str(self.repo_path)
                node["attrs"] = attrs
                continue
            if kind != "File":
                continue
            file_path = str(node.get("path", "")).strip()
            spec = file_specs.get(file_path)
            if not spec:
                continue
            attrs = node.get("attrs", {}) if isinstance(node.get("attrs"), dict) else {}
            target_unit_names = [
                str(unit.get("unit_name", "")).strip()
                for unit in (spec.get("target_units", []) or [])
                if isinstance(unit, dict) and str(unit.get("unit_name", "")).strip()
            ]
            attrs.update(
                {
                    "planning_stage": stage,
                    "file_kind": str(spec.get("file_kind", "")).strip(),
                    "implementation_status": str(spec.get("implementation_status", "")).strip(),
                    "responsibility": str(spec.get("responsibility", "")).strip(),
                    "implementation_summary": str(spec.get("implementation_summary", "")).strip(),
                    "owned_modules": list(spec.get("owned_modules", []) or []),
                    "target_unit_names": target_unit_names,
                    "depends_on_files": list(spec.get("depends_on_files", []) or []),
                    "related_req_ids": list(spec.get("related_req_ids", []) or []),
                    "related_test_ids": list(spec.get("related_test_ids", []) or []),
                    "related_prop_ids": list(spec.get("related_prop_ids", []) or []),
                }
            )
            node["attrs"] = attrs
            node["file_kind"] = attrs["file_kind"]
            node["implementation_status"] = attrs["implementation_status"]
            node["responsibility"] = attrs["responsibility"]
            node["implementation_summary"] = attrs["implementation_summary"]
            node["owned_modules"] = attrs["owned_modules"]
            node["target_unit_names"] = attrs["target_unit_names"]
            node["depends_on_files"] = attrs["depends_on_files"]
            node["related_req_ids"] = attrs["related_req_ids"]
            node["related_test_ids"] = attrs["related_test_ids"]
            node["related_prop_ids"] = attrs["related_prop_ids"]

        return nodes, edges

    def _augment_snapshot_with_text_fallback(
        self,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Add a minimal RTL subgraph when tree-sitter fails to emit Module nodes.

        The external KG builder is still the primary source. This fallback only
        fills files where a text-visible `module ... endmodule` has no matching
        Module node, which keeps debug slicing usable for parser-hostile but
        Verilator-legal RTL.
        """
        module_keys = {
            (str(node.get("name") or ""), self._normalize_kg_path(str(node.get("path") or "")))
            for node in nodes
            if str(node.get("kind") or "") == "Module"
        }
        nodes_by_uid = {
            str(node.get("uid") or ""): node
            for node in nodes
            if str(node.get("uid") or "")
        }
        file_nodes_by_path = {
            self._normalize_kg_path(str(node.get("path") or "")): node
            for node in nodes
            if str(node.get("kind") or "") == "File"
        }

        added_modules = 0
        added_nodes: List[Dict[str, Any]] = []
        added_edges: List[Dict[str, Any]] = []

        for path in sorted(self.repo_path.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in {".v", ".vh", ".sv", ".svh"}:
                continue
            try:
                rel_path = path.relative_to(self.repo_path).as_posix()
                text = path.read_text(encoding="utf-8", errors="ignore").replace("\r\n", "\n")
            except Exception:
                continue
            norm_path = self._normalize_kg_path(rel_path)
            file_node = file_nodes_by_path.get(norm_path)
            if file_node is None:
                file_uid = self._kg_uid("file", norm_path)
                file_node = {
                    "uid": file_uid,
                    "repo_uid": self.repo_uid,
                    "kind": "File",
                    "name": Path(norm_path).name,
                    "path": norm_path,
                    "h": hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest(),
                    "attrs": {"is_dir": False, "suffix": path.suffix},
                }
                if file_uid not in nodes_by_uid:
                    nodes_by_uid[file_uid] = file_node
                    added_nodes.append(file_node)

            for module in self._fallback_modules(text, norm_path):
                module_name = str(module["name"])
                if (module_name, norm_path) in module_keys:
                    continue
                module_nodes, module_edges = self._fallback_module_graph(
                    module=module,
                    file_node=file_node,
                )
                for node in module_nodes:
                    uid = str(node.get("uid") or "")
                    if uid and uid not in nodes_by_uid:
                        nodes_by_uid[uid] = node
                        added_nodes.append(node)
                added_edges.extend(module_edges)
                module_keys.add((module_name, norm_path))
                added_modules += 1

        if added_modules and self.logger is not None:
            self.logger.info(
                "[rtl_kg] Added text-fallback RTL KG nodes for %d module(s): %d node(s), %d edge(s)",
                added_modules,
                len(added_nodes),
                len(added_edges),
            )
        return nodes + added_nodes, edges + added_edges

    def _fallback_modules(self, text: str, rel_path: str) -> List[Dict[str, Any]]:
        modules: List[Dict[str, Any]] = []
        pattern = re.compile(
            rf"(?ms)^\s*{_RTL_ATTR_PREFIX}module\s+([A-Za-z_][A-Za-z0-9_]*)\b.*?^\s*endmodule\b"
        )
        for match in pattern.finditer(text):
            body = match.group(0)
            start = match.start()
            end = match.end()
            modules.append(
                {
                    "name": match.group(1),
                    "path": rel_path,
                    "text": body,
                    "sl": text[:start].count("\n") + 1,
                    "el": text[:end].count("\n") + 1,
                    "h": hashlib.sha1(body.encode("utf-8", errors="ignore")).hexdigest(),
                }
            )
        return modules

    def _fallback_module_graph(
        self,
        *,
        module: Dict[str, Any],
        file_node: Dict[str, Any],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        module_name = str(module["name"])
        rel_path = str(module["path"])
        module_text = str(module["text"])
        module_uid = self._kg_uid("module", module_name, rel_path)
        module_node = {
            "uid": module_uid,
            "repo_uid": self.repo_uid,
            "kind": "Module",
            "name": module_name,
            "path": rel_path,
            "sl": int(module["sl"]),
            "el": int(module["el"]),
            "h": str(module["h"]),
            "attrs": {"fallback_parser": "zerorepo_text"},
        }
        nodes: List[Dict[str, Any]] = [module_node]
        edges: List[Dict[str, Any]] = [
            self._kg_edge("DEFINES", str(file_node["uid"]), module_uid)
        ]

        symbols: Dict[str, Dict[str, Any]] = {}
        for port in self._fallback_ports(module_text):
            name = str(port.get("name") or "")
            if not name:
                continue
            uid = self._kg_uid("port", module_name, name, rel_path)
            node = {
                "uid": uid,
                "repo_uid": self.repo_uid,
                "kind": "Port",
                "name": name,
                "path": rel_path,
                "attrs": {"module": module_name, "fallback_parser": "zerorepo_text", **port},
            }
            symbols.setdefault(name, node)
            nodes.append(node)
            edges.append(self._kg_edge("HAS", module_uid, uid, k="Port"))

        for param in self._fallback_params(module_text):
            name = str(param.get("name") or "")
            if not name or name in symbols:
                continue
            uid = self._kg_uid("param", module_name, name, rel_path)
            node = {
                "uid": uid,
                "repo_uid": self.repo_uid,
                "kind": "Param",
                "name": name,
                "path": rel_path,
                "attrs": {"module": module_name, "fallback_parser": "zerorepo_text", **param},
            }
            symbols[name] = node
            nodes.append(node)
            edges.append(self._kg_edge("HAS", module_uid, uid, k="Param"))

        for sig in self._fallback_signals(module_text, existing=set(symbols)):
            name = str(sig.get("name") or "")
            if not name or name in symbols:
                continue
            uid = self._kg_uid("signal", module_name, name, rel_path)
            node = {
                "uid": uid,
                "repo_uid": self.repo_uid,
                "kind": "Signal",
                "name": name,
                "path": rel_path,
                "attrs": {"module": module_name, "fallback_parser": "zerorepo_text", **sig},
            }
            symbols[name] = node
            nodes.append(node)
            edges.append(self._kg_edge("HAS", module_uid, uid, k="Signal"))

        blocks = parse_rtl_blocks(module_text)
        for block in blocks:
            kg_kind = "AlwaysBlock" if block.kind == "always" else "Assign"
            uid_kind = "always" if block.kind == "always" else "assign"
            sl = int(module["sl"]) + int(block.start_line) - 1
            el = int(module["sl"]) + int(block.end_line) - 1
            block_uid = self._kg_uid(uid_kind, module_name, rel_path, str(sl), str(el))
            block_node = {
                "uid": block_uid,
                "repo_uid": self.repo_uid,
                "kind": kg_kind,
                "path": rel_path,
                "sl": sl,
                "el": el,
                "h": hashlib.sha1(block.code.encode("utf-8", errors="ignore")).hexdigest(),
                "attrs": {
                    "module": module_name,
                    "fallback_parser": "zerorepo_text",
                    "clocking": block.clocking,
                },
            }
            nodes.append(block_node)
            edges.append(self._kg_edge("HAS", module_uid, block_uid, k=kg_kind))

            for name in sorted(set(block.writes) | set(block.reads)):
                if name not in symbols and self._fallback_should_create_symbol(name):
                    sig_uid = self._kg_uid("signal", module_name, name, rel_path)
                    sig_node = {
                        "uid": sig_uid,
                        "repo_uid": self.repo_uid,
                        "kind": "Signal",
                        "name": name,
                        "path": rel_path,
                        "attrs": {
                            "module": module_name,
                            "fallback_parser": "zerorepo_text",
                            "inferred": True,
                        },
                    }
                    symbols[name] = sig_node
                    nodes.append(sig_node)
                    edges.append(self._kg_edge("HAS", module_uid, sig_uid, k="Signal"))

            for write_name in block.writes:
                target = symbols.get(write_name)
                if not target or str(target.get("kind")) == "Param":
                    continue
                edges.append(self._kg_edge("DRIVES", block_uid, str(target["uid"]), k=block.kind, cnt=1))

        return nodes, edges

    def _fallback_ports(self, module_text: str) -> List[Dict[str, Any]]:
        ports: Dict[str, Dict[str, Any]] = {}
        header = self._fallback_module_header(module_text)
        if header:
            for segment in self._split_comma_items(header):
                direction = self._find_decl_direction(segment)
                name = self._last_identifier(segment)
                if direction and name:
                    ports[name] = {
                        "name": name,
                        "dir": direction,
                        "width_expr": self._find_width_expr(segment),
                    }
        for match in re.finditer(r"(?m)^\s*(input|output|inout)\b([^;]*);", module_text):
            direction = match.group(1)
            rest = match.group(2)
            width = self._find_width_expr(rest)
            for name in self._decl_names(rest):
                ports[name] = {"name": name, "dir": direction, "width_expr": width}
        return list(ports.values())

    def _fallback_params(self, module_text: str) -> List[Dict[str, Any]]:
        params: List[Dict[str, Any]] = []
        for match in re.finditer(r"(?m)^\s*(localparam|parameter)\b([^;]*);", module_text):
            kind = match.group(1)
            rest = match.group(2)
            width = self._find_width_expr(rest)
            for name in self._decl_names(rest):
                params.append({"name": name, "decl_kind": kind, "width_expr": width})
        return params

    def _fallback_signals(self, module_text: str, *, existing: Set[str]) -> List[Dict[str, Any]]:
        signals: List[Dict[str, Any]] = []
        for match in re.finditer(r"(?m)^\s*(wire|reg|integer)\b([^;]*);", module_text):
            kind = match.group(1)
            rest = match.group(2)
            width = self._find_width_expr(rest)
            for name in self._decl_names(rest):
                if name not in existing:
                    signals.append({"name": name, "decl_kind": kind, "width_expr": width})
        return signals

    def _fallback_module_header(self, module_text: str) -> str:
        match = re.search(r"\bmodule\b\s+[A-Za-z_][A-Za-z0-9_]*\s*\(", module_text)
        if not match:
            return ""
        start = match.end()
        depth = 1
        i = start
        while i < len(module_text):
            ch = module_text[i]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    return module_text[start:i]
            i += 1
        return ""

    def _split_comma_items(self, text: str) -> List[str]:
        items: List[str] = []
        start = 0
        paren = bracket = brace = 0
        for i, ch in enumerate(text):
            if ch == "(":
                paren += 1
            elif ch == ")":
                paren = max(0, paren - 1)
            elif ch == "[":
                bracket += 1
            elif ch == "]":
                bracket = max(0, bracket - 1)
            elif ch == "{":
                brace += 1
            elif ch == "}":
                brace = max(0, brace - 1)
            elif ch == "," and paren == 0 and bracket == 0 and brace == 0:
                items.append(text[start:i].strip())
                start = i + 1
        tail = text[start:].strip()
        if tail:
            items.append(tail)
        return items

    def _decl_names(self, text: str) -> List[str]:
        cleaned = re.sub(r"\[[^\]]+\]", " ", text)
        cleaned = re.sub(r"\b(input|output|inout|wire|reg|logic|integer|signed|unsigned)\b", " ", cleaned)
        names: List[str] = []
        for item in self._split_comma_items(cleaned):
            item = item.split("=", 1)[0]
            match = re.search(r"\b([A-Za-z_][A-Za-z0-9_]*)\b", item)
            if match:
                names.append(match.group(1))
        return names

    def _find_decl_direction(self, text: str) -> str:
        match = re.search(r"\b(input|output|inout)\b", text)
        return match.group(1) if match else ""

    def _find_width_expr(self, text: str) -> str:
        match = re.search(r"(\[[^\]]+\])", text)
        return match.group(1) if match else ""

    def _last_identifier(self, text: str) -> str:
        cleaned = re.sub(r"\[[^\]]+\]", " ", text)
        names = [
            name
            for name in re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", cleaned)
            if name not in {"input", "output", "inout", "wire", "reg", "logic", "signed", "unsigned"}
        ]
        return names[-1] if names else ""

    def _fallback_should_create_symbol(self, name: str) -> bool:
        if not name or name in {"d0", "d1", "d2", "d3", "d4", "d5", "d6", "d7", "d8", "d9"}:
            return False
        return bool(re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name))

    def _kg_uid(self, *parts: str) -> str:
        return ":".join([self.repo_uid, *[str(part) for part in parts]])

    def _kg_edge(self, rel_type: str, source_uid: str, target_uid: str, **props: Any) -> Dict[str, Any]:
        return {
            "uid": f"{source_uid}:{rel_type}:{target_uid}",
            "eid": f"{source_uid}:{rel_type}:{target_uid}",
            "repo_uid": self.repo_uid,
            "type": rel_type,
            "source_uid": source_uid,
            "target_uid": target_uid,
            **props,
        }

    def _filter_snapshot_to_planned_skeleton(
        self,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        allowed_file_paths = self._planned_kg_file_paths()
        if not allowed_file_paths:
            return nodes, edges

        nodes_by_uid = {
            str(node.get("uid", "")).strip(): node
            for node in nodes
            if isinstance(node, dict) and str(node.get("uid", "")).strip()
        }

        keep_uids: Set[str] = set()
        for uid, node in nodes_by_uid.items():
            kind = str(node.get("kind", "")).strip()
            if kind == "Repo":
                keep_uids.add(uid)
                continue
            if kind != "File":
                continue
            file_path = self._normalize_kg_path(str(node.get("path", "")).strip())
            if file_path in allowed_file_paths:
                keep_uids.add(uid)

        changed = True
        while changed:
            changed = False
            for edge in edges:
                src_uid = self._edge_endpoint_uid(edge, "source")
                dst_uid = self._edge_endpoint_uid(edge, "target")
                if not src_uid or not dst_uid:
                    continue
                src_node = nodes_by_uid.get(src_uid)
                dst_node = nodes_by_uid.get(dst_uid)
                if src_node is None or dst_node is None:
                    continue

                if src_uid in keep_uids and self._node_allowed_in_planned_snapshot(dst_node, allowed_file_paths):
                    if dst_uid not in keep_uids:
                        keep_uids.add(dst_uid)
                        changed = True

                if dst_uid in keep_uids and self._node_allowed_in_planned_snapshot(src_node, allowed_file_paths):
                    if src_uid not in keep_uids:
                        keep_uids.add(src_uid)
                        changed = True

        filtered_nodes = [node for node in nodes if str(node.get("uid", "")).strip() in keep_uids]
        filtered_edges = []
        for edge in edges:
            src_uid = self._edge_endpoint_uid(edge, "source")
            dst_uid = self._edge_endpoint_uid(edge, "target")
            if src_uid in keep_uids and dst_uid in keep_uids:
                filtered_edges.append(edge)

        self.logger.info(
            "Filtered RTL KG snapshot to planned skeleton paths: %d node(s) -> %d, %d edge(s) -> %d",
            len(nodes),
            len(filtered_nodes),
            len(edges),
            len(filtered_edges),
        )
        return filtered_nodes, filtered_edges

    def _planned_kg_file_paths(self) -> Set[str]:
        rtl_metadata = self.repo_data.get("rtl_metadata", {}) or {}
        files = rtl_metadata.get("files", {}) or {}
        file_specs = rtl_metadata.get("file_specs", []) or []

        planned_files: Set[str] = set()
        for file_path in files.keys():
            normalized = self._normalize_kg_path(str(file_path).strip())
            if normalized and normalized != ".":
                planned_files.add(normalized)
        for item in file_specs:
            if not isinstance(item, dict):
                continue
            normalized = self._normalize_kg_path(str(item.get("file_path", "")).strip())
            if normalized and normalized != ".":
                planned_files.add(normalized)

        if not planned_files:
            return set()

        allowed_paths: Set[str] = {"."}
        for file_path in planned_files:
            if file_path.startswith(".zerorepo/") or file_path == ".zerorepo":
                continue
            allowed_paths.add(file_path)
            parent = PurePosixPath(file_path).parent
            while str(parent) not in {"", "."}:
                allowed_paths.add(str(parent))
                parent = parent.parent
        return allowed_paths

    def _node_allowed_in_planned_snapshot(
        self,
        node: Dict[str, Any],
        allowed_file_paths: Set[str],
    ) -> bool:
        kind = str(node.get("kind", "")).strip()
        if kind == "Repo":
            return True
        if kind != "File":
            return True
        file_path = self._normalize_kg_path(str(node.get("path", "")).strip())
        return file_path in allowed_file_paths

    def _edge_endpoint_uid(self, edge: Dict[str, Any], key: str) -> str:
        direct_key = f"{key}_uid"
        if isinstance(edge.get(direct_key), str) and edge.get(direct_key):
            return str(edge.get(direct_key)).strip()
        endpoint = edge.get(key)
        if isinstance(endpoint, dict):
            return str(endpoint.get("uid", "")).strip()
        return ""

    def _normalize_kg_path(self, value: str) -> str:
        normalized = value.replace("\\", "/").strip()
        if not normalized:
            return ""
        if normalized == ".":
            return "."
        return PurePosixPath(normalized).as_posix()

    def _prepare_readonly_query(
        self,
        cypher: str,
        params: Dict[str, Any],
        limit: int,
    ) -> Tuple[str, Dict[str, Any]]:
        cleaned = _strip_code_fences(cypher)
        cleaned = cleaned.rstrip(";").strip()
        cleaned_no_comments = _strip_cypher_comments(cleaned)

        if not cleaned_no_comments:
            raise ValueError("Cypher query is empty.")
        if _WRITE_KEYWORDS.search(cleaned_no_comments) or _CALL_DB.search(cleaned_no_comments):
            raise ValueError("query_rtl_kg only allows read-only Cypher. Write/admin keywords are forbidden.")
        if "return" not in cleaned_no_comments.lower():
            raise ValueError("query_rtl_kg requires a RETURN clause.")

        scoped = cleaned_no_comments
        if "repo_uid" not in cleaned_no_comments.lower():
            scoped = self._inject_repo_uid_scope(cleaned_no_comments)

        if "limit" not in scoped.lower():
            scoped = f"{scoped}\nLIMIT {limit}"

        query_params = dict(params)
        query_params["repo_uid"] = self.repo_uid
        return scoped, query_params

    def _inject_repo_uid_scope(self, cypher: str) -> str:
        replacements = 0

        def repl(match: re.Match) -> str:
            nonlocal replacements
            var = match.group("var")
            label = match.group("label")
            props = match.group("props")
            replacements += 1
            if props:
                inner = props.strip()[1:-1].strip()
                if re.search(r"\brepo_uid\s*:", inner):
                    return match.group(0)
                merged = f"repo_uid: $repo_uid"
                if inner:
                    merged += f", {inner}"
                return f"({var}:{label} {{{merged}}})"
            return f"({var}:{label} {{repo_uid: $repo_uid}})"

        scoped = _NODE_PATTERN.sub(repl, cypher)
        if replacements == 0 and "repo_uid" not in scoped.lower():
            raise ValueError(
                "query_rtl_kg could not automatically scope this query. "
                "Use labeled node patterns or add an explicit repo_uid filter."
            )
        return scoped

    def _serialize_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        return {key: self._serialize_value(value) for key, value in record.items()}

    def _serialize_value(self, value: Any) -> Any:
        try:
            from neo4j.graph import Node, Relationship, Path as Neo4jPath  # type: ignore
        except Exception:  # pragma: no cover - environment dependent
            Node = Relationship = Neo4jPath = tuple()  # type: ignore

        if isinstance(value, dict):
            return {str(k): self._serialize_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._serialize_value(item) for item in value]
        if Node and isinstance(value, Node):
            props = {str(k): self._serialize_value(v) for k, v in value.items()}
            props["_labels"] = sorted(list(value.labels))
            props["_element_id"] = value.element_id
            return props
        if Relationship and isinstance(value, Relationship):
            props = {str(k): self._serialize_value(v) for k, v in value.items()}
            props["_type"] = value.type
            props["_element_id"] = value.element_id
            return props
        if Neo4jPath and isinstance(value, Neo4jPath):
            return {
                "nodes": [self._serialize_value(node) for node in value.nodes],
                "relationships": [self._serialize_value(rel) for rel in value.relationships],
            }
        return value

    def _save_state(self, data: Dict[str, Any]) -> None:
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _append_manifest(self, event: Dict[str, Any]) -> None:
        payload = {"events": []}
        if self.manifest_path.exists():
            try:
                with open(self.manifest_path, "r", encoding="utf-8") as f:
                    payload = json.load(f)
            except Exception:
                payload = {"events": []}
        payload.setdefault("events", []).append(event)
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)


class QueryRtlKgParams(BaseModel):
    cypher: str = Field(..., min_length=1, description="Read-only Cypher query text.")
    params: Dict[str, Any] = Field(default_factory=dict, description="Query parameters.")
    limit: int = Field(default=25, ge=1, le=100, description="Maximum number of rows to return.")


class QueryRtlKgTool(Tool):
    name = "query_rtl_kg"
    description = """
## Tool Name: query_rtl_kg
Run a read-only Cypher query against the current RTL knowledge graph partition.

### Parameters
{
  "tool_name": "query_rtl_kg",
  "parameters": {
    "cypher": "MATCH (m:Module) RETURN m.name AS module_name",
    "params": {},
    "limit": 25
  }
}

### Rules
- This tool is READ-ONLY. Do not use CREATE, MERGE, SET, DELETE, REMOVE, DROP, LOAD CSV, or CALL db.*.
- KG writes are handled by the ZeroRepo pipeline at fixed stages; this tool is for querying only.
- Prefer querying RTL KG entities such as Module, Instance, Port, Signal, Param, Package, CONNECTS, DRIVES, INCLUDES, and IMPORTS.
- You do not need to manually scope repo_uid in common labeled node queries; the system will scope to the current repository partition when possible.
- Keep the query narrow and use LIMIT responsibly.
""".strip()
    ParamModel = QueryRtlKgParams

    @classmethod
    def custom_parse(cls, raw: str) -> Optional[List[ToolCallArguments]]:
        raw = _strip_code_fences(raw)
        candidates: List[ToolCallArguments] = []
        try:
            parsed = json.loads(raw)
            items = parsed if isinstance(parsed, list) else [parsed]
        except Exception:
            return candidates

        for item in items:
            if not isinstance(item, dict):
                continue
            tool_name = str(item.get("tool_name", "")).strip().lower()
            if tool_name != cls.name:
                continue
            params = item.get("parameters", {})
            if isinstance(params, dict):
                candidates.append(params)
        return candidates

    @classmethod
    async def execute(cls, arguments: Dict[str, Any], env: Optional[Any] = None) -> ToolExecResult:
        kg_service = getattr(env, "kg_service", None)
        if kg_service is None:
            return ToolExecResult(output=None, error="RTL KG service is not available in this environment.", error_code=1)
        try:
            result = kg_service.query(
                cypher=arguments.get("cypher", ""),
                params=arguments.get("params", {}) or {},
                limit=arguments.get("limit", 25),
            )
        except Exception as exc:
            return ToolExecResult(output=None, error=str(exc), error_code=1)

        return ToolExecResult(
            output=result["summary"],
            error=None,
            error_code=0,
            state=result,
        )
