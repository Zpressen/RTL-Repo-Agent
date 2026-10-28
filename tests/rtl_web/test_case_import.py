import json
from pathlib import Path
import pytest
from zerorepo.rtl_web.artifacts import Artifacts, parse_report, safe_path
from zerorepo.rtl_web.schemas import DemoError
from zerorepo.rtl_web.import_case import validate_candidate, export_static


def test_duplicate_hints_do_not_double_count():
    s = "Hint: Output 'x' has 1 mismatches. First mismatch occurred at time 1125.\n" * 2
    stats = parse_report(
        json.dumps(
            {
                "stdout": s
                + "Total mismatched samples is 1 out of 222 samples\nSummary:\n system_verify: FAIL\n"
            }
        )
    )
    assert stats["mismatched_samples"] == 1
    assert stats["first_failure_ticks"] == "1125"


def test_pass_requires_authoritative_report():
    assert parse_report("lint PASS")["verdict"] == "unverified"
    assert (
        parse_report("Total mismatched samples is 0 out of 222 samples")["verdict"]
        == "fail"
    )
    with pytest.raises(DemoError):
        parse_report(
            "Total mismatched samples is 0 out of 222 samples\nTotal mismatched samples is 1 out of 222 samples"
        )


def test_inherited_wave_from_lint_failure_rejected():
    with pytest.raises(DemoError):
        validate_candidate(
            {
                "event": "evaluate",
                "result": {
                    "validation_trial": 1,
                    "lint_pass": False,
                    "sim_completed": False,
                },
            },
            1,
        )


def test_symlink_escape_rejected(tmp_path):
    root = tmp_path / "data"
    root.mkdir()
    (root / "escape").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(DemoError):
        safe_path(root, "escape/secret")
    with pytest.raises(DemoError):
        safe_path(root, "../secret")


def test_real_case_binding_and_static_allowlist(settings, ledger, bundle, tmp_path):
    checks = {x["validation_id"]: x for x in bundle["validations"]}
    before = checks[bundle["comparison_pair"]["before_validation_id"]]
    after = checks[bundle["comparison_pair"]["after_validation_id"]]
    assert (before["mismatched_samples"], before["total_samples"]) == (1, 222)
    assert (after["mismatched_samples"], after["kind"]) == (0, "final_system")
    assert before["waveform_sha256"] != after["waveform_sha256"]
    exported = tmp_path / "public"
    export_static(settings, ledger, bundle["bundle_id"], exported)
    files = [
        p.relative_to(exported).as_posix() for p in exported.rglob("*") if p.is_file()
    ]
    assert "manifest.json" in files
    assert not any(
        "codex_home" in p or p.endswith(".vcd") or "provider" in p for p in files
    )
    assert "/home/mokita" not in (exported / "manifest.json").read_text()
    ver = ledger.get("version", after["version_id"])
    art = Artifacts(settings.data, ledger)
    tree = art.version_path(ver)
    target = next(tree.glob("*.v"))
    target.write_text(target.read_text() + "\n// changed\n")
    with pytest.raises(DemoError):
        art.version_path(ver)


def test_bundle_matches_contract(bundle):
    from zerorepo.rtl_web.schemas import Bundle
    from zerorepo.rtl_web.import_case import public

    assert Bundle.model_validate(public(bundle)).case_id == "e203"
