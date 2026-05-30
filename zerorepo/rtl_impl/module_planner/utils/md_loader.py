from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, List


HEADER_RE = re.compile(r"^(#{1,6})\s+(.*)$")


def expand_markdown_inputs(paths: List[str]) -> List[str]:
    expanded: list[Path] = []
    for raw_path in paths:
        path = Path(raw_path).expanduser()
        if path.is_dir():
            expanded.extend(item for item in path.rglob("*.md") if item.is_file())
            continue
        if path.suffix.lower() == ".md":
            expanded.append(path)

    seen: set[str] = set()
    ordered: list[str] = []
    for path in sorted((item.resolve() for item in expanded), key=lambda item: str(item)):
        path_text = str(path)
        if path_text in seen:
            continue
        seen.add(path_text)
        ordered.append(path_text)
    return ordered


def load_markdown(path: str) -> str:
    content = Path(path).read_text(encoding="utf-8")
    return content.replace("\r\n", "\n").strip()


def load_markdown_files(paths: List[str]) -> List[dict]:
    documents = []
    for path in expand_markdown_inputs(paths):
        documents.append(
            {
                "path": str(path),
                "content": load_markdown(path),
            }
        )
    return documents


def extract_markdown_outline(markdown_text: str) -> List[str]:
    headings: List[str] = []
    stack: List[tuple[int, str]] = []
    for raw_line in markdown_text.splitlines():
        match = HEADER_RE.match(raw_line.strip())
        if not match:
            continue
        level = len(match.group(1))
        heading = match.group(2).strip() or "UNTITLED"
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, heading))
        headings.append(" > ".join(item[1] for item in stack))
    return headings


def format_documents_for_prompt(documents: Iterable[dict]) -> str:
    blocks = []
    for index, document in enumerate(documents, start=1):
        outline = extract_markdown_outline(document["content"])
        outline_text = "\n".join(f"- {item}" for item in outline[:40]) or "- ROOT"
        blocks.append(
            (
                f"[Document DOC_{index:03d}] path={document['path']}\n"
                f"Outline:\n{outline_text}\n\n"
                f"Markdown:\n{document['content']}"
            )
        )
    return "\n\n".join(blocks)
