from __future__ import annotations

import json
from typing import Any

from .config import OpenAIConfig, load_openai_config


def debug_openai_config_from_planner_config(llm_config: Any) -> OpenAIConfig:
    if llm_config is None:
        return load_openai_config()
    try:
        from zerorepo.rpg_gen.base.llm_client import LLMConfig

        cfg = LLMConfig.from_source(llm_config)
        extra = dict(getattr(cfg, "extra", {}) or {})
        generate_kwargs: dict[str, Any] = {}
        if getattr(cfg, "temperature", None) is not None:
            generate_kwargs["temperature"] = cfg.temperature
        if getattr(cfg, "top_p", None) is not None:
            generate_kwargs["top_p"] = cfg.top_p
        if getattr(cfg, "max_tokens", None) is not None:
            generate_kwargs["max_completion_tokens"] = cfg.max_tokens
        if extra:
            generate_kwargs["extra_body"] = extra
        return OpenAIConfig(
            model=cfg.model,
            api_key=cfg.api_key,
            base_url=cfg.base_url or cfg.endpoint_url,
            reasoning_effort=extra.get("reasoning_effort"),
            stream=bool(getattr(cfg, "stream", False)),
            generate_kwargs=generate_kwargs,
        )
    except Exception:  # noqa: BLE001
        return load_openai_config()


def build_module_spec_text(*, module_name: str, spec_blocks: Any) -> str:
    modules = _get(spec_blocks, "modules", []) or []
    for module in modules:
        if _get(module, "module", "") != module_name:
            continue
        blocks = _get(module, "blocks", []) or []
        return "\n\n".join(
            f"[{_get(block, 'block_id', '')}]\n{_get(block, 'text', '')}".strip()
            for block in blocks
            if _get(block, "text", "")
        ).strip()
    return ""


def build_debug_contract_json(
    *,
    module_name: str,
    stage1_contracts: Any,
    spec_text: str,
) -> str:
    interface = _find_by_module(_get(stage1_contracts, "interface_contracts", []) or [], module_name)
    timing = _find_by_module(_get(stage1_contracts, "timing_contracts", []) or [], module_name)
    control = _find_by_module(_get(stage1_contracts, "control_contracts", []) or [], module_name)
    datapath = _find_by_module(_get(stage1_contracts, "datapath_contracts", []) or [], module_name)
    planning = _find_by_module(_get(stage1_contracts, "planning_facts", []) or [], module_name)

    ports = []
    for port in _get(interface, "ports", []) or []:
        ports.append(
            {
                "name": _get(port, "name", ""),
                "direction": _get(port, "direction", ""),
                "width": _get(port, "width", ""),
                "role": _get(port, "role", ""),
                "active": _get(port, "active", ""),
                "meaning": _get(port, "meaning", ""),
            }
        )

    payload = {
        "module_name": module_name,
        "io": ports,
        "clocking": {
            "clock": _get(interface, "clock", ""),
            "reset": _get(interface, "reset", ""),
            "reset_polarity": _get(interface, "reset_polarity", ""),
            "timing_contract": _to_plain(timing),
        },
        "timing": _to_plain(timing),
        "control": _to_plain(control),
        "datapath": _to_plain(datapath),
        "planning_facts": _to_plain(planning),
        "functional_summary": _summarize_spec(spec_text),
    }
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def _find_by_module(items: Any, module_name: str) -> Any | None:
    for item in items:
        if _get(item, "module", "") == module_name:
            return item
    return None


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _to_plain(obj: Any) -> Any:
    if obj is None:
        return None
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    return obj


def _summarize_spec(spec_text: str) -> list[str]:
    lines = [line.strip() for line in spec_text.splitlines() if line.strip()]
    return lines[:20]
