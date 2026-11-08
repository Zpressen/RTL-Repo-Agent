from __future__ import annotations

import json
from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from .contracts import Stage1ContractsArtifact, Stage1FactLedger
from .temporal import GlobalTemporalFactsArtifact


ModuleKind = Literal["top_controller", "iterative_engine", "leaf_combinational", "leaf_stateful"]


class ClockingModel(BaseModel):
    primary_clock: str = Field(default="")
    reset_signal: str = Field(default="")
    reset_style: str = Field(default="")


class SkeletonHierarchyEdge(BaseModel):
    parent: str = Field(default="")
    child: str = Field(default="")
    source_kind: str = Field(default="explicit")
    supporting_fact_ids: List[str] = Field(default_factory=list)
    rationale: str = Field(default="")
    confidence: str = Field(default="")


class RepoInstanceHint(BaseModel):
    module: str = Field(default="")
    count: int | str = Field(default="")
    usage: str = Field(default="")
    source_kind: str = Field(default="explicit")
    supporting_fact_ids: List[str] = Field(default_factory=list)
    rationale: str = Field(default="")
    confidence: str = Field(default="")


class GlobalInvariants(BaseModel):
    system_role: str = Field(default="")
    clocking_model: ClockingModel = Field(default_factory=ClockingModel)
    hierarchy: List[SkeletonHierarchyEdge] = Field(default_factory=list)
    file_map: Dict[str, str] = Field(default_factory=dict)
    cross_module_alignment: List[str] = Field(default_factory=list)
    global_data_conventions: List[str] = Field(default_factory=list)


class RepoModuleSkeleton(BaseModel):
    responsibility_ids: List[str] = Field(default_factory=list)
    applicable_constraint_ids: List[str] = Field(default_factory=list)
    module: str = Field(..., min_length=1)
    file_path: str = Field(default="")
    role: str = Field(default="")
    kind: ModuleKind
    source_kind: str = Field(default="explicit")
    supporting_fact_ids: List[str] = Field(default_factory=list)
    rationale: str = Field(default="")
    confidence: str = Field(default="")
    module_decision: str = Field(default="required")
    parents: List[str] = Field(default_factory=list)
    children: List[str] = Field(default_factory=list)
    instance_hints: List[RepoInstanceHint] = Field(default_factory=list)
    repo_notes: List[str] = Field(default_factory=list)


class Stage2SourceSpec(BaseModel):
    path: str = Field(default="")
    stem: str = Field(default="")
    markdown: str = Field(default="")


class Stage2PlanningInput(BaseModel):
    schema_version: str = Field(default="stage2_planning_input_v1")
    task_id: str = Field(..., min_length=1)
    spec_index: Dict[str, str] = Field(default_factory=dict)
    source_specs: List[Stage2SourceSpec] = Field(default_factory=list)
    fact_ledger: Stage1FactLedger = Field(default_factory=Stage1FactLedger)
    legacy_contract_projection: Stage1ContractsArtifact | None = Field(default=None)
    compat_module_candidates: List[str] = Field(default_factory=list)
    temporal_facts: GlobalTemporalFactsArtifact | None = Field(default=None)


class PlanningDecisions(BaseModel):
    generation_order: List[str] = Field(default_factory=list)
    leaf_first: bool = Field(default=True)
    shared_modules: List[str] = Field(default_factory=list)
    top_level_integration_notes: List[str] = Field(default_factory=list)


class Stage2RepoSkeletonArtifact(BaseModel):
    schema_version: str = Field(default="repo_skeleton_v1")
    task_id: str = Field(..., min_length=1)
    input_fingerprint: str = Field(default="")
    source_schema_version: str = Field(default="stage2_planning_input_v1")
    stage2_status: str = Field(default="repo_skeleton_planned", min_length=1)
    top_module: str = Field(default="")
    module_order: List[str] = Field(default_factory=list)
    global_invariants: GlobalInvariants = Field(default_factory=GlobalInvariants)
    modules: List[RepoModuleSkeleton] = Field(default_factory=list)
    planning_decisions: PlanningDecisions = Field(default_factory=PlanningDecisions)
    open_issues: List[str] = Field(default_factory=list)

    @field_validator("open_issues", mode="before")
    @classmethod
    def normalize_open_issues(cls, value: Any) -> List[str]:
        if value is None:
            return []
        items = value if isinstance(value, list) else [value]
        normalized: list[str] = []
        for item in items:
            text = cls._open_issue_to_text(item)
            if text:
                normalized.append(text)
        return normalized

    @staticmethod
    def _open_issue_to_text(item: Any) -> str:
        if item is None:
            return ""
        if isinstance(item, str):
            return item.strip()
        if isinstance(item, dict):
            parts: list[str] = []
            primary = item.get("issue") or item.get("summary") or item.get("topic") or item.get("question")
            if primary:
                parts.append(str(primary).strip())
            for key in ("decision", "options", "rationale", "reason", "impact"):
                if key not in item or item[key] in (None, "", []):
                    continue
                value = item[key]
                if isinstance(value, list):
                    rendered = "; ".join(str(entry).strip() for entry in value if str(entry).strip())
                elif isinstance(value, dict):
                    rendered = json.dumps(value, ensure_ascii=False, sort_keys=True)
                else:
                    rendered = str(value).strip()
                if rendered:
                    parts.append(f"{key}: {rendered}")
            if not parts:
                for key, value in item.items():
                    if value in (None, "", []):
                        continue
                    if isinstance(value, (dict, list)):
                        rendered = json.dumps(value, ensure_ascii=False, sort_keys=True)
                    else:
                        rendered = str(value).strip()
                    if rendered:
                        parts.append(f"{key}: {rendered}")
            return ". ".join(part for part in parts if part).strip()
        if isinstance(item, list):
            return "; ".join(str(entry).strip() for entry in item if str(entry).strip())
        return str(item).strip()

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
