from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import sys
import textwrap
import uuid
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


def bind_reviewer(reviewer, candidate_root, output_dir):
    """Rebind by protocol, including custom reviewers across candidate trials."""
    factory = getattr(reviewer,'for_candidate',None)
    if callable(factory):
        return factory(candidate_root,output_dir)
    # Existing stateless legacy test adapters remain compatible. Custom HDL
    # descriptors require a reconstructible reviewer implementing this method.
    return reviewer


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

    def for_candidate(self,candidate_root,output_dir):
        return type(self)(generated_dir=candidate_root,verify_script=self.verify_script,
                          output_dir=output_dir,timeout=self.timeout)

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
                import hashlib
                import json
                import os
                import pathlib
                import re
                import shutil
                import sys
                import tempfile
                import traceback


                MODULE_RE = re.compile(
                    r"^\s*module\s+([A-Za-z_][A-Za-z0-9_$]*)\b",
                    re.MULTILINE,
                )


                def install_system_suffix_testbench_compat(module, generated_dir, output_dir):
                    """Patch only the staged verifier testbench, never generated RTL."""
                    script_dir = pathlib.Path(str(getattr(module, "SCRIPT_DIR", "")))
                    testbench_name = str(getattr(module, "TESTBENCH_FILE", ""))
                    if not script_dir.is_dir() or not testbench_name:
                        return
                    testbench_path = script_dir / testbench_name
                    if not testbench_path.is_file():
                        return

                    declared = set()
                    for rtl_path in generated_dir.iterdir():
                        if not rtl_path.is_file() or rtl_path.suffix.lower() not in {".v", ".sv"}:
                            continue
                        try:
                            declared.update(MODULE_RE.findall(rtl_path.read_text(encoding="utf-8", errors="ignore")))
                        except OSError:
                            pass

                    try:
                        patched = testbench_path.read_text(encoding="utf-8", errors="ignore")
                    except OSError:
                        return
                    replacements = []
                    for actual_module in sorted(declared):
                        if not actual_module.endswith("_system"):
                            continue
                        testbench_module = actual_module[:-7]
                        if not testbench_module or testbench_module in declared:
                            continue
                        instantiation = re.compile(
                            rf"\b{re.escape(testbench_module)}\b"
                            r"(?=\s+(?:#\s*\([^;]*\)\s*)?[A-Za-z_][A-Za-z0-9_$]*\s*\()"
                        )
                        patched, count = instantiation.subn(actual_module, patched)
                        if count:
                            replacements.append((testbench_module, actual_module, count))
                    if not replacements:
                        return

                    # Some verifiers resolve the testbench relative to SCRIPT_DIR.
                    # Copy that flat directory and point only the imported verifier
                    # module at the compatibility copy.
                    compat_dir = output_dir / "simulation_compat" / "verify_files"
                    compat_dir.mkdir(parents=True, exist_ok=True)
                    for source in script_dir.iterdir():
                        if source.is_file():
                            shutil.copy2(source, compat_dir / source.name)
                    (compat_dir / testbench_name).write_text(patched, encoding="utf-8")
                    module.SCRIPT_DIR = str(compat_dir)
                    for old_name, new_name, count in replacements:
                        print(
                            f"ZEROREPO_TB_MODULE_ALIAS: {old_name} -> {new_name} "
                            f"({count} instantiation(s), simulation-only)"
                        )


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
                        # Deployment-only adaptation: paths and build concurrency.
                        # Preserve the original verifier/TB/stimulus/comparison bytes.
                        deployed_root = os.environ.get("ZEROREPO_DEPLOY_ORACLE_ROOT")
                        if deployed_root:
                            old_root = str(getattr(module, "REALBENCH_ROOT", ""))
                            old_flags = list(getattr(module, "VERILATOR_FLAGS", []))
                            changed = {}
                            for name, value in list(vars(module).items()):
                                if old_root and isinstance(value, str) and (value == old_root or value.startswith(old_root + os.sep)):
                                    new_value = deployed_root + value[len(old_root):]
                                    setattr(module, name, new_value)
                                    changed[name] = {"before": value, "after": new_value}
                            tool_bin = os.environ.get("ZEROREPO_DEPLOY_TOOLCHAIN_BIN")
                            if tool_bin and hasattr(module, "CONDA_REALBENCH_BIN"):
                                module.CONDA_REALBENCH_BIN = tool_bin
                            flags = list(old_flags)
                            jobs = int(os.environ.get("ZEROREPO_DEPLOY_COMPILE_JOBS", "1"))
                            if jobs != 1:
                                raise ValueError("Deployment compilation is limited to one job")
                            for i, flag in enumerate(flags[:-1]):
                                if flag == "-j":
                                    flags[i + 1] = str(jobs)
                            module.VERILATOR_FLAGS = flags
                            (output_dir / "deployment_adaptation.json").write_text(json.dumps({
                                "schema_version": "rtl-verifier-adaptation-v1",
                                "original_script_sha256": hashlib.sha256(verify_script.read_bytes()).hexdigest(),
                                "paths": changed, "toolchain_bin": tool_bin,
                                "original_flags": old_flags, "effective_flags": flags,
                            }, sort_keys=True), encoding="utf-8")
                        install_system_suffix_testbench_compat(
                            module,
                            generated_dir,
                            output_dir,
                        )
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
        self._last_backend_reason = ""
        self._last_backend_mismatch_count: int | None = None

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
        if self.logger is not None:
            self.logger.info(
                "[rtl_system_debug] system_debug_backend=%s "
                "(module_syntax_repair=repo_react)",
                self.config.backend,
            )
        if not planner_top_module:
            return SystemDebugResult(
                status="error",
                top_module="",
                reason="System-level debug requires a non-empty top module.",
            )

        project_hint = self._infer_project_hint(task)
        verify_dir = self._resolve_verify_dir(runtime_top_module, project_hint=project_hint)
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
            expected_dirs = ", ".join(
                str(item)
                for item in self._verify_dir_candidates(runtime_top_module, project_hint)
            )
            return SystemDebugResult(
                top_module=runtime_top_module,
                planner_top_module=planner_top_module,
                status="error",
                reason=(
                    f"System verify directory not found for {runtime_top_module}. "
                    f"Expected one of {expected_dirs}."
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

        testbench_dut_module = self._resolve_system_suffix_testbench_module(
            planner_top_module,
            verify_dir,
        )
        if testbench_dut_module != planner_top_module:
            if self.logger is not None:
                self.logger.info(
                    "[rtl_system_debug] Simulation-only testbench module alias %s -> %s.",
                    testbench_dut_module,
                    planner_top_module,
                )

        workdir = (self.debug_root / runtime_top_module).resolve()
        generated_dir = workdir / "generated"
        try:
            self._ensure_toolchain_path()
            dut_instance, runtime_rtl_path = self._prepare_workdir(
                planner_top_module=planner_top_module,
                runtime_top_module=runtime_top_module,
                testbench_dut_module=testbench_dut_module,
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
            self._last_backend_reason = ""
            self._last_backend_mismatch_count = None
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
                mismatch_count=(
                    0
                    if final_pass
                    else int(
                        self._last_backend_mismatch_count
                        if self._last_backend_mismatch_count is not None
                        else mismatch_count
                    )
                ),
                debug_trials=int(used_trials),
                workdir=str(workdir),
                generated_dir=str(generated_dir),
                verify_dir=str(verify_dir),
                verify_script=str(verify_script),
                sim_output_path=str(debug_sim_path if debug_sim_path.exists() else initial_sim_path),
                trace_report_path=str(workdir / "trace_report.json") if (workdir / "trace_report.json").exists() else "",
                reason=(
                    ""
                    if final_pass
                    else self._last_backend_reason or "System debug trials ended without passing top simulation."
                ),
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

    def _infer_project_hint(self, task: Any) -> str:
        """Infer the RealBench system-task directory from a dataset spec path."""
        for raw_path in list(getattr(task, "spec_md_files", []) or []):
            parts = Path(str(raw_path)).expanduser().parts
            try:
                index = parts.index("rtl_dataset")
            except ValueError:
                continue
            if index + 1 < len(parts):
                project = str(parts[index + 1]).strip()
                if project and project not in {".", ".."}:
                    return project
        return ""

    def _verify_dir_candidates(self, top_module: str, project_hint: str = "") -> list[Path]:
        names = [project_hint, top_module] if project_hint else [top_module]
        candidates: list[Path] = []
        seen: set[Path] = set()
        for name in names:
            candidate = self._default_verify_dir(name)
            if candidate in seen:
                continue
            seen.add(candidate)
            candidates.append(candidate)
        return candidates

    def _resolve_verify_dir(self, top_module: str, project_hint: str = "") -> Path | None:
        for candidate in self._verify_dir_candidates(top_module, project_hint):
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

    def _ensure_toolchain_path(self) -> None:
        if shutil.which("verilator"):
            return
        candidates = [
            Path(self.config.toolchain_bin).expanduser() if self.config.toolchain_bin else None,
            Path("/home/mokita/miniconda3/envs/realbench/bin"),
            Path("/home/mokita/miniconda3/bin"),
        ]
        for candidate in candidates:
            if candidate is not None and (candidate / "verilator").is_file():
                os.environ["PATH"] = f"{candidate}{os.pathsep}{os.environ.get('PATH', '')}"
                return

    def _select_verify_script(self, verify_dir: Path) -> Path | None:
        candidates = sorted(verify_dir.glob("*_verify.py"))
        if not candidates:
            candidates = sorted(verify_dir.glob("*verify*.py"))
        return candidates[0] if candidates else None

    def _resolve_system_suffix_testbench_module(
        self,
        planner_top: str,
        verify_dir: Path,
    ) -> str:
        """Detect a ``foo`` testbench instance for the real ``foo_system`` top."""
        suffix = "_system"
        if not planner_top.endswith(suffix) or len(planner_top) <= len(suffix):
            return planner_top
        compatibility_top = planner_top[: -len(suffix)]
        tb_candidates = sorted(verify_dir.glob("*testbench*.sv")) + sorted(
            verify_dir.glob("*tb*.sv")
        )
        for tb_path in tb_candidates:
            try:
                tb_text = tb_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if re.search(
                rf"\b{re.escape(compatibility_top)}\b\s+"
                r"[a-zA-Z_][a-zA-Z0-9_]*\s*\(",
                tb_text,
            ):
                return compatibility_top
        return planner_top

    def _prepare_workdir(
        self,
        *,
        planner_top_module: str,
        runtime_top_module: str,
        testbench_dut_module: str,
        workdir: Path,
        generated_dir: Path,
        verify_dir: Path,
        verify_script: Path,
        merged_records: list[Any],
        contract_json: str,
        extra_top_rtl: Path | None = None,
    ) -> tuple[str, Path]:
        # Verification scratch files may be recreated, but Codex state and
        # archived runs belong to the persistent debug session, not scratch.
        if workdir.exists():
            for entry in workdir.iterdir():
                if entry.name in {"codex_task", "codex_private", "history", "latest_debug_result.json"}:
                    continue
                if entry.is_dir() and not entry.is_symlink():
                    shutil.rmtree(entry)
                else:
                    entry.unlink()
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
            if match is None and testbench_dut_module != runtime_top_module:
                match = re.search(
                    rf"\b{re.escape(testbench_dut_module)}\b\s+"
                    r"([a-zA-Z_][a-zA-Z0-9_]*)\s*\(",
                    tb_text,
                )
            dut_instance = match.group(1) if match else ""
        (workdir / "contract.json").write_text(contract_json.rstrip() + "\n", encoding="utf-8")
        manifest = {
            "top_module": runtime_top_module,
            "planner_module_name": planner_top_module,
            "runtime_top_module": runtime_top_module,
            "runtime_top_alias_of": (
                planner_top_module if planner_top_module != runtime_top_module else ""
            ),
            "testbench_dut_module": testbench_dut_module,
            "simulation_module_aliases": (
                {testbench_dut_module: runtime_top_module}
                if testbench_dut_module != runtime_top_module
                else {}
            ),
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
        if self.config.backend == "codex":
            return self._run_codex_debug(
                planner_top_module=planner_top_module,
                runtime_top_module=runtime_top_module,
                task=task,
                spec_text=spec_text,
                contract_json=contract_json,
                workdir=workdir,
                generated_dir=generated_dir,
                verify_script=verify_script,
                sim_output=sim_output,
                mismatch_count=mismatch_count,
            )
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

    def _run_codex_debug(
        self,
        *,
        planner_top_module: str,
        runtime_top_module: str,
        task: Any,
        spec_text: str,
        contract_json: str,
        workdir: Path,
        generated_dir: Path,
        verify_script: Path,
        sim_output: str,
        mismatch_count: int,
    ) -> tuple[bool, int]:
        from zerorepo.rtl_impl.codex_debug.runner import CodexDebugRunner
        from zerorepo.rtl_impl.codex_debug.schemas import CodexDebugRunDescriptor, KgRunConfig
        from zerorepo.rtl_impl.codex_debug.history import DebugHistory, debug_binding
        from zerorepo.rtl_impl.module_planner.utils.artifact_store import atomic_write_json

        task_root = workdir / "codex_task"
        spec_root = task_root / "spec"
        merged_root = task_root / "merged"
        private_root = workdir / "codex_private"
        raw_spec_paths = [str(p) for p in (getattr(task, "spec_md_files", []) or []) if Path(p).is_file()]
        binding = debug_binding(top_module=runtime_top_module, spec_text=spec_text, spec_paths=raw_spec_paths,
                                contract_json=contract_json, verify_script=verify_script,
                                memory_snapshot_sha256=self.config.memory_snapshot_sha256,
                                memory_profile_sha256=self.config.memory_profile_sha256)
        history = DebugHistory(workdir, self.logger)
        restored = history.select(binding, generated_dir)
        spec_root.mkdir(parents=True, exist_ok=True)
        merged_root.mkdir(parents=True, exist_ok=True)
        private_root.mkdir(parents=True, exist_ok=True)
        if not restored:
            self._copy_rtl_tree(generated_dir, merged_root)

        copied_specs: list[Path] = []
        for index, raw_path in enumerate(raw_spec_paths):
            source = Path(str(raw_path))
            if not source.is_file():
                continue
            name = source.name
            target = spec_root / name
            if target.exists() and not restored:
                target = spec_root / f"{index:03d}_{name}"
            if not restored:
                shutil.copyfile(source, target)
            copied_specs.append(target)
        inline_spec = spec_root / "initial_spec.md"
        if not restored:
            inline_spec.write_text(spec_text.rstrip() + "\n", encoding="utf-8")
        if inline_spec not in copied_specs:
            copied_specs.append(inline_spec)

        top_rtl = self._select_top_rtl(merged_root, runtime_top_module)
        kg_enabled = bool(
            self.kg_service is not None
            and getattr(self.kg_service, "is_enabled", lambda: False)()
        )
        planning_projection = None
        if self.kg_service is not None:
            candidate = getattr(self.kg_service, "planning_projection_path", None)
            if candidate is not None and Path(candidate).is_file():
                planning_projection = Path(candidate)
        kg_config = KgRunConfig(
            enabled=kg_enabled,
            config=dict(getattr(self.kg_service, "config", {}) or {}) if self.kg_service is not None else {},
            checkpoint_dir=private_root / "kg_checkpoint",
            planning_projection_path=planning_projection,
        )
        descriptor = CodexDebugRunDescriptor(
            run_id=f"{runtime_top_module}-{uuid.uuid4().hex[:12]}",
            outer_run_id=self.config.outer_run_id,
            case_id=self.config.case_id,
            memory_snapshot_path=Path(self.config.memory_snapshot_path) if self.config.memory_snapshot_path else None,
            memory_snapshot_sha256=self.config.memory_snapshot_sha256,
            task_root=task_root,
            spec_root=spec_root,
            merged_root=merged_root,
            private_root=private_root,
            debug_workdir=private_root / "debug_artifacts",
            planner_module_name=planner_top_module,
            top_module=runtime_top_module,
            top_rtl=top_rtl,
            verify_script=verify_script,
            planning_output_root=self.output_root,
            contract_json=contract_json,
            spec_text=spec_text,
            spec_paths=copied_specs,
            initial_sim_output=sim_output,
            initial_wave_path=(workdir / "wave.vcd") if (workdir / "wave.vcd").is_file() else None,
            initial_mismatch_count=int(mismatch_count),
            max_validation_trials=int(self.config.max_trials),
            kg=kg_config,
        )
        if restored:
            previous = CodexDebugRunDescriptor.model_validate(restored["descriptor"])
            state = json.loads((private_root / "session_state.json").read_text())
            used = int(state["counters"]["validation_trials"])
            descriptor = previous.model_copy(update={
                "codex_session_id": restored["runtime"]["session_id"],
                "codex_episode": int(restored["runtime"]["episode"]) + 1,
                "validation_trial_offset": used,
                "max_validation_trials": used + int(self.config.max_trials), "kg": kg_config,
            })
        launch_id = uuid.uuid4().hex
        launch = {"launch_id": launch_id, "run_id": descriptor.run_id,
                  "validation_trial_offset": descriptor.validation_trial_offset,
                  "validation_limit": descriptor.max_validation_trials,
                  "validation_allowance": int(self.config.max_trials)}
        atomic_write_json(private_root / "launches" / f"{launch_id}.json", launch)
        atomic_write_json(private_root / "run_record.json", {"run_id": descriptor.run_id, "binding": binding, **launch})
        if self.logger:
            self.logger.info("[codex_debug] New invocation allowance %s; cumulative validations %s -> limit %s",
                self.config.max_trials, descriptor.validation_trial_offset, descriptor.max_validation_trials)
        runner = CodexDebugRunner(
            codex_bin=self.config.codex_bin,
            profile=self.config.codex_profile,
            model=self.config.codex_model,
            timeout=self.config.codex_timeout,
            multi_agent=self.config.codex_multi_agent,
            logger=self.logger,
        )
        result = runner.run(descriptor)
        atomic_write_json(private_root / "run_result.json", result.model_dump(mode="json"))
        atomic_write_json(workdir / "latest_debug_result.json", {
            "run_id": descriptor.run_id, "result": result.model_dump(mode="json"), "binding": binding,
        })
        self._last_backend_reason = result.reason
        self._last_backend_mismatch_count = int(result.mismatch_count)
        self._copy_rtl_tree(merged_root, generated_dir, replace=True)
        final_output = Path(result.sim_output_path) if result.sim_output_path else None
        if final_output is not None and final_output.is_file():
            shutil.copyfile(final_output, workdir / "debug_sim_output.json")
        final_wave = private_root / "final_verify" / "wave.vcd"
        if final_wave.is_file():
            shutil.copyfile(final_wave, workdir / "wave.vcd")
        return bool(result.is_pass), max(0, int(result.patch_attempts) - descriptor.validation_trial_offset)

    @staticmethod
    def _copy_rtl_tree(source: Path, target: Path, *, replace: bool = False) -> None:
        source = Path(source)
        target = Path(target)
        target.mkdir(parents=True, exist_ok=True)
        if replace:
            for existing in list(target.rglob("*")):
                if existing.is_file() or existing.is_symlink():
                    existing.unlink(missing_ok=True)
            for directory in sorted(
                [path for path in target.rglob("*") if path.is_dir()],
                key=lambda path: len(path.parts),
                reverse=True,
            ):
                directory.rmdir()
        for source_path in sorted(source.rglob("*")):
            if not source_path.is_file() or source_path.is_symlink():
                continue
            if source_path.suffix.lower() not in {".v", ".sv"}:
                continue
            relative = source_path.relative_to(source)
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_path, destination)

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
