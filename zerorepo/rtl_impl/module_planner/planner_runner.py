from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Literal, Optional

from zerorepo.rtl_impl.debug_agent.adapters import (
    build_debug_contract_json,
    build_module_spec_text,
    debug_openai_config_from_planner_config,
)
from zerorepo.rtl_impl.debug_agent.debug_runner import (
    ModuleDebugResult,
    ModuleDebugRunner,
    RtlDebugConfig,
    module_debug_result_to_dict,
)
from zerorepo.rtl_impl.debug_agent.system_debug_runner import (
    SystemDebugRunner,
    system_debug_result_to_dict,
)
from zerorepo.rtl_impl.kg_agent import ModuleResultWriter, PlanningContextRetriever, PlanningGraphWriter

from .agents import (
    Stage1Agent,
    Stage1TemporalAgent,
    Stage2Agent,
    Stage2TemporalContractAgent,
    Stage3Agent,
    Stage3TimingBindingAgent,
    Stage4ModulePlanAgent,
    Stage4SpecBlocksAgent,
    Stage5Agent,
    Stage6MergeAgent,
)
from .agents.base import StageGenerationError, model_dump, validate_model
from .interfaces import (
    NullPlanningArtifactSink,
    NullPlanningContextProvider,
    PlanningArtifactSink,
    PlanningContextProvider,
)
from .module_organizer import (
    build_module_organized_artifact_from_repo_skeleton,
    build_stage2_planning_input,
)
from .schemas import (
    ArchitectureTimingContractArtifact,
    GlobalTemporalFactsArtifact,
    ModuleCodegenRecord,
    ModuleMergeRecord,
    ModuleOrganizationArtifact,
    ModulePlanArtifact,
    ModuleSkeletonExport,
    ModuleTimingBindingArtifact,
    ModuleTimingBindingRecord,
    PlannerTaskInput,
    Stage1ContractsArtifact,
    Stage2DecompositionArtifact,
    Stage2RepoSkeletonArtifact,
    Stage3ModuleSkeletonArtifact,
    Stage3TimingBindingsArtifact,
    Stage4ModulePlansArtifact,
    Stage4SpecBlocksArtifact,
    Stage5CodegenArtifact,
    Stage6MergeArtifact,
    SystemDebugRecord,
    TimingBindingCheckArtifact,
)
from .utils import PlannerLLMClient, canonical_fingerprint, check_temporal_bindings, get_planner_logger
from .utils.artifact_store import atomic_write_json
from .utils.local_repair import REPAIR_POLICY_VERSION, fingerprint
from .utils import resolve_module_spec_text


def _check_single_file_syntax(rtl_path: str, top_module: str | None = None) -> tuple:
    """Run Verilator --lint-only on a single file, without globbing other .v files."""
    import os as _os
    from zerorepo.rtl_impl.debug_agent.bash_tools import CommandResult, run_bash_command

    # Defines-only files (sd_defines.v) have no module declaration — skip check
    try:
        content = Path(rtl_path).read_text(encoding="utf-8")
    except Exception:
        content = ""
    if not re.search(r"\bmodule\s+\w+", content):
        return True, "{}"  # not a synthesizable module, skip syntax check

    rtl_dir = _os.path.dirname(_os.path.abspath(rtl_path))
    top_flag = f"--top-module {top_module} " if top_module else ""
    cmd = f"verilator --lint-only --sv --timing -Wall -Wno-fatal --assert {top_flag}{rtl_path}"
    is_pass, sim_output = run_bash_command(cmd, timeout=60, cwd=rtl_dir)
    obj = CommandResult.model_validate_json(sim_output)
    stdout = obj.stdout or ""
    stderr = obj.stderr or ""
    # Only fail on %Error, not %Warning
    is_pass = bool(is_pass) and "%Error" not in stdout and "%Error" not in stderr
    return is_pass, sim_output


