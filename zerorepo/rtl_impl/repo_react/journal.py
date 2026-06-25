from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any


class RepoReActJournal:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "snapshots").mkdir(parents=True, exist_ok=True)

    def append_jsonl(self, name: str, payload: dict[str, Any]) -> None:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def write_json(self, relative_path: str, payload: dict[str, Any]) -> Path:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return path

    def snapshot_files(self, *, step: int, label: str, files: list[Path]) -> str:
        snap_dir = self.root / "snapshots" / f"step_{int(step):03d}_{label}"
        if snap_dir.exists():
            shutil.rmtree(snap_dir)
        snap_dir.mkdir(parents=True, exist_ok=True)
        for path in files:
            if not path.is_file():
                continue
            target = snap_dir / path.name
            shutil.copyfile(path, target)
        return str(snap_dir)
