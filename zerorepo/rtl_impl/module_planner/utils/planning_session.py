"""Small persisted JSON conversation loop, inspired by pi's tool-result loop."""
from __future__ import annotations
from dataclasses import dataclass
from copy import deepcopy
import json
import re
from pydantic import ValidationError
from zerorepo.rpg_gen.base.llm_client import SystemMessage, UserMessage
from zerorepo.rpg_gen.base.llm_client.errors import LLMResponseTruncatedError
from .local_repair import ArtifactIssue, fingerprint, strict_json


@dataclass
class NodeResult:
    status: str
    artifact: object = None
    issues: list | None = None
    candidate: object = None


def ledger_scope(candidate, issues):
    """A ledger repair replaces complete RU/state entities, never field paths."""
    if not isinstance(candidate, dict):
        return {"full": True}
    groups = {"responsibilities": "responsibility_id", "state_objects": "state_id"}
    selected = {}
    for issue in issues:
        # Explicit locations identify the repair owner. References in a message
        # (dependency targets, state IDs, etc.) are context, not permission to
        # rewrite those entities.
        locations, mentions = [], []
        for group, key in groups.items():
            entries = candidate.get(group, [])
            if not isinstance(entries, list):
                return {"full": True}
            for index, entity in enumerate(entries):
                identity = entity.get(key) if isinstance(entity, dict) else None
                if not isinstance(identity, str) or not identity:
                    continue
                location = (group, key, identity)
                if (issue.unit_id == identity or issue.path.startswith(f"{group}[{identity}]")
                        or issue.path.startswith(f"{group}[{index}]")):
                    locations.append(location)
                elif re.search(r"(?<![\w])" + re.escape(identity) + r"(?![\w])", issue.message):
                    mentions.append(location)
        explicit = bool(issue.unit_id) or any(issue.path.startswith(group + "[") for group in groups)
        targets = locations if explicit else mentions
        if not targets:
            return {"full": True}
        for group, key, identity in targets:
            entries = candidate[group]
            if sum(isinstance(item, dict) and item.get(key) == identity for item in entries) != 1:
                return {"full": True}
            ids = selected.setdefault(group, {"identity": key, "ids": []})["ids"]
            if identity not in ids:
                ids.append(identity)
    return {"entities": selected} if selected else {"full": True}


def entity_scope(candidate, issues):
    """Find whole design entities; field locations are diagnostics only."""
    if not isinstance(candidate, dict):
        return {"full": True}
    obligations = candidate.get("behavioral_obligations", [])
    blocks = candidate.get("structural_blocks", [])
    ids = {issue.unit_id for issue in issues if issue.unit_id}
    parents = set()
    sections = set()
    for issue in issues:
        expected = issue.expected if isinstance(issue.expected, dict) else {}
        identifiable = bool(issue.unit_id)
        for group, key in (("behavioral_obligations", "obligation_id"), ("structural_blocks", "block_id")):
            match = re.match(r"^" + group + r"\[(\d+)\]", issue.path)
            entries = candidate.get(group)
            if match and isinstance(entries, list) and int(match[1]) < len(entries):
                entry = entries[int(match[1])]
                if isinstance(entry, dict) and isinstance(entry.get(key), str):
                    ids.add(entry[key])
                    identifiable = True
        if issue.code in {"uncovered_responsibility", "uncovered_constraint", "uncovered_state_access", "unmapped_block"}:
            parents.add(expected.get("responsibility", ""))
            identifiable = True
        if issue.code == "state_commit_conflict":
            state = expected.get("state")
            ids.update(o.get("obligation_id") for o in obligations if isinstance(o, dict)
                       and any(a.get("state_id") == state for a in o.get("state_accesses", [])))
            identifiable = True
        for section in ("module_frame", "module_behavior", "decision_ledger"):
            if issue.path.startswith(section):
                sections.add(section)
                identifiable = True
        if issue.code == "generation_cycle":
            ids.update(b.get("block_id") for b in blocks if isinstance(b, dict))
            identifiable = True
        if not identifiable:
            return {"full": True}
    parents.discard("")
    return {"obligation_ids": [o["obligation_id"] for o in obligations if isinstance(o, dict)
                              and (o.get("obligation_id") in ids or o.get("parent_responsibility_id") in parents)],
            "responsibility_ids": sorted(parents),
            "block_ids": [b["block_id"] for b in blocks if isinstance(b, dict) and b.get("block_id") in ids],
            "sections": sorted(sections)}


