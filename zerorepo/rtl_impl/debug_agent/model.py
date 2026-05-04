from __future__ import annotations

import json
from typing import Any

from agentscope.formatter import OpenAIChatFormatter
from agentscope.formatter._truncated_formatter_base import TruncatedFormatterBase
from agentscope.message import (
    Msg,
    TextBlock,
    ThinkingBlock,
    ImageBlock,
    AudioBlock,
    ToolUseBlock,
    ToolResultBlock,
)
from agentscope.model import ChatModelBase, OpenAIChatModel

from .config import OpenAIConfig


class Llama4ChatFormatter(TruncatedFormatterBase):
    """Formatter for Llama-4 models that converts tool results to user messages.
    
    Llama-4 (via OpenAI-compatible APIs) does not support the "tool" role.
    This formatter converts tool_result blocks into user messages with formatted
    content instead of using the "tool" role.
    """

    support_tools_api: bool = True
    support_multiagent: bool = True
    support_vision: bool = True

    supported_blocks: list[type] = [
        TextBlock,
        ImageBlock,
        AudioBlock,
        ToolUseBlock,
        ToolResultBlock,
    ]

    async def _format(
        self,
        msgs: list[Msg],
    ) -> list[dict[str, Any]]:
        """Format message objects into Llama-4 compatible format.
        
        Tool results are converted to user messages instead of using "tool" role.
        """
        self.assert_list_of_msgs(msgs)

        messages: list[dict] = []
        for msg in msgs:
            content_blocks = []
            tool_calls = []
            tool_results = []

            for block in msg.get_content_blocks():
                typ = block.get("type")
                if typ == "text":
                    content_blocks.append({**block})

                elif typ == "tool_use":
                    tool_calls.append(
                        {
                            "id": block.get("id"),
                            "type": "function",
                            "function": {
                                "name": block.get("name"),
                                "arguments": json.dumps(
                                    block.get("input", {}),
                                    ensure_ascii=False,
                                ),
                            },
                        },
                    )

                elif typ == "tool_result":
                    # Collect tool results to convert to user message format
                    tool_name = block.get("name", "tool")
                    tool_id = block.get("id", "")
                    tool_output = self.convert_tool_result_to_string(
                        block.get("output"),  # type: ignore[arg-type]
                    )
                    tool_results.append({
                        "name": tool_name,
                        "id": tool_id,
                        "output": tool_output,
                    })

                elif typ == "image":
                    source_type = block["source"]["type"]
                    if source_type == "url":
                        url = block["source"]["url"]
                    elif source_type == "base64":
                        data = block["source"]["data"]
                        media_type = block["source"]["media_type"]
                        url = f"data:{media_type};base64,{data}"
                    else:
                        raise ValueError(
                            f"Unsupported image source type: {source_type}",
                        )

                    content_blocks.append(
                        {
                            "type": "image_url",
                            "image_url": {"url": url},
                        },
                    )

                elif typ == "audio":
                    # Llama-4 may not support audio; skip or handle gracefully
                    pass

            # Build the message
            msg_dict = {
                "role": msg.role,
                "name": msg.name,
                "content": content_blocks or None,
            }

            if tool_calls:
                msg_dict["tool_calls"] = tool_calls

            # Add regular message if it has content or tool_calls
            if msg_dict["content"] or msg_dict.get("tool_calls"):
                messages.append(msg_dict)

            # Convert tool results to user messages (Llama-4 compatible format)
            for tr in tool_results:
                tool_result_text = (
                    f"[Tool Result: {tr['name']}]\n"
                    f"{tr['output']}"
                )
                messages.append({
                    "role": "user",
                    "content": [{"type": "text", "text": tool_result_text}],
                })

        return messages


class DeepSeekReasoningChatFormatter(TruncatedFormatterBase):
    """DeepSeek formatter that preserves thinking blocks as reasoning_content."""

    support_tools_api: bool = True
    support_multiagent: bool = False
    support_vision: bool = False

    supported_blocks: list[type] = [
        TextBlock,
        ThinkingBlock,
        ToolUseBlock,
        ToolResultBlock,
    ]

    async def _format(
        self,
        msgs: list[Msg],
    ) -> list[dict[str, Any]]:
        """Format message objects into DeepSeek API format.

        AgentScope 1.0.7's built-in DeepSeek formatter skips ThinkingBlock, but
        DeepSeek thinking mode requires previous assistant reasoning_content to
        be passed back in follow-up requests.
        """
        self.assert_list_of_msgs(msgs)

        messages: list[dict] = []
        for msg in msgs:
            content_blocks: list[dict[str, Any]] = []
            thinking_blocks: list[str] = []
            tool_calls = []

            for block in msg.get_content_blocks():
                typ = block.get("type")
                if typ == "text":
                    content_blocks.append({**block})

                elif typ == "thinking":
                    thinking = block.get("thinking", "")
                    if thinking:
                        thinking_blocks.append(str(thinking))

                elif typ == "tool_use":
                    tool_calls.append(
                        {
                            "id": block.get("id"),
                            "type": "function",
                            "function": {
                                "name": block.get("name"),
                                "arguments": json.dumps(
                                    block.get("input", {}),
                                    ensure_ascii=False,
                                ),
                            },
                        },
                    )

                elif typ == "tool_result":
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": block.get("id"),
                            "content": self.convert_tool_result_to_string(
                                block.get("output"),  # type: ignore[arg-type]
                            ),
                            "name": block.get("name"),
                        },
                    )

            content_msg = "\n".join(
                content.get("text", "") for content in content_blocks
            )
            msg_deepseek: dict[str, Any] = {
                "role": msg.role,
                "content": content_msg or None,
            }

            if thinking_blocks and msg.role == "assistant":
                msg_deepseek["reasoning_content"] = "\n".join(thinking_blocks)

            if tool_calls:
                msg_deepseek["tool_calls"] = tool_calls

            if (
                msg_deepseek["content"]
                or msg_deepseek.get("tool_calls")
                or msg_deepseek.get("reasoning_content")
            ):
                messages.append(msg_deepseek)

        return messages


