from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentscope.memory import InMemoryMemory
from agentscope.message import Msg
from pydantic import BaseModel

from .agents import SafeReActAgent, clear_memory_safely
from .config import OpenAIConfig
from .model import make_formatter, make_openai_model
from .utils import extract_json_object


SYSTEM_PROMPT = r"""
You are Architect, a senior hardware design lead for SystemVerilog RTL.

Goal: turn an ambiguous natural-language spec into a precise, testable debug contract
that downstream Debugger can treat as the source of truth
for this repair session.

Principles:
- Be concrete about timing, reset behavior, and edge semantics when possible.
- Prefer facts from the spec. If the spec is ambiguous, use the golden testbench only to
  align interface and externally observable timing expectations.
- Never invent ports or widen/narrow the interface unless the spec or golden testbench requires it.
- Keep the contract compact and machine-usable.
"""

CONTRACT_PROMPT = r"""
Create a debug contract for the DUT described in <input_spec>.

Requirements:
1) Output MUST be a single valid JSON object with no extra text.
2) Write everything in English.
3) If <golden_testbench> is provided, use it only to infer interface/timing expectations.
4) Do not assume access to any reference RTL implementation.

Required JSON fields:
- source_of_truth: "spec" or "golden_tb"
- module_name
- io
- clocking
- timing
- functional_summary
- corner_cases
- test_plan
- guidance

Port entries in io must include:
- name
- dir
- width
- notes (optional)

<input_spec>
{input_spec}
</input_spec>

{golden_tb_block}
"""

REVISE_CONTRACT_PROMPT = r"""
Revise the contract below to fix the reported lint errors.

Rules:
1) Output MUST be a single valid JSON object with no extra text.
2) Keep module_name and io aligned with the spec and golden testbench when provided.
3) Do not invent ports or unsupported timing assumptions.

Lint errors:
{lint_errors}

<input_spec>
{input_spec}
</input_spec>

<contract_json>
{contract_json}
</contract_json>

{golden_tb_block}
"""


class ArchitectContract(BaseModel):
    source_of_truth: str = "spec"
    module_name: str = "TopModule"
    io: list[dict[str, Any]] = []
    clocking: dict[str, Any] = {}
    timing: dict[str, Any] = {}
    functional_summary: list[str] = []
    corner_cases: list[str] = []
    test_plan: list[str] = []
    guidance: dict[str, Any] = {}


def normalize_contract_dict(contract: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(contract)
    io = normalized.get("io")
    if isinstance(io, list):
        fixed_ports: list[dict[str, Any]] = []
        for port in io:
            if not isinstance(port, dict):
                fixed_ports.append(port)
                continue
            fixed = dict(port)
            direction = fixed.get("dir", fixed.get("direction"))
            if isinstance(direction, str) and direction:
                fixed["dir"] = direction
                fixed["direction"] = direction
            fixed_ports.append(fixed)
        normalized["io"] = fixed_ports
    return normalized


class ArchitectAgent:
    def __init__(self, cfg: OpenAIConfig) -> None:
        self._agent = SafeReActAgent(
            name="Architect",
            sys_prompt=SYSTEM_PROMPT,
            model=make_openai_model(cfg),
            formatter=make_formatter(cfg.model, cfg.base_url),
            memory=InMemoryMemory(),
            max_iters=10,
        )
        self.last_prompt: str = ""
        self.last_raw_output: str = ""

    def reset(self) -> None:
        clear_memory_safely(self._agent)

    def _read_golden_tb_excerpt(self, golden_tb_path: str, *, max_chars: int = 6000) -> str:
        try:
            text = Path(golden_tb_path).read_text(encoding="utf-8").strip()
        except Exception:  # noqa: BLE001
            return ""
        if not text:
            return ""
        if len(text) > max_chars:
            text = text[:max_chars] + "\n/* ... truncated ... */\n"
        if not text.endswith("\n"):
            text += "\n"
        return text

    async def _call(self, prompt: str) -> str:
        msg = await self._agent(Msg("user", prompt, role="user"))
        return msg.get_text_content() or ""

    def _golden_tb_block(self, golden_tb_path: str | None) -> str:
        if not golden_tb_path:
            return ""
        excerpt = self._read_golden_tb_excerpt(golden_tb_path)
        if not excerpt:
            return ""
        return f"<golden_testbench>\n{excerpt}</golden_testbench>\n"

    def parse_output(self, response_text: str) -> ArchitectContract:
        try:
            payload = extract_json_object(response_text)
            return ArchitectContract.model_validate(normalize_contract_dict(payload))
        except Exception as exc:  # noqa: BLE001
            return ArchitectContract(
                functional_summary=[f"Contract parse error: {type(exc).__name__}: {exc}"],
                guidance={"verifier": [], "coder": [], "debugger": []},
            )

    async def chat(self, input_spec: str, *, golden_tb_path: str | None = None) -> ArchitectContract:
        self.reset()
        prompt = CONTRACT_PROMPT.format(
            input_spec=input_spec,
            golden_tb_block=self._golden_tb_block(golden_tb_path),
        )
        self.last_prompt = prompt
        response_text = await self._call(prompt)
        self.last_raw_output = response_text
        return self.parse_output(response_text)

    async def revise_contract(
        self,
        *,
        input_spec: str,
        contract_json: str,
        lint_errors: str,
        golden_tb_path: str | None = None,
    ) -> ArchitectContract:
        self.reset()
        prompt = REVISE_CONTRACT_PROMPT.format(
            input_spec=input_spec,
            contract_json=contract_json,
            lint_errors=lint_errors.strip(),
            golden_tb_block=self._golden_tb_block(golden_tb_path),
        )
        self.last_prompt = prompt
        response_text = await self._call(prompt)
        self.last_raw_output = response_text
        return self.parse_output(response_text)


def contract_to_json_text(contract: ArchitectContract | dict[str, Any] | str) -> str:
    if isinstance(contract, str):
        try:
            obj = json.loads(contract)
        except Exception:  # noqa: BLE001
            return contract.rstrip() + "\n"
        return json.dumps(normalize_contract_dict(obj), indent=2) + "\n"
    if isinstance(contract, BaseModel):
        obj = contract.model_dump()
    else:
        obj = dict(contract)
    return json.dumps(normalize_contract_dict(obj), indent=2) + "\n"
