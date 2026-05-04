from __future__ import annotations

from typing import Any, Dict


class ModulePlanCompatibilityAdapter:
    """Placeholder for future impl-level compatibility export."""

    def to_impl_level_payload(
        self,
        final_plan: Any,
        artifacts: Dict[str, Any],
    ) -> Dict[str, Any]:
        raise NotImplementedError(
            "Module planner compatibility export is reserved for a future phase. "
            "This first release only produces planner artifacts."
        )
