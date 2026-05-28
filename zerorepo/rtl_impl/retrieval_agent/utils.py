from __future__ import annotations

import json
import re
from typing import Any, List


def blocks(module_spec: Any) -> List[Any]:
    raw_blocks = getattr(module_spec, "blocks", None)
    if raw_blocks is None and isinstance(module_spec, dict):
        raw_blocks = module_spec.get("blocks")
    return list(raw_blocks or [])


def block_id(block: Any) -> str:
    if isinstance(block, dict):
        return str(block.get("block_id", ""))
    return str(getattr(block, "block_id", ""))


def block_text(block: Any) -> str:
    if isinstance(block, dict):
        return str(block.get("text", ""))
    return str(getattr(block, "text", ""))


def first_nonempty_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip().strip("*").strip()
        if stripped:
            return stripped
    return ""


def is_interface_like_spec_block(text: str) -> bool:
    normalized = text.lower()
    if "interface" not in normalized:
        return False
    has_table_headers = "direction" in normalized and "width" in normalized and (
        "signal" in normalized or "port" in normalized
    )
    has_port_rows = bool(re.search(r"\|\s*[a-zA-Z_][\w]*\s*\|\s*(?:input|output|inout)\b", normalized))
    return has_table_headers or has_port_rows


def is_primary_interface_spec_block(text: str) -> bool:
    if not is_interface_like_spec_block(text):
        return False
    heading = first_nonempty_line(text).lower()
    if "interface" not in heading:
        return False
    prefix = heading.split("interface", 1)[0]
    return not re.search(r"\d+\.\d+", prefix)


def interface_block_refs(module_spec: Any) -> List[str]:
    primary_matches = [
        block_id(item)
        for item in blocks(module_spec)
        if is_primary_interface_spec_block(block_text(item))
    ]
    if primary_matches:
        return primary_matches
    fallback_matches = [
        block_id(item)
        for item in blocks(module_spec)
        if is_interface_like_spec_block(block_text(item))
    ]
    return fallback_matches[:1]


def repair_json_payload(raw: Any) -> Any:
    if isinstance(raw, dict):
        return raw
    text = raw if isinstance(raw, str) else str(raw)
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9_+-]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))
