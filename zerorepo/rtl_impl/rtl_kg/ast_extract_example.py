#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
AST extractor for RTL repositories using tree-sitter.

Outputs:
- out_dir/ast/<file>.ast.json   : compact AST json (bounded depth/children)
- out_dir/index.json            : repository-level entity index with spans

Usage:
  python ast_extract_example.py --repo /home/mokita/Riscy-SoC-master --out ./ast_out

Notes:
- Preferred: pip install tree_sitter tree_sitter_languages
- Fallback: build a language .so from tree-sitter grammar (see load_language()).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from tree_sitter import Language, Parser


# -------------------------
# Language loading
# -------------------------
def load_language() -> Language:
    """
    Try to load SystemVerilog/Verilog language in the easiest way.

      Build a language shared library from a tree-sitter grammar repository.
      You can compile e.g. tree-sitter-verilog (or systemverilog) into a .so:
        Language.build_library('build/lang.so', ['path/to/tree-sitter-verilog'])
      Then load with Language('build/lang.so', 'verilog')
    """
    here = Path(__file__).resolve().parent
    build_dir = here / "build"
    build_dir.mkdir(parents=True, exist_ok=True)

    so_path = build_dir / "rtl_langs.so"
    grammar_dir = here / "third_party" / "tree-sitter-verilog"

    if not grammar_dir.exists():
        raise RuntimeError(f"Missing grammar repo: {grammar_dir}")

    if not so_path.exists():
        Language.build_library(str(so_path), [str(grammar_dir)])

    # 注意：语言名通常就是 "verilog"
    return Language(str(so_path), "verilog")


# -------------------------
# Utilities
# -------------------------
RTL_EXTS = {".v", ".sv", ".vh", ".svh"}


def sha1_bytes(b: bytes) -> str:
    return hashlib.sha1(b).hexdigest()


def relpath(path: Path, repo: Path) -> str:
    return path.resolve().as_posix().replace(repo.resolve().as_posix().replace("\\", "/"), "").lstrip("/")


def read_bytes(path: Path) -> bytes:
    return path.read_bytes()


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


# -------------------------
# AST JSON (compact)
# -------------------------
def node_text(src: bytes, node: Node, max_len: int = 140) -> str:
    """Get a short snippet of the node text (safe for JSON)."""
    try:
        t = src[node.start_byte : node.end_byte].decode("utf-8", errors="replace")
    except Exception:
        return ""
    t = " ".join(t.split())
    if len(t) > max_len:
        t = t[: max_len - 3] + "..."
    return t


def ast_to_compact_json(
    src: bytes,
    node: Node,
    *,
    depth: int = 0,
    max_depth: int = 6,
    max_children: int = 80,
) -> Dict[str, Any]:
    """
    Convert tree-sitter Node to a compact JSON dict.
    - Bounded depth to avoid huge dumps
    - Bounded children per node
    """
    obj: Dict[str, Any] = {
        "type": node.type,
        "start": [node.start_point[0] + 1, node.start_point[1] + 1],  # 1-based
        "end": [node.end_point[0] + 1, node.end_point[1] + 1],
        "start_byte": node.start_byte,
        "end_byte": node.end_byte,
    }

    # For named nodes, keep a short snippet (helps debugging)
    if node.is_named:
        obj["text"] = node_text(src, node)

    if depth >= max_depth:
        obj["children_truncated"] = True
        return obj

    children = [c for c in node.children if c.is_named]
    if len(children) > max_children:
        obj["children_truncated"] = True
        children = children[:max_children]

    obj["children"] = [ast_to_compact_json(src, c, depth=depth + 1, max_depth=max_depth, max_children=max_children) for c in children]
    return obj


# -------------------------
# Entity extraction (Prometheus-like "index")
# -------------------------
@dataclass
class Span:
    path: str
    sl: int
    sc: int
    el: int
    ec: int

    @staticmethod
    def from_node(path: str, n: Node) -> "Span":
        return Span(
            path=path,
            sl=n.start_point[0] + 1,
            sc=n.start_point[1] + 1,
            el=n.end_point[0] + 1,
            ec=n.end_point[1] + 1,
        )


@dataclass
class ModuleDecl:
    name: str
    span: Span


@dataclass
class InstanceDecl:
    # parent module is filled by caller (context)
    inst_name: Optional[str]
    module_ref: Optional[str]
    span: Span


@dataclass
class AssignDecl:
    lhs: str
    rhs: str
    span: Span


@dataclass
class AlwaysDecl:
    kind: str  # ff/comb/unknown (heuristic)
    sens: str
    span: Span


