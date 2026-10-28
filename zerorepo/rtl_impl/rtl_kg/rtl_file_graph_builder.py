"""
RTL FileGraphBuilder: parse a single RTL source file (Verilog/SystemVerilog) with tree-sitter
and build a *lean* repository knowledge subgraph according to graph_types_rtl.py.

This is inspired by Prometheus' FileGraphBuilder + KnowledgeGraph pipeline:
- Prometheus builds a directory/file tree, then for each code file parses with tree-sitter and
  stores AST nodes connected by HAS_AST/PARENT_OF edges. fileciteturn3file0 fileciteturn3file1
- For RTL-agent, we avoid statement-level AST explosion and instead materialize
  Repo/File/Module/Instance/Port/Signal/Param/Always/Assign (+ Expr for CONNECTS targets)
  and edges: CONTAINS/DEFINES/HAS/INSTANTIATES/OF_MODULE/CONNECTS/DRIVES (LHS-only).

This module focuses on **per-file parsing + extraction**.
Cross-file resolution (OF_MODULE, INCLUDES path resolution) is done in KnowledgeGraphRTL.
"""

from __future__ import annotations

import ctypes
import hashlib
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

from tree_sitter import Language, Parser

from .graph_types_rtl import (
    AlwaysBlockNode,
    AssignNode,
    ExprNode,
    FileNode,
    FuncNode,
    InstanceNode,
    KnowledgeGraphEdge,
    KnowledgeGraphEdgeType,
    KnowledgeGraphNode,
    ModuleNode,
    PackageNode,
    GenerateNode,
    NodeKind,
    ParamNode,
    PortNode,
    SignalNode,
    canonical_module_uid,
    make_eid,
    make_uid,
)

###############################################################################
#                            Tree-sitter loader                                #
###############################################################################


class VerilogTreeSitter:
    """Load/build tree-sitter Verilog language and expose a Parser().

    By default it expects grammar repo at: <this_dir>/third_party/tree-sitter-verilog
    And builds library at: <this_dir>/build/rtl_langs.so

    You can override via env:
      - RTL_TS_LANG_SO: path to an existing .so/.dylib/.dll that exports tree_sitter_verilog
      - RTL_TS_GRAMMAR_DIR: path to tree-sitter-verilog grammar repo
      - RTL_TS_LANG_NAME: language name inside the .so (default: verilog)
    """

    _parser: Optional[Parser] = None

    @classmethod
    def get_parser(cls) -> Parser:
        if cls._parser is not None:
            return cls._parser

        here = Path(__file__).resolve().parent
        build_dir = Path(os.environ.get('RTL_TS_CACHE_DIR', str(here / 'build')))

        so_path = Path(os.environ.get("RTL_TS_LANG_SO", str(build_dir / "rtl_langs.so")))
        grammar_dir = Path(
            os.environ.get("RTL_TS_GRAMMAR_DIR", str(here / "third_party" / "tree-sitter-verilog"))
        )
        lang_name = os.environ.get("RTL_TS_LANG_NAME", "verilog")

        if not so_path.exists():
            so_path.parent.mkdir(parents=True,exist_ok=True)
            if not grammar_dir.exists():
                raise RuntimeError(
                    f"Missing grammar repo at {grammar_dir}\n"
                    f"Clone it with:\n"
                    f"  git clone https://github.com/tree-sitter/tree-sitter-verilog.git {grammar_dir}\n"
                    f"Or set RTL_TS_GRAMMAR_DIR / RTL_TS_LANG_SO."
                )
            if hasattr(Language,'build_library'):
                Language.build_library(str(so_path), [str(grammar_dir)])
            else:
                # New bindings no longer ship a compiler helper. Build the
                # pinned grammar with the target compiler, never copy host .so.
                import tempfile
                sources=[grammar_dir/'src/parser.c']
                scanner=grammar_dir/'src/scanner.c'
                if scanner.is_file():sources.append(scanner)
                fd,tmp=tempfile.mkstemp(prefix='.rtl-lang-',suffix='.so',dir=so_path.parent)
                os.close(fd)
                try:
                    subprocess.run([os.environ.get('CC','cc'),'-shared','-fPIC','-O2',
                                    '-I',str(grammar_dir/'src'),*map(str,sources),'-o',tmp],check=True)
                    os.replace(tmp,so_path)
                finally:
                    if os.path.exists(tmp):os.unlink(tmp)

        try:
            language = Language(str(so_path), lang_name)
        except TypeError:
            lib = ctypes.CDLL(str(so_path))
            symbol = f"tree_sitter_{lang_name}"
            if not hasattr(lib, symbol):
                raise RuntimeError(f"Language symbol {symbol} not found in {so_path}")
            lang_fn = getattr(lib, symbol)
            lang_fn.restype = ctypes.c_void_p
            language = Language(lang_fn())
        parser = Parser()
        if hasattr(parser, "set_language"):
            parser.set_language(language)
        else:
            parser.language = language
        cls._parser = parser
        return parser


###############################################################################
#                          Lightweight extraction utils                         #
###############################################################################


_RE_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_$]*")
_RE_ESCAPED = re.compile(r"\\[^\s]+")  # Verilog escaped identifier: \foo.bar


_VERILOG_KEYWORDS = {
    # core
    "module",
    "endmodule",
    "input",
    "output",
    "inout",
    "wire",
    "reg",
    "logic",
    "tri",
    "wand",
    "wor",
    "assign",
    "always",
    "always_ff",
    "always_comb",
    "always_latch",
    "begin",
    "end",
    "if",
    "else",
    "case",
    "endcase",
    "for",
    "while",
    "repeat",
    "generate",
    "endgenerate",
    "genvar",
    "parameter",
    "localparam",
    "function",
    "endfunction",
    "task",
    "endtask",
    "package",
    "endpackage",
    "import",
    "export",
    "typedef",
    "struct",
    "union",
    "enum",
    "signed",
    "unsigned",
    "posedge",
    "negedge",
    "or",
    "and",
    "not",
    # literals / builtins
    "default",
    "return",
}


