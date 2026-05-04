from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, Field, model_validator


class ModulePlanSubtask(BaseModel):
    id: str = Field(..., min_length=1)
    target: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    spec_refs: List[str] = Field(..., min_length=1)
    constraints: List[str] = Field(default_factory=list, max_length=3)


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
    module_order: List[str] = Field(..., min_length=1)
    module_plan_files: List[ModulePlanRecord] = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_structure(self) -> "Stage4ModulePlansArtifact":
        modules = [item.module for item in self.module_plan_files]
        if modules != self.module_order:
            raise ValueError("module_plan_files[].module must exactly match module_order")
        return self


class SubtaskCodeArtifact(BaseModel):
    task_id: str = Field(..., min_length=1)
    module: str = Field(..., min_length=1)
    subtask_id: str = Field(..., min_length=1)
    target: str = Field(..., min_length=1)
    spec_refs: List[str] = Field(..., min_length=1)
    code: str = Field(..., min_length=1)


class ModuleCodegenRecord(BaseModel):
    module: str = Field(..., min_length=1)
    workspace_file: str = Field(..., min_length=1)
    completed_subtasks: List[str] = Field(default_factory=list)


class Stage5CodegenArtifact(BaseModel):
    schema_version: str = Field(default="stage5_codegen_v1")
    task_id: str = Field(..., min_length=1)
    module_order: List[str] = Field(..., min_length=1)
    module_files: List[ModuleCodegenRecord] = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_structure(self) -> "Stage5CodegenArtifact":
        modules = [item.module for item in self.module_files]
        if modules != self.module_order:
            raise ValueError("module_files[].module must exactly match module_order")
        return self


class ModuleMergeRecord(BaseModel):
    module: str = Field(..., min_length=1)
    fragment_file: str = Field(..., min_length=1)
    merged_file: str = Field(..., min_length=1)


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


class Stage6MergeArtifact(BaseModel):
    schema_version: str = Field(default="stage6_merge_v1")
    task_id: str = Field(..., min_length=1)
    module_order: List[str] = Field(..., min_length=1)
    module_files: List[ModuleMergeRecord] = Field(..., min_length=1)
    debug_files: List[ModuleDebugRecord] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_structure(self) -> "Stage6MergeArtifact":
        modules = [item.module for item in self.module_files]
        if modules != self.module_order:
            raise ValueError("module_files[].module must exactly match module_order")
        if self.debug_files:
            debug_modules = [item.module for item in self.debug_files]
            if debug_modules != self.module_order:
                raise ValueError("debug_files[].module must exactly match module_order when present")
        return self