@dataclass
class SignalDecl:
    name: str
    decl_kind: str  # wire/reg/logic/unknown
    span: Span


def _first_named_child(node: Node, t: str) -> Optional[Node]:
    for c in node.children:
        if c.is_named and c.type == t:
            return c
    return None


def _collect_identifiers(src: bytes, node: Node) -> List[str]:
    """
    Collect identifier-like nodes under `node`.
    Grammars differ; we do a robust walk.
    """
    out: List[str] = []

    stack = [node]
    while stack:
        cur = stack.pop()
        if cur.type in ("identifier", "simple_identifier"):
            out.append(src[cur.start_byte : cur.end_byte].decode("utf-8", errors="replace"))
        for ch in reversed(cur.children):
            if ch.is_named:
                stack.append(ch)
    return out


def _extract_module_name(src: bytes, mod_node: Node) -> Optional[str]:
    # Most verilog grammars have a direct child identifier for module name.
    for c in mod_node.children:
        if c.is_named and c.type in ("identifier", "simple_identifier"):
            return src[c.start_byte : c.end_byte].decode("utf-8", errors="replace")
    # fallback: deep search first identifier
    ids = _collect_identifiers(src, mod_node)
    return ids[0] if ids else None


def _extract_assign_lhs_rhs(src: bytes, assign_node: Node) -> Tuple[str, str]:
    """
    Extract lhs/rhs from continuous assign.
    This is heuristic and grammar-dependent, but works for many tree-sitter verilog grammars.
    """
    # Common patterns: assign_statement -> (assignment) or has children representing lhs/rhs.
    # We'll just take the first two meaningful expression-ish children by scanning.
    exprs: List[Node] = []
    for c in assign_node.children:
        if not c.is_named:
            continue
        # filter out keywords nodes etc by type name
        if c.type in ("assignment", "blocking_assignment", "nonblocking_assignment", "continuous_assignment"):
            exprs.append(c)
        elif "expression" in c.type or "lvalue" in c.type or "rvalue" in c.type or c.type in ("identifier", "concatenation", "bit_select", "part_select"):
            exprs.append(c)

    # If we got an "assignment" wrapper, try to split inside it
    if exprs and exprs[0].type in ("assignment", "continuous_assignment"):
        a = exprs[0]
        parts = [ch for ch in a.children if ch.is_named]
        if len(parts) >= 2:
            lhs = node_text(src, parts[0], max_len=120)
            rhs = node_text(src, parts[-1], max_len=120)
            return lhs, rhs

    # Fallback: pick first and last named child snippets
    named = [c for c in assign_node.children if c.is_named]
    if len(named) >= 2:
        return node_text(src, named[0], 120), node_text(src, named[-1], 120)
    return "", ""


def _extract_always_sens(src: bytes, always_node: Node) -> str:
    # heuristic: find the first named child that looks like an event control / sensitivity
    for c in always_node.children:
        if c.is_named and ("event" in c.type or "event_control" in c.type or "sensitivity" in c.type):
            return node_text(src, c, max_len=120)
    # fallback: take a small prefix snippet
    return node_text(src, always_node, max_len=120)


def _classify_always_kind(sens: str) -> str:
    s = sens.replace(" ", "").lower()
    if "posedge" in s or "negedge" in s:
        return "ff"
    if "@*" in s or "@(*)" in s:
        return "comb"
    return "unknown"


