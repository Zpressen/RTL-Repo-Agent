from __future__ import annotations

from typing import Any, List, Literal

from pydantic import BaseModel, Field, model_validator

from .responsibility import QualityReport
from .planning import BehaviorObligation, StateObject


Stage3Status = Literal["module_skeletons_in_progress", "module_skeletons_planned"]
BlockKind = Literal["decl", "inst", "seq", "comb", "helper", "meta"]
ControlStyle = Literal["counter_driven", "explicit_fsm", "flag_driven", "mixed", "purely_combinational", "undecided"]


class SourceRefs(BaseModel):
    module_contract_ref: str = Field(..., min_length=1)
    repo_skeleton_ref: str = Field(..., min_length=1)
    module_spec_file: str = Field(..., min_length=1)


class StructuralBlock(BaseModel):
    block_id: str = Field(..., min_length=1)
    block_label: str = Field(..., min_length=1)
    block_kind: BlockKind
    required: bool = Field(default=True)
    purpose: str = Field(..., min_length=1)
    code_shape: str = Field(..., min_length=1)
    depends_on: List[str] = Field(default_factory=list)
    placeholder: str = Field(..., min_length=1)
    must_appear: List[str] = Field(default_factory=list)
    may_appear: List[str] = Field(default_factory=list)
    retrieval_focus: List[str] = Field(default_factory=list)


class SemanticMode(BaseModel):
    mode: str = Field(..., min_length=1)
    meaning: str = Field(..., min_length=1)


class StateModelEntry(BaseModel):
    object: str = Field(..., min_length=1)
    storage_kind: str = Field(default="unspecified")
    representation: str = Field(default="implementation-open")
    notes: str = Field(default="")


class ModuleBehaviorSummary(BaseModel):
    control_style: ControlStyle = Field(default="undecided")
    semantic_modes: List[SemanticMode] = Field(default_factory=list)
    state_model: List[StateModelEntry] = Field(default_factory=list)
    global_invariants: List[str] = Field(default_factory=list)
    open_semantic_questions: List[str] = Field(default_factory=list)


class BlockBehaviorOverlay(BaseModel):
    responsibility_ids: List[str] = Field(default_factory=list)
    obligation_ids: List[str] = Field(default_factory=list)
    supporting_obligation_ids: List[str] = Field(default_factory=list)
    block_id: str = Field(..., min_length=1)
    responsibilities: List[str] = Field(default_factory=list)
    timing_semantics: List[str] = Field(default_factory=list)
    touched_objects: List[str] = Field(default_factory=list)
    coupling_rules: List[str] = Field(default_factory=list)
    forbidden_drift: List[str] = Field(default_factory=list)


class DecisionEntry(BaseModel):
    topic: str = Field(..., min_length=1)
    decision: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)


class DecisionLedger(BaseModel):
    chosen_decisions: List[DecisionEntry] = Field(default_factory=list)
    deferred_decisions: List[str] = Field(default_factory=list)
    structural_risks: List[str] = Field(default_factory=list)
    behavioral_risks: List[str] = Field(default_factory=list)


class ModuleSkeletonExport(BaseModel):
    state_objects: List[StateObject] = Field(default_factory=list)
    behavioral_obligations: List[BehaviorObligation] = Field(default_factory=list)
    schema_version: str = Field(default="module_skeleton_export_v1")
    module: str = Field(..., min_length=1)
    file_path: str = Field(..., min_length=1)
    source_refs: SourceRefs
    planning_note: str = Field(default="")
    module_frame: str = Field(..., min_length=1)
    structural_blocks: List[StructuralBlock] = Field(..., min_length=1)
    module_behavior: ModuleBehaviorSummary
    block_behavior_overlays: List[BlockBehaviorOverlay] = Field(default_factory=list)
    decision_ledger: DecisionLedger

    @model_validator(mode="after")
    def validate_references(self) -> "ModuleSkeletonExport":
        block_ids = [item.block_id for item in self.structural_blocks]
        if len(block_ids) != len(set(block_ids)):
            raise ValueError("structural_blocks must not contain duplicate block_id values")
        block_id_set = set(block_ids)
        for block in self.structural_blocks:
            unknown = [item for item in block.depends_on if item not in block_id_set]
            if unknown:
                raise ValueError(f"block `{block.block_id}` depends_on unknown blocks {unknown}")
        for overlay in self.block_behavior_overlays:
            if overlay.block_id not in block_id_set:
                raise ValueError(f"overlay references unknown block_id `{overlay.block_id}`")
        return self


class ModuleRecord(BaseModel):
    module: str = Field(..., min_length=1)
    doc_file: str = Field(..., min_length=1)
    export_file: str = Field(..., min_length=1)
    spec_context_file: str = Field(default="")
    export_schema_version: str = Field(default="module_skeleton_export_v1")
    source_refs: SourceRefs
    planning_note: str = Field(default="")
    block_ids: List[str] = Field(default_factory=list)


class Stage3ModuleSkeletonArtifact(BaseModel):
    schema_version: str = Field(default="stage3_skeleton_docs_v1")
    task_id: str = Field(..., min_length=1)
    input_fingerprint: str = Field(default="")
    source_schema_versions: dict[str, str] = Field(default_factory=dict)
    stage3_status: Stage3Status = Field(default="module_skeletons_in_progress")
    top_module: str = Field(..., min_length=1)
    module_order: List[str] = Field(..., min_length=1)
    completed_modules: List[str] = Field(default_factory=list)
    resume_cursor: int = Field(default=0, ge=0)
    global_summary: List[str] = Field(default_factory=list)
    module_records: List[ModuleRecord] = Field(default_factory=list)
    open_issues: List[str] = Field(default_factory=list)
    quality_report: QualityReport | None = None

    @model_validator(mode="before")
    @classmethod
    def infer_resume_cursor(cls, data: Any) -> Any:
        if isinstance(data, dict) and "resume_cursor" not in data:
            data = dict(data)
            data["resume_cursor"] = len(data.get("completed_modules") or [])
        return data

    @model_validator(mode="after")
    def validate_completed_modules(self) -> "Stage3ModuleSkeletonArtifact":
        record_modules = [item.module for item in self.module_records]
        if self.completed_modules != record_modules:
            raise ValueError("completed_modules must exactly match module_records[].module order")
        if self.completed_modules != self.module_order[: len(self.completed_modules)]:
            raise ValueError("completed_modules must be a prefix of module_order")
        if self.resume_cursor != len(self.completed_modules):
            raise ValueError("resume_cursor must match completed_modules length")
        if self.resume_cursor > len(self.module_order):
            raise ValueError("resume_cursor must not exceed module_order length")
        if self.stage3_status == "module_skeletons_planned" and self.completed_modules != self.module_order:
            raise ValueError("final stage3 artifact must cover every module in module_order")
        return self
