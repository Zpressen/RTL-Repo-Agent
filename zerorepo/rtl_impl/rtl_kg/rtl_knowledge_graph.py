"""
RTL KnowledgeGraph: traverse a repository, build the directory/file structure and
attach RTL semantic subgraphs produced by RTLFileGraphBuilder.

This mirrors Prometheus' KnowledgeGraph logic:
- Walk directory tree, create nodes for dirs/files, add HAS_FILE edges
- For supported code files, parse and attach AST/text subgraphs fileciteturn3file1

For RTL-agent, we instead:
- Create Repo + File nodes connected by CONTAINS edges
- For each RTL file, add semantic nodes: Module/Port/Signal/Param/Always/Assign/Instance/Expr
- Add edges: DEFINES/HAS/INSTANTIATES/CONNECTS/DRIVES
- Post-pass resolution:
  * OF_MODULE: Instance -> Module (by module_ref name)
  * INCLUDES: File -> File (simple `include resolution; optional and best-effort)
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import re
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .graph_types_rtl import (
    FileNode,
    KnowledgeGraphEdge,
    KnowledgeGraphEdgeType,
    KnowledgeGraphNode,
    ModuleNode,
    PackageNode,
    RepoNode,
    make_eid,
    make_uid,
)

from .rtl_file_graph_builder import RTLFileGraphBuilder


def _sha1_file(p: Path) -> str:
    return hashlib.sha1(p.read_bytes()).hexdigest()


def compute_repo_uid(repo_root: Path) -> str:
    """Prefer git commit hash if available; fallback to absolute path hash."""
    repo_root = repo_root.resolve()
    git_dir = repo_root / ".git"
    if git_dir.exists():
        try:
            out = subprocess.check_output(["git", "-C", str(repo_root), "rev-parse", "HEAD"], stderr=subprocess.DEVNULL)
            commit = out.decode().strip()
            return f"{repo_root.name}@{commit[:12]}"
        except Exception:
            pass
    # fallback: stable-ish hash of absolute path
    return f"{repo_root.name}@{hashlib.sha1(str(repo_root).encode()).hexdigest()[:12]}"


def should_ignore(path: Path) -> bool:
    name = path.name
    if name in {".git", ".hg", ".svn", "__pycache__", ".venv", "venv", "build", "dist", ".idea", ".vscode"}:
        return True
    return False


@dataclass
class KnowledgeGraphRTL:
    repo_root: Path
    repo_uid: str
    nodes: List[KnowledgeGraphNode]
    edges: List[KnowledgeGraphEdge]

    # quick index
    uid2node: Dict[str, KnowledgeGraphNode]

    @classmethod
    def build(cls, repo_root: Path) -> "KnowledgeGraphRTL":
        repo_root = repo_root.resolve()
        repo_uid = compute_repo_uid(repo_root)

        nodes: List[KnowledgeGraphNode] = []
        edges: List[KnowledgeGraphEdge] = []
        uid2node: Dict[str, KnowledgeGraphNode] = {}

        # Repo node
        repo_node = KnowledgeGraphNode(
            uid=make_uid(repo_uid, "repo", repo_root.name),
            repo_uid=repo_uid,
            node=RepoNode(name=repo_root.name, attrs={"abs_path": str(repo_root)}),
        )
        nodes.append(repo_node)
        uid2node[repo_node.uid] = repo_node

        # Root dir File node
        root_file = KnowledgeGraphNode(
            uid=make_uid(repo_uid, "file", "."),
            repo_uid=repo_uid,
            node=FileNode(path=".", name=repo_root.name, h=None, attrs={"is_dir": True}),
        )
        nodes.append(root_file)
        uid2node[root_file.uid] = root_file
        edges.append(
            KnowledgeGraphEdge(
                source=repo_node,
                target=root_file,
                type=KnowledgeGraphEdgeType.contains,
                props={"eid": make_eid(repo_node.uid, "CONTAINS", root_file.uid), "order": 0},
            )
        )

        builder = RTLFileGraphBuilder(repo_uid=repo_uid, repo_root=repo_root)
        module_definition_paths: Dict[str, str] = {}

        # DFS traversal
        stack = deque([(repo_root, root_file)])
        order_counter: Dict[str, int] = defaultdict(int)

        while stack:
            abs_path, parent_file_node = stack.pop()

            if should_ignore(abs_path):
                continue

            if abs_path.is_dir():
                # enumerate children
                try:
                    children = sorted(list(abs_path.iterdir()), key=lambda p: p.name)
                except PermissionError:
                    continue
                for child in reversed(children):
                    if not child.exists():
                        continue
                    if should_ignore(child):
                        continue

                    rel = child.relative_to(repo_root).as_posix()
                    uid = make_uid(repo_uid, "file", rel)
                    fn = KnowledgeGraphNode(
                        uid=uid,
                        repo_uid=repo_uid,
                        node=FileNode(
                            path=rel,
                            name=child.name,
                            h=_sha1_file(child) if child.is_file() else None,
                            attrs={"is_dir": child.is_dir(), "suffix": child.suffix.lower()},
                        ),
                    )
                    nodes.append(fn)
                    uid2node[uid] = fn
                    order = order_counter[parent_file_node.uid]
                    order_counter[parent_file_node.uid] += 1
                    edges.append(
                        KnowledgeGraphEdge(
                            source=parent_file_node,
                            target=fn,
                            type=KnowledgeGraphEdgeType.contains,
                            props={"eid": make_eid(parent_file_node.uid, "CONTAINS", uid), "order": order},
                        )
                    )
                    stack.append((child, fn))
            else:
                # only parse rtl files
                if not builder.supports_file(abs_path):
                    continue

                # Per-file RTL subgraph
                try:
                    res = builder.build_file_graph(parent_file_node, abs_path)
                except Exception as e:
                    # keep graph building robust; skip bad file but continue
                    continue
                for n in res.nodes:
                    if isinstance(n.node, ModuleNode):
                        module_name = str(getattr(n.node, "name", "") or "")
                        module_path = str(getattr(n.node, "path", "") or "")
                        previous_path = module_definition_paths.get(module_name)
                        if previous_path is not None and previous_path != module_path:
                            raise ValueError(
                                "Duplicate RTL Module definition in one repo partition: "
                                f"{module_name!r} appears in {previous_path!r} and {module_path!r}"
                            )
                        module_definition_paths[module_name] = module_path
                    if n.uid not in uid2node:
                        nodes.append(n)
                        uid2node[n.uid] = n
                edges.extend(res.edges)

        kg = cls(repo_root=repo_root, repo_uid=repo_uid, nodes=nodes, edges=edges, uid2node=uid2node)

        # Post passes
        kg._resolve_of_module()
        kg._resolve_imports()
        kg._resolve_includes()

        return kg

    def _resolve_imports(self) -> None:
        """Resolve IMPORTS edges created as Package 'ref' placeholders to real Package nodes (by name).

        The file graph builder emits IMPORTS edges from Module/Package to a placeholder PackageNode:
          PackageNode(name=<pkg>, path='', sl=0, el=0, attrs={'ref': True})

        Here we:
          1) build mapping: package name -> list of real Package nodes (attrs.ref != True)
          2) rebuild IMPORTS edges, replacing placeholder targets with the best matched real package
          3) if no real package found, keep the placeholder (so edge is not lost)
        """
        name2pkgs: Dict[str, List[KnowledgeGraphNode]] = defaultdict(list)
        for n in self.nodes:
            if n.kind().value != "Package":
                continue
            attrs = getattr(n.node, "attrs", None) or {}
            if attrs.get("ref"):
                continue
            pname = getattr(n.node, "name", None)
            if pname:
                name2pkgs[pname].append(n)

        new_edges: List[KnowledgeGraphEdge] = []
        for e in self.edges:
            if e.type != KnowledgeGraphEdgeType.imports:
                new_edges.append(e)
                continue
            tgt = e.target
            if tgt.kind().value != "Package":
                new_edges.append(e)
                continue
            tattrs = getattr(tgt.node, "attrs", None) or {}
            if not tattrs.get("ref") and getattr(tgt.node, "sl", None) not in (0, None):
                # already real
                new_edges.append(e)
                continue

            pkg_name = getattr(tgt.node, "name", None)
            if not pkg_name:
                new_edges.append(e)
                continue

            cands = name2pkgs.get(pkg_name, [])
            if not cands:
                new_edges.append(e)  # keep placeholder
                continue

            chosen = cands[0]
            src_path = getattr(e.source.node, "path", "")
            for p in cands:
                if getattr(p.node, "path", "") == src_path:
                    chosen = p
                    break

            # rebuild edge with new target (KnowledgeGraphEdge is frozen)
            props = dict(e.props or {})
            props.setdefault("eid", make_eid(e.source.uid, "IMPORTS", chosen.uid))
            new_edges.append(
                KnowledgeGraphEdge(
                    source=e.source,
                    target=chosen,
                    type=KnowledgeGraphEdgeType.imports,
                    props=props,
                )
            )

        self.edges = new_edges  # type: ignore[assignment]

    def _resolve_of_module(self) -> None:
        """Create OF_MODULE edges by matching Instance.attrs['module_ref'] to Module.name."""
        # build module name -> module node mapping (may have collisions)
        name2mods: Dict[str, List[KnowledgeGraphNode]] = defaultdict(list)
        for n in self.nodes:
            if n.kind().value == "Module":
                # type: ignore[attr-defined]
                name2mods[getattr(n.node, "name")].append(n)

        # instances
        for n in self.nodes:
            if n.kind().value != "Instance":
                continue
            attrs = getattr(n.node, "attrs", None) or {}
            modref = attrs.get("module_ref")
            if not modref:
                continue
            cands = name2mods.get(modref, [])
            if not cands:
                continue

            # If multiple, choose same-path first; else first
            chosen = cands[0]
            inst_path = getattr(n.node, "path", "")
            for m in cands:
                if getattr(m.node, "path", "") == inst_path:
                    chosen = m
                    break

            self.edges.append(
                KnowledgeGraphEdge(
                    source=n,
                    target=chosen,
                    type=KnowledgeGraphEdgeType.of_module,
                    props={"eid": make_eid(n.uid, "OF_MODULE", chosen.uid), "conf": 1.0},
                )
            )

    def _resolve_includes(self) -> None:
        """
        Best-effort `include parsing:
          - scan file text for lines like: `include "foo.vh"
          - resolve relative to including file directory
          - create INCLUDES edge File->File with ok flag
        """
        for n in list(self.nodes):
            if n.kind().value != "File":
                continue
            attrs = getattr(n.node, "attrs", None) or {}
            if attrs.get("is_dir"):
                continue

            rel = getattr(n.node, "path", None)
            if not rel:
                continue
            abs_p = (self.repo_root / rel).resolve()
            if not abs_p.exists():
                continue
            # only scan RTL-ish headers or sources
            if abs_p.suffix.lower() not in {".v", ".vh", ".sv", ".svh"}:
                continue
            try:
                txt = abs_p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            for m in re.finditer(r"(?m)^\s*`include\s+\"([^\"]+)\"\s*$", txt):
                inc_raw = m.group(1)
                inc_abs = (abs_p.parent / inc_raw).resolve()
                ok = False
                tgt_uid = None
                if inc_abs.exists():
                    try:
                        inc_rel = inc_abs.relative_to(self.repo_root).as_posix()
                        tgt_uid = make_uid(self.repo_uid, "file", inc_rel)
                        ok = tgt_uid in self.uid2node
                    except Exception:
                        ok = False

                if tgt_uid and ok:
                    tgt = self.uid2node[tgt_uid]
                else:
                    # create a "virtual" File node (not in tree) to keep edge; optional
                    v_rel = inc_raw.replace("\\", "/")
                    v_uid = make_uid(self.repo_uid, "file", v_rel)
                    if v_uid not in self.uid2node:
                        v_node = KnowledgeGraphNode(
                            uid=v_uid,
                            repo_uid=self.repo_uid,
                            node=FileNode(path=v_rel, name=Path(v_rel).name, h=None, attrs={"virtual": True}),
                        )
                        self.nodes.append(v_node)
                        self.uid2node[v_uid] = v_node
                    tgt = self.uid2node[v_uid]

                self.edges.append(
                    KnowledgeGraphEdge(
                        source=n,
                        target=tgt,
                        type=KnowledgeGraphEdgeType.includes,
                        props={"eid": make_eid(n.uid, "INCLUDES", tgt.uid, inc_raw), "raw": inc_raw, "ok": ok},
                    )
                )

    # ---- helpers for Neo4j ----
    def neo4j_nodes(self) -> List[dict]:
        return [n.to_neo4j_node() for n in self.nodes]

    def neo4j_edges(self) -> List[dict]:
        return [e.to_neo4j_edge() for e in self.edges]
