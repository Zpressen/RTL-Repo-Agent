"""Cross-launch identity checks; archive incompatible sessions instead of deleting."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shutil
from uuid import uuid4

from zerorepo.rtl_impl.module_planner.utils.artifact_store import atomic_write_json


def file_digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tree_manifest(root):
    root = Path(root)
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("Debug binding cannot contain symlinks")
        if path.is_file():
            result[path.relative_to(root).as_posix()] = file_digest(path)
    return result


def debug_binding(*, top_module, spec_text, spec_paths, contract_json, verify_script, memory_snapshot_sha256='', memory_profile_sha256=''):
    verify_script = Path(verify_script)
    support = {p.relative_to(verify_script.parent).as_posix(): file_digest(p)
               for p in sorted(verify_script.parent.rglob("*"))
               if p.is_file() and not p.is_symlink() and p.suffix in {".py", ".v", ".sv", ".vh", ".mem", ".hex"}}
    result = {"schema_version": 1, "top_module": top_module,
            "spec": hashlib.sha256(spec_text.encode()).hexdigest(),
            "sources": {str(index) + ":" + Path(p).name: file_digest(p) for index, p in enumerate(spec_paths)},
            "contract": hashlib.sha256(contract_json.encode()).hexdigest(), "verifier": support}
    if memory_snapshot_sha256:
        result['memory_snapshot_sha256'] = memory_snapshot_sha256
        result['memory_profile_sha256'] = memory_profile_sha256
    return result


class DebugHistory:
    def __init__(self, workdir, logger=None):
        self.workdir = Path(workdir)
        self.private = self.workdir / "codex_private"
        self.task = self.workdir / "codex_task"
        self.logger = logger

    def select(self, binding, generated_dir):
        if not self.private.exists():
            return None
        reason = "No verifiable debug run binding"
        try:
            record = json.loads((self.private / "run_record.json").read_text())
            state = json.loads((self.private / "session_state.json").read_text())
            descriptor = json.loads((self.private / "run_descriptor.json").read_text())
            status = json.loads((self.private / "debug_status.json").read_text())
            if record["binding"] != binding:
                raise ValueError("Debug source/contract/verifier binding changed")
            if state["run_id"] != descriptor["run_id"] or record["run_id"] != descriptor["run_id"]:
                raise ValueError("Debug run identity mismatch")
            counters = state.get("counters")
            if not isinstance(counters, dict) or any(type(counters.get(key)) is not int or counters[key] < 0
                    for key in ("validation_trials", "readonly_calls", "accepted_actions")):
                raise ValueError("Debug validation counters are invalid")
            accepted = tree_manifest(self.private / "accepted_baseline" / "merged")
            if not accepted or accepted != state["accepted_manifest"]:
                raise ValueError("Accepted RTL baseline checksum mismatch")
            if tree_manifest(generated_dir) != accepted:
                raise ValueError("Current RTL differs from accepted debug baseline")
            if tree_manifest(self.task / "spec") != state["spec_manifest"]:
                raise ValueError("Copied debug spec changed")
            runtime = status["codex_runtime"]
            active_path = self.private / "active_runtime.json"
            if active_path.is_file():
                active = json.loads(active_path.read_text())
                if active.get("run_id") != descriptor["run_id"]:
                    raise ValueError("Live Codex runtime belongs to another run")
                runtime = active
            session_id = runtime["session_id"]
            if not isinstance(session_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", session_id) or not list((self.private / "codex_home" / "sessions").rglob(f"*{session_id}*.jsonl")):
                raise ValueError("Codex session records unavailable")
            if type(runtime.get("episode")) is not int or runtime["episode"] < 1:
                raise ValueError("Codex episode counter is invalid")
            if self.logger:
                self.logger.info("[codex_debug] Resuming verified run %s after %s validations", descriptor["run_id"], state.get("counters", {}).get("validation_trials", 0))
            return {"descriptor": descriptor, "runtime": runtime}
        except (OSError, ValueError, KeyError, TypeError) as exc:
            reason = str(exc)
        self.archive(reason)
        return None

    def archive(self, reason):
        try:
            descriptor = json.loads((self.private / "run_descriptor.json").read_text())
            run_id = descriptor.get("run_id", "legacy")
        except (OSError, ValueError, TypeError):
            run_id = "legacy"
        safe = re.sub(r"[^A-Za-z0-9_.-]", "_", str(run_id)).strip(".") or "legacy"
        directory = self.workdir / "history" / f"{safe}-{uuid4().hex[:8]}"
        directory.mkdir(parents=True)
        for path in (self.private, self.task):
            if path.exists():
                shutil.move(str(path), directory / path.name)
        atomic_write_json(directory / "archive.json", {"run_id": run_id, "reason": reason})
        if self.logger:
            self.logger.info("[codex_debug] Archived previous run at %s: %s", directory, reason)
        return directory
