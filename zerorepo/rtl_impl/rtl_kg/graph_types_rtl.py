"""Type definitions for nodes and edges in the RTL repository knowledge graph.

This module is intentionally "lean":
- Nodes store stable identifiers + lightweight span fields + compact attributes.
- Edges encode repository structure, hierarchy, port-level connections, and *LHS-only* drivers
  (for structural backtrace / COI without statement-level explosion).

Neo4j conventions (recommended):
- Use `uid` as the unique key for every node label.
- Use `eid` as the unique key for relationships (MERGE on relationship + {eid}).

Design goals:
- Repo/File/Module/Instance hierarchy navigation.
- Port/Signal/Param/Always/Assign/Generate skeleton for local-view debugging.
- CONNECTS for port-level wiring.
- DRIVES (LHS-only) for fast structural backtrace and multi-driver detection.
"""

import dataclasses
import enum
from typing import Any, Literal, NotRequired, Required, TypedDict, Union

###############################################################################
#                               Node models                                   #
###############################################################################

Json = dict[str, Any]


@dataclasses.dataclass(frozen=True)
class RepoNode:
    """Repository root node."""

    name: str
    attrs: Json | None = None


@dataclasses.dataclass(frozen=True)
class FileNode:
    """File or directory node (unified)."""

    path: str  # repo-relative path; directories also have a path
    name: str  # basename
    h: str | None = None  # file content hash (optional)
    attrs: Json | None = None  # e.g., {is_dir, lang, role, size, mtime}


@dataclasses.dataclass(frozen=True)
class ModuleNode:
    """SystemVerilog/Verilog module definition."""

    name: str
    path: str
    sl: int  # start line (1-based, inclusive)
    el: int  # end line (1-based, inclusive)
    h: str | None = None  # optional hash of module text span
    attrs: Json | None = None


@dataclasses.dataclass(frozen=True)
class PackageNode:
    """SystemVerilog package definition (optional)."""

    name: str
    path: str
    sl: int
    el: int
    h: str | None = None
    attrs: Json | None = None


@dataclasses.dataclass(frozen=True)
class InstanceNode:
    """Module instantiation site."""

    name: str  # instance name
    path: str
    sl: int
    el: int
    attrs: Json | None = None  # {module_ref, gen_path, hier_path, resolved_module_uid, conf}


@dataclasses.dataclass(frozen=True)
class PortNode:
    """Module port (declaration-level)."""

    name: str
    path: str | None = None
    sl: int | None = None
    el: int | None = None
    attrs: Json | None = None  # {module_uid, dir, dtype, signed, width_expr}


@dataclasses.dataclass(frozen=True)
class SignalNode:
    """Module internal signal (declaration-level only)."""

    name: str
    path: str | None = None
    sl: int | None = None
    el: int | None = None
    attrs: Json | None = None  # {module_uid, decl_kind, signed, width_expr}


@dataclasses.dataclass(frozen=True)
class ParamNode:
    """Parameter / localparam (merged)."""

    name: str
    path: str | None = None
    sl: int | None = None
    el: int | None = None
    attrs: Json | None = None  # {module_uid, pkind, value_short, value_hash, width_expr}


@dataclasses.dataclass(frozen=True)
class AlwaysBlockNode:
    """Process container (always_ff/always_comb/always@...)."""

    path: str
    sl: int
    el: int
    name: str | None = None  # optional label
    h: str | None = None  # optional hash of block text span
    attrs: Json | None = None  # {module_uid, bkind, sens_short, clk, rst}


@dataclasses.dataclass(frozen=True)
class AssignNode:
    """Continuous assignment node (assign lhs = rhs)."""

    path: str
    sl: int
    el: int
    h: str | None = None  # optional expr hash / span hash
    attrs: Json | None = None  # {module_uid, lhs_short, rhs_short, expr_hash}


@dataclasses.dataclass(frozen=True)
class GenerateNode:
    """Generate block skeleton (for/if/case)."""

    path: str
    sl: int
    el: int
    name: str | None = None
    attrs: Json | None = None  # {module_uid, gkind, genvar, range_short, label_path}


