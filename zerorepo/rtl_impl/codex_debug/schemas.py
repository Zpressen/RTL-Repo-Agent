from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


class KgRunConfig(BaseModel):
    """Private configuration used to reconstruct a run-local RTL KG service."""

    enabled: bool = False
    config: dict[str, Any] = Field(default_factory=dict)
    checkpoint_dir: Path | None = None
    planning_projection_path: Path | None = None


class CodexDebugRunDescriptor(BaseModel):
    """Private, serializable input for one Codex Debug MCP process."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    run_id: str = Field(..., min_length=1)
    outer_run_id: str = ''
    case_id: str = ''
    memory_snapshot_path: Path | None = None
    memory_snapshot_sha256: str = ''
    task_root: Path
    spec_root: Path
    merged_root: Path
    private_root: Path
    debug_workdir: Path
    planner_module_name: str = Field(..., min_length=1)
    top_module: str = Field(..., min_length=1)
    top_rtl: Path
    verify_script: Path | None = None
    verifier_timeout: int = Field(default=300, ge=1)
    planning_output_root: Path | None = None
    contract_json: str = ""
    spec_text: str = ""
    spec_paths: list[Path] = Field(default_factory=list)
    initial_sim_output: str = ""
    initial_sim_output_path: Path | None = None
    initial_wave_path: Path | None = None
    initial_mismatch_count: int = Field(default=0, ge=0)
    max_validation_trials: int = Field(default=30, ge=1)
    validation_trial_offset: int = Field(default=0, ge=0)
    codex_session_id: str = ""
    codex_episode: int = Field(default=1, ge=1)
    kg_hop_depth: int = Field(default=3, ge=1)
    kg: KgRunConfig = Field(default_factory=KgRunConfig)

    @model_validator(mode="after")
    def validate_roots(self) -> "CodexDebugRunDescriptor":
        task_root = self.task_root.resolve()
        spec_root = self.spec_root.resolve()
        merged_root = self.merged_root.resolve()
        private_root = self.private_root.resolve()
        debug_workdir = self.debug_workdir.resolve()
        top_rtl = self.top_rtl.resolve()
        if not _is_under(spec_root, task_root):
            raise ValueError("spec_root must be inside task_root")
        if not _is_under(merged_root, task_root):
            raise ValueError("merged_root must be inside task_root")
        if _is_under(private_root, task_root) or _is_under(task_root, private_root):
            raise ValueError("private_root and the Codex-visible task_root must be disjoint")
        if _is_under(spec_root, merged_root) or _is_under(merged_root, spec_root):
            raise ValueError("spec_root and merged_root must be disjoint")
        if not _is_under(debug_workdir, private_root):
            raise ValueError("debug_workdir must be inside private_root")
        if not _is_under(top_rtl, merged_root):
            raise ValueError("top_rtl must be inside merged_root")
        for path in self.spec_paths:
            if not _is_under(path, spec_root):
                raise ValueError(f"spec path is outside spec_root: {path}")
        for hidden_path, label in (
            (self.memory_snapshot_path, 'memory_snapshot_path'),
            (self.verify_script, "verify_script"),
            (self.planning_output_root, "planning_output_root"),
            (self.initial_sim_output_path, "initial_sim_output_path"),
            (self.initial_wave_path, "initial_wave_path"),
        ):
            if hidden_path is not None and _is_under(hidden_path.resolve(), task_root):
                raise ValueError(f"{label} must be outside the Codex-visible task_root")
        if self.memory_snapshot_path:
            import json, hashlib
            from zerorepo.rtl_impl.rtl_memory.ledger import digest
            if self.memory_snapshot_path.is_symlink() or digest(json.loads(self.memory_snapshot_path.read_text())) != self.memory_snapshot_sha256:
                raise ValueError('Memory snapshot changed')
        return self

    def read_initial_sim_output(self) -> str:
        if self.initial_sim_output:
            return self.initial_sim_output
        if self.initial_sim_output_path and self.initial_sim_output_path.is_file():
            return self.initial_sim_output_path.read_text(encoding="utf-8", errors="replace")
        return ""