def merge_entities(candidate, response, scope):
    if scope.get("full"):
        return deepcopy(response)
    merged = deepcopy(candidate)
    if "entities" in scope:
        for group, replacements in response.items():
            if candidate.get(group) == replacements:
                continue
            definition = scope["entities"].get(group)
            if definition is None or not isinstance(replacements, list):
                raise ValueError(f"Untargeted ledger section: {group}")
            key = definition["identity"]
            originals = {item[key]: item for item in candidate[group]}
            seen = set()
            for item in replacements:
                identity = item.get(key) if isinstance(item, dict) else None
                if identity in seen or identity not in originals:
                    raise ValueError(f"Unknown or duplicate ledger entity: {identity}")
                seen.add(identity)
                if identity not in definition["ids"] and item != originals[identity]:
                    raise ValueError(f"Untargeted ledger entity: {identity}")
                originals[identity] = deepcopy(item)
            merged[group] = list(originals.values())
        return merged
    allowed = {"behavioral_obligations", "structural_blocks", "evidence_binding_requests", *scope["sections"]}
    for key, value in response.items():
        if key not in allowed:
            if candidate.get(key) == value:
                continue
            raise ValueError(f"Untargeted design section: {key}")
        if key in {"behavioral_obligations", "structural_blocks"}:
            identity = "obligation_id" if key == "behavioral_obligations" else "block_id"
            permitted = set(scope["obligation_ids"] if key == "behavioral_obligations" else scope["block_ids"])
            if not isinstance(value, list) or any(not isinstance(item, dict) or not isinstance(item.get(identity), str) for item in value):
                raise ValueError(f"Expected identified {key} entities")
            ids = [item[identity] for item in value]
            if len(set(ids)) != len(ids):
                raise ValueError("Duplicate repair entity")
            by_id = {item[identity]: item for item in merged[key]}
            for item in value:
                name = item[identity]
                if name not in permitted:
                    if by_id.get(name) == item:
                        continue
                    if not (key == "behavioral_obligations" and name not in by_id and item.get("parent_responsibility_id") in scope["responsibility_ids"]):
                        raise ValueError(f"Untargeted design entity: {name}")
                by_id[name] = item
            merged[key] = list(by_id.values())
        else:
            merged[key] = deepcopy(value)
    return merged


