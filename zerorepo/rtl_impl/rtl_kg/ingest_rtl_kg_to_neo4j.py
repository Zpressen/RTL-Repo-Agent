#!/usr/bin/env python3
"""
CLI: Build RTL KG and ingest into Neo4j (Docker-friendly).

Usage (run from repo root):
  python -m zerorepo.rtl_impl.rtl_kg.ingest_rtl_kg_to_neo4j \
    --repo /path/to/rtl/repo \
    --neo4j-uri bolt://localhost:7687 \
    --neo4j-user neo4j \
    --neo4j-pass neo4j123456 \
    --mode full

Or run directly:
  python zerorepo/rtl_impl/rtl_kg/ingest_rtl_kg_to_neo4j.py \
    --repo /path/to/rtl/repo ...

Notes:
- Requires: pip install neo4j
- Neo4j must be running (see docker-compose.dev.yml in this directory)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Support both direct execution and module execution
try:
    from .neo4j_ingest import Neo4jConnection, RTLNeo4jIngestor
    from .rtl_knowledge_graph import KnowledgeGraphRTL
except ImportError:
    # Direct execution fallback — add repo root to path
    _repo_root = Path(__file__).resolve().parents[3]
    if str(_repo_root) not in sys.path:
        sys.path.insert(0, str(_repo_root))
    from zerorepo.rtl_impl.rtl_kg.neo4j_ingest import Neo4jConnection, RTLNeo4jIngestor
    from zerorepo.rtl_impl.rtl_kg.rtl_knowledge_graph import KnowledgeGraphRTL


def build_kg(repo: Path):
    # KnowledgeGraphRTL is imported at the top of the file (supports both
    # module-level and direct execution).
    kg = KnowledgeGraphRTL.build(repo)
    # Prefer kg.repo_uid; fallback to whatever your builder returns.
    repo_uid = getattr(kg, "repo_uid", None) or getattr(kg, "uid", None)
    nodes = kg.neo4j_nodes()
    edges = kg.neo4j_edges()
    return repo_uid, nodes, edges


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="Path to RTL repo root")
    ap.add_argument("--neo4j-uri", default="bolt://localhost:7687")
    ap.add_argument("--neo4j-user", default="neo4j")
    ap.add_argument("--neo4j-pass", default="neo4j")
    ap.add_argument("--mode", choices=["full", "delta"], default="delta")
    ap.add_argument("--batch-size", type=int, default=2000)
    args = ap.parse_args()

    repo = Path(args.repo).expanduser().resolve()
    if not repo.exists():
        raise SystemExit(f"Repo path not found: {repo}")

    repo_uid, nodes, edges = build_kg(repo)

    conn = Neo4jConnection(uri=args.neo4j_uri, user=args.neo4j_user, password=args.neo4j_pass)
    ing = RTLNeo4jIngestor(conn, batch_size=args.batch_size)

    ing.ingest(nodes=nodes, edges=edges, mode=args.mode, repo_uid=repo_uid)
    print("[done] Neo4j ingestion complete.")


if __name__ == "__main__":
    main()
