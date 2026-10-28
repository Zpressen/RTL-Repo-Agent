from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import tomllib
from pathlib import Path
from typing import Any

from zerorepo.rtl_impl.debug_agent.system_debug_runner import SystemSimReviewer
from zerorepo.rtl_impl.repo_react.schemas import RepoReActResult

from .schemas import CodexDebugRunDescriptor


TOOL_NAMES = [
    'query_rtl_memories', 'read_rtl_memory', 'record_memory_application',
    "read_module_semantics",
    "query_rtl_kg",
    "trace_signal_cause",
    "list_vcd_signals",
    "probe_vcd",
    "run_check",
    "validate_rtl_changes",
    "get_debug_status",
]


DEFAULT_PROMPT = """
Before editing, query_rtl_memories for relevant prior experience. Read a relevant
revision, check its applicability against this task's specification, then use
record_memory_application to explain apply/reject/not_applicable and actual RTL
targets. Empty memory is valid; do not force adoption. Experience cannot change
the spec, oracle or verification rules. After changes, still evaluate and
accept/rollback normally. A remembered rule or accepted candidate is not PASS.
Debug the RTL implementation in this task and leave the accepted baseline passing.

Scope and workflow:
- Work only inside this task directory. Read spec/ and merged/; edit only .v/.sv files under merged/.
- Use the zerorepo_rtl_debug MCP tools for planning/KG, waveform, causal trace, status, and validation evidence.
- Choose the KG, VCD, spec, status, and RTL inspection order that best fits your diagnosis.
- After every non-empty native RTL edit call validate_rtl_changes(action="evaluate").
- Inspect the objective lint/simulation/metric/trace result, then explicitly accept or rollback that candidate.
- Do not bypass validation with shell lint/simulation commands and do not copy expected/reference values into RTL.
- Before finishing, get_debug_status must report clean_accepted. A dirty or pending candidate is rolled back.
""".strip()


CONTINUE_PROMPT = """
The accepted RTL baseline still does not pass objective verification. Continue debugging autonomously
in the same task and use the available native tools and zerorepo_rtl_debug MCP tools as you judge useful.
Keep the workspace clean_accepted whenever you finish a candidate decision.
""".strip()


