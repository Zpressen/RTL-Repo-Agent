"""Prompt projections retain canonical sources, repair authority and ownership."""
from copy import deepcopy
import json

import pytest

from zerorepo.rtl_impl.module_planner.utils.planning_session import merge_entities
from zerorepo.rtl_impl.module_planner.utils.skeleton_json import (
    design_context, design_candidate_context, repair_context, design_repair_context,
)
from zerorepo.rtl_impl.module_planner.utils.local_repair import ArtifactIssue


def test_module_catalog_keeps_all_referenced_sources_and_their_sections():
    entries = [
        {"id": "EV_MAIN", "file_id": "F1", "section_id": "SEC1", "text": "required effect"},
        {"id": "EV_NEIGHBOR", "file_id": "F1", "section_id": "SEC1", "text": "same-section guard"},
        {"id": "EV_STATE", "file_id": "F1", "section_id": "SEC2", "text": "state reset"},
        {"id": "EV_BOUNDARY", "file_id": "F2", "section_id": "SEC3", "text": "boundary transfer"},
        {"id": "EV_OTHER", "file_id": "F3", "section_id": "SEC4", "text": "unrelated multiplier"},
    ]
    context = {"assigned": {"responsibilities": [{"source_evidence_ids": ["EV_MAIN"]}],
                            "state_objects": [{"source_evidence_ids": ["EV_STATE"]}]},
               "boundary_contracts": [{"source_refs": [{"evidence_ref": "EV_BOUNDARY"}]}],
               "evidence_catalog": {"entries": entries, "files": {"F1": "spec", "F2": "boundary", "F3": "other"},
                                    "sections": {"SEC1": "A", "SEC2": "B", "SEC3": "C", "SEC4": "D"}},
               "schema": {"type": "object"}}
    original = deepcopy(context)
    wire = design_context(context, {})
    assert context == original
    assert wire["evidence_catalog"]["entries"] == entries[:4]
    assert wire["assigned"] == context["assigned"]
    assert wire["boundary_contracts"] == context["boundary_contracts"]
    assert "F3" not in wire["evidence_catalog"]["files"]
    assert "SEC4" not in wire["evidence_catalog"]["sections"]
    # The production repair receives the original authoritative context, so
    # upstream source-only supplements can still reference the entire catalog.
    assert repair_context(context, {})["evidence_catalog"] == original["evidence_catalog"]


def test_missing_context_source_is_an_error_instead_of_silently_omitted():
    with pytest.raises(ValueError, match="EV_MISSING"):
        design_context({"assigned": {"source_evidence_ids": ["EV_MISSING"]},
                        "evidence_catalog": {"entries": []}}, {})


def test_repair_view_preserves_state_commit_index_but_not_unrelated_effect_prose():
    candidate = {"module_frame": "module m(); endmodule", "structural_blocks": [{"block_id": "B1"}],
                 "behavioral_obligations": [
                     {"obligation_id": "O1", "parent_responsibility_id": "R1", "required_effect": "fix this effect",
                      "state_accesses": [{"state_id": "S1", "role": "commit"}], "implementation_block_id": "B1"},
                     {"obligation_id": "O2", "parent_responsibility_id": "R2", "required_effect": "unrelated prose " * 1000,
                      "state_accesses": [{"state_id": "S1", "role": "hold"}], "implementation_block_id": "B1",
                      "source_evidence_ids": ["EV_OTHER"]}]}
    original = deepcopy(candidate)
    scope = {"obligation_ids": ["O1"], "responsibility_ids": [], "block_ids": [], "sections": []}
    wire = design_candidate_context(candidate, scope)
    assert candidate == original
    assert wire["behavioral_obligations"] == candidate["behavioral_obligations"][:1]
    assert wire["preserved_obligation_index"][0]["state_accesses"] == [{"state_id": "S1", "role": "hold"}]
    assert wire["preserved_obligation_index"][0]["implementation_block_id"] == "B1"
    assert wire["module_frame"] == candidate["module_frame"]
    assert wire["structural_blocks"] == candidate["structural_blocks"]
    assert "unrelated prose" not in json.dumps(wire)
    response = {"behavioral_obligations": [{**candidate["behavioral_obligations"][0], "required_effect": "corrected"}]}
    merged = merge_entities(candidate, response, scope)
    assert merged["behavioral_obligations"][1] == original["behavioral_obligations"][1]
    with pytest.raises(ValueError, match="Untargeted design section"):
        merge_entities(candidate, {"preserved_obligation_index": []}, scope)
    assert design_candidate_context(candidate, {"full": True}) == original


