from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable


_TEXT_ENTITY_PATTERNS = (
    re.compile(r"(?:submodule|module|primitive|block)\s+`?([A-Za-z_][A-Za-z0-9_$]*)`?", re.IGNORECASE),
    re.compile(r"`([A-Za-z_][A-Za-z0-9_$]*)`"),
)
_IDENTIFIER_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_$]*")


def extract_explicit_submodule_names(
    *,
    spec_md_files: Iterable[str],
    stage1_artifact: Any,
) -> set[str]:
    if stage1_artifact is None:
        return set()

    spec_md_paths = {str(Path(path).resolve()) for path in spec_md_files}
    explicit = set()
    for atom in getattr(stage1_artifact, "atoms", []):
        if getattr(atom.atom_type, "value", atom.atom_type) != "submodule_hint":
            continue
        if (atom.source_section or "").startswith("Image:"):
            continue

        source_path = str(Path(atom.source_file).resolve()) if atom.source_file else ""
        source_suffix = Path(atom.source_file or "").suffix.lower()
        if spec_md_paths:
            if source_path not in spec_md_paths and source_suffix not in {".md", ".markdown"}:
                continue
        elif source_suffix not in {".md", ".markdown"}:
            continue

        explicit.update(_extract_atom_module_names(atom))
    return explicit


def _extract_atom_module_names(atom: Any) -> set[str]:
    candidates = set()
    text = atom.text or ""
    source_section = atom.source_section or ""
    related_entities = set(atom.related_entities or [])

    for pattern in _TEXT_ENTITY_PATTERNS:
        candidates.update(pattern.findall(text))

    section_tokens = _IDENTIFIER_PATTERN.findall(source_section)
    if section_tokens:
        candidates.add(section_tokens[-1])

    if related_entities:
        candidates = {candidate for candidate in candidates if candidate in related_entities}

    return {candidate for candidate in candidates if candidate}
