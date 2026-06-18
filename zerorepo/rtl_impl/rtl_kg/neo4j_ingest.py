#!/usr/bin/env python3
"""
Neo4j bulk ingestor for RTL Knowledge Graph.

Design goals
- Batch MERGE nodes/edges (UNWIND) for speed
- Create constraints + indexes (IF NOT EXISTS)
- Support full rebuild (delete one repo partition) and incremental (MERGE-only) updates
- Works with Neo4j running in Docker (bolt://localhost:7687)

Expected node format (from kg.neo4j_nodes()):
    {
      "uid": "stable-id",
      "kind": "Module" | "File" | "Signal" | ... ,   # used as Neo4j label
      ... other properties ...
    }

Expected edge format (from kg.neo4j_edges()):
    {
      "type": "CONTAINS" | "DEFINES" | "HAS_PORT" | "CONNECTS" | "DRIVES" | ... ,  # relationship type
      "source_uid": "...",    # OR "source": {"uid": "..."}
      "target_uid": "...",    # OR "target": {"uid": "..."}
      "uid": "stable-edge-id",  # optional; if missing we prefer eid, then derive one
      "eid": "stable-edge-id",  # optional compatibility key
      ... relationship properties ...
    }

Edges in Prometheus-style typed dicts ({"source": {...}, "target": {...}, "eid": ...})
are still accepted, but explicit "type"/"source_uid"/"target_uid" is preferred.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

from neo4j import GraphDatabase
from pathlib import Path

def _safe_ident(x: str) -> str:
    """
    Neo4j label/relationship type must be safe identifiers.
    Prevent Cypher injection and illegal characters.
    Allow: [A-Za-z0-9_]
    """
    if not x:
        raise ValueError("Empty identifier")
    for ch in x:
        if not (ch.isalnum() or ch == "_"):
            raise ValueError(f"Unsafe identifier: {x!r}")
    return x


def _is_primitive(v):
    return v is None or isinstance(v, (str, int, float, bool))

def _truncate(s: str, n: int = 2000) -> str:
    if s is None:
        return s
    if isinstance(s, str) and len(s) > n:
        return s[: n - 3] + "..."
    return s

def _coerce_value(v):
    """
    Neo4j property value must be primitive or list of primitives.
    dict/list-of-dict -> JSON string
    Path/other -> str
    """
    if _is_primitive(v):
        return _truncate(v) if isinstance(v, str) else v

    if isinstance(v, Path):
        return _truncate(str(v))

    if isinstance(v, bytes):
        return _truncate(v.decode("utf-8", errors="replace"))

    if isinstance(v, dict):
        # dict -> JSON string
        return _truncate(json.dumps(v, ensure_ascii=False, sort_keys=True))

    if isinstance(v, (list, tuple)):
        # list of primitives -> keep as list
        if all(_is_primitive(x) for x in v):
            return [(_truncate(x) if isinstance(x, str) else x) for x in v]
        # list contains dict/objects -> JSON string
        return _truncate(json.dumps(v, ensure_ascii=False))

    # fallback: stringify
    return _truncate(str(v))

def _coerce_props(d: dict) -> dict:
    return {str(k): _coerce_value(v) for k, v in d.items()}


def _sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def _truncate(v: str, n: int = 2000) -> str:
    # Neo4j property string is fine, but you don't want megabytes per edge.
    if v is None:
        return v
    if isinstance(v, str) and len(v) > n:
        return v[: n - 3] + "..."
    return v


def _safe_label(x: str) -> str:
    # Basic safeguard: allow alnum + underscore only. (No backticks injection.)
    if not x:
        raise ValueError("Empty label")
    for ch in x:
        if not (ch.isalnum() or ch == "_"):
            raise ValueError(f"Unsafe label: {x!r}")
    return x


def _safe_reltype(x: str) -> str:
    # Same safety constraint as label.
    return _safe_label(x)


def _as_uid(obj: Any) -> Optional[str]:
    if obj is None:
        return None
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        return obj.get("uid") or obj.get("id") or obj.get("node_uid")
    return getattr(obj, "uid", None)


@dataclass
class Neo4jConnection:
    uri: str
    user: str
    password: str

    def driver(self):
        return GraphDatabase.driver(self.uri, auth=(self.user, self.password))


class RTLNeo4jIngestor:
    """
    Bulk ingest nodes/edges into Neo4j.

    - Nodes are MERGE'd by (label, uid)
    - Edges are MERGE'd by (source.uid, reltype, target.uid, edge.uid)
    """

    def __init__(self, conn: Neo4jConnection, batch_size: int = 2000, logger=print):
        self.conn = conn
        self.batch_size = batch_size
        self.log = logger

    # -------------------------- schema --------------------------

    def ensure_schema(self, labels: Iterable[str]) -> None:
        """
        Create uniqueness constraints and a few common indexes.

        We only create constraints for the labels that actually appear in this repo,
        to keep schema small.
        """
        labels = sorted({_safe_label(l) for l in labels})
        if not labels:
            return
        with self.conn.driver() as driver:
            with driver.session() as session:
                # Node uniqueness by uid for each label
                for label in labels:
                    cypher = f"CREATE CONSTRAINT {label.lower()}_uid IF NOT EXISTS FOR (n:{label}) REQUIRE n.uid IS UNIQUE"
                    session.run(cypher)

                # Some helpful indexes (create only if label exists)
                # NOTE: These are optional; feel free to add/remove based on your query workload.
                index_specs = [
                    ("File", "relative_path", "file_relative_path"),
                    ("File", "sha1", "file_sha1"),
                    ("Module", "name", "module_name"),
                    ("Port", "name", "port_name"),
                    ("Signal", "name", "signal_name"),
                    ("Instance", "inst_name", "instance_inst_name"),
                    ("ContinuousAssign", "lhs_summary", "assign_lhs"),
                    ("AlwaysBlock", "block_kind", "always_kind"),
                ]
                for lbl, prop, idx_name in index_specs:
                    if lbl in labels:
                        cypher = f"CREATE INDEX {idx_name} IF NOT EXISTS FOR (n:{lbl}) ON (n.{prop})"
                        session.run(cypher)

    # -------------------------- normalize --------------------------

    def _normalize_node(self, n: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """
        Return (label, props) where props includes uid and everything else.
        """
        label = n.get("kind") or n.get("label") or n.get("labels")
        if isinstance(label, list):
            # If multiple labels, pick first as 'kind' and add others to props.labels
            label = label[0] if label else None
        if not label:
            raise ValueError(f"Node missing kind/label: {n}")
        label = _safe_label(str(label))

        uid = n.get("uid") or n.get("node_uid")
        if not uid:
            # Fallback: hash of stable-ish fields (not ideal, but better than crash)
            uid = _sha1(json.dumps(n, sort_keys=True, ensure_ascii=False))
        props = dict(n)
        props["uid"] = uid
        props["kind"] = label  # keep it as property too for debugging
        props = _coerce_props(props)

        # Truncate large strings defensively
        for k, v in list(props.items()):
            if isinstance(v, str):
                props[k] = _truncate(v)
        return label, props

    def _normalize_edge(self, e: Dict[str, Any]) -> Tuple[str, str, str, Dict[str, Any]]:
        """
        Return (reltype, source_uid, target_uid, props).
        """
        reltype = e.get("type") or e.get("rel_type") or e.get("edge_type")

        # Fallback 1: parse from Prometheus-style "eid": "...:REL:..."
        if not reltype:
            eid = e.get("eid") or e.get("id")
            if isinstance(eid, str):
                # common format: <src>:<REL>:<tgt>  (REL is usually ALLCAPS_WITH_UNDERSCORE)
                parts = eid.split(":")
                # pick the first ALLCAPS token that looks like a rel
                for p in parts:
                    if p and p.replace("_", "").isalnum() and p.upper() == p and any(c.isalpha() for c in p):
                        reltype = p
                        break

        # Fallback 2: sometimes Prometheus uses "label" or "kind" for reltype
        if not reltype:
            reltype = e.get("label") or e.get("kind") or e.get("rel")

        if not reltype:
            raise ValueError(f"Edge missing type/rel_type (and cannot infer from eid): {e}")

        reltype = _safe_ident(str(reltype))


        s_uid = e.get("source_uid") or _as_uid(e.get("source"))
        t_uid = e.get("target_uid") or _as_uid(e.get("target"))
        if not s_uid or not t_uid:
            raise ValueError(f"Edge missing endpoints: {e}")

        props = dict(e)
        props.pop("source", None)
        props.pop("target", None)
        props["source_uid"] = s_uid
        props["target_uid"] = t_uid

        # Relationship uid for MERGE uniqueness (per rel)
        r_uid = props.get("uid") or props.get("eid") or props.get("rel_uid")
        if not r_uid:
            # Use a stable hash of endpoints + reltype + a subset of properties that
            # typically disambiguate multi-edges (e.g., port_name/order for CONNECTS).
            key_fields = []
            for k in ("port_name", "order", "k", "cnt", "lhs_summary", "block_kind", "include_raw", "gen_path"):
                if k in props and props[k] is not None:
                    key_fields.append(f"{k}={props[k]}")
            key = "|".join([s_uid, reltype, t_uid] + key_fields)
            r_uid = _sha1(key)
        props["uid"] = r_uid
        props = _coerce_props(props)

        for k, v in list(props.items()):
            if isinstance(v, str):
                props[k] = _truncate(v)
        return reltype, s_uid, t_uid, props

    # -------------------------- ingestion --------------------------

    def ingest(
        self,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        mode: str = "delta",
        repo_uid: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Ingest nodes/edges.

        mode:
          - "full": delete all nodes that match repo_uid partition, then ingest
          - "delta": MERGE only (upsert)
        """
        norm_nodes: List[Tuple[str, Dict[str, Any]]] = [self._normalize_node(n) for n in nodes]
        labels = sorted({lbl for lbl, _ in norm_nodes})
        self.ensure_schema(labels)

        with self.conn.driver() as driver:
            with driver.session() as session:
                if mode == "full":
                    if not repo_uid:
                        # Try to infer repo_uid from a Repo node if present.
                        for _, p in norm_nodes:
                            if p.get("kind") == "Repo" or p.get("kind") == "ROOT" or p.get("kind") == "Root":
                                repo_uid = p.get("uid") or p.get("repo_uid")
                                break
                    if not repo_uid:
                        raise ValueError("mode=full requires repo_uid (or a Repo node to infer it).")
                    self.log(f"[neo4j] FULL mode: deleting partition repo_uid={repo_uid}")
                    session.run("MATCH (n {repo_uid:$repo_uid}) DETACH DELETE n", repo_uid=repo_uid)
                    # Also try Repo by uid
                    session.run("MATCH (r:Repo {uid:$repo_uid}) DETACH DELETE r", repo_uid=repo_uid)

                self.log(f"[neo4j] ingest nodes: {len(norm_nodes)}")
                node_stats = self._ingest_nodes(session, norm_nodes)
                self.log(f"[neo4j] ingest edges: {len(edges)}")
                norm_edges = [self._normalize_edge(e) for e in edges]
                edge_stats = self._ingest_edges(session, norm_edges)
                if edges and edge_stats.get("relationships_touched", 0) == 0:
                    self.log(
                        "[neo4j] WARNING: edge input was non-empty but no relationships were touched; "
                        "check edge endpoints and relationship type schema."
                    )
                return {
                    "nodes_input": len(nodes),
                    "edges_input": len(edges),
                    **node_stats,
                    **edge_stats,
                }

    def _ingest_nodes(self, session, norm_nodes: List[Tuple[str, Dict[str, Any]]]) -> Dict[str, Any]:
        # Group by label, run one query per label (labels cannot be parameterized)
        by_label: Dict[str, List[Dict[str, Any]]] = {}
        for label, props in norm_nodes:
            by_label.setdefault(label, []).append(props)

        nodes_touched = 0
        for label, rows in by_label.items():
            cypher = f"""
UNWIND $rows AS row
MERGE (n:{label} {{uid: row.uid}})
SET n += row
RETURN count(n) AS touched
"""
            for i in range(0, len(rows), self.batch_size):
                batch = rows[i : i + self.batch_size]
                record = session.run(cypher, rows=batch).single()
                nodes_touched += int(record["touched"] if record else 0)
        return {"nodes_touched": nodes_touched}

    def _ingest_edges(self, session, norm_edges: List[Tuple[str, str, str, Dict[str, Any]]]) -> Dict[str, Any]:
        # Group by relationship type
        by_rel: Dict[str, List[Dict[str, Any]]] = {}
        for reltype, s_uid, t_uid, props in norm_edges:
            by_rel.setdefault(reltype, []).append(props)

        relationships_touched = 0
        reltype_counts: Dict[str, int] = {}
        for reltype, rows in by_rel.items():
            cypher = f"""
UNWIND $rows AS row
MATCH (s {{uid: row.source_uid}})
MATCH (t {{uid: row.target_uid}})
MERGE (s)-[r:{reltype} {{uid: row.uid}}]->(t)
SET r += row
RETURN count(r) AS touched
"""
            for i in range(0, len(rows), self.batch_size):
                batch = rows[i : i + self.batch_size]
                record = session.run(cypher, rows=batch).single()
                touched = int(record["touched"] if record else 0)
                relationships_touched += touched
                reltype_counts[reltype] = reltype_counts.get(reltype, 0) + touched
        return {
            "relationships_touched": relationships_touched,
            "relationship_types_touched": reltype_counts,
        }
