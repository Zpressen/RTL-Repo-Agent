from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from .schemas import ModuleSimulationStatus


class ModuleResultWriter:
    """Write module generation/debug results into the RTL KG."""

    STATUS_FILENAME = "rtl_kg_module_statuses.json"

    def __init__(
        self,
        *,
        kg_service: Any,
        workspace_root: str | Path,
        checkpoint_dir: str | Path,
        logger: Any | None = None,
    ) -> None:
        self.kg_service = kg_service
        self.workspace_root = Path(workspace_root)
        self.checkpoint_dir = Path(checkpoint_dir)
        self.logger = logger

    @property
    def status_path(self) -> Path:
        return self.checkpoint_dir / self.STATUS_FILENAME

    def record_module_result(
        self,
        *,
        module_name: str,
        merged_file: str | Path,
        debug_result: Any,
        stage: str = "post_module_debug",
        refresh_code: bool = True,
    ) -> ModuleSimulationStatus:
        status = self._build_status(module_name=module_name, debug_result=debug_result, stage=stage)
        payload = self._load_status_payload()
        modules = payload.setdefault("modules", {})
        records = payload.setdefault("records", {})
        status_payload = status.model_dump()
        modules[module_name] = status_payload
        records.setdefault(module_name, {})[stage] = status_payload
        self._write_status_payload(payload)

        if refresh_code:
            changed_path = self._relative_changed_path(Path(merged_file))
            self.kg_service.refresh_repo_files(
                changed_paths=[changed_path],
                stage=stage,
                filter_to_planned_skeleton=False,
            )
        self._ingest_simulation_statuses(records)
        return status

    def _build_status(self, *, module_name: str, debug_result: Any, stage: str) -> ModuleSimulationStatus:
        status = str(self._get(debug_result, "status", "error"))
        return ModuleSimulationStatus(
            module=module_name,
            status=status,
            passed=status in {"pass", "fixed"},
            mismatch_count=int(self._get(debug_result, "mismatch_count", 0) or 0),
            debug_trials=int(self._get(debug_result, "debug_trials", 0) or 0),
            final_rtl_path=str(self._get(debug_result, "final_rtl_path", "") or ""),
            trace_report_path=str(self._get(debug_result, "trace_report_path", "") or ""),
            sim_output_path=str(self._get(debug_result, "sim_output_path", "") or ""),
            reason=str(self._get(debug_result, "reason", "") or ""),
            stage=stage,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def _ingest_simulation_statuses(self, records: Dict[str, Dict[str, Dict[str, Any]]]) -> None:
        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []
        for module_name, by_stage in records.items():
            module_uid = self._lookup_module_uid(module_name)
            for stage, payload in by_stage.items():
                sim_uid = self._sim_uid(module_name, stage)
                node = {
                    "uid": sim_uid,
                    "repo_uid": self.kg_service.repo_uid,
                    "kind": "SimulationResult",
                    **payload,
                    "stage": stage,
                }
                nodes.append(node)
                if module_uid:
                    edges.append(
                        {
                            "uid": f"{self.kg_service.repo_uid}:has_sim_result:{module_name}:{stage}",
                            "repo_uid": self.kg_service.repo_uid,
                            "type": "HAS_SIM_RESULT",
                            "source_uid": module_uid,
                            "target_uid": sim_uid,
                            "stage": stage,
                        }
                    )

        self.kg_service.initialize()
        ingestor = getattr(self.kg_service, "_ingestor", None)
        if ingestor is None:
            raise RuntimeError("RTL KG ingestor is not initialized.")
        ingestor.ingest(nodes=nodes, edges=edges, mode="delta", repo_uid=self.kg_service.repo_uid)

    def _lookup_module_uid(self, module_name: str) -> str:
        result = self.kg_service.query(
            """
            MATCH (m:Module {repo_uid: $repo_uid, name: $module_name})
            RETURN m.uid AS module_uid
            """,
            {"module_name": module_name},
            limit=1,
        )
        rows = result.get("rows", [])
        if not rows:
            if self.logger is not None:
                self.logger.warning("[rtl_kg] Could not find Module node for %s", module_name)
            return ""
        return str(rows[0].get("module_uid", "") or "")

    def _load_statuses(self) -> Dict[str, Dict[str, Any]]:
        return self._load_status_payload().get("modules", {})

    def _load_status_payload(self) -> Dict[str, Dict[str, Any]]:
        if not self.status_path.exists():
            return {"modules": {}, "records": {}}
        try:
            with open(self.status_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception:
            return {"modules": {}, "records": {}}
        modules = payload.get("modules", {}) if isinstance(payload, dict) else {}
        if not isinstance(modules, dict):
            modules = {}
        modules = {str(key): value for key, value in modules.items() if isinstance(value, dict)}
        records_raw = payload.get("records", {}) if isinstance(payload, dict) else {}
        records: Dict[str, Dict[str, Dict[str, Any]]] = {}
        if isinstance(records_raw, dict):
            for module_name, by_stage in records_raw.items():
                if not isinstance(by_stage, dict):
                    continue
                stage_rows = {
                    str(stage): row
                    for stage, row in by_stage.items()
                    if isinstance(row, dict)
                }
                if stage_rows:
                    records[str(module_name)] = stage_rows
        for module_name, row in modules.items():
            stage = str(row.get("stage") or "post_module_debug")
            records.setdefault(module_name, {}).setdefault(stage, row)
        return {"modules": modules, "records": records}

    def _write_statuses(self, statuses: Dict[str, Dict[str, Any]]) -> None:
        self._write_status_payload({"modules": statuses, "records": {}})

    def _write_status_payload(self, payload: Dict[str, Dict[str, Any]]) -> None:
        self.status_path.parent.mkdir(parents=True, exist_ok=True)
        out = {
            "schema_version": "rtl_kg_module_statuses_v2",
            "repo_uid": self.kg_service.repo_uid,
            "modules": payload.get("modules", {}),
            "records": payload.get("records", {}),
        }
        tmp_path = self.status_path.with_name(f"{self.status_path.name}.tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
        tmp_path.replace(self.status_path)

    def _relative_changed_path(self, merged_file: Path) -> str:
        try:
            return str(merged_file.resolve().relative_to(Path(self.kg_service.repo_path).resolve()))
        except Exception:
            return merged_file.name

    def _sim_uid(self, module_name: str, stage: str) -> str:
        return f"{self.kg_service.repo_uid}:simulation_result:{module_name}:{stage}"

    def _get(self, obj: Any, key: str, default: Any = None) -> Any:
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)
