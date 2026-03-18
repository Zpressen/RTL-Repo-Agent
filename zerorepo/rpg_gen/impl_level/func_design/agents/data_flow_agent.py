import logging
import json, json5
from typing import Union, Dict, Optional, List, Any, Tuple, Iterable
from collections import defaultdict
from pydantic import BaseModel, Field, ValidationError
from zerorepo.rpg_gen.base import (
    RPG, NodeType,
    Tool, ToolResult, ToolCall,
    ToolExecResult, ToolCallArguments,
    LLMClient, LLMConfig, Memory,
    AgentwithReview, ReviewEnv,
    RepoSkeleton
)
from ..prompts import (
    COMPONENT_DATA_FLOW, 
    COMPONENT_DATA_FLOW_REVIEW,
    GENERATE_DATA_FLOW_TOOL
)
from zerorepo.rpg_gen.impl_level.rtl_trace import format_trace_context

# ========================
# 1. REVIEW MODELS
# ========================
class DataFlowReviewCategory(BaseModel):
    """Single review dimension block"""
    feedback: str = Field(description="Concrete, actionable guidance for this dimension")
    pass_: bool = Field(alias="pass", description="Whether this dimension passed review")


class DataFlowReviewBlock(BaseModel):
    """Full review section containing all required dimensions"""
    Data_Integrity: DataFlowReviewCategory = Field(alias="Data Integrity")
    Flow_Logic: DataFlowReviewCategory = Field(alias="Flow Logic")
    Transformation_Clarity: DataFlowReviewCategory = Field(alias="Transformation Clarity")
    Coverage: DataFlowReviewCategory = Field(alias="Coverage")

    class Config:
        allow_population_by_field_name = True


class DataFlowReviewOutput(BaseModel):
    """Final JSON output for the data flow review process"""
    review: DataFlowReviewBlock
    final_pass: bool = Field(description="True only if all passes or remaining issues are minor")


# ========================
# 2. AGENT TOOL
# ========================
class DataFlowUnit(BaseModel):
    """Single data flow edge between components"""

    source: str = Field(
        ...,
        min_length=1,
        description="Name of the source component or subtree",
    )
    target: str = Field(
        ...,
        min_length=1,
        description="Name of the target component or subtree",
    )
    data_id: str = Field(
        ...,
        min_length=1,
        description="Unique identifier or description of the data being passed",
    )
    data_type: str = Field(
        ...,
        min_length=1,
        description="Type or structure of the data",
    )
    transformation: str = Field(
        ...,
        min_length=1,
        description="Description of what transformation is applied to the data",
    )
    
    
    class Config:
        allow_population_by_field_name = True


class GenerateDataFlowToolParamModel(BaseModel):
    """Input model for the generate_data_flow tool"""

    data_flow: List[DataFlowUnit] = Field(
        ...,
        description="List of data flow units between components",
    )
        
