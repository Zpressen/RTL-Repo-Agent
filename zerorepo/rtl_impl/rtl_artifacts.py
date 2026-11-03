"""Stable HDL tree fingerprints shared by CLI and application runtimes."""
import hashlib
import json
from pathlib import Path


class RTLTreeError(ValueError):
    def __init__(self, code, message, status):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def tree_manifest(root: Path) -> tuple[str, list[dict]]:
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise RTLTreeError("unsafe_path", "RTL快照含符号链接。", 403)
        if path.is_file() and path.suffix.lower() in {".v", ".sv", ".vh", ".svh"}:
            files.append({"path": path.relative_to(root).as_posix(),
                          "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                          "size_bytes": path.stat().st_size})
    if not files:
        raise RTLTreeError("empty_rtl", "未找到完整RTL文件。", 422)
    payload = json.dumps(files, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest(), files
