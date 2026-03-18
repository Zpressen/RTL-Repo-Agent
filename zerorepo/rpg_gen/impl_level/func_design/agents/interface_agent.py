from typing import Union, Dict, Optional, List, Any
from pydantic import BaseModel, Field, ValidationError
import logging
import json, json5
import uuid
import ast
import re
from pathlib import Path
from zerorepo.rpg_gen.base import (
    RPG, NodeType,
    NodeMetaData,
    Tool, ToolResult,
    ToolCall,
    ToolExecResult, ToolCallArguments,
    LLMClient, LLMConfig, Memory,
    AgentwithReview, ReviewEnv,
    RepoSkeleton, FileNode,
    ParsedFile
)
from zerorepo.rpg_gen.base.unit import render_codeunits_as_file
from zerorepo.utils.compress import get_skeleton  
from zerorepo.rpg_gen.impl_level.rtl_trace import (
    build_trace_context,
    format_trace_context,
    build_unit_implementation_context,
    format_implementation_context,
)
from ..prompts import (
    DESIGN_ITF,
    DESIGN_ITF_REVIEW,
    DESIGN_INTERFACE_TOOL
)

RTL_INTERFACE_UNIT_KINDS = {"rtl_module", "rtl_package", "testbench", "script", "build"}


def _is_rtl_mode(rtl_context: Optional[Dict[str, Any]]) -> bool:
    return bool(rtl_context and rtl_context.get("component_names"))


def _contains_python_only_constructs(code: str) -> bool:
    code = re.sub(r"//.*?$", "", code, flags=re.MULTILINE)
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.DOTALL)
    return bool(
        re.search(r"(?m)^\s*(def|class|import|from)\b", code)
        or re.search(r"\b(__init__|dataclass|Protocol)\b", code)
        or re.search(r"(?m)^\s*pass\s*$", code)
    )


def _get_rtl_file_spec(rtl_context: Optional[Dict[str, Any]], file_path: str) -> Dict[str, Any]:
    if not rtl_context:
        return {}
    file_specs_by_path = rtl_context.get("file_specs_by_path", {}) or {}
    if isinstance(file_specs_by_path, dict):
        spec = file_specs_by_path.get(file_path)
        if isinstance(spec, dict):
            return spec
    for spec in rtl_context.get("file_specs", []) or []:
        if isinstance(spec, dict) and spec.get("file_path") == file_path:
            return spec
    return {}


def _pick_canonical_port_name(
    preferred_name: str,
    top_ports: List[Dict[str, Any]],
    predicate,
) -> str:
    candidate_names = [
        str(port.get("name", "")).strip()
        for port in top_ports
        if isinstance(port, dict) and str(port.get("name", "")).strip()
    ]
    if preferred_name and preferred_name in candidate_names:
        return preferred_name
    for port in top_ports:
        if not isinstance(port, dict):
            continue
        name = str(port.get("name", "")).strip()
        if name and predicate(name, port):
            return name
    return preferred_name


def _get_top_module_facts(
    rtl_context: Optional[Dict[str, Any]],
    file_path: str,
) -> Dict[str, Any]:
    spec = _get_rtl_file_spec(rtl_context, file_path)
    if spec.get("file_kind") != "rtl_top_module":
        return {}

    top_module_name = str(rtl_context.get("top_module", "")).strip() if rtl_context else ""
    if not top_module_name:
        return {}

    top_ports = list(rtl_context.get("top_ports", []) or []) if rtl_context else []
    clock_reset = dict(rtl_context.get("clock_reset", {}) or {}) if rtl_context else {}
    clock_port = _pick_canonical_port_name(
        str(clock_reset.get("clock_port", "")).strip(),
        top_ports,
        lambda name, port: (
            str(port.get("domain", "")).strip().lower() == "clk"
            or bool(re.search(r"(?:^|_)(clk|clock)(?:$|_)", name.lower()))
        ),
    )
    reset_port = _pick_canonical_port_name(
        str(clock_reset.get("reset_port", "")).strip(),
        top_ports,
        lambda name, port: bool(re.search(r"(?:^|_)(rst|reset)(?:$|_)", name.lower())),
    )
    clock_reset["clock_port"] = clock_port
    clock_reset["reset_port"] = reset_port
    return {
        "top_module": top_module_name,
        "top_ports": top_ports,
        "top_params": list(rtl_context.get("top_params", []) or []),
        "params": list(rtl_context.get("params", []) or []),
        "default_params": list(rtl_context.get("default_params", []) or []),
        "clock_reset": clock_reset,
        "clock_port": clock_port,
        "reset_port": reset_port,
        "reset_polarity": str(clock_reset.get("reset_polarity", "")).strip(),
    }


def _get_rtl_trace_context(
    rtl_context: Optional[Dict[str, Any]],
    file_path: str,
    trace_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    if not rtl_context:
        return []

    if trace_ids is None:
        file_trace_context = rtl_context.get("file_trace_context_by_path", {}) or {}
        if isinstance(file_trace_context, dict):
            context = file_trace_context.get(file_path)
            if isinstance(context, list):
                return context
        trace_ids = list((rtl_context.get("file_trace_ids_by_path", {}) or {}).get(file_path, []) or [])

    return build_trace_context(list(trace_ids or []), rtl_context.get("trace_catalog", {}) or {})


def _get_rtl_secondary_context(rtl_context: Optional[Dict[str, Any]], file_path: str) -> Dict[str, Any]:
    if not rtl_context:
        return {}
    secondary_context = rtl_context.get("file_secondary_context_by_path", {}) or {}
    if isinstance(secondary_context, dict):
        payload = secondary_context.get(file_path, {})
        if isinstance(payload, dict):
            return payload
    return {}


def _get_rtl_file_implementation_context(rtl_context: Optional[Dict[str, Any]], file_path: str) -> Dict[str, List[Dict[str, Any]]]:
    if not rtl_context:
        return {}
    payload = (rtl_context.get("file_implementation_context_by_path", {}) or {}).get(file_path, {})
    return payload if isinstance(payload, dict) else {}


def _format_secondary_context(secondary_context: Optional[Dict[str, Any]]) -> str:
    secondary_context = secondary_context or {}
    if not secondary_context:
        return "- No supplementary file context."

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


def _get_target_unit_trace_ids(target_unit: Dict[str, Any]) -> List[str]:
    trace_ids: List[str] = []
    for item in target_unit.get("requirement_details", []) or []:
        if isinstance(item, dict):
            value = str(item.get("req_id", "")).strip()
            if value:
                trace_ids.append(value)
    for item in target_unit.get("test_details", []) or []:
        if isinstance(item, dict):
            value = str(item.get("test_id", "")).strip()
            if value:
                trace_ids.append(value)
    for item in target_unit.get("property_details", []) or []:
        if isinstance(item, dict):
            value = str(item.get("prop_id", "")).strip()
            if value:
                trace_ids.append(value)
    return trace_ids


def _get_target_unit_trace_context(
    rtl_context: Optional[Dict[str, Any]],
    file_path: str,
    target_unit: Dict[str, Any],
) -> List[Dict[str, Any]]:
    trace_ids = _get_target_unit_trace_ids(target_unit)
    if trace_ids:
        return _get_rtl_trace_context(rtl_context, file_path, trace_ids)
    return _get_rtl_trace_context(rtl_context, file_path)


def _format_top_module_facts(top_facts: Dict[str, Any]) -> str:
    if not top_facts:
        return ""

    port_lines: List[str] = []
    for port in top_facts.get("top_ports", []) or []:
        if not isinstance(port, dict):
            continue
        name = str(port.get("name", "")).strip()
        if not name:
            continue
        port_lines.append(
            f"- {name}: direction={port.get('direction', '')}, "
            f"width_expr={port.get('width_expr', '')}, domain={port.get('domain', '')}, "
            f"desc={port.get('desc', '')}"
        )

    param_items = list(top_facts.get("top_params", []) or []) or list(top_facts.get("default_params", []) or [])
    param_lines: List[str] = []
    for param in param_items:
        if not isinstance(param, dict):
            continue
        name = str(param.get("name", "")).strip()
        if not name:
            continue
        default = str(param.get("default", "")).strip()
        desc = str(param.get("desc", "")).strip()
        range_value = str(param.get("range", "")).strip()
        param_lines.append(
            f"- {name}: default={default or 'N/A'}, range={range_value or 'N/A'}, desc={desc or 'N/A'}"
        )

    clock_reset = top_facts.get("clock_reset", {}) or {}
    clock_reset_lines = []
    for key in ("clock_port", "clock_description", "reset_port", "reset_polarity", "reset_release", "reset_value_requirement"):
        value = str(clock_reset.get(key, "")).strip()
        if value:
            clock_reset_lines.append(f"- {key}: {value}")

    return (
        "=== Top Module Ports From Spec Facts ===\n"
        f"{chr(10).join(port_lines) if port_lines else '- None provided'}\n\n"
        "=== Top Module Params From Spec Facts ===\n"
        f"{chr(10).join(param_lines) if param_lines else '- None provided'}\n\n"
        "=== Clock/Reset From Spec Facts ===\n"
        f"{chr(10).join(clock_reset_lines) if clock_reset_lines else '- None provided'}"
    )


def _code_fence(code: str) -> str:
    if re.search(r"\b(module|package|typedef|localparam|logic|always_ff|always_comb)\b", code):
        return "systemverilog"
    if re.search(r"\b(make|iverilog|verilator|vvp|python)\b", code):
        return "text"
    return "python"


def _flatten_base_class_entries(base_classes: Any) -> List[Dict[str, Any]]:
    if isinstance(base_classes, list):
        return [item for item in base_classes if isinstance(item, dict)]
    if isinstance(base_classes, dict):
        flattened: List[Dict[str, Any]] = []
        for value in base_classes.values():
            if isinstance(value, list):
                flattened.extend(item for item in value if isinstance(item, dict))
            elif isinstance(value, dict):
                flattened.append(value)
        return flattened
    return []


def _get_unit_name(unit: Any) -> str:
    if isinstance(unit, dict):
        return str(unit.get("unit_name", "")).strip()
    return str(getattr(unit, "name", "")).strip()


def _get_unit_kind(unit: Any) -> str:
    if isinstance(unit, dict):
        return str(unit.get("unit_kind", "")).strip()
    return str(getattr(unit, "unit_type", "")).strip()


def _get_unit_text(unit: Any) -> str:
    if isinstance(unit, dict):
        return str(unit.get("spec") or unit.get("code") or "").strip()
    return ""


def _get_unit_code(unit: Any) -> str:
    if isinstance(unit, dict):
        return str(unit.get("code") or "").strip()
    return ""


def _rtl_file_language(file_path: str) -> str:
    path = str(file_path or "").strip()
    lower = path.lower()
    if Path(path).name == "Makefile":
        return "make"
    if lower.endswith((".sv", ".v", ".vh")):
        return "systemverilog"
    if lower.endswith(".py"):
        return "python"
    if lower.endswith((".sh", ".bash")):
        return "shell"
    return "text"


def _spec_has_invalid_python_constructs(spec: str, file_path: str) -> bool:
    if _rtl_file_language(file_path) == "python":
        return False
    return _contains_python_only_constructs(spec)


def _validate_rtl_skeleton(code: str, unit_kind: str, file_path: str) -> Optional[str]:
    stripped = str(code or "").strip()
    if not stripped:
        return "must include non-empty code skeleton text."

    language = _rtl_file_language(file_path)

    if language == "systemverilog":
        if unit_kind == "rtl_package":
            if not re.search(r"\bpackage\s+\w+", stripped) or "endpackage" not in stripped:
                return "must contain a SystemVerilog package skeleton with `package ... endpackage`."
        else:
            if not re.search(r"\bmodule\s+\w+", stripped) or "endmodule" not in stripped:
                return "must contain a SystemVerilog module skeleton with `module ... endmodule`."
        return None

    if language == "python":
        try:
            parsed = ast.parse(stripped)
        except SyntaxError as exc:
            return f"must be valid Python skeleton code: line {exc.lineno}, column {exc.offset}: {exc.msg}"

        if not any(
            isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                    ast.ClassDef,
                    ast.Import,
                    ast.ImportFrom,
                    ast.Assign,
                    ast.AnnAssign,
                ),
            )
            for node in parsed.body
        ):
            return "must look like a Python verification-model skeleton with imports, assignments, classes, or functions."
        return None

    if language == "shell":
        if _contains_python_only_constructs(stripped):
            return "must remain a shell-script skeleton, not Python code."
        if not (
            stripped.startswith("#!")
            or re.search(r"(?m)^\s*(set\s+-[a-zA-Z]+|if\b|for\b|while\b|echo\b|[A-Za-z_][A-Za-z0-9_]*=)", stripped)
        ):
            return "must look like a shell skeleton with a shebang, shell control flow, variable assignments, or commands."
        return None

    if language == "make":
        if _contains_python_only_constructs(stripped):
            return "must remain a Makefile skeleton, not Python code."
        if not re.search(r"(?m)^[A-Za-z0-9_.-]+:\s*(?:$|[^=].*)", stripped):
            return "must contain at least one Makefile target in `<target>:` form."
        return None

    return None