class GenerateDataFlowTool(Tool):
    name = "generate_data_flow"
    description = GENERATE_DATA_FLOW_TOOL
    
    ParamModel = GenerateDataFlowToolParamModel
    
    @classmethod
    def custom_parse(cls, raw: str) -> List[ToolCallArguments]:
        """Parse raw JSON input for data flow"""
        valid_tools = []
        
        try:
            if isinstance(raw, str):
                raw = raw.strip()
                if raw.startswith("```"):
                    raw = raw.strip("`")
                raw = raw.replace("```json", "").replace("```", "").strip()
                
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
                # Handle both wrapped and direct data flow formats
                if "data_flow" not in params and isinstance(params, list):
                    params = {"data_flow": params}
            
                valid_tools.append(params)
                
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
            data_flow = arguments.get("data_flow", [])
            repo_rpg: RPG = env.repo_rpg
            rtl_context = getattr(env, "rtl_context", None)

            if not data_flow:
                return ToolExecResult(
                    output=None,
                    error="Empty data flow provided",
                    error_code=1,
                    state={}
                )
            
            # Validate data flow
            required_components = repo_rpg.get_functional_areas()
            if rtl_context and rtl_context.get("component_names"):
                required_components = rtl_context["component_names"]

            passed, err_msg = cls._validate_data_flow(data_flow, required_components)
            
            if not passed:
                return ToolExecResult(
                    output=None,
                    error=err_msg,
                    error_code=1,
                    state={}
                )
            
            return ToolExecResult(
                output=err_msg,
                error=None,
                error_code=0,
                state={"data_flow": data_flow}
            )
            
        except Exception as e:
            return ToolExecResult(
                output=None,
                error=str(e),
                error_code=1,
                state={}
            )
    
    @classmethod
    def _validate_data_flow(cls, output_json: List[Dict], required_keys: Iterable[str]) -> Tuple[bool, str]:
        """
        Validate data_flow:
        1. Whether both source / target are in required_keys
        2. Whether any nodes in required_keys are completely unused
        3. Whether there is a cycle, and report the involved nodes and edge (item) indices
        """
        used_nodes = set()
        errors: List[str] = []

        # 记录边到 item 索引的映射，用于报错更精确
        edge_indices: Dict[Tuple[str, str], List[int]] = defaultdict(list)

        # ---- 基础校验：节点是否存在、收集使用情况、边索引 ----
        for i, item in enumerate(output_json):
            from_node = item.get("source")
            to_node = item.get("target")

            # 检查 source/target 是否在 required_keys 中
            for role, node in [("source", from_node), ("target", to_node)]:
                if node is None:
                    errors.append(f"Item {i}: '{role}' is missing.")
                    continue
                if node not in required_keys:
                    errors.append(
                        f"Item {i}: '{role}' node '{node}' is not in required_keys."
                    )

            if from_node and to_node:
                used_nodes.update([from_node, to_node])
                edge_indices[(from_node, to_node)].append(i)

        unused_nodes = set(required_keys) - used_nodes
        if unused_nodes:
            errors.append(
                f"Unused nodes from required_keys (i.e., no data flow defined): {sorted(unused_nodes)}"
            )

        # # ---- 构建图，用于环检测 ----
        # graph: Dict[str, List[str]] = defaultdict(list)
        # all_nodes = set(required_keys)

        # for item in output_json:
        #     src = item.get("source")
        #     tgt = item.get("target")
        #     if src and tgt:
        #         graph[src].append(tgt)
        #         all_nodes.add(src)
        #         all_nodes.add(tgt)

        # # ---- 环检测（DFS）----
        # # 状态：0 = 未访问, 1 = 访问中, 2 = 已完成
        # visit_state: Dict[str, int] = {}
        # cycles: List[List[str]] = []

        # def dfs(node: str, path: List[str]):
        #     state = visit_state.get(node, 0)
        #     if state == 1:
        #         # 找到一个环：从 path 中第一次出现该 node 开始到结尾
        #         if node in path:
        #             idx = path.index(node)
        #             cycle_nodes = path[idx:] + [node]
        #         else:
        #             cycle_nodes = path + [node]
        #         cycles.append(cycle_nodes)
        #         return
        #     if state == 2:
        #         return

        #     visit_state[node] = 1
        #     path.append(node)
        #     for nei in graph.get(node, []):
        #         dfs(nei, path)
        #     path.pop()
        #     visit_state[node] = 2

        # for node in all_nodes:
        #     if visit_state.get(node, 0) == 0:
        #         dfs(node, [])

        # # ---- 如果存在环，构造详细错误信息 ----
        # if cycles:
        #     for idx, cycle in enumerate(cycles, start=1):
        #         # cycle 形如 [A, B, C, A]
        #         cycle_str = " -> ".join(cycle)
        #         errors.append(
        #             f"Cycle {idx} detected in data flow: {cycle_str}"
        #         )

        #         # 找出这个环涉及到的具体边与 item 索引
        #         edge_desc_lines = []
        #         for j in range(len(cycle) - 1):
        #             src = cycle[j]
        #             tgt = cycle[j + 1]
        #             indices = edge_indices.get((src, tgt), [])
        #             if indices:
        #                 edge_desc_lines.append(
        #                     f"  - Edge {src} -> {tgt} appears in items {indices}"
        #                 )
        #             else:
        #                 edge_desc_lines.append(
        #                     f"  - Edge {src} -> {tgt} is implied but no exact item index was found"
        #                 )

        #         errors.append(
        #             "  Edges involved in this cycle:\n" + "\n".join(edge_desc_lines)
        #         )
        #         errors.append(
        #             "  Suggestion: Break this circular dependency by either:\n"
        #             "  - Removing one of the above edges, or\n"
        #             "  - Introducing an intermediate component so that data flows in a single direction "
        #             "(i.e., the graph becomes a DAG)."
        #         )

        if errors:
            return False, "\n".join(errors)

        return True, "All data flow checks passed."

