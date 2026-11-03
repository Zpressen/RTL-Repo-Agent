from __future__ import annotations

import copy
import json
import re
from types import SimpleNamespace

from ..schemas import ModulePlanArtifact, SubtaskCodeArtifact
from .local_repair import ArtifactIssue, JsonRepairAdapter, strict_json


class ModulePlanRepairAdapter(JsonRepairAdapter):
    def __init__(self, *, module, required, context, source_blocks, validator):
        super().__init__(ModulePlanArtifact, context)
        self.module = module
        self.required = required
        self.source_blocks = source_blocks
        self.validator = validator
        self.ambiguous = False
        self.safe_ids = set()

    def _safe_item(self, item):
        return isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"] in self.safe_ids

    def normalize(self, payload):
        changes = []
        for key, expected in (("module", self.module), ("schema_version", "module_plan_v1")):
            if payload.get(key) != expected:
                payload[key] = expected
                changes.append(f"Assembled authoritative {key}")
        items = payload.get("subtasks")
        ids = [item.get("id") if isinstance(item, dict) else None for item in items] if isinstance(items, list) else []
        expected_ids = [item["id"] for item in self.required]
        self.ambiguous = not isinstance(items, list) or len(ids) != len(items) or any(not isinstance(item, str) for item in ids) or len(set(ids)) != len(ids) or any(item not in expected_ids for item in ids)
        self.safe_ids = {item for item in ids if isinstance(item, str) and item in expected_ids and ids.count(item) == 1}
        if self.ambiguous and isinstance(items, list):
            required_by_id = {item["id"]: item for item in self.required}
            for item in items:
                if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"] in self.safe_ids:
                    for key, expected in required_by_id[item["id"]].items():
                        if item.get(key) != expected:
                            item[key] = expected
                            changes.append(f"Assembled {item['id']}.{key} from source")
        if not self.ambiguous:
            by_id = {item["id"]: item for item in items}
            ordered = []
            for required in self.required:
                item = by_id.get(required["id"], {})
                for key, expected in required.items():
                    if item.get(key) != expected:
                        item[key] = expected
                        changes.append(f"Assembled {required['id']}.{key} from source")
                ordered.append(item)
            if ids != expected_ids:
                changes.append("Assembled required subtask order/coverage")
            payload["subtasks"] = ordered
        return payload, changes

    def inspect(self, raw):
        result = super().inspect(raw)
        if result.candidate is None:
            return result
        if self.ambiguous:
            result.issues.append(ArtifactIssue("subtasks", "ambiguous_identity", "Subtask IDs are missing, duplicated, or unknown; cannot map content safely", expected=self.required, category="structure"))
        for index, item in enumerate(result.candidate.get("subtasks", []) if isinstance(result.candidate.get("subtasks"), list) else []):
            if not isinstance(item, dict):
                continue
            unit = item.get("id", "")
            if "constraints" not in item:
                result.issues.append(ArtifactIssue(f"subtasks[{index}].constraints", "missing_required_field", "Declare constraints explicitly; use [] when none", unit_id=unit))
            if isinstance(item.get("description"), str) and not item["description"].strip():
                result.issues.append(ArtifactIssue(f"subtasks[{index}].description", "empty_description", "Description must contain meaningful text", unit_id=unit))
            if result.artifact is None:
                for key in ("timing_obligation_ids", "logical_value_tags"):
                    if item.get(key):
                        result.issues.append(ArtifactIssue(f"subtasks[{index}].{key}", "retired_field", f"{key} compatibility field must be empty", unit_id=unit))
        return result

    def semantic_issues(self, artifact):
        issues = []
        for error in self.validator(artifact):
            subtask = next((item for item in artifact.subtasks if error.startswith(item.id + ":")), None)
            field = next((key for key in ("constraints", "timing_obligation_ids", "logical_value_tags", "spec_refs", "target") if key in error), "")
            index = artifact.subtasks.index(subtask) if subtask else None
            path = f"subtasks[{index}]" + (f".{field}" if field else "") if subtask else "subtasks"
            issues.append(ArtifactIssue(path, "plan_constraint", error, category="structure", unit_id=subtask.id if subtask else ""))
        return issues

    def targets(self, inspection):
        if inspection.candidate is None:
            return {"$": {"original": None, "expected": self.model_type.model_json_schema(), "required_subtasks": self.required}}
        targets = {}
        if self.ambiguous:
            items = inspection.candidate.get("subtasks")
            unresolved = [item for item in items if not self._safe_item(item)] if isinstance(items, list) else items
            targets["subtasks:unresolved"] = {
                "original": unresolved, "expected": [item for item in self.required if item["id"] not in self.safe_ids],
                "content_fields": ["description", "constraints"],
                "rule": "Replace only ambiguous/missing identities; preserve all uniquely identified subtasks",
            }
        elif any(issue.path == "subtasks" for issue in inspection.issues):
            return {"subtasks": {"original": inspection.candidate.get("subtasks"), "expected": self.required, "content_fields": ["description", "constraints"]}}
        for issue in inspection.issues:
            if self.ambiguous and issue.path == "subtasks":
                continue
            match = re.match(r"subtasks\[(\d+)\](?:\.([A-Za-z_]+))?", issue.path)
            if not match:
                return {"$": {"original": inspection.candidate, "expected": self.model_type.model_json_schema()}}
            item = inspection.candidate["subtasks"][int(match.group(1))]
            if self.ambiguous and not self._safe_item(item):
                continue
            target = f"subtasks/{item['id']}" + (f"/{match.group(2)}" if match.group(2) else "")
            targets[target] = {"original": item.get(match.group(2)) if match.group(2) else item, "expected": self.model_type.model_json_schema()["$defs"]["ModulePlanSubtask"]}
        # An entry patch subsumes all its field patches.
        return {key: value for key, value in targets.items() if not any(key.startswith(other + "/") for other in targets if other != key)}

    def context_for(self, inspection, targets):
        selected_ids = {target.split("/")[1] for target in targets if target.startswith("subtasks/")}
        if "subtasks:unresolved" in targets:
            selected_ids.update(item["id"] for item in self.required if item["id"] not in self.safe_ids)
        required = [item for item in self.required if not selected_ids or item["id"] in selected_ids]
        refs = {ref for item in required for ref in item["spec_refs"]}
        blocks = [item for item in self.source_blocks if item["block_id"] in refs]
        return self.context + "\nRequired identities:\n" + json.dumps(required, ensure_ascii=False) + "\nRelevant specification blocks:\n" + json.dumps(blocks, ensure_ascii=False)

    def get(self, payload, target):
        if target == "subtasks:unresolved":
            return [item for item in payload["subtasks"] if isinstance(item, dict) and not self._safe_item(item)]
        if target == "subtasks":
            return payload.get("subtasks")
        parts = target.split("/")
        matches = [item for item in payload["subtasks"] if isinstance(item, dict) and item.get("id") == parts[1]]
        if len(matches) != 1:
            raise ValueError("Subtask patch identity must resolve exactly once")
        return matches[0].get(parts[2]) if len(parts) == 3 else matches[0]

    def set(self, payload, target, replacement):
        if target == "subtasks:unresolved":
            expected_ids = [item["id"] for item in self.required]
            unresolved = set(expected_ids) - self.safe_ids
            if not isinstance(replacement, list) or not all(isinstance(item, dict) and isinstance(item.get("id"), str) for item in replacement):
                raise ValueError("Identity repair must return a list of identified subtasks")
            ids = [item["id"] for item in replacement]
            if len(set(ids)) != len(ids) or set(ids) != unresolved:
                raise ValueError("Identity repair must cover exactly the unresolved required IDs")
            items = payload.get("subtasks")
            by_id = {item["id"]: item for item in items if self._safe_item(item)} if isinstance(items, list) else {}
            by_id.update({item["id"]: item for item in replacement})
            payload["subtasks"] = [by_id[unit] for unit in expected_ids]
            return
        if target == "subtasks":
            payload["subtasks"] = replacement
            return
        parts = target.split("/")
        matches = [i for i, item in enumerate(payload["subtasks"]) if isinstance(item, dict) and item.get("id") == parts[1]]
        if len(matches) != 1:
            raise ValueError("Subtask patch identity must resolve exactly once")
        if len(parts) == 3:
            payload["subtasks"][matches[0]][parts[2]] = replacement
        else:
            if not isinstance(replacement, dict) or replacement.get("id") != parts[1]:
                raise ValueError("Subtask patch must preserve its identity")
            payload["subtasks"][matches[0]] = replacement