@dataclasses.dataclass(frozen=True)
class FuncNode:
    """Module-local function declaration."""

    name: str
    path: str
    sl: int
    el: int
    h: str | None = None
    attrs: Json | None = None  # {module, ret_width_expr, arg_names}


@dataclasses.dataclass(frozen=True)
class ExprNode:
    """Optional expression node for CONNECTS target (when not a plain signal/port)."""

    attrs: Json | None = None  # {text_short, text_hash, ref_names, width_expr}


KGNodePayload = Union[
    RepoNode,
    FileNode,
    ModuleNode,
    PackageNode,
    InstanceNode,
    PortNode,
    SignalNode,
    ParamNode,
    AlwaysBlockNode,
    AssignNode,
    GenerateNode,
    FuncNode,
    ExprNode,
]


class NodeKind(enum.StrEnum):
    """Canonical 'kind' field stored on every Neo4j node."""

    repo = "Repo"
    file = "File"
    module = "Module"
    package = "Package"
    instance = "Instance"
    port = "Port"
    signal = "Signal"
    param = "Param"
    always_block = "AlwaysBlock"
    assign = "Assign"
    generate = "Generate"
    func = "Func"
    expr = "Expr"


@dataclasses.dataclass(frozen=True)
class KnowledgeGraphNode:
    """A node wrapper carrying stable identifiers + a typed payload.

    Attributes:
      uid: Stable unique id for MERGE.
      repo_uid: Partition key (repo@commit).
      node: The payload dataclass.
    """

    uid: str
    repo_uid: str
    node: KGNodePayload

    def kind(self) -> NodeKind:
        """Infer NodeKind from payload type."""
        match self.node:
            case RepoNode():
                return NodeKind.repo
            case FileNode():
                return NodeKind.file
            case ModuleNode():
                return NodeKind.module
            case PackageNode():
                return NodeKind.package
            case InstanceNode():
                return NodeKind.instance
            case PortNode():
                return NodeKind.port
            case SignalNode():
                return NodeKind.signal
            case ParamNode():
                return NodeKind.param
            case AlwaysBlockNode():
                return NodeKind.always_block
            case AssignNode():
                return NodeKind.assign
            case GenerateNode():
                return NodeKind.generate
            case FuncNode():
                return NodeKind.func
            case ExprNode():
                return NodeKind.expr
            case _:
                raise ValueError(f"Unknown node payload type: {type(self.node)}")


    def to_neo4j_node(
        self,
    ) -> Union[
        "Neo4jRepoNode",
        "Neo4jFileNode",
        "Neo4jModuleNode",
        "Neo4jPackageNode",
        "Neo4jInstanceNode",
        "Neo4jPortNode",
        "Neo4jSignalNode",
        "Neo4jParamNode",
        "Neo4jAlwaysBlockNode",
        "Neo4jAssignNode",
        "Neo4jGenerateNode",
        "Neo4jFuncNode",
        "Neo4jExprNode",
    ]:
        """Convert this node to a Neo4j node property dict."""
        base = {"uid": self.uid, "repo_uid": self.repo_uid, "kind": self.kind().value}

        match self.node:
            case RepoNode():
                out: Neo4jRepoNode = {**base, "name": self.node.name}
                if self.node.attrs is not None:
                    out["attrs"] = self.node.attrs
                return out

            case FileNode():
                out: Neo4jFileNode = {**base, "name": self.node.name, "path": self.node.path}
                if self.node.h is not None:
                    out["h"] = self.node.h
                if self.node.attrs is not None:
                    out["attrs"] = self.node.attrs
                return out

            case ModuleNode():
                out: Neo4jModuleNode = {
                    **base,
                    "name": self.node.name,
                    "path": self.node.path,
                    "sl": self.node.sl,
                    "el": self.node.el,
                }
                if self.node.h is not None:
                    out["h"] = self.node.h
                if self.node.attrs is not None:
                    out["attrs"] = self.node.attrs
                return out

            case PackageNode():
                out: Neo4jPackageNode = {
                    **base,
                    "name": self.node.name,
                    "path": self.node.path,
                    "sl": self.node.sl,
                    "el": self.node.el,
                }
                if self.node.h is not None:
                    out["h"] = self.node.h
                if self.node.attrs is not None:
                    out["attrs"] = self.node.attrs
                return out

            case InstanceNode():
                out: Neo4jInstanceNode = {
                    **base,
                    "name": self.node.name,
                    "path": self.node.path,
                    "sl": self.node.sl,
                    "el": self.node.el,
                }
                if self.node.attrs is not None:
                    out["attrs"] = self.node.attrs
                return out

            case PortNode():
                out: Neo4jPortNode = {**base, "name": self.node.name}
                if self.node.path is not None:
                    out["path"] = self.node.path
                if self.node.sl is not None:
                    out["sl"] = self.node.sl
                if self.node.el is not None:
                    out["el"] = self.node.el
                if self.node.attrs is not None:
                    out["attrs"] = self.node.attrs
                return out

            case SignalNode():
                out: Neo4jSignalNode = {**base, "name": self.node.name}
                if self.node.path is not None:
                    out["path"] = self.node.path
                if self.node.sl is not None:
                    out["sl"] = self.node.sl
                if self.node.el is not None:
                    out["el"] = self.node.el
                if self.node.attrs is not None:
                    out["attrs"] = self.node.attrs
                return out

            case ParamNode():
                out: Neo4jParamNode = {**base, "name": self.node.name}
                if self.node.path is not None:
                    out["path"] = self.node.path
                if self.node.sl is not None:
                    out["sl"] = self.node.sl
                if self.node.el is not None:
                    out["el"] = self.node.el
                if self.node.attrs is not None:
                    out["attrs"] = self.node.attrs
                return out

            case AlwaysBlockNode():
                out: Neo4jAlwaysBlockNode = {
                    **base,
                    "path": self.node.path,
                    "sl": self.node.sl,
                    "el": self.node.el,
                }
                if self.node.name is not None:
                    out["name"] = self.node.name
                if self.node.h is not None:
                    out["h"] = self.node.h
                if self.node.attrs is not None:
                    out["attrs"] = self.node.attrs
                return out

            case AssignNode():
                out: Neo4jAssignNode = {**base, "path": self.node.path, "sl": self.node.sl, "el": self.node.el}
                if self.node.h is not None:
                    out["h"] = self.node.h
                if self.node.attrs is not None:
                    out["attrs"] = self.node.attrs
                return out

            case GenerateNode():
                out: Neo4jGenerateNode = {**base, "path": self.node.path, "sl": self.node.sl, "el": self.node.el}
                if self.node.name is not None:
                    out["name"] = self.node.name
                if self.node.attrs is not None:
                    out["attrs"] = self.node.attrs
                return out

            case FuncNode():
                out: Neo4jFuncNode = {
                    **base,
                    "name": self.node.name,
                    "path": self.node.path,
                    "sl": self.node.sl,
                    "el": self.node.el,
                }
                if self.node.h is not None:
                    out["h"] = self.node.h
                if self.node.attrs is not None:
                    out["attrs"] = self.node.attrs
                return out

            case ExprNode():
                out: Neo4jExprNode = {**base}
                if self.node.attrs is not None:
                    out["attrs"] = self.node.attrs
                return out

            case _:
                raise ValueError(f"Unknown node payload type: {type(self.node)}")


