from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any
from .schemas import DemoError
from .store import Store, dump, uid

RTL_SUFFIXES = {".v", ".sv", ".vh", ".svh"}


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def safe_path(root: Path, relative: str) -> Path:
    root = root.resolve()
    p = root / relative
    if p.is_symlink() or not p.resolve().is_relative_to(root):
        raise DemoError("unsafe_path", "产物路径超出允许范围。", 403)
    # Reject symlink components, not only the final component.
    cur = p
    while cur != root:
        if cur.is_symlink():
            raise DemoError("unsafe_path", "不能通过符号链接读取产物。", 403)
        cur = cur.parent
    return p


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".publish-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def tree_manifest(root: Path) -> tuple[str, list[dict]]:
    files = []
    for p in sorted(root.rglob("*")):
        if p.is_symlink():
            raise DemoError("unsafe_path", "RTL快照含符号链接。", 403)
        if p.is_file() and p.suffix.lower() in RTL_SUFFIXES:
            files.append(
                {
                    "path": p.relative_to(root).as_posix(),
                    "sha256": sha(p),
                    "size_bytes": p.stat().st_size,
                }
            )
    if not files:
        raise DemoError("empty_rtl", "未找到完整RTL文件。", 422)
    return hashlib.sha256(dump(files).encode()).hexdigest(), files


PRIVATE_VALUES=set()


def secret_values():
    return PRIVATE_VALUES|{value for name,value in os.environ.items()
            if re.search(r'(?:API_KEY|PASSWORD|ACCESS_TOKEN|GATEWAY_KEY|BRIDGE_TOKEN)$',name,re.I)
            and len(value)>=8}


def redact(text: str) -> str:
    # Tool excerpts may begin in the middle of an absolute private path.
    text = re.sub(r'''[^\s<>"']*codex_private[^\s<>"']*''', '[debug-artifact]', text)
    text=re.sub(r'(?i)([a-z][a-z0-9+.-]*://)[^\s/:@]+:[^\s@]+@',r'\1[redacted]@',text)
    text=re.sub(r'sk-[A-Za-z0-9_-]{16,}','[redacted]',text)
    for value in secret_values():text=text.replace(value,'[redacted]')
    text = re.sub(
        r'(?i)(authorization\s*[:=]\s*(?:bearer\s+)?)[^\s"\']+', r"\1[redacted]", text
    )
    text = re.sub(
        r"(?i)((?:api[_-]?key|password|access[_-]?token|gateway[_-]?key)\s*[=:]\s*)[^\s,]+",
        r"\1[redacted]",
        text,
    )
    text = re.sub(r'/(?:home|run/user|tmp|etc)/[^\s<>"\']+', "[server-path]", text)
    return text


def signal_mismatches(text: str) -> list[dict]:
    """Original per-output counters, never summed into sample counts."""
    return [{'signal': name, 'count': int(count), 'first_failure_ticks': tick}
            for name, count, tick in re.findall(
                r'''Output\s+['"]?(\w+)['"]?\s+(?:signal\s+)?has\s+(\d+)\s+mismatches\.\s+First\s+(?:at time|mismatch occurred at time)\s+(\d+)''', text)]


def parse_report(text: str) -> dict:
    try:
        obj = json.loads(text)
        stdout = str(obj.get("stdout", "")) if isinstance(obj, dict) else str(obj)
        stderr = str(obj.get("stderr", "")) if isinstance(obj, dict) else ""
    except ValueError:
        stdout, stderr = text, ""
    totals = set(
        (int(a), int(b))
        for a, b in re.findall(
            r"Total mismatched samples is\s+(\d+)\s+out of\s+(\d+)\s+samples", stdout
        )
    )
    if len(totals) > 1:
        raise DemoError("report_conflict", "报告包含相互冲突的采样统计。", 422)
    mismatched, total = next(iter(totals)) if totals else (None, None)
    if total is not None and (total <= 0 or mismatched > total):
        raise DemoError("report_conflict", "报告采样计数无效。", 422)
    # Canonical wrapper summaries and the named summaries emitted by the trusted CLIs.
    names = r"(?:system_verify|e203_exu_alu_system|aes_cipher_system|aes_cipher_system_hard|aes_inv_cipher_system|aes_inv_cipher_top_system|sdc_controller_system)"
    summary = re.findall(r"^\s*" + names + r":\s*(PASS|FAIL)\s*$", stdout, re.M)
    if len(set(summary)) > 1:
        raise DemoError("report_conflict", "报告包含冲突的验证结论。", 422)
    fatal = bool(
        re.search(r"%Error|Traceback|\bFAIL\b|error:", stderr, re.I)
        or re.search(r"%Error|Traceback|^\s*FAIL\s*$", stdout, re.M)
    )
    completed = bool(totals) or (
        bool(summary) and set(summary) == {"PASS"} and not fatal
    )
    passed = (
        bool(summary)
        and set(summary) == {"PASS"}
        and not fatal
        and (mismatched is None or mismatched == 0)
    )
    verdict = (
        "pass"
        if passed
        else ("fail" if totals or "FAIL" in summary or fatal else "unverified")
    )
    times = [
        int(x) for x in re.findall(r"First mismatch occurred at time\s+(\d+)", stdout)
    ]
    return {
        "verdict": verdict,
        "simulation_completed": completed,
        "total_samples": total,
        "mismatched_samples": mismatched,
        "first_failure_ticks": str(min(times)) if times else None,
        "text": stdout + ("\n" + stderr if stderr else ""),
    }


