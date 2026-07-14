from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional, Type

from pydantic import BaseModel
from zerorepo.rpg_gen.base.llm_client import AssistantMessage, Memory, SystemMessage, UserMessage

from ..interfaces import (
    NullPlanningArtifactSink,
    NullPlanningContextProvider,
    PlanningArtifactSink,
    PlanningContextProvider,
)
from ..utils import PlannerLLMClient, get_planner_logger, repair_json_payload


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


class BaseStageAgent:
    stage_name: str = ""
    output_model: Type[BaseModel]
    system_role: str = ""
    max_parse_attempts: int = 3
    max_quality_attempts: int = 5
    allow_best_effort_quality_fallback: bool = True
    memory_context_window: int = 8

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
            raw = self.llm_client.complete_with_memory(memory=memory, images=images or None)
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
                self.logger.warning(
                    "[%s] Parse failed on attempt %d/%d: %s",
                    self.stage_name,
                    parse_attempt,
                    parse_attempt_limit,
                    exc,
                )

        if artifact is None:
            raise ValueError(
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
            return artifact

        current_errors = list(quality_errors)
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
            raw = self.llm_client.complete_with_memory(memory=memory, images=images or None)
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

        raise ValueError(
            f"{self.stage_name} output failed quality checks after {quality_attempt_limit} attempts: {best_quality_errors}"
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
