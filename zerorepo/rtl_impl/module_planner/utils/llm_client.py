from __future__ import annotations

import base64
import importlib
import mimetypes
from pathlib import Path
from typing import Any, Callable, Optional, Protocol

from zerorepo.rpg_gen.base.llm_client import LLMClient, LLMConfig, Memory, SystemMessage, UserMessage


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

    def _supports_openai_vision(self) -> bool:
        provider = (self.config.resolve_provider() or "").strip().lower()
        return provider in {"openai", "azure", "openrouter", "deepseek", "vllm", "doubao"}

    def _build_openai_client(self) -> Any:
        openai = self._import_openai()
        kwargs: dict[str, Any] = {}
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
        client = self._build_openai_client()

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

        response = client.chat.completions.create(**kwargs)
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
    ) -> Any:
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
    ) -> Any:
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
    ):
        if backend is None and llm_config is None:
            raise ValueError("PlannerLLMClient requires either llm_config or a custom backend.")
        self.backend = backend if backend is not None else DefaultPlannerLLMBackend(llm_config)

    def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        images: Optional[list[str]] = None,
    ) -> Any:
        backend_complete = getattr(self.backend, "complete", None)
        if backend_complete is not None and not isinstance(self.backend, type):
            return backend_complete(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                images=images,
            )
        if callable(self.backend):
            return self.backend(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                images=images,
            )
        return self.backend.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            images=images,
        )

    def complete_with_memory(
        self,
        *,
        memory: Memory,
        images: Optional[list[str]] = None,
    ) -> Any:
        backend_complete_with_memory = getattr(self.backend, "complete_with_memory", None)
        if backend_complete_with_memory is not None:
            return backend_complete_with_memory(
                memory=memory,
                images=images,
            )
        if callable(self.backend):
            history = memory.history
            system_prompt = next((item.content for item in history if item.role == "system"), "")
            user_prompt = next((item.content for item in reversed(history) if item.role == "user"), "")
            return self.backend(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                images=images,
            )
        history = memory.history
        system_prompt = next((item.content for item in history if item.role == "system"), "")
        user_prompt = next((item.content for item in reversed(history) if item.role == "user"), "")
        return self.backend.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            images=images,
        )
