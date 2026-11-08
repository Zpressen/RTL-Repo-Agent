"""Canonical, case-relative paths for the RTL planner pipeline.

Artifact names are logical keys, not legacy filesystem lookup fallbacks. Every
writer and reader resolves them through this layout; old cases are never moved.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

LAYOUT_VERSION = 1

_ARTIFACTS = {
    "contracts.json": "plan/stage1/contracts.json",
    "modules.json": "plan/stage2/modules.json",
    "repo_skeleton.json": "plan/stage2/repo_skeleton.json",
    "stage2_decomposition.json": "plan/stage2/stage2_decomposition.json",
    "module_skeletons.json": "plan/stage3/module_skeletons.json",
    "spec_blocks.json": "plan/stage4/spec_blocks.json",
    "module_plans.json": "plan/stage4/module_plans.json",
    "planning_gate_report.json": "plan/stage4/planning_gate_report.json",
    "stage5_codegen.json": "generate/metadata/stage5_codegen.json",
    "stage6_merge.json": "generate/metadata/stage6_merge.json",
    "planning_code_consistency.json": "generate/metadata/planning_code_consistency.json",
    "global_defines_manifest.json": "generate/metadata/global_defines_manifest.json",
    "system_debug_latest.json": "debug/system_debug_latest.json",
    "resume_recovery_report.json": "plan/state/resume_recovery_report.json",
    "global_temporal_facts.json": "plan/state/global_temporal_facts.json",
    "architecture_timing_contract.json": "plan/state/architecture_timing_contract.json",
    "module_timing_bindings.json": "plan/state/module_timing_bindings.json",
    "timing_binding_check.json": "plan/state/timing_binding_check.json",
}
_DIRECTORIES = {
    "merged": "generate/rtl",
    "fragments": "generate/fragments",
    "merge_reports": "generate/metadata/merge_reports",
    "merge_drafts": "generate/traces/merge_drafts",
    "merge_journal": "generate/traces/merge_journal",
    "merge_retrieval_json": "generate/metadata/merge_retrieval",
    "merge_child_context_json": "generate/metadata/child_context",
    ".stage5_candidates": "generate/state/candidates",
    ".stage5_generations": "generate/state/generations",
    ".stage5_history": "generate/state/history",
    ".stage5_publish": "generate/state/publish",
    ".debug_generations": "debug/state/generations",
    "debug": "debug/modules",
    "debug_system": "debug/system",
    "rtl_memory": "debug/memory",
    "repo_react": "debug/traces/repo_react",
    "planning_corrections": "debug/planning_corrections",
    "module_timing_binding_json": "plan/state/timing_bindings",
}


@dataclass(frozen=True)
class ArtifactLayout:
    case_root: Path

    def __post_init__(self):
        object.__setattr__(self, "case_root", Path(self.case_root))

    def artifact(self, name: str) -> Path:
        return self.case_root / _ARTIFACTS[name]

    def directory(self, name: str) -> Path:
        return self.case_root / _DIRECTORIES[name]

    @property
    def rtl(self) -> Path:
        return self.directory("merged")

    @property
    def checkpoint(self) -> Path:
        return self.case_root / "plan/state/kg"

    def module(self, stage: int, module: str, filename: str) -> Path:
        if Path(module).name != module or module in {"", ".", ".."}:
            raise ValueError(f"Invalid module path: {module!r}")
        return self.case_root / f"plan/stage{stage}/modules" / module / filename

    def module_relative(self, stage: int, module: str, filename: str) -> str:
        return self.module(stage, module, filename).relative_to(self.case_root).as_posix()

    def stage5_checkpoint(self, module: str) -> Path:
        return self.case_root / "generate/state/checkpoints" / f"{module}.json"

    def stage5_contracts(self, module: str) -> Path:
        return self.case_root / "generate/metadata/contracts" / f"{module}.json"

    def merge_inputs(self, module: str) -> Path:
        return self.case_root / "generate/state/merge_inputs" / f"{module}.json"

    def cache(self, kind: str) -> Path:
        if kind in {"accepted_debug_generation.json", "pending_debug_generation.json"}:
            return self.case_root / "debug/state" / kind
        if kind.startswith("stage6"):
            return self.case_root / "generate/state" / kind
        return self.case_root / "plan/state/cache" / kind

    def traces(self, stage: str, kind: str = "requests") -> Path:
        group = "generate" if stage.startswith(("stage5", "stage6")) else "plan"
        return self.case_root / group / "traces" / kind / stage

    def paths(self, value, *, absolute: bool = False):
        """Encode public manifest paths relative to the case; hydrate at APIs.

        Call only on artifact manifests/reports, not signed source snapshots or
        debug session descriptors, whose representation is part of their hash.
        """
        keys = {"workspace_file", "fragment_file", "merged_file", "contracts_file",
                "final_rtl_path", "workdir", "trace_report_path", "sim_output_path",
                "runtime_rtl_path", "generated_dir", "workspace_path", "draft_file"}
        if isinstance(value, list):
            return [self.paths(item, absolute=absolute) for item in value]
        if not isinstance(value, dict):
            return value
        result = {}
        for key, item in value.items():
            if key in keys and isinstance(item, str) and item:
                path = Path(item)
                if absolute and not path.is_absolute():
                    item = str(self.resolve(item))
                elif not absolute and path.is_absolute() and path.is_relative_to(self.case_root.resolve()):
                    item = path.relative_to(self.case_root.resolve()).as_posix()
                result[key] = item
            else:
                result[key] = self.paths(item, absolute=absolute)
        return result

    def resolve(self, relative: str) -> Path:
        path = (self.case_root / relative).resolve()
        if not path.is_relative_to(self.case_root.resolve()):
            raise ValueError(f"Artifact path escapes case directory: {relative}")
        return path


def artifact_path(root: str | Path, name: str) -> Path:
    return ArtifactLayout(Path(root)).artifact(name)


def artifact_dir(root: str | Path, name: str) -> Path:
    return ArtifactLayout(Path(root)).directory(name)