def sha1_bytes(b: bytes) -> str:
    return hashlib.sha1(b).hexdigest()


def short_hash(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8", errors="ignore")).hexdigest()[:12]


def strip_comments_keep_len(text: str) -> str:
    """
    Remove // and /* */ comments, preserving length with spaces/newlines
    so span line numbers remain roughly aligned.
    """
    # block comments
    def repl_block(m: re.Match) -> str:
        t = m.group(0)
        # keep newlines
        return "".join("\n" if c == "\n" else " " for c in t)

    text = re.sub(r"/\*.*?\*/", repl_block, text, flags=re.S)
    # line comments
    text = re.sub(r"//[^\n]*", lambda m: " " * (m.end() - m.start()), text)
    return text


def split_top_level_commas(s: str) -> List[str]:
    """Split by commas not inside (), [], {}."""
    out: List[str] = []
    buf: List[str] = []
    depth_p = depth_b = depth_c = 0
    for ch in s:
        if ch == "(":
            depth_p += 1
        elif ch == ")":
            depth_p = max(0, depth_p - 1)
        elif ch == "[":
            depth_b += 1
        elif ch == "]":
            depth_b = max(0, depth_b - 1)
        elif ch == "{":
            depth_c += 1
        elif ch == "}":
            depth_c = max(0, depth_c - 1)

        if ch == "," and depth_p == 0 and depth_b == 0 and depth_c == 0:
            out.append("".join(buf).strip())
            buf = []
            continue
        buf.append(ch)
    tail = "".join(buf).strip()
    if tail:
        out.append(tail)
    return out


def extract_idents(text: str) -> List[str]:
    """Extract Verilog identifiers including escaped identifiers."""
    out: List[str] = []
    out.extend(_RE_ESCAPED.findall(text))
    out.extend(_RE_IDENT.findall(text))
    return out


def pick_last_ident(text: str) -> Optional[str]:
    ids = extract_idents(text)
    # remove keywords
    ids = [x for x in ids if x not in _VERILOG_KEYWORDS]
    return ids[-1] if ids else None


def find_balanced(text: str, open_idx: int, open_ch: str = "(", close_ch: str = ")") -> Optional[int]:
    """Return index of matching close_ch for the open_ch at open_idx."""
    depth = 0
    for i in range(open_idx, len(text)):
        ch = text[i]
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return i
    return None


def extract_module_name(module_text: str) -> Optional[str]:
    m = re.search(r"\bmodule\s+([A-Za-z_][A-Za-z0-9_$]*)", module_text)
    return m.group(1) if m else None



def extract_package_name(text: str) -> str | None:
    """Best-effort extract `package <name>` from a package declaration span."""
    text_nc = strip_comments_keep_len(text)
    m = re.search(r"\bpackage\s+([A-Za-z_][A-Za-z0-9_$]*)\b", text_nc)
    return m.group(1) if m else None


def extract_import_packages(text: str) -> List[Tuple[str, str]]:
    """Extract imported package names from `import ...;` statements.

    Returns list of (pkg_name, selector) where selector is '*' or an identifier.
    Handles patterns like:
      import pkg::*;
      import pkg::sym;
      import pkg1::*, pkg2::type_t;
    """
    text_nc = strip_comments_keep_len(text)
    out: List[Tuple[str, str]] = []
    for m in re.finditer(r"\bimport\b([^;]*);", text_nc, flags=re.S):
        body = m.group(1)
        parts = split_top_level_commas(body)
        for p in parts:
            mm = re.search(r"\b([A-Za-z_][A-Za-z0-9_$]*)\s*::\s*([A-Za-z_][A-Za-z0-9_$]*|\*)", p)
            if mm:
                out.append((mm.group(1), mm.group(2)))
    return out

def extract_module_header_ports(module_text: str) -> List[Tuple[str, Dict[str, str]]]:
    """
    Parse ANSI-style ports from a SystemVerilog module header.

    Correctly handles the common pattern:
        module name #(parameter ...) ( port declarations ... );

    Notes:
    - We do NOT treat tree-sitter parse errors as fatal; this is pure text parsing.
    - We strip comments before scanning for header parentheses.
    - We skip an optional parameter port list "#(...)" and then parse the real port list "(...)".

    Returns: list of (port_name, attrs_dict) where attrs_dict contains:
        dir: input|output|inout
        dtype: wire|reg|logic (best-effort)
        signed: "1" if present
        width_expr: e.g. "[31:0]" or "[REG_WIDTH-1:0]" (best-effort)
    """
    t = strip_comments_keep_len(module_text)

    # Find "module <name>"
    mm = re.search(r"\bmodule\s+([A-Za-z_][A-Za-z0-9_$]*)\b", t)
    if not mm:
        return []

    pos = mm.end()

    def _skip_ws(s: str, i: int) -> int:
        while i < len(s) and s[i].isspace():
            i += 1
        return i

    def _skip_attrs(s: str, i: int) -> int:
        """Skip SystemVerilog attributes like (* ... *)."""
        i = _skip_ws(s, i)
        while i + 1 < len(s) and s[i : i + 2] == "(*":
            j = s.find("*)", i + 2)
            if j < 0:
                return i
            i = j + 2
            i = _skip_ws(s, i)
        return i

    pos = _skip_attrs(t, pos)
    pos = _skip_ws(t, pos)

    # Optional parameter port list: #( ... )
    if pos < len(t) and t[pos] == "#":
        pos += 1
        pos = _skip_ws(t, pos)
        if pos < len(t) and t[pos] == "(":
            j = find_balanced(t, pos, "(", ")")
            if j is None:
                # malformed header; give up
                return []
            pos = j + 1
        pos = _skip_ws(t, pos)

    # Now the real port list: ( ... )
    pos = _skip_attrs(t, pos)
    pos = _skip_ws(t, pos)

    if pos >= len(t) or t[pos] != "(":
        return []  # no ANSI port list

    endp = find_balanced(t, pos, "(", ")")
    if endp is None:
        return []

    portlist = t[pos + 1 : endp]
    items = split_top_level_commas(portlist)

    ports: List[Tuple[str, Dict[str, str]]] = []
    ctx: Dict[str, str] = {}

    for it in items:
        it_str = it.strip()
        if not it_str:
            continue

        # Remove default assignment (e.g. "input logic a = 1'b0")
        it_no_default = it_str.split("=", 1)[0].strip()

        # Direction at the beginning is the most reliable signal
        dir_m = re.match(r"^(input|output|inout)\b", it_no_default)
        if dir_m:
            ctx = {"dir": dir_m.group(1)}
            if re.search(r"\bsigned\b", it_no_default):
                ctx["signed"] = "1"
            # width expression (best-effort)
            w_m = re.search(r"\[[^\]]+\]", it_no_default)
            if w_m:
                ctx["width_expr"] = w_m.group(0)
            # net/reg type hints (best-effort)
            dt_m = re.search(r"\b(wire|reg|logic)\b", it_no_default)
            if dt_m:
                ctx["dtype"] = dt_m.group(1)

        name = pick_last_ident(it_no_default)
        if not name:
            continue

        attrs = dict(ctx)
        ports.append((name, attrs))

    return ports

def extract_signal_decls(module_text: str) -> List[Tuple[str, Dict[str, str]]]:
    """
    Extract internal signal declarations in a coarse way.
    Returns list of (signal_name, attrs_dict).
    """
    t = strip_comments_keep_len(module_text)
    out: List[Tuple[str, Dict[str, str]]] = []

    # match declarations like: wire [7:0] a, b;  reg foo;
    # but avoid input/output/inout lines
    for m in re.finditer(r"(?m)^\s*(?!input\b)(?!output\b)(?!inout\b)\s*(wire|reg|logic)\b([^;]*);", t):
        decl_kind = m.group(1)
        rest = m.group(2)
        attrs: Dict[str, str] = {"decl_kind": decl_kind}
        if "signed" in rest:
            attrs["signed"] = "1"
        w_m = re.search(r"\[[^\]]+\]", rest)
        if w_m:
            attrs["width_expr"] = w_m.group(0)

        # remove packed range to simplify parsing names
        rest2 = re.sub(r"\[[^\]]+\]", " ", rest)
        # split by commas at top-level (should be safe here)
        names = split_top_level_commas(rest2)
        for n in names:
            name = pick_last_ident(n)
            if name and name not in _VERILOG_KEYWORDS:
                out.append((name, dict(attrs)))
    return out


def extract_param_decls(module_text: str) -> List[Tuple[str, Dict[str, str]]]:
    t = strip_comments_keep_len(module_text)
    out: List[Tuple[str, Dict[str, str]]] = []
    for m in re.finditer(r"(?m)^\s*(parameter|localparam)\b([^;]*);", t):
        pkind = m.group(1)
        rest = m.group(2)
        w_m = re.search(r"\[[^\]]+\]", rest)
        width_expr = w_m.group(0) if w_m else None
        # naive parse: "NAME = EXPR" possibly multiple per line
        parts = split_top_level_commas(rest)
        for p in parts:
            # allow "type NAME = expr"
            # take last ident before '='
            if "=" in p:
                left, right = p.split("=", 1)
                name = pick_last_ident(left)
                if not name:
                    continue
                attrs: Dict[str, str] = {"pkind": pkind, "value_short": right.strip()[:80]}
                if width_expr:
                    attrs["width_expr"] = width_expr
                out.append((name, attrs))
            else:
                name = pick_last_ident(p)
                if name:
                    attrs = {"pkind": pkind}
                    if width_expr:
                        attrs["width_expr"] = width_expr
                    out.append((name, attrs))
    return out


def extract_assign_lhs_rhs(assign_text: str) -> Tuple[str, str]:
    """
    Given full assign statement text, extract coarse lhs/rhs strings.
    """
    t = strip_comments_keep_len(assign_text).strip()
    # remove leading 'assign'
    t = re.sub(r"^\s*assign\b", "", t).strip()
    # drop trailing ';'
    if t.endswith(";"):
        t = t[:-1].strip()
    if "=" not in t:
        return t.strip(), ""
    lhs, rhs = t.split("=", 1)
    return lhs.strip(), rhs.strip()


def extract_lhs_signal_names(lhs_text: str) -> List[str]:
    """
    LHS-only signal extraction (lightweight):
    - collect identifiers on LHS (including escaped ids)
    - filter keywords
    """
    ids = extract_idents(lhs_text)
    ids = [x for x in ids if x not in _VERILOG_KEYWORDS]
    # de-dupe keeping order
    seen = set()
    out = []
    for x in ids:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def classify_always_write_kinds(always_text: str) -> Tuple[str, Dict[str, int]]:
    """
    Detect blocking/nonblocking writes in an always block using a conservative regex.
    Returns (k, counter_by_signal).
    """
    t = strip_comments_keep_len(always_text)
    # Nonblocking: a <= ...
    nb_pat = re.compile(r"(?<![<>=!])([A-Za-z_][A-Za-z0-9_$]*)\s*(?:\[[^\]]+\])?\s*<=")
    # Blocking assignment: a = ... but not ==, <=, >=, !=
    blk_pat = re.compile(r"(?<![<>=!])([A-Za-z_][A-Za-z0-9_$]*)\s*(?:\[[^\]]+\])?\s*=(?!=)")

    nb = nb_pat.findall(t)
    blk = blk_pat.findall(t)
    counter: Dict[str, int] = {}
    for name in nb + blk:
        if name in _VERILOG_KEYWORDS:
            continue
        counter[name] = counter.get(name, 0) + 1

    has_nb = len(nb) > 0
    has_blk = len(blk) > 0
    if has_nb and has_blk:
        return "mix", counter
    if has_nb:
        return "nb", counter
    if has_blk:
        return "blk", counter
    # no assignment found -> still classify as blk (neutral)
    return "blk", counter


###############################################################################
#                          Tree-sitter node traversal                           #
###############################################################################


def iter_named_nodes(root) -> Iterator:
    """Yield named nodes in a DFS manner."""
    stack = [root]
    while stack:
        n = stack.pop()
        # tree_sitter Node has `is_named`
        if getattr(n, "is_named", False):
            yield n
        # push children
        for c in reversed(getattr(n, "children", [])):
            stack.append(c)


def node_text(src: bytes, node) -> str:
    return src[node.start_byte : node.end_byte].decode("utf-8", errors="ignore")


def node_text_short(src: bytes, node, max_len: int = 160) -> str:
    text = " ".join(node_text(src, node).split())
    if len(text) > max_len:
        return text[: max_len - 3] + "..."
    return text


def extract_function_name_from_text(func_text: str) -> Optional[str]:
    text_nc = strip_comments_keep_len(func_text)
    m = re.search(r"\bfunction\b(.*?)(?:;|\()", text_nc, flags=re.S)
    if not m:
        return None
    return pick_last_ident(m.group(1))


def extract_function_name(src: bytes, func_node) -> Optional[str]:
    for n in iter_named_nodes(func_node):
        if n is func_node:
            continue
        if getattr(n, "type", "") == "function_identifier":
            name = node_text(src, n).strip()
            if name and name not in _VERILOG_KEYWORDS:
                return name
    return extract_function_name_from_text(node_text(src, func_node))


def extract_function_decl_attrs(func_text: str, func_name: str) -> Dict[str, object]:
    text_nc = strip_comments_keep_len(func_text)
    attrs: Dict[str, object] = {}

    name_idx = text_nc.find(func_name)
    if name_idx >= 0:
        prefix = text_nc[:name_idx]
        width_m = re.search(r"\[[^\]]+\]", prefix)
        if width_m:
            attrs["ret_width_expr"] = width_m.group(0)

    arg_names: List[str] = []

    for m in re.finditer(r"(?m)^\s*input\b([^;]*);", text_nc):
        rest = m.group(1)
        rest = re.sub(r"\[[^\]]+\]", " ", rest)
        for item in split_top_level_commas(rest):
            name = pick_last_ident(item)
            if name:
                arg_names.append(name)

    header_pos = name_idx + len(func_name) if name_idx >= 0 else -1
    if header_pos >= 0:
        open_idx = text_nc.find("(", header_pos)
        if open_idx >= 0:
            close_idx = find_balanced(text_nc, open_idx)
            if close_idx is not None:
                port_text = text_nc[open_idx + 1 : close_idx]
                for item in split_top_level_commas(port_text):
                    name = pick_last_ident(item)
                    if name:
                        arg_names.append(name)

    if arg_names:
        deduped: List[str] = []
        seen: set[str] = set()
        for name in arg_names:
            if name in seen:
                continue
            seen.add(name)
            deduped.append(name)
        attrs["arg_names"] = deduped

    return attrs


def extract_function_call_name(src: bytes, call_node) -> Optional[str]:
    for n in iter_named_nodes(call_node):
        if n is call_node:
            continue
        if getattr(n, "type", "") == "function_identifier":
            name = node_text(src, n).strip()
            if name and name not in _VERILOG_KEYWORDS and not name.startswith("$"):
                return name

    call_text = strip_comments_keep_len(node_text(src, call_node)).strip()
    m = re.match(r"([A-Za-z_][A-Za-z0-9_$]*)\s*\(", call_text)
    if not m:
        return None
    name = m.group(1)
    if name in _VERILOG_KEYWORDS or name.startswith("$"):
        return None
    return name


def collect_function_calls(src: bytes, root_node) -> Dict[str, int]:
    counter: Dict[str, int] = {}
    seen_spans: set[tuple[int, int, str]] = set()
    for n in iter_named_nodes(root_node):
        ntype = getattr(n, "type", "")
        if ntype not in {"function_subroutine_call", "subroutine_call"}:
            continue
        parent_type = getattr(getattr(n, "parent", None), "type", "")
        if ntype == "subroutine_call" and parent_type == "function_subroutine_call":
            continue
        name = extract_function_call_name(src, n)
        if not name:
            continue
        key = (n.start_byte, n.end_byte, name)
        if key in seen_spans:
            continue
        seen_spans.add(key)
        counter[name] = counter.get(name, 0) + 1
    return counter


###############################################################################
#                               FileGraphBuilder                               #
###############################################################################


@dataclass
class RTLFileGraphResult:
    nodes: List[KnowledgeGraphNode]
    edges: List[KnowledgeGraphEdge]


class RTLFileGraphBuilder:
    """Build a lean RTL subgraph for a single file."""

    def __init__(self, repo_uid: str, repo_root: Path):
        self.repo_uid = repo_uid
        self.repo_root = repo_root.resolve()

    def supports_file(self, p: Path) -> bool:
        return p.suffix.lower() in {".v", ".vh", ".sv", ".svh"}

    def build_file_graph(self, file_node: KnowledgeGraphNode, abs_path: Path) -> RTLFileGraphResult:
        """
        Parse file with tree-sitter and extract Module/Instance/Port/Signal/Param/Always/Assign/Func
        plus wiring edges (HAS/INSTANTIATES/CONNECTS/CALLS/DRIVES) and file->module DEFINES.
        """
        abs_path = abs_path.resolve()
        rel_path = abs_path.relative_to(self.repo_root).as_posix()
        src = abs_path.read_bytes()
        parser = VerilogTreeSitter.get_parser()
        tree = parser.parse(src)
        if tree.root_node.child_count == 0:
            print(rel_path, tree.root_node.has_error, tree.root_node.child_count)
            return RTLFileGraphResult(nodes=[], edges=[])
        # if tree.root_node.has_error or tree.root_node.child_count == 0:
        #     # still keep file node; return empty subgraph
        #     print(rel_path, tree.root_node.has_error, tree.root_node.child_count)
        #     return RTLFileGraphResult(nodes=[], edges=[])

        created_nodes: List[KnowledgeGraphNode] = []
        created_edges: List[KnowledgeGraphEdge] = []

        # Indexes for module-local nodes for quick linking
        module_uid_to_ports: Dict[str, Dict[str, KnowledgeGraphNode]] = {}
        module_uid_to_sigs: Dict[str, Dict[str, KnowledgeGraphNode]] = {}
        module_uid_to_params: Dict[str, Dict[str, KnowledgeGraphNode]] = {}

        # Traverse and find module declarations and some constructs
        # We rely on node.type strings for module_declaration, continuous_assign, module_instantiation, always*
        for n in iter_named_nodes(tree.root_node):
            ntype = getattr(n, "type", "")
            if ntype == "module_declaration":
                # Slice module text by bytes for more reliable extraction
                m_text = src[n.start_byte : n.end_byte].decode("utf-8", errors="ignore")
                mname = extract_module_name(m_text)
                if not mname:
                    continue
                sl = n.start_point[0] + 1
                el = n.end_point[0] + 1

                # Module is the sole planning/code alignment anchor.  Its identity
                # must therefore survive the Stage2 placeholder -> Stage6 file move.
                mod_uid = canonical_module_uid(self.repo_uid, mname)
                mod = KnowledgeGraphNode(
                    uid=mod_uid,
                    repo_uid=self.repo_uid,
                    node=ModuleNode(
                        name=mname,
                        path=rel_path,
                        sl=sl,
                        el=el,
                        h=sha1_bytes(m_text.encode("utf-8", errors="ignore")),
                        attrs=None,
                    ),
                )
                created_nodes.append(mod)
                created_edges.append(
                    KnowledgeGraphEdge(
                        source=file_node,
                        target=mod,
                        type=KnowledgeGraphEdgeType.defines,
                        props={"eid": make_eid(file_node.uid, "DEFINES", mod_uid)},
                    )
                )

                # Imports inside module (best-effort, SystemVerilog)
                for ipkg, sel in extract_import_packages(m_text):
                    ref_uid = make_uid(self.repo_uid, 'package_ref', ipkg)
                    ref = KnowledgeGraphNode(
                        uid=ref_uid,
                        repo_uid=self.repo_uid,
                        node=PackageNode(name=ipkg, path='', sl=0, el=0, h=None, attrs={'ref': True}),
                    )
                    created_nodes.append(ref)
                    created_edges.append(
                        KnowledgeGraphEdge(
                            source=mod,
                            target=ref,
                            type=KnowledgeGraphEdgeType.imports,
                            props={'eid': make_eid(mod_uid, 'IMPORTS', ref_uid), 'sel': sel},
                        )
                    )

                # Ports (header)
                ports = extract_module_header_ports(m_text)
                port_map: Dict[str, KnowledgeGraphNode] = {}
                for pname, attrs in ports:
                    p_uid = make_uid(self.repo_uid, "port", mname, pname, rel_path)
                    pnode = KnowledgeGraphNode(
                        uid=p_uid,
                        repo_uid=self.repo_uid,
                        node=PortNode(name=pname, path=rel_path, sl=None, el=None, attrs={"module": mname, **attrs}),
                    )
                    created_nodes.append(pnode)
                    created_edges.append(
                        KnowledgeGraphEdge(
                            source=mod,
                            target=pnode,
                            type=KnowledgeGraphEdgeType.has,
                            props={"eid": make_eid(mod_uid, "HAS", p_uid), "k": NodeKind.port.value},
                        )
                    )
                    port_map[pname] = pnode
                module_uid_to_ports[mod_uid] = port_map

                # Params
                params = extract_param_decls(m_text)
                pmap: Dict[str, KnowledgeGraphNode] = {}
                for pname, attrs in params:
                    puid = make_uid(self.repo_uid, "param", mname, pname, rel_path)
                    pnode = KnowledgeGraphNode(
                        uid=puid,
                        repo_uid=self.repo_uid,
                        node=ParamNode(name=pname, path=rel_path, sl=None, el=None, attrs={"module": mname, **attrs}),
                    )
                    created_nodes.append(pnode)
                    created_edges.append(
                        KnowledgeGraphEdge(
                            source=mod,
                            target=pnode,
                            type=KnowledgeGraphEdgeType.has,
                            props={"eid": make_eid(mod_uid, "HAS", puid), "k": NodeKind.param.value},
                        )
                    )
                    pmap[pname] = pnode
                module_uid_to_params[mod_uid] = pmap

                # Signals
                sigs = extract_signal_decls(m_text)
                smap: Dict[str, KnowledgeGraphNode] = {}
                for sname, attrs in sigs:
                    suid = make_uid(self.repo_uid, "signal", mname, sname, rel_path)
                    snode = KnowledgeGraphNode(
                        uid=suid,
                        repo_uid=self.repo_uid,
                        node=SignalNode(name=sname, path=rel_path, sl=None, el=None, attrs={"module": mname, **attrs}),
                    )
                    created_nodes.append(snode)
                    created_edges.append(
                        KnowledgeGraphEdge(
                            source=mod,
                            target=snode,
                            type=KnowledgeGraphEdgeType.has,
                            props={"eid": make_eid(mod_uid, "HAS", suid), "k": NodeKind.signal.value},
                        )
                    )
                    smap[sname] = snode
                module_uid_to_sigs[mod_uid] = smap

                module_named_nodes = list(iter_named_nodes(n))

                # Functions first so CALLS edges can resolve regardless of declaration order.
                func_map: Dict[str, KnowledgeGraphNode] = {}
                for c in module_named_nodes:
                    if getattr(c, "type", "") != "function_declaration":
                        continue
                    f_text = node_text(src, c)
                    fname = extract_function_name(src, c)
                    if not fname:
                        continue
                    f_sl = c.start_point[0] + 1
                    f_el = c.end_point[0] + 1
                    f_uid = make_uid(self.repo_uid, "func", mname, fname, rel_path, str(f_sl), str(f_el))
                    f_attrs = {"module": mname, **extract_function_decl_attrs(f_text, fname)}
                    fnode = KnowledgeGraphNode(
                        uid=f_uid,
                        repo_uid=self.repo_uid,
                        node=FuncNode(
                            name=fname,
                            path=rel_path,
                            sl=f_sl,
                            el=f_el,
                            h=sha1_bytes(f_text.encode("utf-8", errors="ignore")),
                            attrs=f_attrs,
                        ),
                    )
                    created_nodes.append(fnode)
                    created_edges.append(
                        KnowledgeGraphEdge(
                            source=mod,
                            target=fnode,
                            type=KnowledgeGraphEdgeType.has,
                            props={"eid": make_eid(mod_uid, "HAS", f_uid), "k": NodeKind.func.value},
                        )
                    )
                    # Same-name functions in one module are treated as last-wins for call resolution.
                    func_map[fname] = fnode

                # Within this module scope, we will also create Always/Assign/Instance nodes by scanning children nodes
                # We do a nested traversal limited to this module's subtree for better association.
                for c in module_named_nodes:
                    ctype = getattr(c, "type", "")
                    # Generate blocks (best-effort skeleton)
                    if ('generate' in ctype and ctype not in {'generate', 'endgenerate', 'generate_keyword'}):
                        g_sl = c.start_point[0] + 1
                        g_el = c.end_point[0] + 1
                        g_text = src[c.start_byte : c.end_byte].decode('utf-8', errors='ignore')
                        g_text_nc = strip_comments_keep_len(g_text).strip()
                        if g_text_nc.startswith('generate') or 'generate' in g_text_nc[:40] or ctype.startswith('generate'):
                            g_uid = make_uid(self.repo_uid, 'generate', mname, rel_path, str(g_sl), str(g_el))
                            gnode = KnowledgeGraphNode(
                                uid=g_uid,
                                repo_uid=self.repo_uid,
                                node=GenerateNode(
                                    path=rel_path,
                                    sl=g_sl,
                                    el=g_el,
                                    name=None,
                                    attrs={'module': mname, 'gkind': ctype},
                                ),
                            )
                            created_nodes.append(gnode)
                            created_edges.append(
                                KnowledgeGraphEdge(
                                    source=mod,
                                    target=gnode,
                                    type=KnowledgeGraphEdgeType.has,
                                    props={'eid': make_eid(mod_uid, 'HAS', g_uid), 'k': NodeKind.generate.value},
                                )
                            )

                    # Always blocks (any always* construct)
                    if "always" in ctype and ctype != "always_keyword":
                        ab_sl = c.start_point[0] + 1
                        ab_el = c.end_point[0] + 1
                        ab_text = src[c.start_byte : c.end_byte].decode("utf-8", errors="ignore")
                        bkind = "ff" if "ff" in ctype else ("comb" if "comb" in ctype else ("latch" if "latch" in ctype else "always"))
                        sens_short = ""
                        # best-effort: extract "@(...)" if present
                        at_idx = ab_text.find("@")
                        if at_idx >= 0:
                            # grab up to first "begin" or newline
                            cut = ab_text[at_idx : at_idx + 120]
                            sens_short = cut.split("begin", 1)[0].strip().replace("\n", " ")
                        ab_uid = make_uid(self.repo_uid, "always", mname, rel_path, str(ab_sl), str(ab_el))
                        ab_node = KnowledgeGraphNode(
                            uid=ab_uid,
                            repo_uid=self.repo_uid,
                            node=AlwaysBlockNode(
                                path=rel_path,
                                sl=ab_sl,
                                el=ab_el,
                                name=None,
                                h=sha1_bytes(ab_text.encode("utf-8", errors="ignore")),
                                attrs={"module": mname, "bkind": bkind, "sens_short": sens_short} if sens_short else {"module": mname, "bkind": bkind},
                            ),
                        )
                        created_nodes.append(ab_node)
                        created_edges.append(
                            KnowledgeGraphEdge(
                                source=mod,
                                target=ab_node,
                                type=KnowledgeGraphEdgeType.has,
                                props={"eid": make_eid(mod_uid, "HAS", ab_uid), "k": NodeKind.always_block.value},
                            )
                        )

                        # LHS-only DRIVES edges from always block
                        k, counter = classify_always_write_kinds(ab_text)
                        for sig_name, cnt in counter.items():
                            tgt = smap.get(sig_name) or port_map.get(sig_name)
                            if not tgt:
                                continue
                            created_edges.append(
                                KnowledgeGraphEdge(
                                    source=ab_node,
                                    target=tgt,
                                    type=KnowledgeGraphEdgeType.drives,
                                    props={"eid": make_eid(ab_uid, "DRIVES", tgt.uid), "k": k, "cnt": cnt},
                                )
                            )

                        for func_name, cnt in collect_function_calls(src, c).items():
                            tgt = func_map.get(func_name)
                            if not tgt:
                                continue
                            created_edges.append(
                                KnowledgeGraphEdge(
                                    source=ab_node,
                                    target=tgt,
                                    type=KnowledgeGraphEdgeType.calls,
                                    props={"eid": make_eid(ab_uid, "CALLS", tgt.uid), "cnt": cnt},
                                )
                            )

                    # Continuous assigns (tree-sitter usually uses "continuous_assign" or similar; we also check text prefix)
                    if ctype in {"continuous_assign", "continuous_assignment", "continuous_assign_statement"} or (
                        ctype.endswith("assign") and src[c.start_byte : c.end_byte].lstrip().startswith(b"assign")
                    ):
                        as_sl = c.start_point[0] + 1
                        as_el = c.end_point[0] + 1
                        as_text = src[c.start_byte : c.end_byte].decode("utf-8", errors="ignore")
                        lhs, rhs = extract_assign_lhs_rhs(as_text)
                        a_uid = make_uid(self.repo_uid, "assign", mname, rel_path, str(as_sl), str(as_el))
                        anode = KnowledgeGraphNode(
                            uid=a_uid,
                            repo_uid=self.repo_uid,
                            node=AssignNode(
                                path=rel_path,
                                sl=as_sl,
                                el=as_el,
                                h=sha1_bytes(as_text.encode("utf-8", errors="ignore")),
                                attrs={"module": mname, "lhs_short": lhs[:120], "rhs_short": rhs[:120]},
                            ),
                        )
                        created_nodes.append(anode)
                        created_edges.append(
                            KnowledgeGraphEdge(
                                source=mod,
                                target=anode,
                                type=KnowledgeGraphEdgeType.has,
                                props={"eid": make_eid(mod_uid, "HAS", a_uid), "k": NodeKind.assign.value},
                            )
                        )
                        # DRIVES (LHS-only)
                        for sig_name in extract_lhs_signal_names(lhs):
                            tgt = smap.get(sig_name) or port_map.get(sig_name)
                            if not tgt:
                                continue
                            created_edges.append(
                                KnowledgeGraphEdge(
                                    source=anode,
                                    target=tgt,
                                    type=KnowledgeGraphEdgeType.drives,
                                    props={"eid": make_eid(a_uid, "DRIVES", tgt.uid), "k": "cont", "cnt": 1},
                                )
                            )

                        for func_name, cnt in collect_function_calls(src, c).items():
                            tgt = func_map.get(func_name)
                            if not tgt:
                                continue
                            created_edges.append(
                                KnowledgeGraphEdge(
                                    source=anode,
                                    target=tgt,
                                    type=KnowledgeGraphEdgeType.calls,
                                    props={"eid": make_eid(a_uid, "CALLS", tgt.uid), "cnt": cnt},
                                )
                            )

                    # Module instantiation
                    if ctype in {"module_instantiation", "module_instance"} or "module_instantiation" in ctype:
                        inst_text = src[c.start_byte : c.end_byte].decode("utf-8", errors="ignore")
                        # very naive parse: <modref> [#(...)] <instname> ( ... )
                        # (works well for common single-instance statement)
                        inst_text_nc = strip_comments_keep_len(inst_text)
                        # module ref = first ident after optional attributes
                        modref_m = re.search(r"\b([A-Za-z_][A-Za-z0-9_$]*)\b", inst_text_nc)
                        if not modref_m:
                            continue
                        modref = modref_m.group(1)
                        # find inst name after modref (+ optional #(...))
                        rest = inst_text_nc[modref_m.end() :]
                        # skip parameter override
                        hash_idx = rest.find("#")
                        if hash_idx >= 0:
                            # find "(...)" after '#'
                            p_open = rest.find("(", hash_idx)
                            if p_open >= 0:
                                p_close = find_balanced(rest, p_open)
                                if p_close is not None:
                                    rest = rest[p_close + 1 :]

                        # instname = pick_last_ident(rest)
                        inst_m = re.search(r"\b([A-Za-z_][A-Za-z0-9_$]*)\b", rest)
                        instname = inst_m.group(1) if inst_m else None
                        if not instname:
                            continue

                        inst_sl = c.start_point[0] + 1
                        inst_el = c.end_point[0] + 1
                        i_uid = make_uid(self.repo_uid, "inst", mname, instname, rel_path, str(inst_sl), str(inst_el))
                        inode = KnowledgeGraphNode(
                            uid=i_uid,
                            repo_uid=self.repo_uid,
                            node=InstanceNode(
                                name=instname,
                                path=rel_path,
                                sl=inst_sl,
                                el=inst_el,
                                attrs={"module": mname, "module_ref": modref},
                            ),
                        )
                        created_nodes.append(inode)
                        created_edges.append(
                            KnowledgeGraphEdge(
                                source=mod,
                                target=inode,
                                type=KnowledgeGraphEdgeType.instantiates,
                                props={"eid": make_eid(mod_uid, "INSTANTIATES", i_uid)},
                            )
                        )

                        # Extract connections inside the first (...) after instname
                        # We parse text after instname occurrence
                        kpos = inst_text_nc.find(instname)
                        if kpos >= 0:
                            conn_open = inst_text_nc.find("(", kpos + len(instname))
                            if conn_open >= 0:
                                conn_close = find_balanced(inst_text_nc, conn_open)
                                if conn_close is not None:
                                    conn_body = inst_text_nc[conn_open + 1 : conn_close]
                                    conn_items = split_top_level_commas(conn_body)
                                    ord_idx = 0
                                    for ci in conn_items:
                                        ci = ci.strip()
                                        if not ci:
                                            continue
                                        # named: .port(expr)
                                        nm = re.match(r"^\.\s*([A-Za-z_][A-Za-z0-9_$]*)\s*\((.*)\)\s*$", ci, flags=re.S)
                                        if nm:
                                            formal = nm.group(1)
                                            expr = nm.group(2).strip()
                                            # classify target
                                            expr_name = pick_last_ident(expr)
                                            tgt_node = None
                                            t = "expr"
                                            x_short = re.sub(r"\s+", " ", expr)[:120]
                                            h = short_hash(expr)
                                            if expr_name and expr_name in smap:
                                                tgt_node = smap[expr_name]
                                                t = "signal"
                                            elif expr_name and expr_name in port_map:
                                                tgt_node = port_map[expr_name]
                                                t = "port"
                                            else:
                                                # create Expr node (dedup within file by hash)
                                                e_uid = make_uid(self.repo_uid, "expr", mname, rel_path, h)
                                                tgt_node = KnowledgeGraphNode(
                                                    uid=e_uid,
                                                    repo_uid=self.repo_uid,
                                                    node=ExprNode(attrs={"module": mname, "text_short": x_short, "text_hash": h}),
                                                )
                                                # Add only once
                                                if all(n.uid != e_uid for n in created_nodes):
                                                    created_nodes.append(tgt_node)

                                            created_edges.append(
                                                KnowledgeGraphEdge(
                                                    source=inode,
                                                    target=tgt_node,
                                                    type=KnowledgeGraphEdgeType.connects,
                                                    props={
                                                        "eid": make_eid(i_uid, "CONNECTS", tgt_node.uid, formal),
                                                        "p": formal,
                                                        "by": "named",
                                                        "t": t,
                                                        "x": x_short,
                                                        "h": h,
                                                        "path": rel_path,
                                                        "sl": inst_sl,
                                                        "el": inst_el,
                                                    },
                                                )
                                            )
                                        else:
                                            # positional: (expr1, expr2, ...)
                                            expr = ci
                                            expr_name = pick_last_ident(expr)
                                            tgt_node = None
                                            t = "expr"
                                            x_short = re.sub(r"\s+", " ", expr)[:120]
                                            h = short_hash(expr)
                                            if expr_name and expr_name in smap:
                                                tgt_node = smap[expr_name]
                                                t = "signal"
                                            elif expr_name and expr_name in port_map:
                                                tgt_node = port_map[expr_name]
                                                t = "port"
                                            else:
                                                e_uid = make_uid(self.repo_uid, "expr", mname, rel_path, h)
                                                tgt_node = KnowledgeGraphNode(
                                                    uid=e_uid,
                                                    repo_uid=self.repo_uid,
                                                    node=ExprNode(attrs={"module": mname, "text_short": x_short, "text_hash": h}),
                                                )
                                                if all(n.uid != e_uid for n in created_nodes):
                                                    created_nodes.append(tgt_node)

                                            created_edges.append(
                                                KnowledgeGraphEdge(
                                                    source=inode,
                                                    target=tgt_node,
                                                    type=KnowledgeGraphEdgeType.connects,
                                                    props={
                                                        "eid": make_eid(i_uid, "CONNECTS", tgt_node.uid, f"@{ord_idx}"),
                                                        "p": f"$pos{ord_idx}",
                                                        "by": "positional",
                                                        "ord": ord_idx,
                                                        "t": t,
                                                        "x": x_short,
                                                        "h": h,
                                                        "path": rel_path,
                                                        "sl": inst_sl,
                                                        "el": inst_el,
                                                    },
                                                )
                                            )
                                            ord_idx += 1

            # Package declarations (SystemVerilog, best-effort)
            if ntype in {'package_declaration', 'package'} or ('package' in ntype and 'declaration' in ntype):
                p_text = src[n.start_byte : n.end_byte].decode('utf-8', errors='ignore')
                pname = extract_package_name(p_text)
                if pname:
                    p_sl = n.start_point[0] + 1
                    p_el = n.end_point[0] + 1
                    pkg_uid = make_uid(self.repo_uid, 'package', pname, rel_path)
                    pkg = KnowledgeGraphNode(
                        uid=pkg_uid,
                        repo_uid=self.repo_uid,
                        node=PackageNode(
                            name=pname,
                            path=rel_path,
                            sl=p_sl,
                            el=p_el,
                            h=sha1_bytes(p_text.encode('utf-8', errors='ignore')),
                            attrs=None,
                        ),
                    )
                    created_nodes.append(pkg)
                    created_edges.append(
                        KnowledgeGraphEdge(
                            source=file_node,
                            target=pkg,
                            type=KnowledgeGraphEdgeType.defines,
                            props={'eid': make_eid(file_node.uid, 'DEFINES', pkg_uid)},
                        )
                    )
                    for ipkg, sel in extract_import_packages(p_text):
                        ref_uid = make_uid(self.repo_uid, 'package_ref', ipkg)
                        ref = KnowledgeGraphNode(
                            uid=ref_uid,
                            repo_uid=self.repo_uid,
                            node=PackageNode(name=ipkg, path='', sl=0, el=0, h=None, attrs={'ref': True}),
                        )
                        created_nodes.append(ref)
                        created_edges.append(
                            KnowledgeGraphEdge(
                                source=pkg,
                                target=ref,
                                type=KnowledgeGraphEdgeType.imports,
                                props={'eid': make_eid(pkg_uid, 'IMPORTS', ref_uid), 'sel': sel},
                            )
                        )

        return RTLFileGraphResult(nodes=created_nodes, edges=created_edges)
