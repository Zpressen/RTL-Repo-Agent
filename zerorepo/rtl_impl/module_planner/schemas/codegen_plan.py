from __future__ import annotations

from typing import Any, List, Literal

from pydantic import BaseModel, Field, model_validator


class ModulePlanSubtask(BaseModel):
    id: str = Field(..., min_length=1)
    target: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    spec_refs: List[str] = Field(..., min_length=1)
    constraints: List[str] = Field(default_factory=list, max_length=3)
    timing_obligation_ids: List[str] = Field(default_factory=list)
    logical_value_tags: List[str] = Field(default_factory=list)


class ModulePlanArtifact(BaseModel):
    schema_version: str = Field(default="module_plan_v1")
    module: str = Field(..., min_length=1)
    subtasks: List[ModulePlanSubtask] = Field(..., min_length=1)


class ModulePlanRecord(BaseModel):
    module: str = Field(..., min_length=1)
    plan_file: str = Field(..., min_length=1)


class Stage4ModulePlansArtifact(BaseModel):
    schema_version: str = Field(default="module_plans_v1")
    task_id: str = Field(..., min_length=1)
    input_fingerprint: str = Field(default="")
    module_order: List[str] = Field(..., min_length=1)
    stage4_status: Literal["module_plans_in_progress", "module_plans_planned"] = Field(default="module_plans_planned")
    completed_modules: List[str] = Field(default_factory=list)
    resume_cursor: int = Field(default=0, ge=0)
    module_plan_files: List[ModulePlanRecord] = Field(..., min_length=1)

    @model_validator(mode="before")
    @classmethod
    def infer_resume_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data = dict(data)
            if "completed_modules" not in data:
                data["completed_modules"] = [item.get("module") for item in data.get("module_plan_files") or []]
            if "resume_cursor" not in data:
                data["resume_cursor"] = len(data.get("completed_modules") or [])
            if "stage4_status" not in data:
                data["stage4_status"] = (
                    "module_plans_planned"
                    if len(data.get("completed_modules") or []) == len(data.get("module_order") or [])
                    else "module_plans_in_progress"
                )
        return data

    @model_validator(mode="after")
    def validate_structure(self) -> "Stage4ModulePlansArtifact":
        modules = [item.module for item in self.module_plan_files]
        if self.completed_modules != modules:
            raise ValueError("completed_modules must exactly match module_plan_files[].module order")
        if self.completed_modules != self.module_order[: len(self.completed_modules)]:
            raise ValueError("completed_modules must be a prefix of module_order")
        if self.resume_cursor != len(self.completed_modules):
            raise ValueError("resume_cursor must match completed_modules length")
        if self.resume_cursor > len(self.module_order):
            raise ValueError("resume_cursor must not exceed module_order length")
        if self.stage4_status == "module_plans_planned" and self.completed_modules != self.module_order:
            raise ValueError("final stage4 artifact must cover every module in module_order")
        return self


class FragmentContract(BaseModel):
    writes: List[str] = Field(default_factory=list)
    reads: List[str] = Field(default_factory=list)
    clocking: str = Field(default="")
    reset_behavior: str = Field(default="")
    hold_behavior: str = Field(default="")
    latency: str = Field(default="")
    assumptions: List[str] = Field(default_factory=list)


class SubtaskCodeArtifact(BaseModel):
    task_id: str = Field(..., min_length=1)
    module: str = Field(..., min_length=1)
    subtask_id: str = Field(..., min_length=1)
    target: str = Field(..., min_length=1)
    spec_refs: List[str] = Field(..., min_length=1)
    timing_obligation_ids: List[str] = Field(default_factory=list)
    code: str = Field(..., min_length=1)
    contract: FragmentContract | None = None


class ModuleCodegenRecord(BaseModel):
    module: str = Field(..., min_length=1)
    status: Literal["completed", "in_progress", "failed", "blocked"] = "completed"
    error: str = ""
    workspace_file: str = ""
    completed_subtasks: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_completion(self):
        if self.status == "completed" and not self.workspace_file.strip():
            raise ValueError("A completed module must have a workspace_file")
        return self


class Stage5CodegenArtifact(BaseModel):
    schema_version: str = Field(default="stage5_codegen_v1")
    task_id: str = Field(..., min_length=1)
    input_fingerprint: str = Field(default="")
    module_order: List[str] = Field(..., min_length=1)
    module_files: List[ModuleCodegenRecord] = Field(..., min_length=1)
    status: Literal["completed", "in_progress", "failed"] = "completed"

    @model_validator(mode="after")
    def validate_structure(self) -> "Stage5CodegenArtifact":
        modules = [item.module for item in self.module_files]
        if modules != self.module_order:
            raise ValueError("module_files[].module must exactly match module_order")
        if any(item.status != "completed" for item in self.module_files):
            self.status = "failed" if any(item.status in {"failed", "blocked"} for item in self.module_files) else "in_progress"
        return self


class ModuleMergeRecord(BaseModel):
    module: str = Field(..., min_length=1)
    status: Literal["completed", "failed", "blocked"] = "completed"
    error: str = ""
    fragment_file: str = ""
    merged_file: str = ""

    @model_validator(mode="after")
    def validate_completion(self):
        if self.status == "completed" and (not self.fragment_file.strip() or not self.merged_file.strip()):
            raise ValueError("A completed merge must have fragment_file and merged_file")
        return self


class ModuleDebugRecord(BaseModel):
    module: str = Field(..., min_length=1)
    status: Literal["disabled", "skipped", "pass", "fixed", "fail", "error"]
    mismatch_count: int = Field(default=0)
    debug_trials: int = Field(default=0)
    workdir: str = Field(default="")
    final_rtl_path: str = Field(default="")
    trace_report_path: str = Field(default="")
    sim_output_path: str = Field(default="")
    reason: str = Field(default="")


class SystemDebugRecord(BaseModel):
    top_module: str = Field(default="")
    status: Literal["disabled", "skipped", "pass", "fixed", "fail", "error"] = "skipped"
    mismatch_count: int = Field(default=0)
    debug_trials: int = Field(default=0)
    workdir: str = Field(default="")
    generated_dir: str = Field(default="")
    verify_dir: str = Field(default="")
    verify_script: str = Field(default="")
    sim_output_path: str = Field(default="")
    trace_report_path: str = Field(default="")
    reason: str = Field(default="")


class Stage6MergeArtifact(BaseModel):
    schema_version: str = Field(default="stage6_merge_v1")
    task_id: str = Field(..., min_length=1)
    module_order: List[str] = Field(..., min_length=1)
    module_files: List[ModuleMergeRecord] = Field(..., min_length=1)
    debug_files: List[ModuleDebugRecord] = Field(default_factory=list)
    system_debug: SystemDebugRecord | None = None
    latest_system_debug: SystemDebugRecord | None = None
    status: Literal["completed", "failed"] = "completed"

    @model_validator(mode="after")
    def validate_structure(self) -> "Stage6MergeArtifact":
        modules = [item.module for item in self.module_files]
        if modules != self.module_order:
            raise ValueError("module_files[].module must exactly match module_order")
        if any(item.status != "completed" for item in self.module_files):
            self.status = "failed"
        if self.debug_files:
            debug_modules = [item.module for item in self.debug_files]
            if debug_modules != self.module_order:
                raise ValueError("debug_files[].module must exactly match module_order when present")
        return self
