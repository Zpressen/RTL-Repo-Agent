from __future__ import annotations

import base64
import importlib
import inspect
import mimetypes
from pathlib import Path
from zerorepo.rtl_impl.artifact_layout import ArtifactLayout
from typing import Any, Callable, Optional, Protocol
from zerorepo.rtl_impl.process_observer import observed

from zerorepo.rpg_gen.base.llm_client import LLMClient, LLMConfig, Memory, SystemMessage, UserMessage
from zerorepo.rpg_gen.base.llm_client.providers.completion_utils import create_chat_completion, request_with_retries
from zerorepo.rpg_gen.base.llm_client.providers.bounded_completion import create_bounded_chat_completion
from zerorepo.rpg_gen.base.llm_client.request_policy import LLMRequestOptions
from zerorepo.rpg_gen.base.llm_client.errors import LLMRequestError
from zerorepo.rpg_gen.base.llm_client.providers.llm_basics import LLMResponse, LLMUsage


class PlannerLLMBackend(Protocol):
    def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        images: Optional[list[str]] = None,
    ) -> Any:
        ...

    def complete_with_memory(
        self,
        *,
        memory: Memory,
        images: Optional[list[str]] = None,
    ) -> Any:
        ...


def _to_data_url(image_path: str) -> str:
    path = Path(image_path)
    mime_type, _ = mimetypes.guess_type(path.name)
    mime_type = mime_type or "application/octet-stream"
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{payload}"


