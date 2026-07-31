from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import sys
import textwrap
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .bash_tools import CommandResult, run_bash_command
from .config import load_openai_config
from .debug_runner import DebugStatus, RtlDebugConfig
from .sim_reviewer import sim_review_mismatch_cnt
from .utils import clip_text


@dataclass(frozen=True)
class SystemDebugResult:
    top_module: str
    status: DebugStatus
    planner_top_module: str = ""
    dut_instance: str = ""
    runtime_rtl_path: str = ""
    mismatch_count: int = 0
    debug_trials: int = 0
    workdir: str = ""
    generated_dir: str = ""
    verify_dir: str = ""
    verify_script: str = ""
    sim_output_path: str = ""
    trace_report_path: str = ""
    reason: str = ""


class SystemSimReviewer:
    def __init__(
        self,
        *,
        generated_dir: str | Path,
        verify_script: str | Path,
        output_dir: str | Path,
        timeout: int = 300,
    ) -> None:
        self.generated_dir = Path(generated_dir)
        self.verify_script = Path(verify_script)
        self.output_dir = Path(output_dir)
        self.timeout = int(timeout)

    def review(self) -> tuple[bool, int, str]:
        wrapper = self._write_wrapper()
        cmd = " ".join(
            [
                shlex.quote(sys.executable),
                shlex.quote(str(wrapper)),
                shlex.quote(str(self.verify_script)),
                shlex.quote(str(self.generated_dir)),
                shlex.quote(str(self.output_dir)),
            ]
        )
        passed, output = run_bash_command(cmd, timeout=self.timeout, cwd=str(self.output_dir))
        try:
            obj = CommandResult.model_validate_json(output)
            stdout = obj.stdout or ""
            stderr = obj.stderr or ""
        except Exception:  # noqa: BLE001
            stdout = output
            stderr = ""
        mismatch_count = sim_review_mismatch_cnt(stdout)
        if mismatch_count == 0:
            m = re.search(
                r"Hint:\s+Total mismatched samples is\s+(\d+)\s+out of\s+\d+\s+samples",
                stdout,
            )
            if m:
                mismatch_count = int(m.group(1))
        is_pass = bool(passed) and "PASS" in stdout and "FAIL" not in stdout
        if not is_pass and mismatch_count == 0 and re.search(r"\bFAIL\b|%Error|error:", f"{stdout}\n{stderr}", re.IGNORECASE):
            mismatch_count = 0
        return is_pass, int(mismatch_count), output

    def _write_wrapper(self) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        wrapper = self.output_dir / "system_verify_wrapper.py"
        wrapper.write_text(
            textwrap.dedent(
                r'''
                from __future__ import annotations

                import importlib.util
                import pathlib
                import shutil
                import sys
                import tempfile
                import traceback


                def main() -> int:
                    if len(sys.argv) != 4:
                        print("Usage: system_verify_wrapper.py <verify_script> <generated_dir> <output_dir>", file=sys.stderr)
                        return 2
                    verify_script = pathlib.Path(sys.argv[1]).resolve()
                    generated_dir = pathlib.Path(sys.argv[2]).resolve()
                    output_dir = pathlib.Path(sys.argv[3]).resolve()
                    output_dir.mkdir(parents=True, exist_ok=True)

                    created_dirs: list[pathlib.Path] = []
                    original_temporary_directory = tempfile.TemporaryDirectory

                    class KeepTemporaryDirectory:
                        def __init__(self, suffix=None, prefix=None, dir=None, ignore_cleanup_errors=False, delete=True):
                            del ignore_cleanup_errors, delete
                            self.name = tempfile.mkdtemp(suffix=suffix, prefix=prefix, dir=dir)
                            created_dirs.append(pathlib.Path(self.name))

                        def __enter__(self):
                            return self.name

                        def __exit__(self, exc_type, exc, tb):
                            return False

                        def cleanup(self):
                            return None

                    tempfile.TemporaryDirectory = KeepTemporaryDirectory
                    try:
                        spec = importlib.util.spec_from_file_location("_zerorepo_system_verify", verify_script)
                        if spec is None or spec.loader is None:
                            raise RuntimeError(f"Could not import verifier: {verify_script}")
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        verify_system = getattr(module, "verify_system", None)
                        if verify_system is None:
                            raise RuntimeError(f"Verifier does not expose verify_system(generated_dir): {verify_script}")
                        passed, message = verify_system(str(generated_dir))
                    except Exception:
                        traceback.print_exc()
                        return 1
                    finally:
                        tempfile.TemporaryDirectory = original_temporary_directory

                    copied_vcd = False
                    for temp_dir in created_dirs:
                        try:
                            for candidate in temp_dir.rglob("wave.vcd"):
                                shutil.copy2(candidate, output_dir / "wave.vcd")
                                print(f"ZEROREPO_VCD_COPIED: {candidate} -> {output_dir / 'wave.vcd'}")
                                copied_vcd = True
                                break
                        except OSError:
                            pass
                        if copied_vcd:
                            break

                    for temp_dir in created_dirs:
                        shutil.rmtree(temp_dir, ignore_errors=True)

                    print(message)
                    print("Summary:")
                    print(f"  system_verify: {'PASS' if passed else 'FAIL'}")
                    return 0 if passed else 1


                if __name__ == "__main__":
                    raise SystemExit(main())
                '''
            ).lstrip(),
            encoding="utf-8",
        )
        return wrapper


