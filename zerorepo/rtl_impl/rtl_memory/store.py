from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .schemas import RTLMemoryHeader, RTLMemoryRecord, normalize_memory_path


TYPE_DIR = {
    "repair_outcome": "cases",
    "negative_direction": "patterns",
    "planning_correction": "corrections",
    "merge_rule": "rules",
}

TYPE_TITLE = {
    "repair_outcome": "Debug Repair Outcomes",
    "negative_direction": "Negative Directions",
    "planning_correction": "Planning Corrections",
    "merge_rule": "Stage6 Merge Rules",
}


def _slug(text: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.$-]+", "_", str(text).strip())
    value = re.sub(r"_+", "_", value).strip("_")
    return value[:120] or "memory"


def _yaml_scalar(value: Any) -> str:
    if value is None:
        return '""'
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if re.fullmatch(r"[A-Za-z0-9_./$:+-]+", text):
        return text
    return json.dumps(text, ensure_ascii=False)


def _render_frontmatter(header: RTLMemoryHeader) -> str:
    data = header.model_dump(exclude={"path"})
    lines = ["---"]
    for key, value in data.items():
        if isinstance(value, list):
            if not value:
                lines.append(f"{key}: []")
            else:
                lines.append(f"{key}:")
                for item in value:
                    lines.append(f"  - {_yaml_scalar(item)}")
        else:
            lines.append(f"{key}: {_yaml_scalar(value)}")
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def _parse_scalar(text: str) -> Any:
    value = text.strip()
    if value == "[]":
        return []
    if value in {"true", "false"}:
        return value == "true"
    if not value:
        return ""
    try:
        return json.loads(value)
    except Exception:  # noqa: BLE001
        pass
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end < 0:
        return {}, text
    raw = text[4:end].strip("\n")
    body = text[end + len("\n---") :].lstrip("\n")
    data: dict[str, Any] = {}
    current_key: str | None = None
    for line in raw.splitlines():
        if not line.strip():
            continue
        if line.startswith("  - ") and current_key:
            if not isinstance(data.get(current_key), list):
                data[current_key] = []
            data[current_key].append(_parse_scalar(line[4:]))
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        current_key = key.strip()
        parsed = _parse_scalar(value)
        data[current_key] = parsed
    return data, body


class RTLMemoryStore:
    """File-backed causal RTL memory store.

    MEMORY.md is the human/agent-facing index. Individual memory markdown files
    are the source of truth for metadata and full content.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()

    @classmethod
    def from_workspace(cls, workspace_root: str | Path) -> "RTLMemoryStore":
        return cls(Path(workspace_root) / "rtl_memory")

    def ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        for dirname in sorted(set(TYPE_DIR.values())):
            (self.root / dirname).mkdir(parents=True, exist_ok=True)
        if not self.index_path.exists():
            self.index_path.write_text("# RTL Agent Memory Index\n", encoding="utf-8")

    @property
    def index_path(self) -> Path:
        return self.root / "MEMORY.md"

    def read_index(self) -> str:
        if not self.index_path.exists():
            return ""
        return self.index_path.read_text(encoding="utf-8", errors="replace")

    def scan_headers(self, *, memory_type: str | None = None, stage: str | None = None) -> list[RTLMemoryHeader]:
        if not self.root.exists():
            return []
        headers: list[RTLMemoryHeader] = []
        for path in sorted(self.root.glob("*/*.md")):
            if not path.is_file():
                continue
            try:
                data, body = _parse_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
                data["path"] = normalize_memory_path(path.relative_to(self.root))
                if not data.get("description"):
                    data["description"] = self._description_from_body(body)
                header = RTLMemoryHeader.model_validate(data)
            except Exception:  # noqa: BLE001
                continue
            if memory_type and header.type != memory_type:
                continue
            if stage and header.stage != stage:
                continue
            headers.append(header)
        return headers

    def read_memory(self, path: str | Path) -> RTLMemoryRecord | None:
        rel = Path(str(path))
        if rel.is_absolute():
            try:
                rel = rel.resolve().relative_to(self.root.resolve())
            except ValueError:
                return None
        target = (self.root / rel).resolve()
        try:
            target.relative_to(self.root.resolve())
        except ValueError:
            return None
        if not target.is_file():
            return None
        text = target.read_text(encoding="utf-8", errors="replace")
        data, body = _parse_frontmatter(text)
        data["path"] = normalize_memory_path(target.relative_to(self.root))
        if not data.get("description"):
            data["description"] = self._description_from_body(body)
        try:
            header = RTLMemoryHeader.model_validate(data)
        except Exception:  # noqa: BLE001
            return None
        return RTLMemoryRecord(header=header, body=body)

    def upsert_memory(self, header: RTLMemoryHeader, body: str) -> Path:
        self.ensure()
        dirname = TYPE_DIR.get(header.type, "cases")
        rel_path = Path(dirname) / f"{_slug(header.memory_id)}.md"
        header = header.model_copy(update={"path": normalize_memory_path(rel_path)})
        path = self.root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        # Legacy callers keep their latest Markdown view; preserve each content
        # version separately without inventing an approved/reused memory event.
        from .ledger import atomic, digest
        previous = path.read_text() if path.exists() else None
        rendered = _render_frontmatter(header) + body.rstrip() + "\n"
        for content in [previous, rendered]:
            if content is not None:
                snapshot = {'memory_id': header.memory_id, 'content': content}
                revision = self.root/'legacy_revisions'/(digest(snapshot)+'.json')
                if not revision.exists(): atomic(revision, snapshot)
        path.write_text(rendered, encoding="utf-8")
        self.rebuild_index()
        return path

    def rebuild_index(self) -> None:
        self.ensure()
        headers = self.scan_headers()
        lines = ["# RTL Agent Memory Index", ""]
        for memory_type, title in TYPE_TITLE.items():
            group = [h for h in headers if h.type == memory_type]
            if not group:
                continue
            lines.append(f"## {title}")
            lines.append("")
            for header in sorted(group, key=lambda item: (item.module_family, item.module, item.memory_id)):
                desc = header.description or f"{header.type} for {header.module or header.module_family}".strip()
                lines.append(f"- [{header.memory_id}]({header.path})")
                lines.append(f"  - {desc}")
            lines.append("")
        self.index_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    def _description_from_body(self, body: str) -> str:
        for line in body.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            return stripped[:180]
        return ""


__all__ = ["RTLMemoryStore"]