class Artifacts:
    def __init__(self, root: Path, store: Store):
        self.root, self.store = root, store
        self.private_values=set()

    def add(
        self, path: Path, kind: str, owner: str | None = None, display: bool = False
    ) -> dict:
        if path.is_symlink() or not path.is_file():
            raise DemoError("artifact_missing", "所需产物缺失或不安全。", 422)
        source_hash = sha(path)
        data = path.read_bytes()
        if display and kind == "report":
            data = redact(parse_report(data.decode())["text"]).encode()
            for value in self.private_values:data=data.replace(value.encode(),b'[redacted]')
        if display and any(value.encode() in data for value in secret_values()|self.private_values):
            raise DemoError('private_output','产物包含私有配置值，已拒绝公开归档。',409)
        digest = hashlib.sha256(data).hexdigest()
        key = f"artifacts/{digest}.{kind}"
        dst = safe_path(self.root, key)
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists():
            fd, name = tempfile.mkstemp(dir=dst.parent)
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            os.replace(name, dst)
        ident = (
            "artifact-"
            + hashlib.sha256(
                dump([owner, kind, source_hash, digest]).encode()
            ).hexdigest()[:32]
        )
        record = {
            "artifact_id": ident,
            "kind": kind,
            "sha256": digest,
            "source_sha256": source_hash,
            "size_bytes": len(data),
            "storage_key": key,
            "exposure": "display" if display else "private",
        }
        self.store.put("artifact", record["artifact_id"], record, owner, immutable=True)
        return record

    def file(self, artifact: dict, verify: bool = True) -> Path:
        p = safe_path(self.root, artifact["storage_key"])
        if not p.is_file() or (verify and sha(p) != artifact["sha256"]):
            raise DemoError("evidence_inconsistent", "产物缺失或摘要不一致。", 409)
        return p

    def snapshot(
        self,
        source: Path,
        version_id: str,
        run_id: str,
        owner: str | None = None,
        parent: str | None = None,
        disposition: str = "accepted",
    ) -> dict:
        digest, manifest = tree_manifest(source)
        for entry in manifest:
            data=safe_path(source,entry['path']).read_bytes()
            if any(value.encode() in data for value in secret_values()|self.private_values):
                raise DemoError('private_output','RTL包含私有配置值，已拒绝公开归档。',409)
        key = f"snapshots/{version_id}"
        target = safe_path(self.root, key)
        if target.exists():
            if tree_manifest(target)[0] != digest:
                raise DemoError("immutable_conflict", "快照不能覆盖。", 409)
        else:
            target.mkdir(parents=True)
            for entry in manifest:
                dst = safe_path(target, entry["path"])
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(safe_path(source, entry["path"]), dst)
        try:
            existing = self.store.get("version", version_id, owner)
            if existing["tree_sha256"] != digest or existing["run_id"] != run_id:
                raise DemoError("immutable_conflict", "快照不能覆盖。", 409)
            return existing
        except DemoError as error:
            if error.code != "not_found":
                raise
        modules = []
        for entry in manifest:
            src = safe_path(target, entry["path"])
            artifact = self.add(src, "rtl", owner, display=True)
            names = re.findall(
                r"^\s*module\s+([\w$]+)", src.read_text(errors="replace"), re.M
            )
            modules.append(
                {
                    "module_id": names[0] if names else src.stem,
                    "file": entry["path"],
                    "artifact_id": artifact["artifact_id"],
                    "sha256": entry["sha256"],
                }
            )
        record = {
            "version_id": version_id,
            "run_id": run_id,
            "tree_sha256": digest,
            "file_manifest": manifest,
            "modules": modules,
            "storage_key": key,
            "parent_version_id": parent,
            "disposition": disposition,
        }
        self.store.put("version", version_id, record, owner, immutable=True)
        return record

    def version_path(self, version: dict) -> Path:
        root = safe_path(self.root, version["storage_key"])
        if tree_manifest(root)[0] != version["tree_sha256"]:
            raise DemoError("evidence_inconsistent", "RTL快照已变更。", 409)
        return root
