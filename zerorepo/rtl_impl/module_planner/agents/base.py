from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from zerorepo.rtl_impl.artifact_layout import ArtifactLayout
from typing import Any, Callable, Dict, List, Optional, Type

from pydantic import BaseModel
from zerorepo.rpg_gen.base.llm_client import AssistantMessage, Memory, SystemMessage, UserMessage
from zerorepo.rpg_gen.base.llm_client.errors import LLMRequestError, LLMResponseTruncatedError

from ..interfaces import (
    NullPlanningArtifactSink,
    NullPlanningContextProvider,
    PlanningArtifactSink,
    PlanningContextProvider,
)
from ..utils import PlannerLLMClient, get_planner_logger, repair_json_payload
from ..utils.local_repair import ArtifactIssue, fingerprint, patch_rejection_details, repair_prompt, strict_json
from ..utils.artifact_store import atomic_write_json
from ..utils.execution import planning_operation, current_node, PlanningBudgetExceeded
from zerorepo.rtl_impl.process_observer import is_observing, emit_public, public_emitter
from zerorepo.rtl_impl.public_progress import public_step, current_step, live_report_callback, PUBLIC_INSTRUCTION


def validate_model(model_type: Type[BaseModel], payload: Any) -> BaseModel:
    try:
        return model_type.model_validate(payload)
    except AttributeError:
        return model_type.parse_obj(payload)


def model_dump(instance: BaseModel) -> Dict[str, Any]:
    try:
        return instance.model_dump()
    except AttributeError:
        return instance.dict()


class StageGenerationError(ValueError):
    """A recoverable LLM invocation, parse, or quality failure for one planning stage."""