def _validate_top_module_contract(
    spec: str,
    code: str,
    file_path: str,
    rtl_context: Optional[Dict[str, Any]],
) -> Optional[str]:
    top_facts = _get_top_module_facts(rtl_context, file_path)
    if not top_facts:
        return None

    top_module_name = top_facts.get("top_module", "")
    if not re.search(rf"\bmodule\s+{re.escape(top_module_name)}\b", code):
        return f"must declare `module {top_module_name}` for the top-level skeleton."

    top_ports = [str(item.get("name", "")).strip() for item in top_facts.get("top_ports", []) if isinstance(item, dict)]
    missing_ports = [name for name in top_ports if name and not re.search(rf"\b{re.escape(name)}\b", code)]
    if missing_ports:
        return (
            "must include every top-level port from spec facts in the skeleton. "
            f"Missing ports: {missing_ports}"
        )

    spec_lower = str(spec or "").lower()
    missing_spec_terms: List[str] = []
    clock_port = top_facts.get("clock_port", "")
    reset_port = top_facts.get("reset_port", "")
    if clock_port and clock_port.lower() not in spec_lower:
        missing_spec_terms.append(clock_port)
    if reset_port and reset_port.lower() not in spec_lower:
        missing_spec_terms.append(reset_port)
    if any(name.startswith("s_axi_") for name in top_ports) and "axi" not in spec_lower:
        missing_spec_terms.append("AXI-Lite external interface")
    if any(name.startswith("uart_") for name in top_ports) and "uart" not in spec_lower:
        missing_spec_terms.append("UART pins")
    if "irq" in {name.lower() for name in top_ports} and not any(token in spec_lower for token in ("irq", "interrupt")):
        missing_spec_terms.append("irq/interrupt")

    if missing_spec_terms:
        return (
            "must describe the canonical top-level external interface in the contract. "
            f"Missing or under-described items: {missing_spec_terms}"
        )
    return None


def _code_fence_for_file(file_path: str, unit_kind: str, code: str) -> str:
    language = _rtl_file_language(file_path)
    if language == "systemverilog":
        return "systemverilog"
    if language == "python":
        return "python"
    if language == "shell":
        return "bash"
    if language == "make":
        return "makefile"
    if unit_kind in {"script", "build", "testbench"}:
        return "text"
    return _code_fence(code)


def _format_base_classes(base_classes: List) -> str:
    """Format base classes information"""
    if not base_classes:
        return "No base classes available."
    
    base_classes_lines = []
    for base_class in _flatten_base_class_entries(base_classes):
        file_path = base_class.get("file_path", "unknown")
        code = base_class.get("code", "")
        fence = _code_fence(code)
        base_classes_lines.append(
            f"### {file_path}\n"
            f"```{fence}\n{code}\n```\n"
        )
    
    return "\n".join(base_classes_lines)


# ========================
# 1. REVIEW MODELS
# ========================
class InterfaceReviewCategory(BaseModel):
    """Single review dimension block"""
    feedback: str = Field(description="Concrete, actionable guidance for this dimension")
    pass_: bool = Field(alias="pass", description="Whether this dimension passed review")


class InterfaceReviewBlock(BaseModel):
    """Full review section for interface design"""
    Feature_Alignment: InterfaceReviewCategory = Field(alias="Feature Alignment")
    Structural_Completeness: InterfaceReviewCategory = Field(alias="Structural Completeness")
    Docstring_Quality: InterfaceReviewCategory = Field(alias="Docstring Quality")
    Interface_Style_Granularity: InterfaceReviewCategory = Field(alias="Interface Style & Granularity")
    Scalability_Maintainability: InterfaceReviewCategory = Field(alias="Scalability & Maintainability")
    Data_Flow_Consistency: InterfaceReviewCategory = Field(alias="Data Flow Consistency")
    
    class Config:
        allow_population_by_field_name = True


class InterfaceReviewOutput(BaseModel):
    """Final JSON output for the interface review process"""
    review: InterfaceReviewBlock
    final_pass: bool = Field(description="True only if all passes or remaining issues are minor")


# ========================
# 2. AGENT TOOL
# ========================
class InterfaceDefinition(BaseModel):
    features: List[str] = Field(default_factory=list, description="Feature paths or trace IDs handled by this interface")
    code: str = Field(default="", description="Source skeleton text for the interface")
    file_path: Optional[str] = Field(default=None, description="Target file path for RTL mode")
    unit_name: Optional[str] = Field(default=None, description="Target unit name for RTL mode")
    unit_kind: Optional[str] = Field(default=None, description="Target unit kind for RTL mode")
    spec: Optional[str] = Field(default=None, description="RTL contract or stub text for RTL mode")

class DesignInterfacesToolParamModel(BaseModel):
    interfaces: List[InterfaceDefinition] = Field(
        ...,
        description="List of interface definitions, each covering specific feature paths",
    )

