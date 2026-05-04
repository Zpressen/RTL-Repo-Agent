from __future__ import annotations

import re
import urllib.parse
from pathlib import Path
from typing import Iterable, List


HEADER_RE = re.compile(r"^(#{1,6})\s+(.*)$")
IMAGE_REF_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
FIGURE_REF_RE = re.compile(r"(?:^|\b)(?:fig(?:ure)?\.?\s*|)(\d+(?:\.\d+)*)\b", re.IGNORECASE)


def load_image(path: str) -> bytes:
    return Path(path).read_bytes()


def infer_image_type_hint(path: str) -> str:
    name = Path(path).name.lower()
    if "fsm" in name or "state" in name:
        return "fsm"
    if "interface" in name:
        return "interface"
    if "block" in name or "arch" in name or "mod" in name:
        return "block_diagram"
    if "datapath" in name or "dataflow" in name:
        return "datapath"
    if "timing" in name or "wave" in name:
        return "timing"
    return "generic"


def build_image_manifest(paths: List[str], documents: Iterable[dict] | None = None) -> List[dict]:
    image_refs = _collect_image_references(documents or [])
    manifest: List[dict] = []
    for index, path in enumerate(paths, start=1):
        load_image(path)
        resolved = str(Path(path).resolve())
        refs = image_refs.get(resolved, [])
        caption_text = next((item["caption_text"] for item in refs if item["caption_text"]), "")
        figure_ref = next((item["figure_ref"] for item in refs if item["figure_ref"]), "")
        manifest.append(
            {
                "image_id": f"IMG_{index:03d}",
                "image_file": resolved,
                "file_name": Path(path).name,
                "type_hint": infer_image_type_hint(path),
                "referenced_in_sections": [item["section_path"] for item in refs],
                "alt_texts": [item["alt_text"] for item in refs if item["alt_text"]],
                "caption_text": caption_text,
                "figure_ref": figure_ref,
            }
        )
    return manifest


def _collect_image_references(documents: Iterable[dict]) -> dict[str, list[dict]]:
    refs: dict[str, list[dict]] = {}
    for document in documents:
        doc_path = Path(str(document["path"])).resolve()
        heading_stack: List[tuple[int, str]] = []
        previous_nonempty = ""
        for raw_line in str(document["content"]).splitlines():
            stripped_line = raw_line.strip()
            match = HEADER_RE.match(stripped_line)
            if match:
                level = len(match.group(1))
                heading = match.group(2).strip() or "UNTITLED"
                while heading_stack and heading_stack[-1][0] >= level:
                    heading_stack.pop()
                heading_stack.append((level, heading))
                previous_nonempty = stripped_line
                continue
            for image_match in IMAGE_REF_RE.finditer(raw_line):
                alt_text = image_match.group(1).strip()
                raw_ref = urllib.parse.unquote(image_match.group(2).strip())
                candidate = str((doc_path.parent / raw_ref).resolve())
                section_path = " > ".join(item[1] for item in heading_stack) or "ROOT"
                refs.setdefault(candidate, []).append(
                    {
                        "section_path": section_path,
                        "alt_text": alt_text,
                        "caption_text": alt_text or previous_nonempty,
                        "figure_ref": _infer_figure_ref(section_path, alt_text),
                    }
                )
            if stripped_line:
                previous_nonempty = stripped_line
    return refs


def _infer_figure_ref(section_path: str, alt_text: str) -> str:
    for candidate in (section_path.split(" > ")[-1].strip(), alt_text.strip()):
        if not candidate:
            continue
        match = FIGURE_REF_RE.search(candidate)
        if match:
            return f"fig_{match.group(1).replace('.', '_')}"
    return ""
