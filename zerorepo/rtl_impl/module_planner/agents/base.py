from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type

from pydantic import BaseModel
from zerorepo.rpg_gen.base.llm_client import AssistantMessage, Memory, SystemMessage, UserMessage
from zerorepo.rpg_gen.base.llm_client.errors import LLMRequestError

from ..interfaces import (
    NullPlanningArtifactSink,
    NullPlanningContextProvider,
    PlanningArtifactSink,
    PlanningContextProvider,
)
from ..utils import PlannerLLMClient, get_planner_logger, repair_json_payload
from ..utils.local_repair import ArtifactIssue, fingerprint, patch_rejection_details, repair_prompt
from ..utils.artifact_store import atomic_write_json
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
        if not is_observing():
            return self.llm_client.complete_with_memory(memory=memory, images=images, **kwargs)
        from copy import deepcopy
        request_memory = deepcopy(memory)
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
                callback(text)
            from zerorepo.rtl_impl.public_progress import request_progress_callback
            progress=request_progress_callback(public_emitter(),step,options)
            prior_progress=options.progress_callback
            def on_progress(snapshot):
                if prior_progress:prior_progress(snapshot)
                progress(snapshot)
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
    ) -> BaseModel:
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

    def _invoke_local_repair(self, *, prompt, images, adapter, max_attempts=None):
        """Generate once, then repair explicit units using fresh, bounded contexts."""
        limit = max(1, int(max_attempts or max(self.max_parse_attempts, self.max_quality_attempts)))
        inspection = None
        patch_error = None
        patch_diagnostics = None
        for attempt in range(1, limit + 1):
            if inspection is None:
                request = prompt
                targets = None
            else:
                targets = adapter.targets(inspection)
                diagnostics = list(inspection.issues)
                if patch_error:
                    diagnostics.append(ArtifactIssue("patches", "invalid_patch", patch_error,
                        expected=patch_diagnostics["allowed_targets"], actual=patch_diagnostics))
                request = repair_prompt(
                    targets=targets, issues=diagnostics,
                    context=adapter.context_for(inspection, targets),
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
            raw = self._complete_public(**arguments, module=getattr(adapter, 'module', ''), attempt=attempt)
            self._log_llm_raw_output(raw, attempt_label="initial" if attempt == 1 else f"local_repair_{attempt - 1}")
            if inspection is None:
                inspection = adapter.inspect(raw)
            else:
                try:
                    candidate = adapter.merge(inspection, raw, targets)
                    inspection = adapter.inspect(candidate)
                    inspection.normalizations.extend(getattr(adapter, "merge_normalizations", []))
                    patch_error = None
                    patch_diagnostics = None
                except (ValueError, TypeError, KeyError, IndexError) as exc:
                    patch_error = str(exc)
                    patch_diagnostics = patch_rejection_details(raw, targets, patch_error)
                    self.logger.warning("[%s] Patch rejected: %s", self.stage_name, patch_diagnostics)
            for issue in inspection.issues:
                issue.stage = self.stage_name
                issue.module = getattr(adapter, "module", "")
            for change in inspection.normalizations:
                self.logger.info("[%s] Safe normalization: %s", self.stage_name, change)
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
                "[%s] Validation failed on attempt %d/%d: %s%s", self.stage_name, attempt, limit,
                [issue.to_dict() for issue in inspection.issues],
                f"; patch rejected: {patch_error}" if patch_error else "",
            )
            output_root = getattr(self, "output_root", None)
            if output_root is not None:
                draft = Path(output_root) / ".repair_drafts" / self.stage_name / fingerprint(prompt)[:16] / f"attempt_{attempt}.json"
                # Diagnostics are separate from successful artifacts/checkpoints.
                payload = {
                    "raw_output": raw.model_dump(mode="json") if isinstance(raw, BaseModel) else raw,
                    "candidate": inspection.candidate,
                    "issues": [issue.to_dict() for issue in inspection.issues],
                    "patch_error": patch_error, "normalizations": inspection.normalizations,
                    "patch_diagnostics": patch_diagnostics,
                }
                atomic_write_json(draft, payload)
        self._last_quality_errors = [f"{issue.path}: {issue.message}" for issue in inspection.issues]
        if patch_error:
            self._last_quality_errors.append(f"patches: {patch_error}")
        raise StageGenerationError(
            f"{self.stage_name} failed validation after {limit} attempts: " + "; ".join(self._last_quality_errors)
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

        for parse_attempt in range(1, parse_attempt_limit + 1):
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

    def _log_stage_input(
        self,
        prompt: str,
        images: List[str],
        stage_context: Dict[str, Any],
    ) -> None:
        self.logger.info(
            "\n========== %s INPUT ==========\n"
            "System Role:\n%s\n\n"
            "Images:\n%s\n\n"
            "Stage Context:\n%s\n\n"
            "Prompt:\n%s\n"
            "========== END %s INPUT ==========",
            self.stage_name,
            self.system_role,
            self.to_pretty_json(images),
            self.to_pretty_json(stage_context),
            prompt,
            self.stage_name,
        )

    def _log_llm_raw_output(self, raw: Any, attempt_label: str) -> None:
        body = raw if isinstance(raw, str) else self.to_pretty_json(raw)
        self.logger.info(
            "\n========== %s RAW OUTPUT (%s) ==========\n%s\n"
            "========== END %s RAW OUTPUT (%s) ==========",
            self.stage_name,
            attempt_label,
            body,
            self.stage_name,
            attempt_label,
        )

    def _log_retry_prompt(self, retry_prompt: str, reason: str) -> None:
        self.logger.info(
            "\n========== %s RETRY PROMPT (%s) ==========\n%s\n"
            "========== END %s RETRY PROMPT (%s) ==========",
            self.stage_name,
            reason,
            retry_prompt,
            self.stage_name,
            reason,
        )

    def _publish_output(self, artifact: BaseModel) -> None:
        from zerorepo.rtl_impl.public_artifact_report import artifact_report
        report=artifact_report(artifact)
        if report:
            emit_public('output.recorded',purpose_summary='已验证的本步材料',public_progress=report,
                        source_kind='runtime_observation')

    def _log_stage_output(self, artifact: BaseModel) -> None:
        self.logger.info(
            "\n========== %s VALIDATED OUTPUT ==========\n%s\n"
            "========== END %s VALIDATED OUTPUT ==========",
            self.stage_name,
            self.to_pretty_json(artifact),
            self.stage_name,
        )

    def _log_best_effort_output(self, artifact: BaseModel, quality_errors: List[str]) -> None:
        self.logger.warning(
            "\n========== %s BEST-EFFORT OUTPUT ==========\n"
            "Residual Quality Errors:\n%s\n\n%s\n"
            "========== END %s BEST-EFFORT OUTPUT ==========",
            self.stage_name,
            self.to_pretty_json(quality_errors),
            self.to_pretty_json(artifact),
            self.stage_name,
        )

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