class DesignInterfacesTool(Tool):
    name = "design_itfs_for_feature"
    description = DESIGN_INTERFACE_TOOL
    ParamModel = DesignInterfacesToolParamModel

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
        """Parse raw JSON input for data flow"""
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
                    logging.warning(f"Tool name '{tool_name}' does not match expected '{cls.name}'")
                    continue
                
                params = raw_tool.get("parameters", raw_tool)

                parsed = cls.ParamModel(**params).model_dump()
                valid_tools.append(parsed)
                
            except ValidationError as e:
                logging.error(f"[custom_parse] Parameter validation failed: {e.errors()}")
                continue
            except Exception as e:
                logging.error(f"[custom_parse] Unexpected error: {e}")
                continue
        
        return valid_tools
    
    @classmethod
    async def execute(cls, arguments: Dict, env: Optional[Any] = None) -> ToolExecResult:
        try:
            interfaces = arguments.get("interfaces", [])
            rtl_context = getattr(env, "rtl_context", None)
            is_rtl = _is_rtl_mode(rtl_context)
            
            # Access target features from environment if available
            tgt_features = getattr(env, "tgt_features", None)
            covered_features = set(getattr(env, "covered_features", set()))
            tgt_units = getattr(env, "tgt_units", {}) if is_rtl else {}
            covered_units = set(getattr(env, "covered_units", set())) if is_rtl else set()
            
            # Debug logging
            if hasattr(env, 'logger'):
                env.logger.debug(f"Tool execute: tgt_features={len(tgt_features) if tgt_features else 0}, covered_features={len(covered_features)}")
            
            if not interfaces:
                return ToolExecResult(
                    output=None,
                    error="Empty interfaces provided",
                    error_code=1,
                    state={}
                )

            feedbacks: List[str] = []
            parsed_units = []
            all_features: set = set()
            valid_interfaces: List[Dict] = []
            unit_features_map: Dict[str, List[str]] = {}  # unit_id -> features mapping
            unit_trace_context_map: Dict[str, List[Dict[str, Any]]] = {}
            unit_secondary_context_map: Dict[str, Dict[str, Any]] = {}
            unit_implementation_context_map: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
            all_units: set = set()

            if is_rtl:
                for interface in interfaces:
                    file_path = str(interface.get("file_path") or getattr(env, "tgt_file_path", "")).strip()
                    unit_name = str(interface.get("unit_name") or "").strip()
                    unit_kind = str(interface.get("unit_kind") or "").strip()
                    spec = str(interface.get("spec") or "").strip()
                    code = str(interface.get("code") or "").strip()
                    features = interface.get("features", [])
                    interface_errors: List[str] = []

                    if not file_path:
                        interface_errors.append("RTL interface must include file_path.")
                    elif file_path != getattr(env, "tgt_file_path", ""):
                        interface_errors.append(
                            f"RTL interface target file '{file_path}' does not match current file '{getattr(env, 'tgt_file_path', '')}'."
                        )
                    elif getattr(env, "repo_skeleton", None) and not env.repo_skeleton.path_exists(file_path):
                        interface_errors.append(f"RTL interface target file '{file_path}' does not exist in the repository skeleton.")

                    if unit_name not in tgt_units:
                        interface_errors.append(
                            f"RTL unit '{unit_name}' is not a valid target unit for this file. Valid units: {sorted(tgt_units.keys())}"
                        )
                    else:
                        target_unit = tgt_units[unit_name]
                        expected_kind = target_unit.get("unit_kind", "")
                        if unit_kind != expected_kind:
                            interface_errors.append(
                                f"RTL unit '{unit_name}' must use unit_kind '{expected_kind}', got '{unit_kind}'."
                            )
                    target_unit = tgt_units.get(unit_name, {})

                    if unit_kind not in RTL_INTERFACE_UNIT_KINDS:
                        interface_errors.append(
                            f"RTL unit_kind '{unit_kind}' is invalid. Allowed kinds: {sorted(RTL_INTERFACE_UNIT_KINDS)}"
                        )

                    if not spec:
                        interface_errors.append(f"RTL unit '{unit_name}' must include non-empty spec text.")
                    elif _spec_has_invalid_python_constructs(spec, file_path):
                        interface_errors.append(
                            f"RTL unit '{unit_name}' contains Python-only constructs and must remain a pure RTL/build contract."
                        )

                    if not code:
                        interface_errors.append(f"RTL unit '{unit_name}' must include non-empty code skeleton text.")
                    else:
                        code_error = _validate_rtl_skeleton(code, unit_kind, file_path)
                        if code_error:
                            interface_errors.append(
                                f"RTL unit '{unit_name}' {code_error}"
                            )
                        else:
                            top_module_error = _validate_top_module_contract(spec, code, file_path, rtl_context)
                            if top_module_error:
                                interface_errors.append(
                                    f"RTL unit '{unit_name}' {top_module_error}"
                                )

                    if not isinstance(features, list):
                        interface_errors.append(f"RTL unit '{unit_name}' features must be a list.")
                        features = []
                    else:
                        features = [str(item).strip() for item in features if str(item).strip()]
                    target_features = [
                        str(item).strip()
                        for item in (target_unit.get("features", []) or [])
                        if str(item).strip()
                    ]
                    if not features and unit_name in tgt_units:
                        features = list(target_features)
                    elif target_features and not set(features).issubset(set(target_features)):
                        interface_errors.append(
                            f"RTL unit '{unit_name}' features must remain canonical trace IDs for this unit. "
                            f"Allowed features: {target_features}, got: {features}"
                        )
                    elif not target_features and features:
                        interface_errors.append(
                            f"RTL unit '{unit_name}' does not have canonical trace IDs. "
                            f"Do not invent features for this unit; keep features empty, got: {features}"
                        )

                    if unit_name in all_units:
                        interface_errors.append(f"RTL unit '{unit_name}' is already covered by another interface in this tool call.")

                    if interface_errors:
                        feedbacks.extend(interface_errors)
                        continue

                    normalized_interface = {
                        "file_path": file_path,
                        "unit_name": unit_name,
                        "unit_kind": unit_kind,
                        "spec": spec,
                        "code": code,
                        "features": list(target_features),
                        "trace_context": target_unit.get("trace_context", []),
                        "secondary_context": target_unit.get("secondary_context", {}),
                        "implementation_context": target_unit.get("implementation_context", {}),
                    }
                    valid_interfaces.append(normalized_interface)
                    parsed_units.append(normalized_interface)
                    unit_features_map[unit_name] = list(target_features)
                    unit_trace_context_map[unit_name] = list(target_unit.get("trace_context", []) or [])
                    unit_secondary_context_map[unit_name] = dict(target_unit.get("secondary_context", {}) or {})
                    unit_implementation_context_map[unit_name] = dict(target_unit.get("implementation_context", {}) or {})
                    all_units.add(unit_name)
                    all_features.update(target_features)

                feedback_str = "\n".join(str(item) for item in feedbacks if item).strip()
                if not feedback_str:
                    total_units = len(tgt_units)
                    newly_covered_units = covered_units.union(all_units)
                    remaining_units = sorted(set(tgt_units.keys()) - newly_covered_units)
                    covered_count = len(newly_covered_units)
                    if remaining_units:
                        feedback_str = (
                            f"SUCCESS: {len(valid_interfaces)} RTL skeleton/contract pair(s) successfully registered.\n"
                            f"Progress: {covered_count}/{total_units} target units covered.\n"
                            f"Remaining units: {remaining_units}\n"
                            "Continue designing skeletons and contracts for the remaining RTL units."
                        )
                    else:
                        feedback_str = (
                            f"SUCCESS: All {total_units} RTL target units have been covered.\n"
                            "RTL skeleton/interface design is complete."
                        )
                else:
                    total_units = len(tgt_units)
                    remaining_units = sorted(set(tgt_units.keys()) - covered_units)
                    feedback_str += (
                        f"\n\nRE-PLANNING NEEDED:\n"
                        f"Current status: {len(covered_units)}/{total_units} target units covered.\n"
                        f"Remaining target units: {remaining_units}\n"
                        "Please fix the issues above and re-submit a complete RTL skeleton and contract design."
                    )

                if not valid_interfaces:
                    return ToolExecResult(
                        output=None,
                        error=feedback_str.strip() + "\n\nAll provided RTL interfaces had issues - none were accepted.",
                        error_code=1,
                        state={}
                    )

                return ToolExecResult(
                    output=feedbacks,
                    error_code=0,
                    state={
                        "interfaces": valid_interfaces,
                        "parsed_units": parsed_units,
                        "covered_units": list(all_units),
                        "covered_features": list(all_features),
                        "unit_features_map": unit_features_map,
                        "unit_trace_context_map": unit_trace_context_map,
                        "unit_secondary_context_map": unit_secondary_context_map,
                        "unit_implementation_context_map": unit_implementation_context_map,
                    }
                )

            for interface in interfaces:
                features = interface.get("features", [])
                code = interface.get("code", "")
                interface_errors: List[str] = []

                # ====== 校验 features ======
                if not features or not isinstance(features, list):
                    interface_errors.append(
                        f"Interface must have valid features list, got: {features}"
                    )
                else:
                    feature_set = set(features)

                    # Check if features are in target features
                    if tgt_features and not feature_set.issubset(tgt_features):
                        invalid_features = feature_set - set(tgt_features)
                        interface_errors.append(
                            f"Features {list(invalid_features)} are not in target features {list(tgt_features)}"
                        )

                    # Check for feature overlap with already accepted features
                    overlap = all_features & feature_set
                    if overlap:
                        interface_errors.append(
                            f"Features {list(overlap)} are already covered by another interface"
                        )
                if interface_errors:
                    feedbacks.extend(interface_errors)
                    continue

                feature_set = set(features)

                try:
                    ast.parse(code)
                except SyntaxError as e:
                    interface_errors.append(
                        f"Syntax error in interface for features {features}: "
                        f"line {e.lineno}, column {e.offset}: {e.msg}"
                    )
                    feedbacks.extend(interface_errors)
                    continue

                parsed_file = ParsedFile(code=code, file_path="temp_interface.py")
                # Only include class and function, exclude method for units_to_code
                interface_units = [
                    unit for unit in parsed_file.units
                    if unit.unit_type in ["function", "class"]
                ]

                if not interface_units:
                    interface_errors.append(
                        f"No valid functions/classes found for features {features}"
                    )
                    feedbacks.extend(interface_errors)
                    continue

                for unit in interface_units:
                    if not unit.docstring and unit.unit_type in ["function", "class"]:
                        interface_errors.append(
                            f"Missing docstring for {unit.unit_type} '{unit.name}' "
                            f"in features {features}"
                        )

                if interface_errors:
                    feedbacks.extend(interface_errors)
                    continue

                for unit in interface_units:
                    unit_key = f"{unit.unit_type}:{unit.name}:{unit.parent or ''}"
                    unit_features_map[unit_key] = features


                parsed_units.extend(interface_units)
                valid_interfaces.append(interface)
                all_features.update(feature_set)


            feedback_str = ""
            for feedback in feedbacks:
                if isinstance(feedback, str):
                    feedback_str += f"{feedback}\n"
                elif isinstance(feedback, list):
                    feedback_str += "\n".join(feedback) + "\n"
                else:
                    feedback_str += f"{str(feedback)}\n"
            
            # Calculate progress and provide specific guidance with complete context
            if not feedback_str.strip():
                total_features = len(tgt_features) if tgt_features else 0
                # Current batch features + previously covered features
                newly_covered = covered_features.union(set(all_features))
                remaining_features = (set(tgt_features) - newly_covered) if tgt_features else set()
                covered_count = len(newly_covered)
                
                if remaining_features:
                    feedback_str = (
                        f"SUCCESS: {len(valid_interfaces)} interface(s) successfully registered.\n"
                        f"Progress: {covered_count}/{total_features} features covered.\n"
                    )
                    feedback_str += (
                        f"\nPLANNING GUIDANCE:\n"
                        f"  - Continue to design interfaces in your next call\n"
                        f"  - Group logically related features (shared state/config/lifecycle)\n"
                        f"  - Each interface should have ONE clear responsibility\n"
                        f"  - Avoid cramming all features into one large class/function\n"
                        f"  - follow the instruction and output format in the system prompt\n"
                    )
                else:
                    feedback_str = (
                        f"SUCCESS: All {total_features} features have been covered!\n"
                        f"Interface design is complete. You can now proceed."
                    )
            else:
                # There were errors - provide specific guidance for re-planning with complete context
                feedback_str = feedback_str.strip()
                total_features = len(tgt_features) if tgt_features else 0
                # Only subtract actually covered features, not the failed batch
                remaining_features = (set(tgt_features) - covered_features) if tgt_features else set()
                
                feedback_str += (
                    f"\n\nRE-PLANNING NEEDED:\n"
                    f"Current status: {len(covered_features)}/{total_features} features covered.\n"
                    f"Please fix the issues above and re-design interfaces.\n\n"
                    f"PLANNING GUIDANCE:\n"
                    f"  - Review the error messages and fix each issue\n"
                    f"  - Plan interfaces for the remaining features\n"
                    f"  - Ensure each interface has ONE clear responsibility\n"
                    f"  - Double-check feature paths match the target list exactly\n"
                    f"  - follow the instruction and output format in the system prompt\n"
                )
            
            if not valid_interfaces:
                feedback_str += f"\n\nAll provided interfaces had issues - none were accepted."
                # Add format requirement if not already present
                feedback_str = feedback_str.strip()
                return ToolExecResult(
                    output=None,
                    error=feedback_str.strip(),
                    error_code=1,
                    state={}    
                )
                       
            return ToolExecResult(
                output=feedbacks,
                error_code=0,
                state={
                    "interfaces": valid_interfaces,
                    "parsed_units": parsed_units,
                    "covered_features": list(all_features),
                    "unit_features_map": unit_features_map
                }
            )

        except Exception as e:
            return ToolExecResult(
                output=None,
                error=str(e),
                error_code=1,
                state={}
            )


