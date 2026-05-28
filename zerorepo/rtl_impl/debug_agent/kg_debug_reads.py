from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from .trace_slicer import RtlBlock, parse_rtl_blocks


BlockKey = Tuple[str, int, int]


@dataclass(frozen=True)
class DebugReadsMaterializationResult:
    session_id: str
    module: str
    related_modules: List[str] = field(default_factory=list)
    materialized_edges: int = 0
    hop_depth: int = 2
    current_uid_by_key: Dict[BlockKey, str] = field(default_factory=dict)
    fallback_reason: str = ""
    module_rows_count: int = 0
    matched_blocks_count: int = 0
    matched_symbols_count: int = 0
    skipped_modules: List[Dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class KGSliceResult:
    block_uids: List[str]
    rows: List[Dict[str, Any]]


class DebugReadsMaterializer:
    """Materialize session-scoped DEBUG_READS edges for RTL debug slicing."""

    SYMBOL_KINDS = {"Signal", "Port", "Param"}

    def __init__(self, kg_service: Any, logger: Any | None = None):
        self.kg_service = kg_service
        self.logger = logger

    def materialize(
        self,
        *,
        module_name: str,
        session_id: str,
        hop_depth: int = 2,
        current_rtl_path: str | Path | None = None,
        current_blocks: List[RtlBlock] | None = None,
    ) -> DebugReadsMaterializationResult:
        self._ensure_available()
        modules = self._related_modules(module_name=module_name, hop_depth=hop_depth)
        module_rows = self._module_rows(modules)
        edges: List[Dict[str, Any]] = []
        edge_uids_seen: set[str] = set()
        current_uid_by_key: Dict[BlockKey, str] = {}
        matched_block_uids: set[str] = set()
        matched_symbol_uids: set[str] = set()
        skipped_modules: List[Dict[str, Any]] = []

        for module in modules:
            row = module_rows.get(module)
            if row is None:
                skipped_modules.append(
                    {"module": module, "reason": "module_node_missing_or_parse_failed"}
                )
                continue
            blocks = self._blocks_for_module(
                module=module,
                module_row=row,
                current_module=module_name,
                current_rtl_path=current_rtl_path,
                current_blocks=current_blocks,
            )
            if not blocks:
                skipped_modules.append(
                    {"module": module, "reason": "no_rtl_blocks_or_source_missing"}
                )
                continue
            block_uids = self._kg_block_uids(module=module)
            if not block_uids:
                skipped_modules.append({"module": module, "reason": "no_kg_block_nodes"})
                continue
            read_names = sorted({name for block in blocks for name in block.reads if name})
            symbols = self._kg_symbols(module=module, names=read_names)
            if read_names and not symbols:
                skipped_modules.append({"module": module, "reason": "no_symbol_nodes_for_reads"})
                continue
            if not read_names:
                skipped_modules.append({"module": module, "reason": "no_read_symbols"})
                continue
            for block in blocks:
                block_kind = self._kg_block_kind(block)
                source_uid = block_uids.get((block_kind, int(block.start_line), int(block.end_line)))
                if not source_uid:
                    continue
                matched_block_uids.add(source_uid)
                if module == module_name:
                    current_uid_by_key[(block.kind, int(block.start_line), int(block.end_line))] = source_uid
                for read_name in block.reads:
                    target_uid = symbols.get(str(read_name))
                    if not target_uid:
                        continue
                    matched_symbol_uids.add(target_uid)
                    edge_uid = self._edge_uid(session_id, source_uid, target_uid, str(read_name))
                    if edge_uid in edge_uids_seen:
                        continue
                    edge_uids_seen.add(edge_uid)
                    edges.append(
                        {
                            "uid": edge_uid,
                            "type": "DEBUG_READS",
                            "repo_uid": self.kg_service.repo_uid,
                            "source_uid": source_uid,
                            "target_uid": target_uid,
                            "session_id": session_id,
                            "cnt": 1,
                            "role": "read",
                            "source_module": module,
                            "source_path": str(row.get("path") or ""),
                            "source_sl": int(block.start_line),
                            "source_el": int(block.end_line),
                        }
                    )

        if edges:
            ingestor = getattr(self.kg_service, "_ingestor", None)
            if ingestor is None:
                raise RuntimeError("RTL KG ingestor is not initialized.")
            ingestor.ingest(nodes=[], edges=edges, mode="delta", repo_uid=self.kg_service.repo_uid)

        return DebugReadsMaterializationResult(
            session_id=session_id,
            module=module_name,
            related_modules=list(modules),
            materialized_edges=len(edges),
            hop_depth=int(hop_depth),
            current_uid_by_key=current_uid_by_key,
            fallback_reason=self._diagnostic_reason(
                materialized_edges=len(edges),
                skipped_modules=skipped_modules,
                matched_blocks_count=len(matched_block_uids),
                matched_symbols_count=len(matched_symbol_uids),
            ),
            module_rows_count=len(module_rows),
            matched_blocks_count=len(matched_block_uids),
            matched_symbols_count=len(matched_symbol_uids),
            skipped_modules=skipped_modules,
        )

    def _diagnostic_reason(
        self,
        *,
        materialized_edges: int,
        skipped_modules: List[Dict[str, Any]],
        matched_blocks_count: int,
        matched_symbols_count: int,
    ) -> str:
        if materialized_edges > 0:
            return ""
        if skipped_modules:
            reasons = sorted({str(item.get("reason") or "") for item in skipped_modules if item.get("reason")})
            if reasons:
                return "DEBUG_READS materialization produced no edges: " + ", ".join(reasons)
        if matched_blocks_count <= 0:
            return "DEBUG_READS materialization produced no edges: no block line/kind matches."
        if matched_symbols_count <= 0:
            return "DEBUG_READS materialization produced no edges: no read symbol matches."
        return "DEBUG_READS materialization produced no edges."

    def _ensure_available(self) -> None:
        if self.kg_service is None:
            raise RuntimeError("RTL KG service is not available.")
        if not getattr(self.kg_service, "is_enabled", lambda: False)():
            raise RuntimeError("RTL KG service is disabled.")
        self.kg_service.initialize()

    def _related_modules(self, *, module_name: str, hop_depth: int) -> List[str]:
        seen = {module_name}
        frontier = {module_name}
        for _ in range(max(0, int(hop_depth))):
            if not frontier:
                break
            result = self.kg_service.query(
                """
                MATCH (m:Module)
                WHERE m.repo_uid = $repo_uid AND m.name IN $modules
                OPTIONAL MATCH (m)-[:INSTANTIATES]->(:Instance)-[:OF_MODULE]->(child:Module)
                OPTIONAL MATCH (parent:Module)-[:INSTANTIATES]->(:Instance)-[:OF_MODULE]->(m)
                RETURN collect(DISTINCT child.name) AS children,
                       collect(DISTINCT parent.name) AS parents
                """,
                {"repo_uid": self.kg_service.repo_uid, "modules": sorted(frontier)},
                limit=100,
            )
            next_frontier: set[str] = set()
            for row in result.get("rows", []) or []:
                for key in ("children", "parents"):
                    for name in row.get(key, []) or []:
                        name = str(name or "").strip()
                        if name and name not in seen:
                            seen.add(name)
                            next_frontier.add(name)
            frontier = next_frontier
        return sorted(seen, key=lambda item: (item != module_name, item))

    def _module_rows(self, modules: Iterable[str]) -> Dict[str, Dict[str, Any]]:
        result = self.kg_service.query(
            """
            MATCH (m:Module)
            WHERE m.repo_uid = $repo_uid AND m.name IN $modules
            RETURN m.name AS module, m.uid AS uid, m.path AS path, m.sl AS sl, m.el AS el
            """,
            {"repo_uid": self.kg_service.repo_uid, "modules": list(modules)},
            limit=100,
        )
        return {
            str(row.get("module")): row
            for row in result.get("rows", []) or []
            if row.get("module")
        }

    def _blocks_for_module(
        self,
        *,
        module: str,
        module_row: Dict[str, Any],
        current_module: str,
        current_rtl_path: str | Path | None,
        current_blocks: List[RtlBlock] | None,
    ) -> List[RtlBlock]:
        if module == current_module and current_blocks is not None:
            return current_blocks

        source_path: Path | None = None
        if module == current_module and current_rtl_path is not None:
            source_path = Path(current_rtl_path)
        if source_path is None:
            raw_path = str(module_row.get("path") or "").strip()
            if not raw_path:
                return []
            path = Path(raw_path)
            source_path = path if path.is_absolute() else (Path(self.kg_service.repo_path) / raw_path)
        if not source_path.exists():
            return []

        text = source_path.read_text(encoding="utf-8", errors="ignore").replace("\r\n", "\n")
        sl = self._as_int(module_row.get("sl"))
        el = self._as_int(module_row.get("el"))
        if sl is not None and el is not None and sl > 0 and el >= sl:
            lines = text.splitlines()
            snippet = "\n".join(lines[sl - 1 : el]) + "\n"
            blocks = parse_rtl_blocks(snippet)
            return [
                RtlBlock(
                    id=block.id,
                    kind=block.kind,
                    start_line=int(block.start_line) + sl - 1,
                    end_line=int(block.end_line) + sl - 1,
                    clocking=block.clocking,
                    code=block.code,
                    writes=block.writes,
                    reads=block.reads,
                )
                for block in blocks
            ]
        return parse_rtl_blocks(text)

    def _kg_block_uids(self, *, module: str) -> Dict[Tuple[str, int, int], str]:
        result = self.kg_service.query(
            """
            MATCH (m:Module {name: $module, repo_uid: $repo_uid})-[:HAS]->(b)
            WHERE b.kind IN ["AlwaysBlock", "Assign"]
            RETURN b.uid AS uid, b.kind AS kind, b.sl AS sl, b.el AS el
            """,
            {"repo_uid": self.kg_service.repo_uid, "module": module},
            limit=500,
        )
        out: Dict[Tuple[str, int, int], str] = {}
        for row in result.get("rows", []) or []:
            kind = str(row.get("kind") or "")
            sl = self._as_int(row.get("sl"))
            el = self._as_int(row.get("el"))
            uid = str(row.get("uid") or "")
            if kind and sl is not None and el is not None and uid:
                out[(kind, sl, el)] = uid
        return out

    def _kg_symbols(self, *, module: str, names: Iterable[str]) -> Dict[str, str]:
        names = sorted({str(name).strip() for name in names if str(name).strip()})
        if not names:
            return {}
        result = self.kg_service.query(
            """
            MATCH (m:Module {name: $module, repo_uid: $repo_uid})-[:HAS]->(sym)
            WHERE sym.kind IN ["Signal", "Port", "Param"] AND sym.name IN $names
            RETURN sym.name AS name, sym.uid AS uid, sym.kind AS kind
            """,
            {"repo_uid": self.kg_service.repo_uid, "module": module, "names": names},
            limit=max(100, len(names) * 3),
        )
        priority = {"Signal": 0, "Port": 1, "Param": 2}
        ranked: Dict[str, Tuple[int, str]] = {}
        for row in result.get("rows", []) or []:
            name = str(row.get("name") or "").strip()
            uid = str(row.get("uid") or "").strip()
            kind = str(row.get("kind") or "").strip()
            if not name or not uid or kind not in self.SYMBOL_KINDS:
                continue
            rank = priority.get(kind, 99)
            if name not in ranked or rank < ranked[name][0]:
                ranked[name] = (rank, uid)
        return {name: uid for name, (_rank, uid) in ranked.items()}

    def _kg_block_kind(self, block: RtlBlock) -> str:
        return "AlwaysBlock" if block.kind == "always" else "Assign"

    def _edge_uid(self, session_id: str, source_uid: str, target_uid: str, read_name: str) -> str:
        key = f"{self.kg_service.repo_uid}|DEBUG_READS|{session_id}|{source_uid}|{target_uid}|{read_name}"
        return hashlib.sha1(key.encode("utf-8")).hexdigest()

    def _as_int(self, value: Any) -> int | None:
        try:
            return int(value)
        except Exception:
            return None


def kg_dynamic_slice(
    *,
    kg_service: Any,
    module_name: str,
    fail_signals: Iterable[str],
    session_id: str,
    max_depth: int = 3,
) -> KGSliceResult:
    """Run a session-scoped KG backward slice using DRIVES and DEBUG_READS."""
    fail_names = sorted({str(item).strip() for item in fail_signals if str(item).strip()})
    if not fail_names:
        return KGSliceResult(block_uids=[], rows=[])

    start = kg_service.query(
        """
        MATCH (m:Module {name: $module, repo_uid: $repo_uid})-[:HAS]->(sym)
        WHERE sym.kind IN ["Signal", "Port", "Param"] AND sym.name IN $fail_signals
        RETURN sym.uid AS uid
        """,
        {"repo_uid": kg_service.repo_uid, "module": module_name, "fail_signals": fail_names},
        limit=200,
    )
    frontier = {str(row.get("uid")) for row in start.get("rows", []) or [] if row.get("uid")}
    seen_symbols = set(frontier)
    seen_blocks: Dict[str, Dict[str, Any]] = {}

    for _ in range(max(1, int(max_depth))):
        if not frontier:
            break
        driver_rows = kg_service.query(
            """
            MATCH (b)-[:DRIVES]->(sym)
            WHERE b.repo_uid = $repo_uid
              AND b.kind IN ["AlwaysBlock", "Assign"]
              AND sym.uid IN $symbol_uids
            RETURN DISTINCT b.uid AS uid, b.kind AS kind, b.path AS path, b.sl AS sl, b.el AS el
            """,
            {"repo_uid": kg_service.repo_uid, "symbol_uids": sorted(frontier)},
            limit=1000,
        ).get("rows", []) or []
        block_uids = [str(row.get("uid")) for row in driver_rows if row.get("uid")]
        for row in driver_rows:
            uid = str(row.get("uid") or "")
            if uid:
                seen_blocks[uid] = row
        if not block_uids:
            break
        read_rows = kg_service.query(
            """
            MATCH (b)-[r:DEBUG_READS]->(sym)
            WHERE b.repo_uid = $repo_uid
              AND b.uid IN $block_uids
              AND r.session_id = $session_id
            RETURN DISTINCT sym.uid AS uid
            """,
            {"repo_uid": kg_service.repo_uid, "block_uids": block_uids, "session_id": session_id},
            limit=2000,
        ).get("rows", []) or []
        next_frontier = {
            str(row.get("uid"))
            for row in read_rows
            if row.get("uid") and str(row.get("uid")) not in seen_symbols
        }
        seen_symbols.update(next_frontier)
        frontier = next_frontier

    if not seen_blocks:
        return KGSliceResult(block_uids=[], rows=[])

    rows = kg_service.query(
        """
        MATCH (b)
        WHERE b.repo_uid = $repo_uid
          AND b.uid IN $block_uids
          AND b.kind IN ["AlwaysBlock", "Assign"]
        RETURN b.uid AS uid,
               b.kind AS kind,
               b.path AS path,
               b.sl AS sl,
               b.el AS el,
               [(b)-[:DRIVES]->(w) | w.name] AS writes,
               [(b)-[rr:DEBUG_READS]->(rd) WHERE rr.session_id = $session_id | rd.name] AS reads
        """,
        {"repo_uid": kg_service.repo_uid, "block_uids": sorted(seen_blocks), "session_id": session_id},
        limit=1000,
    ).get("rows", []) or []
    return KGSliceResult(block_uids=sorted(seen_blocks), rows=rows)


def kg_debug_session_id(module_name: str) -> str:
    import time

    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    digest = hashlib.sha1(f"{module_name}:{stamp}:{time.time_ns()}".encode("utf-8")).hexdigest()[:10]
    return f"{module_name}:{stamp}:{digest}"


def parse_json_attrs(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}
