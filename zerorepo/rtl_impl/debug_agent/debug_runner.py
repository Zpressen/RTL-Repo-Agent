from __future__ import annotations

import asyncio
import hashlib
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
from .sim_reviewer import SimReviewer, check_syntax
from .utils import add_lineno, clip_text


DebugStatus = Literal["disabled", "skipped", "pass", "fixed", "fail", "error"]


@dataclass(frozen=True)
class RtlDebugConfig:
    enabled: bool = True
    oracle_root: str = "/home/mokita/RealBench"
    max_trials: int = 30
    allow_failure: bool = False
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
    pre_debug_syntax_max_attempts = 5

    def __init__(
        self,
        *,
        config: RtlDebugConfig | None = None,
        workspace_root: str | Path,
        output_root: str | Path | None = None,
        repo_root: str | Path | None = None,
        logger: Any | None = None,
        kg_service: Any | None = None,
        initial_result_recorder: Callable[[str, str | Path, ModuleDebugResult], Any] | None = None,
    ) -> None:
        self.config = config or RtlDebugConfig.from_env()
        self.workspace_root = Path(workspace_root)
        self.output_root = Path(output_root) if output_root is not None else None
        self.repo_root = Path(repo_root) if repo_root is not None else Path.cwd()
        self.debug_root = self.workspace_root / "debug"
        self.logger = logger
        self.kg_service = kg_service
        self.initial_result_recorder = initial_result_recorder

    def _rtl_hash(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

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
            syntax_passed, syntax_output = check_syntax(str(workdir / "rtl.sv"), top_module=module_name)
            if not syntax_passed:
                syntax_passed, _rtl_code, syntax_trials = self._run_repo_react_syntax_repair(
                    spec_text=spec_text,
                    workdir=workdir,
                    syntax_output=syntax_output,
                    contract_json=contract_json,
                    task=task,
                    module_name=module_name,
                    merged_file=Path(merged_file),
                    spec_source_path=spec_source_path,
                )
                self._write_text(
                    workdir / "pre_debug_syntax_repair.json",
                    json.dumps(
                        {
                            "module": module_name,
                            "status": "pass_after_repo_react" if syntax_passed else "fail",
                            "repair_mode": "repo_react_syntax",
                            "debug_trials": int(syntax_trials),
                            "initial_syntax_summary": self._summarize_syntax_output(syntax_output),
                        },
                        indent=2,
                        ensure_ascii=False,
                    )
                    + "\n",
                )
            else:
                self._write_text(
                    workdir / "pre_debug_syntax_repair.json",
                    json.dumps(
                        {
                            "module": module_name,
                            "status": "pass_without_repair",
                            "repair_mode": "repo_react_syntax",
                            "initial_syntax_summary": self._summarize_syntax_output(syntax_output),
                        },
                        indent=2,
                        ensure_ascii=False,
                    )
                    + "\n",
                )
            if not syntax_passed:
                self._write_text(workdir / "initial_sim_output.json", syntax_output)
                initial_result = self._initial_debug_result(
                    module_name=module_name,
                    is_pass=False,
                    mismatch_count=0,
                    sim_output=syntax_output,
                    workdir=workdir,
                )
                self._record_initial_result(
                    module_name=module_name,
                    merged_file=merged_file,
                    result=initial_result,
                )
                return initial_result
            self._write_text(
                workdir / "pre_debug_syntax_repair_legacy_skipped.json",
                json.dumps(
                    {
                        "module": module_name,
                        "status": "skipped",
                        "reason": "RepoReAct syntax repair path is active.",
                    },
                    indent=2,
                    ensure_ascii=False,
                )
                + "\n",
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

            final_pass, _rtl_code, used_trials = self._run_repo_react(
                sim_reviewer=sim_reviewer,
                spec_text=spec_text,
                workdir=workdir,
                sim_output=sim_output,
                mismatch_count=mismatch_count,
                contract_json=contract_json,
                task=task,
                module_name=module_name,
                merged_file=Path(merged_file),
                spec_source_path=spec_source_path,
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
            if final_rtl.is_file():
                shutil.copyfile(final_rtl, Path(merged_file))
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

    def run_module_syntax_gate(
        self,
        *,
        module_name: str,
        merged_file: str | Path,
        task: Any,
        spec_text: str,
        contract_json: str,
        spec_source_path: str | None = None,
    ) -> ModuleDebugResult:
        """Run a module-level syntax/elaboration gate without module oracle simulation."""
        if not self.config.enabled:
            return ModuleDebugResult(module=module_name, status="disabled", reason="RTL debug is disabled.")

        merged_path = Path(merged_file)
        workdir = (self.debug_root / module_name).resolve()
        try:
            self._ensure_toolchain_path()
            self._prepare_syntax_gate_workdir(
                module_name=module_name,
                merged_file=merged_path,
                workdir=workdir,
                contract_json=contract_json,
                spec_source_path=spec_source_path,
            )
            syntax_passed, syntax_output = check_syntax(str(workdir / "rtl.sv"), top_module=module_name)
            self._write_text(workdir / "initial_syntax_output.json", syntax_output)
            if syntax_passed:
                result = ModuleDebugResult(
                    module=module_name,
                    status="pass",
                    mismatch_count=0,
                    workdir=str(workdir),
                    final_rtl_path=str(workdir / "rtl.sv"),
                    sim_output_path=str(workdir / "initial_syntax_output.json"),
                )
                self._write_syntax_gate_log(
                    workdir=workdir,
                    module_name=module_name,
                    status="pass_without_repair",
                    syntax_output=syntax_output,
                    debug_trials=0,
                )
                return result

            syntax_passed, _rtl_code, syntax_trials = self._run_repo_react_syntax_repair(
                spec_text=spec_text,
                workdir=workdir,
                syntax_output=syntax_output,
                contract_json=contract_json,
                task=task,
                module_name=module_name,
                merged_file=merged_path,
                spec_source_path=spec_source_path,
            )
            final_rtl = workdir / "rtl.sv"
            if syntax_passed and final_rtl.is_file():
                shutil.copyfile(final_rtl, merged_path)
                status: DebugStatus = "fixed"
                reason = ""
            else:
                status = "fail"
                reason = "Syntax gate failed after repair attempts."
            self._write_syntax_gate_log(
                workdir=workdir,
                module_name=module_name,
                status="pass_after_repair" if syntax_passed else "fail",
                syntax_output=syntax_output,
                debug_trials=int(syntax_trials),
            )
            return ModuleDebugResult(
                module=module_name,
                status=status,
                mismatch_count=0,
                debug_trials=int(syntax_trials),
                workdir=str(workdir),
                final_rtl_path=str(final_rtl),
                sim_output_path=str(workdir / "initial_syntax_output.json"),
                reason=reason,
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

    def _prepare_syntax_gate_workdir(
        self,
        *,
        module_name: str,
        merged_file: Path,
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
        self._write_text(workdir / "stage1_contract.json", contract_json.rstrip() + "\n")
        self._write_text(workdir / "contract.json", contract_json.rstrip() + "\n")

        merged_root = merged_file.parent
        support_chunks: list[str] = []
        for path in sorted([*merged_root.glob("*.sv"), *merged_root.glob("*.v")], key=lambda item: item.name):
            if path.resolve() == merged_file.resolve():
                continue
            try:
                support_chunks.append(f"// support source: {path.name}\n{path.read_text(encoding='utf-8')}")
            except OSError:
                continue
        self._write_text(workdir / "support.sv", "\n\n".join(support_chunks).rstrip() + "\n")

        for path in sorted(merged_root.iterdir(), key=lambda item: item.name):
            if path.is_file() and path.suffix.lower() in {".vh", ".svh", ".inc"}:
                shutil.copyfile(path, workdir / path.name)

        manifest = {
            "module": module_name,
            "merged_file": str(merged_file),
            "support_file": str(workdir / "support.sv"),
            "spec_source_path": spec_source_path or "",
            "debug_behavior_source": "syntax_gate_only",
            "tb_visibility": "none",
        }
        self._write_text(workdir / "debug_input_manifest.json", json.dumps(manifest, indent=2) + "\n")

    def _write_syntax_gate_log(
        self,
        *,
        workdir: Path,
        module_name: str,
        status: str,
        syntax_output: str,
        debug_trials: int,
    ) -> None:
        payload = {
            "module": module_name,
            "status": status,
            "repair_mode": "repo_react_syntax",
            "debug_trials": int(debug_trials),
            "initial_syntax_summary": self._summarize_syntax_output(syntax_output),
        }
        self._write_text(
            workdir / "pre_debug_syntax_repair.json",
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        )

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

    def _repair_debug_workspace_syntax(
        self,
        *,
        module_name: str,
        workdir: Path,
        spec_text: str,
        contract_json: str,
    ) -> None:
        rtl_path = workdir / "rtl.sv"
        support_path = workdir / "support.sv"
        support_text = support_path.read_text(encoding="utf-8") if support_path.exists() else ""
        support_index = self._build_support_interface_index(workdir)
        macro_table = self._build_macro_table(workdir)
        self._write_text(
            workdir / "support_interface_index.json",
            json.dumps(support_index, indent=2, ensure_ascii=False) + "\n",
        )

        log: dict[str, Any] = {
            "module": module_name,
            "status": "unknown",
            "attempts": [],
            "max_attempts": int(self.pre_debug_syntax_max_attempts),
            "support_interface_index_path": str(workdir / "support_interface_index.json"),
        }

        try:
            syntax_passed, syntax_output = check_syntax(str(rtl_path), top_module=module_name)
        except Exception as exc:  # noqa: BLE001
            log["status"] = "error"
            log["initial"] = {
                "syntax_passed": False,
                "rtl_hash": self._rtl_hash(rtl_path.read_text(encoding="utf-8")),
                "syntax_summary": f"{type(exc).__name__}: {exc}",
                "raw_output_excerpt": f"{type(exc).__name__}: {exc}",
            }
            self._write_text(
                workdir / "pre_debug_syntax_repair.json",
                json.dumps(log, indent=2, ensure_ascii=False) + "\n",
            )
            return
        log["initial"] = {
            "syntax_passed": bool(syntax_passed),
            "rtl_hash": self._rtl_hash(rtl_path.read_text(encoding="utf-8")),
            "syntax_summary": self._summarize_syntax_output(syntax_output),
            "raw_output_excerpt": clip_text(syntax_output, max_chars=8000),
        }
        if syntax_passed:
            log["status"] = "pass_without_repair"
            self._write_text(
                workdir / "pre_debug_syntax_repair.json",
                json.dumps(log, indent=2, ensure_ascii=False) + "\n",
            )
            return

        current_syntax_output = syntax_output
        for attempt in range(1, int(self.pre_debug_syntax_max_attempts) + 1):
            rtl_code = rtl_path.read_text(encoding="utf-8")
            prompt = self._build_pre_debug_syntax_repair_prompt(
                module_name=module_name,
                rtl_code=rtl_code,
                syntax_output=current_syntax_output,
                support_index=support_index,
                support_text=support_text,
                macro_table=macro_table,
                spec_text=spec_text,
                contract_json=contract_json,
            )
            try:
                raw = self._call_pre_debug_syntax_repair_llm(prompt)
                repaired = self._extract_verilog_code(raw)
                if repaired.strip():
                    self._write_text(rtl_path, repaired.rstrip() + "\n")
                else:
                    current_syntax_output = "LLM returned empty RTL."
            except Exception as exc:  # noqa: BLE001
                current_syntax_output = f"{type(exc).__name__}: {exc}"

            try:
                syntax_passed, syntax_output_after = check_syntax(str(rtl_path), top_module=module_name)
            except Exception as exc:  # noqa: BLE001
                syntax_passed = False
                syntax_output_after = f"{type(exc).__name__}: {exc}"
            attempt_log = {
                "attempt": attempt,
                "syntax_passed": bool(syntax_passed),
                "rtl_hash": self._rtl_hash(rtl_path.read_text(encoding="utf-8")),
                "syntax_summary": self._summarize_syntax_output(syntax_output_after),
                "raw_output_excerpt": clip_text(syntax_output_after, max_chars=8000),
            }
            log["attempts"].append(attempt_log)
            current_syntax_output = syntax_output_after
            if syntax_passed:
                log["status"] = "pass_after_repair"
                self._write_text(
                    workdir / "pre_debug_syntax_repair.json",
                    json.dumps(log, indent=2, ensure_ascii=False) + "\n",
                )
                return

        log["status"] = "fail"
        self._write_text(
            workdir / "pre_debug_syntax_repair.json",
            json.dumps(log, indent=2, ensure_ascii=False) + "\n",
        )

    def _build_support_interface_index(self, workdir: Path) -> dict[str, Any]:
        support_path = workdir / "support.sv"
        support_text = support_path.read_text(encoding="utf-8") if support_path.exists() else ""
        modules: dict[str, Any] = {}
        for m in re.finditer(r"\bmodule\s+([a-zA-Z_][a-zA-Z0-9_$]*)\b", support_text):
            name = m.group(1)
            end_m = re.search(r"\bendmodule\b", support_text[m.end() :], flags=re.IGNORECASE)
            module_end = m.end() + end_m.end() if end_m else len(support_text)
            module_text = support_text[m.start() : module_end]
            header_end = module_text.find(";")
            declaration = module_text[: header_end + 1].strip() if header_end >= 0 else module_text[:4000].strip()
            header_text = declaration
            body_text = module_text[header_end + 1 :] if header_end >= 0 else ""
            parameters = self._parse_support_parameters(header_text)
            ports = self._parse_support_ports(header_text, body_text)
            modules[name] = {
                "name": name,
                "parameters": parameters,
                "ports": ports,
                "declaration": declaration,
            }
        return {"source": str(support_path), "modules": modules}

    def _parse_support_parameters(self, header_text: str) -> list[dict[str, Any]]:
        params: list[dict[str, Any]] = []
        seen: set[str] = set()
        param_block = ""
        m = re.search(r"#\s*\((.*)\)\s*\(", header_text, flags=re.DOTALL)
        if m:
            param_block = m.group(1)
        for pm in re.finditer(
            r"\b(?:parameter|localparam)\b\s+(?:\w+\s+)?(?:\[[^\]]+\]\s*)?([a-zA-Z_][a-zA-Z0-9_$]*)\s*(?:=\s*([^,\)]+))?",
            param_block,
            flags=re.DOTALL,
        ):
            name = pm.group(1)
            if name in seen:
                continue
            seen.add(name)
            params.append({"name": name, "default": (pm.group(2) or "").strip()})
        return params

    def _parse_support_ports(self, header_text: str, body_text: str) -> list[dict[str, Any]]:
        ports_by_name: dict[str, dict[str, Any]] = {}

        def add_port(name: str, direction: str = "", width: str = "") -> None:
            if not name or name in {"input", "output", "inout", "wire", "logic", "reg"}:
                return
            current = ports_by_name.get(name, {"name": name, "direction": "", "width": ""})
            if direction:
                current["direction"] = direction
            if width:
                current["width"] = width
            ports_by_name[name] = current

        header_no_params = re.sub(r"#\s*\(.*?\)\s*", "", header_text, flags=re.DOTALL)
        port_block = ""
        start = header_no_params.find("(")
        end = header_no_params.rfind(")")
        if start >= 0 and end > start:
            port_block = header_no_params[start + 1 : end]
        for part in self._split_commas(port_block):
            text = part.strip()
            if not text:
                continue
            direction_match = re.search(r"\b(input|output|inout)\b", text)
            direction = direction_match.group(1) if direction_match else ""
            width_match = re.search(r"(\[[^\]]+\])", text)
            width = width_match.group(1) if width_match else ""
            name_match = re.search(r"([a-zA-Z_][a-zA-Z0-9_$]*)\s*(?:\[[^\]]+\])?\s*$", text)
            if name_match:
                add_port(name_match.group(1), direction, width)

        decl_re = re.compile(
            r"^\s*(input|output|inout)\b\s*(?:wire|logic|reg|signed|unsigned\s+)*\s*(\[[^\]]+\])?\s*([^;]+);",
            flags=re.MULTILINE,
        )
        for dm in decl_re.finditer(body_text):
            direction = dm.group(1)
            width = (dm.group(2) or "").strip()
            names_text = dm.group(3)
            for name_part in names_text.split(","):
                nm = re.search(r"([a-zA-Z_][a-zA-Z0-9_$]*)", name_part.strip())
                if nm:
                    add_port(nm.group(1), direction, width)

        return [ports_by_name[name] for name in sorted(ports_by_name)]

    def _split_commas(self, text: str) -> list[str]:
        parts: list[str] = []
        current: list[str] = []
        depth = 0
        for ch in text:
            if ch in "([{":
                depth += 1
            elif ch in ")]}" and depth > 0:
                depth -= 1
            if ch == "," and depth == 0:
                parts.append("".join(current))
                current = []
                continue
            current.append(ch)
        if current:
            parts.append("".join(current))
        return parts

    def _build_macro_table(self, workdir: Path) -> list[dict[str, Any]]:
        macros: list[dict[str, Any]] = []
        define_re = re.compile(r"^\s*`define\s+([a-zA-Z_][a-zA-Z0-9_$]*)(?:\s+(.*?))?\s*$")
        for path in sorted([*workdir.glob("*.sv"), *workdir.glob("*.v")], key=lambda item: item.name):
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue
            for line_no, line in enumerate(lines, start=1):
                m = define_re.match(line)
                if m:
                    macros.append(
                        {
                            "name": m.group(1),
                            "value": (m.group(2) or "").strip(),
                            "file": path.name,
                            "line": line_no,
                        }
                    )
        return macros

    def _extract_relevant_support_declarations(
        self,
        syntax_output: str,
        index: dict[str, Any],
        support_text: str,
    ) -> str:
        modules = index.get("modules") if isinstance(index, dict) else {}
        if not isinstance(modules, dict) or not modules:
            return clip_text(support_text, max_chars=12000)
        names: set[str] = set()
        haystack = syntax_output
        for name in modules:
            if str(name) in haystack:
                names.add(str(name))
        if not names:
            return clip_text("\n\n".join(str(info.get("declaration", "")) for info in modules.values() if isinstance(info, dict)), max_chars=12000)
        snippets = [
            str(modules[name].get("declaration", ""))
            for name in sorted(names)
            if isinstance(modules.get(name), dict)
        ]
        return clip_text("\n\n".join(snippets), max_chars=12000)

    def _build_pre_debug_syntax_repair_prompt(
        self,
        *,
        module_name: str,
        rtl_code: str,
        syntax_output: str,
        support_index: dict[str, Any],
        support_text: str,
        macro_table: list[dict[str, Any]],
        spec_text: str,
        contract_json: str,
    ) -> str:
        relevant_support = self._extract_relevant_support_declarations(syntax_output, support_index, support_text)
        return (
            "You are repairing Verilog/SystemVerilog syntax, interface, and elaboration errors before functional debug.\n"
            "support.sv is the authoritative child module interface source. Only modify rtl.sv.\n"
            "Do not modify support.sv, tb.sv, sd_defines.v, include files, or testbench behavior.\n"
            "Do not pass macros as parameter overrides unless the support module explicitly declares that parameter. "
            "For example, if the child has no SD_BUS_W parameter, remove #(.SD_BUS_W(...)).\n"
            "Do not connect ports that are absent from the support module. Remove or replace nonexistent ports with real ports.\n"
            "Do not invent child ports or child parameters. Preserve the top module interface and intended behavior.\n"
            "Return only the complete corrected rtl.sv code, preferably in a systemverilog fenced block.\n\n"
            f"<module_name>\n{module_name}\n</module_name>\n\n"
            "<verilator_lint_log>\n"
            f"{self._summarize_syntax_output(syntax_output)}\n"
            "</verilator_lint_log>\n\n"
            "<rtl_sv_with_lineno>\n"
            f"{add_lineno(rtl_code)}"
            "</rtl_sv_with_lineno>\n\n"
            "<support_interface_index_json>\n"
            f"{json.dumps(support_index, indent=2, ensure_ascii=False)}\n"
            "</support_interface_index_json>\n\n"
            "<relevant_support_declarations>\n"
            f"{relevant_support}\n"
            "</relevant_support_declarations>\n\n"
            "<macro_table>\n"
            f"{json.dumps(macro_table, indent=2, ensure_ascii=False)}\n"
            "</macro_table>\n\n"
            "<original_spec_background>\n"
            f"{clip_text(spec_text, max_chars=4000)}\n"
            "</original_spec_background>\n\n"
            "<contract_json_background>\n"
            f"{clip_text(contract_json, max_chars=4000)}\n"
            "</contract_json_background>\n"
        )

    def _call_pre_debug_syntax_repair_llm(self, prompt: str) -> str:
        from agentscope.memory import InMemoryMemory
        from agentscope.message import Msg

        from .agents import SafeReActAgent, clear_memory_safely
        from .model import make_formatter, make_openai_model

        cfg = self.config.openai_config or load_openai_config()
        agent = SafeReActAgent(
            name="PreDebugSyntaxRepair",
            sys_prompt=(
                "You are a precise RTL syntax/interface repair assistant. "
                "Return only corrected rtl.sv code."
            ),
            model=make_openai_model(cfg),
            formatter=make_formatter(cfg.model, cfg.base_url),
            memory=InMemoryMemory(),
            max_iters=3,
        )
        try:
            msg = self._run_async(agent(Msg("user", prompt, role="user")))
            return msg.get_text_content() or ""
        finally:
            clear_memory_safely(agent)

    def _extract_verilog_code(self, raw: str) -> str:
        text = raw if isinstance(raw, str) else str(raw)
        fenced_blocks = re.findall(
            r"```(?:verilog|systemverilog|sv)?\s*\n(.*?)```",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if fenced_blocks:
            return fenced_blocks[0].strip()
        generic_blocks = re.findall(r"```\s*\n(.*?)```", text, flags=re.DOTALL)
        if generic_blocks:
            return generic_blocks[0].strip()
        return text.strip()

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

    def _run_repo_react(
        self,
        *,
        sim_reviewer: SimReviewer,
        spec_text: str,
        workdir: Path,
        sim_output: str,
        mismatch_count: int,
        contract_json: str,
        task: Any,
        module_name: str,
        merged_file: Path,
        spec_source_path: str | None,
        behavior_source: Literal["contract", "spec_tb"] = "contract",
    ) -> tuple[bool, str, int]:
        try:
            from zerorepo.rtl_impl.repo_react import RepoReActInput, RepoReActRunner
        except ModuleNotFoundError as exc:
            if exc.name == "agentscope":
                raise ModuleNotFoundError(
                    "Missing Python dependency 'agentscope'. Install RTL debug dependencies with "
                    "`python -m pip install -r requirements.txt` in the environment that runs ZeroRepo."
                ) from exc
            raise

        cfg = self.config.openai_config or load_openai_config()
        spec_paths = []
        try:
            spec_paths = [str(item) for item in (getattr(task, "spec_md_files", []) or [])]
        except Exception:  # noqa: BLE001
            spec_paths = []
        output_root = self.output_root
        if output_root is None:
            candidate = self.workspace_root.parent / "outputs"
            output_root = candidate if candidate.exists() else None
        runner = RepoReActRunner(
            cfg,
            sim_reviewer=sim_reviewer,
            kg_service=self.kg_service,
            max_steps=int(self.config.max_trials),
            logger=self.logger,
        )
        repo_input = RepoReActInput(
            module_name=module_name,
            workspace_root=self.workspace_root,
            debug_workdir=workdir,
            rtl_path=workdir / "rtl.sv",
            merged_file=merged_file,
            output_root=output_root,
            repo_root=self.repo_root,
            spec_text=spec_text,
            spec_source_path=spec_source_path or "",
            spec_paths=spec_paths,
            contract_json=contract_json,
            sim_failed_log=sim_output,
            initial_mismatch_count=int(mismatch_count),
            max_steps=int(self.config.max_trials),
        )
        del behavior_source
        result = self._run_async(runner.chat(repo_input))
        return bool(result.is_pass), result.rtl_code, int(result.action_calls)

    def _run_repo_react_syntax_repair(
        self,
        *,
        spec_text: str,
        workdir: Path,
        syntax_output: str,
        contract_json: str,
        task: Any,
        module_name: str,
        merged_file: Path,
        spec_source_path: str | None,
    ) -> tuple[bool, str, int]:
        try:
            from zerorepo.rtl_impl.repo_react import RepoReActInput, RepoReActRunner
        except ModuleNotFoundError as exc:
            if exc.name == "agentscope":
                raise ModuleNotFoundError(
                    "Missing Python dependency 'agentscope'. Install RTL debug dependencies with "
                    "`python -m pip install -r requirements.txt` in the environment that runs ZeroRepo."
                ) from exc
            raise

        cfg = self.config.openai_config or load_openai_config()
        spec_paths = []
        try:
            spec_paths = [str(item) for item in (getattr(task, "spec_md_files", []) or [])]
        except Exception:  # noqa: BLE001
            spec_paths = []
        output_root = self.output_root
        if output_root is None:
            candidate = self.workspace_root.parent / "outputs"
            output_root = candidate if candidate.exists() else None
        runner = RepoReActRunner(
            cfg,
            sim_reviewer=SimReviewer(str(workdir), str(workdir / "support.sv")),
            kg_service=self.kg_service,
            max_steps=int(self.pre_debug_syntax_max_attempts),
            logger=self.logger,
        )
        repo_input = RepoReActInput(
            module_name=module_name,
            repair_mode="syntax",
            workspace_root=self.workspace_root,
            debug_workdir=workdir,
            rtl_path=workdir / "rtl.sv",
            merged_file=merged_file,
            output_root=output_root,
            repo_root=self.repo_root,
            spec_text=spec_text,
            spec_source_path=spec_source_path or "",
            spec_paths=spec_paths,
            contract_json=contract_json,
            sim_failed_log=syntax_output,
            initial_mismatch_count=0,
            max_steps=int(self.pre_debug_syntax_max_attempts),
        )
        result = self._run_async(runner.chat(repo_input))
        return bool(result.is_pass), result.rtl_code, int(result.action_calls)

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

    def _summarize_syntax_output(self, syntax_output: str) -> str:
        try:
            obj = CommandResult.model_validate_json(syntax_output)
            text = "\n".join(part for part in [obj.stdout, obj.stderr] if part)
        except Exception:  # noqa: BLE001
            text = syntax_output
        text = text.strip()
        if len(text) > 6000:
            text = text[:6000] + "\n...<snip>..."
        return text

    def _write_text(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def module_debug_result_to_dict(result: ModuleDebugResult) -> dict[str, Any]:
    return asdict(result)
