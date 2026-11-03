from __future__ import annotations

from typing import Any, Dict, Protocol


class PlanningContextProvider(Protocol):
    def get_stage_context(
        self,
        stage_name: str,
        task_input: Any,
        partial_artifacts: Dict[str, Any],
    ) -> Dict[str, Any]:
        ...


class PlanningArtifactSink(Protocol):
    def record_stage_output(
        self,
        stage_name: str,
        artifact: Any,
        task_input: Any,
    ) -> None:
        ...


class ProcessEventSink(Protocol):
    """Optional action observer; legacy callers need no Web dependency."""
    def emit(self, event_type: str, **fields: Any) -> Any:
        ...


class NullProcessEventSink:
    def emit(self, event_type: str, **fields: Any) -> None:
        return None


class NullPlanningContextProvider:
    def get_stage_context(
        self,
        stage_name: str,
        task_input: Any,
        partial_artifacts: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {}


class NullPlanningArtifactSink:
    def record_stage_output(
        self,
        stage_name: str,
        artifact: Any,
        task_input: Any,
    ) -> None:
        return None
