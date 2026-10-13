"""Immutable checkpoint bundles with separate candidate and active markers."""
from __future__ import annotations

import json
from pathlib import Path

from .artifact_store import atomic_write_json, atomic_write_text
from .local_repair import fingerprint


class Stage5Store:
    def __init__(self, workspace):
        self.workspace = Path(workspace).resolve()

    def candidate_file(self, module, key):
        return self.workspace / ".stage5_candidates" / module / key / "checkpoint.json"

    def bundle(self, checkpoint, fragments, contracts):
        checkpoint = {key: value for key, value in checkpoint.items() if key != "bundle_path"}
        module = checkpoint["module"]
        identity = fingerprint({"checkpoint": checkpoint, "fragments": fragments, "contracts": contracts})
        directory = self.workspace / ".stage5_generations" / module / identity / "fragments"
        marker = directory / f"{module}_checkpoint.json"
        if not marker.exists():
            atomic_write_text(directory / f"{module}_fragments.v", fragments)
            atomic_write_json(directory / f"{module}_contracts.json", contracts)
            atomic_write_json(marker, checkpoint)
        self.validate({**checkpoint, "bundle_path": str(directory.relative_to(self.workspace))})
        return {**checkpoint, "bundle_path": str(directory.relative_to(self.workspace))}

    def validate(self, checkpoint):
        directory = (self.workspace / checkpoint["bundle_path"]).resolve()
        if not directory.is_relative_to(self.workspace / ".stage5_generations"):
            raise ValueError("Checkpoint bundle is outside generation storage")
        module = checkpoint["module"]
        saved = json.loads((directory / f"{module}_checkpoint.json").read_text())
        if saved != {k: v for k, v in checkpoint.items() if k != "bundle_path"}:
            raise ValueError("Checkpoint marker does not match immutable bundle")
        fragments = (directory / f"{module}_fragments.v").read_text()
        contracts = json.loads((directory / f"{module}_contracts.json").read_text())
        if fingerprint(fragments) != checkpoint["fragment_fingerprint"] or fingerprint(contracts) != checkpoint["contracts_fingerprint"]:
            raise ValueError("Checkpoint bundle content checksum mismatch")
        return fragments, contracts

    def restore_aliases(self, checkpoint):
        fragments, contracts = self.validate(checkpoint)
        directory = self.workspace / "fragments"
        module = checkpoint["module"]
        for path, value in [(directory / f"{module}_fragments.v", fragments),
                            (directory / f"{module}_contracts.json", json.dumps(contracts, ensure_ascii=False, indent=2) + "\n")]:
            if not path.exists() or path.read_text() != value:
                atomic_write_text(path, value)