class SystemDebugRunner:
    def __init__(
        self,
        *,
        config: RtlDebugConfig | None = None,
        workspace_root: str | Path,
        output_root: str | Path | None = None,
        repo_root: str | Path | None = None,
        logger: Any | None = None,
        kg_service: Any | None = None,
    ) -> None:
        self.config = config or RtlDebugConfig.from_env()
        self.workspace_root = Path(workspace_root)
        self.output_root = Path(output_root) if output_root is not None else None
        self.repo_root = Path(repo_root) if repo_root is not None else Path.cwd()
        self.debug_root = self.workspace_root / "debug_system"
        self.logger = logger
        self.kg_service = kg_service

    def run_system(
        self,
        *,
        top_module: str,
        task: Any,
        spec_text: str,
        contract_json: str,
        merged_records: list[Any],
    ) -> SystemDebugResult:
        planner_top_module = str(top_module or "").strip()
        runtime_top_module = planner_top_module
        if not self.config.enabled:
            return SystemDebugResult(
                top_module=runtime_top_module,
                planner_top_module=planner_top_module,
                status="disabled",
                reason="RTL debug is disabled.",
            )
        if not planner_top_module:
            return SystemDebugResult(status="error", top_module="", reason="System-level debug requires a non-empty top module.")

        verify_dir = self._resolve_verify_dir(runtime_top_module)
        extra_top_rtl: Path | None = None
        if verify_dir is None:
            try:
                resolved = self._resolve_merged_top_alias(planner_top_module)
            except ValueError as exc:
                return SystemDebugResult(
                    top_module=runtime_top_module,
                    planner_top_module=planner_top_module,
                    status="error",
                    reason=str(exc),
                )
            if resolved is not None:
                runtime_top_module, verify_dir, extra_top_rtl = resolved
                if self.logger is not None:
                    self.logger.info(
                        "[rtl_system_debug] Using simulation top alias %s for planner top %s.",
                        runtime_top_module,
                        planner_top_module,
                    )
        if verify_dir is None:
            return SystemDebugResult(
                top_module=runtime_top_module,
                planner_top_module=planner_top_module,
                status="error",
                reason=(
                    f"System verify directory not found for {runtime_top_module}. "
                    f"Expected {self._default_verify_dir(runtime_top_module)}."
                ),
            )
        verify_script = self._select_verify_script(verify_dir)
        if verify_script is None:
            return SystemDebugResult(
                top_module=runtime_top_module,
                planner_top_module=planner_top_module,
                status="error",
                verify_dir=str(verify_dir),
                reason=f"No *_verify.py script found in {verify_dir}.",
            )

        workdir = (self.debug_root / runtime_top_module).resolve()
        generated_dir = workdir / "generated"
        try:
            dut_instance, runtime_rtl_path = self._prepare_workdir(
                planner_top_module=planner_top_module,
                runtime_top_module=runtime_top_module,
                workdir=workdir,
                generated_dir=generated_dir,
                verify_dir=verify_dir,
                verify_script=verify_script,
                merged_records=merged_records,
                contract_json=contract_json,
                extra_top_rtl=extra_top_rtl,
            )
            reviewer = SystemSimReviewer(generated_dir=generated_dir, verify_script=verify_script, output_dir=workdir)
            is_pass, mismatch_count, sim_output = reviewer.review()
            initial_sim_path = workdir / "initial_system_sim_output.json"
            initial_sim_path.write_text(sim_output, encoding="utf-8")
            if is_pass:
                return SystemDebugResult(
                    top_module=runtime_top_module,
                    planner_top_module=planner_top_module,
                    dut_instance=dut_instance,
                    runtime_rtl_path=str(runtime_rtl_path),
                    status="pass",
                    mismatch_count=0,
                    workdir=str(workdir),
                    generated_dir=str(generated_dir),
                    verify_dir=str(verify_dir),
                    verify_script=str(verify_script),
                    sim_output_path=str(initial_sim_path),
                )

            if self.logger is not None:
                self.logger.info(
                    "[rtl_system_debug] Top simulation failed for %s; starting repo-scope debug: %s",
                    runtime_top_module,
                    self._summarize_command_result(sim_output),
                )
            final_pass, used_trials = self._run_repo_react(
                planner_top_module=planner_top_module,
                runtime_top_module=runtime_top_module,
                task=task,
                spec_text=spec_text,
                contract_json=contract_json,
                workdir=workdir,
                generated_dir=generated_dir,
                verify_dir=verify_dir,
                verify_script=verify_script,
                sim_output=sim_output,
                mismatch_count=mismatch_count,
                sim_reviewer=reviewer,
            )
            debug_sim_path = workdir / "debug_sim_output.json"
            self._sync_generated_to_merged(generated_dir)
            return SystemDebugResult(
                top_module=runtime_top_module,
                planner_top_module=planner_top_module,
                dut_instance=dut_instance,
                runtime_rtl_path=str(runtime_rtl_path),
                status="fixed" if final_pass else "fail",
                mismatch_count=0 if final_pass else int(mismatch_count),
                debug_trials=int(used_trials),
                workdir=str(workdir),
                generated_dir=str(generated_dir),
                verify_dir=str(verify_dir),
                verify_script=str(verify_script),
                sim_output_path=str(debug_sim_path if debug_sim_path.exists() else initial_sim_path),
                trace_report_path=str(workdir / "trace_report.json") if (workdir / "trace_report.json").exists() else "",
                reason="" if final_pass else "System debug trials ended without passing top simulation.",
            )
        except Exception as exc:  # noqa: BLE001
            result = SystemDebugResult(
                top_module=runtime_top_module,
                planner_top_module=planner_top_module,
                status="error",
                workdir=str(workdir),
                generated_dir=str(generated_dir),
                verify_dir=str(verify_dir) if verify_dir else "",
                verify_script=str(verify_script) if verify_script else "",
                reason=f"{type(exc).__name__}: {exc}",
            )
            if not self.config.allow_failure:
                raise RuntimeError(result.reason) from exc
            return result

    def _resolve_verify_dir(self, top_module: str) -> Path | None:
        candidate = self._default_verify_dir(top_module)
        if candidate.is_dir():
            return candidate
        return None

    def _resolve_merged_top_alias(self, planner_top: str) -> tuple[str, Path, Path] | None:
        """Resolve a simulation-only top alias without changing planner artifacts."""
        merged_dir = self.workspace_root / "merged"
        if not merged_dir.is_dir():
            return None
        matches: list[tuple[str, Path, Path]] = []
        for rtl_path in sorted([*merged_dir.glob("*.v"), *merged_dir.glob("*.sv")]):
            candidate_top = rtl_path.stem
            if candidate_top == planner_top:
                continue
            verify_dir = self._resolve_verify_dir(candidate_top)
            if verify_dir is None:
                continue
            try:
                source = rtl_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if re.search(rf"\bmodule\s+{re.escape(candidate_top)}\b", source) is None:
                continue
            matches.append((candidate_top, verify_dir, rtl_path))
        if len(matches) > 1:
            names = ", ".join(item[0] for item in matches)
            raise ValueError(
                f"Multiple simulation top aliases match planner top {planner_top}: {names}."
            )
        return matches[0] if matches else None

    def _default_verify_dir(self, top_module: str) -> Path:
        return Path(self.config.oracle_root) / "system_task" / top_module / "verify_test"

    def _select_verify_script(self, verify_dir: Path) -> Path | None:
        candidates = sorted(verify_dir.glob("*_verify.py"))
        if not candidates:
            candidates = sorted(verify_dir.glob("*verify*.py"))
        return candidates[0] if candidates else None

    def _prepare_workdir(
        self,
        *,
        planner_top_module: str,
        runtime_top_module: str,
        workdir: Path,
        generated_dir: Path,
        verify_dir: Path,
        verify_script: Path,
        merged_records: list[Any],
        contract_json: str,
        extra_top_rtl: Path | None = None,
    ) -> tuple[str, Path]:
        if workdir.exists():
            shutil.rmtree(workdir)
        generated_dir.mkdir(parents=True, exist_ok=True)
        copied: list[str] = []
        for record in merged_records:
            merged_file = Path(str(getattr(record, "merged_file", "") or ""))
            if not merged_file.is_file() or merged_file.suffix.lower() not in {".v", ".sv"}:
                continue
            dst = generated_dir / merged_file.name
            shutil.copyfile(merged_file, dst)
            copied.append(str(dst))
        if extra_top_rtl is not None and extra_top_rtl.is_file():
            dst = generated_dir / extra_top_rtl.name
            if str(dst) not in copied:
                shutil.copyfile(extra_top_rtl, dst)
                copied.append(str(dst))
        if not copied:
            raise FileNotFoundError("No merged RTL files were available for system debug.")

        runtime_rtl_path = next(
            (
                generated_dir / f"{runtime_top_module}{suffix}"
                for suffix in (".v", ".sv")
                if (generated_dir / f"{runtime_top_module}{suffix}").is_file()
            ),
            None,
        )
        if runtime_rtl_path is None:
            raise FileNotFoundError(
                f"Runtime top RTL for {runtime_top_module} was not copied into {generated_dir}."
            )
        runtime_source = runtime_rtl_path.read_text(encoding="utf-8", errors="ignore")
        if re.search(rf"\bmodule\s+{re.escape(runtime_top_module)}\b", runtime_source) is None:
            raise ValueError(
                f"Runtime RTL {runtime_rtl_path} does not declare module {runtime_top_module}."
            )

        tb_candidates = sorted(verify_dir.glob("*testbench*.sv")) + sorted(verify_dir.glob("*tb*.sv"))
        visible_tb = tb_candidates[0] if tb_candidates else None
        dut_instance = ""
        if visible_tb is not None:
            shutil.copyfile(visible_tb, workdir / "tb.sv")
            if visible_tb.name != "tb.sv":
                shutil.copyfile(visible_tb, workdir / visible_tb.name)
            tb_text = visible_tb.read_text(encoding="utf-8", errors="ignore")
            match = re.search(
                rf"\b{re.escape(runtime_top_module)}\b\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(",
                tb_text,
            )
            dut_instance = match.group(1) if match else ""
        (workdir / "contract.json").write_text(contract_json.rstrip() + "\n", encoding="utf-8")
        manifest = {
            "top_module": runtime_top_module,
            "planner_module_name": planner_top_module,
            "runtime_top_module": runtime_top_module,
            "dut_instance": dut_instance,
            "runtime_rtl_path": str(runtime_rtl_path),
            "generated_dir": str(generated_dir),
            "verify_dir": str(verify_dir),
            "verify_script": str(verify_script),
            "visible_testbench": str(visible_tb or ""),
            "generated_files": copied,
            "debug_behavior_source": "system_top_testbench",
            "golden_visibility": "hidden_by_verify_script",
        }
        (workdir / "debug_input_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        return dut_instance, runtime_rtl_path

    def _run_repo_react(
        self,
        *,
        planner_top_module: str,
        runtime_top_module: str,
        task: Any,
        spec_text: str,
        contract_json: str,
        workdir: Path,
        generated_dir: Path,
        verify_dir: Path,
        verify_script: Path,
        sim_output: str,
        mismatch_count: int,
        sim_reviewer: SystemSimReviewer,
    ) -> tuple[bool, int]:
        from zerorepo.rtl_impl.repo_react import RepoReActInput, RepoReActRunner

        cfg = self.config.openai_config or load_openai_config()
        spec_paths = []
        try:
            spec_paths = [str(item) for item in (getattr(task, "spec_md_files", []) or [])]
        except Exception:  # noqa: BLE001
            spec_paths = []
        top_rtl = self._select_top_rtl(generated_dir, runtime_top_module)
        output_root = self.output_root
        if output_root is None:
            candidate = self.workspace_root.parent / "outputs"
            output_root = candidate if candidate.exists() else None
        stage_artifacts = {
            name: str(output_root / filename)
            for name, filename in {
                "contracts": "contracts.json",
                "modules": "modules.json",
                "repo_skeleton": "repo_skeleton.json",
                "module_skeletons": "module_skeletons.json",
                "spec_blocks": "spec_blocks.json",
                "module_plans": "module_plans.json",
                "stage5_codegen": "stage5_codegen.json",
                "stage6_merge": "stage6_merge.json",
            }.items()
            if output_root is not None
        }
        runner = RepoReActRunner(
            cfg,
            sim_reviewer=sim_reviewer,
            kg_service=self.kg_service,
            max_steps=int(self.config.max_trials),
            logger=self.logger,
        )
        repo_input = RepoReActInput(
            module_name=planner_top_module,
            top_module=runtime_top_module,
            repair_scope="repo",
            repair_mode="functional",
            workspace_root=self.workspace_root,
            debug_workdir=workdir,
            rtl_path=top_rtl,
            merged_file=(self.workspace_root / "merged" / top_rtl.name),
            rtl_root=generated_dir,
            verify_dir=verify_dir,
            verify_script=verify_script,
            output_root=output_root,
            repo_root=self.repo_root,
            spec_text=spec_text,
            spec_source_path=spec_paths[0] if spec_paths else "",
            spec_paths=spec_paths,
            contract_json=contract_json,
            sim_failed_log=sim_output,
            initial_mismatch_count=int(mismatch_count),
            max_steps=int(self.config.max_trials),
            stage_artifacts=stage_artifacts,
        )
        result = self._run_async(runner.chat(repo_input))
        return bool(result.is_pass), int(result.action_calls)

    def _select_top_rtl(self, generated_dir: Path, top_module: str) -> Path:
        for suffix in (".v", ".sv"):
            candidate = generated_dir / f"{top_module}{suffix}"
            if candidate.is_file():
                return candidate
        candidates = sorted([*generated_dir.glob("*.v"), *generated_dir.glob("*.sv")])
        if not candidates:
            raise FileNotFoundError(f"No generated RTL found in {generated_dir}")
        return candidates[0]

    def _sync_generated_to_merged(self, generated_dir: Path) -> None:
        merged_dir = self.workspace_root / "merged"
        merged_dir.mkdir(parents=True, exist_ok=True)
        for src in sorted([*generated_dir.glob("*.v"), *generated_dir.glob("*.sv")], key=lambda item: item.name):
            shutil.copyfile(src, merged_dir / src.name)

    def _run_async(self, coroutine: Any) -> Any:
        import asyncio
        import threading

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

        thread = threading.Thread(target=runner)
        thread.start()
        thread.join()
        if "error" in result:
            raise result["error"]
        return result.get("value")

    def _summarize_command_result(self, sim_output: str) -> str:
        try:
            obj = CommandResult.model_validate_json(sim_output)
            text = "\n".join(part for part in [obj.stdout, obj.stderr] if part)
        except Exception:  # noqa: BLE001
            text = sim_output
        return clip_text(text, max_chars=3000)


def system_debug_result_to_dict(result: SystemDebugResult) -> dict[str, Any]:
    return asdict(result)