class PlanningSession:
    def __init__(self, agent):
        self.agent = agent
        self.executor = agent.llm_client.executor

    def execute(self, *, module, prompt, context, validate, operation="design_json", scope_builder=entity_scope, images=None,
                repair_context=None, repair_prompt=None, context_view=None, prompt_view=None, candidate_view=None):
        def inputs():
            return {"prompt": prompt, "context": context, "system": self.agent.system_role, "images": images}
        with self.executor.node(self.agent.stage_name, module, operation, inputs()) as node:
            candidate = node.state.candidate
            issues = []
            feedback = [ArtifactIssue(**issue) for issue in node.state.feedback]
            feedback_scope = node.state.targets
            stagnant = 0
            # A response is journaled by RequestExecutor before returning. Recover
            # that narrow crash window under the original scope and full checks.
            if node.restored and node.state.last_response is not None:
                try:
                    pending = strict_json(node.state.last_response)
                    if isinstance(pending, dict):
                        pending.pop("_public_start", None)
                        pending.pop("_public_progress", None)
                    proposed = merge_entities(candidate, pending, node.state.targets or {"full": True})
                    _, replay_issues = validate(proposed)
                    if not any(i.category in {"format", "structure"} for i in replay_issues):
                        candidate = proposed
                except (ValueError, TypeError, KeyError):
                    pass
            while node.attempts < self.executor.max_attempts and node.remaining > 0:
                if candidate is not None:
                    artifact, issues = validate(candidate)
                    node.rebind(inputs())
                    if not issues:
                        node.inspect(candidate)
                        node.state.status = "completed"
                        node.state.last_error = ""
                        node.state.feedback = []
                        node.save()
                        return NodeResult("validated", artifact, [], candidate)
                scope = scope_builder(candidate, issues)
                if scope != feedback_scope:
                    # Revalidation may correct an earlier repair scope. Do not
                    # tell the model that edits now explicitly allowed are still
                    # forbidden by a stale response rejection from that scope.
                    feedback = []
                node.inspect(candidate, issues, scope)
                # Checkpoint identity always binds the complete authoritative
                # context. A repair may omit redundant derived context while
                # retaining the sources and contracts needed for its entities.
                request_context = context_view(context, scope) if context_view else context
                if candidate is not None and issues and repair_context:
                    request_context = repair_context(request_context, scope, issues + feedback)
                # Some stages embed their context in the original prompt rather
                # than INPUT. Project that context too, without changing the
                # checkpoint identity or discarding an interrupted candidate.
                request_prompt = prompt_view(scope) if prompt_view else prompt
                if candidate is not None and issues and repair_prompt:
                    request_prompt = repair_prompt(scope)
                serialized_context = json.dumps(request_context, ensure_ascii=False, separators=(",", ":"))
                request = request_prompt + "\nINPUT:\n" + serialized_context
                serialized_validation = ""
                if candidate is not None or feedback:
                    shown_candidate = candidate_view(candidate, scope) if candidate is not None and candidate_view else candidate
                    serialized_validation = json.dumps({"candidate": shown_candidate, "issues": [i.to_dict() for i in issues + feedback], "repair_scope": scope}, ensure_ascii=False, separators=(",", ":"))
                    request += "\nVALIDATION RESULT:\n" + serialized_validation
                    request += "\nReturn only the requested replacement entities using the SAME design schema. Omitted entities are preserved. Never remove required behavior to satisfy validation."
                node.state.prompt_budget = {"context_sections": {
                    key: len(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
                    for key, value in request_context.items()} if isinstance(request_context, dict) else {}, "components": {
                    "system_chars": len(self.agent.system_role), "base_prompt_chars": len(request_prompt),
                    "context_chars": len(serialized_context), "validation_chars": len(serialized_validation),
                    "framing_chars": len(request) - len(request_prompt) - len(serialized_context) - len(serialized_validation)}}
                memory = self.agent._create_stage_memory()
                memory.add_message(SystemMessage(content=self.agent.system_role))
                memory.add_message(UserMessage(content=request))
                self.agent._trace_event("input", {"module": module, "operation": operation, "prompt": request})
                before = fingerprint({"candidate": candidate, "issues": [i.to_dict() for i in issues]})
                feedback = []
                try:
                    node.state.content_rounds += 1
                    node.save()
                    raw = self.agent._complete_public(memory=memory, images=images, module=module, attempt=node.state.content_rounds)
                    self.agent._trace_event("response", {"module": module, "operation": operation, "raw": raw})
                    response = strict_json(raw)
                    if isinstance(response, dict):
                        response.pop("_public_start", None)
                        response.pop("_public_progress", None)
                    if not isinstance(response, dict):
                        raise ValueError("Expected a JSON design object")
                    proposed = merge_entities(candidate, response, scope)
                    artifact, proposed_issues = validate(proposed)
                    node.rebind(inputs())
                    # Schema-invalid proposals do not replace a saved design.
                    prior_schema = {(i.code, i.path) for i in issues if i.category in {"format", "structure"}}
                    next_schema = {(i.code, i.path) for i in proposed_issues if i.category in {"format", "structure"}}
                    if candidate is not None and next_schema and not (next_schema < prior_schema):
                        feedback = proposed_issues
                    else:
                        candidate, issues = proposed, proposed_issues
                    node.inspect(candidate, issues, scope_builder(candidate, issues))
                    if not issues and not feedback:
                        node.state.status = "completed"
                        node.state.last_error = ""
                        node.state.feedback = []
                        node.save()
                        return NodeResult("validated", artifact, [], candidate)
                except (ValueError, TypeError, KeyError, ValidationError, LLMResponseTruncatedError) as exc:
                    feedback = [ArtifactIssue("response", "invalid_response", str(exc), stage=self.agent.stage_name, module=module)]
                    if candidate is None:
                        issues = feedback
                    node.inspect(candidate, issues, scope)
                node.state.feedback = [issue.to_dict() for issue in feedback]
                feedback_scope = scope
                node.save()
                after = fingerprint({"candidate": candidate, "issues": [i.to_dict() for i in issues]})
                stagnant = stagnant + 1 if before == after else 0
                self.agent.logger.info("[%s] %s: %d validation issue(s), API attempts %d/%d", self.agent.stage_name, module, len(issues), node.attempts, self.executor.max_attempts)
                if stagnant >= 2:
                    break
            node.inspect(candidate, issues, scope_builder(candidate, issues))
            if stagnant < 2:
                from .execution import PlanningBudgetExceeded
                raise PlanningBudgetExceeded(
                    f"Planning node budget exhausted: {node.attempts}/{self.executor.max_attempts} API attempts, "
                    f"{max(0, node.remaining):.1f}s remaining; candidate and {len(issues)} issues retained",
                    stage=self.agent.stage_name, module=module, operation=operation)
            node.state.status = "needs_repair"
            node.state.last_error = "Planning node requires repair: candidate and issue set unchanged for two responses"
            node.save()
            # Surface rejected responses as well as the candidate's domain
            # errors. Otherwise a broken repair protocol looks like a model
            # repeatedly ignoring a valid correction request.
            return NodeResult("needs_repair", issues=issues + feedback, candidate=candidate)
