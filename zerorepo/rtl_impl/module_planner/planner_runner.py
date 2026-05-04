from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from zerorepo.rtl_impl.debug_agent.adapters import (
    build_debug_contract_json,
    build_module_spec_text,
    debug_openai_config_from_planner_config,
)
from zerorepo.rtl_impl.debug_agent.debug_runner import (
    ModuleDebugRunner,
    RtlDebugConfig,
    module_debug_result_to_dict,
)
from zerorepo.rtl_impl.debug_agent.sim_reviewer import check_syntax

from .agents import (
    Stage1Agent,
    Stage2Agent,
    Stage3Agent,
    Stage4ModulePlanAgent,
    Stage4SpecBlocksAgent,
    Stage5Agent,
    Stage6MergeAgent,
)
from .agents.base import model_dump, validate_model
from .interfaces import (
    NullPlanningArtifactSink,
    NullPlanningContextProvider,
    PlanningArtifactSink,
    PlanningContextProvider,
)
from .module_organizer import build_module_organized_artifact
from .schemas import (
    ModuleCodegenRecord,
    ModuleMergeRecord,
    ModuleOrganizationArtifact,
    ModulePlanArtifact,
    PlannerTaskInput,
    Stage1ContractsArtifact,
    Stage2RepoSkeletonArtifact,
    Stage3ModuleSkeletonArtifact,
    Stage4ModulePlansArtifact,
    Stage4SpecBlocksArtifact,
    Stage5CodegenArtifact,
    Stage6MergeArtifact,
)
from .utils import PlannerLLMClient, get_planner_logger


