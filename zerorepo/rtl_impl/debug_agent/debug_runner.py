from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from shutil import which
from typing import Any, Callable, Literal

from .bash_tools import CommandResult
from .config import OpenAIConfig, load_openai_config
from .sim_reviewer import SimReviewer


DebugStatus = Literal["disabled", "skipped", "pass", "fixed", "fail", "error"]


@dataclass(frozen=True)
class RtlDebugConfig:
    enabled: bool = True
    oracle_root: str = "/home/mokita/RealBench"
    max_trials: int = 30
    allow_failure: bool = False
    enable_asserter: bool = True
    enable_boolean_proofer: bool = True
    toolchain_bin: str = ""
    openai_config: OpenAIConfig | None = None

    @classmethod
    def from_env(cls) -> "RtlDebugConfig":
        enabled_env = os.environ.get("ZEROREPO_RTL_DEBUG", "1").strip().lower()
        allow_failure_env = os.environ.get("ZEROREPO_RTL_DEBUG_ALLOW_FAILURE", "0").strip().lower()
        return cls(
            enabled=enabled_env not in {"0", "false", "no", "off"},
            oracle_root=os.environ.get("ZEROREPO_RTL_DEBUG_ORACLE_ROOT", cls.oracle_root),
            max_trials=int(os.environ.get("ZEROREPO_RTL_DEBUG_MAX_TRIALS", str(cls.max_trials))),
            allow_failure=allow_failure_env not in {"0", "false", "no", "off"},
            enable_asserter=os.environ.get("ZEROREPO_RTL_DEBUG_ASSERTER", "1").strip().lower()
            not in {"0", "false", "no", "off"},
            enable_boolean_proofer=os.environ.get("ZEROREPO_RTL_DEBUG_BOOLEAN_PROOFER", "1").strip().lower()
            not in {"0", "false", "no", "off"},
            toolchain_bin=os.environ.get("ZEROREPO_RTL_DEBUG_TOOLCHAIN_BIN", ""),
            openai_config=load_openai_config(),
        )


def _resolve_oracle_dir(oracle_root: Path, module_name: str) -> Path | None:
    """Resolve the verification directory for *module_name* under *oracle_root*.

    Resolution order:
    1. Direct:  oracle_root / module_name / "verification"
    2. Dynamic: oracle_root / <any_subdir> / module_name / "verification"

    Returns the first matching Path, or None if not found.
    """
    # Step 1: direct lookup (backward-compatible with category-specific roots)
    direct = oracle_root / module_name / "verification"
    if direct.is_dir():
        return direct

    # Step 2: scan immediate subdirectories
    if not oracle_root.is_dir():
        return None

    try:
        for subdir in sorted(oracle_root.iterdir()):
            if not subdir.is_dir():
                continue
            candidate = subdir / module_name / "verification"
            if candidate.is_dir():
                return candidate
    except OSError:
        return None

    return None


@dataclass(frozen=True)
class ModuleDebugResult:
    module: str
    status: DebugStatus
    mismatch_count: int = 0
    debug_trials: int = 0
    workdir: str = ""
    final_rtl_path: str = ""
    trace_report_path: str = ""
    sim_output_path: str = ""
    reason: str = ""


