from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


FailureType = Literal[
    "timing_bug",
    "local_logic_bug",
    "interface_bug",
    "plan_bug",
    "unknown",
]
NextAction = Literal["patch", "read_more", "record_correction", "stop"]
RepoReActStatus = Literal["pass", "fail", "give_up", "max_steps_exceeded", "error"]


class Patch(BaseModel):
    path: str = Field(..., min_length=1)
    start_line: int = Field(..., ge=1)
    end_line: int = Field(..., ge=1)
    new_text: str


class Diagnosis(BaseModel):
    failure_type: FailureType = "unknown"
    suspected_module: str = ""
    suspected_files: list[str] = Field(default_factory=list)
    suspected_signals: list[str] = Field(default_factory=list)
    evidence_summary: list[str] = Field(default_factory=list)
    next_action: NextAction = "read_more"


class Correction(BaseModel):
    correction_type: Literal[
        "wrong_contract",
        "wrong_module_plan",
        "wrong_interface",
        "wrong_timing",
        "wrong_dependency",
        "wrong_retrieval",
    ]
    module_name: str
    original_artifact: str
    problem: str
    evidence: list[str] = Field(default_factory=list)
    override: dict[str, Any] = Field(default_factory=dict)


class StepRecord(BaseModel):
    step: int
    role: str
    content: str
    diagnosis: Diagnosis | None = None
    tool_name: str | None = None
    tool_result: dict[str, Any] | None = None


class SimSnapshot(BaseModel):
    is_pass: bool = False
    mismatch_count: int = 0
    first_fail_time: int | None = None
    sim_output_path: str = ""


class RepoReActInput(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    module_name: str
    repair_mode: Literal["syntax", "functional"] = "functional"
    workspace_root: Path
    debug_workdir: Path
    rtl_path: Path
    merged_file: Path
    output_root: Path | None = None
    repo_root: Path | None = None
    spec_text: str = ""
    spec_source_path: str = ""
    spec_paths: list[str] = Field(default_factory=list)
    contract_json: str = ""
    sim_failed_log: str = ""
    initial_mismatch_count: int = 0
    max_steps: int = 30
    kg_hop_depth: int = 3
    stage_artifacts: dict[str, str] = Field(default_factory=dict)


class RepoReActResult(BaseModel):
    status: RepoReActStatus
    is_pass: bool = False
    rtl_code: str = ""
    steps: int = 0
    action_calls: int = 0
    mismatch_count: int = 0
    trace_report_path: str = ""
    sim_output_path: str = ""
    workdir: str = ""
    reason: str = ""