###############################################################################
#                               Edge models                                   #
###############################################################################


class KnowledgeGraphEdgeType(enum.StrEnum):
    """Enum of all KG edge types (Neo4j relationship types)."""

    contains = "CONTAINS"  # Repo -> File, File(dir) -> File
    defines = "DEFINES"  # File -> Module/Package
    includes = "INCLUDES"  # File -> File
    imports = "IMPORTS"  # Module/File -> Package

    instantiates = "INSTANTIATES"  # Module -> Instance
    of_module = "OF_MODULE"  # Instance -> Module

    has = "HAS"  # Module -> Port/Signal/Param/Always/Assign/Generate
    connects = "CONNECTS"  # Instance -> (Signal|Port|Expr)
    calls = "CALLS"  # (Assign|AlwaysBlock) -> Func

    drives = "DRIVES"  # (Assign|AlwaysBlock) -> (Signal|Port)   (LHS-only)


@dataclasses.dataclass(frozen=True)
class KnowledgeGraphEdge:
    """A generic edge with properties.

    Attributes:
      source: The source node.
      target: The target node.
      type: Relationship type.
      props: Relationship properties (must be JSON/Neo4j-property serializable).
    """

    source: KnowledgeGraphNode
    target: KnowledgeGraphNode
    type: KnowledgeGraphEdgeType
    props: Json | None = None

    def to_neo4j_edge(
        self,
    ) -> Union[
        "Neo4jContainsEdge",
        "Neo4jDefinesEdge",
        "Neo4jIncludesEdge",
        "Neo4jImportsEdge",
        "Neo4jInstantiatesEdge",
        "Neo4jOfModuleEdge",
        "Neo4jHasEdge",
        "Neo4jConnectsEdge",
        "Neo4jCallsEdge",
        "Neo4jDrivesEdge",
    ]:
        """Convert to a Neo4j edge property dict with embedded endpoints."""
        src = self.source.to_neo4j_node()
        dst = self.target.to_neo4j_node()
        p = self.props or {}

        match self.type:
            case KnowledgeGraphEdgeType.contains:
                edge: Neo4jContainsEdge = {"source": src, "target": dst, **p}
                return edge
            case KnowledgeGraphEdgeType.defines:
                edge: Neo4jDefinesEdge = {"source": src, "target": dst, **p}
                return edge
            case KnowledgeGraphEdgeType.includes:
                edge: Neo4jIncludesEdge = {"source": src, "target": dst, **p}
                return edge
            case KnowledgeGraphEdgeType.imports:
                edge: Neo4jImportsEdge = {"source": src, "target": dst, **p}
                return edge
            case KnowledgeGraphEdgeType.instantiates:
                edge: Neo4jInstantiatesEdge = {"source": src, "target": dst, **p}
                return edge
            case KnowledgeGraphEdgeType.of_module:
                edge: Neo4jOfModuleEdge = {"source": src, "target": dst, **p}
                return edge
            case KnowledgeGraphEdgeType.has:
                edge: Neo4jHasEdge = {"source": src, "target": dst, **p}
                return edge
            case KnowledgeGraphEdgeType.connects:
                edge: Neo4jConnectsEdge = {"source": src, "target": dst, **p}
                return edge
            case KnowledgeGraphEdgeType.calls:
                edge: Neo4jCallsEdge = {"source": src, "target": dst, **p}
                return edge
            case KnowledgeGraphEdgeType.drives:
                edge: Neo4jDrivesEdge = {"source": src, "target": dst, **p}
                return edge
            case _:
                raise ValueError(f"Unknown edge type: {self.type}")