class ModuleDebugRunner:
    def __init__(
        self,
        *,
        config: RtlDebugConfig | None = None,
        workspace_root: str | Path,
        logger: Any | None = None,
        kg_service: Any | None = None,
        initial_result_recorder: Callable[[str, str | Path, ModuleDebugResult], Any] | None = None,
    ) -> None:
        self.config = config or RtlDebugConfig.from_env()
        self.workspace_root = Path(workspace_root)
        self.debug_root = self.workspace_root / "debug"
        self.logger = logger
        self.kg_service = kg_service
        self.initial_result_recorder = initial_result_recorder

    def run_module(
        self,
        *,
        module_name: str,
        merged_file: str | Path,
        task: Any,
        spec_text: str,
        contract_json: str,
        spec_source_path: str | None = None,
    ) -> ModuleDebugResult:
        del task
        if not self.config.enabled:
            return ModuleDebugResult(module=module_name, status="disabled", reason="RTL debug is disabled.")

        oracle_root_path = Path(self.config.oracle_root)
        oracle_dir = _resolve_oracle_dir(oracle_root_path, module_name)
        if oracle_dir is None:
            return ModuleDebugResult(
                module=module_name,
                status="skipped",
                reason=(
                    f"Oracle directory not found: no {module_name}/verification "
                    f"under {oracle_root_path} or its immediate subdirectories"
                ),
            )

        workdir = (self.debug_root / module_name).resolve()
        try:
            self._ensure_toolchain_path()
            self._prepare_workdir(
                module_name=module_name,
                merged_file=Path(merged_file),
                oracle_dir=oracle_dir,
                workdir=workdir,
                contract_json=contract_json,
                spec_source_path=spec_source_path,
            )
            sim_reviewer = SimReviewer(str(workdir), str(workdir / "support.sv"))
            is_pass, mismatch_count, sim_output = sim_reviewer.review()
            self._write_text(workdir / "initial_sim_output.json", sim_output)
            initial_result = self._initial_debug_result(
                module_name=module_name,
                is_pass=is_pass,
                mismatch_count=mismatch_count,
                sim_output=sim_output,
                workdir=workdir,
            )
            self._record_initial_result(
                module_name=module_name,
                merged_file=merged_file,
                result=initial_result,
            )
            if is_pass:
                return initial_result
            if mismatch_count <= 0:
                return initial_result

            final_pass, _rtl_code, used_trials = self._run_editor(
                sim_reviewer=sim_reviewer,
                spec_text=spec_text,
                workdir=workdir,
                sim_output=sim_output,
                mismatch_count=mismatch_count,
                contract_json=contract_json,
                behavior_source="spec_tb",
            )
            final_rtl = workdir / "rtl.sv"
            trace_report = workdir / "trace_report.json"
            debug_sim_output = workdir / "debug_sim_output.json"
            if final_pass:
                shutil.copyfile(final_rtl, Path(merged_file))
                return ModuleDebugResult(
                    module=module_name,
                    status="fixed",
                    mismatch_count=0,
                    debug_trials=int(used_trials),
                    workdir=str(workdir),
                    final_rtl_path=str(final_rtl),
                    trace_report_path=str(trace_report) if trace_report.exists() else "",
                    sim_output_path=str(debug_sim_output) if debug_sim_output.exists() else str(workdir / "initial_sim_output.json"),
                )
            return ModuleDebugResult(
                module=module_name,
                status="fail",
                mismatch_count=int(mismatch_count),
                debug_trials=int(used_trials),
                workdir=str(workdir),
                final_rtl_path=str(final_rtl),
                trace_report_path=str(trace_report) if trace_report.exists() else "",
                sim_output_path=str(debug_sim_output) if debug_sim_output.exists() else str(workdir / "initial_sim_output.json"),
                reason="Debug trials ended without passing simulation.",
            )
        except Exception as exc:  # noqa: BLE001
            result = ModuleDebugResult(
                module=module_name,
                status="error",
                workdir=str(workdir),
                final_rtl_path=str(workdir / "rtl.sv"),
                reason=f"{type(exc).__name__}: {exc}",
            )
            if not self.config.allow_failure:
                raise RuntimeError(result.reason) from exc
            return result

    def _prepare_workdir(
        self,
        *,
        module_name: str,
        merged_file: Path,
        oracle_dir: Path,
        workdir: Path,
        contract_json: str,
        spec_source_path: str | None,
    ) -> None:
        if not merged_file.is_file():
            raise FileNotFoundError(f"Merged RTL not found: {merged_file}")
        if workdir.exists():
            shutil.rmtree(workdir)
        workdir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(merged_file, workdir / "rtl.sv")
        stage1_contract_path = workdir / "stage1_contract.json"
        self._write_text(stage1_contract_path, contract_json.rstrip() + "\n")
        self._write_text(workdir / "contract.json", contract_json.rstrip() + "\n")

        tb_path = self._select_testbench(oracle_dir, module_name)
        shutil.copyfile(tb_path, workdir / "tb.sv")
        support_text = self._build_support_text(oracle_dir, module_name, tb_path)
        self._write_text(workdir / "support.sv", support_text)
        self._copy_support_files_to_workdir(oracle_dir, module_name, tb_path, workdir)
        manifest = {
            "module": module_name,
            "oracle_dir": str(oracle_dir),
            "merged_file": str(merged_file),
            "testbench": str(tb_path),
            "support_file": str(workdir / "support.sv"),
            "stage1_contract_path": str(stage1_contract_path),
            "spec_source_path": spec_source_path or "",
            "debug_behavior_source": "original_spec_and_visible_tb",
            "diagnostic_metadata_source": "stage1",
            "tb_visibility": "tb_only",
        }
        self._write_text(workdir / "debug_input_manifest.json", json.dumps(manifest, indent=2) + "\n")

    def _initial_debug_result(
        self,
        *,
        module_name: str,
        is_pass: bool,
        mismatch_count: int,
        sim_output: str,
        workdir: Path,
    ) -> ModuleDebugResult:
        if is_pass:
            return ModuleDebugResult(
                module=module_name,
                status="pass",
                mismatch_count=0,
                workdir=str(workdir),
                final_rtl_path=str(workdir / "rtl.sv"),
                sim_output_path=str(workdir / "initial_sim_output.json"),
            )
        reason = "" if mismatch_count > 0 else self._summarize_command_result(sim_output)
        return ModuleDebugResult(
            module=module_name,
            status="fail",
            mismatch_count=max(0, int(mismatch_count)),
            workdir=str(workdir),
            final_rtl_path=str(workdir / "rtl.sv"),
            sim_output_path=str(workdir / "initial_sim_output.json"),
            reason=reason,
        )

    def _record_initial_result(
        self,
        *,
        module_name: str,
        merged_file: str | Path,
        result: ModuleDebugResult,
    ) -> None:
        if self.initial_result_recorder is None:
            return
        try:
            self.initial_result_recorder(module_name, merged_file, result)
        except Exception as exc:  # noqa: BLE001
            if self.logger is not None:
                self.logger.warning(
                    "[rtl_module_planner] Initial simulation KG record failed for %s: %s",
                    module_name,
                    exc,
                )

    def _ensure_toolchain_path(self) -> None:
        if which("verilator"):
            return
        candidates = [
            Path(self.config.toolchain_bin).expanduser() if self.config.toolchain_bin else None,
            Path("/home/mokita/miniconda3/envs/realbench/bin"),
            Path("/home/mokita/miniconda3/bin"),
        ]
        for candidate in candidates:
            if candidate is None:
                continue
            verilator = candidate / "verilator"
            if verilator.is_file():
                os.environ["PATH"] = f"{candidate}{os.pathsep}{os.environ.get('PATH', '')}"
                return

    def _select_testbench(self, oracle_dir: Path, module_name: str) -> Path:
        candidates = sorted(oracle_dir.glob(f"{module_name}_testbench.sv")) or sorted(oracle_dir.glob("*testbench.sv"))
        if not candidates:
            raise FileNotFoundError(f"No testbench found in {oracle_dir}")
        return candidates[0]

    def _select_support_files(self, oracle_dir: Path, module_name: str, tb_path: Path) -> list[Path]:
        source_files = sorted(
            path
            for path in oracle_dir.iterdir()
            if path.is_file() and path.suffix in {".sv", ".v"} and path != tb_path
        )
        selected: list[Path] = []
        for path in source_files:
            stem = path.stem
            if stem == module_name or stem == f"{module_name}_top" or stem.endswith("_top"):
                continue
            selected.append(path)
        return selected

    def _build_support_text(self, oracle_dir: Path, module_name: str, tb_path: Path) -> str:
        selected = self._select_support_files(oracle_dir, module_name, tb_path)
        chunks = [f"// support source: {path.name}\n{path.read_text(encoding='utf-8')}" for path in selected]
        return "\n\n".join(chunks).rstrip() + "\n"

    def _copy_support_files_to_workdir(self, oracle_dir: Path, module_name: str, tb_path: Path, workdir: Path) -> None:
        # Only copy files that are referenced by `include directives from the
        # testbench or support files.  Copying all support files would duplicate
        # modules already concatenated into support.sv, breaking check_syntax.
        include_names: set[str] = set()
        include_re = re.compile(r"^\s*`include\s+\"(.+?)\"", re.MULTILINE)
        for src_path in [tb_path, *self._select_support_files(oracle_dir, module_name, tb_path)]:
            try:
                text = src_path.read_text(encoding="utf-8")
            except OSError:
                continue
            for m in include_re.finditer(text):
                include_names.add(m.group(1))

        for sf in self._select_support_files(oracle_dir, module_name, tb_path):
            if sf.name in include_names:
                shutil.copyfile(sf, workdir / sf.name)

    def _run_editor(
        self,
        *,
        sim_reviewer: SimReviewer,
        spec_text: str,
        workdir: Path,
        sim_output: str,
        mismatch_count: int,
        contract_json: str,
        behavior_source: Literal["contract", "spec_tb"] = "contract",
    ) -> tuple[bool, str, int]:
        try:
            from .rtl_editor import RTLEditor
        except ModuleNotFoundError as exc:
            if exc.name == "agentscope":
                raise ModuleNotFoundError(
                    "Missing Python dependency 'agentscope'. Install RTL debug dependencies with "
                    "`python -m pip install -r requirements.txt` in the environment that runs ZeroRepo."
                ) from exc
            raise

        cfg = self.config.openai_config or load_openai_config()
        editor = RTLEditor(
            cfg,
            sim_reviewer=sim_reviewer,
            max_trials=int(self.config.max_trials),
            enable_asserter=bool(self.config.enable_asserter),
            enable_boolean_proofer=bool(self.config.enable_boolean_proofer),
            kg_service=self.kg_service,
        )
        return self._run_async(
            editor.chat(
                spec=spec_text,
                output_dir_per_run=str(workdir),
                sim_failed_log=sim_output,
                sim_mismatch_cnt=int(mismatch_count),
                contract_json=contract_json,
                behavior_source=behavior_source,
                max_trials=int(self.config.max_trials),
            )
        )

    def _run_async(self, coroutine: Any) -> Any:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coroutine)

        result: dict[str, Any] = {}

        def runner() -> None:
            try:
                result["value"] = asyncio.run(coroutine)
            except BaseException as exc:  # noqa: BLE001
                result["error"] = exc

        import threading

        thread = threading.Thread(target=runner)
        thread.start()
        thread.join()
        if "error" in result:
            raise result["error"]
        return result["value"]

    def _summarize_command_result(self, sim_output: str) -> str:
        try:
            obj = CommandResult.model_validate_json(sim_output)
            text = "\n".join(part for part in [obj.stdout, obj.stderr] if part)
        except Exception:  # noqa: BLE001
            text = sim_output
        text = text.strip()
        if len(text) > 2000:
            text = text[:2000] + "\n...<snip>..."
        return text

    def _write_text(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def module_debug_result_to_dict(result: ModuleDebugResult) -> dict[str, Any]:
    return asdict(result)
