"""Conservative string escaping shared by artifact and public-report readers."""
from __future__ import annotations

import re


def escape_invalid_json_backslashes(text: str) -> str:
    """Preserve literal LaTeX/HDL backslashes emitted inside JSON strings.

    Only escapes rejected by JSON are doubled. Existing valid escapes (including
    escaped quotes, newlines and Unicode) and structural text stay untouched.
    """
    out = []
    in_string = False
    index = 0
    while index < len(text):
        char = text[index]
        if in_string and char == "\\" and index + 1 < len(text):
            following = text[index + 1]
            valid = following in '"\\/bfnrt' or (
                following == "u" and re.fullmatch(r"[0-9a-fA-F]{4}", text[index + 2:index + 6])
            )
            if valid:
                out.extend((char, following))
                index += 2
                continue
            out.append("\\\\")
        else:
            out.append(char)
            if char == '"':
                in_string = not in_string
        index += 1
    return "".join(out)