# ========================
# 3. ENVIRONMENT
# ========================

class DataFlowEnv(ReviewEnv):
    """Environment for data flow generation phase"""
    
    def __init__(
        self,
        review_llm: LLMClient,
        review_format: BaseModel,
        review_memory: Memory,
        review_times: int = 1,
        register_tools: List = [],
        repo_skeleton: RepoSkeleton=None,
        repo_rpg: RPG = None,
        rtl_context: Optional[Dict[str, Any]] = None,
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
        # self.data_flow = []
        self.is_completed = False
        self.logger = logger or logging.getLogger(__name__)

    def _is_rtl_mode(self) -> bool:
        return bool(self.rtl_context and self.rtl_context.get("component_names"))

    def _format_rtl_file_specs(self) -> str:
        if not self.rtl_context:
            return ""

        lines: List[str] = []
        for spec in self.rtl_context.get("file_specs", []):
            file_path = spec.get("file_path", "")
            bucket = spec.get("bucket", "")
            file_kind = spec.get("file_kind", "")
            responsibility = spec.get("responsibility", "")
            implementation_status = spec.get("implementation_status", "")
            implementation_summary = spec.get("implementation_summary", "")
            depends = ", ".join(spec.get("depends_on_files", [])) or "-"
            modules = ", ".join(spec.get("owned_modules", [])) or "-"
            target_units = ", ".join(
                [
                    str(unit.get("unit_name", "")).strip()
                    for unit in (spec.get("target_units", []) or [])
                    if isinstance(unit, dict) and str(unit.get("unit_name", "")).strip()
                ]
            ) or "-"
            req_ids = ", ".join(spec.get("related_req_ids", [])) or "-"
            test_ids = ", ".join(spec.get("related_test_ids", [])) or "-"
            prop_ids = ", ".join(spec.get("related_prop_ids", [])) or "-"
            trace_ids = (
                list(spec.get("related_req_ids", []) or [])
                + list(spec.get("related_test_ids", []) or [])
                + list(spec.get("related_prop_ids", []) or [])
            )
            trace_context = format_trace_context(
                list((self.rtl_context.get("file_trace_context_by_path", {}) or {}).get(file_path, []) or [])
            ) if trace_ids else "- No canonical trace context."
            lines.append(
                f"- {file_path} | bucket={bucket} | kind={file_kind}\n"
                f"  implementation_status: {implementation_status or '-'}\n"
                f"  responsibility: {responsibility or '-'}\n"
                f"  implementation_summary: {implementation_summary or '-'}\n"
                f"  depends_on_files: {depends}\n"
                f"  owned_modules: {modules}\n"
                f"  target_units: {target_units}\n"
                f"  related_req_ids: {req_ids}\n"
                f"  related_test_ids: {test_ids}\n"
                f"  related_prop_ids: {prop_ids}\n"
                f"  trace_context:\n{trace_context}"
            )
        return "\n".join(lines)

    def _format_rtl_file_graph_seed(self) -> str:
        if not self.rtl_context:
            return ""

        seed = self.rtl_context.get("file_graph_seed", [])
        if not seed:
            return "- No explicit depends_on_files edges were provided."

        lines = [
            f"- {item.get('source', '')} -> {item.get('target', '')} ({item.get('reason', 'seed')})"
            for item in seed
        ]
        return "\n".join(lines)
    
    def load_review_message(self, tool_calls: List[ToolCall]):
        repo_name = self.repo_rpg.repo_name
        repo_info = self.repo_rpg.repo_info
        
        repo_skeleton_str = self.repo_skeleton.to_tree_string()
        tool_str = json.dumps([tool_call.to_dict() for tool_call in tool_calls], indent=2)

        if self._is_rtl_mode():
            available_files = ", ".join(self.rtl_context.get("component_names", []))
            review_input = (
                "You should review an RTL file-level data flow design based on the following information:\n"
                f"Repository Name: {repo_name}\n"
                f"Description: {repo_info}\n"
                f"Repository Skeleton: {repo_skeleton_str}\n"
                f"Functional Graph Overview: {self.rtl_context.get('skeleton_overview', repo_skeleton_str)}\n"
                f"Available RTL Files: {available_files}\n"
                f"RTL File Specs:\n{self._format_rtl_file_specs()}\n"
                f"File Dependency Seed:\n{self._format_rtl_file_graph_seed()}\n"
                f"Owned Modules By File:\n{json.dumps(self.rtl_context.get('owned_modules', {}), indent=2)}\n"
                f"Proposed data flow:\n{tool_str}\n"
                "Please evaluate the data flow according to the review criteria and produce a consolidated review.\n"
                "Respond with a valid JSON object that follows the required output format in the system prompt.\n"
                "Do not include any text outside of the JSON object."
            )
        else:
            tree_overview = self.repo_rpg.visualize_dir_map(max_depth=3, feature_only=False)
            trees_names = self.repo_rpg.get_functional_areas()
            review_input = (
                "You should review a component data flow design based on the following information:\n"
                f"Repository Name: {repo_name}\n"
                f"Description: {repo_info}\n"
                f"Repository Skeleton: {repo_skeleton_str}\n"
                f"Functional Graph Overview: {tree_overview}\n"
                f"Available Subgraph Names: {', '.join(trees_names)}\n"
                f"Proposed data flow:\n{tool_str}\n"
                "Please evaluate the data flow according to the review criteria and produce a consolidated review.\n"
                "Respond with a valid JSON object that follows the required output format in the system prompt.\n"
                "Do not include any text outside of the JSON object."
            )
        
        return review_input
    
    def should_terminate(self, tool_calls, tool_results):
        """Check if data flow generation is complete"""
        return self.is_completed
    
    def update_env(self, tool_call, result):
        """Update environment state after tool execution"""
        if tool_call.name == "generate_data_flow" and result.success:
            try:
                data_flow = result.state.get("data_flow", [])
                if data_flow:
                    # Check if we have adequate data flow coverage
                    component_names = self.repo_rpg.get_functional_areas()
                    if self._is_rtl_mode():
                        component_names = self.rtl_context.get("component_names", [])
                    data_flow_cmpt_names = []
                    for flow_item in data_flow:
                        data_flow_cmpt_names.append(flow_item["source"])
                        data_flow_cmpt_names.append(flow_item["target"])
                    data_flow_cmpt_names = list(set(data_flow_cmpt_names))
                    if component_names and len(component_names) == len(data_flow_cmpt_names):
                        self.repo_rpg.data_flow = data_flow
                        self.is_completed = True
                        self.logger.info("[DataFlow] Adequate data flow coverage, marking as completed")
            except Exception as e:
                self.logger.error(f"Failed to update data flow: {e}")


# ========================
# 4. AGENT
# ========================

class DataFlowAgent(AgentwithReview):
    """Agent responsible for generating component data flows"""
    
    def __init__(
        self,
        llm_cfg: Union[str, Dict, LLMConfig],
        design_system_prompt: str = COMPONENT_DATA_FLOW,
        design_context_window: int = 30,
        review_system_prompt: str = COMPONENT_DATA_FLOW_REVIEW,
        review_context_window: int = 10,
        max_review_times: int = 1,
        repo_rpg: RPG = None,
        repo_skeleton: RepoSkeleton=None,
        rtl_context: Optional[Dict[str, Any]] = None,
        register_tools: Optional[List[Tool]] = None,
        logger: Optional[logging.Logger] = None,
        **kwargs
    ):
        if register_tools is None:
            register_tools = [GenerateDataFlowTool()]
        
        super().__init__(
            llm_cfg=llm_cfg,
            design_system_prompt=design_system_prompt,
            design_context_window=design_context_window,
            review_system_prompt=review_system_prompt,
            review_format=DataFlowReviewOutput,
            max_review_times=max_review_times,
            register_tools=register_tools,
            logger=logger,
            review_context_window=review_context_window,
            **kwargs
        )
        
        self.repo_rpg = repo_rpg
        self.repo_skeleton=repo_skeleton
        self.rtl_context = rtl_context
        
        # Create custom environment
        self._env = DataFlowEnv(
            review_llm=self.review_llm,
            review_format=DataFlowReviewOutput,
            review_memory=self.review_memory,
            review_times=max_review_times,
            register_tools=register_tools,
            repo_skeleton=repo_skeleton,
            repo_rpg=repo_rpg,
            rtl_context=rtl_context,
            logger=logger
        )

    def _is_rtl_mode(self) -> bool:
        return bool(self.rtl_context and self.rtl_context.get("component_names"))
    
    def generate_data_flow(
        self,
        max_retry: int =3,
        max_steps: int = 10,
        **kwargs
    ) -> Dict:
        """Generate component data flow"""
        extra_message = kwargs.get("extra_message", "")
        repo_name = self.repo_rpg.repo_name
        repo_info = self.repo_rpg.repo_info
        skeleton_info = self.repo_skeleton.to_tree_string()

        if self._is_rtl_mode():
            tree_overview = self.rtl_context.get("skeleton_overview", skeleton_info)
            component_names = self.rtl_context.get("component_names", [])
            file_specs = json.dumps(self.rtl_context.get("file_specs", []), indent=2)
            file_graph_seed = json.dumps(self.rtl_context.get("file_graph_seed", []), indent=2)
            task = (
                "Based on the RTL repository structure and deterministic file dependency relationships, "
                "generate file-level data flow between RTL implementation artifacts:\n"
                f"Repository Name: {repo_name}\n"
                f"Repository Info: {repo_info}\n"
                f"RTL Skeleton Overview: {tree_overview}\n\n"
                f"RTL File Paths: {', '.join(component_names)}\n"
                f"RTL File Specs:\n{file_specs}\n\n"
                f"File Dependency Seed:\n{file_graph_seed}\n"
                "Please use the generate_data_flow tool to create comprehensive file-level data flow definitions.\n"
                "In RTL mode:\n"
                "1. source and target must be file paths from the RTL File Paths list\n"
                "2. use depends_on_files, owned_modules, and related req/test/prop ids as the primary grounding context\n"
                "3. describe meaningful artifacts that move between files, modules, packages, testbenches, and scripts\n"
                "4. keep the flow acyclic and cover every RTL file at least once"
            )
        else:
            tree_overview = self.repo_rpg.visualize_dir_map(max_depth=3, feature_only=False)
            subgraph_names = self.repo_rpg.get_functional_areas()
            task = (
                f"Based on the repository structure and dependency relationships, generate data flow between components:\n"
                f"Repository Name: {repo_name}\n"
                f"Repository Info: {repo_info}\n"
                f"Functional Graph Overview: {tree_overview}\n\n"
                f"Component Names: {', '.join(subgraph_names)}\n"
                "Please use the generate_data_flow tool to create comprehensive data flow definitions.\n"
                "Focus on:\n"
                "1. What data flows between components\n"
                "2. Data types and formats\n"
                "3. Any transformations applied\n"
                "4. Direction of data flow"
            )
        
        task += f"\n{extra_message}\n".strip()
        
        
        result = self.run(
            task=task,
            max_error_times=max_retry,
            max_steps=max_steps
        )
        
        return {
            "data_flow": self.repo_rpg.data_flow,
            "repo_rpg": self._env.repo_rpg,
            "success": self._env.is_completed,
            "agent_results": result
        }
