from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from zerorepo.config.checkpoint_config import CheckpointManager
from zerorepo.rtl_impl.debug_agent.sim_reviewer import check_syntax
from zerorepo.rtl_impl.debug_agent.system_debug_runner import SystemSimReviewer
from zerorepo.rtl_impl.debug_agent.trace_report import build_trace_report
from zerorepo.rtl_impl.repo_react.journal import RepoReActJournal
from zerorepo.rtl_impl.repo_react.schemas import RepoReActInput, SimSnapshot
from zerorepo.rtl_impl.repo_react.tools import (
    RepoReActTools,
    RepoReActToolState,
    _extract_first_fail_time,
    _metric_delta,
    _parse_sim_metrics,
    _summarize_command_json,
)
from zerorepo.rtl_impl.rtl_kg import RTLKgService

from .schemas import CodexDebugRunDescriptor


SessionPhase = Literal["clean_accepted", "dirty_unvalidated", "pending_validated"]
ValidationAction = Literal["evaluate", "accept", "rollback"]


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


@dataclass
class CandidateState:
    candidate_id: str
    revision: int = 0
    evaluated_manifest: dict[str, str] = field(default_factory=dict)
    lint_pass: bool = False
    sim_completed: bool = False
    result: dict[str, Any] = field(default_factory=dict)
    artifact_root: Path | None = None


