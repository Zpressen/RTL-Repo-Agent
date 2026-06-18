"""
RTL Knowledge Graph package.

Provides RTL source parsing (tree-sitter based), knowledge graph construction,
and Neo4j ingestion for Verilog/SystemVerilog repositories.

Core exports:
- KnowledgeGraphRTL: repo-level graph builder (traversal + cross-file resolution)
- RTLFileGraphBuilder: per-file tree-sitter parser
- compute_repo_uid: generate <repo_name>@<commit_sha> identity
- Neo4jConnection: Neo4j Bolt connection wrapper
- RTLNeo4jIngestor: bulk MERGE of nodes/edges into Neo4j
- RTLKgService / QueryRtlKgTool: service wrapper exports kept for migration compatibility
"""

from .rtl_knowledge_graph import KnowledgeGraphRTL, compute_repo_uid
from .neo4j_ingest import Neo4jConnection, RTLNeo4jIngestor
from .rtl_file_graph_builder import RTLFileGraphBuilder

__all__ = [
    "KnowledgeGraphRTL",
    "RTLFileGraphBuilder",
    "compute_repo_uid",
    "Neo4jConnection",
    "RTLNeo4jIngestor",
    "RTLKgService",
    "QueryRtlKgTool",
]


def __getattr__(name: str):
    if name in {"RTLKgService", "QueryRtlKgTool"}:
        from zerorepo.rtl_impl.rtl_kg_service import QueryRtlKgTool, RTLKgService

        return {"RTLKgService": RTLKgService, "QueryRtlKgTool": QueryRtlKgTool}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