def walk_entities_in_file(src: bytes, root: Node, path_rel: str) -> Dict[str, Any]:
    """
    Extract a repository-friendly entity index:
      modules, instances, assigns, always blocks, signals (decl-level)
    Note: exact node type names vary with grammar, so we use a robust scan.
    """
    modules: List[ModuleDecl] = []
    instances: List[InstanceDecl] = []
    assigns: List[AssignDecl] = []
    always_blocks: List[AlwaysDecl] = []
    signals: List[SignalDecl] = []

    # A simple stack traversal
    stack: List[Node] = [root]
    current_module_name: Optional[str] = None

    while stack:
        n = stack.pop()

        # Detect module declaration nodes
        if n.is_named and n.type in ("module_declaration", "module_declaration_statement", "module"):
            mn = _extract_module_name(src, n)
            if mn:
                current_module_name = mn
                modules.append(ModuleDecl(name=mn, span=Span.from_node(path_rel, n)))

        # Detect continuous assign
        if n.is_named and n.type in ("continuous_assign", "continuous_assignment", "assign_statement"):
            lhs, rhs = _extract_assign_lhs_rhs(src, n)
            assigns.append(AssignDecl(lhs=lhs, rhs=rhs, span=Span.from_node(path_rel, n)))

        # Detect always blocks
        if n.is_named and n.type in ("always_construct", "always_ff_construct", "always_comb_construct", "always_latch_construct", "always"):
            sens = _extract_always_sens(src, n)
            kind = "unknown"
            # Some grammars encode always_ff/always_comb as specific node types.
            if "always_ff" in n.type:
                kind = "ff"
            elif "always_comb" in n.type or "always_latch" in n.type:
                kind = "comb" if "comb" in n.type else "unknown"
            else:
                kind = _classify_always_kind(sens)
            always_blocks.append(AlwaysDecl(kind=kind, sens=sens, span=Span.from_node(path_rel, n)))

        # Detect instance / module instantiation
        # Grammars vary: "module_instantiation" / "module_instance" / "instantiation"
        if n.is_named and n.type in ("module_instantiation", "instantiation", "module_instance", "hierarchical_instance"):
            # Heuristic: first identifier is module_ref, second identifier is inst_name
            ids = _collect_identifiers(src, n)
            module_ref = ids[0] if len(ids) >= 1 else None
            inst_name = ids[1] if len(ids) >= 2 else None
            instances.append(InstanceDecl(inst_name=inst_name, module_ref=module_ref, span=Span.from_node(path_rel, n)))

        # Detect signal declarations (decl-level)
        # Grammar-dependent; we use heuristic on node types containing "net" or "data_declaration"
        if n.is_named and n.type in ("net_declaration", "data_declaration", "variable_declaration", "reg_declaration", "logic_declaration"):
            # Collect identifiers as candidates; filter out keywords by a rough rule
            ids = _collect_identifiers(src, n)
            # Determine decl_kind
            t = n.type
            decl_kind = "unknown"
            if "net" in t:
                decl_kind = "wire"
            elif "reg" in t:
                decl_kind = "reg"
            elif "logic" in t:
                decl_kind = "logic"
            elif "variable" in t:
                decl_kind = "logic"  # common SV default
            for name in ids:
                # Very rough guard
                if name and name not in ("input", "output", "wire", "reg", "logic", "signed", "unsigned"):
                    signals.append(SignalDecl(name=name, decl_kind=decl_kind, span=Span.from_node(path_rel, n)))

        # Continue traversal
        for ch in reversed(n.children):
            if ch.is_named:
                stack.append(ch)

    # Convert to json-serializable dict
    return {
        "path": path_rel,
        "sha1": sha1_bytes(src),
        "modules": [asdict(m) for m in modules],
        "instances": [asdict(i) for i in instances],
        "assigns": [asdict(a) for a in assigns],
        "always": [asdict(ab) for ab in always_blocks],
        "signals": [asdict(s) for s in signals],
    }


# -------------------------
# Main entry
# -------------------------
def iter_rtl_files(repo: Path) -> List[Path]:
    out: List[Path] = []
    for p in repo.rglob("*"):
        if p.is_file() and p.suffix.lower() in RTL_EXTS:
            out.append(p)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, default="/home/mokita/Riscy-SoC-master", help="Path to RTL repository root")
    ap.add_argument("--out", required=True, help="Output directory")
    ap.add_argument("--max-depth", type=int, default=6, help="AST JSON max depth")
    ap.add_argument("--max-children", type=int, default=80, help="AST JSON max children per node")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    out_dir = Path(args.out).resolve()
    ast_dir = out_dir / "ast"
    ensure_dir(ast_dir)

    language = load_language()
    parser = Parser()
    parser.set_language(language)

    files = iter_rtl_files(repo)
    index: Dict[str, Any] = {"repo": repo.as_posix(), "files": []}

    for fp in files:
        src = read_bytes(fp)
        tree = parser.parse(src)
        root = tree.root_node

        path_rel = relpath(fp, repo)
        # 1) write compact AST json
        ast_json = ast_to_compact_json(src, root, max_depth=args.max_depth, max_children=args.max_children)

        out_ast_path = ast_dir / (path_rel.replace("/", "__") + ".ast.json")
        ensure_dir(out_ast_path.parent)
        out_ast_path.write_text(json.dumps(ast_json, ensure_ascii=False, indent=2), encoding="utf-8")

        # 2) entity index
        ent = walk_entities_in_file(src, root, path_rel)
        index["files"].append(ent)

    (out_dir / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] Parsed {len(files)} RTL files. Output: {out_dir}")


if __name__ == "__main__":
    main()
