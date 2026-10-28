"""Public contracts; deliberately independent of the RTL/LLM stack."""

from __future__ import annotations
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DemoError(Exception):
    def __init__(self, code: str, message: str, status: int = 400, **details: Any):
        super().__init__(message)
        self.code, self.message, self.status, self.details = (
            code,
            message,
            status,
            details,
        )


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


CaseId = Literal[
    "e203",
    "aes_cipher_system_hard",
    "aes_inv_cipher_top_system",
    "sdc_controller_system",
]


WorkspacePanel = Literal["spec", "architecture", "code", "verify", "repair"]


class Context(Model):
    workspace_panel: WorkspacePanel | None = None
    case_id: CaseId = "e203"
    view: Literal['workspace', 'optimization', 'experience'] = 'workspace'
    story_id: str | None = None
    memory_revision_id: str | None = None
    memory_use_id: str | None = None
    run_id: str | None = None
    version_id: str | None = None
    validation_id: str | None = None
    module_id: str | None = None
    signal_id: str | None = None
    time_range: list[str] | None = None


class SessionRequest(Model):
    case_id: CaseId = "e203"


class MessageRequest(Model):
    text: str = Field(min_length=1, max_length=4000)
    context_ref: Context
    client_message_id: str = Field(min_length=1, max_length=128)


class OperationRequest(Model):
    kind: Literal["generate_and_verify", "verify", "fix"]
    context_ref: Context
    source_message_id: str | None = None


class Selection(Context):
    browsing_mode: Literal["historical", "live"] = "historical"
    workspace_panel: WorkspacePanel = 'architecture'


class EvidenceRef(Model):
    artifact_id: str
    module_id: str | None = None


class ChatDecision(Model):
    _model_receipt: dict | None = PrivateAttr(default=None)
    kind: Literal[
        "answer", "clarify", "open_artifact", "generate_and_verify", "verify", "fix"
    ]
    text: str = Field(min_length=1, max_length=12000)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list, max_length=12)


