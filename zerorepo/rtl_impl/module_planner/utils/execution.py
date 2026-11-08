"""Durable planning operations and a single budget/usage boundary for requests."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import replace
from functools import wraps
import json
import os
import hashlib
from pathlib import Path
import time
from uuid import uuid4
from typing import Literal

from pydantic import BaseModel, Field

from zerorepo.rpg_gen.base.llm_client.errors import LLMRequestError
from .artifact_store import atomic_write_json
from .local_repair import fingerprint


PLANNING_POLICY_VERSION = "planning_harness_v2"
CHECKPOINT_VERSION = "planning_node_v2"
_CURRENT_NODE = ContextVar("planning_execution_node", default=None)


class PlanningBudgetExceeded(LLMRequestError):
    """A planning operation exhausted its current invocation's execution budget."""


def fatal_request_error(error):
    return isinstance(error, PlanningBudgetExceeded) or (
        isinstance(error, LLMRequestError) and error.diagnostics.get("http_status") in {400, 401, 403, 404, 422})


class PlanningNodeCheckpoint(BaseModel):
    version: str = CHECKPOINT_VERSION
    policy_version: str = PLANNING_POLICY_VERSION
    input_fingerprint: str
    template_fingerprint: str = ""
    scope_fingerprint: str = ""
    stage: str
    module: str = ""
    operation: str
    status: Literal["pending", "running", "interrupted", "needs_repair", "validated", "completed", "failed"] = "pending"
    candidate: object = None
    issues: list[dict] = Field(default_factory=list)
    feedback: list[dict] = Field(default_factory=list)
    targets: dict = Field(default_factory=dict)
    last_response: object = None
    last_error: str = ""
    api_attempts: int = 0
    content_rounds: int = 0
    elapsed_seconds: float = 0
    prompt_budget: dict = Field(default_factory=dict)