class BaseStageAgent:
    stage_name: str = ""
    output_model: Type[BaseModel]
    system_role: str = ""
    max_parse_attempts: int = 3
    max_quality_attempts: int = 5
    allow_best_effort_quality_fallback: bool = True
    memory_context_window: int = 8

    def _complete_public(self, *, memory, images=None, output_model=None, module='', attempt=1, **kwargs):
        if "request_options" not in kwargs:
            factory = getattr(self.llm_client, "request_options", None)
            if factory:
                kwargs["request_options"] = factory(stage=self.stage_name, module=module,
                    output_root=getattr(self, "output_root", None), attempt=attempt)
        if not is_observing():
            return self.llm_client.complete_with_memory(memory=memory, images=images, **kwargs)
        from copy import deepcopy
        request_memory = deepcopy(memory)
        if not self.stage_name.startswith(("stage1", "stage2", "stage3", "stage4")):
            # Memory always retains its first system message; an extra trailing
            # system message may be ignored or trimmed by a backend.
            first_system=next((message for message in request_memory.history if message.role=='system'),None)
            if first_system is not None:first_system.content+='\n\n'+PUBLIC_INSTRUCTION
            else:request_memory.add_message(SystemMessage(content=PUBLIC_INSTRUCTION))
            latest=request_memory.last('user')
            if latest:latest.content+='\n\nWorkbench response: write _public_start FIRST (Chinese summary and this-call plan), then the required artifact fields, then _public_progress. These public fields are removed before artifact validation. Do not emit private reasoning.'
        model = output_model or getattr(self, 'output_model', None)
        operation=getattr(self,'_retry_output_name','')
        with public_step(self.stage_name, module=module, output=getattr(model, '__name__', ''), attempt=attempt):
            step=current_step()
            operation_names={'conservative_candidate':'保守方案','balanced_candidate':'均衡方案','modular_candidate':'模块化方案',
                             'architecture_ranking_first_pass':'首轮比较','architecture_ranking_second_pass':'交叉复核',
                             'architecture_ranking_adjudication':'分歧裁定'}
            if operation in operation_names:step['label']+=' · '+operation_names[operation]
            from dataclasses import replace
            from zerorepo.rpg_gen.base.llm_client.request_policy import LLMRequestOptions
            options=kwargs.get('request_options')
            if options is None:
                factory=getattr(self.llm_client,'request_options',None)
                options=factory(stage=self.stage_name,module=module,output_root=getattr(self,'output_root',None),attempt=attempt) if factory else LLMRequestOptions()
            callback=live_report_callback(public_emitter(),step)
            prior=options.content_callback
            def on_content(text):
                if prior:prior(text)
                try:
                    callback(text)
                except Exception as exc:
                    self.logger.warning("Workbench content observer failed (%s); request continues", type(exc).__name__)
            from zerorepo.rtl_impl.public_progress import request_progress_callback
            progress=request_progress_callback(public_emitter(),step,options)
            prior_progress=options.progress_callback
            def on_progress(snapshot):
                if prior_progress:prior_progress(snapshot)
                try:
                    progress(snapshot)
                except Exception as exc:
                    self.logger.warning("Workbench progress observer failed (%s); request continues", type(exc).__name__)
            kwargs['request_options']=replace(options,content_callback=on_content,progress_callback=on_progress)
            return self.llm_client.complete_with_memory(memory=request_memory, images=images, **kwargs)

    def __init__(
        self,
        llm_client: PlannerLLMClient,
        context_provider: Optional[PlanningContextProvider] = None,
        artifact_sink: Optional[PlanningArtifactSink] = None,
        logger=None,
    ):
        self.llm_client = llm_client
        self.context_provider = context_provider or NullPlanningContextProvider()
        self.artifact_sink = artifact_sink or NullPlanningArtifactSink()
        self.logger = logger or get_planner_logger(f"rtl_module_planner.{self.stage_name}")

    def run(self, task_input: Any, partial_artifacts: Dict[str, Any]) -> BaseModel:
        self._last_quality_errors: List[str] = []
        stage_context = self.context_provider.get_stage_context(
            self.stage_name,
            task_input,
            partial_artifacts,
        )
        prompt, images = self.build_prompt(task_input, partial_artifacts, stage_context)
        self._log_stage_input(prompt=prompt, images=images, stage_context=stage_context)
        artifact = self._invoke_with_repair(prompt, images, task_input, partial_artifacts)
        if self._last_quality_errors:
            self._log_best_effort_output(artifact, self._last_quality_errors)
        else:
            self._log_stage_output(artifact)
        self.artifact_sink.record_stage_output(self.stage_name, artifact, task_input)
        return artifact

    def build_prompt(
        self,
        task_input: Any,
        partial_artifacts: Dict[str, Any],
        stage_context: Dict[str, Any],
    ) -> tuple[str, List[str]]:
        raise NotImplementedError

    def validate_quality(
        self,
        artifact: BaseModel,
        task_input: Any,
        partial_artifacts: Dict[str, Any],
    ) -> List[str]:
        return []

    def _invoke_with_repair(
        self,
        prompt: str,
        images: List[str],
        task_input: Any,
        partial_artifacts: Dict[str, Any],
        output_model: Optional[Type[BaseModel]] = None,
        quality_validator: Optional[Callable[[BaseModel], List[str]]] = None,
        prompt_view=None,
    ) -> BaseModel:
        if self.stage_name.startswith(("stage1", "stage2")) and getattr(self.llm_client, "executor", None) is not None:
            return self._invoke_json_node(prompt, images, task_input, partial_artifacts,
                                          output_model, quality_validator, prompt_view=prompt_view)
        if prompt_view:
            prompt = prompt_view({"full": True})
        memory = self._create_stage_memory()
        memory.add_message(SystemMessage(content=self.system_role))
        return self._invoke_with_repair_on_memory(
            memory=memory,
            prompt=prompt,
            images=images,
            task_input=task_input,
            partial_artifacts=partial_artifacts,
            output_model=output_model,
            quality_validator=quality_validator,
        )

    def _invoke_json_node(self, prompt, images, task_input, partial_artifacts, output_model, quality_validator, *, prompt_view=None):
        from ..utils.planning_session import PlanningSession
        model = output_model or self.output_model
        validator = quality_validator or (lambda artifact: self.validate_quality(artifact, task_input, partial_artifacts))
        def validate(payload):
            try:
                artifact = self._coerce_output(payload, output_model=model)
            except (ValueError, TypeError) as exc:
                return None, [ArtifactIssue("$", "invalid_structure", str(exc), category="structure")]
            return artifact, [ArtifactIssue("$", "domain_validation", message, category="hardware",
                                           stage=self.stage_name) for message in validator(artifact)]
        result = PlanningSession(self).execute(module=getattr(task_input, "task_id", ""), prompt=prompt,
            context={"schema": model.model_json_schema()}, images=images, validate=validate,
            operation=getattr(self, "_retry_output_name", "") or model.__name__,
            scope_builder=lambda candidate, issues: {"full": True}, prompt_view=prompt_view)
        if result.status != "validated":
            raise StageGenerationError(f"{self.stage_name} needs_repair: " + "; ".join(i.message for i in result.issues or []))
        self._last_quality_errors = []
        self._publish_output(result.artifact)
        return result.artifact

    @planning_operation
    def _invoke_local_repair(self, *, prompt, images, adapter, max_attempts=None, allow_progress_extension=False):
        """Generate once, then repair explicit units using fresh, bounded contexts."""
        limit = max(1, int(max_attempts or max(self.max_parse_attempts, self.max_quality_attempts)))
        inspection = None
        node = current_node()
        ceiling = max(limit, node.executor.max_attempts) if node and allow_progress_extension else limit
        progress_seen, stagnant, attempts_used = False, 0, 0

        def apply_response(previous, response, targets):
            apply = getattr(adapter, "apply_response", None)
            if apply:
                return apply(previous, response, targets)
            candidate = adapter.merge(previous, response, targets)
            proposed = adapter.inspect(candidate)
            validate_transition = getattr(adapter, "validate_transition", None)
            if validate_transition:
                validate_transition(previous, proposed)
            return proposed

        if node and node.restored:
            saved = node.state.candidate if node.state.candidate is not None else node.state.last_response
            if saved is not None:
                inspection = adapter.inspect(saved)
                if not inspection.issues and inspection.artifact is not None:
                    self.llm_client.executor.reuse(self.stage_name, node.state.module, node.state.operation)
                    self._last_quality_errors = []
                    return inspection
                # A complete response may have been persisted before validation,
                # or rejected by an older transition check. Replay only the
                # fingerprinted checkpoint's patch, under today's full checks.
                pending = node.state.last_response
                if node.state.candidate is not None and getattr(adapter, "replay_saved_patch", False):
                    try:
                        payload = strict_json(pending)
                        if isinstance(payload, dict) and set(payload) == {"patches"}:
                            proposed = apply_response(inspection, payload, adapter.targets(inspection))
                            if proposed.candidate != inspection.candidate:
                                self.logger.info("[%s] Revalidated saved repair: %d -> %d issues",
                                                 self.stage_name, len(inspection.issues), len(proposed.issues))
                                inspection = proposed
                                node.inspect(inspection.candidate, inspection.issues,
                                             adapter.targets(inspection) if inspection.issues else {})
                                self.llm_client.executor.reuse(self.stage_name, node.state.module,
                                                               node.state.operation + ".saved_patch")
                    except (ValueError, TypeError, KeyError, IndexError):
                        adapter.inspect(inspection.candidate)
                    if not inspection.issues and inspection.artifact is not None:
                        self._last_quality_errors = []
                        return inspection
        patch_error = None
        patch_diagnostics = None
        for attempt in range(1, ceiling + 1):
            if attempt > limit and (not progress_seen or stagnant >= 2):
                self.logger.warning("[%s] Stopped local repair after %d calls: no recent validated progress",
                                    self.stage_name, attempts_used)
                break
            attempts_used = attempt
            previous = inspection
            if inspection is None:
                initial_request = getattr(adapter, "initial_request", None)
                request = initial_request(prompt) if initial_request else prompt
                if request != prompt:
                    self.logger.info("[%s] Shared initial context for %s: expanded=%d, request=%d chars",
                                     self.stage_name, getattr(adapter, "module", ""), len(prompt), len(request))
                targets = None
            else:
                targets = adapter.targets(inspection)
                if node:
                    node.inspect(inspection.candidate, inspection.issues, targets)
                diagnostics = list(inspection.issues)
                if patch_error:
                    diagnostics.append(ArtifactIssue("patches", "invalid_patch", patch_error,
                        expected=patch_diagnostics["allowed_targets"], actual=patch_diagnostics))
                request = repair_prompt(
                    targets=targets, issues=diagnostics,
                    context=adapter.context_for(inspection, targets),
                    compact=self.stage_name.startswith(("stage1", "stage2", "stage3", "stage4")),
                )
                self._log_retry_prompt(request, reason=f"local_repair_attempt_{attempt - 1}")
            memory = self._create_stage_memory()
            memory.add_message(SystemMessage(content=self.system_role + (
                "\nFor repair requests, obey the JSON patch output format in the user message."
            )))
            memory.add_message(UserMessage(content=request))
            # Request errors are deliberately outside parse/patch exception handling.
            arguments = dict(memory=memory, images=images or None)
            options = getattr(self.llm_client, "request_options", None)
            if options and self.stage_name.startswith(("stage3", "stage4", "stage5")):
                arguments["request_options"] = options(stage=self.stage_name, module=getattr(adapter, "module", ""),
                    output_root=getattr(self, "output_root", None), attempt=attempt)
            try:
                raw = self._complete_public(**arguments, module=getattr(adapter, 'module', ''), attempt=attempt)
            except LLMResponseTruncatedError as exc:
                stagnant += 1
                patch_error = str(exc)
                patch_diagnostics = {"allowed_targets": sorted(targets or {}), "response_kind": "truncated"}
                if node:
                    node.state.last_error = str(exc)
                    node.save()
                continue
            self._log_llm_raw_output(raw, attempt_label="initial" if attempt == 1 else f"local_repair_{attempt - 1}")
            if inspection is None:
                inspection = adapter.inspect(raw)
                patch_error = None
                patch_diagnostics = None
            else:
                try:
                    proposed = apply_response(inspection, raw, targets)
                    inspection = proposed
                    inspection.normalizations.extend(getattr(adapter, "merge_normalizations", []))
                    patch_error = None
                    patch_diagnostics = None
                except (ValueError, TypeError, KeyError, IndexError) as exc:
                    # Some adapters retain parser state during inspect(). A
                    # rejected proposal must not change subsequent targets.
                    adapter.inspect(inspection.candidate)
                    patch_error = str(exc)
                    patch_diagnostics = patch_rejection_details(raw, targets, patch_error)
                    self.logger.warning("[%s] Patch rejected: %s", self.stage_name, patch_diagnostics)
            if previous is not None:
                before = Counter((i.code, i.path, i.unit_id) for i in previous.issues)
                after = Counter((i.code, i.path, i.unit_id) for i in inspection.issues)
                made_progress = inspection.candidate != previous.candidate and bool(before - after)
                progress_seen = progress_seen or made_progress
                stagnant = 0 if made_progress else stagnant + 1
                if made_progress and attempt >= limit and inspection.issues and ceiling > limit:
                    self.logger.info("[%s] Retained progress; continuing within node budget (%d remaining issue(s))",
                                     self.stage_name, len(inspection.issues))
            for issue in inspection.issues:
                issue.stage = self.stage_name
                issue.module = getattr(adapter, "module", "")
            for change in inspection.normalizations:
                self.logger.info("[%s] Safe normalization: %s", self.stage_name, change)
            if node:
                node.inspect(inspection.candidate, inspection.issues, adapter.targets(inspection) if inspection.issues else {})
            if self.stage_name.startswith('stage5') and isinstance(inspection.candidate,dict) and isinstance(inspection.candidate.get('code'),str):
                from zerorepo.rtl_impl.material_observer import current_publisher
                publisher=current_publisher()
                if publisher is not None:
                    publisher.capture_fragment_text(inspection.candidate['code'],getattr(adapter,'module',''),getattr(adapter,'locked',{}).get('subtask_id','fragment'))
            if not inspection.issues and not patch_error and inspection.artifact is not None:
                self._last_quality_errors = []
                self._publish_output(inspection.artifact)
                return inspection
            emit_public('finding.created', purpose_summary='本步结果需要局部修正',
                        result_summary=f'{self.stage_name} 第{attempt}次结果有{len(inspection.issues)}项约束问题'+('，补丁未被接受。' if patch_error else '，将针对缺项修正。'))
            self.logger.warning(
                "[%s] Validation failed on attempt %d/%d: %s%s", self.stage_name, attempt, ceiling,
                [{"code": issue.code, "path": issue.path, "unit_id": issue.unit_id, "message": issue.message}
                 for issue in inspection.issues],
                f"; patch rejected: {patch_error}" if patch_error else "",
            )
            output_root = getattr(self, "output_root", None)
            if output_root is not None:
                draft = ArtifactLayout(output_root).traces(self.stage_name, "repairs") / (getattr(adapter, "module", "") or "global") / fingerprint(prompt)[:16] / f"attempt_{attempt}.json"
                # Diagnostics are separate from successful artifacts/checkpoints.
                payload = {
                    "raw_output": raw.model_dump(mode="json") if isinstance(raw, BaseModel) else raw,
                    "candidate": inspection.candidate,
                    "issues": [issue.to_dict() for issue in inspection.issues],
                    "patch_error": patch_error, "normalizations": inspection.normalizations,
                    "patch_diagnostics": patch_diagnostics,
                    "rejected_patch_groups": getattr(adapter, "last_patch_rejections", []),
                }
                atomic_write_json(draft, payload)
        if inspection is None:
            raise StageGenerationError(f"{self.stage_name} returned no complete candidate after {attempts_used} attempts")
        self._last_quality_errors = [f"{issue.path}: {issue.message}" for issue in inspection.issues]
        if patch_error:
            self._last_quality_errors.append(f"patches: {patch_error}")
        if allow_progress_extension and node and (node.attempts >= node.executor.max_attempts or node.remaining <= 0):
            raise PlanningBudgetExceeded(
                f"Planning node budget exhausted after {attempts_used} content attempts; "
                f"{len(inspection.issues)} issues remain; validated candidate progress retained",
                stage=self.stage_name, module=getattr(adapter, "module", ""),
            )
        raise StageGenerationError(
            f"{self.stage_name} failed validation after {attempts_used} attempts: " + "; ".join(self._last_quality_errors)
        )

    def _invoke_with_repair_using_memory(
        self,
        *,
        base_memory: Memory,
        prompt: str,
        images: List[str],
        task_input: Any,
        partial_artifacts: Dict[str, Any],
        output_model: Optional[Type[BaseModel]] = None,
        quality_validator: Optional[Callable[[BaseModel], List[str]]] = None,
    ) -> BaseModel:
        memory = Memory(context_window=base_memory.context_window)
        memory.load_snapshot(base_memory.snapshot())
        return self._invoke_with_repair_on_memory(
            memory=memory,
            prompt=prompt,
            images=images,
            task_input=task_input,
            partial_artifacts=partial_artifacts,
            output_model=output_model,
            quality_validator=quality_validator,
        )

    @planning_operation
    def _invoke_with_repair_on_memory(
        self,
        *,
        memory: Memory,
        prompt: str,
        images: List[str],
        task_input: Any,
        partial_artifacts: Dict[str, Any],
        output_model: Optional[Type[BaseModel]] = None,
        quality_validator: Optional[Callable[[BaseModel], List[str]]] = None,
    ) -> BaseModel:
        parse_attempt_limit = max(1, int(getattr(self, "max_parse_attempts", 2)))
        parse_errors: List[str] = []
        artifact: Optional[BaseModel] = None

        node = current_node()
        if node and node.restored:
            saved = node.state.candidate if node.state.candidate is not None else node.state.last_response
            if saved is not None:
                try:
                    artifact = self._coerce_output(saved, output_model=output_model)
                    memory.add_message(UserMessage(content=prompt))
                    memory.add_message(AssistantMessage(content=self.to_pretty_json(artifact)))
                    self.llm_client.executor.reuse(self.stage_name, node.state.module, node.state.operation)
                except (ValueError, TypeError):
                    pass

        for parse_attempt in range(1, parse_attempt_limit + 1):
            if artifact is not None:
                break
            retry_prompt = prompt if parse_attempt == 1 else self._build_retry_prompt(prompt, parse_errors[-1:])
            if parse_attempt > 1:
                self._log_retry_prompt(retry_prompt, reason=f"parse_failure_attempt_{parse_attempt - 1}")
            memory.add_message(UserMessage(content=retry_prompt))
            self.logger.info(
                "[%s] Calling LLM backend for parse attempt %d/%d (prompt_chars=%d, images=%d)",
                self.stage_name,
                parse_attempt,
                parse_attempt_limit,
                len(retry_prompt),
                len(images or []),
            )
            try:
                raw = self._complete_public(memory=memory, images=images or None, output_model=output_model, attempt=parse_attempt, module=getattr(task_input,'task_id',''))
            except LLMResponseTruncatedError as exc:
                parse_errors.append(str(exc))
                continue
            except LLMRequestError:
                raise
            except Exception as exc:
                parse_errors.append(f"LLM invocation failed: {exc}")
                self.logger.warning(
                    "[%s] LLM invocation failed on parse attempt %d/%d: %s",
                    self.stage_name,
                    parse_attempt,
                    parse_attempt_limit,
                    exc,
                )
                continue
            if parse_attempt == 1:
                self._log_llm_raw_output(raw, attempt_label="initial")
            else:
                self._log_llm_raw_output(raw, attempt_label=f"retry_after_parse_failure_{parse_attempt - 1}")
            memory.add_message(AssistantMessage(content=raw if isinstance(raw, str) else self.to_pretty_json(raw)))
            try:
                artifact = self._coerce_output(raw, output_model=output_model)
                break
            except Exception as exc:
                parse_errors.append(str(exc))
                if hasattr(exc, 'errors'):
                    issues = exc.errors(include_input=False)
                    fields = ['.'.join(map(str, issue['loc'])) for issue in issues[:3]]
                    reason = f'结构检查发现{len(issues)}项字段问题：' + '、'.join(fields) + '。'
                else:
                    reason = '返回内容不是可解析的 JSON，需修正字符串转义或结构。'
                next_action = ('将保留输入并请求修正。' if parse_attempt < parse_attempt_limit
                               else '已达到本步重试上限，本轮停止；原始结果已保留。')
                emit_public('finding.created', purpose_summary='模型结果格式尚未通过检查',
                            result_summary=f'{self.stage_name} 第{parse_attempt}次结果未通过检查。{reason}{next_action}')
                self.logger.warning(
                    "[%s] Parse failed on attempt %d/%d: %s",
                    self.stage_name,
                    parse_attempt,
                    parse_attempt_limit,
                    exc,
                )

        if artifact is None:
            raise StageGenerationError(
                f"{self.stage_name} output failed parse after {parse_attempt_limit} attempts: {parse_errors[-1]}"
            )

        validator = quality_validator or (
            lambda parsed_artifact: self.validate_quality(parsed_artifact, task_input, partial_artifacts)
        )
        quality_attempt_limit = max(1, int(getattr(self, "max_quality_attempts", 5)))
        quality_errors = validator(artifact)
        if node:
            node.inspect(model_dump(artifact), [{"message": e} for e in quality_errors])
        best_artifact = artifact
        best_quality_errors = list(quality_errors)
        if not quality_errors:
            self._last_quality_errors = []
            self._publish_output(artifact)
            return artifact

        current_errors = list(quality_errors)
        emit_public('finding.created', purpose_summary='本步结果仍有待解决的约束',
                    result_summary=f'{self.stage_name} 检查发现{len(quality_errors)}项问题，将修正当前结果；尚未进行HDL仿真。')
        for quality_attempt in range(2, quality_attempt_limit + 1):
            self.logger.warning(
                "[%s] Quality check failed on attempt %d/%d: %s",
                self.stage_name,
                quality_attempt - 1,
                quality_attempt_limit,
                current_errors,
            )
            retry_prompt = self._build_retry_prompt(prompt, current_errors)
            self._log_retry_prompt(retry_prompt, reason=f"quality_failure_attempt_{quality_attempt - 1}")
            memory.add_message(UserMessage(content=retry_prompt))
            self.logger.info(
                "[%s] Calling LLM backend for quality retry %d/%d (prompt_chars=%d, images=%d)",
                self.stage_name,
                quality_attempt,
                quality_attempt_limit,
                len(retry_prompt),
                len(images or []),
            )
            try:
                raw = self._complete_public(memory=memory, images=images or None, output_model=output_model, attempt=quality_attempt, module=getattr(task_input,'task_id',''))
            except LLMResponseTruncatedError as exc:
                current_errors = [str(exc)]
                continue
            except LLMRequestError:
                raise
            except Exception as exc:
                current_errors = [f"LLM invocation failed during quality retry: {exc}"]
                self.logger.warning(
                    "[%s] LLM invocation failed on quality attempt %d/%d: %s",
                    self.stage_name,
                    quality_attempt,
                    quality_attempt_limit,
                    exc,
                )
                continue
            self._log_llm_raw_output(raw, attempt_label=f"retry_after_quality_failure_{quality_attempt - 1}")
            memory.add_message(AssistantMessage(content=raw if isinstance(raw, str) else self.to_pretty_json(raw)))
            try:
                candidate = self._coerce_output(raw, output_model=output_model)
            except Exception as exc:
                current_errors = [f"parse_failure during quality retry: {exc}"]
                self.logger.warning(
                    "[%s] Parse failed during quality retry %d/%d: %s",
                    self.stage_name,
                    quality_attempt,
                    quality_attempt_limit,
                    exc,
                )
                continue
            candidate_errors = validator(candidate)
            if node:
                node.inspect(model_dump(candidate), [{"message": e} for e in candidate_errors])
            if len(candidate_errors) < len(best_quality_errors):
                best_artifact = candidate
                best_quality_errors = list(candidate_errors)
            if not candidate_errors:
                self._last_quality_errors = []
                self._publish_output(candidate)
                return candidate
            current_errors = list(candidate_errors)

        if self.allow_best_effort_quality_fallback:
            self._last_quality_errors = list(best_quality_errors)
            self.logger.warning(
                "[%s] Quality checks still failed after %d attempts; continuing with best-effort artifact: %s",
                self.stage_name,
                quality_attempt_limit,
                best_quality_errors,
            )
            return best_artifact

        raise StageGenerationError(
            f"{self.stage_name} output failed quality checks after {quality_attempt_limit} attempts; "
            f"last_candidate_errors={current_errors}; best_candidate_errors={best_quality_errors}; "
            "selected_candidate_reason=fewest_quality_errors"
        )

    def _create_stage_memory(self) -> Memory:
        context_window = max(
            int(getattr(self, "memory_context_window", 8)),
            int(getattr(self, "max_parse_attempts", 2)) + int(getattr(self, "max_quality_attempts", 5)) + 1,
        )
        return Memory(context_window=context_window)

    def _coerce_output(
        self,
        raw: Any,
        output_model: Optional[Type[BaseModel]] = None,
    ) -> BaseModel:
        if isinstance(raw, BaseModel):
            payload = model_dump(raw)
        else:
            payload = repair_json_payload(raw)
        artifact = validate_model(output_model or self.output_model, payload)
        return artifact

    def _build_retry_prompt(self, original_prompt: str, errors: List[str]) -> str:
        return (
            f"{original_prompt}\n\n"
            "The previous output was invalid. Fix it and return the full JSON again.\n"
            f"Issues:\n- " + "\n- ".join(errors)
        )

    def _trace_event(self, kind, payload):
        self.logger.info("[%s] %s%s", self.stage_name, kind,
                         f" ({len(str(payload))} chars)" if kind in {"input", "response"} else "")
        root = getattr(self, "output_root", None)
        if root is not None and getattr(self.llm_client, "retention", "compact") == "full":
            path = ArtifactLayout(root).traces(self.stage_name, "events") / "events.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({"kind": kind, "payload": self._json_ready(payload)}, ensure_ascii=False, default=str) + "\n")

    def _log_stage_input(
        self,
        prompt: str,
        images: List[str],
        stage_context: Dict[str, Any],
    ) -> None:
        self._trace_event("input", {"system_role": self.system_role, "prompt": prompt, "images": images, "context": stage_context})

    def _log_llm_raw_output(self, raw: Any, attempt_label: str) -> None:
        self._trace_event("response", {"attempt": attempt_label, "raw": self._json_ready(raw)})

    def _log_retry_prompt(self, retry_prompt: str, reason: str) -> None:
        self._trace_event("retry", {"reason": reason, "prompt": retry_prompt})

    def _publish_output(self, artifact: BaseModel) -> None:
        from zerorepo.rtl_impl.public_artifact_report import artifact_report
        report=artifact_report(artifact)
        if report:
            emit_public('output.recorded',purpose_summary='已验证的本步材料',public_progress=report,
                        source_kind='runtime_observation')

    def _log_stage_output(self, artifact: BaseModel) -> None:
        self._trace_event("validated", self._json_ready(artifact))

    def _log_best_effort_output(self, artifact: BaseModel, quality_errors: List[str]) -> None:
        self.logger.warning("[%s] Best-effort result retains quality issues: %s", self.stage_name, quality_errors)
        self._trace_event("best_effort", {"quality_errors": quality_errors, "artifact": self._json_ready(artifact)})

    @staticmethod
    def to_pretty_json(payload: Any) -> str:
        return json.dumps(BaseStageAgent._json_ready(payload), ensure_ascii=False, indent=2)

    @staticmethod
    def _json_ready(payload: Any) -> Any:
        if isinstance(payload, BaseModel):
            return model_dump(payload)
        if isinstance(payload, list):
            return [BaseStageAgent._json_ready(item) for item in payload]
        if isinstance(payload, dict):
            return {key: BaseStageAgent._json_ready(value) for key, value in payload.items()}
        return payload
