from __future__ import annotations

import json
import re
from typing import Any, Optional


def strip_code_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z0-9_+-]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)
    return cleaned.strip()


def auto_close_json(text: str) -> Optional[str]:
    if not isinstance(text, str):
        return None
    text = strip_code_fences(text)
    positions = [pos for pos in (text.find("{"), text.find("[")) if pos >= 0]
    if not positions:
        return None
    payload = text[min(positions):]
    out = []
    stack = []
    in_str = False
    escape = False
    for ch in payload:
        out.append(ch)
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            stack.append("}")
        elif ch == "[":
            stack.append("]")
        elif ch in ("}", "]") and stack and stack[-1] == ch:
            stack.pop()
    if in_str:
        out.append('"')
    while stack:
        out.append(stack.pop())
    return "".join(out)


def extract_balanced_json(text: str) -> Optional[str]:
    text = strip_code_fences(text)
    start = None
    depth = 0
    in_str = False
    escape = False
    for idx, ch in enumerate(text):
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            continue
        if ch in "{[":
            if depth == 0:
                start = idx
            depth += 1
        elif ch in "}]":
            depth -= 1
            if depth == 0 and start is not None:
                return text[start:idx + 1]
    return None


def repair_json_payload(raw: Any) -> Any:
    if isinstance(raw, (dict, list)):
        return raw
    if raw is None:
        raise ValueError("Empty JSON payload.")
    text = str(raw).strip()
    candidates = [strip_code_fences(text), extract_balanced_json(text), auto_close_json(text)]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            return json.loads(candidate)
        except Exception:
            continue
    raise ValueError("Unable to repair JSON payload.")