class CodexDebugRunner:
    """Run one isolated Codex session across autonomous exec/resume episodes."""

    def __init__(
        self,
        *,
        codex_bin: str = "codex",
        profile: str = "proxy-a",
        model: str = "",
        timeout: int = 10800,
        multi_agent: bool = False,
        logger: Any | None = None,
    ) -> None:
        self.codex_bin = codex_bin
        self.profile = profile.strip()
        self.model = model
        self.timeout = int(timeout)
        self.multi_agent = bool(multi_agent)
        self.logger = logger

    def run(self, descriptor: CodexDebugRunDescriptor, *, prompt: str = DEFAULT_PROMPT) -> RepoReActResult:
        descriptor.private_root.mkdir(parents=True, exist_ok=True)
        if descriptor.codex_session_id:
            state = json.loads((descriptor.private_root / "session_state.json").read_text())
            accepted = descriptor.private_root / "accepted_baseline" / "merged"
            if state.get("run_id") != descriptor.run_id or self._tree_manifest(accepted) != state.get("accepted_manifest"):
                raise ValueError("Cannot resume an unverified accepted debug baseline")
            self._restore_private_baseline(descriptor)
        launcher_root = descriptor.private_root / "launcher_baseline"
        self._replace_tree(descriptor.merged_root, launcher_root / "merged")
        self._replace_tree(descriptor.spec_root, launcher_root / "spec")
        descriptor_path = descriptor.private_root / "run_descriptor.json"
        self._write_descriptor(descriptor_path, descriptor)
        process_env = os.environ.copy()
        if self.profile:
            try:
                codex_home = self._prepare_private_codex_home(descriptor.private_root)
            except Exception as exc:
                message = f"Codex profile preflight failed: {exc}"
                with (descriptor.private_root / "codex_stderr.log").open("a", encoding="utf-8") as stream:
                    stream.write(message + "\n")
                raise RuntimeError(message) from exc
            process_env["CODEX_HOME"] = str(codex_home)
        deadline = time.monotonic() + self.timeout
        episode = max(0, descriptor.codex_episode - 1) if descriptor.codex_session_id else 0
        session_id = descriptor.codex_session_id
        exit_code = 0
        timed_out = False
        scope_violation = False
        scope_violations: list[str] = []
        resume_unavailable = False
        all_stdout: list[str] = []
        all_stderr: list[str] = []
        status: dict[str, Any] = {}

        while True:
            previous_status = self._read_status(descriptor.private_root)
            previous_budgets = previous_status.get("budgets") or {}
            if int(previous_budgets.get("validation_trials") or 0) >= descriptor.max_validation_trials:
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                break
            episode += 1
            episode_descriptor = descriptor.model_copy(
                update={"codex_session_id": session_id, "codex_episode": episode}
            )
            self._write_descriptor(descriptor_path, episode_descriptor)
            last_message_path = descriptor.private_root / f"codex_last_message_episode_{episode:03d}.txt"
            isolated_web_job=os.environ.get('ZEROREPO_WEB_JOB')=='1'
            if isolated_web_job:
                model_output=descriptor.private_root/'model_output'
                model_output.mkdir(exist_ok=True)
                last_message_path=model_output/last_message_path.name
            if not session_id:
                command = self.build_command(
                    episode_descriptor, descriptor_path, last_message_path, prompt
                )
            else:
                command = self.build_resume_command(
                    episode_descriptor,
                    descriptor_path,
                    last_message_path,
                    session_id,
                    CONTINUE_PROMPT,
                )
            tee_path = descriptor.private_root / f"codex_trace_episode_{episode:03d}.jsonl"
            bridge=None
            try:
                episode_env=process_env
                if isolated_web_job:
                    from zerorepo.rtl_web.tool_bridge import ToolBridge
                    from zerorepo.rtl_web.sandbox import model_command
                    self._write_descriptor(descriptor_path,episode_descriptor)
                    bridge=ToolBridge(descriptor_path,episode_descriptor.run_id)
                    command,episode_env=model_command(episode_descriptor,command,process_env,bridge)
                exit_code, episode_timed_out, stdout, stderr = self._run_process(
                    command,
                    cwd=descriptor.task_root,
                    tee_path=tee_path,
                    process_env=episode_env,
                    timeout=max(1.0, remaining),
                )
            finally:
                if bridge:bridge.close()
            all_stdout.append(stdout)
            all_stderr.append(stderr)
            timed_out = timed_out or episode_timed_out
            parsed_session_id = self._extract_session_id(stdout)
            if parsed_session_id:
                if session_id and parsed_session_id != session_id:
                    exit_code = exit_code or 1
                    all_stderr.append(
                        f"Codex resumed an unexpected session {parsed_session_id}; expected {session_id}\n"
                    )
                else:
                    session_id = parsed_session_id

            status = self._read_status(descriptor.private_root)
            self._augment_runtime_status(descriptor.private_root, status, session_id, episode)
            scope_violations = self._task_scope_violations(
                descriptor,
                launcher_root / "spec",
            )
            scope_violation = bool(scope_violations)
            if scope_violation or timed_out or exit_code != 0:
                break

            accepted_root = descriptor.private_root / "accepted_baseline" / "merged"
            clean_matches_accepted = accepted_root.is_dir() and self._trees_equal(
                descriptor.merged_root, accepted_root
            )
            if (
                status.get("phase") != "clean_accepted"
                or not self._valid_rtl_tree(descriptor.merged_root)
                or not clean_matches_accepted
            ):
                self._restore_private_baseline(descriptor)
                status = self._read_status(descriptor.private_root)

            latest = status.get("latest") if isinstance(status.get("latest"), dict) else {}
            if bool(latest.get("is_pass")):
                if self._parent_episode_passes(descriptor, episode):
                    break
            budgets = status.get("budgets") if isinstance(status.get("budgets"), dict) else {}
            if int(budgets.get("validation_trials") or 0) >= descriptor.max_validation_trials:
                break
            if not session_id:
                resume_unavailable = True
                break

        stdout = "".join(all_stdout)
        stderr = "".join(all_stderr)
        for filename, content in (("codex_trace.jsonl", stdout), ("codex_events.jsonl", stdout), ("codex_stderr.log", stderr)):
            with (descriptor.private_root / filename).open("a", encoding="utf-8") as stream:
                stream.write(content)

        status = self._read_status(descriptor.private_root)
        accepted_root = descriptor.private_root / "accepted_baseline" / "merged"
        clean_matches_accepted = accepted_root.is_dir() and self._trees_equal(descriptor.merged_root, accepted_root)
        if scope_violation:
            # A scope violation invalidates unvalidated task edits, not an RTL
            # revision that the validation service already linted, simulated,
            # and explicitly accepted.  Preserve that accepted baseline so the
            # caller writes the validated RTL back to the Stage 6 workspace.
            if accepted_root.is_dir() and self._valid_rtl_tree(accepted_root):
                self._restore_private_baseline(descriptor)
            else:
                self._replace_tree(launcher_root / "merged", descriptor.merged_root)
            self._replace_tree(launcher_root / "spec", descriptor.spec_root)
            self._remove_task_extras(descriptor.task_root)
            (descriptor.private_root / "scope_violation.json").write_text(
                json.dumps(
                    {"violations": scope_violations},
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        elif (
            status.get("phase") != "clean_accepted"
            or not self._valid_rtl_tree(descriptor.merged_root)
            or not clean_matches_accepted
        ):
            self._restore_private_baseline(descriptor)
            status = self._read_status(descriptor.private_root)

        final_dir = descriptor.private_root / "final_verify"
        reviewer = SystemSimReviewer(
            generated_dir=descriptor.merged_root,
            verify_script=descriptor.verify_script,
            output_dir=final_dir,
            timeout=descriptor.verifier_timeout,
        )
        verifier_pass, mismatch_count, sim_output = reviewer.review()
        is_pass = bool(verifier_pass) and not scope_violation
        final_output = descriptor.private_root / "final_sim_output.json"
        final_output.write_text(sim_output, encoding="utf-8")

        budgets = status.get("budgets") if isinstance(status.get("budgets"), dict) else {}
        accepted_actions = int(budgets.get("accepted_actions") or 0)
        validation_trials = int(budgets.get("validation_trials") or 0)
        reason_parts: list[str] = []
        if timed_out:
            reason_parts.append(f"Codex debug run timed out after {self.timeout}s")
        elif exit_code != 0:
            reason_parts.append(f"Codex process exited with code {exit_code}")
        elif resume_unavailable:
            reason_parts.append("Codex session id was unavailable, so the failed run could not resume")
        if scope_violation:
            detail = "; ".join(scope_violations[:4])
            reason_parts.append(
                "Codex modified files outside merged RTL or changed the read-only spec"
                + (f": {detail}" if detail else "")
            )
        if not verifier_pass:
            reason_parts.append("parent verifier rejected the accepted RTL baseline")
        top_rtl = descriptor.top_rtl
        rtl_code = top_rtl.read_text(encoding="utf-8", errors="replace") if top_rtl.is_file() else ""
        return RepoReActResult(
            status="pass" if is_pass else ("error" if exit_code != 0 and not validation_trials else "fail"),
            is_pass=bool(is_pass),
            rtl_code=rtl_code,
            steps=self._event_count(stdout),
            agent_turns=self._event_count(stdout, event_type="agent_message"),
            action_calls=accepted_actions,
            patch_attempts=validation_trials,
            mismatch_count=int(mismatch_count),
            trace_report_path=str(final_dir / "trace_report.json") if (final_dir / "trace_report.json").is_file() else "",
            sim_output_path=str(final_output),
            workdir=str(descriptor.private_root),
            reason="; ".join(reason_parts),
        )

    @staticmethod
    def _write_descriptor(path: Path, descriptor: CodexDebugRunDescriptor) -> None:
        temporary = path.with_name(f".{path.name}.tmp")
        temporary.write_text(descriptor.model_dump_json(indent=2) + "\n", encoding="utf-8")
        temporary.chmod(0o600)
        temporary.replace(path)

    def build_command(
        self,
        descriptor: CodexDebugRunDescriptor,
        descriptor_path: Path,
        last_message_path: Path,
        prompt: str,
    ) -> list[str]:
        command = [
            self.codex_bin,
            "exec",
        ]
        if self.profile:
            command.extend(["--profile", self.profile])
        command.extend(
            [
                "--json",
                *self._feature_args(),
                "--skip-git-repo-check",
                "--sandbox",
                "workspace-write",
                "--cd",
                str(descriptor.task_root),
                "--output-last-message",
                str(last_message_path),
                "--config",
                'approval_policy="never"',
                "--config",
                'sandbox_mode="workspace-write"',
                "--config",
                "tools.web_search=false",
                *self._mcp_config_args(descriptor, descriptor_path),
            ]
        )
        if self.profile:
            command.extend(["--config", 'forced_login_method="api"'])
        if self.model and not self.profile:
            command.extend(["--model", self.model])
        command.append(prompt)
        return command

    def build_resume_command(
        self,
        descriptor: CodexDebugRunDescriptor,
        descriptor_path: Path,
        last_message_path: Path,
        session_id: str,
        prompt: str,
    ) -> list[str]:
        if not session_id:
            raise ValueError("A Codex session id is required for resume")
        command = [
            self.codex_bin,
            "exec",
            "resume",
            "--json",
            *self._feature_args(),
            "--skip-git-repo-check",
            "--output-last-message",
            str(last_message_path),
            "--config",
            'approval_policy="never"',
            "--config",
            'sandbox_mode="workspace-write"',
            "--config",
            "tools.web_search=false",
            *self._mcp_config_args(descriptor, descriptor_path),
        ]
        if self.profile:
            command.extend(["--config", 'forced_login_method="api"'])
        if self.model and not self.profile:
            command.extend(["--model", self.model])
        command.extend([session_id, prompt])
        return command

    def _feature_args(self) -> list[str]:
        arguments: list[str] = []
        for feature in ("plugins", "apps", "browser_use", "computer_use", "image_generation"):
            arguments.extend(["--disable", feature])
        arguments.extend(["--enable" if self.multi_agent else "--disable", "multi_agent"])
        return arguments

    @staticmethod
    def _mcp_config_args(
        descriptor: CodexDebugRunDescriptor, descriptor_path: Path
    ) -> list[str]:
        server_args = [
            "-m",
            "zerorepo.rtl_impl.codex_debug.mcp_server",
            "--run-descriptor",
            str(descriptor_path),
        ]
        if os.environ.get('ZEROREPO_WEB_JOB')=='1':
            server_args=['-m','zerorepo.rtl_impl.codex_debug.mcp_server','--bridge']
        package_root = Path(__file__).resolve().parents[3]
        values = [
            f"mcp_servers.zerorepo_rtl_debug.command={json.dumps(sys.executable)}",
            f"mcp_servers.zerorepo_rtl_debug.args={json.dumps(server_args)}",
            f"mcp_servers.zerorepo_rtl_debug.env.PYTHONPATH={json.dumps(str(package_root))}",
            f"mcp_servers.zerorepo_rtl_debug.env.PATH={json.dumps(os.environ.get('PATH', ''))}",
            "mcp_servers.zerorepo_rtl_debug.required=true",
            f"mcp_servers.zerorepo_rtl_debug.enabled_tools={json.dumps(TOOL_NAMES)}",
            f"mcp_servers.zerorepo_rtl_debug.startup_timeout_sec={descriptor.verifier_timeout + 60}",
            f"mcp_servers.zerorepo_rtl_debug.tool_timeout_sec={descriptor.verifier_timeout + 60}",
        ]
        arguments: list[str] = []
        for value in values:
            arguments.extend(["--config", value])
        return arguments

    def profile_layers(self):
        """Read exactly the layers used by the runner, without creating state."""
        if not self.profile or Path(self.profile).name != self.profile:
            raise ValueError("Codex profile must be a plain profile name")

        source_home = Path(
            os.environ.get("CODEX_HOME") or (Path.home() / ".codex")
        ).expanduser().resolve()
        source_profile = source_home / f"{self.profile}.config.toml"
        if not source_profile.is_file() or source_profile.is_symlink():
            raise FileNotFoundError(
                f"Codex profile `{self.profile}` was not found under {source_home}"
            )

        source_base = source_home / "config.toml"
        base_config = self._read_toml(source_base) if source_base.is_file() else {}
        profile_config = self._read_toml(source_profile)
        self._require_provider_environment(base_config, profile_config)

        return source_home, source_profile, base_config, profile_config

    def _prepare_private_codex_home(self, private_root: Path) -> Path:
        """Copy only config layers needed by the selected profile into this run."""

        source_home, source_profile, base_config, profile_config = self.profile_layers()

        target_home = (private_root / "codex_home").resolve()
        if target_home == source_home or source_home.is_relative_to(target_home):
            raise ValueError("Private CODEX_HOME overlaps the source CODEX_HOME")
        target_home.mkdir(parents=True, mode=0o700, exist_ok=True)

        # exec resume does not accept --profile. Its default config must still
        # resolve to the selected profile/provider, without credentials in argv.
        effective = self._merge_config(base_config, profile_config)
        if os.environ.get('ZEROREPO_WEB_JOB')=='1':
            # Do not expose unrelated MCP credentials/providers to the model view.
            effective.pop('mcp_servers',None)
            provider=effective.get('model_provider','openai')
            effective['model_providers']={provider:effective.get('model_providers',{}).get(provider,{})}
            if 'profiles' in effective:
                effective['profiles']={self.profile:effective['profiles'].get(self.profile,{})}
        target_base = target_home / "config.toml"
        binding_path = target_home / "provider_binding.json"
        binding = self._provider_binding(effective)
        if binding_path.exists():
            previous = json.loads(binding_path.read_text(encoding="utf-8"))
            if previous != binding:
                raise RuntimeError("Selected Codex profile/provider configuration changed; existing session preserved")
        elif target_base.exists() and (target_home / "sessions").exists():
            # Older sessions have no binding marker. Compare their actual
            # persisted provider defaults before migrating, never overwrite them.
            if self._provider_binding(self._read_toml(target_base)) != binding:
                raise RuntimeError("Selected Codex provider differs from the saved session; existing session preserved")
        target_base.write_text(self._serialize_toml(effective), encoding="utf-8")
        target_base.chmod(0o600)
        target_profile = target_home / source_profile.name
        shutil.copy2(source_profile, target_profile)
        target_profile.chmod(0o600)
        binding_path.write_text(json.dumps(binding, sort_keys=True), encoding="utf-8")
        binding_path.chmod(0o600)
        return target_home

    def _provider_binding(self, config):
        provider = config.get("model_provider") or "openai"
        relevant = {"profile": self.profile, "model": config.get("model"),
                    "provider": provider, "configuration": (config.get("model_providers") or {}).get(provider, {})}
        # Provider configuration may contain credentials; persist only its digest.
        return {"fingerprint": hashlib.sha256(json.dumps(relevant, sort_keys=True).encode()).hexdigest()}

    @classmethod
    def _merge_config(cls, base, override):
        result = dict(base) if isinstance(base, dict) else {}
        for key, value in override.items():
            result[key] = cls._merge_config(result.get(key, {}), value) if isinstance(value, dict) else value
        return result

    @classmethod
    def _serialize_toml(cls, data, prefix=()):
        def value(item):
            if isinstance(item, bool):
                return "true" if item else "false"
            if isinstance(item, (int, float, str)):
                return json.dumps(item, ensure_ascii=False)
            if isinstance(item, list):
                return "[" + ", ".join(value(v) for v in item) + "]"
            if isinstance(item, dict):
                return "{" + ", ".join(json.dumps(k) + " = " + value(v) for k, v in item.items()) + "}"
            raise ValueError("Unsupported Codex profile config value")
        lines = []
        if prefix:
            lines.append("[" + ".".join(json.dumps(k) for k in prefix) + "]")
        lines.extend(json.dumps(k) + " = " + value(v) for k, v in data.items() if not isinstance(v, dict))
        for key, entry in data.items():
            if isinstance(entry, dict):
                lines.append(cls._serialize_toml(entry, (*prefix, key)))
        return "\n".join(lines) + "\n"

    @staticmethod
    def _read_toml(path: Path) -> dict[str, Any]:
        try:
            value = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise ValueError(f"Unable to read Codex config {path.name}: {exc}") from exc
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _require_provider_environment(
        base_config: dict[str, Any], profile_config: dict[str, Any]
    ) -> None:
        provider_name = str(
            profile_config.get("model_provider")
            or base_config.get("model_provider")
            or "openai"
        )
        base_providers = base_config.get("model_providers")
        profile_providers = profile_config.get("model_providers")
        provider_config: dict[str, Any] = {}
        if isinstance(base_providers, dict) and isinstance(
            base_providers.get(provider_name), dict
        ):
            provider_config.update(base_providers[provider_name])
        if isinstance(profile_providers, dict) and isinstance(
            profile_providers.get(provider_name), dict
        ):
            provider_config.update(profile_providers[provider_name])
        if provider_name != "openai" and not provider_config:
            raise RuntimeError(f"Selected Codex provider `{provider_name}` has no configuration")
        env_key = provider_config.get("env_key")
        if isinstance(env_key, str) and env_key.strip() and not os.environ.get(env_key.strip()):
            raise RuntimeError(
                f"Codex provider `{provider_name}` requires environment variable "
                f"`{env_key.strip()}`"
            )
        if provider_name == "openai" and not env_key and not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("Selected OpenAI API provider requires OPENAI_API_KEY in the private Codex process")

    def _run_process(
        self,
        command: list[str],
        *,
        cwd: Path,
        tee_path: Path | None = None,
        process_env: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> tuple[int, bool, str, str]:
        if self.logger is not None:
            self.logger.info("[codex_debug] Starting task-scoped Codex process in %s", cwd)
        process = subprocess.Popen(
            command,
            cwd=str(cwd),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
            env=process_env,
        )
        # Tee stdout to a file in real-time so the user can `tail -f` the trace.
        tee_file = None
        if tee_path is not None:
            tee_path.parent.mkdir(parents=True, exist_ok=True)
            tee_file = open(str(tee_path), "w", encoding="utf-8")  # noqa: SIM115
        stdout_chunks: list[str] = []
        stderr_chunks: list[str] = []

        def _read_stdout() -> None:
            assert process.stdout is not None
            for line in iter(process.stdout.readline, ""):
                stdout_chunks.append(line)
                if tee_file is not None:
                    tee_file.write(line)
                    tee_file.flush()
                    try:
                        event = json.loads(line)
                        if event.get("type") == "thread.started" and isinstance(event.get("thread_id"), str):
                            descriptor_path = tee_path.parent / "run_descriptor.json"
                            active = CodexDebugRunDescriptor.model_validate_json(descriptor_path.read_text())
                            if not active.codex_session_id or active.codex_session_id == event["thread_id"]:
                                from zerorepo.rtl_impl.module_planner.utils.artifact_store import atomic_write_json
                                runtime = {"run_id": active.run_id, "session_id": event["thread_id"],
                                           "episode": active.codex_episode, "resumed": active.codex_episode > 1}
                                atomic_write_json(tee_path.parent / "active_runtime.json", runtime)
                                self._write_descriptor(descriptor_path, active.model_copy(update={"codex_session_id": event["thread_id"]}))
                    except (OSError, ValueError, TypeError, AttributeError):
                        pass

        def _read_stderr() -> None:
            assert process.stderr is not None
            for line in iter(process.stderr.readline, ""):
                stderr_chunks.append(line)

        stdout_reader = threading.Thread(target=_read_stdout, daemon=True)
        stderr_reader = threading.Thread(target=_read_stderr, daemon=True)
        stdout_reader.start()
        stderr_reader.start()
        effective_timeout = self.timeout if timeout is None else max(0.1, float(timeout))
        try:
            process.wait(timeout=effective_timeout)
            timed_out = False
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            timed_out = True
        except BaseException:
            # An interrupted parent must not leave a detached Codex process
            # editing the task while a later invocation resumes its state.
            try:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
            except ProcessLookupError:
                pass
            raise
        finally:
            stdout_reader.join(timeout=5)
            stderr_reader.join(timeout=5)
            if tee_file is not None:
                tee_file.close()
        stdout = "".join(stdout_chunks)
        stderr = "".join(stderr_chunks)
        return int(process.returncode or 0), timed_out, stdout, stderr

    @staticmethod
    def _extract_session_id(payload: str) -> str:
        for line in payload.splitlines():
            try:
                event = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            if str(event.get("type") or "") == "thread.started":
                value = event.get("thread_id")
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return ""

    @classmethod
    def _augment_runtime_status(
        cls,
        private_root: Path,
        status: dict[str, Any],
        session_id: str,
        episode: int,
    ) -> None:
        if not status:
            return
        status["codex_runtime"] = {
            "session_id": session_id,
            "episode": episode,
            "resumed": episode > 1,
        }
        path = private_root / "debug_status.json"
        temporary = path.with_name(f".{path.name}.runner.tmp")
        temporary.write_text(json.dumps(status, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        temporary.chmod(0o600)
        temporary.replace(path)

    @staticmethod
    def _parent_episode_passes(descriptor: CodexDebugRunDescriptor, episode: int) -> bool:
        reviewer = SystemSimReviewer(
            generated_dir=descriptor.merged_root,
            verify_script=descriptor.verify_script,
            output_dir=descriptor.private_root / "episode_verify" / f"episode_{episode:03d}",
            timeout=descriptor.verifier_timeout,
        )
        verifier_pass, _mismatch_count, _sim_output = reviewer.review()
        return bool(verifier_pass)

    @staticmethod
    def _read_status(private_root: Path) -> dict[str, Any]:
        path = private_root / "debug_status.json"
        if not path.is_file():
            return {}
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except Exception:  # noqa: BLE001
            return {}

    @staticmethod
    def _valid_rtl_tree(root: Path) -> bool:
        try:
            return all(
                not path.is_symlink() and (not path.is_file() or path.suffix.lower() in {".v", ".sv"})
                for path in root.rglob("*")
            )
        except OSError:
            return False

    @classmethod
    def _task_scope_valid(cls, descriptor: CodexDebugRunDescriptor, spec_baseline: Path) -> bool:
        return not cls._task_scope_violations(descriptor, spec_baseline)

    @classmethod
    def _task_scope_violations(
        cls,
        descriptor: CodexDebugRunDescriptor,
        spec_baseline: Path,
    ) -> list[str]:
        violations: list[str] = []
        try:
            if not cls._trees_equal(descriptor.spec_root, spec_baseline):
                violations.append("read-only spec tree changed")
            for path in descriptor.task_root.rglob("*"):
                relative = path.relative_to(descriptor.task_root)
                if not relative.parts or relative.parts[0] not in {"spec", "merged"}:
                    violations.append(
                        f"out-of-scope task path: {relative.as_posix()}"
                    )
                if path.is_symlink():
                    violations.append(f"task symlink: {relative.as_posix()}")
            if not cls._valid_rtl_tree(descriptor.merged_root):
                violations.append("merged RTL tree contains a symlink or non-RTL file")
        except OSError as exc:
            violations.append(f"scope inspection failed: {type(exc).__name__}: {exc}")
        return list(dict.fromkeys(violations))

    @staticmethod
    def _tree_manifest(root: Path) -> dict[str, str]:
        manifest: dict[str, str] = {}
        if not root.is_dir():
            return manifest
        for path in sorted(root.rglob("*")):
            if path.is_symlink():
                manifest[f"!symlink:{path.relative_to(root).as_posix()}"] = ""
            elif path.is_file():
                manifest[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        return manifest

    @classmethod
    def _trees_equal(cls, first: Path, second: Path) -> bool:
        return cls._tree_manifest(first) == cls._tree_manifest(second)

    @staticmethod
    def _replace_tree(source: Path, target: Path) -> None:
        target.mkdir(parents=True, exist_ok=True)
        for child in list(target.iterdir()):
            if child.is_dir() and not child.is_symlink():
                shutil.rmtree(child)
            else:
                child.unlink(missing_ok=True)
        for item in source.rglob("*"):
            relative = item.relative_to(source)
            destination = target / relative
            if item.is_dir() and not item.is_symlink():
                destination.mkdir(parents=True, exist_ok=True)
            elif item.is_file() and not item.is_symlink():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, destination)

    @staticmethod
    def _remove_task_extras(task_root: Path) -> None:
        for child in list(task_root.iterdir()):
            if child.name in {"spec", "merged"}:
                continue
            if child.is_dir() and not child.is_symlink():
                shutil.rmtree(child)
            else:
                child.unlink(missing_ok=True)

    @staticmethod
    def _restore_private_baseline(descriptor: CodexDebugRunDescriptor) -> None:
        source = descriptor.private_root / "accepted_baseline" / "merged"
        if not source.is_dir():
            source = descriptor.private_root / "launcher_baseline" / "merged"
        if not source.is_dir():
            return
        descriptor.merged_root.mkdir(parents=True, exist_ok=True)
        for child in list(descriptor.merged_root.iterdir()):
            if child.is_dir() and not child.is_symlink():
                shutil.rmtree(child)
            else:
                child.unlink(missing_ok=True)
        for item in source.rglob("*"):
            relative = item.relative_to(source)
            target = descriptor.merged_root / relative
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            elif item.is_file() and item.suffix.lower() in {".v", ".sv"} and not item.is_symlink():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, target)

    @staticmethod
    def _event_count(payload: str, *, event_type: str = "") -> int:
        count = 0
        for line in payload.splitlines():
            try:
                event = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            item = event.get("item") if isinstance(event.get("item"), dict) else {}
            matches_type = str(event.get("type") or "") == event_type
            if event_type == "agent_message" and str(item.get("type") or "") == event_type:
                matches_type = True
            if not event_type or matches_type:
                count += 1
        return count
