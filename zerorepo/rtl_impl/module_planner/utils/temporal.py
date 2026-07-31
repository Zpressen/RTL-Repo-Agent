from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel


def canonical_fingerprint(value: Any) -> str:
    payload = json.dumps(
        _normalize(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _normalize(value: Any) -> Any:
    if isinstance(value, BaseModel):
        try:
            value = value.model_dump()
        except AttributeError:
            value = value.dict()
    if isinstance(value, dict):
        return {str(key): _normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    if isinstance(value, set):
        return sorted(_normalize(item) for item in value)
    return value
