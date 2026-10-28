import json

from zerorepo.rtl_web.agent_trace import project_debug_trace


def test_trace_projection_preserves_decisions_and_discards_private_fields():
    bundle = {"case_id": "e203", "bundle_id": "demo", "source_run_id": "run",
              "source_fingerprint": "fp", "events": [{"trial_no": 1}, {"trial_no": 2}]}
    rows = [
        {"event": "evaluate", "candidate_id": "c1", "result": {
            "validation_trial": 1, "expected_effect": "Fix load boundary",
            "lint_pass": False, "sim_completed": False,
            "lint_output_excerpt": "%Error /home/private/work/dut.v:1 api_key=sk-12345678901234567890",
            "diff": {"modified": ["dut.v", "/private/password.v", "../secret.v"]},
            "trace_summary": {"trace_report_path": "/secret/trace.json",
                              "first_divergence": {"status": "sampling_alignment_unresolved"},
                              "raw_fail_outputs": [{"sig": "out", "actual": "untrusted"}]},
            "raw_private": "DO_NOT_EXPORT"}},
        {"event": "rollback", "candidate_id": "unrelated"},
        {"event": "rollback", "candidate_id": "c1"},
        {"event": "evaluate", "candidate_id": "c2", "result": {
            "validation_trial": 2, "lint_pass": True, "sim_completed": True,
            "is_pass": True, "mismatch_count": 0}},
        {"event": "accept", "candidate_id": "c2"},
    ]
    result = project_debug_trace(bundle, rows, "journal-hash")
    a, b = result["trials"]
    assert a["decision"] == "rollback" and b["decision"] == "accept"
    assert a["verdict"] == "fail" and b["verdict"] == "pass"
    assert a["files"] == [{"path": "dut.v", "change": "modified"}]
    assert a["signals"] == ["out"] and a["alignment"] == "unresolved"
    assert "mismatch_count" not in a and b["mismatch_count"] == 0
    encoded = json.dumps(result)
    for forbidden in ("/home/private", "sk-123", "DO_NOT_EXPORT", "trace_report_path", "untrusted"):
        assert forbidden not in encoded
    assert result["source_fingerprint"] == "fp" and result["journal_sha256"] == "journal-hash"


def test_real_archive_debug_trace_is_bound_without_changing_the_archive(bundle, settings):
    from zerorepo.rtl_web.agent_trace import export_debug_trace
    before = json.dumps(bundle, sort_keys=True)
    trace = export_debug_trace(settings, bundle)
    assert len(trace["trials"]) == 9
    assert [x["trial_no"] for x in trace["trials"]] == list(range(1, 10))
    assert trace["trials"][4]["decision"] == "accept"
    assert trace["trials"][5]["decision"] == "rollback"
    assert trace["trials"][8]["verdict"] == "pass"
    assert trace["trials"][4]["signals"] == ["wbck_o_wdat"]
    assert json.dumps(bundle, sort_keys=True) == before
    assert "codex_private" not in json.dumps(trace)


def test_export_rejects_unrelated_journal(bundle, settings):
    import copy
    import pytest
    from zerorepo.rtl_web.agent_trace import export_debug_trace
    changed = copy.deepcopy(bundle)
    changed["validations"][0]["source_candidate"] = "unrelated-candidate"
    with pytest.raises(ValueError, match="does not match"):
        export_debug_trace(settings, changed)
