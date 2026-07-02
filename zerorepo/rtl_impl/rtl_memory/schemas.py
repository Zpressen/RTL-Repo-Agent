from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


MemoryType = Literal[
    "repair_outcome",
    "negative_direction",
    "planning_correction",
    "merge_rule",
]


class RTLMemoryHeader(BaseModel):
    memory_id: str
    type: MemoryType
    stage: str
    description: str = ""
    path: str = ""
    module: str = ""
    module_family: str = ""
    signals: list[str] = Field(default_factory=list)
    failure_type: str = ""
    alignment: str = ""
    outcome: str = ""
    confidence: float = 0.5
    verified_by: list[str] = Field(default_factory=list)
    source_artifacts: list[str] = Field(default_factory=list)
    trigger_signals: list[str] = Field(default_factory=list)
    trigger_failure_type: str = ""
    trigger_alignment: str = ""
    risk_signals: list[str] = Field(default_factory=list)
    patch_pattern: str = ""
    anti_trigger: str = ""

    def brief(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "memory_id": self.memory_id,
            "type": self.type,
            "stage": self.stage,
            "module": self.module,
            "module_family": self.module_family,
            "signals": self.signals,
            "failure_type": self.failure_type,
            "alignment": self.alignment,
            "outcome": self.outcome,
            "confidence": self.confidence,
            "description": self.description,
            "trigger_signals": self.trigger_signals,
            "trigger_failure_type": self.trigger_failure_type,
            "trigger_alignment": self.trigger_alignment,
            "risk_signals": self.risk_signals,
            "patch_pattern": self.patch_pattern,
            "anti_trigger": self.anti_trigger,
        }


class RTLMemoryRecord(BaseModel):
    header: RTLMemoryHeader
    body: str


class SelectedMemory(BaseModel):
    path: str
    header: RTLMemoryHeader
    content: str


def normalize_memory_path(path: str | Path) -> str:
    return str(Path(path).as_posix()).lstrip("./")