###############################################################################
#                              Neo4j TypedDicts                                #
###############################################################################

# ---- Node TypedDicts ----

class Neo4jBaseNode(TypedDict, total=False):
    uid: Required[str]
    repo_uid: Required[str]
    kind: Required[str]
    name: NotRequired[str]
    path: NotRequired[str]
    sl: NotRequired[int]
    el: NotRequired[int]
    sc: NotRequired[int]
    ec: NotRequired[int]
    h: NotRequired[str]
    attrs: NotRequired[Json]


class Neo4jRepoNode(Neo4jBaseNode):
    kind: Required[Literal["Repo"]]
    name: Required[str]


class Neo4jFileNode(Neo4jBaseNode):
    kind: Required[Literal["File"]]
    name: Required[str]
    path: Required[str]


class Neo4jModuleNode(Neo4jBaseNode):
    kind: Required[Literal["Module"]]
    name: Required[str]
    path: Required[str]
    sl: Required[int]
    el: Required[int]


class Neo4jPackageNode(Neo4jBaseNode):
    kind: Required[Literal["Package"]]
    name: Required[str]
    path: Required[str]
    sl: Required[int]
    el: Required[int]


class Neo4jInstanceNode(Neo4jBaseNode):
    kind: Required[Literal["Instance"]]
    name: Required[str]
    path: Required[str]
    sl: Required[int]
    el: Required[int]