class SubtaskCodeRepairAdapter(JsonRepairAdapter):
    def __init__(self, *, task_id, module, subtask, context, validator, contract_validator):
        super().__init__(SubtaskCodeArtifact, context)
        self.module = module
        self.locked = dict(task_id=task_id, module=module, subtask_id=subtask.id, target=subtask.target, spec_refs=list(subtask.spec_refs))
        self.validator = validator
        self.contract_validator = contract_validator

    def normalize(self, payload):
        changes = []
        for key, expected in self.locked.items():
            if payload.get(key) != expected:
                payload[key] = expected
                changes.append(f"Assembled authoritative {key}")
        return payload, changes

    def inspect(self, raw):
        result = super().inspect(raw)
        if result.candidate is None:
            return result
        if result.artifact is None and isinstance(result.candidate.get("code"), str):
            partial = SimpleNamespace(**self.locked, code=result.candidate["code"], timing_obligation_ids=result.candidate.get("timing_obligation_ids", []))
            for error in self.validator(partial):
                path = "timing_obligation_ids" if "timing_obligation_ids" in error else "code"
                result.issues.append(ArtifactIssue(path, "fragment_constraint", error, category="structure", unit_id=self.locked["subtask_id"]))
        contract = result.candidate.get("contract")
        if contract is None:
            result.issues.append(ArtifactIssue("contract", "missing_required_field", "Generated fragments require an explicit contract", expected=self.model_type.model_json_schema()["$defs"]["FragmentContract"]))
        elif isinstance(contract, dict):
            for key in ("writes", "reads", "clocking", "reset_behavior", "hold_behavior", "latency", "assumptions"):
                if key not in contract:
                    result.issues.append(ArtifactIssue(f"contract.{key}", "missing_required_field", f"Declare {key} explicitly; empty lists must be []"))
                elif key in {"clocking", "reset_behavior", "hold_behavior", "latency"} and isinstance(contract[key], str) and not contract[key].strip():
                    result.issues.append(ArtifactIssue(f"contract.{key}", "empty_contract_field", f"Contract {key} must contain an explicit statement"))
        return result

    def semantic_issues(self, artifact):
        issues = []
        for error in self.validator(artifact):
            path = "timing_obligation_ids" if "timing_obligation_ids" in error else "code"
            issues.append(ArtifactIssue(path, "fragment_constraint", error, category="structure", unit_id=artifact.subtask_id))
        issues.extend(self.contract_validator(artifact))
        return issues

    def targets(self, inspection):
        if inspection.candidate is None:
            return {"$": {"original": None, "expected": self.model_type.model_json_schema(), "identity": self.locked}}
        keys = set()
        contract = inspection.candidate.get("contract")
        schema = self.model_type.model_json_schema()
        fields = schema["$defs"]["FragmentContract"]["properties"]
        for issue in inspection.issues:
            root = issue.path.split(".", 1)[0].split("[", 1)[0]
            if root == "contract" and isinstance(contract, dict) and issue.path.startswith("contract."):
                field = issue.path.split(".", 1)[1].split("[", 1)[0]
                keys.add(f"contract.{field}" if field in fields else "contract")
            else:
                keys.add(root)
        if "code" in keys:
            # Any new code needs a complete, current contract, including when
            # the original response omitted it altogether.
            keys.add("contract")
        if "contract" in keys:
            keys = {key for key in keys if not key.startswith("contract.")}
        allowed = {"code", "contract", "timing_obligation_ids", *(f"contract.{field}" for field in fields)}
        if not keys <= allowed:
            return {"$": {"original": inspection.candidate, "expected": schema, "identity": self.locked}}
        return {key: {
            "original": contract.get(key.split(".")[1]) if key.startswith("contract.") else inspection.candidate.get(key),
            "expected": fields[key.split(".")[1]] if key.startswith("contract.") else (
                schema["$defs"]["FragmentContract"] if key == "contract" else schema["properties"][key]),
        } for key in sorted(keys)}

    def merge(self, inspection, raw, targets):
        self.merge_normalizations = []
        fields = self.model_type.model_json_schema()["$defs"]["FragmentContract"]["properties"]
        allowed = {"$", "code", "contract", "timing_obligation_ids", *(f"contract.{field}" for field in fields)}
        if not set(targets) <= allowed:
            raise ValueError("Unknown Stage5 repair target")
        if ("$" in targets and len(targets) > 1) or ("contract" in targets and any(key.startswith("contract.") for key in targets)):
            raise ValueError("Overlapping Stage5 repair targets")
        payload = strict_json(raw)
        changes = []
        if isinstance(payload, dict) and "patches" not in payload:
            # Only absent identity fields are harmless compatibility differences.
            # Explicitly wrong values must not be hidden by normalize().
            for key, expected in self.locked.items():
                if key not in payload:
                    payload[key] = copy.deepcopy(expected)
                    changes.append(f"Legacy full-object repair: restored authoritative {key}")
                elif payload[key] != expected:
                    raise ValueError(f"Full-object repair changed identity field: {key}")
            changes.append("Accepted legacy full-object repair with unchanged untargeted fields")
        candidate = super().merge(inspection, payload, targets)
        self.merge_normalizations = changes
        return candidate

    def get(self, payload, target):
        if target.startswith("contract."):
            return payload["contract"][target.split(".")[1]]
        return super().get(payload, target)

    def set(self, payload, target, replacement):
        if target.startswith("contract."):
            payload["contract"][target.split(".")[1]] = replacement
        else:
            super().set(payload, target, replacement)

    def context_for(self, inspection, targets):
        context = self.context
        if any(key == "contract" or key.startswith("contract.") for key in targets) and "code" not in targets:
            context += "\nThe code is fixed. Repair only its contract:\n" + str(inspection.candidate.get("code", ""))
        if "contract" in targets or "contract.writes" in targets:
            context += (
                "\nreplacement is the COMPLETE requested value, not an append/delta. "
                "contract.writes must cover every reliably identified assignment target in the code, "
                "including output signals and internal signals in continuous, combinational and sequential assignments. "
                "The diagnostics' expected list covers known assignment targets; the message lists only missing signals."
                " Include function return variables and function-local assignments, even if the fragment only declares helpers. "
                "For contract.writes, replacement must be a JSON array of strings such as [\"xtime\"], not a schema object. "
                "Do not copy schema properties such as items/type/title into the replacement value."
            )
        return context