# ========================
# 3. ENVIRONMENT
# ========================

class InterfaceEnv(ReviewEnv):
    """Environment for interface design phase"""
    
    def __init__(
        self,
        review_llm: LLMClient,
        review_format: BaseModel,
        review_memory: Memory,
        review_times: int = 1,
        register_tools: List = [],
        repo_skeleton: RepoSkeleton = None,
        repo_rpg: RPG = None,
        rtl_context: Optional[Dict[str, Any]] = None,
        tgt_file_path: str = "",
        tgt_subgraph_name: str = "", 
        logger: logging.Logger = None
    ):
        super().__init__(
            review_llm, review_format,
            review_memory, review_times,
            register_tools,
            logger
        )
        
        self.repo_rpg = repo_rpg
        self.repo_skeleton = repo_skeleton
        self.rtl_context = rtl_context
        self.tgt_file_path = tgt_file_path
        self.tgt_subgraph_name = tgt_subgraph_name
        
        self.imports_units = []
        self.designed_interfaces = {}
        self.covered_features = set()
        self.covered_units = set()
        self.is_completed = False
        self.logger = logger or logging.getLogger(__name__)
        
        self.tgt_features = []
        self.tgt_units = {}
        self.tgt_subtree_implemented = []
        self.all_implemented_subtrees = {}

    def _is_rtl_mode(self) -> bool:
        return _is_rtl_mode(self.rtl_context)

    def _format_top_module_facts(self) -> str:
        return _format_top_module_facts(_get_top_module_facts(self.rtl_context, self.tgt_file_path))

    def _format_tgt_units(self, only_remaining: bool = False) -> str:
        if not self.tgt_units:
            return "No target units available."
        lines = []
        remaining = set(self.tgt_units) - set(self.covered_units)
        for unit_name, unit_info in self.tgt_units.items():
            if only_remaining and unit_name not in remaining:
                continue
            trace_ids = list(unit_info.get("features", []) or [])
            trace_context = unit_info.get("trace_context", []) or []
            lines.append(
                f"- {unit_name} ({unit_info.get('unit_kind', 'unknown')})"
                f": responsibility={unit_info.get('responsibility', '')}, "
                f"depends_on_files={unit_info.get('depends_on_files', [])}, "
                f"trace_ids={trace_ids}"
            )
            if trace_context:
                lines.append(f"  trace_context:\n{format_trace_context(trace_context)}")
            implementation_context = unit_info.get("implementation_context", {})
            if implementation_context:
                lines.append(
                    "  implementation_context:\n"
                    f"{format_implementation_context(implementation_context)}"
                )
        return "\n".join(lines) if lines else "All target RTL units are covered."

    def _format_designed_contracts(self) -> str:
        if not self.designed_interfaces:
            return "No RTL contracts designed yet."
        blocks = []
        for interface_key, info in self.designed_interfaces.items():
            unit = info.get("unit")
            spec = _get_unit_text(unit)
            kind = _get_unit_kind(unit)
            file_path = str(unit.get("file_path", self.tgt_file_path)) if isinstance(unit, dict) else self.tgt_file_path
            fence = _code_fence_for_file(file_path, kind, spec)
            trace_context = info.get("trace_context", [])
            implementation_context = info.get("implementation_context", {})
            trace_block = ""
            if trace_context:
                trace_block = f"\nTrace Context:\n{format_trace_context(trace_context)}\n"
            implementation_block = ""
            if implementation_context:
                implementation_block = (
                    "\nImplementation Context:\n"
                    f"{format_implementation_context(implementation_context)}\n"
                )
            blocks.append(f"### {interface_key}{trace_block}{implementation_block}```{fence}\n{spec}\n```")
        return "\n\n".join(blocks)

    def _format_designed_skeletons(self) -> str:
        if not self.designed_interfaces:
            return "No RTL skeletons designed yet."
        blocks = []
        for interface_key, info in self.designed_interfaces.items():
            unit = info.get("unit")
            kind = _get_unit_kind(unit)
            code = _get_unit_code(unit)
            file_path = str(unit.get("file_path", self.tgt_file_path)) if isinstance(unit, dict) else self.tgt_file_path
            fence = _code_fence_for_file(file_path, kind, code)
            blocks.append(f"### {interface_key}\n```{fence}\n{code}\n```")
        return "\n\n".join(blocks)
    
    def post_feedback(self) -> str:
        """Provide complete context information as post-feedback after tool execution"""
        if self._is_rtl_mode():
            if not self.tgt_units:
                return ""
            remaining_units = set(self.tgt_units) - set(self.covered_units)
            if not remaining_units:
                return ""
            context_info = self.build_complete_context_info()
            self.logger.info(f"[Post Feedback]: COMPLETE RTL CONTEXT FOR NEXT ITERATION:\n{context_info}")
            return f"\n\nCOMPLETE RTL CONTEXT FOR NEXT ITERATION:\n{context_info}"

        # Check if there are remaining features or if we need context
        if not self.tgt_features:
            self.logger.debug("post_feedback: No target features, returning empty")
            return ""
            
        covered_features = getattr(self, 'covered_features', set())
        remaining_features = set(self.tgt_features) - covered_features
        
        self.logger.info(f"post_feedback: {len(covered_features)}/{len(self.tgt_features)} features covered, {len(remaining_features)} remaining")
        
        # Only provide context if there are remaining features
        if not remaining_features:
            self.logger.info("post_feedback: All features covered, no context needed")
            return ""
        
        self.logger.debug(f"post_feedback: Building complete context for {len(remaining_features)} remaining features")
        context_info = self.build_complete_context_info()
        self.logger.info(f"[Post Feedback]: COMPLETE CONTEXT FOR NEXT ITERATION:\n{context_info}")
        
        return f"\n\nCOMPLETE CONTEXT FOR NEXT ITERATION:\n{context_info}"
    
    def build_complete_context_info(self) -> str:
        """Build complete context information including current implementation status"""
        if not self.repo_rpg:
            return ""
        if self._is_rtl_mode():
            repo_info = self.repo_rpg.repo_info or "Repository information not available"
            data_flow_str = json.dumps(self.repo_rpg.data_flow, indent=2) if self.repo_rpg.data_flow else "No data flow available"
            upstream_context = self._extract_upstream_context(
                self.repo_rpg.data_flow or [],
                self.tgt_subgraph_name,
                self.all_implemented_subtrees
            )
            implemented_summary = self._format_implemented_summary(
                self.tgt_subtree_implemented,
                self.tgt_file_path
            )
            base_classes_str = _format_base_classes(self.repo_rpg.base_classes)
            current_contracts = self._format_designed_contracts()
            current_skeletons = self._format_designed_skeletons()
            top_module_facts = self._format_top_module_facts()
            secondary_context = _format_secondary_context(
                _get_rtl_secondary_context(self.rtl_context, self.tgt_file_path)
            )
            return (
                f"{repo_info}\n\n"
                "=== RTL Data Flow Graph ===\n"
                f"{data_flow_str}\n\n"
                "=== Upstream Context ===\n"
                f"{upstream_context}\n\n"
                "=== Implemented Summary ===\n"
                f"{implemented_summary}\n\n"
                "=== Shared Definitions ===\n"
                f"{base_classes_str}\n\n"
                "=== Supplementary File Context ===\n"
                f"{secondary_context}\n\n"
                f"{top_module_facts + chr(10) + chr(10) if top_module_facts else ''}"
                "=== Target RTL Units ===\n"
                f"{self._format_tgt_units()}\n\n"
                "=== Current RTL Skeletons ===\n"
                f"{current_skeletons}\n\n"
                "=== Current RTL Contracts ===\n"
                f"{current_contracts}\n\n"
                "=== Remaining RTL Units ===\n"
                f"{self._format_tgt_units(only_remaining=True)}"
            )
            
        # Calculate remaining features
        covered_features = getattr(self, 'covered_features', set())
        remaining_features = set(self.tgt_features) - covered_features
        
        # Current file code
        current_code = ""
        if hasattr(self, 'designed_interfaces') and self.designed_interfaces:
            imports_units = getattr(self, 'imports_units', [])
            interface_units = [info['unit'] for info in self.designed_interfaces.values()]
            current_code = render_codeunits_as_file(units=imports_units + interface_units)
        
        # Prepare all context information
        repo_info = self.repo_rpg.repo_info or "Repository information not available"
        data_flow_str = json.dumps(self.repo_rpg.data_flow, indent=2) if self.repo_rpg.data_flow else "No data flow available"
        
        # Format upstream context (reuse existing logic from agent)
        from zerorepo.utils.compress import get_skeleton
        upstream_context = self._extract_upstream_context(
            self.repo_rpg.data_flow or [], 
            self.tgt_subgraph_name, 
            self.all_implemented_subtrees
        )
        
        # Format implemented summary
        implemented_summary = self._format_implemented_summary(
            self.tgt_subtree_implemented, 
            self.tgt_file_path
        )
        
        # Format base classes
        base_classes_str = _format_base_classes(self.repo_rpg.base_classes)
        
        # Format features lists
        all_features_str = '\n'.join([f"- {f}" for f in self.tgt_features])
        remaining_features_str = '\n'.join([f"- {f}" for f in remaining_features]) if remaining_features else "All features covered!"
        
        # Current code section
        current_code_section = ""
        if current_code.strip():
            current_code_section = (
                "=== Current File Implementation Status ===\n"
                f"Current implementation of `{self.tgt_file_path}` after previous iterations:\n"
                f"```python\n{current_code}\n```\n\n"
            )
        
        # Build comprehensive context
        context_info = (
            f"{repo_info}\n\n"
            "=== Data Flow Graph ===\n"
            f"{data_flow_str}\n\n"
            "=== Upstream Context ===\n"
            f"{upstream_context}\n\n"
            "=== Implemented Summary ===\n"
            f"{implemented_summary}\n\n"
            "=== Available Base Classes ===\n"
            f"{base_classes_str}\n\n"
            f"{current_code_section}"
            "=== Remaining Features To Design ===\n"
            f"{remaining_features_str}\n\n"
            "Continue designing interfaces for the REMAINING features listed above. "
            "Use the complete context information provided to make informed design decisions."
        )
        
        return context_info
    
    def _extract_upstream_context(self, data_flow_graph, tgt_subgraph, all_implemented_subtrees, top_n=5):
        """Extract upstream interface context"""
        upstream_nodes = set()
        
        # Find upstream dependencies
        for edge in data_flow_graph:
            from_node = edge.get("source")
            to_node = edge.get("target")
            if self._is_rtl_mode():
                if to_node == self.tgt_file_path:
                    upstream_nodes.add(from_node)
            elif to_node and to_node.startswith(tgt_subgraph):
                upstream_nodes.add(from_node)
        
        if not upstream_nodes:
            return "No upstream modules connected to this subtree."
        
        # Format upstream context
        upstream_summary = []
        for node in sorted(upstream_nodes):
            impl_files = all_implemented_subtrees.get(node, [])
            if not isinstance(impl_files, list):
                continue
            impl_files = impl_files[:top_n]
            if not impl_files:
                continue
            for file_node in impl_files:
                path = file_node.path
                features = ', '.join(file_node.feature_paths)
                code_skeleton = get_skeleton(file_node.code, keep_indent=True)
                if self._is_rtl_mode():
                    upstream_summary.append(
                        f"### From file: `{node}`\n"
                        f"Implemented file: `{path}`\n"
                        f"Code Skeleton:\n```text\n{code_skeleton}\n```\n"
                    )
                else:
                    upstream_summary.append(
                        f"### From module: `{node}`\nFile: `{path}`\nFeatures: {features}\nCode:\n```python\n{code_skeleton}\n```\n"
                    )
            upstream_summary.append('...some files have been omitted due to context length constraints...')

        
        return "\n".join(upstream_summary) if upstream_summary else "No implemented upstream interfaces found."
    
    def _format_implemented_summary(self, tgt_subtree_implemented, current_file, latest_k=5):
        """Format summary of already implemented files in subtree"""
        if not tgt_subtree_implemented:
            return "No files implemented yet in this subtree."
        
        summary_lines = []
        for impl_file in tgt_subtree_implemented[-latest_k:]:
            if impl_file.path != current_file:
                skeleton = get_skeleton(raw_code=impl_file.code, keep_indent=True)
                if self._is_rtl_mode():
                    block = (
                        f"#### Related Implemented File: `{impl_file.path}`\n"
                        f"**Code Skeleton:**\n"
                        f"```text\n{skeleton}\n```\n"
                    )
                else:
                    features_str = ', '.join(impl_file.feature_paths[:2])
                    if len(impl_file.feature_paths) > 2:
                        features_str += f", ...{len(impl_file.feature_paths) - 2} more"
                    block = (
                        f"#### Related Implemented File: `{impl_file.path}`\n"
                        f"**Associated Features:** {features_str}\n"
                        f"**Code Skeleton:**\n"
                        f"```python\n{skeleton}\n```\n"
                    )
                summary_lines.append(block)
        
        return "\n".join(summary_lines)
    
    def load_review_message(self, tool_calls: List[ToolCall]):
        """Load review message for interface design"""
        if not self.repo_rpg or not self.repo_skeleton:
            return "Missing repository context for review"
        if self._is_rtl_mode():
            repo_info = self.repo_rpg.repo_info
            data_flow = self.repo_rpg.data_flow
            base_classes = _format_base_classes(self.repo_rpg.base_classes)
            data_flow_str = json.dumps(data_flow, indent=2) if data_flow else "No data flow available"
            top_module_facts = self._format_top_module_facts()

            interfaces_info = []
            for tool_call in tool_calls:
                if hasattr(tool_call, 'arguments') and 'interfaces' in tool_call.arguments:
                    for interface in tool_call.arguments['interfaces']:
                        fence = _code_fence_for_file(
                            interface.get("file_path", self.tgt_file_path),
                            interface.get("unit_kind", ""),
                            interface.get("code", "") or interface.get("spec", ""),
                        )
                        interfaces_info.append(
                            f"Unit: {interface.get('unit_name')} ({interface.get('unit_kind')})\n"
                            f"File: {interface.get('file_path')}\n"
                            f"Trace IDs: {interface.get('features', [])}\n"
                            f"Trace Context:\n{format_trace_context(interface.get('trace_context', []))}\n"
                            f"Implementation Context:\n{format_implementation_context(interface.get('implementation_context', {}))}\n"
                            f"Supplementary Context:\n{_format_secondary_context(interface.get('secondary_context', {}))}\n"
                            f"Skeleton:\n```{fence}\n{interface.get('code', '')}\n```\n"
                            f"Contract:\n{interface.get('spec') or ''}\n"
                        )

            interfaces_str = "\n---\n".join(interfaces_info) if interfaces_info else "No RTL skeletons/contracts found"
            return (
                "Please review the following RTL skeleton and contract design:\n\n"
                f"Repository Info: {repo_info}\n\n"
                f"RTL Files:\n{self.repo_skeleton.to_tree_string()}\n\n"
                f"Data Flow:\n{data_flow_str}\n\n"
                f"Shared Definitions:\n{base_classes}\n\n"
                f"{top_module_facts + chr(10) + chr(10) if top_module_facts else ''}"
                f"Target RTL Units:\n{self._format_tgt_units()}\n\n"
                f"Designed RTL Skeletons and Contracts:\n{interfaces_str}\n\n"
                "Evaluate the skeletons and contracts according to the review criteria and provide detailed feedback.\n"
                "Respond with a valid JSON object following the required output format."
            )
        
        repo_info = self.repo_rpg.repo_info
        # skeleton_str = self.repo_skeleton.to_tree_string()
        data_flow = self.repo_rpg.data_flow
        base_classes = _format_base_classes(self.repo_rpg.base_classes)
        data_flow_str = json.dumps(data_flow, indent=2) if data_flow else "No data flow available"
        
        # Extract interface information from tool calls
        interfaces_info = []
        for tool_call in tool_calls:
            if hasattr(tool_call, 'arguments') and 'interfaces' in tool_call.arguments:
                interfaces = tool_call.arguments['interfaces']
                for interface in interfaces:
                    features = interface.get('features', [])
                    code = interface.get('code', '')
                    interfaces_info.append(f"Features: {features}\nCode:\n{code}\n")
        
        interfaces_str = "\n---\n".join(interfaces_info) if interfaces_info else "No interfaces found"
        
        review_input = (
            "Please review the following interface design:\n\n"
            f"Repository Info: {repo_info}\n\n"
            # f"Repository Skeleton:\n{skeleton_str}\n\n"
            f"Data Flow:\n{data_flow_str}\n\n"
            f"Base Classes:\n{base_classes}"
            f"Designed Interfaces:\n{interfaces_str}\n\n"
            "Evaluate the interfaces according to the review criteria and provide detailed feedback.\n"
            "Respond with a valid JSON object following the required output format."
        )
        
        return review_input
    
    def should_terminate(self, tool_calls, tool_results):
        """Check if interface design is complete"""
        if self._is_rtl_mode():
            if not self.tgt_units:
                return False
            tgt_units_set = set(self.tgt_units.keys())
            covered_units_set = set(self.covered_units)
            self.is_completed = tgt_units_set.issubset(covered_units_set)
            if self.is_completed:
                self.logger.info(
                    f"All {len(tgt_units_set)} target RTL units have been covered. Interface design complete."
                )
            return self.is_completed

        # Don't update state here - that's handled in update_env
        # Just check if all target features are covered
        if not self.tgt_features:
            return False
            
        tgt_features_set = set(self.tgt_features)
        covered_features_set = set(self.covered_features)
        
        # Debug logging
        self.logger.debug(f"should_terminate: tgt_features={len(tgt_features_set)}, covered_features={len(covered_features_set)}")
        self.logger.debug(f"Missing features: {tgt_features_set - covered_features_set}")
        
        # Check if all target features are covered
        self.is_completed = tgt_features_set.issubset(covered_features_set)
        
        if self.is_completed:
            self.logger.info(f"All {len(self.tgt_features)} target features have been covered. Interface design complete.")
        else:
            remaining = len(tgt_features_set - covered_features_set)
            self.logger.debug(f"Still need to cover {remaining} features out of {len(self.tgt_features)} total.")
        
        return self.is_completed
    
    def update_env(self, tool_call, result: ToolResult):
        """Update environment state after tool execution"""
        if tool_call.name == "design_itfs_for_feature" and result.success:
            try:
                if self._is_rtl_mode():
                    valid_interfaces = result.state.get("interfaces", [])
                    parsed_units = result.state.get("parsed_units", [])
                    unit_features_map = result.state.get("unit_features_map", {})
                    unit_trace_context_map = result.state.get("unit_trace_context_map", {})
                    unit_secondary_context_map = result.state.get("unit_secondary_context_map", {})
                    unit_implementation_context_map = result.state.get("unit_implementation_context_map", {})
                    covered_units = result.state.get("covered_units", [])

                    self.covered_units.update(covered_units or [])
                    for unit_info in parsed_units:
                        unit_name = unit_info.get("unit_name", "")
                        if not unit_name:
                            continue
                        self.designed_interfaces[unit_name] = {
                            "unit": unit_info,
                            "features": unit_features_map.get(unit_name, unit_info.get("features", [])),
                            "trace_context": unit_trace_context_map.get(unit_name, unit_info.get("trace_context", [])),
                            "secondary_context": unit_secondary_context_map.get(unit_name, unit_info.get("secondary_context", {})),
                            "implementation_context": unit_implementation_context_map.get(unit_name, unit_info.get("implementation_context", {})),
                        }

                    self.logger.info(
                        f"Updated RTL interfaces: {len(self.designed_interfaces)} total, "
                        f"covered units: {len(self.covered_units)}/{len(self.tgt_units)}"
                    )
                    return

                valid_interfaces = result.state.get("interfaces", [])
                parsed_units = result.state.get("parsed_units", [])
                unit_features_map = result.state.get("unit_features_map", {})
                covered_features = result.state.get("covered_features", [])
                
                # Extract imports from valid interfaces for import handling
                for v_itf in valid_interfaces:
                    code = v_itf.get("code", "")
                    temp_units = ParsedFile(code=code, file_path="temp_interface.py").units
                    self.imports_units.extend([unit for unit in temp_units if unit.unit_type in ["import", "assignment"]])
                
                # Update covered features (ensure it's a set)
                if isinstance(covered_features, list):
                    self.covered_features.update(covered_features)
                    self.logger.debug(f"Updated covered_features: added {len(covered_features)} features, total now {len(self.covered_features)}")
                else:
                    self.covered_features.update(covered_features or [])
                    self.logger.debug(f"Updated covered_features from set/other: total now {len(self.covered_features)}")
                
                # Store interface information and update RPG
                for unit in parsed_units:
                    # Only include class and function units, exclude methods
                    if unit.unit_type in ["class", "function"]:
                        unit_key = f"{unit.unit_type}:{unit.name}:{unit.parent or ''}"
                        features = unit_features_map.get(unit_key, [])
                        interface_key = f"{unit.unit_type} {unit.name}"
                        self.designed_interfaces[interface_key] = {
                            'unit': unit,
                            'features': features
                        }
                        
                        # Debug logging
                        self.logger.debug(f"Interface {unit.name} ({unit.unit_type}) has features: {features}")
                        
                        # Update RPG with interface metadata
                        self._update_rpg_metadata(unit, features)

                self.logger.info(f"Updated interfaces: {len(self.designed_interfaces)} total, "
                               f"covered features: {len(self.covered_features)}/{len(self.tgt_features)}")
                
            except Exception as e:
                self.logger.error(f"Failed to update interface environment: {e}")
    
    def _update_rpg_metadata(self, unit, features):
        """Update RPG node metadata with interface information"""
    
        if not self.repo_rpg:
            return
        
        if not unit.unit_type in ["function", "class"]:
            return 
        
        for feature_path in features:
            try:
                self.logger.debug(f"Processing feature path: {feature_path}")
                
                # Add subgraph prefix if not already present
                if not feature_path.startswith(self.tgt_subgraph_name + "/"):
                    feature_path = self.tgt_subgraph_name + "/" + feature_path 
                
                self.logger.debug(f"Final feature path: {feature_path}")
                
                # Find the feature node in RPG
                node = self.repo_rpg.get_node_by_feature_path(feature_path)
                
                self.logger.debug(f"Found node: {node.name if node else 'None'}")

                
                if node:
                    node_type = None
                    if unit.unit_type == "function":
                        node_type = NodeType.FUNCTION
                    elif unit.unit_type == "class":
                        node_type = NodeType.CLASS
                    
                    # Ensure node has metadata object
                    if node.meta is None:
                        node.meta = NodeMetaData()
                    
                    if node.meta.type_name == None:
                        node.meta.type_name = node_type
                    new_path = f"{self.tgt_file_path}:{unit.name}"
                    if node.meta.path == None:
                        node.meta.path = new_path
                    else:
                        if isinstance(node.meta.path, str):
                            if node.meta.path != new_path:
                                node.meta.path = [node.meta.path, new_path]
                        else:
                            if new_path not in node.meta.path:
                                node.meta.path.append(new_path)
                            
                    self.logger.info(f"Updated RPG node {node.name} with interface {unit.name}")
                        
            except Exception as e:
                self.logger.warning(f"Failed to update RPG metadata for feature {feature_path}: {e}")


