"""Exact source indexing and a compact, locally repairable responsibility draft."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import re

from pydantic import Field

from ..schemas import ResponsibilityUnit, ResponsibilityLedgerOutput, StateObject, SourceEvidence
from .artifact_store import atomic_write_json
from .local_repair import JsonRepairAdapter, ArtifactIssue, fingerprint
from .responsibility_planning import _sections, source_documents, verify_source


class DraftResponsibility(ResponsibilityUnit):
    source_evidence_ids: list[str] = Field(default_factory=list)


class DraftState(StateObject):
    source_evidence_ids: list[str] = Field(default_factory=list)


class ResponsibilityLedgerDraft(ResponsibilityLedgerOutput):
    responsibilities: list[DraftResponsibility] = Field(min_length=1)
    state_objects: list[DraftState] = Field(default_factory=list)


class EvidenceRegistry:
    def __init__(self, planning_input):
        self._planning_input = planning_input
        self.documents = source_documents(planning_input)
        self.entries = {}
        for path, text in sorted(self.documents.items()):
            if text is None:
                raise ValueError(f"Unreadable input specification: {path}")
            sections = _sections(text)
            lines = text.splitlines(keepends=True)
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
            start, size, fenced = 0, 0, False

            def add(end):
                quote = "".join(lines[start:end]).rstrip("\n")
                if not quote.strip():
                    return
                ref = SourceEvidence(source_file=path, quote=quote, start_line=start + 1,
                    end_line=start + 1 + quote.count("\n"), section_path=sections[start], content_hash=digest)
                verify_source(ref, self.documents)
                identity = "EV_" + fingerprint(ref.model_dump())[:24]
                self.entries[identity] = ref

            for i, line in enumerate(lines):
                if re.match(r"^\s*(```|~~~)", line):
                    fenced = not fenced
                if i > start and (size >= 2400 or (not fenced and re.match(r"^#{1,6}\s", line))):
                    add(i)
                    start, size = i, 0
                size += len(line)
                if not fenced and not line.strip():
                    add(i + 1)
                    start, size = i + 1, 0
            if start < len(lines):
                add(len(lines))

    def register(self, source):
        ref = source.model_copy(deep=True) if isinstance(source, SourceEvidence) else SourceEvidence.model_validate(source)
        verify_source(ref, source_documents(self._planning_input))
        identity = evidence_id(ref.model_dump())
        self.entries[identity] = ref
        return identity

    def expand(self, identities):
        if not identities:
            raise ValueError("Select a nonempty list of unique EV evidence IDs")
        if len(set(identities)) != len(identities):
            from collections import Counter
            repeated = [identity for identity, count in Counter(identities).items() if count > 1]
            raise ValueError(f"Select unique EV evidence IDs; repeated IDs: {repeated}")
        result = []
        documents = source_documents(self._planning_input)
        for identity in identities:
            if identity not in self.entries:
                raise ValueError(f"Unknown evidence ID: {identity}")
            ref = self.entries[identity].model_copy(deep=True)
            verify_source(ref, documents)
            result.append(ref.model_dump())
        return result

    def register_tree(self, value):
        if hasattr(value, "model_dump"):
            value = value.model_dump()
        if isinstance(value, dict):
            if value.get("source_file") and value.get("quote"):
                self.register(value)
            else:
                for item in value.values():
                    self.register_tree(item)
        elif isinstance(value, list):
            for item in value:
                self.register_tree(item)

    def save(self, root):
        atomic_write_json(Path(root) / "plan/state/evidence_registry.json", {
            "version": "evidence_registry_v2", "source_fingerprint": fingerprint(self.documents),
            "entries": {k: v.model_dump() for k, v in self.entries.items()},
        })

    def catalog(self):
        return [{"id": k, "file": v.source_file, "section": v.section_path,
                 "lines": [v.start_line, v.end_line], "text": v.quote} for k, v in self.entries.items()]

    def prompt_catalog(self, identities=None):
        """Lossless prompt view: share repeated file and section strings once."""
        if identities is None:
            entries = self.entries
        else:
            identities = set(identities)
            unknown = identities - self.entries.keys()
            if unknown:
                raise ValueError(f"Unknown evidence IDs in prompt catalog: {sorted(unknown)}")
            entries = {key: ref for key, ref in self.entries.items() if key in identities}
        files = {value: f"FILE_{index:03d}" for index, value in enumerate(
            sorted({ref.source_file for ref in entries.values()}), 1)}
        sections = {value: f"SECTION_{index:03d}" for index, value in enumerate(
            sorted({ref.section_path for ref in entries.values()}), 1)}
        return {
            "usage": "Resolve file_id and section_id with the dictionaries. Select only entries[].id as EV evidence IDs.",
            "files": {identity: value for value, identity in files.items()},
            "sections": {identity: value for value, identity in sections.items()},
            "entries": [{"id": key, "file_id": files[ref.source_file], "section_id": sections[ref.section_path],
                         "lines": [ref.start_line, ref.end_line], "text": ref.quote}
                        for key, ref in entries.items()],
        }

    def resolve(self, draft):
        payload = draft.model_dump()
        for group in ("responsibilities", "state_objects"):
            for item in payload[group]:
                identities = item.pop("source_evidence_ids", [])
                item["source_refs"] = self.expand(identities)
        return ResponsibilityLedgerOutput.model_validate(payload)

    @property
    def planning_input(self):
        return self._planning_input

    @planning_input.setter
    def planning_input(self, value):
        self._planning_input = value


class ResponsibilityRepairAdapter(JsonRepairAdapter):
    def __init__(self, registry, planning_input, validator):
        super().__init__(ResponsibilityLedgerDraft, "")
        self.registry = registry
        registry.planning_input = planning_input
        self.planning_input, self.validator = planning_input, validator

    def inspect(self, raw):
        inspection = super().inspect(raw)
        payload = inspection.candidate
        if isinstance(payload, dict):
            for issue in inspection.issues:
                match = re.match(r"^(responsibilities|state_objects)\[(\d+)\](?:\.(.+))?$", issue.path)
                if not match:
                    continue
                group, position, field = match.groups()
                entries = payload.get(group, [])
                key = "responsibility_id" if group == "responsibilities" else "state_id"
                if not isinstance(entries, list) or int(position) >= len(entries) or not isinstance(entries[int(position)], dict):
                    continue
                identity = entries[int(position)].get(key)
                if not isinstance(identity, str) or not identity or sum(isinstance(e, dict) and e.get(key) == identity for e in entries) != 1:
                    continue
                path = f"{group}[{identity}]"
                if field and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", field):
                    path += "." + field
                elif field and field.startswith("source_evidence_ids["):
                    path += ".source_evidence_ids"
                issue.path = path
        return inspection

    def semantic_issues(self, artifact):
        issues = []
        for group, identity_field in (("responsibilities", "responsibility_id"), ("state_objects", "state_id")):
            for item in getattr(artifact, group):
                ids = item.source_evidence_ids
                if any(i not in self.registry.entries for i in ids) or (not ids and not item.source_refs):
                    issues.append(ArtifactIssue(f"{group}[{getattr(item, identity_field)}].source_evidence_ids",
                        "invalid_evidence", "Select nonempty IDs from the supplied evidence registry", category="source"))
        if issues:
            return issues
        try:
            ledger = self.registry.resolve(artifact)
            errors = self.validator(ledger)
        except (ValueError, TypeError) as exc:
            return [ArtifactIssue("$", "invalid_ledger", str(exc), category="source")]
        for error in errors:
            target = "$"
            for ru in artifact.responsibilities:
                if error.startswith(ru.responsibility_id + ":"):
                    target = f"responsibilities[{ru.responsibility_id}]"
                    if "source_refs" in error:
                        target += ".source_evidence_ids"
                    break
            for state in artifact.state_objects:
                if error.startswith("state " + state.state_id + ":"):
                    target = f"state_objects[{state.state_id}]"
                    if any(x in error for x in ("quote", "source", "content_hash")):
                        target += ".source_evidence_ids"
                    break
            issues.append(ArtifactIssue(target, "invalid_ledger", error, category="hardware"))
        return issues

    def targets(self, inspection):
        paths = {i.path for i in inspection.issues}
        if "$" in paths or any(not re.fullmatch(r"(responsibilities|state_objects)\[[^\]]+\](?:\.[A-Za-z_][A-Za-z0-9_]*)?", p) for p in paths):
            return {"$": {"type": "ResponsibilityLedgerDraft", "schema": draft_schema()}}
        # An entity replacement subsumes its evidence field replacement.
        paths = {p for p in paths if not any(p.startswith(other + ".") for other in paths)}
        targets = {}
        schema = draft_schema()
        for path in sorted(paths):
            hint = {"type": "complete ledger entry"}
            if "]." in path:
                field = path.split("].", 1)[1]
                definition = "DraftResponsibility" if path.startswith("responsibilities[") else "DraftState"
                hint = {"required_structure": schema["$defs"][definition]["properties"].get(field, {})}
            targets[path] = hint
        return targets

    def get(self, payload, target):
        if target == "$":
            return payload
        match = re.fullmatch(r"(responsibilities|state_objects)\[([^\]]+)\](?:\.(.+))?", target)
        group, identity, field = match.groups()
        key = "responsibility_id" if group == "responsibilities" else "state_id"
        items = [x for x in payload[group] if x.get(key) == identity]
        if len(items) != 1:
            raise ValueError("Repair requires one unique stable ledger identity")
        return items[0].get(field, []) if field else items[0]

    def set(self, payload, target, replacement):
        match = re.fullmatch(r"(responsibilities|state_objects)\[([^\]]+)\](?:\.(.+))?", target)
        group, identity, field = match.groups()
        key = "responsibility_id" if group == "responsibilities" else "state_id"
        items = [x for x in payload[group] if x.get(key) == identity]
        if len(items) != 1:
            raise ValueError("Repair requires one unique stable ledger identity")
        if field:
            items[0][field] = replacement
            if field == "source_evidence_ids":
                items[0].pop("source_refs", None)
        else:
            if not isinstance(replacement, dict) or replacement.get(key) != identity:
                raise ValueError("Repair cannot change a ledger entry's identity")
            items[0].clear()
            items[0].update(copy.deepcopy(replacement))

    def context_for(self, inspection, targets):
        context = {"targets": {t: self.get(inspection.candidate, t) for t in targets},
                   "evidence_catalog": self.registry.catalog()}
        if "$" not in targets:
            context["related_entries"] = {t.split("].", 1)[0] + "]": self.get(inspection.candidate, t.split("].", 1)[0] + "]")
                for t in targets if "]." in t}
        return json.dumps(context, ensure_ascii=False, separators=(",", ":"))


def draft_schema():
    schema = ResponsibilityLedgerDraft.model_json_schema()
    for definition in schema.get("$defs", {}).values():
        definition.get("properties", {}).pop("source_refs", None)
    schema.get("$defs", {}).pop("SourceEvidence", None)
    return schema


def evidence_id(source):
    return "EV_" + fingerprint(source)[:24]


def deduplicate_evidence(value):
    """Prompt-only projection: preserve all evidence once and refer to it by ID."""
    evidence = {}

    def visit(item):
        if isinstance(item, dict):
            if item.get("source_file") and item.get("quote"):
                identity = evidence_id(item)
                evidence[identity] = item
                return {"evidence_ref": identity}
            return {k: visit(v) for k, v in item.items()}
        if isinstance(item, list):
            return [visit(v) for v in item]
        return item

    context = visit(value)
    return {**context, "evidence": evidence} if isinstance(context, dict) else {"context": context, "evidence": evidence}
