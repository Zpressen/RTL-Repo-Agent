from __future__ import annotations

import re

from .local_repair import ArtifactIssue, RepairInspection, checked_patches
from .skeleton_doc import inspect_module_skeleton_doc, scan_doc_regions, _match_field_line


class SkeletonRepairAdapter:
    def __init__(self, *, expected_module, expected_file_path, source_refs, context, example, quality_validator, partial_validator=None):
        self.arguments = dict(expected_module=expected_module, expected_file_path=expected_file_path, source_refs=source_refs)
        self.module = expected_module
        self.context = context
        self.example = example
        self.quality_validator = quality_validator
        self.partial_validator = partial_validator
        self.result = None

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
            return {"document": {"original": inspection.candidate, "expected": self.example}}
        targets = {}
        for issue in inspection.issues:
            section = issue.section
            if not section:
                return {"document": {"original": inspection.candidate, "expected": self.example}}
            block_target = f"Behavioral Overlay/block:{issue.unit_id}"
            target = block_target if issue.unit_id and block_target in ranges and issue.code != "invalid_reference" else section
            targets[target] = {}
        # A section replacement subsumes its block replacements.
        if "Behavioral Overlay" in targets:
            targets = {key: value for key, value in targets.items() if not key.startswith("Behavioral Overlay/block:")}
        example_regions, _ = scan_doc_regions(self.example)
        examples = {r.name: self.example[r.body_start:r.end] for r in example_regions}
        for target in targets:
            start, end = ranges.get(target, (0, 0))
            targets[target] = {
                "original": inspection.candidate[start:end] if target in ranges else None,
                "expected": examples.get(target.split("/block:")[0], ""),
            }
        return targets

    def context_for(self, inspection, targets):
        # Keep authoritative input sources and structural identities in view,
        # without retaining previous full generation responses in chat history.
        return self.context + "\nValid structural blocks:\n" + str(self.result.candidate.get("structural_blocks", []) if self.result else [])

    def merge(self, inspection, raw, targets):
        if isinstance(raw, str) and raw.lstrip().startswith("# MODULE_SKELETON_DOC"):
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
        for target, value in patches.items():
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
        full_doc = isinstance(raw, str) and raw.lstrip().startswith("# MODULE_SKELETON_DOC")
        previous_start = len(candidate) + 1
        for start, end, value in sorted(replacements, reverse=True):
            if end > previous_start:
                raise ValueError("Overlapping Markdown patches")
            separator = "" if full_doc or end == len(candidate) or value.endswith("\n") else "\n"
            candidate = candidate[:start] + value + separator + candidate[end:]
            previous_start = start
        candidate += "".join(added)
        if full_doc and candidate != raw:
            raise ValueError("Full-document repair changed untargeted text or headings")
        return candidate