class CodexDebugSession:
    """Stateful tool backend for one run-scoped Codex RTL debug session.

    Codex edits ``merged_root`` with its native tools.  This class owns the
    accepted baseline, validation trials, dynamic evidence, rollback, and the
    RepoReAct read/debug tools.
    """

    def __init__(
        self,
        descriptor: CodexDebugRunDescriptor,
        *,
        reviewer: Any | None = None,
        kg_service: Any | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.descriptor = descriptor
        self.logger = logger or logging.getLogger(__name__)
        self._lock = threading.RLock()
        self._closed = False
        self.readonly_calls = 0
        self.validation_trials = 0
        self.accepted_actions = 0
        self.baseline_revision = 0
        self.candidate: CandidateState | None = None
        self.last_validation: dict[str, Any] = {}
        self.kg_error = ""

        self.task_root = descriptor.task_root.resolve()
        self.spec_root = descriptor.spec_root.resolve()
        self.merged_root = descriptor.merged_root.resolve()
        self.private_root = descriptor.private_root.resolve()
        self.debug_workdir = descriptor.debug_workdir.resolve()
        self.baseline_root = self.private_root / "accepted_baseline"
        self.baseline_rtl_root = self.baseline_root / "merged"
        self.baseline_artifact_root = self.baseline_root / "artifacts"
        self.candidates_root = self.private_root / "candidates"
        self.journal_root = self.private_root / "journal"
        self.session_state_path = self.private_root / "session_state.json"
        for root in (
            self.debug_workdir,
            self.baseline_rtl_root,
            self.baseline_artifact_root,
            self.candidates_root,
            self.journal_root,
        ):
            root.mkdir(parents=True, exist_ok=True)

        self._spec_manifest = self._manifest(self.spec_root, allow_symlinks=False)
        self._validate_merged_tree()
        persisted = self._load_persistent_state()
        if persisted is None:
            self._replace_tree(self.merged_root, self.baseline_rtl_root)
            self.accepted_manifest = self._manifest(self.merged_root, allow_symlinks=False)
        else:
            self._restore_persistent_counters(persisted)
            self.accepted_manifest = self._validate_persistent_baseline(persisted)
            if self._manifest(self.merged_root, allow_symlinks=False) != self.accepted_manifest:
                self._replace_tree(self.baseline_rtl_root, self.merged_root)

        if reviewer is None and descriptor.verify_script is not None:
            reviewer = SystemSimReviewer(
                generated_dir=self.merged_root,
                verify_script=descriptor.verify_script,
                output_dir=self.debug_workdir,
                timeout=descriptor.verifier_timeout,
            )
        self.reviewer = reviewer

        if kg_service is None and descriptor.kg.enabled:
            try:
                kg_service = self._build_run_kg_service()
            except Exception as exc:  # noqa: BLE001
                self.kg_error = f"{type(exc).__name__}: {exc}"
                self.logger.warning("Codex Debug KG unavailable: %s", self.kg_error)
                kg_service = None
        self.kg_service = kg_service

        initial_sim_output = descriptor.read_initial_sim_output()
        if persisted is not None:
            initial_sim_output = str(persisted.get("accepted_sim_output") or "")
        initial_first_fail = _extract_first_fail_time(initial_sim_output)
        self.journal = RepoReActJournal(self.journal_root)
        repo_input = RepoReActInput(
            module_name=descriptor.planner_module_name,
            top_module=descriptor.top_module,
            repair_scope="repo",
            repair_mode="functional",
            workspace_root=self.private_root / "workspace",
            debug_workdir=self.debug_workdir,
            rtl_path=descriptor.top_rtl.resolve(),
            merged_file=descriptor.top_rtl.resolve(),
            rtl_root=self.merged_root,
            verify_dir=None,
            verify_script=None,
            output_root=descriptor.planning_output_root,
            repo_root=None,
            spec_text=descriptor.spec_text,
            spec_source_path=str(descriptor.spec_paths[0]) if descriptor.spec_paths else "",
            spec_paths=[str(path) for path in descriptor.spec_paths],
            contract_json=descriptor.contract_json,
            sim_failed_log=initial_sim_output,
            initial_mismatch_count=descriptor.initial_mismatch_count,
            max_steps=descriptor.max_validation_trials,
            kg_hop_depth=descriptor.kg_hop_depth,
        )
        self.state = RepoReActToolState(
            input=repo_input,
            sim_reviewer=reviewer,
            journal=self.journal,
            kg_service=kg_service,
            logger=self.logger,
            last_sim=SimSnapshot(
                is_pass=False,
                mismatch_count=descriptor.initial_mismatch_count,
                first_fail_time=initial_first_fail,
                sim_output_path=str(self.debug_workdir / "initial_sim_output.json"),
            ),
            last_sim_output=initial_sim_output,
        )
        self.tools = RepoReActTools(self.state)
        if persisted is None:
            self.accepted_sim = self.state.last_sim.model_copy(deep=True)
            self.accepted_sim_output = initial_sim_output
            if initial_sim_output:
                (self.debug_workdir / "initial_sim_output.json").write_text(initial_sim_output, encoding="utf-8")
            if descriptor.initial_wave_path and descriptor.initial_wave_path.is_file():
                shutil.copy2(descriptor.initial_wave_path, self.debug_workdir / "wave.vcd")
            self._build_initial_trace()
            self._snapshot_artifacts(self.baseline_artifact_root)
        else:
            self.accepted_sim = SimSnapshot.model_validate(persisted.get("accepted_sim") or {})
            self.accepted_sim_output = initial_sim_output
            self.state.last_sim = self.accepted_sim.model_copy(deep=True)
            self.state.last_sim_output = self.accepted_sim_output
            self.required_initial_trace = dict(persisted.get("initial_trace_hint") or {})
            self.initial_trace_completed = bool(persisted.get("initial_trace_observed"))
            self._restore_artifacts(self.baseline_artifact_root)
            self._restore_state_from_baseline_artifacts()
        self._write_status()

    # ------------------------------------------------------------------
    # Construction and filesystem policy
    # ------------------------------------------------------------------

    @classmethod
    def from_descriptor_path(
        cls,
        path: str | Path,
        *,
        reviewer: Any | None = None,
        kg_service: Any | None = None,
        logger: logging.Logger | None = None,
    ) -> "CodexDebugSession":
        descriptor = CodexDebugRunDescriptor.model_validate_json(Path(path).read_text(encoding="utf-8"))
        return cls(descriptor, reviewer=reviewer, kg_service=kg_service, logger=logger)

    def _build_run_kg_service(self) -> Any:
        cfg = self.descriptor.kg
        checkpoint_dir = cfg.checkpoint_dir or (self.private_root / "kg_checkpoint")
        service = RTLKgService(
            repo_path=self.merged_root,
            checkpoint_manager=CheckpointManager(checkpoint_dir),
            repo_data={},
            config=cfg.config,
            logger=self.logger,
        )
        service.initialize()
        service.refresh_repo_files(
            changed_paths=[str(path) for path in self._rtl_files()],
            stage="codex_debug_initial",
            filter_to_planned_skeleton=False,
        )
        if cfg.planning_projection_path and cfg.planning_projection_path.is_file():
            projection = json.loads(cfg.planning_projection_path.read_text(encoding="utf-8"))
            old_uid = str(projection.get("repo_uid") or "")
            nodes = [self._remap_projection_value(dict(item), old_uid, service.repo_uid) for item in projection.get("nodes") or []]
            edges = [self._remap_projection_value(dict(item), old_uid, service.repo_uid) for item in projection.get("edges") or []]
            service.upsert_planning_projection(nodes, edges)
        return service

    def _load_persistent_state(self) -> dict[str, Any] | None:
        if not self.session_state_path.is_file():
            return None
        try:
            value = json.loads(self.session_state_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"Codex Debug persistent state is unreadable: {exc}") from exc
        if not isinstance(value, dict) or value.get("schema_version") != 1:
            raise ValueError("Codex Debug persistent state has an unsupported schema")
        if value.get("run_id") != self.descriptor.run_id:
            raise ValueError("Codex Debug persistent state belongs to another run")
        persisted_spec = value.get("spec_manifest")
        if not isinstance(persisted_spec, dict) or persisted_spec != self._spec_manifest:
            raise ValueError("Codex Debug spec changed since the persisted session")
        return value

    def _restore_persistent_counters(self, value: dict[str, Any]) -> None:
        counters = value.get("counters")
        if not isinstance(counters, dict):
            raise ValueError("Codex Debug persistent counters are missing")
        self.readonly_calls = max(0, int(counters.get("readonly_calls") or 0))
        self.validation_trials = max(0, int(counters.get("validation_trials") or 0))
        self.accepted_actions = max(0, int(counters.get("accepted_actions") or 0))
        self.baseline_revision = max(0, int(value.get("baseline_revision") or 0))
        if self.validation_trials > self.descriptor.max_validation_trials:
            raise ValueError("Persisted validation trials exceed the configured budget")
        last_validation = value.get("last_validation")
        self.last_validation = dict(last_validation) if isinstance(last_validation, dict) else {}

    def _validate_persistent_baseline(self, value: dict[str, Any]) -> dict[str, str]:
        manifest = value.get("accepted_manifest")
        if not isinstance(manifest, dict) or not all(
            isinstance(path, str) and isinstance(digest, str) for path, digest in manifest.items()
        ):
            raise ValueError("Codex Debug accepted manifest is invalid")
        if not self.baseline_rtl_root.is_dir():
            raise ValueError("Codex Debug accepted baseline is missing")
        actual = self._manifest(self.baseline_rtl_root, allow_symlinks=False)
        if actual != manifest:
            raise ValueError("Codex Debug accepted baseline does not match persistent state")
        return dict(manifest)

    @classmethod
    def _remap_projection_value(cls, value: Any, old_uid: str, new_uid: str) -> Any:
        if isinstance(value, dict):
            remapped = {key: cls._remap_projection_value(item, old_uid, new_uid) for key, item in value.items()}
            if "repo_uid" in remapped:
                remapped["repo_uid"] = new_uid
            return remapped
        if isinstance(value, list):
            return [cls._remap_projection_value(item, old_uid, new_uid) for item in value]
        if isinstance(value, str) and old_uid and value.startswith(old_uid):
            return new_uid + value[len(old_uid) :]
        return value

    def _rtl_files(self) -> list[Path]:
        return sorted(
            [path for path in self.merged_root.rglob("*") if path.is_file() and path.suffix.lower() in {".v", ".sv"}],
            key=lambda path: path.relative_to(self.merged_root).as_posix(),
        )

    def _validate_merged_tree(self) -> None:
        if not self.merged_root.is_dir():
            raise ValueError(f"merged_root does not exist: {self.merged_root}")
        if not _is_under(self.descriptor.top_rtl, self.merged_root):
            raise ValueError("top RTL is outside merged_root")
        for path in self.merged_root.rglob("*"):
            if path.is_symlink():
                raise ValueError(f"symlinks are forbidden in merged_root: {path}")
            if path.is_file() and path.suffix.lower() not in {".v", ".sv"}:
                raise ValueError(f"non-RTL files are forbidden in merged_root: {path}")

    def _manifest(self, root: Path, *, allow_symlinks: bool) -> dict[str, str]:
        manifest: dict[str, str] = {}
        if not root.exists():
            return manifest
        for path in sorted(root.rglob("*")):
            if path.is_symlink() and not allow_symlinks:
                raise ValueError(f"symlink is not allowed: {path}")
            if not path.is_file():
                continue
            resolved = path.resolve()
            if not _is_under(resolved, root):
                raise ValueError(f"path escapes root: {path}")
            manifest[path.relative_to(root).as_posix()] = _sha256_file(path)
        return manifest

    def _replace_tree(self, source: Path, target: Path) -> None:
        target.mkdir(parents=True, exist_ok=True)
        for path in sorted(target.rglob("*"), reverse=True):
            if path.is_file() or path.is_symlink():
                path.unlink()
            elif path.is_dir():
                try:
                    path.rmdir()
                except OSError:
                    pass
        for source_path in sorted(source.rglob("*")):
            relative = source_path.relative_to(source)
            target_path = target / relative
            if source_path.is_dir():
                target_path.mkdir(parents=True, exist_ok=True)
            elif source_path.is_file():
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_path, target_path)

    def _spec_unchanged(self) -> bool:
        try:
            return self._manifest(self.spec_root, allow_symlinks=False) == self._spec_manifest
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Session state and evidence
    # ------------------------------------------------------------------

    def _build_initial_trace(self) -> None:
        try:
            report, _blocks = build_trace_report(
                rtl_path=self.state.input.rtl_path,
                sim_log_json=self.state.last_sim_output,
                output_dir=self.debug_workdir,
                planner_module_name=self.state.input.module_name,
                runtime_top_module=self.state.input.top_module or self.state.input.module_name,
                kg_service=self.kg_service,
                kg_hop_depth=self.state.input.kg_hop_depth,
            )
        except Exception as exc:  # noqa: BLE001
            report = {"trace_error": f"{type(exc).__name__}: {exc}"}
        self._atomic_write_json(self.debug_workdir / "trace_report.json", report)
        divergence = report.get("first_divergence") if isinstance(report, dict) else {}
        divergence = divergence if isinstance(divergence, dict) else {}
        first = divergence.get("first_divergence") if isinstance(divergence.get("first_divergence"), dict) else {}
        required: dict[str, Any] = {}
        if first.get("signal") not in (None, "") and first.get("time") is not None:
            required = {
                "module_name": str(report.get("runtime_top_module") or self.state.input.top_module or self.state.input.module_name),
                "signal_name": str(first.get("signal")),
                "time": int(first.get("time")),
                "expected_value": None if first.get("ref") is None else str(first.get("ref")),
            }
        self.required_initial_trace = required
        self.initial_trace_completed = not bool(required)
        self.state.last_trace_summary = {
            "root_module": report.get("runtime_top_module") if isinstance(report, dict) else self.state.input.top_module,
            "root_signal": first.get("signal"),
            "first_divergence_time": first.get("time"),
            "expected_value": first.get("ref"),
            "actual_value": first.get("dut"),
            "sampling_event": divergence.get("sampling_event"),
            "suggested_tool": "trace_signal_cause" if required else None,
            "arguments": required,
        }
        self.state.last_divergence_summary = divergence

    def _current_manifest(self) -> dict[str, str]:
        self._validate_merged_tree()
        return self._manifest(self.merged_root, allow_symlinks=False)

    def _phase(self) -> SessionPhase:
        try:
            current = self._current_manifest()
        except Exception:
            return "dirty_unvalidated"
        if self.candidate is not None and current == self.candidate.evaluated_manifest:
            return "pending_validated"
        if current == self.accepted_manifest:
            return "clean_accepted"
        return "dirty_unvalidated"

    def _evidence_revision(self) -> dict[str, Any]:
        phase = self._phase()
        if phase == "pending_validated" and self.candidate is not None:
            return {
                "source": "validated_candidate",
                "baseline_revision": self.baseline_revision,
                "candidate_id": self.candidate.candidate_id,
                "candidate_revision": self.candidate.revision,
            }
        return {"source": "accepted_baseline", "baseline_revision": self.baseline_revision}

    def _consume_read(self, tool: str) -> None:
        del tool
        self.readonly_calls += 1
        self._persist_session_state()

    def _dynamic_evidence_guard(self, tool: str) -> dict[str, Any] | None:
        phase = self._phase()
        if phase == "dirty_unvalidated":
            return {
                "status": "dirty_workspace_requires_validation",
                "tool": tool,
                "message": "RTL changed after the last validation; call validate_rtl_changes(action='evaluate').",
            }
        if phase == "pending_validated" and self.candidate is not None and not self.candidate.sim_completed:
            return {
                "status": "candidate_dynamic_evidence_unavailable",
                "tool": tool,
                "candidate_id": self.candidate.candidate_id,
                "candidate_revision": self.candidate.revision,
                "message": "The pending candidate has no completed simulation evidence.",
            }
        return None

    def _snapshot_artifacts(self, target: Path) -> None:
        target.mkdir(parents=True, exist_ok=True)
        for name in ("wave.vcd", "trace_report.json", "debug_sim_output.json", "initial_sim_output.json"):
            source = self.debug_workdir / name
            if source.is_file():
                shutil.copy2(source, target / name)

    def _restore_artifacts(self, source: Path) -> None:
        for name in ("wave.vcd", "trace_report.json", "debug_sim_output.json", "initial_sim_output.json"):
            target = self.debug_workdir / name
            if target.exists():
                target.unlink()
            saved = source / name
            if saved.is_file():
                shutil.copy2(saved, target)

    def _write_status(self) -> None:
        payload = self.get_debug_status(count_read=False)
        self._persist_status(payload)
        self._persist_session_state()

    def _persist_status(self, payload: dict[str, Any]) -> None:
        self._atomic_write_json(self.private_root / "debug_status.json", payload)

    def _persist_session_state(self) -> None:
        if not hasattr(self, "accepted_manifest") or not hasattr(self, "accepted_sim"):
            return
        payload = {
            "schema_version": 1,
            "run_id": self.descriptor.run_id,
            "spec_manifest": self._spec_manifest,
            "accepted_manifest": self.accepted_manifest,
            "baseline_revision": self.baseline_revision,
            "counters": {
                "readonly_calls": self.readonly_calls,
                "validation_trials": self.validation_trials,
                "accepted_actions": self.accepted_actions,
            },
            "accepted_sim": self.accepted_sim.model_dump(mode="json"),
            "accepted_sim_output": self.accepted_sim_output,
            "last_validation": self.last_validation,
            "initial_trace_hint": self.required_initial_trace,
            "initial_trace_observed": self.initial_trace_completed,
        }
        self._atomic_write_json(self.session_state_path, payload)

    @staticmethod
    def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
        temporary = path.with_name(f".{path.name}.tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.chmod(0o600)
        temporary.replace(path)

    # ------------------------------------------------------------------
    # Read/debug tool facade
    # ------------------------------------------------------------------

    def read_module_semantics(
        self,
        module_name: str,
        sections: list[str] | None = None,
        focus_signals: list[str] | None = None,
        focus_blocks: list[str] | None = None,
        max_chars: int = 12000,
    ) -> dict[str, Any]:
        with self._lock:
            blocked = self._consume_read("read_module_semantics")
            if blocked:
                return blocked
            max_chars = max(1000, min(int(max_chars), 40000))
            result = self.tools.read_module_semantics(
                module_name,
                sections,
                focus_signals,
                focus_blocks,
                max_chars,
            )
            result["rtl_revision"] = {
                **self._evidence_revision(),
                "workspace_phase": self._phase(),
                "kg_stale_for_candidate": self._phase() != "clean_accepted",
            }
            return self._public_result(result)

    def query_rtl_kg(
        self,
        query_type: Literal["module_interface", "module_instances", "instance_connections", "signal_drivers"],
        module_name: str,
        signal_name: str | None = None,
        instance_name: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            blocked = self._consume_read("query_rtl_kg")
            if blocked:
                return blocked
            result = self.tools.query_rtl_kg(query_type, module_name, signal_name, instance_name)
            result["kg_revision"] = {
                "baseline_revision": self.baseline_revision,
                "stale_for_candidate": self._phase() != "clean_accepted",
            }
            if self.kg_error:
                result["kg_error"] = self.kg_error
            return self._public_result(result)

    def trace_signal_cause(
        self,
        module_name: str,
        signal_name: str,
        time: int | None = None,
        expected_value: str | None = None,
        max_candidates: int = 5,
    ) -> dict[str, Any]:
        with self._lock:
            blocked = self._consume_read("trace_signal_cause") or self._dynamic_evidence_guard("trace_signal_cause")
            if blocked:
                return blocked
            result = self.tools.trace_signal_cause(module_name, signal_name, time, expected_value, max_candidates)
            if self.required_initial_trace and not self.initial_trace_completed:
                requested = {
                    "module_name": module_name,
                    "signal_name": signal_name,
                    "time": time,
                    "expected_value": expected_value,
                }
                required = self.required_initial_trace
                matches = all(requested.get(key) == required.get(key) for key in required)
                if matches and str(result.get("status") or "") in {"ok", "static_only"}:
                    self.initial_trace_completed = True
                    result["initial_trace_hint"] = {"status": "observed"}
                    self._persist_session_state()
                else:
                    result["initial_trace_hint"] = {
                        "status": "available",
                        "arguments": required,
                    }
            result["evidence_revision"] = self._evidence_revision()
            return self._public_result(result)

    def list_vcd_signals(self, pattern: str = "", scope: str = "", limit: int = 100) -> dict[str, Any]:
        with self._lock:
            blocked = self._consume_read("list_vcd_signals") or self._dynamic_evidence_guard("list_vcd_signals")
            if blocked:
                return blocked
            result = self.tools.list_vcd_signals(pattern, scope, max(1, min(int(limit), 500)))
            result["evidence_revision"] = self._evidence_revision()
            return self._public_result(result)

    def probe_vcd(
        self,
        signals: list[str],
        time: int | None = None,
        time_range: list[int] | None = None,
        edge: str | None = None,
        mode: Literal["sample", "changes"] = "sample",
        max_rows: int = 80,
    ) -> dict[str, Any]:
        with self._lock:
            blocked = self._consume_read("probe_vcd") or self._dynamic_evidence_guard("probe_vcd")
            if blocked:
                return blocked
            result = self.tools.probe_vcd(signals, time, time_range, edge, mode, max(1, min(int(max_rows), 500)))
            result["evidence_revision"] = self._evidence_revision()
            return self._public_result(result)

    def run_check(
        self,
        mode: Literal["lint", "top_sim", "trace_summary", "first_divergence"],
        signals: list[str] | None = None,
        time_window: list[int] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            blocked = self._consume_read("run_check")
            if blocked:
                return blocked
            phase = self._phase()
            if mode in {"lint", "top_sim"} and phase != "clean_accepted":
                return {
                    "status": "dirty_workspace_requires_validation",
                    "mode": mode,
                    "phase": phase,
                    "message": "Use validate_rtl_changes(action='evaluate') for feedback on edited RTL.",
                }
            if mode in {"trace_summary", "first_divergence"}:
                dynamic_block = self._dynamic_evidence_guard("run_check")
                if dynamic_block:
                    return dynamic_block
            window = tuple(time_window) if time_window is not None else None
            result = self.tools.run_check(mode, None, signals, window)
            if mode == "top_sim" and self._phase() == "clean_accepted":
                self.accepted_sim = self.state.last_sim.model_copy(deep=True)
                self.accepted_sim_output = self.state.last_sim_output
                self._snapshot_artifacts(self.baseline_artifact_root)
                self._write_status()
            result["evidence_revision"] = self._evidence_revision()
            return self._public_result(result)

    # ------------------------------------------------------------------
    # Transactional validation
    # ------------------------------------------------------------------

    def validate_rtl_changes(
        self,
        action: ValidationAction,
        candidate_id: str | None = None,
        reason: str = "",
        expected_effect: str = "",
    ) -> dict[str, Any]:
        with self._lock:
            if action == "evaluate":
                return self._evaluate_changes(reason=reason, expected_effect=expected_effect)
            if action == "accept":
                return self._accept_candidate(candidate_id)
            return self._rollback_candidate(candidate_id)

    def _evaluate_changes(self, *, reason: str, expected_effect: str) -> dict[str, Any]:
        if not self._spec_unchanged():
            return {
                "status": "security_violation",
                "reason": "The read-only spec tree changed; abort this run.",
            }
        try:
            current_manifest = self._current_manifest()
        except Exception as exc:  # noqa: BLE001
            self._restore_baseline()
            return {
                "status": "security_violation",
                "reason": f"Invalid merged tree: {type(exc).__name__}: {exc}",
                "restored": True,
            }
        if current_manifest == self.accepted_manifest:
            self.candidate = None
            return {"status": "no_changes", "baseline_revision": self.baseline_revision}
        if self.validation_trials >= self.descriptor.max_validation_trials:
            return {
                "status": "validation_budget_exhausted",
                "validation_trials": self.validation_trials,
                "max_validation_trials": self.descriptor.max_validation_trials,
            }
        self.validation_trials += 1
        # Persist immediately so a verifier crash or killed MCP process cannot
        # reset and silently reuse a consumed validation trial on resume.
        self._persist_session_state()
        if self.candidate is None:
            self.candidate = CandidateState(candidate_id=f"candidate_{uuid.uuid4().hex[:12]}")
        self.candidate.revision += 1
        self.candidate.evaluated_manifest = current_manifest
        candidate_id = self.candidate.candidate_id
        revision = self.candidate.revision
        candidate_root = self.candidates_root / candidate_id / f"revision_{revision:03d}"
        candidate_rtl_root = candidate_root / "merged"
        candidate_artifact_root = candidate_root / "artifacts"
        self._replace_tree(self.merged_root, candidate_rtl_root)
        top_relative = self.descriptor.top_rtl.resolve().relative_to(self.merged_root)
        candidate_top_rtl = candidate_rtl_root / top_relative

        before_snapshot = self.accepted_sim.model_copy(deep=True)
        before_sim_output = self.accepted_sim_output
        before_metrics = _parse_sim_metrics(before_sim_output)
        result: dict[str, Any] = {
            "status": "evaluated",
            "candidate_id": candidate_id,
            "candidate_revision": revision,
            "reason": reason,
            "expected_effect": expected_effect,
            "validation_trial": self.validation_trials,
            "diff": self._diff_summary(self.accepted_manifest, current_manifest),
            "before": {
                "is_pass": before_snapshot.is_pass,
                "mismatch_count": before_snapshot.mismatch_count,
                "first_fail_time": before_snapshot.first_fail_time,
            },
        }
        try:
            lint_ok, lint_output = check_syntax(
                str(candidate_top_rtl),
                top_module=self.state.input.top_module or self.state.input.module_name,
            )
            result["lint_pass"] = bool(lint_ok)
            result["lint_output_excerpt"] = _summarize_command_json(lint_output, max_chars=5000)
            self.candidate.lint_pass = bool(lint_ok)
            if not lint_ok:
                result["status"] = "lint_failed"
                result["sim_completed"] = False
                self.candidate.sim_completed = False
            elif self.reviewer is None:
                result["status"] = "verifier_unavailable"
                result["sim_completed"] = False
                self.candidate.sim_completed = False
            else:
                validation_reviewer = self.reviewer
                if isinstance(self.reviewer, SystemSimReviewer):
                    validation_reviewer = SystemSimReviewer(
                        generated_dir=candidate_rtl_root,
                        verify_script=self.reviewer.verify_script,
                        output_dir=self.debug_workdir,
                        timeout=self.reviewer.timeout,
                    )
                is_pass, mismatch_count, sim_output = validation_reviewer.review()
                sim_path = self.debug_workdir / "debug_sim_output.json"
                sim_path.write_text(sim_output, encoding="utf-8")
                first_fail = _extract_first_fail_time(sim_output)
                after_metrics = _parse_sim_metrics(sim_output)
                self.state.last_sim = SimSnapshot(
                    is_pass=bool(is_pass),
                    mismatch_count=int(mismatch_count),
                    first_fail_time=first_fail,
                    sim_output_path=str(sim_path),
                )
                self.state.last_sim_output = sim_output
                trace_summary = None
                trace_error = None
                if not is_pass and int(mismatch_count) > 0:
                    try:
                        report = self.tools._refresh_trace(sim_output)  # noqa: SLF001 - shared debug primitive
                        trace_summary = self.tools._trace_summary(report)  # noqa: SLF001
                        self.state.last_trace_summary = trace_summary
                    except Exception as exc:  # noqa: BLE001
                        # A verifier result is still a completed validation even when
                        # optional trace extraction cannot understand its output.
                        trace_error = f"{type(exc).__name__}: {exc}"
                result.update(
                    {
                        "is_pass": bool(is_pass),
                        "mismatch_count": int(mismatch_count),
                        "first_fail_time": first_fail,
                        "sim_completed": True,
                        "sim_output_excerpt": _summarize_command_json(sim_output),
                        "metric_delta": _metric_delta(before_metrics, after_metrics),
                        "trace_summary": trace_summary,
                        "trace_error": trace_error,
                    }
                )
                self.candidate.sim_completed = True
        except Exception as exc:  # noqa: BLE001
            result.update(
                {
                    "status": "validation_error",
                    "sim_completed": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            self.candidate.sim_completed = False
        self._snapshot_artifacts(candidate_artifact_root)
        self.candidate.artifact_root = candidate_artifact_root
        self.candidate.result = dict(result)
        self.last_validation = dict(result)
        self.journal.append_jsonl(
            "codex_validation_journal.jsonl",
            {
                "event": "evaluate",
                "candidate_id": candidate_id,
                "revision": revision,
                "reason": reason,
                "expected_effect": expected_effect,
                "result": result,
            },
        )
        self._write_status()
        return self._public_result(result)

    def _accept_candidate(self, candidate_id: str | None) -> dict[str, Any]:
        error = self._candidate_resolution_error(candidate_id)
        if error:
            return error
        assert self.candidate is not None
        if not self.candidate.lint_pass or not self.candidate.sim_completed:
            return {
                "status": "candidate_not_acceptable",
                "candidate_id": self.candidate.candidate_id,
                "lint_pass": self.candidate.lint_pass,
                "sim_completed": self.candidate.sim_completed,
            }
        self._replace_tree(self.merged_root, self.baseline_rtl_root)
        if self.candidate.artifact_root is not None:
            self._replace_tree(self.candidate.artifact_root, self.baseline_artifact_root)
        self.accepted_manifest = dict(self.candidate.evaluated_manifest)
        self.baseline_revision += 1
        self.accepted_actions += 1
        accepted_id = self.candidate.candidate_id
        accepted_revision = self.candidate.revision
        self.journal.append_jsonl(
            "codex_validation_journal.jsonl",
            {
                "event": "accept",
                "candidate_id": accepted_id,
                "candidate_revision": accepted_revision,
                "baseline_revision": self.baseline_revision,
                "result": self.candidate.result,
            },
        )
        self.candidate = None
        self.state.action_calls = self.accepted_actions
        self.accepted_sim = self.state.last_sim.model_copy(deep=True)
        self.accepted_sim_output = self.state.last_sim_output
        self._refresh_kg_after_accept()
        result = {
            "status": "accepted",
            "candidate_id": accepted_id,
            "candidate_revision": accepted_revision,
            "baseline_revision": self.baseline_revision,
            "is_pass": self.state.last_sim.is_pass,
            "mismatch_count": self.state.last_sim.mismatch_count,
            "first_fail_time": self.state.last_sim.first_fail_time,
        }
        self.last_validation = result
        self._write_status()
        return result

    def _rollback_candidate(self, candidate_id: str | None) -> dict[str, Any]:
        if self.candidate is None:
            if self._phase() == "clean_accepted":
                return {"status": "no_pending_candidate", "baseline_revision": self.baseline_revision}
            rolled_back_id = None
            rolled_back_revision = 0
        else:
            if candidate_id is not None and candidate_id != self.candidate.candidate_id:
                return {
                    "status": "candidate_id_mismatch",
                    "expected_candidate_id": self.candidate.candidate_id,
                }
            rolled_back_id = self.candidate.candidate_id
            rolled_back_revision = self.candidate.revision
        self._restore_baseline()
        self.journal.append_jsonl(
            "codex_validation_journal.jsonl",
            {
                "event": "rollback",
                "candidate_id": rolled_back_id,
                "candidate_revision": rolled_back_revision,
                "baseline_revision": self.baseline_revision,
            },
        )
        result = {
            "status": "rolled_back",
            "candidate_id": rolled_back_id,
            "candidate_revision": rolled_back_revision,
            "baseline_revision": self.baseline_revision,
        }
        self.last_validation = result
        self._write_status()
        return result

    def _candidate_resolution_error(self, candidate_id: str | None, *, allow_dirty: bool = False) -> dict[str, Any] | None:
        if self.candidate is None:
            return {"status": "no_pending_candidate"}
        if candidate_id != self.candidate.candidate_id:
            return {
                "status": "candidate_id_mismatch",
                "expected_candidate_id": self.candidate.candidate_id,
            }
        if not allow_dirty and self._phase() != "pending_validated":
            return {
                "status": "stale_candidate",
                "candidate_id": self.candidate.candidate_id,
                "message": "RTL changed after evaluation; evaluate it again before accepting.",
            }
        return None

    def _restore_baseline(self) -> None:
        self._replace_tree(self.baseline_rtl_root, self.merged_root)
        self._restore_artifacts(self.baseline_artifact_root)
        self.accepted_manifest = self._manifest(self.merged_root, allow_symlinks=False)
        self.candidate = None
        self._restore_state_from_baseline_artifacts()

    def _restore_state_from_baseline_artifacts(self) -> None:
        self.state.last_sim = self.accepted_sim.model_copy(deep=True)
        self.state.last_sim_output = self.accepted_sim_output
        trace_path = self.debug_workdir / "trace_report.json"
        if trace_path.is_file():
            try:
                report = json.loads(trace_path.read_text(encoding="utf-8"))
                self.state.last_trace_summary = self.tools._trace_summary(report)  # noqa: SLF001
            except Exception:
                pass

    def _refresh_kg_after_accept(self) -> None:
        if self.kg_service is None or not hasattr(self.kg_service, "refresh_repo_files"):
            return
        try:
            self.kg_service.refresh_repo_files(
                changed_paths=[str(path) for path in self._rtl_files()],
                stage="codex_debug_accept",
                filter_to_planned_skeleton=False,
            )
        except Exception as exc:  # noqa: BLE001
            self.kg_error = f"{type(exc).__name__}: {exc}"
            self.logger.warning("Could not refresh Codex Debug KG: %s", self.kg_error)

    @staticmethod
    def _diff_summary(before: dict[str, str], after: dict[str, str]) -> dict[str, list[str]]:
        before_paths = set(before)
        after_paths = set(after)
        return {
            "added": sorted(after_paths - before_paths),
            "deleted": sorted(before_paths - after_paths),
            "modified": sorted(path for path in before_paths & after_paths if before[path] != after[path]),
        }

    # ------------------------------------------------------------------
    # Status, redaction, shutdown
    # ------------------------------------------------------------------

    def get_debug_status(self, *, count_read: bool = True) -> dict[str, Any]:
        with self._lock:
            if count_read:
                blocked = self._consume_read("get_debug_status")
                if blocked:
                    return blocked
            phase = self._phase()
            latest_sim = self.state.last_sim
            if phase == "dirty_unvalidated":
                latest_sim = self.accepted_sim
            elif phase == "pending_validated" and self.candidate is not None and not self.candidate.sim_completed:
                latest_sim = self.accepted_sim
            pending = None
            if self.candidate is not None:
                pending = {
                    "candidate_id": self.candidate.candidate_id,
                    "revision": self.candidate.revision,
                    "lint_pass": self.candidate.lint_pass,
                    "sim_completed": self.candidate.sim_completed,
                    "stale": phase != "pending_validated",
                }
            next_actions = {
                "clean_accepted": ["edit merged RTL", "run_check", "read debug evidence"],
                "dirty_unvalidated": ["validate_rtl_changes:evaluate", "validate_rtl_changes:rollback"],
                "pending_validated": ["validate_rtl_changes:accept", "validate_rtl_changes:rollback", "read candidate evidence"],
            }[phase]
            payload = {
                "status": "ok",
                "phase": phase,
                "run_id": self.descriptor.run_id,
                "codex_runtime": {
                    "session_id": self.descriptor.codex_session_id,
                    "episode": self.descriptor.codex_episode,
                    "resumed": self.descriptor.codex_episode > 1,
                },
                "baseline_revision": self.baseline_revision,
                "pending_candidate": pending,
                "latest": {
                    "is_pass": latest_sim.is_pass,
                    "mismatch_count": latest_sim.mismatch_count,
                    "first_fail_time": latest_sim.first_fail_time,
                    "evidence_revision": self._evidence_revision(),
                },
                "budgets": {
                    "readonly_calls": self.readonly_calls,
                    "validation_trials": self.validation_trials,
                    "max_validation_trials": self.descriptor.max_validation_trials,
                    "validation_trials_this_launch": max(0, self.validation_trials - self.descriptor.validation_trial_offset),
                    "remaining_validation_trials": max(0, self.descriptor.max_validation_trials - self.validation_trials),
                    "accepted_actions": self.accepted_actions,
                },
                "initial_trace_hint": {
                    "observed": self.initial_trace_completed,
                    "suggested_call": self.required_initial_trace,
                },
                "kg": {"available": self.kg_service is not None, "error": self.kg_error},
                "last_validation": self._public_result(self.last_validation),
                "next_actions": next_actions,
            }
            if count_read:
                self._persist_status(payload)
            return payload

    def _public_result(self, value: Any) -> Any:
        hidden_keys = {
            "artifact_paths",
            "output_root",
            "repo_root",
            "verify_dir",
            "verify_script",
            "sim_output_path",
            "trace_report_path",
        }
        if isinstance(value, dict):
            return {
                key: self._public_result(item)
                for key, item in value.items()
                if key not in hidden_keys
            }
        if isinstance(value, list):
            return [self._public_result(item) for item in value]
        if isinstance(value, tuple):
            return [self._public_result(item) for item in value]
        if isinstance(value, str):
            replacements: list[tuple[Path, str]] = [
                (self.spec_root, "spec"),
                (self.merged_root, "merged"),
                (self.task_root, "."),
                (self.private_root, "<private>"),
            ]
            if self.descriptor.planning_output_root is not None:
                replacements.append((self.descriptor.planning_output_root.resolve(), "<planning>"))
            if self.descriptor.verify_script is not None:
                replacements.append((self.descriptor.verify_script.resolve().parent, "<verifier>"))
            for root, label in replacements:
                root_text = str(root)
                if root_text in value:
                    value = value.replace(root_text, label)
            # Hide remaining absolute paths without damaging multi-line logs.
            if "\n" not in value and re.match(r"^/(?:[^/]+/)+[^/]*$", value):
                return f"<hidden>/{Path(value).name}"
        return value

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            phase = self._phase()
            if phase != "clean_accepted":
                pending_id = self.candidate.candidate_id if self.candidate is not None else None
                pending_revision = self.candidate.revision if self.candidate is not None else 0
                self._restore_baseline()
                self.last_validation = {
                    "status": "fail_closed_rollback",
                    "previous_phase": phase,
                    "candidate_id": pending_id,
                    "candidate_revision": pending_revision,
                    "baseline_revision": self.baseline_revision,
                }
                self.journal.append_jsonl("codex_validation_journal.jsonl", self.last_validation)
            self._closed = True
            self._write_status()

    def __enter__(self) -> "CodexDebugSession":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        del exc_type, exc, traceback
        self.close()