class DefaultPlannerLLMBackend:
    def __init__(self, llm_config: LLMConfig | dict | str):
        self.config = LLMConfig.from_source(llm_config)
        self.client = LLMClient(self.config)

    def _build_async_openai_client(self):
        """Resolve fresh provider credentials without changing the shared client."""
        import httpx
        openai = self._import_openai()
        provider = getattr(self.client.client, "provider_config", None)
        source = provider.create_client(self.config) if provider else self._build_openai_client()
        try:
            kwargs = dict(api_key=source.api_key, base_url=str(source.base_url), max_retries=0,
                          organization=source.organization, project=source.project,
                          default_headers=dict(source._custom_headers), default_query=dict(source._custom_query),
                          timeout=httpx.Timeout(120, connect=15))
            if isinstance(source, openai.AzureOpenAI):
                kwargs.update(api_version=source._api_version, azure_ad_token=source._azure_ad_token,
                              azure_ad_token_provider=source._azure_ad_token_provider)
                return openai.AsyncAzureOpenAI(**kwargs)
            return openai.AsyncOpenAI(**kwargs)
        finally:
            source.close()

    def _complete_bounded(self, memory, images, options):
        messages = self._build_multimodal_messages_from_memory(memory=memory, images=images)
        kwargs = {"model": self.config.model, "messages": messages, "top_p": self.config.top_p, "n": 1}
        provider = getattr(self.client.client, "provider_config", None)
        reasoning = provider.is_reasoning_model(self.config.model) if provider else False
        if reasoning:
            kwargs.update(reasoning_effort=self.config.extra.get("reasoning_effort", "high"),
                          max_completion_tokens=options.max_tokens or self.config.max_tokens)
        else:
            kwargs.update(temperature=self.config.temperature, max_tokens=options.max_tokens or self.config.max_tokens)
        if self.config.stop:
            kwargs["stop"] = self.config.stop
        for name in ('response_format','reasoning_effort','extra_body'):
            if name in self.config.extra:
                kwargs[name]=self.config.extra[name]
        if provider and provider.get_extra_headers():
            kwargs["extra_headers"] = provider.get_extra_headers()
        response = create_bounded_chat_completion(self._build_async_openai_client, kwargs,
            stream=self.config.stream or options.content_callback is not None, include_usage=self.config.stream_include_usage,
            options=options, log=self.config.log)
        self.last_request_usage = None
        if response.usage is not None:
            prompt_details = getattr(response.usage, "prompt_tokens_details", None)
            completion_details = getattr(response.usage, "completion_tokens_details", None)
            self.last_request_usage = {
                "input_tokens": response.usage.prompt_tokens, "output_tokens": response.usage.completion_tokens,
                "cache_read_input_tokens": (getattr(prompt_details, "cached_tokens", None)
                    if getattr(prompt_details, "cached_tokens", None) is not None
                    else getattr(response.usage, "prompt_cache_hit_tokens", None)),
                "reasoning_tokens": (getattr(completion_details, "reasoning_tokens", None)
                    if getattr(completion_details, "reasoning_tokens", None) is not None
                    else getattr(response.usage, "reasoning_tokens", None)),
            }
        self.client._last_response = LLMResponse(content=response.choices[0].message.content,
            model=response.model, finish_reason=response.choices[0].finish_reason,
            usage=LLMUsage(input_tokens=response.usage.prompt_tokens, output_tokens=response.usage.completion_tokens,
                cache_read_input_tokens=getattr(getattr(response.usage, "prompt_tokens_details", None), "cached_tokens", 0) or 0,
                reasoning_tokens=getattr(getattr(response.usage, "completion_tokens_details", None), "reasoning_tokens", 0) or 0)
                  if response.usage is not None else None)
        return (response.choices[0].message.content or "").strip()

    def _supports_openai_vision(self) -> bool:
        provider = (self.config.resolve_provider() or "").strip().lower()
        return provider in {"openai", "azure", "openrouter", "deepseek", "vllm", "doubao"}

    def _build_openai_client(self) -> Any:
        openai = self._import_openai()
        kwargs: dict[str, Any] = {"max_retries": 0}
        api_key = self.config.api_key
        if api_key:
            kwargs["api_key"] = api_key
        if self.config.base_url:
            kwargs["base_url"] = self.config.base_url
        return openai.OpenAI(**kwargs)

    def _import_openai(self):
        try:
            return importlib.import_module("openai")
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Multimodal planner input requires the Python package `openai` "
                "for OpenAI-compatible vision requests."
            ) from exc

    def _complete_multimodal_openai_compatible_messages(
        self,
        *,
        messages: list[dict[str, Any]],
    ) -> Any:
        openai = self._import_openai()

        kwargs: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "top_p": self.config.top_p,
            "n": 1,
        }

        is_reasoning_model = (
            "o3" in self.config.model
            or "o4-mini" in self.config.model
            or "gpt-5" in self.config.model
        )
        if is_reasoning_model:
            kwargs["temperature"] = openai.NOT_GIVEN
            kwargs["reasoning_effort"] = self.config.extra.get("reasoning_effort", "high")
            kwargs["max_completion_tokens"] = self.config.max_tokens
        else:
            kwargs["temperature"] = self.config.temperature
            kwargs["max_tokens"] = self.config.max_tokens

        if self.config.stop:
            kwargs["stop"] = self.config.stop

        def request():
            client = self._build_openai_client()
            try:
                return create_chat_completion(
                    client, kwargs, stream=self.config.stream,
                    include_usage=self.config.stream_include_usage, log=self.config.log,
                )
            finally:
                close = getattr(client, "close", None)
                if close is not None:
                    close()

        response = request_with_retries(
            request, provider_name=self.config.resolve_provider(), max_retries=self.config.max_retries,
        )
        choice = response.choices[0]
        return (choice.message.content or "").strip()

    def _build_multimodal_messages_from_memory(
        self,
        *,
        memory: Memory,
        images: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        history = memory.history
        latest_user_index = None
        for index in range(len(history) - 1, -1, -1):
            if history[index].role == "user":
                latest_user_index = index
                break

        messages: list[dict[str, Any]] = []
        for index, message in enumerate(history):
            if message.role not in {"system", "user", "assistant"}:
                continue
            content: Any = message.content
            if (
                message.role == "user"
                and images
                and latest_user_index is not None
                and index == latest_user_index
            ):
                rich_content: list[dict[str, Any]] = [{"type": "text", "text": message.content}]
                for image_path in images:
                    rich_content.append(
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": _to_data_url(image_path),
                            },
                        }
                    )
                content = rich_content
            messages.append({"role": message.role, "content": content})
        return messages

    def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        images: Optional[list[str]] = None,
        request_options: LLMRequestOptions | None = None,
    ) -> Any:
        if request_options is not None and not self._supports_openai_vision():
            raise LLMRequestError("The configured production backend does not support bounded planning requests", http_status=400)
        if request_options is not None and self._supports_openai_vision():
            memory = Memory(context_window=6)
            memory.add_message(SystemMessage(content=system_prompt))
            memory.add_message(UserMessage(content=user_prompt))
            return self._complete_bounded(memory, images, request_options)
        if images and self._supports_openai_vision():
            memory = Memory(context_window=2)
            memory.add_message(SystemMessage(content=system_prompt))
            memory.add_message(UserMessage(content=user_prompt))
            return self.complete_with_memory(
                memory=memory,
                images=images,
            )

        memory = Memory(context_window=6)
        memory.add_message(SystemMessage(content=system_prompt))
        prompt = user_prompt
        if images:
            prompt = (
                f"{user_prompt}\n\n"
                f"Referenced image inputs (path only; multimodal backend may use them directly): {images}"
            )
        memory.add_message(UserMessage(content=prompt))
        return self.client.generate(memory=memory, max_retries=1, retry_delay=0.0)

    def complete_with_memory(
        self,
        *,
        memory: Memory,
        images: Optional[list[str]] = None,
        request_options: LLMRequestOptions | None = None,
    ) -> Any:
        if request_options is not None and not self._supports_openai_vision():
            raise LLMRequestError("The configured production backend does not support bounded planning requests", http_status=400)
        if request_options is not None and self._supports_openai_vision():
            return self._complete_bounded(memory, images, request_options)
        if images and self._supports_openai_vision():
            return self._complete_multimodal_openai_compatible_messages(
                messages=self._build_multimodal_messages_from_memory(memory=memory, images=images),
            )
        return self.client.generate(memory=memory, max_retries=1, retry_delay=0.0)


