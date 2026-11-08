from __future__ import annotations

import re
import json
from collections import Counter
from copy import deepcopy

from pydantic import TypeAdapter

from ..schemas import BehaviorObligation
from .local_repair import ArtifactIssue, RepairInspection, checked_patches, strict_json, fingerprint
from .skeleton_doc import inspect_module_skeleton_doc, scan_doc_regions, _match_field_line


class SkeletonRepairAdapter:
    replay_saved_patch = True
    def __init__(self, *, expected_module, expected_file_path, source_refs, context, example, quality_validator, partial_validator=None, enhanced=False):
        self.arguments = dict(expected_module=expected_module, expected_file_path=expected_file_path, source_refs=source_refs)
        self.module = expected_module
        self.context = context
        self.example = example
        self.quality_validator = quality_validator
        self.partial_validator = partial_validator
        self.enhanced = enhanced
        self.result = None

    @staticmethod
    def _field_ranges(text, start):
        """Locate JSON values without rewriting other members of an obligation."""
        decoder = json.JSONDecoder()
        offset = start + 1
        fields = {}
        while True:
            while text[offset].isspace() or text[offset] == ",":
                offset += 1
            if text[offset] == "}":
                return fields
            key, length = decoder.raw_decode(text[offset:])
            offset += length
            while text[offset].isspace():
                offset += 1
            if text[offset] != ":":
                raise ValueError("Expected JSON member separator")
            offset += 1
            while text[offset].isspace():
                offset += 1
            _, length = decoder.raw_decode(text[offset:])
            fields[key] = (offset, offset + length)
            offset += length

    def inspect(self, raw):
        if not isinstance(raw, str):
            return RepairInspection("", issues=[ArtifactIssue("document", "invalid_document", "Expected Markdown text")])
        self.result = inspect_module_skeleton_doc(raw, **self.arguments)
        issues = list(self.result.issues)
        if self.partial_validator is not None:
            issues.extend(self.partial_validator(self.result.candidate))
        if self.result.artifact is not None:
            issues.extend(self.quality_validator(self.result.artifact))
        for issue in issues:
            if issue.line is None and issue.section:
                region = next((item for item in self.result.regions if item.name == issue.section), None)
                issue.line = region.line if region else len(self.result.normalized_doc.splitlines()) + 1
        return RepairInspection(self.result.normalized_doc, self.result.artifact, issues, self.result.normalizations)

    def _ranges(self, text):
        regions, _ = scan_doc_regions(text)
        ranges = {region.name: (region.body_start, region.end) for region in regions}
        behavioral = next((r for r in regions if r.name == "Behavioral Overlay"), None)
        if behavioral:
            body = text[behavioral.body_start:behavioral.end]
            subs, _ = scan_doc_regions(body, level=3)
            entries = []
            for sub in subs:
                if sub.name == "Behavioral Obligations":
                    begin, end = behavioral.body_start + sub.body_start, behavioral.body_start + sub.end
                    ranges["Behavioral Overlay/obligations"] = (begin, end)
                    match = re.search(r"```json\s*\n", text[begin:end])
                    if match:
                        offset = begin + match.end()
                        try:
                            while text[offset].isspace(): offset += 1
                            if text[offset] != "[": raise ValueError("Expected array")
                            offset += 1
                            decoded = []
                            while True:
                                while text[offset].isspace() or text[offset] == ",": offset += 1
                                if text[offset] == "]": break
                                item, length = json.JSONDecoder().raw_decode(text[offset:])
                                decoded.append((item.get("obligation_id"), offset, offset + length))
                                offset += length
                            for identity, start, finish in decoded:
                                if identity and sum(i == identity for i, _, _ in decoded) == 1:
                                    ranges[f"Behavioral Overlay/obligation:{identity}"] = (start, finish)
                                    for key, span in self._field_ranges(text, start).items():
                                        ranges[f"Behavioral Overlay/obligation:{identity}/field:{key}"] = span
                        except (ValueError, IndexError, AttributeError):
                            pass  # Malformed arrays are repaired as one subsection.
                if sub.name != "Block Behavioral Overlay":
                    continue
                offset = behavioral.body_start + sub.body_start
                for line in body[sub.body_start:sub.end].splitlines(keepends=True):
                    match = _match_field_line(line, "block_id")
                    if match:
                        entries.append((match[1], offset, behavioral.body_start + sub.end))
                    offset += len(line)
            for i, (block_id, start, end) in enumerate(entries):
                if i + 1 < len(entries) and entries[i + 1][1] < end:
                    end = entries[i + 1][1]
                if sum(item[0] == block_id for item in entries) == 1:
                    ranges[f"Behavioral Overlay/block:{block_id}"] = (start, end)
        return ranges

    def targets(self, inspection):
        ranges = self._ranges(inspection.candidate)
        if any(issue.code in {"invalid_header", "unclosed_fence", "duplicate_section", "invalid_document", "unknown_section"} for issue in inspection.issues):
            return {"document": self._document_target(inspection)}
        targets = {}
        local_state_repairs = {issue.unit_id for issue in inspection.issues
                               if issue.code in {"unknown_responsibility", "unauthorized_state_access"} and issue.unit_id}
        for issue in inspection.issues:
            section = issue.section
            if not section:
                return {"document": self._document_target(inspection)}
            if issue.code in {"state_commit_conflict", "uncovered_state_access"}:
                state = (issue.expected or {}).get("state")
                if state and any(o.get("obligation_id") in local_state_repairs
                                 and any(a.get("state_id") == state for a in o.get("state_accesses", []))
                                 for o in self.result.candidate.get("behavioral_obligations", [])):
                    # Parent/access errors can cause missing coverage. Repair
                    # their explicit fields first, then recheck all coverage.
                    continue
                related = [o for o in self.result.candidate.get("behavioral_obligations", [])
                           if o.get("parent_responsibility_id") == (issue.expected or {}).get("responsibility")
                           and any(a.get("state_id") == state and (issue.code != "state_commit_conflict"
                                   or a.get("role") in {"commit", "reset", "hold"})
                                   for a in o.get("state_accesses", []))]
                if related:
                    # Resolve ownership/role coverage in the affected entries,
                    # rather than rewriting every obligation in the module.
                    for obligation in related:
                        target = f"Behavioral Overlay/obligation:{obligation['obligation_id']}"
                        if target in ranges:
                            targets[target] = {}
                    if all(f"Behavioral Overlay/obligation:{o['obligation_id']}" in ranges for o in related):
                        continue
            if issue.code == "uncovered_constraint" and (issue.expected or {}).get("constraint"):
                constraint = issue.expected["constraint"]
                ru = issue.expected["responsibility"]
                identities = [o["obligation_id"] for o in self.result.candidate.get("behavioral_obligations", [])
                              if f"Behavioral Overlay/obligation:{o['obligation_id']}" in ranges]
                if identities:
                    target = f"Behavioral Overlay/constraint_coverage:{constraint}:{ru}"
                    targets[target] = {"replacement_type": "json_array", "constraint": constraint, "responsibility": ru,
                        "expected": {"type": "array", "minItems": 1, "uniqueItems": True,
                                     "items": {"type": "string", "enum": identities}},
                        "instructions": "Select existing obligation IDs whose final parent is this responsibility. "
                                        "The program adds only this constraint reference; it preserves other references."}
                    continue
            block_target = f"Behavioral Overlay/block:{issue.unit_id}"
            obligation_target = f"Behavioral Overlay/obligation:{issue.unit_id}"
            if issue.path.startswith("behavioral_obligations") and "Behavioral Overlay/obligations" in ranges:
                target = obligation_target if obligation_target in ranges else "Behavioral Overlay/obligations"
                field = {"unbound_source": "source_refs", "invalid_source": "source_refs",
                         "unauthorized_state_access": "state_accesses",
                         "unknown_constraint": "constraint_refs", "contract_drift": (issue.expected or {}).get("field")}.get(issue.code)
                field_target = f"{target}/field:{field}"
                if field and field_target in ranges:
                    target = field_target
            else:
                target = block_target if issue.unit_id and block_target in ranges and issue.code != "invalid_reference" else section
            targets[target] = {}
        # A section replacement subsumes its block replacements.
        if "Behavioral Overlay" in targets:
            targets = {key: value for key, value in targets.items() if not key.startswith("Behavioral Overlay/")}
        if "Behavioral Overlay/obligations" in targets:
            targets = {k: v for k, v in targets.items() if not k.startswith(("Behavioral Overlay/obligation:", "Behavioral Overlay/constraint_coverage:"))}
        for key in list(targets):
            if "/field:" not in key and "/obligation:" in key:
                targets = {k: v for k, v in targets.items() if not k.startswith(key + "/field:")}
        example_regions, _ = scan_doc_regions(self.example)
        examples = {r.name: self.example[r.body_start:r.end] for r in example_regions}
        for target in targets:
            if "/constraint_coverage:" in target:
                continue
            start, end = ranges.get(target, (0, 0))
            schema = BehaviorObligation.model_json_schema()
            kind = "markdown"
            if target == "Behavioral Overlay/obligations":
                expected, kind = TypeAdapter(list[BehaviorObligation]).json_schema(), "json_array"
                expected["minItems"] = 1
            elif "/field:" in target:
                field = target.split("/field:", 1)[1]
                expected = {**schema["properties"][field], "$defs": schema.get("$defs", {})}
                kind = "json_value"
            elif "/obligation:" in target:
                expected, kind = schema, "json_object"
            else:
                expected = examples.get(target.split("/block:")[0], "")
            targets[target] = {
                "original": inspection.candidate[start:end] if target in ranges else None,
                "expected": expected, "replacement_type": kind,
            }
            if kind == "markdown" and target == "Behavioral Overlay" and self._is_enhanced(inspection):
                targets[target]["obligations_schema"] = TypeAdapter(list[BehaviorObligation]).json_schema()
                targets[target]["instructions"] = "Retain the Behavioral Obligations subsection with a json-fenced array."
            if target.endswith("/field:source_refs"):
                identity = target.split("/obligation:", 1)[1].split("/field:", 1)[0]
                refs = [ref for issue in inspection.issues if issue.unit_id == identity
                        for ref in (issue.expected or {}).get("allowed_source_refs", [])]
                options = {"SRC_" + fingerprint(ref)[:24]: ref for ref in refs}
                if options:
                    targets[target].update(
                        expected={"type": "array", "minItems": 1, "uniqueItems": True,
                                  "items": {"type": "string", "enum": list(options)}},
                        source_evidence_options=options,
                        instructions="Return selected source evidence IDs as a JSON array. The program expands "
                                     "them into exact canonical source_refs. Do not retype quotes, lines or hashes. "
                                     "Select evidence supporting this obligation; do not change its behavior to pass validation.",
                    )
        return targets

    def _is_enhanced(self, inspection):
        return self.enhanced or inspection.candidate.lstrip().startswith("# MODULE_SKELETON_DOC v2")

    def _document_target(self, inspection):
        expected = self.example
        if self._is_enhanced(inspection):
            expected = {"header": "# MODULE_SKELETON_DOC v2",
                        "sections": ["Module Identity", "Module Frame", "Structural Skeleton", "Behavioral Overlay", "Decision Ledger"],
                        "behavioral_obligations_schema": TypeAdapter(list[BehaviorObligation]).json_schema(),
                        "instructions": "Inside Behavioral Overlay, include ### Behavioral Obligations with a json-fenced array."}
        return {"original": inspection.candidate, "expected": expected, "replacement_type": "markdown"}

    def context_for(self, inspection, targets):
        # Keep authoritative input sources and structural identities in view,
        # without retaining previous full generation responses in chat history.
        rules = ("For json_array/json_object/json_value targets, return native JSON values in replacement; "
                  "do not add Markdown fences or an obligations wrapper. The program handles serialization. "
                  "parent_responsibility_id must be an owned RU, never a non-owning constraint. "
                  "Apply non-owning constraints through constraint_refs on obligations of their applicable RUs. "
                  "Copy canonical source_refs exactly from the parent RU or referenced applicable constraints. "
                  "For source_refs targets with source_evidence_options, return an array of selected evidence IDs; "
                  "the program copies canonical source objects. Unknown IDs and foreign sources are rejected. "
                  "State accesses must be declared by the parent RU. Do not invent an upstream permission "
                  "or remove required behavior just to silence a diagnostic.")
        context = self.context if isinstance(self.context, dict) else {"source_context": self.context}
        return {**context, "structural_blocks": self.result.candidate.get("structural_blocks", []) if self.result else [],
                "current_obligations": self.result.candidate.get("behavioral_obligations", []) if self.result else [],
                "repair_rules": rules}

    def validate_transition(self, previous, proposed):
        """A repair may leave semantic errors, but must not introduce format errors."""
        def structural(inspection):
            return {(i.code, i.path, i.unit_id) for i in inspection.issues if i.category in {"format", "structure"}}
        if structural(proposed) - structural(previous):
            raise ValueError("Patch introduced new document format/schema errors; previous candidate preserved")
        if not structural(previous):
            before = {(i.code, i.path, i.unit_id) for i in previous.issues}
            after = {(i.code, i.path, i.unit_id) for i in proposed.issues}
            if after - before:
                introduced = [i for i in proposed.issues if (i.code, i.path, i.unit_id) not in before]
                if not self._only_exposed_parent_errors(previous, proposed, introduced):
                    messages = "; ".join(i.message for i in introduced)
                    raise ValueError("Patch introduced new validation errors; previous candidate preserved: " + messages)

    def _only_exposed_parent_errors(self, previous, proposed, introduced):
        """A corrected parent may reveal an error in otherwise unchanged data.

        Keep that progress for the next repair; this never authorizes publishing
        an invalid module, changing unrelated obligations, or adding bad data.
        """
        blocked = {i.unit_id for i in previous.issues if i.code == "unknown_responsibility" and i.unit_id}
        resolved = blocked - {i.unit_id for i in proposed.issues if i.code == "unknown_responsibility"}
        if not resolved:
            return False

        def entries(text):
            return {key.split("/obligation:", 1)[1]: strict_json(text[slice(*span)])
                    for key, span in self._ranges(text).items() if "/obligation:" in key and "/field:" not in key}
        old, new = entries(previous.candidate), entries(proposed.candidate)
        for issue in introduced:
            if issue.code in {"state_commit_conflict", "uncovered_state_access"} and not issue.unit_id:
                state = (issue.expected or {}).get("state")
                affected = {identity for identity, item in [*old.items(), *new.items()]
                            if any(a.get("state_id") == state for a in item.get("state_accesses", []))}
                if state and all(old.get(identity) == new.get(identity) for identity in affected - resolved) and any(identity in old and identity in new
                                 and old[identity].get("state_accesses") == new[identity].get("state_accesses")
                                 and old[identity].get("implementation_block_id") == new[identity].get("implementation_block_id")
                                 and any(a.get("state_id") == state for a in old[identity].get("state_accesses", []))
                                 for identity in resolved):
                    continue
                return False
            if issue.unit_id not in resolved or issue.unit_id not in old or issue.unit_id not in new:
                return False
            field = {"unbound_source": "source_refs", "contract_drift": (issue.expected or {}).get("field"),
                     "unauthorized_state_access": "state_accesses", "state_owner_conflict": "state_accesses",
                     "unknown_constraint": "constraint_refs"}.get(issue.code)
            if not field:
                return False
            left, right = old[issue.unit_id].get(field), new[issue.unit_id].get(field)
            if isinstance(left, list) and isinstance(right, list):
                # Binding lists have no behavioral ordering; retain multiplicity
                # while allowing an otherwise unchanged list to be reordered.
                left = sorted(json.dumps(v, sort_keys=True, ensure_ascii=False) for v in left)
                right = sorted(json.dumps(v, sort_keys=True, ensure_ascii=False) for v in right)
            if left != right:
                return False
        return True

    @staticmethod
    def _json_replacement(value, target):
        # Older callers may send a string containing JSON (possibly fenced).
        # It must still obey the exact target type and schema.
        original_text = value if isinstance(value, str) and not value.lstrip().startswith("```") else None
        if isinstance(value, str):
            value = strict_json(value)
        if target == "Behavioral Overlay/obligations":
            if not isinstance(value, list) or not value:
                raise ValueError("Obligations replacement must be a nonempty JSON array, without an object wrapper")
            TypeAdapter(list[BehaviorObligation]).validate_python(value)
            identities = [o["obligation_id"] for o in value]
            if len(set(identities)) != len(identities):
                raise ValueError("Obligation IDs must be unique")
            return "```json\n" + json.dumps(value, ensure_ascii=False, indent=2) + "\n```\n"
        if not isinstance(value, dict):
            raise ValueError("Obligation replacement must be a JSON object")
        BehaviorObligation.model_validate(value)
        if value.get("obligation_id") != target.split("/obligation:", 1)[1]:
            raise ValueError("Obligation patch must preserve its requested identity")
        return original_text if original_text is not None else json.dumps(value, ensure_ascii=False, indent=2)

    def merge(self, inspection, raw, targets):
        full_doc = isinstance(raw, str) and raw.lstrip().startswith("# MODULE_SKELETON_DOC")
        if full_doc:
            # Backward-compatible full-doc response: accept only byte-preserving edits
            # to the authorized bodies. The generated headings are never copied.
            incoming = self._ranges(raw)
            if set(targets) == {"document"}:
                return raw
            patches = {key: raw[slice(*incoming[key])] for key in targets if key in incoming}
            if set(patches) != set(targets):
                raise ValueError("Full-document repair did not contain every target")
        else:
            patches = checked_patches(raw, targets)
        if set(targets) == {"document"}:
            if not isinstance(patches["document"], str):
                raise ValueError("Document replacement must be Markdown text")
            return patches["document"]
        ranges = self._ranges(inspection.candidate)
        replacements = []
        added = []
        coverage = []
        for target, value in patches.items():
            original_value = value
            if "/constraint_coverage:" in target:
                spec = targets[target]
                if (not isinstance(value, list) or not value or not all(isinstance(v, str) for v in value)
                        or len(set(value)) != len(value) or not set(value) <= set(spec["expected"]["items"]["enum"])):
                    raise ValueError("Constraint coverage replacement must select known, unique obligation IDs")
                coverage.append((spec, value))
                continue
            if target == "Behavioral Overlay/obligations" or ("/obligation:" in target and "/field:" not in target):
                value = self._json_replacement(value, target)
            elif "/field:" in target:
                field = target.split("/field:", 1)[1]
                if isinstance(value, str) and (full_doc or BehaviorObligation.model_fields[field].annotation is not str):
                    value = strict_json(value)
                if field == "source_refs" and isinstance(value, list) and value and all(isinstance(v, str) for v in value):
                    options = targets[target].get("source_evidence_options", {})
                    if len(set(value)) != len(value) or any(identity not in options for identity in value):
                        raise ValueError("Source repair must select unique evidence IDs from this obligation's allowed sources")
                    value = [deepcopy(options[identity]) for identity in value]
                TypeAdapter(BehaviorObligation.model_fields[field].annotation).validate_python(value)
                value = json.dumps(value, ensure_ascii=False, indent=2)
            if full_doc:
                value = original_value  # Validated full-document bodies preserve their exact formatting.
            if not isinstance(value, str):
                raise ValueError("Markdown replacement must be text")
            headings, _ = scan_doc_regions(value)
            if headings or re.search(r"(?m)^#\s+MODULE_SKELETON_DOC", value):
                raise ValueError("A section/entry patch must not introduce document or section headings")
            if "/block:" in target:
                ids = [match[1] for line in value.splitlines() if (match := _match_field_line(line, "block_id"))]
                if ids != [target.split("/block:", 1)[1]] or re.search(r"(?m)^###\s", value):
                    raise ValueError("Overlay patch must preserve exactly its requested block identity")
            if target in ranges:
                replacements.append((*ranges[target], value))
            else:
                added.append(f"\n## {target}\n{value}\n")
        candidate = inspection.candidate
        previous_start = len(candidate) + 1
        for start, end, value in sorted(replacements, reverse=True):
            if end > previous_start:
                raise ValueError("Overlapping Markdown patches")
            separator = "" if full_doc or end == len(candidate) or value.endswith("\n") or candidate[end:end + 1].isspace() or candidate[end:end + 1] in {",", "]"} else "\n"
            candidate = candidate[:start] + value + separator + candidate[end:]
            previous_start = start
        candidate += "".join(added)
        if full_doc and candidate != raw:
            raise ValueError("Full-document repair changed untargeted text or headings")
        # Apply coverage selections after parent/source field edits. Every
        # selected obligation must actually belong to the requested RU now.
        for spec, identities in coverage:
            ranges = self._ranges(candidate)
            edits = []
            for identity in identities:
                target = f"Behavioral Overlay/obligation:{identity}"
                item = strict_json(candidate[slice(*ranges[target])])
                if item["parent_responsibility_id"] != spec["responsibility"]:
                    raise ValueError("Constraint coverage must select obligations of the applicable responsibility")
                refs = item.get("constraint_refs", [])
                if spec["constraint"] in refs:
                    continue
                refs = [*refs, spec["constraint"]]
                field_target = target + "/field:constraint_refs"
                if field_target in ranges:
                    edits.append((*ranges[field_target], json.dumps(refs, ensure_ascii=False)))
                else:
                    finish = ranges[target][1] - 1
                    edits.append((finish, finish, ', "constraint_refs": ' + json.dumps(refs, ensure_ascii=False)))
            for start, end, value in sorted(edits, reverse=True):
                candidate = candidate[:start] + value + candidate[end:]
        return candidate

    def apply_response(self, previous, raw, targets):
        """Try the whole transaction, then salvage independent obligation groups.

        Validate the complete envelope before any edit. Related fields of one
        obligation stay atomic. Each retained group passes whole-module checks
        and the same no-regression guard as the complete transaction.
        """
        self.last_patch_rejections = []
        def validate_edit(before, after, requested):
            self.validate_transition(before, after)
            source_units = {target.split("/obligation:", 1)[1].split("/field:", 1)[0]
                            for target in requested if target.endswith("/field:source_refs")}
            if any(issue.unit_id in source_units and issue.code in {"invalid_source", "unbound_source"}
                   for issue in after.issues):
                raise ValueError("Source field repair still contains invalid or unbound evidence; previous field preserved")
        try:
            proposed = self.inspect(self.merge(previous, raw, targets))
            validate_edit(previous, proposed, targets)
            return proposed
        except (ValueError, TypeError, KeyError, IndexError) as original_error:
            self.inspect(previous.candidate)
            # Unknown/duplicate/missing targets cannot authorize partial edits.
            patches = checked_patches(raw, targets)
            if any(i.category in {"format", "structure"} for i in previous.issues):
                raise original_error
            groups = {}
            for target in patches:
                if "/obligation:" not in target:
                    raise original_error
                group = target.split("/field:", 1)[0]
                groups.setdefault(group, []).append(target)
            if len(groups) < 2:
                raise original_error
            current = previous
            accepted = []
            for group, names in groups.items():
                try:
                    self.inspect(current.candidate)
                    fresh_targets = self.targets(current)
                    if any(name not in fresh_targets for name in names):
                        raise ValueError("Group targets are no longer independently authorized")
                    subset = {name: fresh_targets[name] for name in names}
                    response = {"patches": [{"target": name, "replacement": patches[name]} for name in names]}
                    proposed = self.inspect(self.merge(current, response, subset))
                    validate_edit(current, proposed, subset)
                    before = Counter((i.code, i.path, i.unit_id) for i in current.issues)
                    after = Counter((i.code, i.path, i.unit_id) for i in proposed.issues)
                    if proposed.candidate == current.candidate or not before - after:
                        raise ValueError("Independent repair group made no validated progress")
                    current = proposed
                    accepted.append(group)
                except (ValueError, TypeError, KeyError, IndexError) as exc:
                    self.last_patch_rejections.append({"targets": names, "reason": str(exc)})
                    self.inspect(current.candidate)
            if not accepted:
                raise original_error
            current.normalizations.append("Retained independent repairs: " + ", ".join(accepted))
            return current
