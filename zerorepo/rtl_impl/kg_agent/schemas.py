from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


DebugStatus = Literal["disabled", "skipped", "pass", "fixed", "fail", "error"]


class ModuleSimulationStatus(BaseModel):
    module: str = Field(..., min_length=1)
    status: DebugStatus
    passed: bool
    mismatch_count: int = Field(default=0, ge=0)
    debug_trials: int = Field(default=0, ge=0)
    final_rtl_path: str = Field(default="")
    trace_report_path: str = Field(default="")
    sim_output_path: str = Field(default="")
    reason: str = Field(default="")
    stage: str = Field(default="post_module_debug")
    timestamp: str = Field(default="")
