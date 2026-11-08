"""Bound long fact requests while preserving original evidence and resume state."""
from copy import deepcopy
import json

import pytest

from test_rtl_module_planner import make_task_input, make_stage1_fact_payload
from test_planning_harness import RaisingBackend
from zerorepo.rpg_gen.base.llm_client.errors import LLMRequestTimeoutError
from zerorepo.rtl_impl.module_planner import PlannerRunner
from zerorepo.rtl_impl.module_planner.agents import Stage1Agent
from zerorepo.rtl_impl.module_planner.schemas import Stage1ContractsArtifact
from zerorepo.rtl_impl.module_planner.utils import PlannerLLMClient
from zerorepo.rtl_impl.module_planner.utils.md_loader import load_markdown_files


def agent():
    return Stage1Agent(PlannerLLMClient(backend=RaisingBackend([])))


def test_segments_preserve_every_source_character_and_original_line_positions(tmp_path):
    path = tmp_path / "long.md"
    body = "# Source\n\n" + "\n".join(f"## Part {i}\n\n| x | 1 |\n| y | 2 |\n\n```verilog\nwire x;\n```\n" for i in range(20))
    path.write_text("\n\n" + body)
    documents = load_markdown_files([str(path)])
    run = agent(); run._MAX_SOURCE_CHARS_PER_BATCH = 190
    batches = run._make_document_batches(documents)
    parts = [p for batch in batches for p in batch]
    assert len(parts) > 1
    assert "".join(p["content"] for p in parts) == documents[0]["content"]
    assert all(len(p["content"]) <= 190 for p in parts)
    for part in parts:
        segment = part["_source_segment"]
        original = path.read_text().splitlines(keepends=True)
        assert "".join(original[segment["start_line"] - 1:segment["end_line"]]).rstrip() == part["content"].rstrip()
    for left, right in zip(parts, parts[1:]):
        assert left["_source_segment"]["end_line"] + 1 == right["_source_segment"]["start_line"]


def test_batch_size_is_bounded_across_files_and_long_lines_are_not_truncated():
    run = agent(); run._MAX_SOURCE_CHARS_PER_BATCH = 100
    docs = [{"path": f"/missing/spec{i}.md", "content": "x" * 70} for i in range(3)]
    assert len(run._make_document_batches(docs)) == 3
    long = {"path": "/missing/long.md", "content": "x" * 250 + "\nshort"}
    parts = [p for b in run._make_document_batches([long]) for p in b]
    assert "".join(p["content"] for p in parts) == long["content"]
    assert parts[0]["content"] == "x" * 250 + "\n"


def test_segment_ids_bind_content_and_intervals():
    run = agent(); run._MAX_SOURCE_CHARS_PER_BATCH = 100
    original = {"path": "/missing/spec.md", "content": "same\n" * 80}
    batches = run._make_document_batches([original])
    ids = [run._batch_id(i, b) for i, b in enumerate(batches, 1)]
    assert len(ids) == len(set(ids))
    changed = run._make_document_batches([{**original, "content": original["content"] + "changed"}])
    assert ids[0] != run._batch_id(1, changed[0])


def test_segment_prompt_does_not_replay_the_growing_fact_ledger(tmp_path):
    task, spec, _ = make_task_input(tmp_path, image_count=0)
    payload = make_stage1_fact_payload(spec)
    payload["fact_ledger"]["facts"][0]["notes"] = "DO_NOT_REPEAT_THIS_" * 20000
    artifact = Stage1ContractsArtifact(task_id=task.task_id, fact_ledger=payload["fact_ledger"])
    prompt, _ = agent()._build_round_prompt("facts", artifact,
        {"source_segments": [{"start_line": 2, "end_line": 3}]}, "CURRENT_SOURCE_ONLY")
    assert "CURRENT_SOURCE_ONLY" in prompt and "DO_NOT_REPEAT_THIS_" not in prompt
    assert len(prompt) < 20_000


def test_unsegmented_fact_batch_uses_the_same_compact_wire_view(tmp_path):
    task, spec, _ = make_task_input(tmp_path, image_count=0)
    payload = make_stage1_fact_payload(spec)
    payload["fact_ledger"]["facts"][0]["notes"] = "PRIOR_BATCH_DETAIL_" * 10000
    artifact = Stage1ContractsArtifact(task_id=task.task_id, fact_ledger=payload["fact_ledger"])
    run = agent()
    canonical, _ = run._build_round_prompt("facts", artifact, {}, "CURRENT_FILE_ORIGINAL")
    wire, _ = run._build_round_prompt("facts", artifact, {}, "CURRENT_FILE_ORIGINAL", compact_fact_context=True)
    assert "PRIOR_BATCH_DETAIL_" in canonical
    assert "PRIOR_BATCH_DETAIL_" not in wire and "CURRENT_FILE_ORIGINAL" in wire
    assert "known_modules" in wire
    assert len(wire) < 20000


def test_completed_source_segments_resume_after_timeout_without_reextracting(tmp_path, monkeypatch):
    task, spec, _ = make_task_input(tmp_path, image_count=0)
    first = make_stage1_fact_payload(spec)
    with spec.open("a") as stream:
        stream.write("\n\n# Additional commentary\n" + "Explanation without additional interface requirements.\n" * 140)
    monkeypatch.setattr(Stage1Agent, "_MAX_SOURCE_CHARS_PER_BATCH", 2000)
    run = agent(); run._prepare_inputs(task)
    count = len(run._document_batches)
    assert count > 2
    root = tmp_path / "case"
    runner = PlannerRunner(root, llm_backend=RaisingBackend([first, LLMRequestTimeoutError("segment interrupted")]))
    with pytest.raises(LLMRequestTimeoutError):
        runner.run(task, end_stage="stage1")
    saved = json.loads((root / "plan/stage1/contracts.json").read_text())
    assert len(saved["completed_batches"]) == 1
    empty = {"fact_ledger": {"source_files": [str(spec)], "facts": [], "ambiguous_items": []}}
    backend = RaisingBackend([deepcopy(empty) for _ in range(count - 1)])
    resumed = PlannerRunner(root, llm_backend=backend)
    result = resumed.run(task, resume=True, end_stage="stage1")
    assert result.stage1_status == "contracts_completed"
    assert len(result.completed_batches) == count and len(backend.calls) == count - 1
    assert all("source_segments" in call["user_prompt"] for call in backend.calls)