class PlannerRunner:
    CONTRACTS_FILENAME = "contracts.json"
    MODULES_FILENAME = "modules.json"
    REPO_SKELETON_FILENAME = "repo_skeleton.json"
    STAGE2_DECOMPOSITION_FILENAME = "stage2_decomposition.json"
    MODULE_SKELETONS_FILENAME = "module_skeletons.json"
    SPEC_BLOCKS_FILENAME = "spec_blocks.json"
    MODULE_PLANS_FILENAME = "module_plans.json"
    STAGE5_CODEGEN_FILENAME = "stage5_codegen.json"
    STAGE6_MERGE_FILENAME = "stage6_merge.json"
    GLOBAL_TEMPORAL_FACTS_FILENAME = "global_temporal_facts.json"
    ARCHITECTURE_TIMING_CONTRACT_FILENAME = "architecture_timing_contract.json"
    MODULE_TIMING_BINDINGS_FILENAME = "module_timing_bindings.json"
    TIMING_BINDING_CHECK_FILENAME = "timing_binding_check.json"
    TIMING_BINDING_CHECK_RULESET_VERSION = "stage3_5_refinement_v2"
    INTERFACE_PLANNING_POLICY_VERSION = "facts_top_interface_v1"
    PIPELINE_POLICY_VERSION = "stage2_multi_candidate_decomposition_v3"
    MODULE_SKELETON_DOCS_DIRNAME = "module_skeleton_docs"
    MODULE_SKELETON_JSON_DIRNAME = "module_skeleton_json"
    MODULE_PLAN_JSON_DIRNAME = "module_plan_json"
    BLOCK_SPEC_RETRIEVAL_JSON_DIRNAME = "block_spec_retrieval_json"
    MODULE_TIMING_BINDING_JSON_DIRNAME = "module_timing_binding_json"

    def __init__(
        self,
        output_root: str | Path = "outputs",
        llm_config: Optional[Any] = None,
        llm_backend: Optional[Any] = None,
        context_provider: Optional[PlanningContextProvider] = None,
        artifact_sink: Optional[PlanningArtifactSink] = None,
        logger=None,
        debug_config: Optional[RtlDebugConfig] = None,
        kg_service: Optional[Any] = None,
        checkpoint_dir: Optional[str | Path] = None,
        temporal_planning_enabled: bool = False,
        temporal_failure_policy: Literal["strict", "degrade"] = "degrade",
        request_policy: dict | None = None,
        retrieval_limits: dict | None = None,
    ):
        self.output_root = Path(output_root)
        self.logger = logger or get_planner_logger("rtl_module_planner.runner")
        self.context_provider = context_provider or NullPlanningContextProvider()
        self.artifact_sink = artifact_sink or NullPlanningArtifactSink()
        self.llm_client = PlannerLLMClient(llm_config=llm_config, backend=llm_backend, request_policy=request_policy)
        self.kg_service = kg_service
        self.checkpoint_dir = Path(checkpoint_dir) if checkpoint_dir is not None else self._default_checkpoint_dir()
        self.planning_graph_writer = (
            PlanningGraphWriter(self.kg_service, self.output_root, self.logger)
            if self.kg_service is not None and self.kg_service.is_enabled()
            else None
        )
        self.planning_context_retriever = (
            PlanningContextRetriever(self.kg_service, self.output_root, self.logger)
            if self.planning_graph_writer is not None
            else None
        )
        requested_temporal_planning = bool(temporal_planning_enabled)
        self.temporal_planning_enabled = False
        if temporal_failure_policy not in {"strict", "degrade"}:
            raise ValueError("temporal_failure_policy must be `strict` or `degrade`")
        self.temporal_failure_policy = temporal_failure_policy
        if requested_temporal_planning:
            self.logger.warning(
                "[rtl_module_planner] temporal_planning_enabled is deprecated and ignored; "
                "the runner uses the Stage1 -> Stage2 -> Stage3 -> Stage4 -> Stage5 -> Stage6 pipeline"
            )
        if debug_config is None:
            debug_config = RtlDebugConfig.from_env()
            debug_config = RtlDebugConfig(
                enabled=debug_config.enabled,
                backend=debug_config.backend,
                oracle_root=debug_config.oracle_root,
                max_trials=debug_config.max_trials,
                allow_failure=debug_config.allow_failure,
                toolchain_bin=debug_config.toolchain_bin,
                codex_bin=debug_config.codex_bin,
                codex_profile=debug_config.codex_profile,
                codex_model=debug_config.codex_model,
                codex_timeout=debug_config.codex_timeout,
                codex_multi_agent=debug_config.codex_multi_agent,
                openai_config=debug_openai_config_from_planner_config(llm_config),
            )
        self.stage1 = Stage1Agent(self.llm_client, self.context_provider, self.artifact_sink, self.logger)
        self.stage1_temporal = Stage1TemporalAgent(
            self.llm_client, self.context_provider, self.artifact_sink, self.logger
        )
        self.stage2 = Stage2Agent(self.llm_client, self.context_provider, self.artifact_sink, self.logger)
        self.stage2_temporal = Stage2TemporalContractAgent(
            self.llm_client, self.context_provider, self.artifact_sink, self.logger
        )
        self.stage3 = Stage3Agent(
            self.llm_client,
            self.context_provider,
            self.artifact_sink,
            self.logger,
            output_root=self.output_root,
            planning_context_retriever=self.planning_context_retriever,
            retrieval_limits=retrieval_limits,
        )
        self.stage3_timing = Stage3TimingBindingAgent(
            self.llm_client, self.context_provider, self.artifact_sink, self.logger
        )
        self.stage4_spec_blocks = Stage4SpecBlocksAgent(
            self.llm_client,
            self.context_provider,
            self.artifact_sink,
            self.logger,
            output_root=self.output_root,
            retrieval_limits=retrieval_limits,
        )
        self.stage4_module_plans = Stage4ModulePlanAgent(
            self.llm_client,
            self.context_provider,
            self.artifact_sink,
            self.logger,
            output_root=self.output_root,
            planning_context_retriever=self.planning_context_retriever,
        )
        self.stage5 = Stage5Agent(
            self.llm_client,
            self.context_provider,
            self.artifact_sink,
            self.logger,
            output_root=self.output_root,
            planning_context_retriever=self.planning_context_retriever,
            oracle_root=debug_config.oracle_root,
        )
        self.stage6 = Stage6MergeAgent(
            self.llm_client,
            self.context_provider,
            self.artifact_sink,
            self.logger,
            output_root=self.output_root,
            kg_service=self.kg_service,
            planning_context_retriever=self.planning_context_retriever,
            oracle_root=debug_config.oracle_root,
        )
        self.debug_runner = ModuleDebugRunner(
            config=debug_config,
            workspace_root=self.stage6.workspace_root,
            output_root=self.output_root,
            repo_root=Path.cwd(),
            logger=self.logger,
            kg_service=self.kg_service,
            initial_result_recorder=self._record_initial_kg_module_result,
        )
        self.system_debug_runner = SystemDebugRunner(
            config=debug_config,
            workspace_root=self.stage6.workspace_root,
            output_root=self.output_root,
            repo_root=Path.cwd(),
            logger=self.logger,
            kg_service=self.kg_service,
        )
        self.logger.info(
            "[rtl_module_planner] Debug routing: module_syntax_repair=repo_react, "
            "system_debug_backend=%s",
            debug_config.backend,
        )
        self.kg_result_writer = (
            ModuleResultWriter(
                kg_service=self.kg_service,
                workspace_root=self.stage6.workspace_root,
                checkpoint_dir=self.checkpoint_dir,
                logger=self.logger,
            )
            if self.kg_service is not None and self.kg_service.is_enabled()
            else None
        )

    def run(
        self,
        task_input: PlannerTaskInput | Dict[str, Any],
        resume: bool = False,
        end_stage: str = "stage1",
        force_rebuild: bool = False,
    ) -> Stage1ContractsArtifact | Stage2RepoSkeletonArtifact | Stage3ModuleSkeletonArtifact | Stage4ModulePlansArtifact | Stage5CodegenArtifact | Stage6MergeArtifact:
        if end_stage not in {"stage1", "stage2", "stage3", "stage4", "stage5", "stage6"}:
            raise NotImplementedError("module_planner currently supports end_stage in {'stage1', 'stage2', 'stage3', 'stage4', 'stage5', 'stage6'} only.")

        resume = resume and not force_rebuild
        self._allow_debug_generation_reuse = resume
        task = task_input if isinstance(task_input, PlannerTaskInput) else validate_model(PlannerTaskInput, task_input)
        self.stage3.module_spec_context_retriever.cache_enabled = resume
        self.stage4_spec_blocks.module_spec_context_retriever.cache_enabled = resume
        self.stage4_module_plans.cache_enabled = resume
        artifacts: Dict[str, Any] = {}
        existing_contracts = self._read_contracts_if_valid(task) if resume else None
        if existing_contracts is not None:
            self.logger.info(
                "[rtl_module_planner] Resume reused stage1 contracts artifact from %s",
                self._contracts_path(),
            )
            stage1_contracts = existing_contracts
        else:
            stage1_contracts = self.stage1.run_incremental(
                task,
                {},
                persist_callback=self._write_payload,
            )
        artifacts["stage1"] = stage1_contracts
        stage2_input = build_stage2_planning_input(
            stage1_artifact=stage1_contracts,
            task_input=task,
        )

        if end_stage == "stage1":
            return stage1_contracts

        stage2_fingerprint_payload = model_dump(stage2_input)
        stage2_fingerprint_payload.pop("temporal_facts", None)
        stage2_input_fingerprint = canonical_fingerprint(
            {
                # contracts.json intentionally compacts derived grounding on
                # disk. Fingerprints must use the same compact semantic view
                # before and after resume, while retaining authoritative fact
                # ledger grounding and all interface values.
                "stage2_input": self._drop_text_grounding(
                    stage2_fingerprint_payload,
                    preserve_fact_ledger=True,
                ),
                "interface_policy": self.INTERFACE_PLANNING_POLICY_VERSION,
                "pipeline_policy": self.PIPELINE_POLICY_VERSION,
            }
        )
        if resume:
            existing_decomposition = self._read_stage2_decomposition_if_valid(
                stage2_input_fingerprint
            )
            existing_repo_skeleton = (
                self._read_repo_skeleton_if_valid(stage2_input_fingerprint)
                if existing_decomposition is not None
                and existing_decomposition.status in {"selected", "selected_with_degradation"}
                else None
            )
            if existing_repo_skeleton is not None and existing_decomposition is not None:
                self.logger.info(
                    "[rtl_module_planner] Resume reused stage2 decomposition and repo skeleton artifacts",
                )
                repo_skeleton = existing_repo_skeleton
                stage2_decomposition = existing_decomposition
            else:
                repo_skeleton = self.stage2.run(
                    task,
                    {
                        "stage2_input": stage2_input,
                        "stage2_input_fingerprint": stage2_input_fingerprint,
                        **(
                            {"stage2_decomposition": existing_decomposition}
                            if existing_decomposition is not None
                            else {}
                        ),
                    },
                    decomposition_persist_callback=self._write_stage2_decomposition_payload,
                )
                repo_skeleton.input_fingerprint = stage2_input_fingerprint
                stage2_decomposition = self.stage2._last_decomposition
                self._write_repo_skeleton_payload(model_dump(repo_skeleton))
        else:
            repo_skeleton = self.stage2.run(
                task,
                {
                    "stage2_input": stage2_input,
                    "stage2_input_fingerprint": stage2_input_fingerprint,
                },
                decomposition_persist_callback=self._write_stage2_decomposition_payload,
            )
            repo_skeleton.input_fingerprint = stage2_input_fingerprint
            stage2_decomposition = self.stage2._last_decomposition
            self._write_repo_skeleton_payload(model_dump(repo_skeleton))
        artifacts["stage2_decomposition"] = stage2_decomposition

        modules_artifact = build_module_organized_artifact_from_repo_skeleton(
            stage1_artifact=stage1_contracts,
            repo_skeleton=repo_skeleton,
        )
        self._write_modules_payload(model_dump(modules_artifact))
        if self.planning_graph_writer is not None:
            self.planning_graph_writer.upsert_module_anchors(task, repo_skeleton)

        if end_stage == "stage2":
            return repo_skeleton

        module_skeletons = None
        stage3_input_fingerprint = canonical_fingerprint(
            {
                "repair_policy": REPAIR_POLICY_VERSION,
                "modules": self._drop_text_grounding(
                    model_dump(modules_artifact),
                    preserve_fact_ledger=True,
                ),
                "repo_skeleton": repo_skeleton,
                "stage2_decomposition": stage2_decomposition,
                "interface_policy": self.INTERFACE_PLANNING_POLICY_VERSION,
                "pipeline_policy": self.PIPELINE_POLICY_VERSION,
            }
        )

        if resume:
            existing_stage3 = self._read_module_skeletons_if_valid(
                stage3_input_fingerprint
            )
            if existing_stage3 is not None:
                if existing_stage3.stage3_status == "module_skeletons_planned":
                    self.logger.info(
                        "[rtl_module_planner] Resume reused stage3 module skeleton artifact from %s",
                        self._module_skeletons_path(),
                    )
                    module_skeletons = existing_stage3
                else:
                    self.logger.info(
                        "[rtl_module_planner] Resume continuing stage3 module skeleton artifact from %s (cursor=%d)",
                        self._module_skeletons_path(),
                        existing_stage3.resume_cursor,
                    )
                    artifacts["stage3"] = existing_stage3

        if module_skeletons is None:
            module_skeletons = self.stage3.run_incremental(
                task,
                {
                    "stage2_input": stage2_input,
                    "modules": modules_artifact,
                    "stage2": repo_skeleton,
                    "stage2_decomposition": stage2_decomposition,
                    "stage3_input_fingerprint": stage3_input_fingerprint,
                    **({"stage3": artifacts["stage3"]} if "stage3" in artifacts else {}),
                },
                persist_callback=self._write_stage3_outputs,
                spec_context_persist_callback=self._write_stage3_spec_context,
            )
            module_skeletons.input_fingerprint = stage3_input_fingerprint
            self._write_module_skeletons_payload(model_dump(module_skeletons))
        if self.planning_graph_writer is not None:
            self.planning_graph_writer.ensure_projection(
                task,
                repo_skeleton,
                module_skeletons=module_skeletons,
            )

        if end_stage == "stage3":
            return module_skeletons

        spec_stage_inputs = {
            "stage2_input": stage2_input,
            "modules": modules_artifact,
            "stage2": repo_skeleton,
            "stage2_decomposition": stage2_decomposition,
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
        stage4_input_fingerprint = canonical_fingerprint(
            {
                "repair_policy": REPAIR_POLICY_VERSION,
                "inputs": self._drop_text_grounding(
                    {
                        key: model_dump(value) if hasattr(value, "model_dump") else value
                        for key, value in module_plan_stage_inputs.items()
                    },
                    preserve_fact_ledger=True,
                ),
                "pipeline_policy": self.PIPELINE_POLICY_VERSION,
            }
        )
        module_plan_stage_inputs["stage4_input_fingerprint"] = stage4_input_fingerprint
        if resume:
            existing_module_plans = self._read_module_plans_if_valid(
                task,
                module_plan_stage_inputs,
                stage4_input_fingerprint,
            )
            if existing_module_plans is not None and existing_module_plans.stage4_status == "module_plans_planned":
                self.logger.info(
                    "[rtl_module_planner] Resume reused stage4 module plans artifact from %s",
                    self._module_plans_path(),
                )
                module_plans = existing_module_plans
            else:
                if existing_module_plans is not None:
                    module_plan_stage_inputs = dict(module_plan_stage_inputs)
                    module_plan_stage_inputs["stage4_existing"] = existing_module_plans
                    self.logger.info(
                        "[rtl_module_planner] Resume continuing stage4 module plans from cursor %d",
                        existing_module_plans.resume_cursor,
                    )
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
        if self.planning_graph_writer is not None:
            self.planning_graph_writer.ensure_projection(
                task,
                repo_skeleton,
                module_skeletons=module_skeletons,
                module_plans=module_plans,
            )
        if end_stage == "stage4":
            return module_plans

        codegen_stage_inputs = {
            "modules": modules_artifact,
            "stage2": repo_skeleton,
            "stage3": module_skeletons,
            "stage4": module_plans,
            "spec_blocks": spec_blocks,
        }
        codegen_stage_inputs["stage5_input_fingerprint"] = canonical_fingerprint(
            {
                "stage4": module_plans,
                "repair_policy": REPAIR_POLICY_VERSION,
                "pipeline_policy": self.PIPELINE_POLICY_VERSION,
            }
        )
        if end_stage == "stage5":
            if resume:
                existing_stage5 = self._read_stage5_codegen_if_valid(
                    task,
                    codegen_stage_inputs,
                    codegen_stage_inputs["stage5_input_fingerprint"],
                )
                if existing_stage5 is not None:
                    self.logger.info(
                        "[rtl_module_planner] Resume reused stage5 codegen artifact from %s",
                        self._stage5_codegen_path(),
                    )
                    return existing_stage5
            return self.stage5.run_incremental(
                task,
                codegen_stage_inputs,
                persist_callback=self._write_stage5_codegen_outputs,
            )

        return self._run_stage6_per_module(task, codegen_stage_inputs, spec_blocks)

    def _report_timing_check(
        self,
        timing_check: TimingBindingCheckArtifact | None,
    ) -> None:
        if timing_check is not None and timing_check.status == "fail":
            self.logger.warning(
                "[rtl_module_planner] Stage3.5 temporal binding check reported errors; "
                "continuing to Stage4 with the diagnostic artifact at %s.",
                self._timing_binding_check_path(),
            )

    def _read_contracts_if_valid(self, task: PlannerTaskInput) -> Any | None:
        path = self._contracts_path()
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            artifact = validate_model(Stage1ContractsArtifact, payload)
            if artifact.task_id != task.task_id:
                raise ValueError("stage1 contracts task_id mismatch")
            quality_errors = self.stage1.validate_quality(artifact, task, {})
            if quality_errors:
                raise ValueError(quality_errors)
            return artifact
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

    def _read_temporal_facts_if_valid(self, expected_input_fingerprint: str) -> GlobalTemporalFactsArtifact | None:
        path = self._temporal_facts_path()
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                artifact = validate_model(GlobalTemporalFactsArtifact, json.load(f))
            if artifact.input_fingerprint != expected_input_fingerprint:
                raise ValueError("global temporal facts input fingerprint mismatch")
            return artifact
        except Exception as exc:
            self.logger.warning(
                "[rtl_module_planner] Resume ignored invalid global temporal facts at %s: %s",
                path,
                exc,
            )
            return None

    def _build_degraded_temporal_facts(
        self,
        task: PlannerTaskInput,
        exc: Exception,
    ) -> GlobalTemporalFactsArtifact:
        reason = f"Stage1 temporal facts failed: {exc}"
        self.logger.warning(
            "[rtl_module_planner] %s Continuing with a safe empty temporal artifact.",
            reason,
        )
        return GlobalTemporalFactsArtifact(
            task_id=task.task_id,
            planning_status="degraded",
            degradation_reasons=[reason],
        )

    def _build_degraded_architecture_timing(
        self,
        task: PlannerTaskInput,
        repo_skeleton: Stage2RepoSkeletonArtifact,
        reason: str,
    ) -> ArchitectureTimingContractArtifact:
        modules = list(repo_skeleton.planning_decisions.generation_order) or [
            item.module for item in repo_skeleton.modules
        ]
        self.logger.warning(
            "[rtl_module_planner] %s Continuing with a safe empty architecture timing contract.",
            reason,
        )
        return ArchitectureTimingContractArtifact(
            task_id=task.task_id,
            planning_status="degraded",
            degradation_reasons=[reason],
            module_set=modules,
            architecture_logical_objects=[],
            module_assignments=[{"module": module} for module in modules],
            cross_module_transfers=[],
            module_obligations=[],
            assumptions=[
                "Temporal architecture planning degraded; downstream stages must rely on the source specification."
            ],
        )

    def _write_temporal_facts_payload(self, payload: Dict[str, Any]) -> Path:
        path = self._temporal_facts_path()
        self._write_json_payload(payload, path)
        self.logger.info("[rtl_module_planner] Wrote global temporal facts artifact to %s", path)
        return path

    def _read_architecture_timing_if_valid(
        self,
        task: PlannerTaskInput,
        temporal_facts: GlobalTemporalFactsArtifact,
        repo_skeleton: Stage2RepoSkeletonArtifact,
        expected_input_fingerprint: str,
    ) -> ArchitectureTimingContractArtifact | None:
        path = self._architecture_timing_path()
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                artifact = validate_model(ArchitectureTimingContractArtifact, json.load(f))
            if artifact.input_fingerprint != expected_input_fingerprint:
                raise ValueError("architecture timing input fingerprint mismatch")
            quality_errors = self.stage2_temporal.validate_quality(
                artifact,
                task,
                {"temporal_facts": temporal_facts, "stage2": repo_skeleton},
            )
            if quality_errors:
                raise ValueError(quality_errors)
            return artifact
        except Exception as exc:
            self.logger.warning(
                "[rtl_module_planner] Resume ignored invalid architecture timing artifact at %s: %s",
                path,
                exc,
            )
            return None

    def _write_architecture_timing_payload(self, payload: Dict[str, Any]) -> Path:
        path = self._architecture_timing_path()
        self._write_json_payload(payload, path)
        self.logger.info("[rtl_module_planner] Wrote architecture timing artifact to %s", path)
        return path

    def _run_temporal_binding_stages(
        self,
        *,
        task: PlannerTaskInput,
        temporal_facts: GlobalTemporalFactsArtifact,
        repo_skeleton: Stage2RepoSkeletonArtifact,
        architecture_timing: ArchitectureTimingContractArtifact,
        module_skeletons: Stage3ModuleSkeletonArtifact,
        resume: bool,
    ) -> tuple[Stage3TimingBindingsArtifact, TimingBindingCheckArtifact]:
        bindings_input_fingerprint = canonical_fingerprint(
            {
                "temporal_facts": temporal_facts,
                "architecture_timing": architecture_timing,
                "module_skeletons": module_skeletons,
            }
        )
        manifest = (
            self._read_timing_bindings_if_valid(bindings_input_fingerprint)
            if resume
            else None
        )
        records = list(manifest.module_binding_files) if manifest is not None else []
        completed = {item.module for item in records}
        record_by_module = {item.module: item for item in module_skeletons.module_records}

        for module_name in module_skeletons.module_order:
            if module_name in completed:
                continue
            skeleton_record = record_by_module[module_name]
            skeleton_path = self.output_root / skeleton_record.export_file
            with open(skeleton_path, "r", encoding="utf-8") as f:
                skeleton_export = validate_model(ModuleSkeletonExport, json.load(f))
            spec_context: Dict[str, Any] = {}
            if skeleton_record.spec_context_file:
                spec_context_path = self.output_root / skeleton_record.spec_context_file
                if spec_context_path.exists():
                    with open(spec_context_path, "r", encoding="utf-8") as f:
                        spec_context = json.load(f)
            module_input_fingerprint = canonical_fingerprint(
                {
                    "module": module_name,
                    "temporal_facts": temporal_facts,
                    "architecture_timing": architecture_timing,
                    "module_skeleton_export": skeleton_export,
                }
            )
            if architecture_timing.planning_status == "degraded":
                binding = ModuleTimingBindingArtifact(
                    task_id=task.task_id,
                    module=module_name,
                    assumptions=[
                        "Architecture timing is degraded; no temporal bindings were generated."
                    ],
                )
            else:
                binding = self.stage3_timing.run(
                    task,
                    {
                        "module_name": module_name,
                        "temporal_facts": temporal_facts,
                        "architecture_timing": architecture_timing,
                        "module_skeleton_export": skeleton_export,
                        "module_spec_context": spec_context,
                    },
                )
            binding.input_fingerprint = module_input_fingerprint
            binding_file = self._module_timing_binding_relative_path(module_name)
            self._write_json_payload(model_dump(binding), self.output_root / binding_file)
            records.append(ModuleTimingBindingRecord(module=module_name, binding_file=binding_file))
            incremental = Stage3TimingBindingsArtifact(
                task_id=task.task_id,
                input_fingerprint=bindings_input_fingerprint,
                module_order=list(module_skeletons.module_order),
                status="in_progress",
                completed_modules=[item.module for item in records],
                resume_cursor=len(records),
                module_binding_files=records,
            )
            self._write_timing_bindings_payload(model_dump(incremental))

        manifest = Stage3TimingBindingsArtifact(
            task_id=task.task_id,
            input_fingerprint=bindings_input_fingerprint,
            module_order=list(module_skeletons.module_order),
            status="planned",
            completed_modules=[item.module for item in records],
            resume_cursor=len(records),
            module_binding_files=records,
        )
        self._write_timing_bindings_payload(model_dump(manifest))

        bindings_by_module: Dict[str, ModuleTimingBindingArtifact] = {}
        skeletons_by_module: Dict[str, ModuleSkeletonExport] = {}
        for record in manifest.module_binding_files:
            with open(self.output_root / record.binding_file, "r", encoding="utf-8") as f:
                bindings_by_module[record.module] = validate_model(
                    ModuleTimingBindingArtifact,
                    json.load(f),
                )
            skeleton_record = record_by_module[record.module]
            with open(self.output_root / skeleton_record.export_file, "r", encoding="utf-8") as f:
                skeletons_by_module[record.module] = validate_model(
                    ModuleSkeletonExport,
                    json.load(f),
                )

        check_input_fingerprint = canonical_fingerprint(
            {
                "checker_ruleset": self.TIMING_BINDING_CHECK_RULESET_VERSION,
                "temporal_facts": temporal_facts,
                "repo_skeleton": repo_skeleton,
                "architecture_timing": architecture_timing,
                "module_skeletons": module_skeletons,
                "timing_bindings": manifest,
            }
        )
        timing_check = (
            self._read_timing_check_if_valid(check_input_fingerprint)
            if resume
            else None
        )
        if timing_check is None:
            timing_check = check_temporal_bindings(
                task_id=task.task_id,
                temporal_facts=temporal_facts,
                repo_skeleton=repo_skeleton,
                architecture=architecture_timing,
                skeletons=skeletons_by_module,
                bindings=bindings_by_module,
                input_fingerprint=check_input_fingerprint,
            )
            self._write_timing_check_payload(model_dump(timing_check))
        return manifest, timing_check

    def _read_timing_bindings_if_valid(
        self,
        expected_input_fingerprint: str,
    ) -> Stage3TimingBindingsArtifact | None:
        path = self._timing_bindings_path()
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                artifact = validate_model(Stage3TimingBindingsArtifact, json.load(f))
            if artifact.input_fingerprint != expected_input_fingerprint:
                raise ValueError("module timing bindings input fingerprint mismatch")
            for record in artifact.module_binding_files:
                binding_path = self.output_root / record.binding_file
                if not binding_path.exists():
                    raise FileNotFoundError(f"missing module timing binding: {binding_path}")
                with open(binding_path, "r", encoding="utf-8") as f:
                    binding = validate_model(ModuleTimingBindingArtifact, json.load(f))
                if binding.task_id != artifact.task_id or binding.module != record.module:
                    raise ValueError(f"invalid module timing binding identity at {binding_path}")
            return artifact
        except Exception as exc:
            self.logger.warning(
                "[rtl_module_planner] Resume ignored invalid module timing bindings at %s: %s",
                path,
                exc,
            )
            return None

    def _write_timing_bindings_payload(self, payload: Dict[str, Any]) -> Path:
        path = self._timing_bindings_path()
        self._write_json_payload(payload, path)
        self.logger.info("[rtl_module_planner] Wrote module timing bindings manifest to %s", path)
        return path

    def _read_timing_check_if_valid(
        self,
        expected_input_fingerprint: str,
    ) -> TimingBindingCheckArtifact | None:
        path = self._timing_binding_check_path()
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                artifact = validate_model(TimingBindingCheckArtifact, json.load(f))
            if artifact.input_fingerprint != expected_input_fingerprint:
                raise ValueError("timing binding check input fingerprint mismatch")
            return artifact
        except Exception as exc:
            self.logger.warning(
                "[rtl_module_planner] Resume ignored invalid timing binding check at %s: %s",
                path,
                exc,
            )
            return None

    def _write_timing_check_payload(self, payload: Dict[str, Any]) -> Path:
        path = self._timing_binding_check_path()
        self._write_json_payload(payload, path)
        self.logger.info("[rtl_module_planner] Wrote timing binding check artifact to %s", path)
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

    def _read_repo_skeleton_if_valid(self, expected_input_fingerprint: str | None = None) -> Any | None:
        path = self._repo_skeleton_path()
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            artifact = validate_model(Stage2RepoSkeletonArtifact, payload)
            if expected_input_fingerprint is not None and artifact.input_fingerprint != expected_input_fingerprint:
                raise ValueError("repo skeleton input fingerprint mismatch")
            return artifact
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

    def _read_stage2_decomposition_if_valid(
        self,
        expected_input_fingerprint: str | None = None,
    ) -> Stage2DecompositionArtifact | None:
        path = self._stage2_decomposition_path()
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            artifact = validate_model(Stage2DecompositionArtifact, payload)
            if expected_input_fingerprint is not None and artifact.input_fingerprint != expected_input_fingerprint:
                raise ValueError("stage2 decomposition input fingerprint mismatch")
            if artifact.status in {"selected", "selected_with_degradation"} and artifact.selected_candidate() is None:
                raise ValueError("stage2 decomposition selected candidate is missing")
            return artifact
        except Exception as exc:
            self.logger.warning(
                "[rtl_module_planner] Resume ignored invalid stage2 decomposition artifact at %s: %s",
                path,
                exc,
            )
            return None

    def _write_stage2_decomposition_payload(self, payload: Dict[str, Any]) -> Path:
        path = self._stage2_decomposition_path()
        self._write_json_payload(payload, path)
        self.logger.info("[rtl_module_planner] Wrote stage2 decomposition artifact to %s", path)
        return path

    def _read_module_skeletons_if_valid(self, expected_input_fingerprint: str | None = None) -> Any | None:
        path = self._module_skeletons_path()
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            artifact = validate_model(Stage3ModuleSkeletonArtifact, payload)
            if expected_input_fingerprint is not None and artifact.input_fingerprint != expected_input_fingerprint:
                raise ValueError("module skeleton input fingerprint mismatch")
            return artifact
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

    def _read_module_plans_if_valid(
        self,
        task: PlannerTaskInput,
        partial_artifacts: Dict[str, Any],
        expected_input_fingerprint: str | None = None,
    ) -> Any | None:
        path = self._module_plans_path()
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            artifact = validate_model(Stage4ModulePlansArtifact, payload)
            if expected_input_fingerprint is not None and artifact.input_fingerprint != expected_input_fingerprint:
                raise ValueError("module plans input fingerprint mismatch")
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

    def _read_stage5_codegen_if_valid(
        self,
        task: PlannerTaskInput,
        codegen_stage_inputs: Dict[str, Any],
        expected_input_fingerprint: str,
    ) -> Stage5CodegenArtifact | None:
        path = self._stage5_codegen_path()
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                artifact = validate_model(Stage5CodegenArtifact, json.load(f))
            if artifact.input_fingerprint != expected_input_fingerprint:
                raise ValueError("stage5 codegen input fingerprint mismatch")
            for record in artifact.module_files:
                reused = self._reuse_stage5_fragment_if_valid(record.module, codegen_stage_inputs, task)
                if reused is None:
                    raise ValueError(f"stage5 fragment for `{record.module}` is not reusable")
            quality_errors = self.stage5.validate_quality(artifact, task, codegen_stage_inputs)
            if quality_errors:
                raise ValueError(quality_errors)
            return artifact
        except Exception as exc:
            self.logger.warning(
                "[rtl_module_planner] Resume ignored invalid stage5 codegen artifact at %s: %s",
                path,
                exc,
            )
            return None

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
            if "retrieval_file" in payload and "retrieval_payload" in payload:
                self._write_json_payload(payload["retrieval_payload"], self.output_root / payload["retrieval_file"])
            if self.planning_graph_writer is not None:
                self.planning_graph_writer.upsert_module_plan(
                    payload.get("task") or {"task_id": payload["manifest"].get("task_id", "")},
                    module_name,
                    payload["plan_payload"],
                    artifact_path=payload["plan_file"],
                    input_fingerprint=str(payload.get("input_fingerprint") or ""),
                )
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
            if "spec_context_file" in payload and "spec_context_payload" in payload:
                self._write_json_payload(payload["spec_context_payload"], self.output_root / payload["spec_context_file"])
            if self.planning_graph_writer is not None:
                self.planning_graph_writer.upsert_module_skeleton(
                    payload.get("task") or {"task_id": payload["manifest"].get("task_id", "")},
                    module_name,
                    payload["export_payload"],
                    artifact_path=export_file,
                    input_fingerprint=str(payload.get("input_fingerprint") or ""),
                    spec_context_fingerprint=self.planning_graph_writer._module_spec_fingerprint(module_name),
                )
            self.logger.info(
                "[rtl_module_planner] Wrote stage3 module doc/json sidecars for %s",
                module_name,
            )
        return self._write_module_skeletons_payload(payload["manifest"])

    def _write_stage3_spec_context(self, payload: Dict[str, Any]) -> Path:
        path = self.output_root / payload["spec_context_file"]
        self._write_json_payload(payload["spec_context_payload"], path)
        if self.planning_graph_writer is not None:
            self.planning_graph_writer.upsert_spec_fragments(
                payload.get("task") or {},
                str(payload["module"]),
                payload["spec_context_payload"],
                artifact_path=str(payload["spec_context_file"]),
                input_fingerprint=str(payload.get("input_fingerprint") or ""),
            )
        return path

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

    def _temporal_facts_path(self) -> Path:
        return self.output_root / self.GLOBAL_TEMPORAL_FACTS_FILENAME

    def _architecture_timing_path(self) -> Path:
        return self.output_root / self.ARCHITECTURE_TIMING_CONTRACT_FILENAME

    def _timing_bindings_path(self) -> Path:
        return self.output_root / self.MODULE_TIMING_BINDINGS_FILENAME

    def _timing_binding_check_path(self) -> Path:
        return self.output_root / self.TIMING_BINDING_CHECK_FILENAME

    def _module_timing_binding_relative_path(self, module_name: str) -> str:
        return f"{self.MODULE_TIMING_BINDING_JSON_DIRNAME}/{module_name}.json"

    def _modules_path(self) -> Path:
        return self.output_root / self.MODULES_FILENAME

    def _repo_skeleton_path(self) -> Path:
        return self.output_root / self.REPO_SKELETON_FILENAME

    def _stage2_decomposition_path(self) -> Path:
        return self.output_root / self.STAGE2_DECOMPOSITION_FILENAME

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
        failed_modules = set()
        restored_debug = self._restore_debug_generation(task, codegen_stage_inputs)
        stage5_inputs = codegen_stage_inputs
        if restored_debug:
            stage5_inputs = {**codegen_stage_inputs, "_stage5_dependency_files": {
                n: self._debug_generation_origin / f"{n}.v" for n in spec_blocks.module_order}}
        repo = codegen_stage_inputs.get("stage2")
        children_by_module = {item.module: list(item.children) for item in getattr(repo, "modules", [])}
        for module_name in spec_blocks.module_order:
            blocked_by = sorted(set(children_by_module.get(module_name, [])) & failed_modules)
            if blocked_by:
                reason = f"Dependency modules failed: {blocked_by}"
                stage5_records.append(ModuleCodegenRecord(module=module_name, status="blocked", error=reason))
                stage6_records.append(ModuleMergeRecord(module=module_name, status="blocked", error=reason))
                debug_records.append(ModuleDebugResult(module=module_name, status="skipped", reason=reason))
                failed_modules.add(module_name)
                continue
            stage5_record = (restored_debug.get(module_name) if restored_debug else
                            self._reuse_stage5_fragment_if_valid(module_name, stage5_inputs, task))
            if stage5_record is not None:
                self.logger.info(
                    "[rtl_module_planner] Resume reused stage5 fragments for module %s from %s",
                    module_name,
                    stage5_record.workspace_file,
                )
            else:
                self.logger.info("[rtl_module_planner] Stage5 generating fragments for module %s", module_name)
                try:
                    stage5_record = self.stage5.run_module(task, codegen_stage_inputs, module_name)
                except Exception as exc:
                    self.logger.error(
                        "[rtl_module_planner] Stage5 failed for module %s: %s",
                        module_name, exc,
                    )
                    stage5_record = ModuleCodegenRecord(
                        module=module_name,
                        status="failed", error=f"{type(exc).__name__}: {exc}",
                        workspace_file=str(self.stage5._workspace_file(module_name)),
                        completed_subtasks=list(self.stage5._validated_subtasks_by_module.get(module_name, [])),
                    )
            stage5_records.append(stage5_record)
            if stage5_record.status != "completed":
                failed_modules.add(module_name)
                reason = f"Stage5 {stage5_record.status}: {stage5_record.error}"
                stage6_records.append(ModuleMergeRecord(module=module_name, status="blocked", error=reason, fragment_file=stage5_record.workspace_file))
                debug_records.append(ModuleDebugResult(module=module_name, status="skipped", reason=reason))
                continue
            stage6_record = self._reuse_stage6_merge_if_valid(module_name, stage5_record, codegen_stage_inputs)
            if stage6_record is not None:
                self.logger.info(
                    "[rtl_module_planner] Resume reused stage6 merged RTL for module %s from %s",
                    module_name,
                    stage6_record.merged_file,
                )
            else:
                self.logger.info("[rtl_module_planner] Stage6 merging module %s immediately after stage5", module_name)
                try:
                    stage6_record = self.stage6.run_module(
                        task,
                        codegen_stage_inputs,
                        module_name,
                        stage5_record,
                    )
                except Exception as exc:
                    self.logger.error(
                        "[rtl_module_planner] Stage6 failed for module %s: %s",
                        module_name, exc,
                    )
                    stage6_record = ModuleMergeRecord(
                        module=module_name,
                        fragment_file=str(getattr(stage5_record, "workspace_file", "")),
                        merged_file="", status="failed", error=f"{type(exc).__name__}: {exc}",
                    )
            stage6_records.append(stage6_record)
            if not stage6_record.merged_file:
                failed_modules.add(module_name)
                self.logger.warning(
                    "[rtl_module_planner] Skipping syntax gate for %s: no merged RTL (stage5 or stage6 failed)",
                    module_name,
                )
                debug_result = ModuleDebugResult(
                    module=module_name,
                    status="skipped",
                    final_rtl_path="",
                    reason="Stage5 or Stage6 failed; no merged RTL to syntax-check.",
                )
                debug_records.append(debug_result)
                self._record_kg_module_result(module_name, "", debug_result, stage="post_module_syntax")
                continue
            self.logger.info("[rtl_module_planner] Syntax checking module %s after stage6", module_name)
            module_spec_text = build_module_spec_text(module_name=module_name, spec_blocks=spec_blocks)
            debug_spec_source_path = ""
            debug_spec_text = module_spec_text
            try:
                debug_spec_source_path, debug_spec_text = resolve_module_spec_text(module_name, task.spec_md_files)
            except FileNotFoundError:
                debug_spec_source_path = ""
            try:
                debug_result = self.debug_runner.run_module_syntax_gate(
                    module_name=module_name,
                    merged_file=stage6_record.merged_file,
                    task=task,
                    spec_text=debug_spec_text,
                    contract_json=build_debug_contract_json(
                        module_name=module_name,
                        stage1_contracts=codegen_stage_inputs.get("stage1"),
                        spec_text=debug_spec_text,
                    ),
                    spec_source_path=debug_spec_source_path,
                )
            except Exception as exc:
                debug_result = ModuleDebugResult(
                    module=module_name,
                    status="error",
                    final_rtl_path=stage6_record.merged_file,
                    reason=f"{type(exc).__name__}: {exc}",
                )
                self._record_kg_module_result(
                    module_name,
                    stage6_record.merged_file,
                    debug_result,
                    stage="post_module_syntax",
                )
                self.logger.warning(
                    "[rtl_module_planner] Syntax gate failed for module %s (continuing): %s",
                    module_name, exc,
                )
            debug_records.append(debug_result)
            if (
                self.kg_service is not None
                and self.kg_service.is_enabled()
                and debug_result.status in {"pass", "fixed"}
            ):
                # Materialize code structure only after the merged module passes
                # syntax, and before any simulation/system-debug activity.
                self.kg_service.refresh_repo_files(
                    changed_paths=[stage6_record.merged_file],
                    stage="post_stage6_syntax",
                    filter_to_planned_skeleton=False,
                )
            self._record_kg_module_result(
                module_name,
                stage6_record.merged_file,
                debug_result,
                stage="post_module_syntax",
            )
            self.logger.info(
                "[rtl_module_planner] Syntax gate result for %s: %s%s",
                module_name,
                debug_result.status,
                f" ({debug_result.reason})" if debug_result.reason else "",
            )
            if debug_result.status in {"fail", "error"} and not self.debug_runner.config.allow_failure:
                self.logger.warning(
                    "[rtl_module_planner] RTL syntax gate %s for %s (tolerated per resilience policy): %s",
                    debug_result.status,
                    module_name,
                    debug_result.reason,
                )

            if Path(stage6_record.merged_file).is_file():
                atomic_write_json(self._stage6_cache_path(module_name), {
                    "input_fingerprint": self._stage6_reuse_key(module_name, stage5_record, codegen_stage_inputs),
                    "merged_fingerprint": fingerprint(Path(stage6_record.merged_file).read_text(encoding="utf-8")),
                })

        stage5_artifact = Stage5CodegenArtifact(
            task_id=task.task_id,
            input_fingerprint=str(codegen_stage_inputs.get("stage5_input_fingerprint") or ""),
            module_order=list(spec_blocks.module_order),
            module_files=stage5_records,
        )
        stage5_quality_errors = self.stage5.validate_quality(stage5_artifact, task, codegen_stage_inputs)
        if stage5_quality_errors:
            self.logger.warning(
                "[rtl_module_planner] Stage5 aggregate quality check has issues (non-fatal): %s",
                stage5_quality_errors,
            )
        self._write_stage5_codegen_payload(model_dump(stage5_artifact))
        self.artifact_sink.record_stage_output(self.stage5.stage_name, stage5_artifact, task)

        self._write_planning_kg_consistency_report(
            repo_skeleton=codegen_stage_inputs.get("stage2"),
            stage3=codegen_stage_inputs.get("stage3"),
            stage6_records=stage6_records,
            debug_records=debug_records,
        )

        repo_skeleton = codegen_stage_inputs.get("stage2")
        top_module = str(getattr(repo_skeleton, "top_module", "") or "")
        system_debug_result = None
        if not failed_modules:
            try:
                self._prepare_debug_generation(task, codegen_stage_inputs, stage6_records)
                system_spec_text = self._build_system_spec_text(task)
                system_debug_result = self.system_debug_runner.run_system(
                    top_module=top_module,
                    task=task,
                    spec_text=system_spec_text,
                    contract_json=build_debug_contract_json(
                        module_name=top_module or (spec_blocks.module_order[-1] if spec_blocks.module_order else ""),
                        stage1_contracts=codegen_stage_inputs.get("stage1"),
                        spec_text=system_spec_text,
                    ),
                    merged_records=stage6_records,
                )
                self.logger.info(
                    "[rtl_module_planner] System debug result for %s: %s%s",
                    top_module or "<unknown>",
                    system_debug_result.status,
                    f" ({system_debug_result.reason})" if system_debug_result.reason else "",
                )
            except Exception as exc:
                self.logger.warning(
                    "[rtl_module_planner] System debug failed for %s (continuing): %s",
                    top_module or "<unknown>",
                    exc,
                )
            self._publish_debug_generation(task, codegen_stage_inputs)

        else:
            system_debug_result = SystemDebugRecord(
                top_module=top_module, status="skipped",
                reason=f"Generation incomplete; failed or blocked modules: {sorted(failed_modules)}",
            )

        current_debug = (model_dump(system_debug_result) if isinstance(system_debug_result, SystemDebugRecord)
                         else system_debug_result_to_dict(system_debug_result)) if system_debug_result is not None else None
        latest_debug_path = self.output_root / "system_debug_latest.json"
        latest_debug = None
        if current_debug and current_debug.get("status") not in {"skipped", "disabled"}:
            latest_debug = current_debug
            atomic_write_json(latest_debug_path, latest_debug)
        elif latest_debug_path.is_file():
            try:
                latest_debug = json.loads(latest_debug_path.read_text())
            except (OSError, ValueError):
                self.logger.warning("[rtl_module_planner] Latest system debug record is unreadable")
        stage6_artifact = Stage6MergeArtifact(
            task_id=task.task_id,
            module_order=list(spec_blocks.module_order),
            module_files=stage6_records,
            debug_files=[module_debug_result_to_dict(item) for item in debug_records],
            system_debug=(model_dump(system_debug_result) if isinstance(system_debug_result, SystemDebugRecord) else system_debug_result_to_dict(system_debug_result)) if system_debug_result is not None else None,
            latest_system_debug=latest_debug,
        )
        stage6_quality_errors = self.stage6.validate_quality(stage6_artifact, task, codegen_stage_inputs)
        if stage6_quality_errors:
            self.logger.warning(
                "[rtl_module_planner] Stage6 aggregate quality check has issues (non-fatal): %s",
                stage6_quality_errors,
            )
        self._write_stage6_merge_payload(model_dump(stage6_artifact))
        self.artifact_sink.record_stage_output(self.stage6.stage_name, stage6_artifact, task)
        return stage6_artifact

    def _write_planning_kg_consistency_report(
        self,
        *,
        repo_skeleton: Any,
        stage3: Any,
        stage6_records: list[Any],
        debug_records: list[Any],
    ) -> Path | None:
        """Emit a read-only Stage6 planning/code comparison before system debug."""
        if repo_skeleton is None:
            return None
        planned = [str(item.module) for item in repo_skeleton.modules]
        passed = {
            str(item.module)
            for item in debug_records
            if str(getattr(item, "status", "")) in {"pass", "fixed"}
        }
        merged = {
            str(item.module)
            for item in stage6_records
            if str(getattr(item, "merged_file", ""))
        }
        report: Dict[str, Any] = {
            "schema_version": "planning_code_consistency_v1",
            "planned_modules": planned,
            "materialized_modules": sorted(passed),
            "missing_actual_modules": sorted(set(planned) - passed),
            "unexpected_actual_modules": sorted(merged - set(planned)),
            "planned_child_not_instantiated": [],
            "interface_width_mismatches": [],
            "unmaterialized_skeleton_blocks": [],
            "query_errors": [],
        }
        if self.kg_service is not None and self.kg_service.is_enabled():
            try:
                hierarchy = self.kg_service.query(
                    """
                    MATCH (m:Module {repo_uid: $repo_uid})
                    OPTIONAL MATCH (m)-[:INSTANTIATES]->(:Instance)-[:OF_MODULE]->(child:Module)
                    RETURN m.name AS module, collect(DISTINCT child.name) AS children
                    """,
                    {"repo_uid": self.kg_service.repo_uid},
                    limit=max(10, len(planned) * 2),
                )
                actual_children = {
                    str(row.get("module")): {str(item) for item in row.get("children") or [] if item}
                    for row in hierarchy.get("rows") or []
                }
                for module in repo_skeleton.modules:
                    for child in module.children:
                        if module.module in passed and child not in actual_children.get(module.module, set()):
                            report["planned_child_not_instantiated"].append(
                                {"parent": module.module, "child": child}
                            )
            except Exception as exc:
                report["query_errors"].append(f"hierarchy: {exc}")

            try:
                blocks = self.kg_service.query(
                    """
                    MATCH (m:Module {repo_uid: $repo_uid})
                    OPTIONAL MATCH (m)-[:HAS|INSTANTIATES]->(b)
                    WHERE b:AlwaysBlock OR b:Assign OR b:Instance
                    RETURN m.name AS module, collect(DISTINCT b.kind) AS kinds
                    """,
                    {"repo_uid": self.kg_service.repo_uid},
                    limit=max(10, len(planned) * 2),
                )
                actual_kinds = {
                    str(row.get("module")): {str(item) for item in row.get("kinds") or [] if item}
                    for row in blocks.get("rows") or []
                }
                for record in getattr(stage3, "module_records", []) or []:
                    export_path = self.output_root / str(record.export_file)
                    if not export_path.exists() or record.module not in passed:
                        continue
                    export = json.loads(export_path.read_text(encoding="utf-8"))
                    for block in export.get("structural_blocks") or []:
                        block_kind = str(block.get("block_kind") or "")
                        kinds = actual_kinds.get(record.module, set())
                        realized = (
                            block_kind not in {"inst", "seq", "comb"}
                            or (block_kind == "inst" and "Instance" in kinds)
                            or (block_kind == "seq" and "AlwaysBlock" in kinds)
                            or (block_kind == "comb" and bool(kinds & {"AlwaysBlock", "Assign"}))
                        )
                        if not realized:
                            report["unmaterialized_skeleton_blocks"].append(
                                {
                                    "module": record.module,
                                    "block_id": str(block.get("block_id") or ""),
                                    "block_kind": block_kind,
                                }
                            )
            except Exception as exc:
                report["query_errors"].append(f"blocks: {exc}")

            if self.planning_context_retriever is not None:
                for module_name in sorted(passed):
                    try:
                        context = self.planning_context_retriever.get_module_context(
                            module_name,
                            require_skeleton=True,
                            include_code_interface=True,
                        )
                        frame = str((context.get("skeleton_artifact") or {}).get("module_frame") or "")
                        for port in context.get("code_interface") or []:
                            name = str(port.get("name") or "")
                            match = re.search(
                                rf"\b(input|output|inout)\b\s*(?:wire|reg|logic)?\s*"
                                rf"(?P<width>\[[^\]]+\])?\s*{re.escape(name)}\b",
                                frame,
                            )
                            actual_width = re.sub(r"\s+", "", str(port.get("width") or ""))
                            planned_width = re.sub(
                                r"\s+", "", str(match.group("width") if match else "")
                            )
                            if match is None or planned_width != actual_width:
                                report["interface_width_mismatches"].append(
                                    {
                                        "module": module_name,
                                        "port": name,
                                        "planned_width": planned_width,
                                        "actual_width": actual_width,
                                        "reason": "port missing from skeleton frame" if match is None else "width differs",
                                    }
                                )
                    except Exception as exc:
                        report["query_errors"].append(f"interface/{module_name}: {exc}")

        issue_keys = (
            "missing_actual_modules",
            "unexpected_actual_modules",
            "planned_child_not_instantiated",
            "interface_width_mismatches",
            "unmaterialized_skeleton_blocks",
            "query_errors",
        )
        report["status"] = "pass" if not any(report[key] for key in issue_keys) else "warn"
        path = self.output_root / "planning_code_consistency.json"
        self._write_json_payload(report, path)
        self.logger.info("[rtl_module_planner] Wrote planning/code consistency report to %s", path)
        return path

    def _record_kg_module_result(
        self,
        module_name: str,
        merged_file: str,
        debug_result: Any,
        stage: str = "post_module_debug",
    ) -> None:
        if self.kg_result_writer is None:
            return
        try:
            status = self.kg_result_writer.record_module_result(
                module_name=module_name,
                merged_file=merged_file,
                debug_result=debug_result,
                stage=stage,
                refresh_code=(
                    stage != "post_module_syntax"
                    or str(getattr(debug_result, "status", "")) in {"pass", "fixed"}
                ),
            )
            self.logger.info(
                "[rtl_module_planner] Wrote RTL KG module result for %s at %s: %s passed=%s",
                module_name,
                stage,
                status.status,
                status.passed,
            )
        except Exception as exc:  # noqa: BLE001 - optional KG must not block RTL generation/debug.
            if str(getattr(self.kg_service, "mode", "") or "").strip().lower() == "required":
                self.logger.error(
                    "[rtl_module_planner] RTL KG module result write failed for %s in required mode: %s",
                    module_name,
                    exc,
                )
                raise
            self.logger.warning(
                "[rtl_module_planner] RTL KG module result write failed for %s: %s",
                module_name,
                exc,
            )

    def _record_initial_kg_module_result(
        self,
        module_name: str,
        merged_file: str | Path,
        debug_result: Any,
    ) -> None:
        self._record_kg_module_result(
            module_name=module_name,
            merged_file=str(merged_file),
            debug_result=debug_result,
            stage="post_initial_sim",
        )

    def _build_system_spec_text(self, task: PlannerTaskInput) -> str:
        chunks: list[str] = []
        for item in task.spec_md_files:
            path = Path(item)
            try:
                if path.is_dir():
                    for md_path in sorted(path.rglob("*.md")):
                        chunks.append(f"// spec source: {md_path}\n{md_path.read_text(encoding='utf-8')}")
                elif path.is_file():
                    chunks.append(f"// spec source: {path}\n{path.read_text(encoding='utf-8')}")
            except OSError:
                continue
        return "\n\n".join(chunks)

    def _reuse_stage5_fragment_if_valid(self, module_name, codegen_stage_inputs, task=None):
        # Validate every checkpoint against current subtask sources/context. A
        # marker or global manifest fingerprint alone is not completion evidence.
        if task is None:
            return None
        try:
            return self.stage5.run_module(task, codegen_stage_inputs, module_name, reuse_only=True)
        except (ValueError, OSError, KeyError, TypeError) as exc:
            self.logger.info("[rtl_module_planner] Stage5 cache unavailable for %s: %s", module_name, exc)
            return None

    def _stage6_cache_path(self, module_name):
        return self.stage6._merged_file(module_name).with_suffix(".inputs.json")

    def _stage6_reuse_key(self, module_name, stage5_record, inputs, dependency_root=None):
        stage3 = inputs.get("stage3")
        record = next((item for item in getattr(stage3, "module_records", []) if item.module == module_name), None)
        skeleton = ""
        if record:
            path = Path(record.doc_file)
            path = path if path.is_absolute() else self.output_root / path
            skeleton = path.read_text(encoding="utf-8") if path.is_file() else ""
        specs = inputs.get("spec_blocks")
        spec = next((item for item in getattr(specs, "modules", []) if item.module == module_name), None)
        repo = inputs.get("stage2")
        repo_module = next((item for item in getattr(repo, "modules", []) if item.module == module_name), None)
        children = {}
        for child in getattr(repo_module, "children", []):
            path = Path(dependency_root) / f"{child}.v" if dependency_root else self.stage6._merged_file(child)
            children[child] = path.read_text(encoding="utf-8") if path.is_file() else ""
        return fingerprint({"policy": REPAIR_POLICY_VERSION, "module": module_name,
                            "fragments": Path(stage5_record.workspace_file).read_text(encoding="utf-8"),
                            "skeleton": skeleton, "spec": spec, "children": children})

    def _debug_generation_binding_path(self):
        return self.output_root / ".repair_cache" / "accepted_debug_generation.json"

    def _debug_generation_private(self, inputs):
        top = inputs["stage2"].top_module
        return self.stage5.workspace_root / "debug_system" / top / "codex_private"

    def _debug_generation_state(self, task, inputs):
        """Verify the private accepted tree and original debug source binding."""
        from zerorepo.rtl_impl.codex_debug.history import tree_manifest, debug_binding
        private = self._debug_generation_private(inputs)
        state = json.loads((private / "session_state.json").read_text())
        descriptor = json.loads((private / "run_descriptor.json").read_text())
        record = json.loads((private / "run_record.json").read_text())
        if not state["run_id"] == descriptor["run_id"] == record["run_id"]:
            raise ValueError("Debug generation run identities disagree")
        binding = debug_binding(top_module=descriptor["top_module"], spec_text=descriptor["spec_text"],
            spec_paths=task.spec_md_files, contract_json=descriptor["contract_json"],
            verify_script=descriptor["verify_script"])
        if record["binding"] != binding:
            raise ValueError("Debug spec or verifier binding changed")
        accepted = private / "accepted_baseline" / "merged"
        if tree_manifest(accepted) != state["accepted_manifest"]:
            raise ValueError("Accepted debug RTL checksum mismatch")
        names = inputs["spec_blocks"].module_order
        if any(f"{n}.v" not in state["accepted_manifest"] for n in names):
            raise ValueError("Accepted debug tree does not cover all generation modules")
        return private, state, accepted

    def _restore_debug_generation(self, task, inputs):
        """Restore only a fully source-verified accepted generation, never a candidate."""
        self._debug_generation_origin = None
        if not getattr(self, "_allow_debug_generation_reuse", True) or not hasattr(self.stage5, "workspace_root"):
            return None
        verified = False
        try:
            from .utils.debug_generation import generation_sources, save_origin, validate_origin
            from zerorepo.rtl_impl.codex_debug.history import tree_manifest
            private, state, accepted = self._debug_generation_state(task, inputs)
            workspace = self.stage5.workspace_root
            sources = generation_sources(self.output_root, workspace, inputs, task)
            path = self._debug_generation_binding_path()
            saved = json.loads(path.read_text()) if path.is_file() else None
            names = inputs["spec_blocks"].module_order
            if saved:
                if (saved.get("version") != "accepted_debug_generation_v1" or
                        saved.get("binding_fingerprint") != fingerprint({k:v for k,v in saved.items() if k != "binding_fingerprint"})):
                    raise ValueError("Accepted debug generation binding checksum mismatch")
                if saved["run_id"] != state["run_id"]:
                    raise ValueError("Generation binding belongs to another debug run")
                origin = validate_origin(workspace, saved, sources)
            else:
                # Legacy recovery must prove every original Stage6 source AND
                # original output, using the preserved pre-debug launcher tree.
                origin = private / "launcher_baseline" / "merged"
                for n in names:
                    stamp = json.loads(self._stage6_cache_path(n).read_text())
                    fragment = ModuleCodegenRecord(module=n, workspace_file=str(self.stage5._workspace_file(n)))
                    if (stamp["input_fingerprint"] != self._stage6_reuse_key(n, fragment, inputs, origin)
                            or stamp["merged_fingerprint"] != fingerprint((origin / f"{n}.v").read_text())):
                        raise ValueError(f"No complete pre-debug generation evidence for {n}")
            dependency_files = {n: origin / f"{n}.v" for n in names}
            checked = {**inputs, "_stage5_dependency_files": dependency_files}
            records = {n: self.stage5.run_module(task, checked, n, reuse_only=True) for n in names}
            merged = workspace / "merged"
            current = {f"{n}.v": tree_manifest(merged).get(f"{n}.v") for n in names}
            expected = {f"{n}.v": state["accepted_manifest"][f"{n}.v"] for n in names}
            known = [{f"{n}.v": tree_manifest(origin).get(f"{n}.v") for n in names}, expected]
            if saved:
                known.append({f"{n}.v": saved["accepted_manifest"].get(f"{n}.v") for n in names})
            if current not in known:
                raise ValueError("Current merged RTL has edits outside the verified debug lineage")
            if not saved:
                origin = save_origin(workspace, sources, {f"{n}.v": (origin / f"{n}.v").read_text() for n in names})
            verified = True
            self._debug_generation_origin = origin
            if current != expected:
                from .utils.artifact_store import atomic_write_text
                for n in names:
                    atomic_write_text(merged / f"{n}.v", (accepted / f"{n}.v").read_text())
            if not self._publish_debug_generation(task, inputs):
                raise OSError("Could not publish verified debug generation bindings")
            self.logger.info("[rtl_module_planner] Restored accepted debug generation %s; original fragments and debug RTL retained", state["run_id"])
            return records
        except (OSError, ValueError, KeyError, TypeError) as exc:
            if verified:
                raise RuntimeError("Verified debug generation could not be committed; retained for retry") from exc
            if self._debug_generation_private(inputs).exists():
                self.logger.info("[rtl_module_planner] Accepted debug generation unavailable: %s", exc)
            self._debug_generation_origin = None
            return None

    def _prepare_debug_generation(self, task, inputs, records):
        from .utils.debug_generation import generation_sources, save_origin
        if getattr(self, "_debug_generation_origin", None):
            return
        try:
            sources = generation_sources(self.output_root, self.stage5.workspace_root, inputs, task)
            self._debug_generation_origin = save_origin(self.stage5.workspace_root, sources,
                {Path(r.merged_file).name: Path(r.merged_file).read_text() for r in records})
            atomic_write_json(self.output_root / ".repair_cache" / "pending_debug_generation.json", {
                "origin_path": str(self._debug_generation_origin.relative_to(self.stage5.workspace_root)),
                "source_fingerprint": fingerprint(sources)})
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self.logger.info("[rtl_module_planner] Debug origin snapshot unavailable: %s", exc)

    def _publish_debug_generation(self, task, inputs):
        origin = getattr(self, "_debug_generation_origin", None)
        if not origin:
            return
        try:
            from .utils.debug_generation import generation_sources, validate_origin
            from zerorepo.rtl_impl.codex_debug.history import tree_manifest
            _, state, accepted = self._debug_generation_state(task, inputs)
            workspace = self.stage5.workspace_root
            binding = {"version": "accepted_debug_generation_v1", "run_id": state["run_id"],
                "origin_path": str(origin.relative_to(workspace)), "accepted_manifest": tree_manifest(accepted),
                "source_fingerprint": fingerprint(generation_sources(self.output_root, workspace, inputs, task))}
            binding["binding_fingerprint"] = fingerprint(binding)
            validate_origin(workspace, binding, generation_sources(self.output_root, workspace, inputs, task))
            for n in inputs["spec_blocks"].module_order:
                merged_file = self.stage6._merged_file(n)
                if tree_manifest(merged_file.parent).get(merged_file.name) != binding["accepted_manifest"][merged_file.name]:
                    raise ValueError("Accepted debug files were not fully published")
            atomic_write_json(self._debug_generation_binding_path(), binding)
            for n in inputs["spec_blocks"].module_order:
                path = self._stage6_cache_path(n)
                if path.is_file():
                    old = json.loads(path.read_text())
                    atomic_write_json(self.output_root / ".repair_cache" / "stage6_history" / f"{n}_{fingerprint(old)}.json", old)
                fragment = ModuleCodegenRecord(module=n, workspace_file=str(self.stage5._workspace_file(n)))
                atomic_write_json(path, {"input_fingerprint": self._stage6_reuse_key(n, fragment, inputs),
                    "merged_fingerprint": fingerprint(self.stage6._merged_file(n).read_text()),
                    "accepted_debug_run": state["run_id"], "generation_source_fingerprint": binding["source_fingerprint"]})
            return True
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self.logger.info("[rtl_module_planner] Accepted debug generation binding not committed: %s", exc)
            return False

    def _reuse_stage6_merge_if_valid(
        self,
        module_name: str,
        stage5_record: ModuleCodegenRecord,
        codegen_stage_inputs=None,
    ):
        """Reuse existing stage6 merge if it exists, is non-empty, and passes Verilator syntax check."""
        fragment_file = Path(stage5_record.workspace_file)
        merged_file = self.stage6._merged_file(module_name)
        if not fragment_file.is_file() or not merged_file.is_file():
            return None
        try:
            stamp = json.loads(self._stage6_cache_path(module_name).read_text(encoding="utf-8"))
            if not codegen_stage_inputs:
                return None
            if stamp["merged_fingerprint"] != fingerprint(merged_file.read_text(encoding="utf-8")):
                return None
            current_key = self._stage6_reuse_key(module_name, stage5_record, codegen_stage_inputs)
            migration = None
            if stamp["input_fingerprint"] != current_key:
                # A preserved historical child tree must cryptographically bind
                # the old parent source. Equal full interfaces then permit a
                # one-time dependency implementation update without rewriting RTL.
                from .utils.stage5_sources import Stage5LogEvidence
                from zerorepo.rtl_impl.port_contracts import ansi_module_ports
                evidence = Stage5LogEvidence(self.output_root.parent.parent / "zerorepo.log")
                previous_interfaces = evidence._verified_stage6_children(module_name)
                repo = codegen_stage_inputs.get("stage2")
                repo_module = next((item for item in getattr(repo, "modules", []) if item.module == module_name), None)
                interfaces = []
                for child in sorted(getattr(repo_module, "children", [])):
                    child_file = self.stage6._merged_file(child)
                    ports = ansi_module_ports(child_file.read_text())
                    interfaces.append({"module": child, "ports": sorted([
                        {"name": p.name, "direction": p.direction, "width": p.width} for p in ports], key=lambda p: p["name"])})
                if not previous_interfaces or previous_interfaces != interfaces:
                    return None
                migration = {"old_input_fingerprint": stamp["input_fingerprint"],
                             "proof": "historical_stage6_source_and_equal_complete_child_interfaces"}
        except (OSError, ValueError, KeyError, TypeError):
            return None
        code = merged_file.read_text(encoding="utf-8").replace("\r\n", "\n")
        if not code.strip():
            self.logger.info(
                "[rtl_module_planner] Existing stage6 merge for %s is empty; regenerating",
                module_name,
            )
            return None
        self.stage6._ensure_toolchain_path()
        # check_syntax globs all .v files in the directory — use a temp copy
        # of just this module to avoid MULTITOP / cross-module errors.
        syntax_ok, syntax_output = _check_single_file_syntax(
            str(merged_file), top_module=module_name,
        )
        if not syntax_ok:
            self.logger.info(
                "[rtl_module_planner] Existing stage6 merge for %s fails Verilator syntax; regenerating: %s",
                module_name,
                self.stage6._summarize_syntax_output(syntax_output),
            )
            return None
        if migration:
            atomic_write_json(self.output_root / ".repair_cache" / "stage6_history" / f"{module_name}_{stamp['input_fingerprint']}.json", stamp)
            atomic_write_json(self._stage6_cache_path(module_name), {
                **stamp, "input_fingerprint": current_key, "migration_evidence": migration,
            })
            self.logger.info("[rtl_module_planner] Migrated verified Stage6 dependency binding for %s; RTL unchanged", module_name)
        return ModuleMergeRecord(
            module=module_name,
            fragment_file=str(fragment_file),
            merged_file=str(merged_file),
        )

    def _compact_stage1_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._drop_text_grounding(payload, preserve_fact_ledger=True)

    def _drop_text_grounding(self, value: Any, *, preserve_fact_ledger: bool = False) -> Any:
        if isinstance(value, dict):
            if preserve_fact_ledger and {"facts", "ambiguous_items", "source_files"}.issubset(value.keys()):
                return value
            return {
                key: self._drop_text_grounding(item, preserve_fact_ledger=preserve_fact_ledger)
                for key, item in value.items()
                if key != "text_grounding"
            }
        if isinstance(value, list):
            return [self._drop_text_grounding(item, preserve_fact_ledger=preserve_fact_ledger) for item in value]
        return value

    def _compact_repo_skeleton_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        compact = dict(payload)
        if compact.get("module_order") == []:
            compact.pop("module_order", None)
        return compact

    def _default_checkpoint_dir(self) -> Path:
        if self.output_root.name == "outputs" and self.output_root.parent.name == "module_planner":
            return self.output_root.parent.parent
        return self.output_root.parent
