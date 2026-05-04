from __future__ import annotations

from typing import Dict, List, Literal

from pydantic import BaseModel, Field, model_validator


ModuleKind = Literal["top_controller", "iterative_engine", "leaf_combinational", "leaf_stateful"]


class ClockingModel(BaseModel):
    primary_clock: str = Field(default="")
    reset_signal: str = Field(default="")
    reset_style: str = Field(default="")


class SkeletonHierarchyEdge(BaseModel):
    parent: str = Field(default="")
    child: str = Field(default="")


class RepoInstanceHint(BaseModel):
    module: str = Field(default="")
    count: int | str = Field(default="")
    usage: str = Field(default="")


class GlobalInvariants(BaseModel):
    system_role: str = Field(default="")
    clocking_model: ClockingModel = Field(default_factory=ClockingModel)
    hierarchy: List[SkeletonHierarchyEdge] = Field(default_factory=list)
    file_map: Dict[str, str] = Field(default_factory=dict)
    cross_module_alignment: List[str] = Field(default_factory=list)
    global_data_conventions: List[str] = Field(default_factory=list)


class RepoModuleSkeleton(BaseModel):
    module: str = Field(..., min_length=1)
    file_path: str = Field(default="")
    role: str = Field(default="")
    kind: ModuleKind
    parents: List[str] = Field(default_factory=list)
    children: List[str] = Field(default_factory=list)
    instance_hints: List[RepoInstanceHint] = Field(default_factory=list)
    repo_notes: List[str] = Field(default_factory=list)


class PlanningDecisions(BaseModel):
    generation_order: List[str] = Field(default_factory=list)
    leaf_first: bool = Field(default=True)
    shared_modules: List[str] = Field(default_factory=list)
    top_level_integration_notes: List[str] = Field(default_factory=list)


class Stage2RepoSkeletonArtifact(BaseModel):
    schema_version: str = Field(default="repo_skeleton_v1")
    task_id: str = Field(..., min_length=1)
    source_schema_version: str = Field(default="module_contracts_v1")
    stage2_status: str = Field(default="repo_skeleton_planned", min_length=1)
    top_module: str = Field(default="")
    module_order: List[str] = Field(default_factory=list)
    global_invariants: GlobalInvariants = Field(default_factory=GlobalInvariants)
    modules: List[RepoModuleSkeleton] = Field(default_factory=list)
    planning_decisions: PlanningDecisions = Field(default_factory=PlanningDecisions)
    open_issues: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_structure(self) -> "Stage2RepoSkeletonArtifact":
        module_names = [item.module for item in self.modules]
        if self.top_module and self.top_module not in module_names:
            raise ValueError(f"top_module `{self.top_module}` must appear in modules")
        if self.module_order:
            if len(self.module_order) != len(set(self.module_order)):
                raise ValueError("module_order must not contain duplicates")
            if set(self.module_order) != set(module_names):
                raise ValueError("module_order must match the module set in modules")
        return self