class PlannerLLMClient:
    def __init__(
        self,
        llm_config: Optional[LLMConfig | dict | str] = None,
        backend: Optional[PlannerLLMBackend | Callable[..., Any]] = None,
        request_policy: dict | None = None,
    ):
        if backend is None and llm_config is None:
            raise ValueError("PlannerLLMClient requires either llm_config or a custom backend.")
        self.config = LLMConfig.from_source(llm_config) if llm_config is not None else None
        self.backend = backend if backend is not None else DefaultPlannerLLMBackend(llm_config)
        if self.config is None:
            self.config = getattr(self.backend, "config", None)
        self.request_policy = request_policy or {}
        self.executor = None
        self.output_root = None

    def configure_execution(self, output_root, policy=None):
        from .execution import RequestExecutor
        self.output_root = Path(output_root)
        model = {k: getattr(self.config, k, None) for k in ("model", "provider", "temperature", "top_p", "max_tokens", "stop", "deployment_name", "api_version")}
        model["extra"] = {k: v for k, v in (getattr(self.config, "extra", {}) or {}).items()
                          if k in {"reasoning_effort", "response_format"}}
        from .local_repair import fingerprint
        model["endpoint_fingerprint"] = fingerprint({key: getattr(self.config, key, None)
            for key in ("base_url", "endpoint_url")})
        self.executor = RequestExecutor(output_root, policy=policy, model=model)

    def _usage(self):
        if hasattr(self.backend, "last_request_usage"):
            return self.backend.last_request_usage
        response = getattr(getattr(self.backend, "client", None), "_last_response", None)
        usage = getattr(response, "usage", None)
        return usage.to_dict() if usage is not None else None

    def request_options(self, *, stage, module, output_root=None, retrieval=False, attempt=1):
        values = {"total_timeout_seconds": 180 if retrieval else 600,
                  "max_tokens": 4096 if retrieval else None,
                  "first_content_timeout_seconds": 120 if retrieval else 240,
                  "retry_first_content_timeout": True, "retry_idle_timeout": True}
        if stage == "stage3_module_skeletons" and not retrieval:
            values.update(total_timeout_seconds=1200, first_content_timeout_seconds=480,
                          reasoning_timeout_seconds=900)
        values.update(self.request_policy.get("retrieval" if retrieval else "generation", {}))
        if stage == "stage5_codegen" and not retrieval:
            values.update(first_content_timeout_seconds=240, retry_first_content_timeout=True)
        values.update(self.request_policy.get("stages", {}).get(stage, {}))
        output_root = output_root if output_root is not None else self.output_root
        values.update(stage=stage, module=module, repair_attempt=attempt,
                      draft_root=ArtifactLayout(output_root).traces(stage).parent if output_root is not None else None)
        return LLMRequestOptions(**values)

    def _call_backend(self, method, arguments, request_options):
        # Existing injected backends do not have to accept the new optional interface.
        try:
            supported = "request_options" in inspect.signature(method).parameters
        except (ValueError, TypeError):
            supported = False
        if request_options is not None and supported:
            arguments["request_options"] = request_options
        if request_options is not None and self.executor is not None:
            return self.executor.execute(method, arguments, request_options,
                bounded=isinstance(self.backend, DefaultPlannerLLMBackend), usage_reader=self._usage)
        return method(**arguments)

    @observed("model", "请求当前规划步骤的模型输出")
    def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        images: Optional[list[str]] = None,
        request_options: LLMRequestOptions | None = None,
    ) -> Any:
        from zerorepo.rtl_impl.output_language import requirement
        if requirement():system_prompt=system_prompt+'\n\n'+requirement()
        backend_complete = getattr(self.backend, "complete", None)
        if backend_complete is not None and not isinstance(self.backend, type):
            return self._call_backend(backend_complete, dict(system_prompt=system_prompt,
                user_prompt=user_prompt, images=images), request_options)
        if callable(self.backend):
            return self._call_backend(self.backend, dict(system_prompt=system_prompt,
                user_prompt=user_prompt, images=images), request_options)
        return self._call_backend(self.backend.complete, dict(system_prompt=system_prompt,
            user_prompt=user_prompt, images=images), request_options)

    @observed("model", "请求当前规划步骤的模型输出")
    def complete_with_memory(
        self,
        *,
        memory: Memory,
        images: Optional[list[str]] = None,
        request_options: LLMRequestOptions | None = None,
    ) -> Any:
        from zerorepo.rtl_impl.output_language import requirement
        if requirement():
            from copy import deepcopy
            memory=deepcopy(memory)
            memory.add_message(SystemMessage(content=requirement()))
        backend_complete_with_memory = getattr(self.backend, "complete_with_memory", None)
        if backend_complete_with_memory is not None:
            return self._call_backend(backend_complete_with_memory, dict(memory=memory, images=images), request_options)
        if callable(self.backend):
            history = memory.history
            system_prompt = next((item.content for item in history if item.role == "system"), "")
            user_prompt = next((item.content for item in reversed(history) if item.role == "user"), "")
            return self._call_backend(self.backend, dict(system_prompt=system_prompt,
                user_prompt=user_prompt, images=images), request_options)
        history = memory.history
        system_prompt = next((item.content for item in history if item.role == "system"), "")
        user_prompt = next((item.content for item in reversed(history) if item.role == "user"), "")
        return self._call_backend(self.backend.complete, dict(system_prompt=system_prompt,
            user_prompt=user_prompt, images=images), request_options)
