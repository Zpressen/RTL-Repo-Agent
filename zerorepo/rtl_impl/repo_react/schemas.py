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
SystemFailureCategory = Literal[
    "compile_or_elaboration",
    "vcd_or_trace_unavailable",
    "top_protocol_or_fsm",
    "hierarchy_connection",
    "interface_width_or_port_order",
    "endian_or_byte_lane_mapping",
    "key_schedule_logic",
    "round_transform_logic",
    "sbox_or_lookup_logic",
    "latency_or_done_timing",
    "spec_or_plan_mismatch",
    "unknown",
]
NextAction = Literal["patch", "read_more", "record_correction", "stop"]
RepoReActStatus = Literal["pass", "fail", "give_up", "max_steps_exceeded", "error"]
DebugContextGoal = Literal[
    "initial_triage",
    "before_patch",
    "after_patch",
    "compact_resume",
    "specific_question",
]


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


class RawArtifactRef(BaseModel):
    kind: str
    path: str = ""
    artifact_id: str = ""
    description: str = ""


class EvidenceItem(BaseModel):
    evidence_id: str
    kind: str
    summary: str
    artifact_ref: RawArtifactRef
    why_selected: str = ""
    salient: dict[str, Any] = Field(default_factory=dict)


class TimingEvidence(BaseModel):
    signal: str = ""
    time: int | None = None
    edge: str = ""
    sampling_mode: str = ""
    ref: str = ""
    dut: str = ""
    driver_assignment_kind: str = ""
    block_id: str = ""
    line_range: list[int] = Field(default_factory=list)


class SystemTriage(BaseModel):
    category: SystemFailureCategory = "unknown"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    symptom: str = ""
    root_signal: str = ""
    root_time: int | None = None
    suspect_modules: list[str] = Field(default_factory=list)
    suspect_files: list[str] = Field(default_factory=list)
    signal_path: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    recommended_tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    patch_scope: str = ""
    reason: str = ""


class DebugContextPack(BaseModel):
    schema_version: str = "debug_context_pack_v1"
    goal: DebugContextGoal = "initial_triage"
    module: str
    repair_mode: Literal["syntax", "functional"] = "functional"
    pack_path: str = ""
    task_frame: dict[str, Any] = Field(default_factory=dict)
    evidence_pack: list[EvidenceItem] = Field(default_factory=list)
    active_working_set: dict[str, Any] = Field(default_factory=dict)
    causal_memory: dict[str, Any] = Field(default_factory=dict)
    raw_artifacts: dict[str, RawArtifactRef] = Field(default_factory=dict)
    timing_evidence: TimingEvidence = Field(default_factory=TimingEvidence)
    system_triage: SystemTriage = Field(default_factory=SystemTriage)
    fallback_used: bool = False
    fallback_reason: str = ""


class DebugContextRouterInput(BaseModel):
    goal: DebugContextGoal = "initial_triage"
    focus_signals: list[str] = Field(default_factory=list)
    focus_blocks: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    max_items: int = Field(default=5, ge=1, le=10)


class RepoReActInput(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    module_name: str
    repair_mode: Literal["syntax", "functional"] = "functional"
    repair_scope: Literal["module", "repo"] = "module"
    workspace_root: Path
    debug_workdir: Path
    rtl_path: Path
    merged_file: Path
    rtl_root: Path | None = None
    top_module: str = ""
    verify_dir: Path | None = None
    verify_script: Path | None = None
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
    context_pack_path: str = ""
    context_pack_json: dict[str, Any] = Field(default_factory=dict)


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
