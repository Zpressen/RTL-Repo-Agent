import yaml
import json
import logging
import re
from typing import Union, Dict, Tuple, Optional, Any, List
from pathlib import Path, PurePosixPath
from zerorepo.rpg_gen.base import (
    RPG, NodeType, Node, NodeMetaData,
    RepoSkeleton, LLMConfig
)
from zerorepo.utils.logs import setup_logger
from zerorepo.config.checkpoint_config import CheckpointManager, CheckpointFiles, get_checkpoint_manager
from .file_design import FileDesigner
from zerorepo.rtl_impl.rtl_kg import RTLKgService

# 封装完整的类去构建repo
class ImplBuilder:
    
    def __init__(
        self,
        llm_cfg: Optional[Union[str, Dict, LLMConfig]],
        skeleton_cfg: Union[str, Path],
        graph_cfg: Union[str, Path],
        repo_path: Union[str, Path],
        ckpt_dir: Union[str, Path],
        logger: logging.Logger,
        checkpoint_manager: Optional[CheckpointManager] = None,
        rtl_kg_config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize ImplBuilder with checkpoint management
        
        Args:
            llm_cfg: LLM configuration
            skeleton_cfg: skeleton configuration file path
            graph_cfg: graph configuration file path  
            repo_path: target repository path
            ckpt_dir: checkpoint directory
            logger: logger instance
            checkpoint_manager: optional CheckpointManager instance
            checkpoint_config: optional custom checkpoint configuration
        """
        self.llm_cfg = llm_cfg
        self.skeleton_cfg = skeleton_cfg if isinstance(skeleton_cfg, Path) \
            else Path(skeleton_cfg)
        self.graph_cfg = graph_cfg if isinstance(graph_cfg, Path) \
            else Path(graph_cfg)
            
        self.repo_path = repo_path if isinstance(repo_path, Path) \
            else Path(repo_path)
        self.repo_path.mkdir(exist_ok=True)
        self.rtl_kg_config = dict(rtl_kg_config or {})
        self.rtl_kg_service: Optional[RTLKgService] = None
        
        # Initialize checkpoint manager
        self.checkpoint_manager = checkpoint_manager
        # Legacy support - keep ckpt_dir for backward compatibility
        self.ckpt_dir = self.checkpoint_manager.checkpoint_dir
        
        # Save checkpoint configuration
        self.checkpoint_manager.save_config()
        
        self.logger = logger or setup_logger()
        self.logger.info(f"ImplBuilder initialized with checkpoint dir: {self.checkpoint_manager.checkpoint_dir}")
    
    # Properties for accessing checkpoint paths - eliminates hardcoded paths!
    @property
    def repo_data_path(self) -> Path:
        """Get repo data file path"""
        return self.checkpoint_manager.repo_data_path
    
    @property 
    def skeleton_result_path(self) -> Path:
        """Get skeleton result file path"""
        return self.checkpoint_manager.get_path("skeleton")
    
    @property
    def skeleton_agent_result_path(self) -> Path:
        """Get skeleton agent trajectory file path"""
        return self.checkpoint_manager.get_path("skeleton_trajectory")
    
    @property
    def graph_result_path(self) -> Path:
        """Get graph result file path"""
        return self.checkpoint_manager.get_path("graph")
    
    @property
    def tasks_result_path(self) -> Path:
        """Get tasks result file path"""
        return self.checkpoint_manager.get_path("tasks")
    
    @property
    def state_file(self) -> Path:
        """Get task manager state file path"""
        return self.checkpoint_manager.get_path("task_manager_state")
    
    @property
    def global_rpg_path(self) -> Path:
        """Get global RPG file path"""
        return self.checkpoint_manager.get_path("global_repo_rpg")
    
    @property 
    def cur_rpg_path(self) -> Path:
        """Get current RPG file path"""
        return self.checkpoint_manager.get_path("current_repo_rpg")
    
    def load_repo_data(self) -> Dict[str, Any]:
        """Load and validate JSON data from file"""
        try:
            with open(self.repo_data_path, 'r', encoding='utf-8') as f:
                self.repo_data = json.load(f)
            self.repo_data["_repo_data_path"] = str(self.repo_data_path)
            self.repo_data["_repo_data_dir"] = str(self.repo_data_path.parent)
            self.logger.info(f"Successfully loaded JSON data from {self.repo_data_path}")
            # Validate required fields
            required_fields = ["repository_name", "Component"]
            missing_fields = [field for field in required_fields if field not in self.repo_data]
            if missing_fields:
                raise ValueError(f"Missing required fields: {missing_fields}")
            
        except Exception as e:
            self.logger.error(f"Failed to load JSON data from {self.repo_data_path}: {e}")
            raise

    def _is_rtl_repo(self) -> bool:
        rtl_metadata = self.repo_data.get("rtl_metadata", {}) if hasattr(self, "repo_data") else {}
        return rtl_metadata.get("mode") == "rtl_spec2repo"

    def _get_rtl_kg_service(self) -> Optional[RTLKgService]:
        if not self._is_rtl_repo():
            return None
        if self.rtl_kg_service is None:
            self.rtl_kg_service = RTLKgService(
                repo_path=self.repo_path,
                checkpoint_manager=self.checkpoint_manager,
                repo_data=self.repo_data,
                config=self.rtl_kg_config,
                logger=self.logger,
            )
        return self.rtl_kg_service

    def _should_preserve_rtl_blueprint(self) -> bool:
        rtl_metadata = self.repo_data.get("rtl_metadata", {}) if hasattr(self, "repo_data") else {}
        return self._is_rtl_repo() and bool(rtl_metadata.get("preserve_repo_blueprint", False))

    def _get_rtl_file_feature_map(self) -> Dict[str, List[str]]:
        rtl_metadata = self.repo_data.get("rtl_metadata", {})
        file_specs = rtl_metadata.get("file_specs", []) or []
        files = rtl_metadata.get("files", {}) or {}

        file_feature_map: Dict[str, List[str]] = {}
        all_paths = sorted(set(files.keys()) | {str(item.get("file_path", "")).strip() for item in file_specs if isinstance(item, dict)})
        file_spec_by_path = {
            str(item.get("file_path", "")).strip(): item
            for item in file_specs
            if isinstance(item, dict) and str(item.get("file_path", "")).strip()
        }

        for file_path in all_paths:
            item = file_spec_by_path.get(file_path)
            if isinstance(item, dict):
                feature_paths = self._build_feature_paths_for_file_spec(item)
            else:
                feature_paths = self._build_fallback_feature_paths(
                    bucket_name="root_files",
                    file_path=file_path,
                    description=str(files.get(file_path, "")).strip(),
                )
            file_feature_map[file_path] = sorted(set(feature_paths))

        return file_feature_map

    def _build_feature_paths_for_file_spec(
        self,
        file_spec: Dict[str, Any],
    ) -> List[str]:
        bucket_name = str(file_spec.get("bucket", "root_files")).strip() or "root_files"
        file_label = self._rtl_file_label(str(file_spec.get("file_path", "")).strip())
        responsibility = self._safe_feature_leaf(str(file_spec.get("responsibility", "")).strip() or file_label)

        paths = [f"{bucket_name}/files/{file_label}/responsibility/{responsibility}"]
        for branch, key in (
            ("requirements", "related_req_ids"),
            ("tests", "related_test_ids"),
            ("properties", "related_prop_ids"),
            ("nodes", "related_node_ids"),
            ("anchors", "related_code_anchor_ids"),
            ("hints", "related_hint_ids"),
        ):
            for value in sorted(set(file_spec.get(key, []) or [])):
                paths.append(f"{bucket_name}/files/{file_label}/{branch}/{self._safe_feature_leaf(str(value))}")
        return paths

    def _build_fallback_feature_paths(
        self,
        bucket_name: str,
        file_path: str,
        description: str,
    ) -> List[str]:
        file_label = self._rtl_file_label(file_path)
        leaf = self._safe_feature_leaf(description or PurePosixPath(file_path).name)
        return [
            f"{bucket_name}/files/{file_label}/responsibility/{leaf}",
        ]

    def _rtl_file_label(self, file_path: str) -> str:
        path = PurePosixPath(file_path)
        parts = list(path.parts)
        if parts[:2] == ["rtl", "modules"]:
            rel = parts[2:]
        elif parts[:2] == ["rtl", "pkg"]:
            rel = parts[2:]
        elif parts[:1] == ["tb"]:
            rel = parts[1:]
        elif parts[:1] == ["scripts"]:
            rel = parts[1:]
        else:
            rel = parts
        label = "__".join(rel) if rel else path.name
        return label or path.name

    def _safe_feature_leaf(self, text: str) -> str:
        text = re.sub(r"[\\/]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text or "file responsibility"
    
    def create_initial_rpg(self) -> RPG:
        """Create initial RPG from JSON repository data"""
        repo_name = self.repo_data.get("repository_name", "repo")
        repo_info = self.repo_data.get("repository_purpose", "")
        repo_cmpt = self.repo_data.get("Component", [])

        # 先建 RPG，再往里面塞节点
        rpg = RPG(
            repo_name=repo_name,
            repo_info=repo_info,
            excluded_files=[]
        )

        # --- 小工具: 统一生成 id ---
        def _new_id(name: str) -> str:
            return f"{name}_{rpg._rand8()}"

        # --- 小工具: 在 parent 下按名字找/建子节点 ---
        def _ensure_child(parent: Node, name: str, is_leaf: bool) -> Node:
            """
            is_leaf=True  -> 视作 feature 节点 (FUNCTION)
            is_leaf=False -> 视作中间分组节点 (DIRECTORY)
            """
            existing = rpg.find_child_by_name(parent.id, name)
            if existing:
                return existing

            node = Node(
                id=_new_id(name),
                name=name,
                # level 这里可以不指定，让后面 recalculate_levels_topdown 来统一收拾
                meta=None
            )
            rpg.add_node(node)
            rpg.add_edge(parent, node)
            return node

        # --- 递归: 把 refactored_subtree 变成节点树 ---
        def _build_from_subtree(parent: Node, subtree: Any):
            """
            subtree 的几种形态：
            - dict:      {"ChildA": {...}, "ChildB": [...]}
            - list:      ["feature1", "feature2"]
            """
            if isinstance(subtree, dict):
                for key, child in subtree.items():
                    if isinstance(child, list):
                        # key 是一层分组，list 里的每个元素是叶子 feature
                        group_node = _ensure_child(parent, key, is_leaf=False)
                        for feat in child:
                            if not feat:
                                continue
                            _ensure_child(group_node, str(feat), is_leaf=True)
                    elif isinstance(child, dict):
                        # 还是 dict -> 中间分组，继续下钻
                        node = _ensure_child(parent, key, is_leaf=False)
                        _build_from_subtree(node, child)
                    else:
                        # 其他类型直接当成 leaf
                        _ensure_child(parent, str(key), is_leaf=True)

            elif isinstance(subtree, list):
                # parent 下直接是一堆 feature
                for feat in subtree:
                    if not feat:
                        continue
                    _ensure_child(parent, str(feat), is_leaf=True)

            else:
                # 单一叶子
                _ensure_child(parent, str(subtree), is_leaf=True)

        # --- 主逻辑: 遍历所有 Component ---
        for component in repo_cmpt:
            cmpt_name = component.get("name", "") or "Component"
            re_tree = component.get("refactored_subtree", {})

            if not re_tree:
                continue

            # 这里：name 节点是 refactored_subtree 的父节点
            # -> 作为 repo 的直接子节点，level=1
            cmpt_node = rpg.find_child_by_name(rpg.repo_node.id, cmpt_name)
            if not cmpt_node:
                cmpt_node = Node(
                    id=_new_id(cmpt_name),
                    name=cmpt_name,
                    level=1,
                    meta=NodeMetaData(
                        type_name=NodeType.DIRECTORY,
                        path=None
                    )
                )
                rpg.add_node(cmpt_node)
                rpg.add_edge(rpg.repo_node, cmpt_node)

            # 把整个 refactored_subtree 都挂到这个 name 节点下面
            _build_from_subtree(cmpt_node, re_tree)

        # 统一按“自顶向下”规则重算 level 和 node_type
        rpg.recalculate_levels_topdown()

        self.logger.info(f"Created initial RPG for repository: {repo_name}")
        return rpg
    
    def build_skeleton(
        self,
        rpg: RPG
    ) -> Tuple[RepoSkeleton, RPG]:
        
        self.logger.info("=== Building Repository Skeleton ===")
        skeleton_designer = FileDesigner(
            file_map={},
            llm_config=self.llm_cfg,
            config_path=self.skeleton_cfg,
            rpg=rpg
        )

        if self._should_preserve_rtl_blueprint():
            self.logger.info("Using RTL seeded skeleton path to preserve repository blueprint")
            rtl_metadata = self.repo_data.get("rtl_metadata", {})
            file_feature_map = self._get_rtl_file_feature_map()
            file_content_map = {
                file_path: ""
                for file_path in (rtl_metadata.get("files", {}) or {}).keys()
            }
            skeleton, updated_rpg, results = skeleton_designer.build_seeded_skeleton(
                file_feature_map=file_feature_map,
                file_content_map=file_content_map,
            )
            skeleton.save_json(self.skeleton_result_path)
            with open(self.skeleton_agent_result_path, 'w') as f:
                json.dump(results, f, indent=4)
        else:
            skeleton, updated_rpg, results = skeleton_designer.run(
                skeleton_result_path=self.skeleton_result_path,
                agent_result_path=self.skeleton_agent_result_path
            )
        
        if not results.get("success", False):
            self.logger.error("Skeleton generation failed")
            raise Exception("Failed to generate repository skeleton")
        
        self.logger.info(f"Successfully built skeleton with {len(skeleton.path_to_node)} nodes")
        skeleton.write_to_workspace(str(self.repo_path))

        rtl_kg_service = self._get_rtl_kg_service()
        if rtl_kg_service and rtl_kg_service.is_enabled():
            self.logger.info("Syncing RTL knowledge graph after skeleton materialization")
            rtl_kg_service.sync_plan_snapshot(stage="post_skeleton")
        
        with open(self.global_rpg_path, 'w') as f:
            json.dump(updated_rpg.to_dict(), f, indent=4)
        return skeleton, updated_rpg
    
    
    def build_graph(
        self,
        skeleton: RepoSkeleton,
        rpg: RPG
    ) -> Tuple[RPG, Dict[str, Any]]:
        """Build repository graph using GraphDesigner"""
        self.logger.info("=== Building Repository Graph ===")
        from .func_design import FuncDesigner
        graph_designer = FuncDesigner(
            repo_skeleton=skeleton,
            llm_config=self.llm_cfg,
            repo_rpg=rpg,
            repo_data=self.repo_data,
            kg_service=self._get_rtl_kg_service(),
            config_path=str(self.graph_cfg),
            logger=self.logger
        )
        
        final_skeleton, final_rpg, graph_results = graph_designer.run(
            result_path=self.graph_result_path
        )
        
        if not graph_results.get("success", False):
            self.logger.error("Graph generation failed")
            raise Exception("Failed to generate repository graph")
        
        self.logger.info(f"Successfully built graph with {len(final_rpg.nodes)} nodes and {len(final_rpg.edges)} edges")
        final_skeleton.write_to_workspace(str(self.repo_path))

        rtl_kg_service = self._get_rtl_kg_service()
        if rtl_kg_service and rtl_kg_service.is_enabled():
            self.logger.info("Refreshing RTL knowledge graph after interface graph build")
            rtl_kg_service.refresh_repo_files(stage="post_graph")
        
        with open(self.global_rpg_path, 'w') as f:
            json.dump(final_rpg.to_dict(), f, indent=4)

        return final_skeleton, final_rpg, graph_results

    def plan_all_tasks(self, rpg, graph_data):    
        from .plan_tasks import TaskPlanner
        planner = TaskPlanner(
            rpg=rpg,
            llm_cfg=self.llm_cfg,
            graph_data=graph_data,
            repo_data=self.repo_data,
            logger=self.logger
        )
        
        task_batches = planner.plan_all_batches(
            result_path=self.tasks_result_path
        )
        
        return task_batches
    
    
    def run(self):
        state_dict = {}
        if not self.state_file.exists():
            with open(self.state_file, 'w') as f:
                json.dump({}, f, indent=4)
        else:
            with open(self.state_file, 'r') as f:
                state_dict = json.load(f)

        state_dict = self._repair_incomplete_state(state_dict)
        
        self.load_repo_data()
        if not state_dict.get("build_skeleton", False):
            rpg = self.create_initial_rpg()
            skeleton, rpg = self.build_skeleton(
                rpg
            )
            state_dict["build_skeleton"] = True
            with open(self.state_file, 'w') as f:
                json.dump(state_dict, f, indent=4)
        else:
            with open(self.skeleton_result_path, 'r') as f:
                skeleton_dict = json.load(f)
            with open(self.global_rpg_path, 'r') as f:
                rpg_dict = json.load(f)
            skeleton = RepoSkeleton.from_dict(skeleton_dict)
            rpg = RPG.from_dict(rpg_dict)
    
        if not state_dict.get("build_function", False):
            skeleton, rpg, _ = self.build_graph(
                skeleton=skeleton,
                rpg=rpg
            )
            state_dict["build_function"] = True
            with open(self.state_file, 'w') as f:
                json.dump(state_dict, f, indent=4)
        else:
            with open(self.skeleton_result_path, 'r') as f:
                skeleton_dict = json.load(f)
            with open(self.global_rpg_path, 'r') as f:
                rpg_dict = json.load(f)
            skeleton = RepoSkeleton.from_dict(skeleton_dict)
            rpg = RPG.from_dict(rpg_dict)
        
        with open(self.graph_result_path, 'r') as f:
            graph_data = json.load(f)
        
        if not state_dict.get("plan_tasks", False):
            plan_batches = self.plan_all_tasks(
                rpg,
                graph_data
            )
            state_dict["plan_tasks"] = True
            with open(self.state_file, 'w') as f:
                json.dump(state_dict, f, indent=4)
        else:
            with open(self.tasks_result_path, 'r') as f:
                tasks_data = json.load(f)
            
            # Extract flattened list of task batches using shared utility function
            from zerorepo.utils.task_loader import load_batches_from_dict
            
            planned_batches_dict = tasks_data.get("planned_batches_dict", {})
            plan_batches = load_batches_from_dict(planned_batches_dict, graph_data, self.logger)

        # 设计阶段完成，返回任务批次供代码生成阶段使用
        self.logger.info(f"Design phase completed. Generated {len(plan_batches)} task batches.")
        return plan_batches, skeleton, rpg, graph_data

    def _repair_incomplete_state(self, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        repaired = dict(state_dict or {})

        stage_requirements = {
            "build_skeleton": [self.skeleton_result_path, self.global_rpg_path],
            "build_function": [self.skeleton_result_path, self.global_rpg_path, self.graph_result_path],
            "plan_tasks": [self.tasks_result_path, self.graph_result_path, self.global_rpg_path],
        }

        updated = False
        for stage, required_paths in stage_requirements.items():
            if not repaired.get(stage, False):
                continue
            missing = [str(path) for path in required_paths if not path.exists()]
            if missing:
                self.logger.warning(
                    "Checkpoint state marked '%s' as complete, but artifacts are missing: %s. "
                    "Resetting this and downstream stages.",
                    stage,
                    missing,
                )
                reset = False
                for reset_stage in ("build_skeleton", "build_function", "plan_tasks"):
                    if reset_stage == stage:
                        reset = True
                    if reset:
                        if repaired.get(reset_stage, False):
                            repaired[reset_stage] = False
                            updated = True
                break

        if updated:
            with open(self.state_file, 'w') as f:
                json.dump(repaired, f, indent=4)
        return repaired
        
    
        
        
        