def test_missing_responsibility_expands_all_its_existing_obligations():
    candidate = {"behavioral_obligations": [
        {"obligation_id": "O1", "parent_responsibility_id": "R1", "required_effect": "mandatory"}]}
    view = design_candidate_context(candidate, {"obligation_ids": [], "responsibility_ids": ["R1"]})
    assert view["behavioral_obligations"] == candidate["behavioral_obligations"]
    assert not view.get("preserved_obligation_index")


def test_only_source_feedback_broadens_the_catalog():
    context = {"assigned": {"source_evidence_ids": ["EV_A"]}, "evidence_catalog": {"entries": [
        {"id": "EV_A", "file_id": "F", "section_id": "A", "text": "required"},
        {"id": "EV_B", "file_id": "F", "section_id": "B", "text": "other"}]}}
    ordinary = [ArtifactIssue("behavioral_obligations", "unknown_block", "Fix block ID")]
    source = [ArtifactIssue("behavioral_obligations", "unbound_source", "Select inherited sources")]
    assert len(design_repair_context(context, {}, ordinary)["evidence_catalog"]["entries"]) == 1
    assert len(design_repair_context(context, {}, source)["evidence_catalog"]["entries"]) == 2


def test_split_table_is_preserved_in_full_within_the_selected_section(tmp_path):
    from types import SimpleNamespace
    from zerorepo.rtl_impl.module_planner.utils.evidence import EvidenceRegistry
    path = tmp_path / "spec.md"
    table = "# Full lookup\n\n" + "\n".join(f"| {i} | {255-i} | lookup value |" for i in range(256))
    path.write_text(table + "\n\n# Unrelated\nother behavior\n")
    registry = EvidenceRegistry(SimpleNamespace(source_specs=[SimpleNamespace(path=str(path), markdown=path.read_text())]))
    identity = next(key for key, ref in registry.entries.items() if "| 0 |" in ref.quote)
    assert not all(f"| {i} |" in registry.entries[identity].quote for i in range(256))
    context = {"assigned": {"source_evidence_ids": [identity]}, "evidence_catalog": registry.prompt_catalog()}
    view = design_context(context, {})
    text = "\n".join(entry["text"] for entry in view["evidence_catalog"]["entries"])
    assert all(f"| {i} |" in text for i in range(256))
    assert "other behavior" not in text


def test_selected_provenance_catalog_preserves_exact_quote_and_location(tmp_path):
    from test_planning_harness import make_draft
    _, _, registry, draft = make_draft(tmp_path)
    identity = draft["responsibilities"][0]["source_evidence_ids"][0]
    catalog = registry.prompt_catalog([identity])
    assert len(catalog["entries"]) == 1
    entry, source = catalog["entries"][0], registry.entries[identity]
    assert entry["id"] == identity and entry["text"] == source.quote
    assert entry["lines"] == [source.start_line, source.end_line]
    assert catalog["files"][entry["file_id"]] == source.source_file
    assert catalog["sections"][entry["section_id"]] == source.section_path
    with pytest.raises(ValueError, match="Unknown evidence IDs"):
        registry.prompt_catalog(["EV_MISSING"])


def test_stage5_task_view_keeps_contracts_and_shares_repeated_originals():
    from zerorepo.rtl_impl.module_planner.utils.stage5_sources import task_prompt_context
    source = {"source_file": "/spec.md", "quote": "mandatory original " * 1000,
              "section_path": "Reset", "start_line": 5, "end_line": 5, "content_hash": "hash"}
    payload = {"id": "T", "obligation_ids": ["O"], "supporting_obligation_ids": [],
        "task_contract": {"support_only": False, "state_accesses": [{"state_id": "S", "role": "commit"}],
            "obligations": [{"obligation_id": "O", "required_effect": "update exactly", "source_refs": [source]}],
            "state_objects": [{"state_id": "S", "owner_responsibility_id": "R", "source_refs": [source]}]}}
    original = deepcopy(payload)
    view = task_prompt_context(payload)
    assert payload == original
    def expand(item):
        if isinstance(item, dict):
            if set(item) == {"evidence_ref"}:
                return view["evidence"][item["evidence_ref"]]
            return {k: expand(v) for k, v in item.items() if k not in {"evidence", "source_context"}}
        return [expand(v) for v in item] if isinstance(item, list) else item
    assert expand(view) == original
    assert len(json.dumps(view)) < len(json.dumps(payload))
