"""Lossless source ranges and bounded, reproducible retrieval inputs."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import tempfile


POLICY_VERSION = "module_spec_selection_v3_harness"


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def strict_payload(raw):
    if hasattr(raw, "model_dump"):
        return raw.model_dump(mode="json")
    if isinstance(raw, dict):
        return json.loads(json.dumps(raw))
    text = str(raw).strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) < 3 or lines[-1].strip() != "```":
            raise ValueError("Unclosed JSON fence")
        text = "\n".join(lines[1:-1])
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    def constant(value):
        raise ValueError(f"Invalid JSON constant: {value}")
    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


def source_ranges(text, limit=6000):
    """Partition every source character; headings in fences are never separators."""
    if not text:
        return []
    sections = []
    headings = []
    offset = 0
    start = 0
    parent = []
    fence = None
    for line in text.splitlines(keepends=True):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line.rstrip("\r\n"))
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= fence[1] and not marker[2].strip():
                fence = None
        elif marker:
            fence = (marker[1][0], len(marker[1]))
        else:
            heading = re.match(r"^ {0,3}(#{1,6})\s+(.+)", line)
            bold = re.match(r"^\s*\*\*\s*\d+(?:\.\d+)*\.?\s+\S.*\*\*\s*$", line)
            if heading or bold:
                if offset > start:
                    sections.append((start, offset, parent[:]))
                level = len(heading[1]) if heading else 4
                parent = [item for item in headings if item[0] < level]
                parent.append((level, heading[2].strip() if heading else line.strip()))
                headings = parent[:]
                start = offset
        offset += len(line)
    sections.append((start, len(text), parent[:]))
    result = []
    for first, last, path in sections:
        cursor = first
        while cursor < last:
            end = min(cursor + limit, last)
            if end < last:
                paragraph = text.rfind("\n\n", cursor + limit // 2, end)
                boundary = paragraph + 2 if paragraph >= 0 else text.rfind("\n", cursor + limit // 2, end) + 1
                if boundary > cursor:
                    end = boundary
            result.append({"start": cursor, "end": end, "heading_path": [title for _, title in path]})
            cursor = end
    return result
