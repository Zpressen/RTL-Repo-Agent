"""Bounded, stage-specific repairs with explicit targets and whole-artifact validation."""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError

from .json_repair import strip_code_fences


REPAIR_POLICY_VERSION = "local_repair_v1"


def fingerprint(value: Any) -> str:
    def encode(item):
        if isinstance(item, BaseModel):
            return item.model_dump(mode="json")
        raise TypeError(f"Unsupported fingerprint value: {type(item).__name__}")
    text = json.dumps(value, sort_keys=True, ensure_ascii=False, default=encode)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def strict_json(raw: Any) -> Any:
    """Never auto-close a truncated object or accept a valid prefix as a candidate."""
    if isinstance(raw, BaseModel):
        return raw.model_dump(mode="json")
    if isinstance(raw, (dict, list)):
        return copy.deepcopy(raw)
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    def reject_constant(value):
        raise ValueError(f"Invalid JSON numeric constant: {value}")
    return json.loads(strip_code_fences(str(raw)), object_pairs_hook=unique_pairs, parse_constant=reject_constant)


@dataclass
class ArtifactIssue:
    path: str
    code: str
    message: str
    expected: Any = None
    actual: Any = None
    category: str = "format"
    section: str = ""
    unit_id: str = ""
    line: int | None = None
    stage: str = ""
    module: str = ""

    def to_dict(self):
        return asdict(self)


@dataclass
class RepairInspection:
    candidate: Any
    artifact: Any = None
    issues: list[ArtifactIssue] = field(default_factory=list)
    normalizations: list[str] = field(default_factory=list)


def model_issues(model_type, candidate, *, prefix="", section="", unit_id=""):
    try:
        return model_type.model_validate(candidate), []
    except ValidationError as exc:
        issues = []
        for error in exc.errors():
            suffix = "".join(f"[{item}]" if isinstance(item, int) else f".{item}" for item in error["loc"])
            issues.append(ArtifactIssue(
                path=(prefix + suffix).lstrip("."), code=error["type"],
                message=error["msg"], actual=error.get("input"),
                category="structure", section=section, unit_id=unit_id,
            ))
        return None, issues


def repair_prompt(*, targets: dict[str, Any], issues: list[ArtifactIssue], context: str) -> str:
    return (
        "Repair ONLY the explicitly listed targets. Preserve their meaning and all untargeted content.\n"
        "Do not invent missing design facts or fill them with unspecified/empty defaults.\n"
        'Return JSON only: {"patches": [{"target": "<exact target>", "replacement": <required value>}]}.\n'
        "Return exactly one patch per target; no extra targets or overlapping edits.\n"
        "For a document target, replacement is the full Markdown document. For other Markdown targets, "
        "replacement is the target body only, without its heading.\n"
        f"Targets and required structure:\n{json.dumps(targets, ensure_ascii=False, indent=2)}\n"
        f"All diagnostics:\n{json.dumps([issue.to_dict() for issue in issues], ensure_ascii=False, indent=2, default=str)}\n"
        f"Source and binding constraints:\n{context}"
    )


def checked_patches(raw: Any, targets: dict[str, Any]) -> dict[str, Any]:
    payload = strict_json(raw)
    if not isinstance(payload, dict) or set(payload) != {"patches"} or not isinstance(payload["patches"], list):
        raise ValueError("Repair output must contain only a patches list")
    patches = {}
    for item in payload["patches"]:
        if not isinstance(item, dict) or set(item) != {"target", "replacement"}:
            raise ValueError("Each patch must contain only target and replacement")
        target = item["target"]
        if not isinstance(target, str) or target not in targets or target in patches:
            raise ValueError(f"Unknown or duplicate repair target: {target}")
        patches[target] = item["replacement"]
    if set(patches) != set(targets):
        raise ValueError("Repair must cover exactly the requested targets")
    return patches


def patch_rejection_details(raw: Any, targets: dict[str, Any], reason: str) -> dict[str, Any]:
    """Describe the protocol failure without copying another full response."""
    try:
        payload = strict_json(raw)
    except (ValueError, TypeError):
        received = None
        response_kind = "invalid_json"
    else:
        if isinstance(payload, dict) and isinstance(payload.get("patches"), list):
            response_kind = "patches"
            received = [item.get("target") if isinstance(item, dict) else None for item in payload["patches"]]
        else:
            response_kind = "full_object" if isinstance(payload, dict) else "invalid_object"
            received = list(payload) if isinstance(payload, dict) else None
    return {"allowed_targets": sorted(targets), "received_targets": received,
            "response_kind": response_kind, "reason": reason}


class JsonRepairAdapter:
    """JSON field repairs; subclasses choose stable identities and validate semantics."""

    def __init__(self, model_type, context: str):
        self.model_type = model_type
        self.context = context

    def normalize(self, payload):
        return payload, []

    def semantic_issues(self, artifact):
        return []

    def inspect(self, raw):
        try:
            payload = strict_json(raw)
        except (ValueError, TypeError) as exc:
            return RepairInspection(None, issues=[ArtifactIssue("$", "invalid_json", str(exc))])
        if not isinstance(payload, dict):
            return RepairInspection(None, issues=[ArtifactIssue("$", "invalid_object", "Expected a JSON object")])
        payload, changes = self.normalize(payload)
        artifact, issues = model_issues(self.model_type, payload)
        if artifact is not None:
            issues.extend(self.semantic_issues(artifact))
        return RepairInspection(payload, artifact, issues, changes)

    def targets(self, inspection):
        raise NotImplementedError

    def context_for(self, inspection, targets):
        return self.context

    def merge(self, inspection, raw, targets):
        # Accept old full-object responses only when ALL untargeted fields are unchanged.
        # This makes old prompt adapters usable without allowing whole-output rewrites.
        payload = strict_json(raw)
        if isinstance(payload, dict) and "patches" in payload:
            patches = checked_patches(payload, targets)
        else:
            if set(targets) == {"$"}:
                return payload
            patches = {target: self.get(payload, target) for target in targets}
            proposed = copy.deepcopy(inspection.candidate)
            for target, replacement in patches.items():
                self.set(proposed, target, replacement)
            if proposed != payload:
                raise ValueError("Full-object repair changed untargeted fields")
        candidate = copy.deepcopy(inspection.candidate)
        for target, replacement in patches.items():
            if target == "$":
                candidate = replacement
            else:
                self.set(candidate, target, replacement)
        return candidate

    def get(self, payload, target):
        return payload[target]

    def set(self, payload, target, replacement):
        payload[target] = replacement
