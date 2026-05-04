from __future__ import annotations

import re
from collections import defaultdict
from typing import Iterable, List


_NON_WORD_RE = re.compile(r"[^A-Za-z0-9_]+")

_EXACT_CANONICAL_MAP = {
    "LOAD": "INIT_ROUND",
    "ROUND_PROC": "ROUND_OP",
}

_LOWER_CANONICAL_MAP = {
    "data_in": "text_in",
    "plaintext_in": "text_in",
    "text": "text_in",
    "text_in": "text_in",
    "key_in": "key",
    "secret_key": "key",
    "cipher_key": "key",
    "key": "key",
    "start": "ld",
    "load": "ld",
    "ld": "ld",
    "round_proc": "ROUND_OP",
    "roundop": "ROUND_OP",
    "init_round": "INIT_ROUND",
}


def _normalize_surface_form(entity: str) -> str:
    value = str(entity or "").strip()
    if not value:
        return ""
    value = _NON_WORD_RE.sub("_", value).strip("_")
    return value


def canonicalize_entity(entity: str) -> str:
    surface = _normalize_surface_form(entity)
    if not surface:
        return ""
    if surface in _EXACT_CANONICAL_MAP:
        return _EXACT_CANONICAL_MAP[surface]
    lower = surface.lower()
    if lower in _LOWER_CANONICAL_MAP:
        return _LOWER_CANONICAL_MAP[lower]
    if surface.isupper() and len(surface) > 1:
        return surface
    return lower


def canonicalize_entities(entities: Iterable[str]) -> List[str]:
    canonical: List[str] = []
    seen = set()
    for entity in entities:
        value = canonicalize_entity(entity)
        if not value or value in seen:
            continue
        seen.add(value)
        canonical.append(value)
    return canonical


def build_entity_alias_groups(groups: Iterable[Iterable[str]]) -> List[dict]:
    canonical_to_aliases: dict[str, set[str]] = defaultdict(set)
    for entity_group in groups:
        for entity in entity_group:
            surface = _normalize_surface_form(entity)
            canonical = canonicalize_entity(surface)
            if not canonical:
                continue
            if surface:
                canonical_to_aliases[canonical].add(surface)
            canonical_to_aliases[canonical].add(canonical)
    result: List[dict] = []
    for canonical_name in sorted(canonical_to_aliases):
        aliases = sorted(canonical_to_aliases[canonical_name], key=lambda item: (item != canonical_name, item))
        result.append(
            {
                "canonical_name": canonical_name,
                "aliases": aliases,
            }
        )
    return result
