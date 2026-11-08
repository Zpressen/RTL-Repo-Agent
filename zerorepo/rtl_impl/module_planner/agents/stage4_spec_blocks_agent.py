from __future__ import annotations


import re
from pathlib import Path
from typing import Any, Dict, List


from ..schemas import (
    ModuleSpecBlocks,
    PlannerTaskInput,
    Stage2RepoSkeletonArtifact,
    Stage3ModuleSkeletonArtifact,
    Stage4SpecBlocksArtifact,
)
from ..utils import interface_contract_errors, markdown_ports
from .base import BaseStageAgent, validate_model


class Stage4SpecBlocksAgent(BaseStageAgent):
    stage_name = "stage4_spec_blocks"
    output_model = Stage4SpecBlocksArtifact

    def __init__(
        self,
        llm_client,
        context_provider=None,
        artifact_sink=None,
        logger=None,
        output_root: str | Path | None = None,
        retrieval_limits: dict | None = None,
    ):
        super().__init__(llm_client, context_provider, artifact_sink, logger)
        self.output_root = Path(output_root) if output_root is not None else None

    def run(self, task_input: Any, partial_artifacts: Dict[str, Any]) -> Stage4SpecBlocksArtifact:
        task = task_input if isinstance(task_input, PlannerTaskInput) else validate_model(PlannerTaskInput, task_input)
        repo_skeleton = self._get_repo_skeleton_artifact(partial_artifacts)
        stage3 = self._get_stage3_artifact(partial_artifacts)
        module_order = self._generation_order(repo_skeleton)

        if stage3.module_order != module_order:
            raise ValueError(
                "Stage4 spec block splitting requires stage3.module_order to match "
                "repo_skeleton.planning_decisions.generation_order"
            )

        modules: List[ModuleSpecBlocks] = []
        from ..utils.evidence import EvidenceRegistry
        registry = EvidenceRegistry(partial_artifacts["stage2_input"])
        registry.register_tree(partial_artifacts["stage2_decomposition"])
        for module_name in module_order:
            from ..utils.responsibility_planning import module_context
            context = module_context(partial_artifacts["stage2_decomposition"], module_name)
            from ..schemas import ModuleSkeletonExport
            from ..utils.spec_mapping import module_spec_blocks
            record = next(r for r in stage3.module_records if r.module == module_name)
            export = ModuleSkeletonExport.model_validate_json((self.output_root / record.export_file).read_text(encoding="utf-8"))
            bundle = next(m for m in partial_artifacts["modules"].modules if m.module == module_name)
            modules.append(module_spec_blocks(export, context, bundle, registry))

        artifact = Stage4SpecBlocksArtifact(
            schema_version="spec_blocks_v2",
            task_id=task.task_id,
            module_order=module_order,
            modules=modules,
        )
        quality_errors = self.validate_quality(artifact, task, partial_artifacts)
        if quality_errors:
            raise ValueError(f"{self.stage_name} output failed quality checks: {quality_errors}")
        registry.save(self.output_root)
        self.logger.info(
            "[%s] Split %d module spec(s) into %d block(s)",
            self.stage_name,
            len(artifact.modules),
            sum(len(module.blocks) for module in artifact.modules),
        )
        self.artifact_sink.record_stage_output(self.stage_name, artifact, task)
        return artifact

    def build_prompt(self, task_input: Any, partial_artifacts: Dict[str, Any], stage_context: Dict[str, Any]):
        raise NotImplementedError("Stage4SpecBlocksAgent is deterministic and does not build prompts.")

    def validate_quality(
        self,
        artifact: Stage4SpecBlocksArtifact,
        task_input: PlannerTaskInput,
        partial_artifacts: Dict[str, Any],
    ) -> List[str]:
        repo_skeleton = self._get_repo_skeleton_artifact(partial_artifacts)
        expected_order = self._generation_order(repo_skeleton)
        errors: List[str] = []
        if artifact.schema_version != "spec_blocks_v2":
            errors.append("schema_version must remain spec_blocks_v2")
        if artifact.task_id != task_input.task_id:
            errors.append(f"task_id must remain {task_input.task_id}")
        if artifact.module_order != expected_order:
            errors.append("module_order must equal repo_skeleton.planning_decisions.generation_order")
        if [item.module for item in artifact.modules] != artifact.module_order:
            errors.append("modules[].module must exactly match module_order")
        for module in artifact.modules:
            if not module.blocks:
                errors.append(f"{module.module}: blocks must not be empty")
                continue
            for index, block in enumerate(module.blocks, start=1):
                expected_id = f"S{index:03d}"
                if block.block_id != expected_id:
                    errors.append(f"{module.module}: expected block_id {expected_id}, got {block.block_id}")
                if not block.text.strip():
                    errors.append(f"{module.module}: {block.block_id} text must not be empty")
        top_module = repo_skeleton.top_module
        top_blocks = next((item for item in artifact.modules if item.module == top_module), None)
        expected_ports = self._top_interface_ports(partial_artifacts, top_module)
        if top_blocks is not None and expected_ports:
            block_text = "\n\n".join(block.text for block in top_blocks.blocks)
            retrieved_ports = markdown_ports(block_text)
            if retrieved_ports:
                errors.extend(
                    interface_contract_errors(
                        retrieved_ports,
                        expected_ports,
                        label=f"top spec blocks `{top_module}`",
                    )
                )
            else:
                missing = [
                    port.name
                    for port in expected_ports
                    if not re.search(rf"\b{re.escape(port.name)}\b", block_text)
                ]
                if missing:
                    errors.append(f"{top_module}: top spec blocks are missing interface ports {missing}")
        return errors

    def _generation_order(self, repo_skeleton: Stage2RepoSkeletonArtifact) -> List[str]:
        module_order = [str(item).strip() for item in repo_skeleton.planning_decisions.generation_order if str(item).strip()]
        if not module_order:
            raise ValueError("Stage4 spec block splitting requires repo_skeleton.planning_decisions.generation_order")
        return module_order

    def _top_interface_ports(self, partial_artifacts: Dict[str, Any], top_module: str) -> List[Any]:
        modules = partial_artifacts.get("modules")
        bundles = getattr(modules, "modules", None)
        if bundles is None and isinstance(modules, dict):
            bundles = modules.get("modules")
        for bundle in bundles or []:
            module_name = bundle.get("module") if isinstance(bundle, dict) else getattr(bundle, "module", "")
            if module_name != top_module:
                continue
            contract = (
                bundle.get("interface_contract")
                if isinstance(bundle, dict)
                else getattr(bundle, "interface_contract", None)
            )
            if contract is None:
                return []
            return list(contract.get("ports") if isinstance(contract, dict) else getattr(contract, "ports", []))
        return []

    def _get_repo_skeleton_artifact(self, partial_artifacts: Dict[str, Any]) -> Stage2RepoSkeletonArtifact:
        candidate = partial_artifacts.get("stage2")
        if candidate is None:
            raise ValueError("Stage4 spec block splitting requires partial_artifacts['stage2']")
        if isinstance(candidate, Stage2RepoSkeletonArtifact):
            return candidate
        return validate_model(Stage2RepoSkeletonArtifact, candidate)

    def _get_stage3_artifact(self, partial_artifacts: Dict[str, Any]) -> Stage3ModuleSkeletonArtifact:
        candidate = partial_artifacts.get("stage3")
        if candidate is None:
            raise ValueError("Stage4 spec block splitting requires partial_artifacts['stage3']")
        if isinstance(candidate, Stage3ModuleSkeletonArtifact):
            return candidate
        return validate_model(Stage3ModuleSkeletonArtifact, candidate)
