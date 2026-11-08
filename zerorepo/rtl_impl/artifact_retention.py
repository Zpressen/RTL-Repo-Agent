"""Conservative compaction after durable stage commits, never legacy cleanup."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from .artifact_layout import ArtifactLayout, LAYOUT_VERSION


class ArtifactRetention:
    def __init__(self, layout: ArtifactLayout, mode: str = "compact"):
        if mode not in {"compact", "full"}:
            raise ValueError("artifacts.retention must be compact or full")
        self.layout, self.mode = layout, mode

    def initialize(self, task_id: str):
        from .module_planner.utils.artifact_store import atomic_write_json

        root = self.layout.case_root
        marker = root / "run.json"
        if marker.exists():
            saved = json.loads(marker.read_text(encoding="utf-8"))
            if saved.get("layout_version") != LAYOUT_VERSION:
                raise ValueError("Unsupported RTL output layout version; choose a new case directory")
            if saved.get("task_id") != task_id:
                raise ValueError("RTL output directory belongs to a different task")
        atomic_write_json(marker, {"layout_version": LAYOUT_VERSION, "task_id": task_id,
            "artifacts": {"retention": self.mode},
            "directories": {"plan": "plan", "generate": "generate", "debug": "debug"}})

    @staticmethod
    def _json(path):
        return json.loads(path.read_text(encoding="utf-8"))

    def _remove(self, path):
        # Resolve before removing: a symlink must never grant cleanup access to
        # another case or to external source specifications.
        if path.is_symlink() or not path.resolve().is_relative_to(self.layout.case_root.resolve()):
            return
        if path.is_dir():
            shutil.rmtree(path)
        elif path.is_file():
            path.unlink()

    def compact(self, committed_stages):
        if self.mode != "compact":
            return
        marker = self.layout.case_root / "run.json"
        if not marker.is_file() or self._json(marker).get("layout_version") != LAYOUT_VERSION:
            return
        stages = set(committed_stages)
        # Completed nodes are redundant only after their stage's authoritative
        # artifact is committed. Never collect unfinished repair candidates.
        from .module_planner.utils.local_repair import fingerprint
        owners = {1: "contracts.json", 2: "stage2_decomposition.json",
                  3: "module_skeletons.json", 4: "module_plans.json"}
        for path in (self.layout.case_root / "plan/state/execution").glob("*.json"):
            try:
                payload = self._json(path)
                checksum = payload.pop("checkpoint_fingerprint")
                if checksum != fingerprint(payload) or payload.get("status") != "completed":
                    continue
                for number, artifact in owners.items():
                    prefix = f"stage{number}"
                    if payload.get("stage", "").startswith(prefix) and any(s.startswith(prefix) for s in stages) and self.layout.artifact(artifact).is_file():
                        self._remove(path)
                        break
            except (OSError, ValueError, KeyError, TypeError):
                continue
        for group in ("plan", "generate"):
            requests = self.layout.case_root / group / "traces/requests"
            if requests.is_dir():
                stages.update(path.name for path in requests.iterdir() if path.is_dir())
        for stage in stages:
            # RequestProgress appends stage/module/request-id to the trace root.
            requests = self.layout.traces(stage)
            for module_dir in requests.iterdir() if requests.is_dir() else []:
                failed = []
                for request in module_dir.iterdir() if module_dir.is_dir() else []:
                    status = request / "status.json"
                    try:
                        state = self._json(status).get("status")
                    except (OSError, ValueError, AttributeError):
                        continue
                    if state == "completed" and stage in committed_stages:
                        self._remove(request)
                    elif state in {"failed", "interrupted"}:
                        failed.append(request)
                for request in sorted(failed, key=lambda p: (self._json(p / "status.json").get("updated_at_ns", p.stat().st_mtime_ns), p.name))[:-1]:
                    self._remove(request)
            repairs = self.layout.traces(stage, "repairs")
            if stage in committed_stages:
                self._remove(repairs)
            elif repairs.is_dir():
                for module in repairs.iterdir():
                    attempts = list(module.glob("*/attempt_*.json"))
                    for path in sorted(attempts, key=lambda p: (p.stat().st_mtime_ns, p.name))[:-1]:
                        self._remove(path)
        if "stage5_codegen" in committed_stages:
            self._compact_generations()
        if "stage6_merge" in committed_stages:
            self._remove(self.layout.directory("merge_drafts"))
            self._remove(self.layout.directory("merge_journal"))
            self._compact_debug_simulations()
        self._prune_empty_trace_dirs()

    def _compact_generations(self):
        """Collect only bundles proven unreferenced by explicit store markers."""
        layout = self.layout
        checkpoints = layout.case_root / "generate/state/checkpoints"
        candidates = layout.directory(".stage5_candidates")
        bundles = layout.directory(".stage5_generations")
        references = set()
        active = {}
        obsolete_candidates = []
        from .module_planner.utils.stage5_store import Stage5Store
        store = Stage5Store(layout.case_root)
        try:
            for path in checkpoints.glob("*.json"):
                value = self._json(path)
                store.validate(value)
                active[value["module"]] = value
                references.add(value["bundle_path"])
            # History can be required by accepted debug recovery. It remains a
            # root until its owning recovery implementation retires the record.
            for path in layout.directory(".stage5_history").glob("*/*.json"):
                value = self._json(path)
                if value.get("bundle_path"):
                    store.validate(value)
                    references.add(value["bundle_path"])
            for path in layout.directory(".stage5_publish").glob("*.json"):
                references.add(self._json(path)["candidate"])
            for path in candidates.glob("*/*/checkpoint.json"):
                value = self._json(path)
                store.validate(value)
                current = active.get(value["module"], {})
                # Retain partial candidates: a completed alias can coexist with
                # work on a changed plan that has not yet been promoted.
                if value.get("status") != "completed" or current.get("status") != "completed":
                    references.add(value["bundle_path"])
                else:
                    # The active marker already roots completed bundles. A
                    # completed candidate marker is a redundant publication alias.
                    obsolete_candidates.append(path.parent)
        except (OSError, ValueError, KeyError, TypeError):
            return  # A corrupt reference graph cannot authorize collection.
        if any(not (layout.case_root / ref).resolve().is_relative_to(bundles.resolve())
               or not (layout.case_root / ref).is_dir() for ref in references):
            return
        for path in obsolete_candidates:
            self._remove(path)
        for directory in bundles.glob("*/*"):
            if not any((layout.case_root / ref).resolve().is_relative_to(directory.resolve()) for ref in references):
                self._remove(directory)

    def snapshot_debug_scratch(self, workdir, generated_dir=None):
        """Full traces retain previous simulation inputs before scratch reset."""
        if self.mode != "full":
            return
        workdir = Path(workdir)
        if not workdir.is_dir() or not any(workdir.iterdir()):
            return
        if not workdir.resolve().is_relative_to(self.layout.case_root.resolve()):
            raise ValueError("Debug scratch must belong to its case")
        from uuid import uuid4
        target = workdir.parent / "state/history" / f"simulation-{uuid4().hex}"
        shutil.copytree(workdir, target / "simulation", symlinks=True)
        if generated_dir is not None and Path(generated_dir).is_dir():
            shutil.copytree(generated_dir, target / "generated", symlinks=True)

    def _compact_debug_simulations(self):
        # Scratch build trees are reproducible; accepted RTL/spec/session trees
        # and their manifests are never searched or modified by this collector.
        debug = self.layout.case_root / "debug"
        for category in ("modules", "system"):
            root = debug / category
            for module in root.iterdir() if root.is_dir() else []:
                self._remove(module / "simulation/obj_dir")
                private = module / "state/codex_private"
                for scratch in ("debug_artifacts/obj_dir", "final_verify/obj_dir"):
                    self._remove(private / scratch)
                journal = private / "journal/codex_validation_journal.jsonl"
                if not journal.is_file():
                    continue
                try:
                    events = [json.loads(line) for line in journal.read_text().splitlines() if line.strip()]
                    evaluations = [e for e in events if e.get("event") == "evaluate"]
                    keep = set()
                    # Keep current trial, latest failed trial, and accepted trial.
                    for records in (evaluations, [e for e in evaluations if not e.get("result", {}).get("is_pass")],
                                    [e for e in events if e.get("event") == "accept"]):
                        if records:
                            last = records[-1]
                            keep.add((last["candidate_id"], int(last.get("revision", last.get("candidate_revision")))))
                    state = self._json(private / "session_state.json")
                    last = state.get("last_validation") or {}
                    if last.get("candidate_id") and last.get("candidate_revision"):
                        keep.add((last["candidate_id"], int(last["candidate_revision"])))
                except (OSError, ValueError, KeyError, TypeError):
                    continue
                for wave in (private / "candidates").glob("*/revision_*/artifacts/wave.vcd"):
                    try:
                        identity = (wave.parents[2].name, int(wave.parents[1].name.removeprefix("revision_")))
                    except ValueError:
                        continue
                    if identity not in keep:
                        self._remove(wave)

    def _prune_empty_trace_dirs(self):
        for group in ("plan", "generate"):
            root = self.layout.case_root / group / "traces"
            if root.is_symlink() or not root.resolve().is_relative_to(self.layout.case_root.resolve()):
                continue
            for path in sorted(root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
                if (path.is_dir() and not path.is_symlink()
                        and path.resolve().is_relative_to(self.layout.case_root.resolve()) and not any(path.iterdir())):
                    path.rmdir()
