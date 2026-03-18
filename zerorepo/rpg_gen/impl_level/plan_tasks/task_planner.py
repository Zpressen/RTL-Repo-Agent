"""
Task Planning Agent for organizing implementation tasks
Based on the agent pattern from graph/refactored_agents
"""
import logging
import json
import uuid
from copy import deepcopy
from typing import Union, Dict, Optional, List, Any
from pydantic import BaseModel, Field
from collections import Counter
from datetime import datetime
import json5
from zerorepo.rpg_gen.base import (
    RPG,
    Tool, ToolCall,
    ToolExecResult, ToolCallArguments,
    LLMClient, LLMConfig, Memory,
    BaseAgent, BaseEnv
)
from .prompts.task_planner import PLAN_TASK_BATCHES_TOOL, BATCH_PLANNER
from .task_batch import TaskBatch
from ..rtl_trace import (
    load_rtl_spec_facts,
    build_rtl_trace_catalog,
    build_trace_context,
    format_trace_context,
    build_implementation_node_catalog,
    build_code_anchor_catalog,
    build_implementation_hint_catalog,
    build_file_implementation_context_by_path,
    build_unit_implementation_context,
    format_implementation_context,
)


# ========================
# 2. AGENT TOOL
# ========================

RTL_UNIT_KIND_MAP = {
    "rtl_module": "rtl_module",
    "rtl_top_module": "rtl_module",
    "rtl_package": "rtl_package",
    "testbench": "testbench",
    "tb_model": "testbench",
    "script": "script",
    "build_file": "build",
}

RTL_SPECIAL_TASK_TYPES = {"subtree_verification", "final_repo_validation"}


def _is_rtl_repo(repo_data: Optional[Dict[str, Any]]) -> bool:
    rtl_metadata = (repo_data or {}).get("rtl_metadata", {})
    return rtl_metadata.get("mode") == "rtl_spec2repo"


