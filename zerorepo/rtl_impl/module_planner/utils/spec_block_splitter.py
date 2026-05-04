from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, List, Tuple

from ..schemas import SpecBlock


_MARKDOWN_SUBHEADING_RE = re.compile(r"^\s*#{2,3}\s+\S.*$")
_BOLD_NUMBERED_HEADING_RE = re.compile(r"^\s*\*\*\s*\d+(?:\.\d+)*\.?\s*\S.*\*\*\s*$")
_TOP_HEADING_RE = re.compile(r"^\s*#\s+(.+?)\s*$")


def resolve_module_spec_text(module_name: str, spec_md_files: Iterable[str]) -> Tuple[str, str]:
    paths = [Path(item).resolve() for item in spec_md_files if str(item).strip()]

    for path in paths:
        if path.stem == module_name and path.exists():
            return str(path), _read_markdown(path)

    checked_dirs: List[Path] = []
    for path in paths:
        parent = path.parent
        if parent in checked_dirs:
            continue
        checked_dirs.append(parent)
        candidate = parent / f"{module_name}.md"
        if candidate.exists():
            return str(candidate.resolve()), _read_markdown(candidate)

    for path in paths:
        if not path.exists():
            continue
        markdown = _read_markdown(path)
        module_text = extract_module_section(markdown, module_name)
        if module_text:
            return str(path), module_text

    raise FileNotFoundError(f"Could not find spec text for module `{module_name}`")


def extract_module_section(markdown_text: str, module_name: str) -> str:
    lines = markdown_text.replace("\r\n", "\n").splitlines()
    top_headings: List[tuple[int, str]] = []
    for index, line in enumerate(lines):
        match = _TOP_HEADING_RE.match(line)
        if match:
            top_headings.append((index, _normalize_heading_text(match.group(1))))

    for item_index, (start, heading) in enumerate(top_headings):
        if not _heading_matches_module(heading, module_name):
            continue
        end = top_headings[item_index + 1][0] if item_index + 1 < len(top_headings) else len(lines)
        return "\n".join(lines[start:end]).strip()
    return ""


def split_spec_blocks(markdown_text: str) -> List[SpecBlock]:
    text = markdown_text.replace("\r\n", "\n").strip()
    if not text:
        return []

    lines = text.splitlines()
    heading_indexes = [index for index, line in enumerate(lines) if _is_split_heading(line)]
    if not heading_indexes:
        return [SpecBlock(block_id="S001", text=text)]

    block_texts: List[str] = []
    for block_index, start in enumerate(heading_indexes):
        if block_index == 0:
            start = 0
        end = heading_indexes[block_index + 1] if block_index + 1 < len(heading_indexes) else len(lines)
        block_text = "\n".join(lines[start:end]).strip()
        if block_text:
            block_texts.append(block_text)
    block_texts = _merge_heading_only_blocks(block_texts)
    return [
        SpecBlock(block_id=f"S{index:03d}", text=block_text)
        for index, block_text in enumerate(block_texts, start=1)
    ]


def _read_markdown(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n").strip()


def _is_split_heading(line: str) -> bool:
    return bool(_MARKDOWN_SUBHEADING_RE.match(line) or _BOLD_NUMBERED_HEADING_RE.match(line))


def _merge_heading_only_blocks(block_texts: List[str]) -> List[str]:
    merged: List[str] = []
    pending_headings: List[str] = []
    for block_text in block_texts:
        if _is_heading_only_block(block_text):
            pending_headings.append(block_text)
            continue
        if pending_headings:
            block_text = "\n\n".join([*pending_headings, block_text])
            pending_headings = []
        merged.append(block_text)
    return merged


def _is_heading_only_block(block_text: str) -> bool:
    nonempty_lines = [line.strip() for line in block_text.splitlines() if line.strip()]
    return len(nonempty_lines) == 1 and _is_split_heading(nonempty_lines[0])


def _normalize_heading_text(text: str) -> str:
    return text.strip().strip("*").strip()


def _heading_matches_module(heading: str, module_name: str) -> bool:
    normalized = heading.lower()
    target = module_name.lower()
    if normalized == target:
        return True
    return bool(re.match(rf"^{re.escape(target)}(?:\s|:|-)", normalized))
