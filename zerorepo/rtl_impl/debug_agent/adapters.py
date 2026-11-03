from __future__ import annotations

import json
from typing import Any

from .config import OpenAIConfig, load_openai_config


def _config_get(obj: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        value = default
        found = False
        if isinstance(obj, dict) and name in obj:
            value = obj[name]
            found = True
        if hasattr(obj, name):
            value = getattr(obj, name)
            found = True
        if found and value is not None:
            return value
    return default


def debug_openai_config_from_planner_config(llm_config: Any) -> OpenAIConfig:
    if llm_config is None:
        return load_openai_config()
    cfg = llm_config
    try:
        from zerorepo.rpg_gen.base.llm_client import LLMConfig

        cfg = LLMConfig.from_source(llm_config)
    except Exception:  # noqa: BLE001
        cfg = llm_config

    try:
        extra = dict(getattr(cfg, "extra", {}) or {})
        generate_kwargs: dict[str, Any] = {}
        temperature = _config_get(cfg, "temperature")
        top_p = _config_get(cfg, "top_p")
        max_tokens = _config_get(cfg, "max_tokens", "max_completion_tokens")
        if temperature is not None:
            generate_kwargs["temperature"] = temperature
        if top_p is not None:
            generate_kwargs["top_p"] = top_p
        if max_tokens is not None:
            token_parameter = "max_tokens" if _config_get(cfg, "provider") == "deepseek" else "max_completion_tokens"
            generate_kwargs[token_parameter] = max_tokens
        if extra:
            # Planner extras may already contain an SDK extra_body. Flatten it
            # once; nesting extra_body would silently lose DeepSeek's options.
            body = dict(extra.get("extra_body") or {})
            body.update({key: value for key, value in extra.items() if key not in {"extra_body", "reasoning_effort"}})
            if body:
                generate_kwargs["extra_body"] = body
        return OpenAIConfig(
            model=_config_get(cfg, "model", default=OpenAIConfig.model),
            api_key=_config_get(cfg, "api_key"),
            base_url=_config_get(cfg, "base_url", "endpoint_url"),
            reasoning_effort=extra.get("reasoning_effort"),
            stream=bool(_config_get(cfg, "stream", default=False)),
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
        direction = _get(port, "direction", "") or _get(port, "dir", "")
        ports.append(
            {
                "name": _get(port, "name", ""),
                "dir": direction,
                "direction": direction,
                "width": _get(port, "width", ""),
                "role": _get(port, "role", ""),
                "active": _get(port, "active", ""),
                "meaning": _get(port, "meaning", ""),
            }
        )

    raw_timing = _to_plain(timing)
    normalized_clocking = _normalize_clocking(interface=interface, timing=timing)
    normalized_timing = _normalize_output_timing(
        ports=ports,
        timing=raw_timing,
        is_sequential=bool(normalized_clocking["is_sequential"]),
    )

    payload = {
        "module_name": module_name,
        "io": ports,
        "clocking": {**normalized_clocking, "timing_contract": raw_timing},
        "timing": normalized_timing,
        "raw_timing_contract": raw_timing,
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


def _normalize_clocking(*, interface: Any, timing: Any) -> dict[str, Any]:
    raw_clocking = _get(timing, "clocking", {}) or {}
    clock_name = _get(raw_clocking, "clock", "") or _get(interface, "clock", "") or None
    registered_objects = _get(timing, "registered_objects", []) or []
    has_clock = isinstance(clock_name, str) and clock_name.strip().lower() not in {"", "none"}
    is_sequential = bool(has_clock and registered_objects)

    reset_behavior = _get(timing, "reset_behavior", {}) or {}
    reset_name = _get(reset_behavior, "signal", "") or _get(interface, "reset", "") or None
    reset_active = _normalize_active(_get(reset_behavior, "active", ""))
    if reset_active is None:
        reset_active = _normalize_active(_get(interface, "reset_polarity", ""))

    reset_type = _get(reset_behavior, "type", "") or _get(reset_behavior, "reset_type", "")
    reset_type_norm = str(reset_type).strip().lower() if reset_type is not None else ""
    if reset_type_norm not in {"synchronous", "asynchronous"}:
        reset_type_norm = None

    return {
        "is_sequential": is_sequential,
        "clock": {
            "name": clock_name,
            "edge": _normalize_edge(_get(raw_clocking, "update_edge", "")),
        },
        "reset": {
            "name": reset_name,
            "active": reset_active,
            "type": reset_type_norm,
        },
    }


def _normalize_output_timing(
    *, ports: list[dict[str, Any]], timing: Any, is_sequential: bool
) -> dict[str, dict[str, Any]]:
    raw_timing = timing if isinstance(timing, dict) else {}
    registered = raw_timing.get("registered_objects") or []
    registered_by_name = {
        str(item.get("name")).strip(): item
        for item in registered
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    }
    clock_value = str((raw_timing.get("clocking") or {}).get("clock", "")).strip().lower()
    explicitly_combinational = not is_sequential and clock_value == "none"

    out: dict[str, dict[str, Any]] = {}
    for port in ports:
        if port.get("dir") != "output":
            continue
        name = str(port.get("name") or "").strip()
        if not name:
            continue
        latency = None
        direct = raw_timing.get(name)
        registered_item = registered_by_name.get(name)
        if isinstance(direct, dict) and "latency_cycles" in direct:
            latency = direct.get("latency_cycles")
        elif isinstance(registered_item, dict) and "latency_cycles" in registered_item:
            latency = registered_item.get("latency_cycles")
        elif explicitly_combinational:
            latency = 0
        out[name] = {"latency_cycles": latency}
    return out


def _normalize_edge(value: Any) -> str | None:
    text = str(value or "").lower()
    if "rising" in text or "posedge" in text:
        return "posedge"
    if "falling" in text or "negedge" in text:
        return "negedge"
    return None


def _normalize_active(value: Any) -> str | None:
    text = str(value or "").strip().lower().replace("_", "-")
    if text in {"high", "active-high", "active high"}:
        return "high"
    if text in {"low", "active-low", "active low"}:
        return "low"
    return None


def _summarize_spec(spec_text: str) -> list[str]:
    lines = [line.strip() for line in spec_text.splitlines() if line.strip()]
    return lines[:20]