def _get_rtl_file_specs(repo_data: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    rtl_metadata = (repo_data or {}).get("rtl_metadata", {})
    return {
        str(item.get("file_path", "")).strip(): item
        for item in (rtl_metadata.get("file_specs", []) or [])
        if isinstance(item, dict) and str(item.get("file_path", "")).strip()
    }


def _get_rtl_target_units(file_spec: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    file_spec = file_spec or {}
    return [
        unit
        for unit in (file_spec.get("target_units", []) or [])
        if isinstance(unit, dict) and str(unit.get("unit_name", "")).strip() and str(unit.get("unit_kind", "")).strip()
    ]


def _get_target_unit_trace_ids(target_unit: Optional[Dict[str, Any]]) -> List[str]:
    target_unit = target_unit or {}
    trace_ids: List[str] = []
    for item in (target_unit.get("requirement_details", []) or []):
        if isinstance(item, dict):
            value = str(item.get("req_id", "")).strip()
            if value:
                trace_ids.append(value)
    for item in (target_unit.get("test_details", []) or []):
        if isinstance(item, dict):
            value = str(item.get("test_id", "")).strip()
            if value:
                trace_ids.append(value)
    for item in (target_unit.get("property_details", []) or []):
        if isinstance(item, dict):
            value = str(item.get("prop_id", "")).strip()
            if value:
                trace_ids.append(value)
    return trace_ids


def _format_rtl_target_unit_spec(file_path: str, target_unit: Dict[str, Any]) -> str:
    requirement_lines = [
        f"{item.get('req_id', '')}: {item.get('statement', '')}".strip(": ")
        for item in (target_unit.get("requirement_details", []) or [])
        if isinstance(item, dict) and str(item.get("req_id", "")).strip()
    ]
    test_lines = [
        f"{item.get('test_id', '')}: {item.get('purpose', '')}".strip(": ")
        for item in (target_unit.get("test_details", []) or [])
        if isinstance(item, dict) and str(item.get("test_id", "")).strip()
    ]
    property_lines = [
        f"{item.get('prop_id', '')}: {item.get('statement', '')}".strip(": ")
        for item in (target_unit.get("property_details", []) or [])
        if isinstance(item, dict) and str(item.get("prop_id", "")).strip()
    ]
    node_lines = [
        f"{item.get('node_id', '')}: {item.get('goal', '')}".strip(": ")
        for item in (target_unit.get("node_details", []) or [])
        if isinstance(item, dict) and str(item.get("node_id", "")).strip()
    ]
    hint_lines = [
        f"{item.get('hint_id', '')}: {item.get('statement', '')}".strip(": ")
        for item in (target_unit.get("hint_details", []) or [])
        if isinstance(item, dict) and str(item.get("hint_id", "")).strip()
    ]
    return (
        f"file_path={file_path}\n"
        f"unit_name={target_unit.get('unit_name', '')}\n"
        f"unit_kind={target_unit.get('unit_kind', '')}\n"
        f"role={target_unit.get('role', '')}\n"
        f"responsibility={target_unit.get('responsibility', '')}\n"
        f"implementation_summary={target_unit.get('implementation_summary', '')}\n"
        f"depends_on_files={target_unit.get('depends_on_files', [])}\n"
        f"depends_on_units={target_unit.get('depends_on_units', [])}\n"
        f"requirements={requirement_lines}\n"
        f"tests={test_lines}\n"
        f"properties={property_lines}\n"
        f"nodes={node_lines}\n"
        f"hints={hint_lines}"
    )


def _build_rtl_unit_bundle(file_path: str, file_spec: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    file_spec = file_spec or {}
    file_kind = str(file_spec.get("file_kind", "")).strip()
    responsibility = str(file_spec.get("responsibility", "")).strip()
    depends_on_files = list(file_spec.get("depends_on_files", []) or [])
    owned_modules = [str(item).strip() for item in (file_spec.get("owned_modules", []) or []) if str(item).strip()]
    target_units = _get_rtl_target_units(file_spec)
    if target_units:
        units_to_spec = {
            str(unit.get("unit_name", "")).strip(): _format_rtl_target_unit_spec(file_path, unit)
            for unit in target_units
        }
        unit_to_kind = {
            str(unit.get("unit_name", "")).strip(): str(unit.get("unit_kind", "")).strip()
            for unit in target_units
        }
        unit_to_feature = {
            str(unit.get("unit_name", "")).strip(): _get_target_unit_trace_ids(unit)
            for unit in target_units
        }
        return {
            "units_to_spec": {key: value for key, value in units_to_spec.items() if key},
            "unit_to_kind": {key: value for key, value in unit_to_kind.items() if key and value},
            "unit_to_feature": {key: value for key, value in unit_to_feature.items() if key},
        }
    feature_ids = (
        list(file_spec.get("related_req_ids", []) or [])
        + list(file_spec.get("related_test_ids", []) or [])
        + list(file_spec.get("related_prop_ids", []) or [])
    )
    unit_kind = RTL_UNIT_KIND_MAP.get(file_kind)
    if not unit_kind:
        return {"units_to_spec": {}, "unit_to_kind": {}, "unit_to_feature": {}}

    def make_spec(unit_name: str) -> str:
        return (
            f"file_path={file_path}\n"
            f"unit_name={unit_name}\n"
            f"unit_kind={unit_kind}\n"
            f"responsibility={responsibility}\n"
            f"depends_on_files={depends_on_files}\n"
            f"owned_modules={owned_modules}\n"
            f"related_ids={feature_ids}"
        )

    unit_names: List[str] = []
    if unit_kind == "rtl_module":
        unit_names = [f"module:{name}" for name in (owned_modules or [file_path])]
    elif unit_kind == "rtl_package":
        unit_names = [f"package:{name}" for name in (owned_modules or [file_path])]
    elif unit_kind == "testbench":
        unit_names = [f"tb:{file_path}"]
    elif unit_kind == "script":
        unit_names = [f"script:{file_path}"]
    elif unit_kind == "build":
        unit_names = [f"build:{file_path}"]

    return {
        "units_to_spec": {name: make_spec(name) for name in unit_names},
        "unit_to_kind": {name: unit_kind for name in unit_names},
        "unit_to_feature": {name: deepcopy(feature_ids) for name in unit_names},
    }


def _get_rtl_trace_ids(file_spec: Optional[Dict[str, Any]]) -> List[str]:
    file_spec = file_spec or {}
    target_units = _get_rtl_target_units(file_spec)
    if target_units:
        trace_ids: List[str] = []
        for unit in target_units:
            trace_ids.extend(_get_target_unit_trace_ids(unit))
        return trace_ids
    trace_ids: List[str] = []
    for key in ("related_req_ids", "related_test_ids", "related_prop_ids"):
        for item in (file_spec.get(key, []) or []):
            value = str(item).strip()
            if value:
                trace_ids.append(value)
    return trace_ids


def _normalize_rtl_unit_features(
    file_spec: Optional[Dict[str, Any]],
    unit_names: List[str],
    units_to_feature: Optional[Dict[str, List[Any]]],
) -> Dict[str, List[Any]]:
    target_units = _get_rtl_target_units(file_spec)
    if target_units:
        by_unit = {
            str(unit.get("unit_name", "")).strip(): _get_target_unit_trace_ids(unit)
            for unit in target_units
            if str(unit.get("unit_name", "")).strip()
        }
        expected_units = [str(unit).strip() for unit in unit_names if str(unit).strip()] or list(by_unit.keys())
        return {
            unit_name: deepcopy(by_unit.get(unit_name, []))
            for unit_name in expected_units
        }
    trace_ids = _get_rtl_trace_ids(file_spec)
    normalized: Dict[str, List[Any]] = {}
    expected_units = [str(unit).strip() for unit in unit_names if str(unit).strip()]

    if not expected_units:
        expected_units = [
            str(unit).strip()
            for unit in (units_to_feature or {}).keys()
            if str(unit).strip()
        ]

    for unit_name in expected_units:
        normalized[unit_name] = deepcopy(trace_ids)

    return normalized


def _build_rtl_unit_trace_context(
    unit_names: List[str],
    units_to_feature: Optional[Dict[str, List[Any]]],
    trace_catalog: Optional[Dict[str, Dict[str, Any]]],
) -> Dict[str, List[Dict[str, Any]]]:
    units_to_feature = units_to_feature or {}
    return {
        unit_name: build_trace_context(
            [str(item).strip() for item in (units_to_feature.get(unit_name, []) or []) if str(item).strip()],
            trace_catalog or {},
        )
        for unit_name in unit_names
    }


def _build_rtl_secondary_context(file_spec: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    file_spec = file_spec or {}
    return {
        "responsibility": str(file_spec.get("responsibility", "")).strip(),
        "implementation_summary": str(file_spec.get("implementation_summary", "")).strip(),
        "related_node_ids": [str(item).strip() for item in (file_spec.get("related_node_ids", []) or []) if str(item).strip()],
        "related_code_anchor_ids": [str(item).strip() for item in (file_spec.get("related_code_anchor_ids", []) or []) if str(item).strip()],
        "related_hint_ids": [str(item).strip() for item in (file_spec.get("related_hint_ids", []) or []) if str(item).strip()],
    }


def _build_rtl_unit_implementation_context(
    file_path: str,
    file_spec: Optional[Dict[str, Any]],
    unit_to_kind: Optional[Dict[str, str]],
    file_implementation_context_by_path: Optional[Dict[str, Dict[str, List[Dict[str, Any]]]]],
) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    file_spec = file_spec or {}
    unit_to_kind = unit_to_kind or {}
    owned_modules = [str(item).strip() for item in (file_spec.get("owned_modules", []) or []) if str(item).strip()]
    contexts: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}

    for unit_name, unit_kind in unit_to_kind.items():
        if unit_kind not in {"rtl_module", "rtl_package"}:
            continue
        module_name = unit_name.split(":", 1)[-1].strip() if ":" in unit_name else ""
        if unit_kind == "rtl_package" and not module_name and owned_modules:
            module_name = owned_modules[0]
        contexts[unit_name] = build_unit_implementation_context(
            file_path=file_path,
            unit_kind=str(file_spec.get("file_kind", "")).strip(),
            module_name=module_name,
            file_implementation_context_by_path=file_implementation_context_by_path,
        )
    return contexts


def _format_secondary_context(secondary_context: Optional[Dict[str, Any]]) -> str:
    secondary_context = secondary_context or {}
    lines: List[str] = []
    responsibility = str(secondary_context.get("responsibility", "")).strip()
    if responsibility:
        lines.append(f"- responsibility: {responsibility}")
    implementation_summary = str(secondary_context.get("implementation_summary", "")).strip()
    if implementation_summary:
        lines.append(f"- implementation_summary: {implementation_summary}")
    for key in ("related_node_ids", "related_code_anchor_ids", "related_hint_ids"):
        values = [str(item).strip() for item in (secondary_context.get(key, []) or []) if str(item).strip()]
        if values:
            lines.append(f"- {key}: {values}")
    return "\n".join(lines) if lines else "- No supplementary file context."

class PlanTaskBatchesTool(Tool):
    name = "plan_task_batches"
    description = PLAN_TASK_BATCHES_TOOL
    
    class ParamModel(BaseModel):
        batches: List[Dict] = Field(..., description="List of task batches for this file")

    @staticmethod
    def _normalize_raw_tool_payload(raw: str) -> str:
        raw = raw.strip()
        if "<tool_call>" in raw:
            raw = raw.split("<tool_call>", 1)[-1]
        if "</tool_call>" in raw:
            raw = raw.split("</tool_call>", 1)[0]
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
        raw = raw.replace("```json", "").replace("```", "").strip()
        if raw.startswith("{{") and raw.endswith("}}"):
            raw = raw[1:-1].strip()
        return raw
    
    @classmethod
    def custom_parse(cls, raw: str) -> List[ToolCallArguments]:
        """Parse raw JSON input for task batches"""
        valid_tools = []
        
        try:
            if isinstance(raw, str):
                raw = cls._normalize_raw_tool_payload(raw)
                raw_tools = json5.loads(raw)
                raw_tools = raw_tools if isinstance(raw_tools, list) else [raw_tools]
        except json.JSONDecodeError as e:
            logging.error(f"[custom_parse] Invalid JSON: {e}")
            return valid_tools
        
        for raw_tool in raw_tools:
            try:
                tool_name = raw_tool.get("tool_name", "")
                if tool_name.lower().strip() != cls.name.lower():
                    continue
                
                params = raw_tool.get("parameters", raw_tool)
                parsed = cls.ParamModel(**params).model_dump()
                valid_tools.append(parsed)
            except Exception as e:
                logging.error(f"[custom_parse] Error: {e}")
                continue
        
        return valid_tools
    
    @classmethod
    async def execute(cls, arguments: Dict, env: Optional[Any] = None) -> ToolExecResult:
        try:
            file_unit_keys = list(env.get_unit_catalog().keys())
            batches = arguments.get("batches", [])

            if not batches:
                return ToolExecResult(
                    output=None,
                    error="Invalid arguments: 'batches' is missing or empty. You must provide a complete list of ALL task batches for this file, not partial updates. Re-plan all units from scratch.",
                    error_code=1,
                    state=None
                )

            # Validate batch structure + collect unit keys
            all_unit_keys: List[str] = []

            for i, batch in enumerate(batches):
                required_keys = ["units", "task"]
                missing = [k for k in required_keys if k not in batch]
                if missing:
                    return ToolExecResult(
                        output=None,
                        error=f"Invalid batch at index {i}: missing required keys {missing}. Each batch must include: {required_keys}. You must re-plan ALL batches for this file, not just fix the problematic ones. Start over with a complete plan.",
                        error_code=1,
                        state=None
                    )

                batch_units = batch["units"]
                if not isinstance(batch_units, list) or not batch_units:
                    return ToolExecResult(
                        output=None,
                        error=f"Invalid batch at index {i}: 'units' must be a non-empty list of unit keys. You must re-plan ALL batches for this file with correct format. Each batch should have: {{'units': [...], 'task': '...'}}",
                        error_code=1,
                        state=None
                    )

                all_unit_keys.extend(batch_units)

            expected = set(file_unit_keys)
            got = set(all_unit_keys)

            # Detect duplicates across all batches in current call (same unit key appears multiple times)
            counter = Counter(all_unit_keys)
            duplicates = sorted([k for k, c in counter.items() if c > 1])

            # Reject duplicates within current call
            if duplicates:
                return ToolExecResult(
                    output=None,
                    error=(
                        "Duplicate unit keys detected across batches. "
                        f"Each unit key should appear exactly once. Duplicates: {duplicates}.\n\n"
                        "IMPORTANT: You must re-plan ALL batches for this file from scratch. "
                        "Ensure each unit appears in exactly one batch. Start with a fresh complete plan."
                    ),
                    error_code=1,
                    state=None
                )

            # Check if this is not a complete re-planning (we require complete re-planning each time)
            if got != expected:
                missing = sorted(list(expected - got))
                extra = sorted(list(got - expected))
                return ToolExecResult(
                    output=None,
                    error=(
                        "Unit key mismatch: expected "
                        f"{len(expected)} unique unit keys from units in file, got {len(got)} unique keys from batches.\n"
                        f"Missing units: {missing}\n"
                        f"Extra units: {extra}\n\n"
                        "IMPORTANT: You must re-plan ALL batches for this file from scratch. Do not try to add only the missing units. "
                        "Create a complete new plan that includes ALL units: " + str(file_unit_keys)
                    ),
                    error_code=1,
                    state=None
                )

            # All units must be covered - success case
            return ToolExecResult(
                output=f"Planned {len(batches)} batches covering all {len(expected)} file units.",
                error=None,
                error_code=0,
                state={"batches": batches}
            )
        except Exception as e:
            return ToolExecResult(
                output=None,
                error=f"Unexpected error while planning task batches: {type(e).__name__}: {e}",
                error_code=1,
                state={"batches": arguments.get("batches", [])}
            )


# ========================  
# 3. ENVIRONMENT
# ========================

class TaskPlanningEnv(BaseEnv):
    """Environment for task planning phase"""

    def __init__(
        self,
        cur_subtree: str,
        repo_rpg: RPG,
        file_path: str,
        units_to_feature: Dict[str, List],
        units_to_code: Dict[str, str],
        units_to_spec: Optional[Dict[str, str]] = None,
        unit_to_kind: Optional[Dict[str, str]] = None,
        units_to_trace_context: Optional[Dict[str, List[Dict[str, Any]]]] = None,
        units_to_implementation_context: Optional[Dict[str, Dict[str, List[Dict[str, Any]]]]] = None,
        secondary_context: Optional[Dict[str, Any]] = None,
        register_tools: List = [PlanTaskBatchesTool],
        logger: logging.Logger = None
    ):
        super().__init__(
            register_tools,
            logger
        )

        self.repo_rpg=repo_rpg
        self.cur_subtree = cur_subtree
        self.file_path = file_path
        self.units_to_feature = units_to_feature
        self.units_to_code = units_to_code
        self.units_to_spec = units_to_spec or {}
        self.unit_to_kind = unit_to_kind or {}
        self.units_to_trace_context = units_to_trace_context or {}
        self.units_to_implementation_context = units_to_implementation_context or {}
        self.secondary_context = secondary_context or {}

        self.planned_batches = []
        self.is_completed = False
        self.logger = logger or logging.getLogger(__name__)

    def get_unit_catalog(self) -> Dict[str, str]:
        return self.units_to_spec or self.units_to_code

    def is_rtl_mode(self) -> bool:
        return bool(self.units_to_spec or self.unit_to_kind)

    def should_terminate(self, tool_calls, tool_results):
        """Check if planning is complete"""
        # If already completed, remain terminated
        if self.is_completed:
            return True
            
        # Check if there are successful results
        if tool_results and all(result.success for result in tool_results):
            # Check if it's the plan_task_batches tool
            for tool_call, result in zip(tool_calls, tool_results):
                if tool_call.name == "plan_task_batches" and result.success:
                    # The actual completion will be set in update_env
                    # after validating the batches are complete
                    pass
        
        return self.is_completed

    def update_env(self, tool_call, result):
        """Update environment after tool execution"""
        if tool_call.name == "plan_task_batches" and result.success:
            try:
                batches_data = result.state.get("batches", [])
                
                # Convert to TaskBatch objects
                batches = []
                for idx, batch_data in enumerate(batches_data):
                    task = batch_data["task"]
                    b_unit_keys = batch_data["units"]
                    b_unit_keys = b_unit_keys if isinstance(
                        b_unit_keys, list
                    ) else [b_unit_keys]
        
                    b_unit_to_code = {
                        unit: self.units_to_code[unit] for unit in b_unit_keys
                        if unit in self.units_to_code
                    }
                    b_unit_to_spec = {
                        unit: self.get_unit_catalog()[unit] for unit in b_unit_keys
                        if unit in self.get_unit_catalog()
                    }
                    b_unit_to_features = {
                        unit: self.units_to_feature[unit] for unit in b_unit_keys
                    }
                    b_unit_to_kind = {
                        unit: self.unit_to_kind[unit] for unit in b_unit_keys
                        if unit in self.unit_to_kind
                    }
                    
                    batch = TaskBatch(
                        task=task,
                        file_path=self.file_path,
                        units_key=b_unit_keys,
                        unit_to_code=b_unit_to_code,
                        unit_to_spec=b_unit_to_spec,
                        unit_to_kind=b_unit_to_kind,
                        unit_to_features=b_unit_to_features,
                        priority=idx,
                        subtree=self.cur_subtree
                    )
                    batches.append(batch)
                
                # Only update planned_batches if the planning is complete and correct
                # The tool execution already validated that all units are covered
                self.planned_batches = batches
                self.is_completed = True  # Mark as completed immediately after successful planning
                self.logger.info(f"Successfully planned {len(batches)} batches for {self.file_path}")
                
            except Exception as e:
                # Don't save partial results on error
                self.logger.error(f"Failed to update planning: {e}")
                self.planned_batches = []
                self.is_completed = False


# ========================
# 4. AGENT
# ========================

class TaskPlannerAgent(BaseAgent):
    """Agent for planning implementation tasks"""
    
    def __init__(
        self,
        llm_cfg: Union[str, Dict, LLMConfig],
        file_path: str,
        repo_rpg: RPG,
        cur_subtree: str,
        units_to_feature: Dict[str, List],
        units_to_code: Dict[str, str],
        units_to_spec: Optional[Dict[str, str]] = None,
        unit_to_kind: Optional[Dict[str, str]] = None,
        units_to_trace_context: Optional[Dict[str, List[Dict[str, Any]]]] = None,
        units_to_implementation_context: Optional[Dict[str, Dict[str, List[Dict[str, Any]]]]] = None,
        secondary_context: Optional[Dict[str, Any]] = None,
        rtl_file_spec: Optional[Dict[str, Any]] = None,
        system_prompt: str =BATCH_PLANNER,
        context_window: int = 30,
        register_tools: Optional[List[Tool]] = [PlanTaskBatchesTool],
        logger: Optional[logging.Logger] = None,
        **kwargs
    ):
        super().__init__(
            llm_cfg=llm_cfg,
            system_prompt=system_prompt,
            context_window=context_window,
            register_tools=register_tools,
            logger=logger,
            **kwargs
        )
        self.repo_rpg = repo_rpg
        self.rtl_file_spec = rtl_file_spec or {}
        
        self._env = TaskPlanningEnv(
            repo_rpg=repo_rpg,
            cur_subtree=cur_subtree,
            file_path=file_path,
            units_to_feature=units_to_feature,
            units_to_code=units_to_code,
            units_to_spec=units_to_spec,
            unit_to_kind=unit_to_kind,
            units_to_trace_context=units_to_trace_context,
            units_to_implementation_context=units_to_implementation_context,
            secondary_context=secondary_context,
            register_tools=register_tools,
            logger=logger
        )        

    def _build_rtl_task(self) -> str:
        file_spec = self.rtl_file_spec or {}
        unit_catalog = self._env.get_unit_catalog()
        unit_kinds = self._env.unit_to_kind or {}
        units_summary = []
        for unit_name, unit_spec in unit_catalog.items():
            unit_kind = unit_kinds.get(unit_name, "unknown")
            features = self._env.units_to_feature.get(unit_name, [])
            trace_context = self._env.units_to_trace_context.get(unit_name, [])
            implementation_context = self._env.units_to_implementation_context.get(unit_name, {})
            units_summary.append(
                f"### {unit_name}\n"
                f"- unit_kind: {unit_kind}\n"
                f"- trace_ids: {features}\n"
                f"- trace_context:\n{format_trace_context(trace_context)}\n"
                f"- implementation_context:\n{format_implementation_context(implementation_context)}\n"
                f"- contract:\n{unit_spec}"
            )

        return (
            f"Plan the implementation tasks for the repository: {self.repo_rpg.repo_name}\n"
            f"Repository description: {self.repo_rpg.repo_info}\n\n"
            "Context:\n"
            f"- You are planning the implementation order for the RTL/build file: {self._env.file_path}\n"
            f"- File planning node: {self._env.cur_subtree}\n"
            f"- file_kind: {file_spec.get('file_kind', '')}\n"
            f"- responsibility: {file_spec.get('responsibility', '')}\n"
            f"- implementation_summary: {file_spec.get('implementation_summary', '')}\n"
            f"- depends_on_files: {file_spec.get('depends_on_files', [])}\n"
            f"- owned_modules: {file_spec.get('owned_modules', [])}\n"
            f"- related_req_ids: {file_spec.get('related_req_ids', [])}\n"
            f"- related_test_ids: {file_spec.get('related_test_ids', [])}\n"
            f"- related_prop_ids: {file_spec.get('related_prop_ids', [])}\n\n"
            "Supplementary file context:\n"
            f"{_format_secondary_context(self._env.secondary_context)}\n\n"
            "Target RTL units to plan:\n"
            f"{json.dumps(list(unit_catalog.keys()), indent=2)}\n\n"
            "RTL unit contracts:\n"
            f"{chr(10).join(units_summary)}\n\n"
            "Plan dependency-aware implementation batches for these RTL units. "
            "Use natural hardware/build milestones such as shared package definitions, leaf module implementation, "
            "top-level wiring, verification enablement, and build/simulation orchestration. "
            "For a leaf module, explain the local capability it delivers and what later integration it supports. "
            "For a top-level module, explain the integration responsibility and the end-to-end behavior it closes. "
            "Keep each unit in exactly one batch and avoid Python helper/class decomposition."
        )
        
    def plan_all_tasks(
        self,
        file_code: str,
        max_retry: int = 3,
        max_steps: int = 20
    ) -> Dict:
        """Plan tasks for all files in the repository"""
        if self._env.is_rtl_mode():
            task = self._build_rtl_task()
        else:
            repo_name = self.repo_rpg.repo_name
            repo_info = self.repo_rpg.repo_info
            task = (
                f"Plan the implementation tasks for the repository: {repo_name}\n"
                f"Repository description: {repo_info}\n\n"
                f"Context:\n"
                f"- You are planning the implementation order for the file: {self._env.file_path}\n"
                f"- Functional area / subtree: {self._env.cur_subtree}\n\n"
                f"Source code of the file:\n"
                f"{file_code}\n\n"
                f"Units to plan (to be implemented):\n"
                f"{json.dumps(list(self._env.get_unit_catalog().keys()), indent=2)}"
            )
        
        result = self.run(
            task=task,
            max_error_times=max_retry,
            max_steps=max_steps
        )
        
        return {
            "planned_batches": self._env.planned_batches,
            "success": self._env.is_completed,
            "agent_result": result
        }


# ========================
# 5. LEGACY INTERFACE  
# ========================

class TaskPlanner:
    """Legacy interface wrapping the new agent-based planner"""
    
    def __init__(
        self,
        rpg: RPG,
        llm_cfg: Union[Dict, LLMConfig],
        graph_data: Union[str, Dict],
        repo_data: Optional[Dict[str, Any]],
        logger: logging.Logger
    ):
        self.repo_rpg = rpg
        
        if isinstance(graph_data, str):
            with open(graph_data, 'r') as f:
                graph_data = json.load(f)
        
        self.llm_cfg = llm_cfg        
        self.graph_data = graph_data
        self.repo_data = repo_data or {}
        self.rtl_file_specs = _get_rtl_file_specs(self.repo_data)
        self.rtl_spec_facts = load_rtl_spec_facts(self.repo_data, logger)
        self.rtl_trace_catalog = build_rtl_trace_catalog(self.rtl_spec_facts)
        self.implementation_node_catalog = build_implementation_node_catalog(self.rtl_spec_facts)
        self.code_anchor_catalog = build_code_anchor_catalog(self.rtl_spec_facts)
        self.implementation_hint_catalog = build_implementation_hint_catalog(self.rtl_spec_facts)
        self.file_implementation_context_by_path = build_file_implementation_context_by_path(
            list(self.rtl_file_specs.values()),
            self.implementation_node_catalog,
            self.code_anchor_catalog,
            self.implementation_hint_catalog,
        )

        self.logger = logger
        self.planned_batches_dict = {}
        self.agent_results_dict = {}
    
    @staticmethod
    def load_batches_from_dict(
        planned_batches_dict: Dict, 
        graph_data: Dict
    ) -> List[TaskBatch]:
        """
        Utility function to convert planned_batches_dict to a properly ordered list of TaskBatch objects.
        (Deprecated: Use zerorepo.utils.task_loader.load_batches_from_dict instead)
        """
        from ....utils.task_loader import load_batches_from_dict
        return load_batches_from_dict(planned_batches_dict, graph_data)

    def plan_all_batches(self, result_path) -> List[TaskBatch]:
        """Plan all implementation batches"""
        subtree_order = self.graph_data["data_flow_phase"]["subtree_order"]
        rtl_mode = _is_rtl_repo(self.repo_data)
        
        planned_batches = {}
        agent_results = {}
        
        subtrees_data = self.graph_data['interfaces_phase']["interfaces"]["subtrees"]
        for subtree in subtree_order:
            if subtree not in subtrees_data:
                continue
                
            subtree_dict = subtrees_data[subtree]
            planned_batches[subtree] = {}
            agent_results[subtree] = {}
            
            subtree_interfaces = subtree_dict["interfaces"]
            files_order = subtree_dict["files_order"]
            
            for file_path in files_order:
                rtl_file_spec = self.rtl_file_specs.get(file_path, {})
                if file_path not in subtree_interfaces and not (rtl_mode and _get_rtl_target_units(rtl_file_spec)):
                    continue
                file_dict = subtree_interfaces.get(file_path, {})
                if rtl_mode and rtl_file_spec.get("file_kind") == "documentation":
                    self.logger.info(f"Skipping RTL documentation file during task planning: {file_path}")
                    continue

                file_code = file_dict.get("file_code", "")
                units_to_code = file_dict.get("units_to_code", {})
                units_to_spec = file_dict.get("units_to_spec", {})
                unit_to_kind = file_dict.get("unit_to_kind", {})
                units_to_feature = file_dict.get("units_to_features", {})
                units_to_trace_context = file_dict.get("units_to_trace_context", {})
                units_to_implementation_context = file_dict.get("units_to_implementation_context", {})
                secondary_context = file_dict.get("secondary_context", {})

                if rtl_mode and rtl_file_spec:
                    fallback_bundle = _build_rtl_unit_bundle(file_path, rtl_file_spec)
                    if not units_to_spec:
                        units_to_spec = fallback_bundle["units_to_spec"]
                    if not unit_to_kind:
                        unit_to_kind = fallback_bundle["unit_to_kind"]
                    if not units_to_feature:
                        units_to_feature = fallback_bundle["unit_to_feature"]
                    units_to_feature = _normalize_rtl_unit_features(
                        rtl_file_spec,
                        list((units_to_spec or {}).keys()) or list((unit_to_kind or {}).keys()),
                        units_to_feature,
                    )
                    if not units_to_trace_context:
                        units_to_trace_context = _build_rtl_unit_trace_context(
                            list((units_to_spec or {}).keys()) or list((unit_to_kind or {}).keys()),
                            units_to_feature,
                            self.rtl_trace_catalog,
                        )
                    if not units_to_implementation_context:
                        units_to_implementation_context = _build_rtl_unit_implementation_context(
                            file_path=file_path,
                            file_spec=rtl_file_spec,
                            unit_to_kind=unit_to_kind,
                            file_implementation_context_by_path=self.file_implementation_context_by_path,
                        )
                    if not secondary_context:
                        secondary_context = _build_rtl_secondary_context(rtl_file_spec)

                if not units_to_code and not units_to_spec:
                    self.logger.info(f"Skipping task planning for {file_path} - no units available")
                    continue
                
                plan_agent = TaskPlannerAgent(
                    llm_cfg=self.llm_cfg,
                    file_path=file_path,
                    repo_rpg=self.repo_rpg,
                    cur_subtree=subtree,
                    units_to_feature=units_to_feature,
                    units_to_code=units_to_code,
                    units_to_spec=units_to_spec,
                    unit_to_kind=unit_to_kind,
                    units_to_trace_context=units_to_trace_context,
                    units_to_implementation_context=units_to_implementation_context,
                    secondary_context=secondary_context,
                    rtl_file_spec=rtl_file_spec,
                    logger=self.logger
                )
                
                results = plan_agent.plan_all_tasks(
                    file_code=file_code,
                    max_retry=5,
                    max_steps=5
                )
                assert results["success"]

                file_plan_batch = results["planned_batches"]
                file_agent_result = results["agent_result"]
                
                planned_batches[subtree][file_path] = file_plan_batch
                agent_results[subtree][file_path] = file_agent_result

            if not planned_batches[subtree]:
                planned_batches.pop(subtree, None)
                agent_results.pop(subtree, None)
        
        # Add integration / final validation batches
        self._add_special_batches(planned_batches, agent_results)
                
        # Convert TaskBatch objects to dictionaries for JSON serialization
        planned_batches_serializable = {}
        for subtree, files_dict in planned_batches.items():
            planned_batches_serializable[subtree] = {}
            for file_path, batches_list in files_dict.items():
                # Convert list of TaskBatch objects to list of dictionaries
                planned_batches_serializable[subtree][file_path] = [
                    batch.to_dict() for batch in batches_list
                ]
        
        # Save results
        with open(result_path, 'w', encoding='utf-8') as f:
            json.dump({
                "planned_batches_dict": planned_batches_serializable,
                "agent_results_dict": agent_results,
                "success": True
            }, f, indent=2)
            
        self.planned_batches_dict = planned_batches
        self.agent_results_dict = agent_results
        self.logger.info(f"Planned batches and agent results saved to {result_path}")
        
        return self.get_batches_as_list()
    
    def get_batches_as_dict(self) -> Dict[str, Dict[str, List[TaskBatch]]]:
        """Return batches organized by subtree and file path (dictionary version)"""
        if not hasattr(self, 'planned_batches_dict'):
            raise RuntimeError("Must call plan_all_batches first")
        return self.planned_batches_dict
    
    def get_agent_results_as_dict(self) -> Dict[str, Dict[str, Any]]:
        """Return agent results organized by subtree and file path (dictionary version)"""
        if not hasattr(self, 'agent_results_dict'):
            raise RuntimeError("Must call plan_all_batches first")
        return self.agent_results_dict
    
    def get_batches_as_list(self) -> List[TaskBatch]:
        """Return all batches in a flattened list with proper ordering (list version)"""
        if not hasattr(self, 'planned_batches_dict'):
            raise RuntimeError("Must call plan_all_batches first")
            
        return self.load_batches_from_dict(self.planned_batches_dict, self.graph_data)
    
    def _add_special_batches(self, planned_batches: Dict, agent_results: Dict):
        """Add subtree-level verification and final validation batches."""
        rtl_mode = _is_rtl_repo(self.repo_data)

        # Get subtree order from graph data  
        subtree_order = self.graph_data.get("data_flow_phase", {}).get("subtree_order", [])
        
        # Add per-subtree verification batch
        for subtree in subtree_order:
            if subtree in planned_batches:
                has_batches = any(
                    len(batches) > 0 
                    for batches in planned_batches.get(subtree, {}).values()
                )
                
                if not has_batches:
                    self.logger.info(f"Skipping special verification for subtree {subtree} - no implementation batches")
                    continue
                
                subtree_path = self._get_subtree_path_from_rpg(subtree)
                unit_key = f"{subtree}_subtree_verification"
                if rtl_mode:
                    task_text = (
                        f"Validate the implemented RTL/build artifacts for {subtree} "
                        f"{f'located in {subtree_path}' if subtree_path else ''}. "
                        "compile, lint, or simulate the subtree as appropriate, verify dependency wiring between its files, "
                        "and check that the planned requirement/property/test coverage for this subtree is exercised without introducing integration regressions."
                    )
                    unit_to_code = {unit_key: f"# RTL subtree verification for {subtree}"}
                    unit_to_spec = {
                        unit_key: (
                            f"subtree verification contract for {subtree}: "
                            "run subtree-scoped compile/lint/sim checks, validate file dependency wiring, "
                            "and confirm relevant requirement/property/test coverage."
                        )
                    }
                    task_type = "subtree_verification"
                    marker = "<SUBTREE_VERIFICATION>"
                else:
                    task_text = (
                        f"Write comprehensive integration tests for the {subtree} module "
                        f"{f'located in {subtree_path}' if subtree_path else ''}. "
                        f"Test the interactions between all components in this module, "
                        f"verify data flow, error handling, and edge cases, and ensure all public APIs "
                        f"work correctly together. "
                        f"Focus on testing the integration points between different files in this module. "
                        f"In addition to the integration tests, create small, focused usage examples for this module "
                        f"(e.g., example scripts or functions) that demonstrate typical end-to-end usage of its main APIs. "
                        f"Create appropriate test files and example files in the module directory or the test/example "
                        f"directory as needed, following the existing project conventions."
                    )
                    unit_to_code = {unit_key: f"# Integration tests for {subtree} module"}
                    unit_to_spec = {}
                    task_type = "integration_test"
                    marker = "<INTEGRATION_TEST>"

                integration_test_batch = TaskBatch(
                    task=task_text,
                    file_path=marker,
                    units_key=[unit_key],
                    unit_to_code=unit_to_code,
                    unit_to_spec=unit_to_spec,
                    unit_to_features={unit_key: []},
                    priority=1000,
                    subtree=subtree,
                    task_type=task_type,
                )
                
                integration_file_path = f"{marker}_{subtree}"
                planned_batches[subtree][integration_file_path] = [integration_test_batch]
                agent_results[subtree][integration_file_path] = {"success": True, "type": task_type}
                
                self.logger.info(f"Added {task_type} batch for subtree: {subtree} (path: {subtree_path})")
        
        final_subtree = "FINAL_TASKS"
        planned_batches[final_subtree] = {}
        agent_results[final_subtree] = {}
        
        if rtl_mode:
            final_task = (
                "Run final repository-wide RTL validation. "
                "Execute full lint and simulation flows, verify top-level integration wiring, "
                "and perform a final sanity check that planned requirement/property/test coverage is represented across the repository."
            )
            final_file_path = "<FINAL_REPO_VALIDATION>"
            final_task_type = "final_repo_validation"
            final_unit_to_code = {"final_repo_validation": "# Final RTL repository validation"}
            final_unit_to_spec = {
                "final_repo_validation": (
                    "final repository validation contract: run full lint and simulation, "
                    "check top-level integration behavior, and confirm repository-wide traceability coverage sanity."
                )
            }
            final_features = {"final_repo_validation": []}
        else:
            final_task = (
                "Design and implement comprehensive end-to-end tests for the entire repository. "
                "Cover system tests, integration tests across all major modules, performance scenarios, "
                "and critical edge cases. "
                "Verify the complete workflow from input to output and validate interactions between modules "
                "so the system works reliably as a whole. "
                "In addition, create clear usage examples (e.g., example scripts or notebooks) that demonstrate "
                "typical end-to-end workflows, and add or update an executable main entry point (e.g., main.py) "
                "that can run a representative full pipeline using the implemented tests and examples. "
                "Place the new test files, examples, and main entry point in appropriate locations in the project structure."
            )
            final_file_path = "<COMPREHENSIVE_TEST>"
            final_task_type = "final_test_docs"
            final_unit_to_code = {"comprehensive_tests": "# Comprehensive end-to-end tests"}
            final_unit_to_spec = {}
            final_features = {"comprehensive_tests": ["comprehensive system testing"]}

        comprehensive_test_batch = TaskBatch(
            task=final_task,
            file_path=final_file_path,
            units_key=list(final_unit_to_code.keys()),
            unit_to_code=final_unit_to_code,
            unit_to_spec=final_unit_to_spec,
            unit_to_features=final_features,
            priority=2000,
            subtree=final_subtree,
            task_type=final_task_type,
        )

        planned_batches[final_subtree][final_file_path] = [comprehensive_test_batch]
        self.logger.info(f"Added final special batch: {final_task_type}")
    
    def _get_subtree_path_from_rpg(self, subtree_name: str) -> Optional[str]:
        """Get the directory path for a subtree from RPG metadata"""
        try:
            # Look for nodes with matching names at level 1 (direct children of repo)
            for node in self.repo_rpg.nodes.values():
                if (node.name == subtree_name and 
                    node.level == 1):
                    
                    if node.meta and node.meta.path and node.meta.path != ".":
                        final_path = node.meta.path
                        final_path = final_path if isinstance(final_path, str) else ", ".join(final_path)
                        return final_path
                    break
            
            return ""
            
        except Exception as e:
            self.logger.warning(f"Failed to get subtree path from RPG for {subtree_name}: {e}")
            return None
    
    def get_next_batch(self, processed_files: set = None) -> Optional[TaskBatch]:
        """Get next unprocessed batch"""
        processed_files = processed_files or set()
        
        for batch in self.get_batches_as_list():
            if batch.file_path not in processed_files:
                return batch
        
        return None
    
    def get_batch_count(self) -> Dict[str, int]:
        """Get statistics about planned batches"""
        if not hasattr(self, 'planned_batches_dict'):
            return {"total_batches": 0, "total_files": 0, "total_subtrees": 0}
            
        total_batches = 0
        total_files = 0
        total_subtrees = len(self.planned_batches_dict)
        
        for subtree, files_dict in self.planned_batches_dict.items():
            total_files += len(files_dict)
            for file_batches in files_dict.values():
                total_batches += len(file_batches)
                
        return {
            "total_batches": total_batches,
            "total_files": total_files,
            "total_subtrees": total_subtrees
        }