class PlannerRunner:
    CONTRACTS_FILENAME = "contracts.json"
    MODULES_FILENAME = "modules.json"
    REPO_SKELETON_FILENAME = "repo_skeleton.json"
    MODULE_SKELETONS_FILENAME = "module_skeletons.json"
    SPEC_BLOCKS_FILENAME = "spec_blocks.json"
    MODULE_PLANS_FILENAME = "module_plans.json"
    STAGE5_CODEGEN_FILENAME = "stage5_codegen.json"
    STAGE6_MERGE_FILENAME = "stage6_merge.json"
    MODULE_SKELETON_DOCS_DIRNAME = "module_skeleton_docs"
    MODULE_SKELETON_JSON_DIRNAME = "module_skeleton_json"
    MODULE_PLAN_JSON_DIRNAME = "module_plan_json"

    def __init__(
        self,
        output_root: str | Path = "outputs",
        llm_config: Optional[Any] = None,
        llm_backend: Optional[Any] = None,
        context_provider: Optional[PlanningContextProvider] = None,
        artifact_sink: Optional[PlanningArtifactSink] = None,
        logger=None,
        debug_config: Optional[RtlDebugConfig] = None,
    ):
        self.output_root = Path(output_root)
        self.logger = logger or get_planner_logger("rtl_module_planner.runner")
        self.context_provider = context_provider or NullPlanningContextProvider()
        self.artifact_sink = artifact_sink or NullPlanningArtifactSink()
        self.llm_client = PlannerLLMClient(llm_config=llm_config, backend=llm_backend)
        self.stage1 = Stage1Agent(self.llm_client, self.context_provider, self.artifact_sink, self.logger)
        self.stage2 = Stage2Agent(self.llm_client, self.context_provider, self.artifact_sink, self.logger)
        self.stage3 = Stage3Agent(
            self.llm_client,
            self.context_provider,
            self.artifact_sink,
            self.logger,
            output_root=self.output_root,
        )
        self.stage4_spec_blocks = Stage4SpecBlocksAgent(
            self.llm_client,
            self.context_provider,
            self.artifact_sink,
            self.logger,
        )
        self.stage4_module_plans = Stage4ModulePlanAgent(
            self.llm_client,
            self.context_provider,
            self.artifact_sink,
            self.logger,
            output_root=self.output_root,
        )
        self.stage5 = Stage5Agent(
            self.llm_client,
            self.context_provider,
            self.artifact_sink,
            self.logger,
            output_root=self.output_root,
        )
        self.stage6 = Stage6MergeAgent(
            self.llm_client,
            self.context_provider,
            self.artifact_sink,
            self.logger,
            output_root=self.output_root,
        )
        if debug_config is None:
            debug_config = RtlDebugConfig.from_env()
            debug_config = RtlDebugConfig(
                enabled=debug_config.enabled,
                oracle_root=debug_config.oracle_root,
                max_trials=debug_config.max_trials,
                allow_failure=debug_config.allow_failure,
                enable_asserter=debug_config.enable_asserter,
                enable_boolean_proofer=debug_config.enable_boolean_proofer,
                toolchain_bin=debug_config.toolchain_bin,
                openai_config=debug_openai_config_from_planner_config(llm_config),
            )
        self.debug_runner = ModuleDebugRunner(
            config=debug_config,
            workspace_root=self.stage6.workspace_root,
            logger=self.logger,
        )

    def run(
        self,
        task_input: PlannerTaskInput | Dict[str, Any],
        resume: bool = False,
        end_stage: str = "stage1",
    ) -> Stage1ContractsArtifact | Stage2RepoSkeletonArtifact | Stage3ModuleSkeletonArtifact | Stage4ModulePlansArtifact | Stage5CodegenArtifact | Stage6MergeArtifact:
        if end_stage not in {"stage1", "stage2", "stage3", "stage4", "stage5", "stage6"}:
            raise NotImplementedError("module_planner currently supports end_stage in {'stage1', 'stage2', 'stage3', 'stage4', 'stage5', 'stage6'} only.")

        task = task_input if isinstance(task_input, PlannerTaskInput) else validate_model(PlannerTaskInput, task_input)
        artifacts: Dict[str, Any] = {}

        existing_artifact = None
        if resume:
            existing_artifact = self._read_contracts_if_valid()
            if existing_artifact is not None and not self.stage1.validate_quality(existing_artifact, task, {}):
                self.logger.info(
                    "[rtl_module_planner] Resume reused stage1 contracts artifact from %s",
                    self._contracts_path(),
                )
                artifacts["stage1"] = existing_artifact
            elif existing_artifact is not None:
                self.logger.info(
                    "[rtl_module_planner] Resume ignored semantically invalid stage1 contracts artifact at %s",
                    self._contracts_path(),
                )

        artifact = self.stage1.run_incremental(
            task,
            artifacts,
            persist_callback=self._write_payload,
        )
        modules_artifact = build_module_organized_artifact(artifact)
        self._write_modules_payload(model_dump(modules_artifact))
        if end_stage == "stage1":
            return artifact

        if resume:
            existing_repo_skeleton = self._read_repo_skeleton_if_valid()
            if existing_repo_skeleton is not None:
                self.logger.info(
                    "[rtl_module_planner] Resume reused stage2 repo skeleton artifact from %s",
                    self._repo_skeleton_path(),
                )
                if end_stage == "stage2":
                    return existing_repo_skeleton
                repo_skeleton = existing_repo_skeleton
            else:
                repo_skeleton = self.stage2.run(
                    task,
                    {"modules": modules_artifact},
                )
                self._write_repo_skeleton_payload(model_dump(repo_skeleton))
        else:
            repo_skeleton = self.stage2.run(
                task,
                {"modules": modules_artifact},
            )
            self._write_repo_skeleton_payload(model_dump(repo_skeleton))

        if end_stage == "stage2":
            return repo_skeleton

        if resume:
            existing_stage3 = self._read_module_skeletons_if_valid()
            if existing_stage3 is not None:
                self.logger.info(
                    "[rtl_module_planner] Resume continuing stage3 module skeleton artifact from %s",
                    self._module_skeletons_path(),
                )
                artifacts["stage3"] = existing_stage3

        module_skeletons = self.stage3.run_incremental(
            task,
            {
                "modules": modules_artifact,
                "stage2": repo_skeleton,
                **({"stage3": artifacts["stage3"]} if "stage3" in artifacts else {}),
            },
            persist_callback=self._write_stage3_outputs,
        )
        if end_stage == "stage3":
            return module_skeletons

        spec_stage_inputs = {
            "modules": modules_artifact,
            "stage2": repo_skeleton,
            "stage3": module_skeletons,
        }
        if resume:
            existing_spec_blocks = self._read_spec_blocks_if_valid(task, spec_stage_inputs)
            if existing_spec_blocks is not None:
                self.logger.info(
                    "[rtl_module_planner] Resume reused stage4 spec blocks artifact from %s",
                    self._spec_blocks_path(),
                )
                spec_blocks = existing_spec_blocks
            else:
                spec_blocks = self.stage4_spec_blocks.run(task, spec_stage_inputs)
                self._write_spec_blocks_payload(model_dump(spec_blocks))
        else:
            spec_blocks = self.stage4_spec_blocks.run(task, spec_stage_inputs)
            self._write_spec_blocks_payload(model_dump(spec_blocks))

        module_plan_stage_inputs = {
            "modules": modules_artifact,
            "stage2": repo_skeleton,
            "stage3": module_skeletons,
            "spec_blocks": spec_blocks,
        }
        if resume:
            existing_module_plans = self._read_module_plans_if_valid(task, module_plan_stage_inputs)
            if existing_module_plans is not None:
                self.logger.info(
                    "[rtl_module_planner] Resume reused stage4 module plans artifact from %s",
                    self._module_plans_path(),
                )
                module_plans = existing_module_plans
            else:
                module_plans = self.stage4_module_plans.run_incremental(
                    task,
                    module_plan_stage_inputs,
                    persist_callback=self._write_stage4_module_plan_outputs,
                )
        else:
            module_plans = self.stage4_module_plans.run_incremental(
                task,
                module_plan_stage_inputs,
                persist_callback=self._write_stage4_module_plan_outputs,
            )
        if end_stage == "stage4":
            return module_plans

        codegen_stage_inputs = {
            "stage1": artifact,
            "modules": modules_artifact,
            "stage2": repo_skeleton,
            "stage3": module_skeletons,
            "stage4": module_plans,
            "spec_blocks": spec_blocks,
        }
        if end_stage == "stage5":
            return self.stage5.run_incremental(
                task,
                codegen_stage_inputs,
                persist_callback=self._write_stage5_codegen_outputs,
            )

        return self._run_stage6_per_module(task, codegen_stage_inputs, spec_blocks)

    def _read_contracts_if_valid(self) -> Any | None:
        path = self._contracts_path()
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            return validate_model(Stage1ContractsArtifact, payload)
        except Exception as exc:
            self.logger.warning(
                "[rtl_module_planner] Resume ignored invalid stage1 contracts artifact at %s: %s",
                path,
                exc,
            )
            return None

    def _write_payload(self, payload: Dict[str, Any]) -> Path:
        directory = self.output_root
        directory.mkdir(parents=True, exist_ok=True)
        path = self._contracts_path()
        tmp_path = path.with_name(f"{path.name}.tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(self._compact_stage1_payload(payload), f, indent=2, ensure_ascii=False)
        tmp_path.replace(path)
        self.logger.info("[rtl_module_planner] Wrote stage1 contracts artifact to %s", path)
        return path

    def _write_modules_payload(self, payload: Dict[str, Any]) -> Path:
        directory = self.output_root
        directory.mkdir(parents=True, exist_ok=True)
        path = self._modules_path()
        tmp_path = path.with_name(f"{path.name}.tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(self._compact_stage1_payload(payload), f, indent=2, ensure_ascii=False)
        tmp_path.replace(path)
        self.logger.info("[rtl_module_planner] Wrote module-organized artifact to %s", path)
        return path

    def _read_repo_skeleton_if_valid(self) -> Any | None:
        path = self._repo_skeleton_path()
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            return validate_model(Stage2RepoSkeletonArtifact, payload)
        except Exception as exc:
            self.logger.warning(
                "[rtl_module_planner] Resume ignored invalid repo skeleton artifact at %s: %s",
                path,
                exc,
            )
            return None

    def _write_repo_skeleton_payload(self, payload: Dict[str, Any]) -> Path:
        directory = self.output_root
        directory.mkdir(parents=True, exist_ok=True)
        path = self._repo_skeleton_path()
        tmp_path = path.with_name(f"{path.name}.tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(self._compact_repo_skeleton_payload(payload), f, indent=2, ensure_ascii=False)
        tmp_path.replace(path)
        self.logger.info("[rtl_module_planner] Wrote repo skeleton artifact to %s", path)
        return path

    def _read_module_skeletons_if_valid(self) -> Any | None:
        path = self._module_skeletons_path()
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            return validate_model(Stage3ModuleSkeletonArtifact, payload)
        except Exception as exc:
            self.logger.warning(
                "[rtl_module_planner] Resume ignored invalid module skeleton artifact at %s: %s",
                path,
                exc,
            )
            return None

    def _read_spec_blocks_if_valid(self, task: PlannerTaskInput, partial_artifacts: Dict[str, Any]) -> Any | None:
        path = self._spec_blocks_path()
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            artifact = validate_model(Stage4SpecBlocksArtifact, payload)
            quality_errors = self.stage4_spec_blocks.validate_quality(artifact, task, partial_artifacts)
            if quality_errors:
                raise ValueError(quality_errors)
            return artifact
        except Exception as exc:
            self.logger.warning(
                "[rtl_module_planner] Resume ignored invalid stage4 spec blocks artifact at %s: %s",
                path,
                exc,
            )
            return None

    def _read_module_plans_if_valid(self, task: PlannerTaskInput, partial_artifacts: Dict[str, Any]) -> Any | None:
        path = self._module_plans_path()
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            artifact = validate_model(Stage4ModulePlansArtifact, payload)
            quality_errors = self.stage4_module_plans.validate_quality(artifact, task, partial_artifacts)
            if quality_errors:
                raise ValueError(quality_errors)
            for record in artifact.module_plan_files:
                plan_path = self.output_root / record.plan_file
                if not plan_path.exists():
                    raise FileNotFoundError(f"missing module plan sidecar: {plan_path}")
                with open(plan_path, "r", encoding="utf-8") as f:
                    plan_payload = json.load(f)
                plan = validate_model(ModulePlanArtifact, plan_payload)
                if plan.module != record.module:
                    raise ValueError(f"{plan_path}: module must be {record.module}, got {plan.module}")
            return artifact
        except Exception as exc:
            self.logger.warning(
                "[rtl_module_planner] Resume ignored invalid stage4 module plans artifact at %s: %s",
                path,
                exc,
            )
            return None

    def _write_module_skeletons_payload(self, payload: Dict[str, Any]) -> Path:
        directory = self.output_root
        directory.mkdir(parents=True, exist_ok=True)
        path = self._module_skeletons_path()
        tmp_path = path.with_name(f"{path.name}.tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        tmp_path.replace(path)
        self.logger.info("[rtl_module_planner] Wrote stage3 module skeleton artifact to %s", path)
        return path

    def _write_spec_blocks_payload(self, payload: Dict[str, Any]) -> Path:
        directory = self.output_root
        directory.mkdir(parents=True, exist_ok=True)
        path = self._spec_blocks_path()
        tmp_path = path.with_name(f"{path.name}.tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        tmp_path.replace(path)
        self.logger.info("[rtl_module_planner] Wrote stage4 spec blocks artifact to %s", path)
        return path

    def _write_module_plans_payload(self, payload: Dict[str, Any]) -> Path:
        directory = self.output_root
        directory.mkdir(parents=True, exist_ok=True)
        path = self._module_plans_path()
        tmp_path = path.with_name(f"{path.name}.tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        tmp_path.replace(path)
        self.logger.info("[rtl_module_planner] Wrote stage4 module plans artifact to %s", path)
        return path

    def _write_stage5_codegen_payload(self, payload: Dict[str, Any]) -> Path:
        directory = self.output_root
        directory.mkdir(parents=True, exist_ok=True)
        path = self._stage5_codegen_path()
        tmp_path = path.with_name(f"{path.name}.tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        tmp_path.replace(path)
        self.logger.info("[rtl_module_planner] Wrote stage5 codegen artifact to %s", path)
        return path

    def _write_stage6_merge_payload(self, payload: Dict[str, Any]) -> Path:
        directory = self.output_root
        directory.mkdir(parents=True, exist_ok=True)
        path = self._stage6_merge_path()
        tmp_path = path.with_name(f"{path.name}.tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        tmp_path.replace(path)
        self.logger.info("[rtl_module_planner] Wrote stage6 merge artifact to %s", path)
        return path

    def _write_stage4_module_plan_outputs(self, payload: Dict[str, Any]) -> Path:
        module_name = payload.get("module")
        if module_name:
            self._write_json_payload(payload["plan_payload"], self.output_root / payload["plan_file"])
            self.logger.info("[rtl_module_planner] Wrote stage4 module plan sidecar for %s", module_name)
        return self._write_module_plans_payload(payload["manifest"])

    def _write_stage5_codegen_outputs(self, payload: Dict[str, Any]) -> Path:
        return self._write_stage5_codegen_payload(payload["manifest"])

    def _write_stage6_merge_outputs(self, payload: Dict[str, Any]) -> Path:
        return self._write_stage6_merge_payload(payload["manifest"])

    def _write_stage3_outputs(self, payload: Dict[str, Any]) -> Path:
        module_name = payload.get("module")
        if module_name:
            doc_file = payload["doc_file"]
            export_file = payload["export_file"]
            self._write_text_payload(payload["doc_text"], self.output_root / doc_file)
            self._write_json_payload(payload["export_payload"], self.output_root / export_file)
            self.logger.info(
                "[rtl_module_planner] Wrote stage3 module doc/json sidecars for %s",
                module_name,
            )
        return self._write_module_skeletons_payload(payload["manifest"])

    def _write_json_payload(self, payload: Dict[str, Any], path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_name(f"{path.name}.tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        tmp_path.replace(path)
        return path

    def _write_text_payload(self, payload: str, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_name(f"{path.name}.tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(payload)
        tmp_path.replace(path)
        return path

    def _contracts_path(self) -> Path:
        return self.output_root / self.CONTRACTS_FILENAME

    def _modules_path(self) -> Path:
        return self.output_root / self.MODULES_FILENAME

    def _repo_skeleton_path(self) -> Path:
        return self.output_root / self.REPO_SKELETON_FILENAME

    def _module_skeletons_path(self) -> Path:
        return self.output_root / self.MODULE_SKELETONS_FILENAME

    def _spec_blocks_path(self) -> Path:
        return self.output_root / self.SPEC_BLOCKS_FILENAME

    def _module_plans_path(self) -> Path:
        return self.output_root / self.MODULE_PLANS_FILENAME

    def _stage5_codegen_path(self) -> Path:
        return self.output_root / self.STAGE5_CODEGEN_FILENAME

    def _stage6_merge_path(self) -> Path:
        return self.output_root / self.STAGE6_MERGE_FILENAME

    def _run_stage6_per_module(
        self,
        task: PlannerTaskInput,
        codegen_stage_inputs: Dict[str, Any],
        spec_blocks: Stage4SpecBlocksArtifact,
    ) -> Stage6MergeArtifact:
        stage5_records = []
        stage6_records = []
        debug_records = []
        for module_name in spec_blocks.module_order:
            stage5_record = self._reuse_stage5_fragment_if_valid(module_name, codegen_stage_inputs)
            if stage5_record is not None:
                self.logger.info(
                    "[rtl_module_planner] Resume reused stage5 fragments for module %s from %s",
                    module_name,
                    stage5_record.workspace_file,
                )
            else:
                self.logger.info("[rtl_module_planner] Stage5 generating fragments for module %s", module_name)
                stage5_record = self.stage5.run_module(task, codegen_stage_inputs, module_name)
            stage5_records.append(stage5_record)
            stage6_record = self._reuse_stage6_merge_if_valid(module_name, stage5_record)
            if stage6_record is not None:
                self.logger.info(
                    "[rtl_module_planner] Resume reused stage6 merged RTL for module %s from %s",
                    module_name,
                    stage6_record.merged_file,
                )
            else:
                self.logger.info("[rtl_module_planner] Stage6 merging module %s immediately after stage5", module_name)
                stage6_record = self.stage6.run_module(
                    task,
                    codegen_stage_inputs,
                    module_name,
                    stage5_record,
                )
            stage6_records.append(stage6_record)
            self.logger.info("[rtl_module_planner] Debug checking module %s after stage6", module_name)
            module_spec_text = build_module_spec_text(module_name=module_name, spec_blocks=spec_blocks)
            debug_result = self.debug_runner.run_module(
                module_name=module_name,
                merged_file=stage6_record.merged_file,
                task=task,
                spec_text=module_spec_text,
                contract_json=build_debug_contract_json(
                    module_name=module_name,
                    stage1_contracts=codegen_stage_inputs.get("stage1"),
                    spec_text=module_spec_text,
                ),
            )
            debug_records.append(debug_result)
            self.logger.info(
                "[rtl_module_planner] Debug result for %s: %s%s",
                module_name,
                debug_result.status,
                f" ({debug_result.reason})" if debug_result.reason else "",
            )
            if debug_result.status in {"fail", "error"} and not self.debug_runner.config.allow_failure:
                raise RuntimeError(f"RTL debug failed for {module_name}: {debug_result.reason}")

        stage5_artifact = Stage5CodegenArtifact(
            task_id=task.task_id,
            module_order=list(spec_blocks.module_order),
            module_files=stage5_records,
        )
        stage5_quality_errors = self.stage5.validate_quality(stage5_artifact, task, codegen_stage_inputs)
        if stage5_quality_errors:
            raise ValueError(f"stage5_codegen output failed quality checks: {stage5_quality_errors}")
        self._write_stage5_codegen_payload(model_dump(stage5_artifact))
        self.artifact_sink.record_stage_output(self.stage5.stage_name, stage5_artifact, task)

        stage6_artifact = Stage6MergeArtifact(
            task_id=task.task_id,
            module_order=list(spec_blocks.module_order),
            module_files=stage6_records,
            debug_files=[module_debug_result_to_dict(item) for item in debug_records],
        )
        stage6_quality_errors = self.stage6.validate_quality(stage6_artifact, task, codegen_stage_inputs)
        if stage6_quality_errors:
            raise ValueError(f"stage6_merge output failed quality checks: {stage6_quality_errors}")
        self._write_stage6_merge_payload(model_dump(stage6_artifact))
        self.artifact_sink.record_stage_output(self.stage6.stage_name, stage6_artifact, task)
        return stage6_artifact

    def _reuse_stage5_fragment_if_valid(
        self,
        module_name: str,
        codegen_stage_inputs: Dict[str, Any],
    ):
        fragment_file = self.stage5._workspace_file(module_name)
        if not fragment_file.exists():
            return None
        text = fragment_file.read_text(encoding="utf-8").replace("\r\n", "\n")
        if not text.strip():
            return None
        if "STAGE5_SUBTASK_BEGIN" not in text or "STAGE5_SUBTASK_END" not in text:
            return None

        stage4 = codegen_stage_inputs["stage4"]
        plan_record = next((item for item in stage4.module_plan_files if item.module == module_name), None)
        if plan_record is None:
            return None
        plan_path = self.output_root / plan_record.plan_file
        if not plan_path.exists():
            return None
        with open(plan_path, "r", encoding="utf-8") as f:
            plan = validate_model(ModulePlanArtifact, json.load(f))
        expected_subtask_ids = [item.id for item in plan.subtasks]
        missing_markers = [
            subtask_id
            for subtask_id in expected_subtask_ids
            if f"STAGE5_SUBTASK_BEGIN {subtask_id}" not in text
            or f"STAGE5_SUBTASK_END {subtask_id}" not in text
        ]
        if missing_markers:
            self.logger.info(
                "[rtl_module_planner] Existing fragments for %s are incomplete; missing markers: %s",
                module_name,
                missing_markers,
            )
            return None

        return ModuleCodegenRecord(
            module=module_name,
            workspace_file=str(fragment_file),
            completed_subtasks=expected_subtask_ids,
        )

    def _reuse_stage6_merge_if_valid(
        self,
        module_name: str,
        stage5_record: ModuleCodegenRecord,
    ):
        fragment_file = Path(stage5_record.workspace_file)
        merged_file = self.stage6._merged_file(module_name)
        if not fragment_file.exists() or not merged_file.exists():
            return None
        code = merged_file.read_text(encoding="utf-8").replace("\r\n", "\n")
        errors = self.stage6._validate_raw_module(code, module_name)
        if errors:
            self.logger.info(
                "[rtl_module_planner] Existing stage6 merge for %s is invalid; regenerating: %s",
                module_name,
                errors,
            )
            return None
        self.stage6._ensure_toolchain_path()
        syntax_ok, syntax_output = check_syntax(str(merged_file))
        if not syntax_ok:
            self.logger.info(
                "[rtl_module_planner] Existing stage6 merge for %s fails Verilator syntax; regenerating: %s",
                module_name,
                self.stage6._summarize_syntax_output(syntax_output),
            )
            return None
        return ModuleMergeRecord(
            module=module_name,
            fragment_file=str(fragment_file),
            merged_file=str(merged_file),
        )

    def _compact_stage1_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._drop_text_grounding(payload)

    def _drop_text_grounding(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: self._drop_text_grounding(item)
                for key, item in value.items()
                if key != "text_grounding"
            }
        if isinstance(value, list):
            return [self._drop_text_grounding(item) for item in value]
        return value

    def _compact_repo_skeleton_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        compact = dict(payload)
        if compact.get("module_order") == []:
            compact.pop("module_order", None)
        return compact