class UsageTrackingModel(ChatModelBase):
    def __init__(self, base_model: ChatModelBase) -> None:
        self._base_model = base_model
        super().__init__(
            model_name=base_model.model_name,
            stream=base_model.stream,
        )
        self._input_tokens = 0
        self._output_tokens = 0

    @property
    def model_name(self) -> str:  # type: ignore[override]
        return self._base_model.model_name if hasattr(self, "_base_model") else self.__dict__.get("model_name", "")

    @model_name.setter
    def model_name(self, value: str) -> None:  # type: ignore[override]
        self.__dict__["model_name"] = value
        if hasattr(self, "_base_model"):
            self._base_model.model_name = value

    @property
    def stream(self) -> bool:  # type: ignore[override]
        return self._base_model.stream if hasattr(self, "_base_model") else bool(self.__dict__.get("stream", False))

    @stream.setter
    def stream(self, value: bool) -> None:
        self.__dict__["stream"] = value
        if hasattr(self, "_base_model"):
            self._base_model.stream = value

    @property
    def total_input_tokens(self) -> int:
        return self._input_tokens

    @property
    def total_output_tokens(self) -> int:
        return self._output_tokens

    def reset_usage(self) -> None:
        self._input_tokens = 0
        self._output_tokens = 0

    def _accumulate_usage(self, usage: Any) -> None:
        if usage is None:
            return
        self._input_tokens += int(getattr(usage, "input_tokens", 0) or 0)
        self._output_tokens += int(getattr(usage, "output_tokens", 0) or 0)

    async def __call__(self, *args: Any, **kwargs: Any):  # type: ignore[override]
        res = await self._base_model(*args, **kwargs)
        if self._base_model.stream:
            async def _gen():
                seen_usage = False
                async for chunk in res:
                    if (not seen_usage) and getattr(chunk, "usage", None):
                        self._accumulate_usage(chunk.usage)
                        seen_usage = True
                    yield chunk
            return _gen()
        self._accumulate_usage(getattr(res, "usage", None))
        return res

    def __getattr__(self, name: str) -> Any:
        return getattr(self._base_model, name)


def get_model_usage(model: Any) -> tuple[int, int]:
    input_tokens = getattr(model, "total_input_tokens", None)
    output_tokens = getattr(model, "total_output_tokens", None)
    if input_tokens is None or output_tokens is None:
        return 0, 0
    return int(input_tokens), int(output_tokens)


def _is_llama_model(model_name: str) -> bool:
    """Check if the model name indicates a Llama model."""
    name_lower = model_name.lower()
    return any(k in name_lower for k in ["llama", "meta-llama"])


def _is_deepseek_model(model_name: str | None = None, base_url: str | None = None) -> bool:
    """Check if the model/backend should use DeepSeek message formatting."""
    haystack = " ".join(part.lower() for part in [model_name or "", base_url or ""])
    return "deepseek" in haystack


def make_openai_model(cfg: OpenAIConfig) -> ChatModelBase:
    client_args: dict[str, Any] = {}
    if cfg.base_url:
        client_args["base_url"] = cfg.base_url

    base_model = OpenAIChatModel(
        model_name=cfg.model,
        api_key=cfg.api_key,
        stream=cfg.stream,
        reasoning_effort=cfg.reasoning_effort,  # type: ignore[arg-type]
        organization=cfg.organization,
        client_args=client_args or None,
        generate_kwargs=cfg.generate_kwargs or None,
    )
    return UsageTrackingModel(base_model)


def make_formatter(
    model_name: str | None = None,
    base_url: str | None = None,
) -> OpenAIChatFormatter | DeepSeekReasoningChatFormatter | Llama4ChatFormatter:
    """Create a message formatter appropriate for the model.
    
    Args:
        model_name: The model name to determine formatter type.
        base_url: Optional backend URL used to detect OpenAI-compatible
                  providers such as DeepSeek.
    
    Returns:
        A formatter compatible with the specified model.
    """
    if _is_deepseek_model(model_name, base_url):
        return DeepSeekReasoningChatFormatter()
    if model_name and _is_llama_model(model_name):
        return Llama4ChatFormatter()
    return OpenAIChatFormatter()