# ========================
# 4. AGENT
# ========================
class InterfaceAgent(AgentwithReview):
    """Agent responsible for designing component interfaces"""
    
    def __init__(
        self,
        llm_cfg: Union[str, Dict, LLMConfig],
        design_system_prompt: str = DESIGN_ITF,
        design_context_window: int = 30,
        review_system_prompt: str = DESIGN_ITF_REVIEW,
        review_context_window: int = 10,
        max_review_times: int = 1,
        register_tools: Optional[List[Tool]] = None,
        logger: Optional[logging.Logger] = None,
    
        file_node: FileNode=None,
        tgt_subgraph_name: str=None,
        repo_skeleton: RepoSkeleton = None,
        repo_rpg: RPG = None,
        rtl_context: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        if register_tools is None:
            register_tools = [DesignInterfacesTool()]
        
        super().__init__(
            llm_cfg=llm_cfg,
            design_system_prompt=design_system_prompt,
            design_context_window=design_context_window,
            review_system_prompt=review_system_prompt,
            review_format=InterfaceReviewOutput,
            max_review_times=max_review_times,
            register_tools=register_tools,
            logger=logger,
            review_context_window=review_context_window,
            **kwargs
        )
        
        self.tgt_file_node = file_node
        self.tgt_file_path = file_node.path if file_node else ""
        self.tgt_subgraph_name = tgt_subgraph_name
        self.repo_skeleton = repo_skeleton
        self.repo_rpg = repo_rpg
        self.rtl_context = rtl_context
        
        # Create custom environment
        self._env = InterfaceEnv(
            review_llm=self.review_llm,
            review_format=InterfaceReviewOutput,
            review_memory=self.review_memory,
            review_times=max_review_times,
            register_tools=register_tools,
            tgt_file_path=file_node.path if file_node else "",
            tgt_subgraph_name=tgt_subgraph_name if tgt_subgraph_name else "",
            repo_skeleton=repo_skeleton,
            repo_rpg=repo_rpg,
            rtl_context=rtl_context,
            logger=logger
        )

    def _is_rtl_mode(self) -> bool:
        return _is_rtl_mode(self.rtl_context)

    def _get_rtl_file_spec(self, file_path: str) -> Dict[str, Any]:
        return _get_rtl_file_spec(self.rtl_context, file_path)

    def _build_rtl_units_for_file(self, file_path: str) -> Dict[str, Dict[str, Any]]:
        spec = self._get_rtl_file_spec(file_path)
        if not spec:
            return {}

        file_kind = spec.get("file_kind", "")
        owned_modules = list(spec.get("owned_modules", []) or [])
        secondary_context = _get_rtl_secondary_context(self.rtl_context, file_path)
        file_implementation_context = _get_rtl_file_implementation_context(self.rtl_context, file_path)

        def unit_entry(
            unit_name: str,
            unit_kind: str,
            module_name: str = "",
            responsibility: str = "",
            depends_on_files: Optional[List[str]] = None,
            trace_features: Optional[List[str]] = None,
            implementation_summary: str = "",
            detail_payload: Optional[Dict[str, Any]] = None,
        ) -> Dict[str, Any]:
            module_name = module_name or (unit_name.split(":", 1)[-1].strip() if ":" in unit_name else "")
            trace_features = list(trace_features or [])
            trace_context = _get_rtl_trace_context(self.rtl_context, file_path, trace_features)
            entry = {
                "file_path": file_path,
                "unit_name": unit_name,
                "unit_kind": unit_kind,
                "responsibility": responsibility or spec.get("responsibility", ""),
                "implementation_summary": implementation_summary or responsibility or spec.get("responsibility", ""),
                "depends_on_files": list(depends_on_files or spec.get("depends_on_files", []) or []),
                "owned_modules": owned_modules,
                "features": trace_features,
                "trace_context": trace_context,
                "secondary_context": secondary_context,
                "implementation_context": {},
            }
            if isinstance(detail_payload, dict):
                for key in (
                    "requirement_details",
                    "test_details",
                    "property_details",
                    "node_details",
                    "anchor_details",
                    "hint_details",
                    "depends_on_units",
                    "role",
                ):
                    if key in detail_payload:
                        entry[key] = detail_payload.get(key)
            if unit_kind in {"rtl_module", "rtl_package"}:
                entry["implementation_context"] = build_unit_implementation_context(
                    file_path=file_path,
                    unit_kind=file_kind,
                    module_name=module_name,
                    file_implementation_context_by_path={file_path: file_implementation_context},
                )
            top_facts = _get_top_module_facts(self.rtl_context, file_path)
            if top_facts:
                entry.update(top_facts)
            return entry

        units: Dict[str, Dict[str, Any]] = {}
        target_units = [unit for unit in (spec.get("target_units", []) or []) if isinstance(unit, dict)]
        if target_units:
            for target in target_units:
                unit_name = str(target.get("unit_name", "")).strip()
                unit_kind = str(target.get("unit_kind", "")).strip()
                if not unit_name or not unit_kind:
                    continue
                module_name = str(target.get("module_name", "")).strip()
                trace_features = _get_target_unit_trace_ids(target)
                units[unit_name] = unit_entry(
                    unit_name=unit_name,
                    unit_kind=unit_kind,
                    module_name=module_name,
                    responsibility=str(target.get("responsibility", "")).strip(),
                    depends_on_files=list(target.get("depends_on_files", []) or []),
                    trace_features=trace_features,
                    implementation_summary=str(target.get("implementation_summary", "")).strip(),
                    detail_payload=target,
                )
                if not units[unit_name].get("trace_context"):
                    units[unit_name]["trace_context"] = _get_target_unit_trace_context(self.rtl_context, file_path, target)
            if units:
                return units

        trace_features = (
            list(spec.get("related_req_ids", []) or [])
            + list(spec.get("related_test_ids", []) or [])
            + list(spec.get("related_prop_ids", []) or [])
        )
        if file_kind in {"rtl_module", "rtl_top_module"}:
            target_names = owned_modules or [file_path]
            for name in target_names:
                units[f"module:{name}"] = unit_entry(
                    f"module:{name}",
                    "rtl_module",
                    module_name=name,
                    trace_features=trace_features,
                )
        elif file_kind == "rtl_package":
            target_names = owned_modules or [file_path]
            for name in target_names:
                units[f"package:{name}"] = unit_entry(
                    f"package:{name}",
                    "rtl_package",
                    module_name=name,
                    trace_features=trace_features,
                )
        elif file_kind in {"testbench", "tb_model"}:
            unit_name = f"tb:{file_path}"
            units[unit_name] = unit_entry(unit_name, "testbench", trace_features=trace_features)
        elif file_kind == "script":
            unit_name = f"script:{file_path}"
            units[unit_name] = unit_entry(unit_name, "script", trace_features=trace_features)
        elif file_kind == "build_file":
            unit_name = f"build:{file_path}"
            units[unit_name] = unit_entry(unit_name, "build", trace_features=trace_features)
        return units

    def _render_rtl_skeletons(self, designed_interfaces: Dict[str, Dict[str, Any]]) -> str:
        code_blocks: List[str] = []
        for _, info in designed_interfaces.items():
            unit = info.get("unit")
            code = _get_unit_code(unit)
            if code:
                code_blocks.append(code.strip())
        if not code_blocks:
            return ""
        rendered = "\n\n".join(block for block in code_blocks if block)
        return rendered if rendered.endswith("\n") else rendered + "\n"
    
    def design_file_interface(
        self,
        tgt_subtree_implemented: List[FileNode],
        all_implemented_subtrees: Dict[str, List[FileNode]],
        max_steps: int = 10,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Design interface for a specific file, following the original InterfacesDesigner pattern
        
        Args:
            file_node: File to design interfaces for
            data_flow_graph: Component data flow relationships
            tgt_subtree: Target subtree containing the file
            tgt_subtree_implemented: Already implemented files in subtree
            all_implemented_subtrees: All implemented subtrees
            base_classes: Available base classes
            max_steps: Maximum design iterations
            max_retries: Maximum retry attempts
            
        Returns:
            Dict with designed interfaces, code, and metadata
        """
        file_node = self.tgt_file_node
        tgt_subgraph_name = self.tgt_subgraph_name
        
        self.logger.info(f"[InterfaceAgent] Designing interface for {file_node.path}")
        
        file_path = file_node.path
        # Store context information in environment for dynamic injection
        self._env.tgt_subtree_implemented = tgt_subtree_implemented
        self._env.all_implemented_subtrees = all_implemented_subtrees
        file_features = set(file_node.feature_paths)
        self._env.tgt_features = file_features
        
        # Prepare context information
        repo_info = self.repo_rpg.repo_info if self.repo_rpg else "Repository information not available"
        data_flow_str = json.dumps(self.repo_rpg.data_flow, indent=2)
        upstream_context = self._extract_upstream_context(
            self.repo_rpg.data_flow if self.repo_rpg else [], 
            tgt_subgraph_name, 
            all_implemented_subtrees
        )
        implemented_summary = self._format_implemented_summary(
            tgt_subtree_implemented, file_node.path
        )
        base_classes_str = _format_base_classes(self.repo_rpg.base_classes)
        if self._is_rtl_mode():
            rtl_units = self._build_rtl_units_for_file(file_path)
            self._env.tgt_units = rtl_units
            self._env.covered_units = set()
            top_facts = _get_top_module_facts(self.rtl_context, file_path)
            unit_targets = []
            for unit_name, unit_info in rtl_units.items():
                trace_context = format_trace_context(unit_info.get("trace_context", []))
                secondary_context = _format_secondary_context(unit_info.get("secondary_context", {}))
                implementation_context = format_implementation_context(unit_info.get("implementation_context", {}))
                unit_targets.append(
                    f"- {unit_name} ({unit_info['unit_kind']}): responsibility={unit_info['responsibility']}, "
                    f"depends_on_files={unit_info['depends_on_files']}, owned_modules={unit_info['owned_modules']}, "
                    f"trace_ids={unit_info['features']}\n"
                    f"  trace_context:\n{trace_context}\n"
                    f"  implementation_context:\n{implementation_context}\n"
                    f"  supplementary_context:\n{secondary_context}"
                )
            unit_targets_str = "\n".join(unit_targets) if unit_targets else "- No RTL units found."
            top_facts_section = ""
            top_module_rules = ""
            if top_facts:
                top_facts_section = f"{_format_top_module_facts(top_facts)}\n\n"
                top_module_rules = (
                    "- For `rtl_top_module`, first preserve the canonical top-level external interface, then sketch the minimal integration structure.\n"
                    "- Use the exact top-level external ports listed in the spec facts section below.\n"
                    "- Treat `top_module` as the default integration focus, not as a reason to over-design the file.\n"
                    "- Use `file_kind`, `responsibility`, `implementation_summary`, `depends_on_files`, `owned_modules`, and `target_units` as task semantics: they tell you what this file must deliver now.\n"
                    "- The `spec` should explain what the unit does, what it depends on, what interface it exposes, what minimal skeleton it needs, and how it fits into the repository.\n\n"
                )
            task = (
                "[Begin Iteration]\n"
                f"Design RTL implementation skeletons and contracts for file: `{file_node.path}`.\n\n"
                "Requirements:\n"
                "- ONLY cover the following RTL target units:\n"
                f"{unit_targets_str}\n"
                "- When calling `design_itfs_for_feature`, use the exact `file_path`, `unit_name`, and `unit_kind` listed above.\n"
                "- Do NOT emit Python syntax, Python functions/classes, dataclasses, or `pass` stubs.\n"
                "- For each target unit, return BOTH a minimal contract (`spec`) and a minimal code skeleton (`code`).\n"
                "- Define minimal RTL/build skeletons only for the current file.\n"
                "- Reuse upstream files and shared package definitions when they are already available.\n"
                "- Prefer minimal, concrete RTL contracts over generic architecture commentary.\n\n"
                f"{top_module_rules}"
                "Skeleton expectations by unit kind:\n"
                "- `rtl_module`: provide a SystemVerilog `module ... endmodule` skeleton with parameters, ports, and placeholders.\n"
                "- `rtl_package`: provide a SystemVerilog `package ... endpackage` skeleton with typedef/localparam placeholders.\n"
                "- `testbench`: provide a SystemVerilog testbench skeleton with DUT hookup and checker placeholders.\n"
                "- `script`: provide a shell skeleton with shebang, env/input checks, and placeholder command flow.\n"
                "- `build`: provide a Makefile skeleton with targets, dependencies, and command placeholders.\n\n"
                "Contract expectations by unit kind:\n"
                "- `rtl_module`: describe ports, parameters, clock/reset expectations, and key I/O behavior.\n"
                "- `rtl_package`: describe typedef/enum/constant/export contents.\n"
                "- `testbench`: describe DUT hookup, stimulus, checkers, or golden-model interaction.\n"
                "- `script` / `build`: describe inputs, outputs, commands, dependencies, and failure conditions.\n\n"
                "Global context you can use:\n"
                "=== Repository Info ===\n"
                f"{repo_info}\n\n"
                "=== Data Flow Graph ===\n"
                f"{data_flow_str}\n\n"
                "=== Upstream Context ===\n"
                f"{upstream_context}\n\n"
                "=== Implemented Summary ===\n"
                f"{implemented_summary}\n\n"
                "=== Shared Definitions ===\n"
                f"{base_classes_str}\n\n"
                "=== Supplementary File Context ===\n"
                f"{_format_secondary_context(_get_rtl_secondary_context(self.rtl_context, file_path))}\n\n"
                f"{top_facts_section}"
                "Please follow the system prompt carefully and output RTL skeletons and contracts for the target units only.\n"
            )
        else:
            file_features_str = '\n'.join([f"- {f}" for f in file_features])
            task = (
                "[Begin Iteration]\n"
                f"Design interfaces for file: `{file_node.path}`.\n\n"
                "Requirements:\n"
                "- ONLY cover the following feature paths:\n"
                f"{file_features_str}\n"
                "- When calling `design_itfs_for_feature`, ONLY use feature paths listed above.\n"
                "- Do NOT introduce new/unspecified feature paths.\n"
                "- Define interfaces only (imports + signature + docstring + `pass`).\n\n"
                "**Interface Planning Strategy:**\n"
                "- **Design interfaces per call**: Create several focused interfaces in each tool call.\n"
                "- **Avoid large monolithic interfaces**: Don't put all features in one big class or function.\n"
                "- **Group logically related features**: Only group features that share state, configuration, or lifecycle.\n"
                "- **One responsibility per interface**: Each interface should have a single, clear purpose.\n"
                "- **Iterative approach**: After each successful call, the tool will show your progress and suggest next steps.\n\n"
                "- You MAY import and reuse symbols (classes, functions, data structures) described in "
                "`Upstream Context`, `Implemented Summary`, and `Available Base Classes` via normal Python imports.\n\n"
                "Global context you can use:\n"
                "=== Repository Info ===\n"
                f"{repo_info}\n\n"
                "=== Data Flow Graph ===\n"
                f"{data_flow_str}\n\n"
                "=== Upstream Context ===\n"
                f"{upstream_context}\n\n"
                "=== Implemented Summary ===\n"
                f"{implemented_summary}\n\n"
                "=== Available Base Classes ===\n"
                f"{base_classes_str}\n"
                "Please follow the instructions and output format in the system prompt carefully and design the interfaces accordingly.\n"
            )
        
        # Execute the design process
        result = self.run(
            task=task,
            max_error_times=max_retries,
            max_steps=max_steps
        )
        
        # Process results
        designed_interfaces = self._env.designed_interfaces
        covered_features = self._env.covered_features
        
        # Generate final code
        if self._is_rtl_mode():
            final_code = self._render_rtl_skeletons(designed_interfaces)
        else:
            final_code = render_codeunits_as_file(
                units=self._env.imports_units + [info['unit'] for info in designed_interfaces.values()]
            )
        
        # Create feature interface map
        feature_interface_map = self._create_feature_interface_map(designed_interfaces)
        unit_to_kind = {
            interface_key: _get_unit_kind(interface_info["unit"])
            for interface_key, interface_info in designed_interfaces.items()
        }
        unit_to_spec = {
            interface_key: _get_unit_text(interface_info["unit"])
            for interface_key, interface_info in designed_interfaces.items()
        }
        unit_to_code = {
            interface_key: _get_unit_code(interface_info["unit"])
            for interface_key, interface_info in designed_interfaces.items()
        }
        unit_to_trace_context = {
            interface_key: interface_info.get("trace_context", [])
            for interface_key, interface_info in designed_interfaces.items()
        }
        unit_to_implementation_context = {
            interface_key: interface_info.get("implementation_context", {})
            for interface_key, interface_info in designed_interfaces.items()
        }
        secondary_context = _get_rtl_secondary_context(self.rtl_context, file_node.path) if self._is_rtl_mode() else {}
        
        # Log feature map like original implementation
        self.logger.info(f"Feature Map for file `{file_node.path}`: {json.dumps(feature_interface_map, indent=4)}")
        self.logger.info(f"[InterfaceAgent] Designed {len(designed_interfaces)} interfaces for {file_node.path}")
        
        return {
            "code": final_code,
            "feature_interface_map": feature_interface_map,
            "designed_interfaces": designed_interfaces,
            "unit_to_kind": unit_to_kind,
            "unit_to_spec": unit_to_spec,
            "unit_to_code": unit_to_code,
            "unit_to_trace_context": unit_to_trace_context,
            "unit_to_implementation_context": unit_to_implementation_context,
            "secondary_context": secondary_context,
            "units": list(feature_interface_map.keys()),
            "update_repo_rpg": self._env.repo_rpg,
            "repo_rpg": self._env.repo_rpg,
            "covered_features": list(covered_features) if not self._is_rtl_mode() else list(self._env.covered_units),
            "success": self._env.is_completed,
            "agent_results": result
        }
    
    def _extract_upstream_context(
        self, 
        data_flow_graph: List[Dict],
        tgt_subgraph: str,
        all_implemented_subtrees: Dict[str, List[FileNode]],
        top_n: int=5
    ) -> str:
        """Extract upstream interface context"""
        upstream_nodes = set()
        
        # Find upstream dependencies
        for edge in data_flow_graph:
            from_node = edge.get("source")
            to_node = edge.get("target")
            if self._is_rtl_mode():
                if to_node == self.tgt_file_path:
                    upstream_nodes.add(from_node)
            elif to_node and to_node.startswith(tgt_subgraph):
                upstream_nodes.add(from_node)
        
        if not upstream_nodes:
            return "No upstream modules connected to this subtree."
        
        # Format upstream context
        upstream_summary = []
        for node in sorted(upstream_nodes):
            impl_files = all_implemented_subtrees.get(node, [])
            if not isinstance(impl_files, list):
                logging.warning(f"Expected list of FileNode, but got {type(impl_files)} for node={node}")
                continue
            impl_files = impl_files[:top_n]
            if not impl_files:
                continue
            for file_node in impl_files:
                path = file_node.path
                code_skeleton = get_skeleton(file_node.code, keep_indent=True)
                if self._is_rtl_mode():
                    fence = _code_fence_for_file(path, "", file_node.code)
                    upstream_summary.append(
                        f"### From file: `{node}`\n"
                        f"Implemented file: `{path}`\n"
                        f"Code Skeleton:\n```{fence}\n{code_skeleton}\n```\n"
                    )
                else:
                    features = ', '.join(file_node.feature_paths)
                    upstream_summary.append(
                        f"### From module: `{node}`\nFile: `{path}`\nFeatures: {features}\nCode:\n```python\n{code_skeleton}\n```\n"
                    )
            upstream_summary.append('...some files have been omitted due to context length constraints...')

        
        return "\n".join(upstream_summary) if upstream_summary else "No implemented upstream interfaces found."
    
    def _format_implemented_summary(
        self, 
        tgt_subtree_implemented: List[FileNode], 
        current_file: str,
        latest_k: int =5
    ) -> str:
        """Format summary of already implemented files in subtree"""
        if not tgt_subtree_implemented:
            return "No files implemented yet in this subtree."
        
        summary_lines = []
        for impl_file in tgt_subtree_implemented[-latest_k:]:
            if impl_file.path != current_file:
                skeleton = get_skeleton(raw_code=impl_file.code, keep_indent=True)
                if self._is_rtl_mode():
                    fence = _code_fence_for_file(impl_file.path, "", impl_file.code)
                    block = (
                        f"#### Related Implemented File: `{impl_file.path}`\n"
                        f"**Code Skeleton:**\n"
                        f"```{fence}\n{skeleton}\n```\n"
                    )
                else:
                    features_str = ', '.join(impl_file.feature_paths[:2])
                    if len(impl_file.feature_paths) > 2:
                        features_str += f", ...{len(impl_file.feature_paths) - 2} more"
                    block = (
                        f"#### Related Implemented File: `{impl_file.path}`\n"
                        f"**Associated Features:** {features_str}\n"
                        f"**Code Skeleton:**\n"
                        f"```python\n{skeleton}\n```\n"
                    )
                summary_lines.append(block)
        
        return "\n".join(summary_lines)
    
    def _create_feature_interface_map(self, designed_interfaces: Dict) -> Dict[str, List[str]]:
        """
        Create mapping from interface key to features, following the original implementation logic
        
        Args:
            designed_interfaces: Dict with interface information
            
        Returns:
            Dict mapping interface key (e.g. "function login_user") to list of feature paths
        """
        feature_interface_map = {}
        
        for interface_key, interface_info in designed_interfaces.items():
            unit = interface_info['unit']
            features = interface_info.get('features', [])

            if self._is_rtl_mode():
                map_key = _get_unit_name(unit) or interface_key
                feature_interface_map[map_key] = features
            elif unit.unit_type in ["class", "function"]:
                map_key = f"{unit.unit_type} {unit.name}"
                feature_interface_map[map_key] = features
        
        return feature_interface_map
    