class Verdict(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    UNVERIFIED = "unverified"


class Artifact(Model):
    artifact_id: str
    kind: str
    sha256: str
    source_sha256: str | None = None
    size_bytes: int
    storage_key: str | None = None
    exposure: Literal["private", "display"] = "private"
    owner_session: str | None = None


class RTLVersion(Model):
    version_id: str
    run_id: str
    tree_sha256: str
    file_manifest: list[dict[str, Any]]
    modules: list[dict[str, Any]] = Field(default_factory=list)
    parent_version_id: str | None = None
    disposition: str = "accepted"
    storage_key: str | None = None


class SignalMismatch(Model):
    signal: str
    count: int
    first_failure_ticks: str


class ProbeSample(Model):
    time_ticks: str
    signal: str
    reference: str
    dut: str
    reference_path: str
    dut_path: str


class Validation(Model):
    validation_id: str
    run_id: str
    version_id: str
    kind: Literal["syntax", "edit_only", "candidate", "initial_system", "final_system"]
    verdict: Verdict
    simulation_completed: bool
    total_samples: int | None = None
    mismatched_samples: int | None = None
    internal_mismatch_count: int | None = None
    first_failure_ticks: str | None = None
    report_artifact_id: str
    waveform_artifact_id: str | None = None
    waveform_sha256: str | None = None
    verifier_fingerprint: str | None = None
    binding_level: str = "recorded_candidate"
    marker_status: str = "unsupported"
    comparison_policy_id: str | None = None
    signal_names: list[str] | None = None
    waveform_tile_artifact_ids: list[str] = Field(default_factory=list)
    trial_no: int | None = None
    source_candidate: str | None = None
    waveform_index_artifact_id: str | None = None
    full_end_ticks: str | None = None
    input_manifest_artifact_id: str | None = None
    signal_mismatches: list[SignalMismatch] = Field(default_factory=list)
    probe_samples: list[ProbeSample] = Field(default_factory=list)
    probe_source_sha256: str | None = None
    waveform_note: str | None = None
    report_scope: str | None = None
    verification_scope: str | None = None
    signal_counter_status: str | None = None


class SampleMarker(Model):
    time_ticks: str
    sample_index: int
    verdict: Literal["pass", "fail"]
    failed_signals: list[str] = Field(default_factory=list)
    source: Literal["testbench_counter_delta"] = "testbench_counter_delta"
    sampled_value_available: Literal[False] = False


class WaveWindow(Model):
    validation_id: str
    version_id: str
    waveform_sha256: str
    timescale: dict[str, Any]
    start_ticks: str
    end_ticks: str
    signals: list[dict[str, Any]]
    sample_markers: list[SampleMarker]
    missing_signals: list[str] = Field(default_factory=list)
    marker_status: str
    comparison_policy_id: str = "e203-posedge-stats-v1"
    truncated: Literal[False] = False


class Case(Model):
    case_id: CaseId = "e203"
    title: str
    subtitle: str | None = None
    summary: str
    spec_artifact_id: str
    planner_artifact_id: str
    source_run_id: str


class Message(Model):
    message_id: str
    session_id: str
    sequence: int
    text: str
    context_ref: Context
    state: Literal["replying", "answered", "clarification", "failed", "interrupted"]
    answer: str | None = None
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    operation_id: str | None = None
    origin: Literal["live"] = "live"
    client_message_id: str | None = None
    decision: str | None = None
    error_code: str | None = None
    created_at: str
    finished_at: str | None = None
    answer_source: Literal['recorded_evidence', 'model', 'unsupported_notice'] | None = None
    model_receipt: dict[str, str | int] | None = None


class Operation(Model):
    operation_id: str
    session_id: str
    run_id: str
    kind: Literal["generate_and_verify", "verify", "fix"]
    context_ref: Context
    state: Literal[
        "accepted", "running", "completed", "failed", "timed_out", "interrupted"
    ]
    origin: Literal["live"] = "live"
    stage: str
    verdict: Verdict = Verdict.UNVERIFIED
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None
    error_code: str | None = None
    validation_id: str | None = None
    version_id: str | None = None


class Run(Model):
    run_id: str
    case_id: CaseId = "e203"
    origin: Literal["historical", "live"]
    state: str
    versions: list[str] = Field(default_factory=list)
    validations: list[str] = Field(default_factory=list)
    operation_id: str | None = None
    source_run_id: str | None = None
    stage: str | None = None
    verdict: Verdict = Verdict.UNVERIFIED
    completed_at: str | None = None
    modules: list[dict[str, Any]] = Field(default_factory=list)


class Session(Model):
    session_id: str
    case_id: CaseId = "e203"
    selection: Selection
    created_at: str
    messages: list[Message] = Field(default_factory=list)
    operations: list[Operation] = Field(default_factory=list)
    last_event_id: int = 0
    operation: Operation | None = None


class RepairAttempt(Model):
    source_candidate: str | None = None
    candidate_revision: int | None = None
    attempt_id: str
    run_id: str
    trial_no: int
    candidate_version_id: str
    validation_id: str | None = None
    decision: Literal["pending", "accepted", "rolled_back"]
    lint_pass: bool | None = None
    simulation_completed: bool


class Event(Model):
    event_id: int
    session_id: str
    type: str
    origin: Literal["historical", "live"]
    observed_at: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class Bundle(Model):
    schema_version: Literal["rtl-demo-bundle-v1"] = "rtl-demo-bundle-v1"
    bundle_id: str
    case_id: CaseId = "e203"
    source_run_id: str
    origin: Literal["historical"] = "historical"
    versions: list[RTLVersion]
    validations: list[Validation]
    comparison_pair: dict[str, str | None]
    manifest_sha256: str
    title: str
    subtitle: str | None = None
    summary: str
    spec_artifact_id: str
    planner_artifact_id: str
    source_fingerprint: str
    verifier_fingerprint: str
    binding_level: str
    binding_note: str
    modules: list[dict[str, Any]]
    artifacts: list[dict[str, Any]]
    events: list[dict[str, Any]]
    stats_fields: list[str]
    trial_count: int | None
    content_urls: dict[str, str] | None = None
    waveform_urls: dict[str, str] | None = None