class Neo4jPortNode(Neo4jBaseNode):
    kind: Required[Literal["Port"]]
    name: Required[str]


class Neo4jSignalNode(Neo4jBaseNode):
    kind: Required[Literal["Signal"]]
    name: Required[str]


class Neo4jParamNode(Neo4jBaseNode):
    kind: Required[Literal["Param"]]
    name: Required[str]


class Neo4jAlwaysBlockNode(Neo4jBaseNode):
    kind: Required[Literal["AlwaysBlock"]]
    path: Required[str]
    sl: Required[int]
    el: Required[int]


class Neo4jAssignNode(Neo4jBaseNode):
    kind: Required[Literal["Assign"]]
    path: Required[str]
    sl: Required[int]
    el: Required[int]


class Neo4jGenerateNode(Neo4jBaseNode):
    kind: Required[Literal["Generate"]]
    path: Required[str]
    sl: Required[int]
    el: Required[int]


class Neo4jFuncNode(Neo4jBaseNode):
    kind: Required[Literal["Func"]]
    name: Required[str]
    path: Required[str]
    sl: Required[int]
    el: Required[int]


class Neo4jExprNode(Neo4jBaseNode):
    kind: Required[Literal["Expr"]]


Neo4jAnyNode = Union[
    Neo4jRepoNode,
    Neo4jFileNode,
    Neo4jModuleNode,
    Neo4jPackageNode,
    Neo4jInstanceNode,
    Neo4jPortNode,
    Neo4jSignalNode,
    Neo4jParamNode,
    Neo4jAlwaysBlockNode,
    Neo4jAssignNode,
    Neo4jGenerateNode,
    Neo4jFuncNode,
    Neo4jExprNode,
]


# ---- Edge TypedDicts ----

class Neo4jBaseEdge(TypedDict, total=False):
    source: Required[Neo4jAnyNode]
    target: Required[Neo4jAnyNode]
    eid: NotRequired[str]  # recommended relationship MERGE key


class Neo4jContainsEdge(Neo4jBaseEdge, total=False):
    order: NotRequired[int]


class Neo4jDefinesEdge(Neo4jBaseEdge, total=False):
    pass


class Neo4jIncludesEdge(Neo4jBaseEdge, total=False):
    raw: NotRequired[str]
    ok: NotRequired[bool]


class Neo4jImportsEdge(Neo4jBaseEdge, total=False):
    raw: NotRequired[str]


class Neo4jInstantiatesEdge(Neo4jBaseEdge, total=False):
    gen_path: NotRequired[str]


class Neo4jOfModuleEdge(Neo4jBaseEdge, total=False):
    conf: NotRequired[float]


class Neo4jHasEdge(Neo4jBaseEdge, total=False):
    k: Required[str]  # Port/Signal/Param/AlwaysBlock/Assign/Generate/Func


class Neo4jConnectsEdge(Neo4jBaseEdge, total=False):
    p: Required[str]  # formal port name
    by: NotRequired[Literal["named", "positional"]]
    ord: NotRequired[int]
    t: NotRequired[str]  # signal/port/expr/lit/unknown
    x: NotRequired[str]  # expr short text
    h: NotRequired[str]  # expr hash
    path: NotRequired[str]
    sl: NotRequired[int]
    el: NotRequired[int]


class Neo4jCallsEdge(Neo4jBaseEdge, total=False):
    cnt: NotRequired[int]


class Neo4jDrivesEdge(Neo4jBaseEdge, total=False):
    k: Required[Literal["nb", "blk", "cont", "mix"]]
    cnt: NotRequired[int]
    cond_hint: NotRequired[str]


###############################################################################
#                      Optional: uid/eid helper functions                      #
###############################################################################

def make_uid(*parts: str) -> str:
    """Join uid parts with ':' (caller ensures parts are normalized)."""
    return ":".join(parts)


def make_eid(*parts: str) -> str:
    """Join eid parts with ':' (caller ensures parts are normalized)."""
    return ":".join(parts)
