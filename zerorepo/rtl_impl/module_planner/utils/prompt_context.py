"""Lossless, prompt-only sharing of repeated evidence and structured context."""
from __future__ import annotations

from collections import Counter
import copy
import hashlib
import json


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      default=lambda item: item.model_dump(mode="json") if hasattr(item, "model_dump") else str(item))


def share_repair_context(payload):
    """Retain every input value, sharing repeated large subtrees and strings.

    The caller's candidate, targets and diagnostics remain authoritative and
    untouched. References exist only in the model's reading context.
    """
    from .evidence import deduplicate_evidence
    projected = deduplicate_evidence(copy.deepcopy(payload))
    counts = Counter()
    values = {}

    def inventory(item):
        if isinstance(item, (dict, list, str)):
            text = encode(item)
            if len(text) >= 256:
                identity = "CTX_" + hashlib.sha256(text.encode()).hexdigest()[:24]
                counts[identity] += 1
                values[identity] = item
            children = item.values() if isinstance(item, dict) else item if isinstance(item, list) else ()
            for child in children:
                inventory(child)

    inventory(projected)
    shared = {}

    def visit(item, *, defining=None):
        if not isinstance(item, (dict, list, str)):
            return item
        text = encode(item)
        identity = "CTX_" + hashlib.sha256(text.encode()).hexdigest()[:24] if len(text) >= 256 else None
        if identity != defining and counts[identity] > 1:
            if identity not in shared:
                shared[identity] = None
                shared[identity] = visit(values[identity], defining=identity)
            return {"context_ref": identity}
        if isinstance(item, dict):
            return {key: visit(value) for key, value in item.items()}
        return [visit(value) for value in item] if isinstance(item, list) else item

    return {"inputs": visit(projected), "shared_values": shared}


SHARED_INPUT_MARKER = "Complete input sections, evidence and shared values:\n"


def shared_input_prompt(instructions, inputs):
    """Serialize a structured view without dropping any logical input section.

    Keep the original expanded prompt as the checkpoint identity. This is only
    its wire representation; the artifact schema and source authority stay fixed.
    """
    return (instructions + "\n\nInput sections are provided as structured JSON below. "
            "Read context_ref through shared_values and evidence_ref through inputs.evidence; "
            "references are reading aids only. Resolve them before using any value. "
            "All original input sections, including the complete Markdown skeleton, are retained. "
            "Return the required artifact JSON with complete canonical values, never reference wrappers.\n\n"
            + SHARED_INPUT_MARKER + encode(share_repair_context(inputs)))


def native_target_originals(targets):
    """Avoid JSON strings containing escaped copies of JSON replacement values."""
    from .local_repair import strict_json
    projected = copy.deepcopy(targets)
    for target in projected.values():
        if target.get("replacement_type") in {"json_array", "json_object", "json_value"}:
            try:
                target["original"] = strict_json(target["original"])
            except (ValueError, TypeError, KeyError):
                pass  # A malformed candidate must remain visible, verbatim.
    return projected
