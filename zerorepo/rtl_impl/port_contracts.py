from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, List

from zerorepo.rtl_impl.rtl_kg.rtl_file_graph_builder import extract_module_header_ports


@dataclass(frozen=True)
class MarkdownPort:
    name: str
    direction: str
    width: str


@dataclass(frozen=True)
class MarkdownPortSection:
    text: str
    ports: tuple[MarkdownPort, ...]


_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+\S")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")


def split_markdown_sections(text: str) -> List[str]:
    normalized = str(text or "").replace("\r\n", "\n").strip()
    if not normalized:
        return []
    lines = normalized.splitlines()
    headings = [index for index, line in enumerate(lines) if _HEADING_RE.match(line)]
    if not headings:
        return [normalized]
    sections: list[str] = []
    for heading_index, heading_start in enumerate(headings):
        start = 0 if heading_index == 0 else heading_start
        end = headings[heading_index + 1] if heading_index + 1 < len(headings) else len(lines)
        section = "\n".join(lines[start:end]).strip()
        if section:
            sections.append(section)
    return sections or [normalized]


def extract_markdown_port_sections(text: str) -> List[MarkdownPortSection]:
    results: list[MarkdownPortSection] = []
    for section in split_markdown_sections(text):
        ports = _extract_ports_from_markdown_tables(section)
        if ports:
            results.append(MarkdownPortSection(text=section, ports=tuple(ports)))
    return results


def markdown_ports(text: str) -> List[MarkdownPort]:
    ordered: list[MarkdownPort] = []
    seen: set[str] = set()
    for section in extract_markdown_port_sections(text):
        for port in section.ports:
            if port.name in seen:
                continue
            seen.add(port.name)
            ordered.append(port)
    return ordered


def normalize_direction(value: Any) -> str:
    direction = str(value or "").strip().lower()
    aliases = {"in": "input", "out": "output", "io": "inout", "bidirectional": "inout"}
    return aliases.get(direction, direction)


def normalize_width(value: Any) -> str:
    width = str(value or "").strip().strip("`").strip()
    width = re.sub(r"\b(bits?|bit)\b", "", width, flags=re.IGNORECASE).strip()
    width = width.replace("`", "")
    width = re.sub(r"\s+", "", width)
    if not width or width in {"1", "[0:0]"}:
        return "1"
    if width.startswith("[") and width.endswith("]"):
        body = width[1:-1]
        match = re.fullmatch(r"(.+):0", body)
        if match:
            msb = _strip_outer_parentheses(match.group(1))
            if msb.isdigit():
                return str(int(msb) + 1)
            minus_one = re.fullmatch(r"(.+?)-1", msb)
            if minus_one:
                return _strip_outer_parentheses(minus_one.group(1))
        return body
    return _strip_outer_parentheses(width)


def ansi_module_ports(module_frame: str) -> List[MarkdownPort]:
    # Preprocessor controls may appear between comma-separated ANSI declarations.
    # Removing directive-only lines preserves every declaration for the text parser.
    cleaned = "\n".join(
        line for line in str(module_frame or "").splitlines() if not line.strip().startswith("`")
    )
    return [
        MarkdownPort(
            name=name,
            direction=normalize_direction(attrs.get("dir")),
            width=normalize_width(attrs.get("width_expr") or "1"),
        )
        for name, attrs in extract_module_header_ports(cleaned)
    ]


def interface_contract_errors(
    actual_ports: Iterable[Any],
    expected_ports: Iterable[Any],
    *,
    label: str = "interface",
) -> List[str]:
    actual = [_coerce_port(item) for item in actual_ports]
    expected = [_coerce_port(item) for item in expected_ports]
    errors: list[str] = []
    actual_names = [item.name for item in actual if item.name]
    expected_names = [item.name for item in expected if item.name]
    duplicates = sorted({name for name in actual_names if actual_names.count(name) > 1})
    if duplicates:
        errors.append(f"{label} contains duplicate ports: {duplicates}")
    missing = [name for name in expected_names if name not in actual_names]
    extra = [name for name in actual_names if name not in expected_names]
    if missing:
        errors.append(f"{label} is missing ports: {missing}")
    if extra:
        errors.append(f"{label} contains unexpected ports: {extra}")
    actual_by_name = {item.name: item for item in actual if item.name}
    for expected_port in expected:
        actual_port = actual_by_name.get(expected_port.name)
        if actual_port is None:
            continue
        if normalize_direction(actual_port.direction) != normalize_direction(expected_port.direction):
            errors.append(
                f"{label} port `{expected_port.name}` direction must be "
                f"{normalize_direction(expected_port.direction)}, got {normalize_direction(actual_port.direction)}"
            )
        if normalize_width(actual_port.width) != normalize_width(expected_port.width):
            errors.append(
                f"{label} port `{expected_port.name}` width must be "
                f"{normalize_width(expected_port.width)}, got {normalize_width(actual_port.width)}"
            )
    return errors


def _extract_ports_from_markdown_tables(section: str) -> List[MarkdownPort]:
    lines = section.splitlines()
    ports: list[MarkdownPort] = []
    index = 0
    while index + 1 < len(lines):
        header = _table_cells(lines[index])
        separator = _table_cells(lines[index + 1])
        if not header or not separator or not all(_is_separator_cell(cell) for cell in separator):
            index += 1
            continue
        columns = [_normalize_column_name(cell) for cell in header]
        name_index = _find_column(columns, {"name", "signal", "signalname", "port", "portname"})
        direction_index = _find_column(columns, {"direction", "dir"})
        width_index = _find_column(columns, {"width", "bitwidth", "bits"})
        if name_index is None or direction_index is None or width_index is None:
            index += 2
            continue
        index += 2
        while index < len(lines):
            cells = _table_cells(lines[index])
            if not cells:
                break
            required_index = max(name_index, direction_index, width_index)
            if len(cells) <= required_index:
                break
            name = cells[name_index].strip().strip("`")
            direction = normalize_direction(cells[direction_index])
            width = normalize_width(cells[width_index])
            if _IDENTIFIER_RE.fullmatch(name) and direction in {"input", "output", "inout"} and width:
                ports.append(MarkdownPort(name=name, direction=direction, width=width))
            index += 1
    deduped: list[MarkdownPort] = []
    seen: set[str] = set()
    for port in ports:
        if port.name in seen:
            continue
        seen.add(port.name)
        deduped.append(port)
    return deduped


def _table_cells(line: str) -> List[str]:
    stripped = str(line or "").strip()
    if "|" not in stripped:
        return []
    return [cell.strip() for cell in stripped.strip("|").split("|")]


def _is_separator_cell(cell: str) -> bool:
    return bool(re.fullmatch(r":?-{3,}:?", cell.strip()))


def _normalize_column_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _find_column(columns: List[str], names: set[str]) -> int | None:
    return next((index for index, value in enumerate(columns) if value in names), None)


def _strip_outer_parentheses(value: str) -> str:
    result = value.strip()
    while result.startswith("(") and result.endswith(")"):
        inner = result[1:-1]
        depth = 0
        balanced = True
        for char in inner:
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth < 0:
                    balanced = False
                    break
        if not balanced or depth != 0:
            break
        result = inner
    return result


def _coerce_port(value: Any) -> MarkdownPort:
    if isinstance(value, MarkdownPort):
        return value
    if isinstance(value, dict):
        getter = value.get
    else:
        getter = lambda key, default="": getattr(value, key, default)
    return MarkdownPort(
        name=str(getter("name", "") or "").strip(),
        direction=normalize_direction(getter("direction", getter("dir", ""))),
        width=normalize_width(getter("width", getter("width_expr", "1"))),
    )