def _value(value):
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(k): _value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_value(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    return value


def template_fingerprint(stage=None):
    root = Path(__file__).resolve().parents[1] / "prompts"
    prefix = stage.split("_", 1)[0] if stage else ""
    return fingerprint({p.name: p.read_text(encoding="utf-8") for p in sorted(root.glob("*.py"))
                        if not prefix or p.stem.startswith(prefix)})


class PlanningNode:
    def __init__(self, executor, stage, module, operation, inputs):
        self.executor = executor
        templates = template_fingerprint(stage)
        key = fingerprint({"policy": PLANNING_POLICY_VERSION, "templates": templates,
                           "inputs": _value(inputs), "scope": executor.scope,
                           "model": executor.model, "stage": stage, "module": module, "operation": operation})
        self.path = executor.root / "plan/state/execution" / f"{key}.json"
        self.state = PlanningNodeCheckpoint(input_fingerprint=key, template_fingerprint=templates,
            scope_fingerprint=fingerprint(executor.scope), stage=stage, module=module, operation=operation)
        self.restored = False
        if executor.resume and self.path.is_file():
            try:
                saved = json.loads(self.path.read_text(encoding="utf-8"))
                checksum = saved.pop("checkpoint_fingerprint")
                if checksum != fingerprint(saved):
                    raise ValueError("Planning checkpoint checksum mismatch")
                state = PlanningNodeCheckpoint.model_validate(saved)
                if state.version != CHECKPOINT_VERSION or state.policy_version != PLANNING_POLICY_VERSION or state.input_fingerprint != key:
                    raise ValueError("Planning checkpoint version/input mismatch")
                self.state, self.restored = state, True
                if state.status == "running":
                    state.status = "interrupted"
            except (OSError, ValueError, KeyError, TypeError):
                pass  # Diagnostics alone never authorize importing an old draft.
        self.started = time.monotonic()
        self.attempts = 0
        self.prior_elapsed = self.state.elapsed_seconds

    @property
    def remaining(self):
        return self.executor.node_timeout - (time.monotonic() - self.started)

    def consume(self, _snapshot=None):
        if self.remaining <= 0 or self.attempts >= self.executor.max_attempts:
            raise PlanningBudgetExceeded("Planning node budget exhausted", stage=self.state.stage,
                                        module=self.state.module, operation=self.state.operation)
        self.attempts += 1
        self.state.api_attempts += 1
        self.state.status = "running"
        self.save()

    def save(self):
        self.state.elapsed_seconds = self.prior_elapsed + max(0, time.monotonic() - self.started)
        payload = self.state.model_dump(mode="json")
        atomic_write_json(self.path, {**payload, "checkpoint_fingerprint": fingerprint(payload)})

    def rebind(self, inputs):
        """Carry the live transaction after a validated upstream source addition.

        Only the node's trusted context builder can call this. A changed spec,
        model, template or unrelated upstream artifact still creates a fresh node.
        The previous journal remains diagnostic and is never implicitly imported.
        """
        target = PlanningNode(self.executor, self.state.stage, self.state.module, self.state.operation, inputs)
        if target.state.input_fingerprint == self.state.input_fingerprint:
            return
        self.path = target.path
        self.state.input_fingerprint = target.state.input_fingerprint
        self.executor._nodes[self.state.input_fingerprint] = self
        self.save()

    def inspect(self, candidate, issues=(), targets=None):
        self.state.candidate = _value(candidate)
        self.state.issues = [i.to_dict() if hasattr(i, "to_dict") else _value(i) for i in issues]
        self.state.targets = _value(targets or {})
        self.state.status = "needs_repair" if self.state.issues else "validated"
        self.save()


class RequestExecutor:
    def __init__(self, root, *, policy=None, model=None):
        self.root = Path(root)
        policy = policy or {}
        self.node_timeout = float(policy.get("node_timeout_seconds", 1800))
        self.max_attempts = int(policy.get("max_api_attempts", 10))
        self.max_prompt_chars = int(policy.get("max_prompt_chars", 256000))
        if self.node_timeout <= 0 or self.max_attempts < 1 or self.max_prompt_chars < 1:
            raise ValueError("Invalid planning execution budget")
        self.model = model or {}
        self.templates = template_fingerprint()
        self.resume, self.scope, self.case_id = False, {}, ""
        self.run_id = uuid4().hex
        self._nodes = {}

    def begin_run(self, task, *, resume):
        self.resume = resume
        self.case_id = task.task_id
        self.run_id = uuid4().hex
        self.templates = template_fingerprint()
        self.scope = {"task": _value(task), "sources": {
            str(Path(p).resolve()): fingerprint(Path(p).read_text(encoding="utf-8").replace("\r\n", "\n"))
            for p in task.spec_md_files}}
        self.scope["images"] = {str(Path(p).resolve()): hashlib.sha256(Path(p).read_bytes()).hexdigest() if Path(p).is_file() else None
                                for p in task.spec_images}
        self._nodes = {}

    @contextmanager
    def node(self, stage, module, operation, inputs):
        candidate = PlanningNode(self, stage, module, operation, inputs)
        node = self._nodes.setdefault(candidate.state.input_fingerprint, candidate)
        token = _CURRENT_NODE.set(node)
        try:
            yield node
        except BaseException as exc:
            node.state.status = "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
            node.state.last_error = f"{type(exc).__name__}: {exc}"
            node.save()
            raise
        finally:
            _CURRENT_NODE.reset(token)

    def record(self, record):
        record = {"policy_version": PLANNING_POLICY_VERSION, "case_id": self.case_id, "run_id": self.run_id, **record}
        path = self.root / "plan/state/request_usage.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(_value(record), ensure_ascii=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        self.summarize()

    def summarize(self):
        path = self.root / "plan/state/request_usage.jsonl"
        records = {}
        for line in path.read_text(encoding="utf-8").splitlines() if path.exists() else []:
            try:
                value = json.loads(line)
                if value.get("policy_version") != PLANNING_POLICY_VERSION:
                    continue
                records[(value["request_id"], value["transport_attempt"])] = value
            except (ValueError, KeyError):
                continue
        attempts = [r for r in records.values() if r["transport_attempt"] > 0]
        stages = {}
        for r in attempts:
            group = stages.setdefault(r["stage"], {"api_attempts": 0, "elapsed_seconds": 0,
                "input_chars": 0, "output_chars": 0, "unknown_usage_attempts": 0,
                "transport_retries": 0, "content_repair_attempts": 0,
                "known_cached_input_tokens": 0, "known_reasoning_tokens": 0,
                "unknown_cached_usage_attempts": 0, "unknown_reasoning_usage_attempts": 0,
                "known_input_tokens": 0, "known_output_tokens": 0, "known_total_tokens": 0})
            group["api_attempts"] += 1
            group["transport_retries"] += r["transport_attempt"] > 1
            group["content_repair_attempts"] += bool(r.get("is_repair"))
            for name in ("elapsed_seconds", "input_chars", "output_chars"):
                group[name] += r.get(name, 0)
            usage = r.get("usage")
            for source, total, unknown in (("cache_read_input_tokens", "known_cached_input_tokens", "unknown_cached_usage_attempts"),
                                           ("reasoning_tokens", "known_reasoning_tokens", "unknown_reasoning_usage_attempts")):
                detail = usage.get(source) if usage is not None else None
                if detail is None:
                    group[unknown] += 1
                else:
                    group[total] += detail
            if usage is None or usage.get("input_tokens") is None or usage.get("output_tokens") is None:
                group["unknown_usage_attempts"] += 1
            if usage is not None:
                for source, target in (("input_tokens", "known_input_tokens"), ("output_tokens", "known_output_tokens")):
                    if usage.get(source) is not None:
                        group[target] += usage[source]
                        group["known_total_tokens"] += usage[source]
        for stage, group in stages.items():
            stage_attempts = [r for r in attempts if r["stage"] == stage]
            group["logical_requests"] = len({r["request_id"] for r in stage_attempts})
            group["content_repair_requests"] = len({r["request_id"] for r in stage_attempts if r.get("is_repair")})
            group["full_object_regeneration_requests"] = len({r["request_id"] for r in stage_attempts if r.get("full_object_regeneration")})
        atomic_write_json(self.root / "plan/metrics.json", {
            "policy_version": PLANNING_POLICY_VERSION, "case_id": self.case_id,
            "latest_run_id": self.run_id,
            "latest_run_api_attempts": sum(r.get("run_id") == self.run_id for r in attempts),
            "api_attempts": len(attempts), "logical_requests": len({r["request_id"] for r in attempts}),
            "cache_reuses": sum(r.get("status") == "reused" for r in records.values()),
            "stages": stages,
        })

    def reuse(self, stage, module, operation):
        self.record({"request_id": uuid4().hex, "transport_attempt": 0, "stage": stage,
                     "module": module, "operation": operation, "status": "reused", "usage": None})

    def check_inputs(self):
        for path, expected in self.scope.get("sources", {}).items():
            try:
                actual = fingerprint(Path(path).read_text(encoding="utf-8").replace("\r\n", "\n"))
            except OSError as exc:
                raise LLMRequestError("Input specification is no longer readable", http_status=400) from exc
            if actual != expected:
                raise LLMRequestError("Input specification changed during planning; restart with current inputs", http_status=400)
        for path, expected in self.scope.get("images", {}).items():
            actual = hashlib.sha256(Path(path).read_bytes()).hexdigest() if Path(path).is_file() else None
            if actual != expected:
                raise LLMRequestError("Input image changed during planning", http_status=400)

    def execute(self, method, arguments, options, *, bounded=False, usage_reader=None):
        self.check_inputs()
        node = _CURRENT_NODE.get()
        if node is None and options.stage.startswith(("stage1", "stage2", "stage3", "stage4")):
            inputs = self.request_inputs(arguments)
            with self.node(options.stage, options.module, options.operation or options.stage, inputs) as standalone:
                if standalone.restored and standalone.state.last_response is not None:
                    self.reuse(options.stage, options.module, standalone.state.operation)
                    return standalone.state.last_response
                result = self.execute(method, arguments, options, bounded=bounded, usage_reader=usage_reader)
                standalone.state.status = "completed"
                standalone.save()
                return result
        started = time.monotonic()
        request_id = uuid4().hex
        inputs = self.request_inputs(arguments)
        input_chars = sum(len(str(m.get("content", ""))) for m in inputs.get("messages", []))
        if "messages" not in inputs:
            input_chars = len(inputs.get("system_prompt", "")) + len(inputs.get("user_prompt", ""))
        base = {"request_id": request_id, "stage": options.stage, "module": options.module,
                "operation": node.state.operation if node else options.operation,
                "model": self.model.get("model"), "provider": self.model.get("provider"),
                "node_id": node.state.input_fingerprint if node else "", "content_attempt": options.repair_attempt,
                "is_repair": bool(node and (node.state.candidate is not None or node.state.issues or node.state.feedback)),
                "full_object_regeneration": bool(node and node.state.targets.get("full")
                    and (node.state.candidate is not None or node.state.issues or node.state.feedback)),
                "input_chars": input_chars,
                "prompt_component_chars": node.state.prompt_budget.get("components", {}) if node else {},
                "context_section_chars": node.state.prompt_budget.get("context_sections", {}) if node else {}}
        snapshots = []
        accepted_attempts = []
        prior = options.progress_callback
        prior_attempt = options.attempt_callback

        def stream_diagnostics(snapshot):
            return {key: snapshot.get(key) for key in (
                "chunks", "content_chunks", "reasoning_chunks", "empty_chunks", "reasoning_chars",
                "first_content_seconds", "first_reasoning_seconds", "waiting_phase",
                "first_content_timeout_seconds", "reasoning_timeout_seconds", "total_timeout_seconds")}

        def attempt(snapshot):
            if node:
                node.consume(snapshot)
            accepted_attempts.append(snapshot.get("attempt", 1))
            if prior_attempt:
                prior_attempt(snapshot)

        def progress(snapshot):
            snapshots.append(snapshot)
            if snapshot.get("status") == "retrying":
                self.record({**base, "transport_attempt": snapshot["attempt"], "status": "retrying",
                    **stream_diagnostics(snapshot),
                    "elapsed_seconds": snapshot["attempt_elapsed_seconds"],
                    "output_chars": snapshot["content_chars"], "usage": None,
                    "timeout_reason": snapshot.get("timeout_reason")})
            if prior:
                prior(snapshot)

        total = min(options.total_timeout_seconds, node.remaining) if node else options.total_timeout_seconds
        if total <= 0:
            raise PlanningBudgetExceeded("Planning node time budget exhausted")
        if node:
            messages = inputs.get("messages", [])
            node.state.prompt_budget = {"input_chars": input_chars, "max_prompt_chars": self.max_prompt_chars,
                "fits": input_chars <= self.max_prompt_chars,
                "components": node.state.prompt_budget.get("components", {}),
                "context_sections": node.state.prompt_budget.get("context_sections", {}),
                "message_chars": [{"role": m.get("role"), "chars": len(str(m.get("content", "")))} for m in messages],
                "candidate_retained": node.state.candidate is not None}
            node.save()
        if input_chars > self.max_prompt_chars:
            raise PlanningBudgetExceeded(f"Planning prompt exceeds max_prompt_chars: {input_chars} > {self.max_prompt_chars}; "
                f"stage={options.stage}; module={options.module}; "
                "candidate and prompt size breakdown retained in execution checkpoint; no API attempt started")
        effective = replace(options, request_id=request_id, case_id=self.case_id,
            node_id=base["node_id"], operation=base["operation"], total_timeout_seconds=total,
            progress_callback=progress, attempt_callback=attempt)
        if bounded:
            arguments = {**arguments, "request_options": effective}
        else:
            attempt({"attempt": 1})  # Injected model doubles do not run the HTTP supervisor.
            if "request_options" in arguments:
                arguments = {**arguments, "request_options": effective}
        status, result, error = "failed", None, None
        try:
            result = method(**arguments)
            if node and node.remaining <= 0:
                raise PlanningBudgetExceeded("Planning node time budget exhausted")
            status = "completed"
            if node:
                node.state.last_response = _value(result)
                node.save()  # Durable before parse/validation or the next model call.
            return result
        except BaseException as exc:
            error = exc
            if node and node.remaining <= 0 and isinstance(exc, Exception) and not isinstance(exc, PlanningBudgetExceeded):
                raise PlanningBudgetExceeded("Planning node time budget exhausted") from exc
            raise
        finally:
            last = snapshots[-1] if snapshots else {}
            usage = usage_reader() if status == "completed" and usage_reader else None
            index = last.get("attempt", 1)
            if index not in accepted_attempts:
                index = 0  # Budget/capability rejection happened before starting I/O.
            self.record({**base, "transport_attempt": index, "status": status,
                **stream_diagnostics(last),
                "elapsed_seconds": last.get("attempt_elapsed_seconds", time.monotonic() - started),
                "output_chars": len(result) if isinstance(result, str) else len(json.dumps(_value(result))) if result is not None else last.get("content_chars", 0),
                "first_content_seconds": last.get("first_content_seconds"),
                "http_status": last.get("http_status"), "server_request_id": last.get("server_request_id"),
                "usage": usage, "timeout_reason": last.get("timeout_reason"),
                "error_type": type(error).__name__ if error else None})

    @staticmethod
    def request_inputs(arguments):
        if "memory" in arguments:
            return {"messages": [{"role": m.role, "content": m.content} for m in arguments["memory"].history],
                    "images": list(arguments.get("images") or [])}
        return {k: _value(v) for k, v in arguments.items() if k != "request_options"}


def current_node():
    return _CURRENT_NODE.get()


def prompt_semantic_view(value):
    """Match persisted planning views without dropping authoritative fact evidence."""
    if isinstance(value, dict):
        if {"facts", "ambiguous_items", "source_files"} <= set(value):
            return value
        return {k: prompt_semantic_view(v) for k, v in value.items()
                if k not in {"text_grounding", "input_fingerprint", "planning_policy_version"}}
    if isinstance(value, list):
        return [prompt_semantic_view(v) for v in value]
    return value


def planning_operation(function):
    """Attach a durable operation without coupling observer/UI state to policy."""
    @wraps(function)
    def wrapped(self, *args, **kwargs):
        executor = getattr(self.llm_client, "executor", None)
        if executor is None or not self.stage_name.startswith(("stage1", "stage2", "stage3", "stage4")):
            return function(self, *args, **kwargs)
        import inspect
        bound = inspect.signature(function).bind(self, *args, **kwargs)
        values = bound.arguments
        adapter = values.get("adapter")
        prompt = values.get("prompt", "")
        module = getattr(adapter, "module", "") or getattr(values.get("task_input"), "task_id", "")
        operation = getattr(self, "_retry_output_name", "") or getattr(values.get("output_model"), "__name__", "") or function.__name__
        with executor.node(self.stage_name, module, operation, {"prompt": prompt, "system": self.system_role}) as node:
            self._last_quality_errors = []
            result = function(self, *args, **kwargs)
            if not self._last_quality_errors:
                candidate = result.candidate if hasattr(result, "candidate") else _value(result)
                node.inspect(candidate)
                node.state.status = "completed"
                node.state.last_error = ""
                node.save()
            return result
    return wrapped
