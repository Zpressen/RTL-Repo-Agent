"""Real saved cases only; these tests never invoke a model or simulator."""

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from zerorepo.rtl_web.artifacts import Artifacts, parse_report
from zerorepo.rtl_web.cases import CASES
from zerorepo.rtl_web.import_case import import_case, export_static
from zerorepo.rtl_web.api import create_app
from zerorepo.rtl_web.schemas import Bundle
from zerorepo.rtl_web.settings import Settings
from zerorepo.rtl_web.runtime import repair_contracts
from zerorepo.rtl_web.schemas import DemoError


@pytest.mark.parametrize(
    "text",
    [
        "Passed\nSummary:\n  system_verify: PASS\n",
        "PASS\nSummary:\n  aes_cipher_system: PASS\n",
        "Hint: Total mismatched samples is 0 out of 222 samples\nPASS\nSummary:\n  e203_exu_alu_system: PASS\n",
    ],
)
def test_trusted_cli_pass_does_not_require_optional_statistics(text):
    result = parse_report(json.dumps({"stdout": text, "stderr": ""}))
    assert result["verdict"] == "pass" and result["simulation_completed"]
    if "222" not in text:
        assert result["total_samples"] is None and result["mismatched_samples"] is None


def test_no_stats_does_not_hide_fail_or_promote_lint():
    assert parse_report("Summary:\n system_verify: FAIL")["verdict"] == "fail"
    assert not parse_report("Summary:\n system_verify: FAIL")["simulation_completed"]
    assert parse_report("lint: PASS")["verdict"] == "unverified"
    assert (
        parse_report(
            "Total mismatched samples is 1 out of 222 samples\nSummary:\n system_verify: PASS"
        )["verdict"]
        == "fail"
    )
    assert (
        parse_report(
            json.dumps(
                {
                    "stdout": "Summary:\n system_verify: PASS",
                    "stderr": "%Error: compile failed",
                }
            )
        )["verdict"]
        == "fail"
    )


@pytest.fixture
def catalog(settings, ledger):
    if not all(settings.path(c["source_output"]).is_dir() for c in CASES.values()):
        pytest.skip("Reviewed local RTL outputs unavailable")
    return {cid: import_case(settings.for_case(cid), ledger) for cid in CASES}


def test_real_catalog_has_bound_pass_and_case_signals(
    settings, ledger, catalog, tmp_path
):
    for cid, b in catalog.items():
        Bundle.model_validate(b)
        assert b["case_id"] == cid
        final = next(
            v
            for v in b["validations"]
            if v["validation_id"] == b["comparison_pair"]["after_validation_id"]
        )
        assert final["verdict"] == "pass" and final["marker_status"] == "verified"
        if cid != "e203":
            assert (
                final["total_samples"] is None
                and b["comparison_pair"]["before_validation_id"] is None
            )
            assert final["signal_names"] == CASES[cid]["signals"]
        exported = export_static(
            settings.for_case(cid), ledger, b["bundle_id"], tmp_path / cid
        )
        if cid == "sdc_controller_system":
            url = exported["waveform_urls"][final["validation_id"]]
            index = json.loads(
                (
                    tmp_path / cid / "bundles" / b["bundle_id"] / Path(url).name
                ).read_text()
            )
            assert index["tiled"] and len(index["tiles"]) > 1
            markers = []
            for tile in index["tiles"]:
                data = json.loads(
                    (
                        tmp_path
                        / cid
                        / "bundles"
                        / b["bundle_id"]
                        / Path(tile["url"]).name
                    ).read_text()
                )
                assert sum(len(s["changes"]) for s in data["signals"]) <= 20000
                assert data["validation_id"] == final["validation_id"]
                assert data["signals"][0]["id"] == "wb_clk_i"
                markers.extend(data["sample_markers"])
            assert len(markers) == 23932 and not any(
                m["verdict"] == "fail" for m in markers
            )


def test_case_switch_retains_cookies_and_rejects_cross_case_operations(
    settings, ledger, catalog, monkeypatch
):
    monkeypatch.setattr(Settings, "require", lambda *args: None)
    with TestClient(create_app(settings), base_url="http://127.0.0.1") as c:
        h = {"Origin": "http://127.0.0.1:5173", "X-Demo-Request": "1"}
        sessions = {}
        for cid in CASES:
            res = c.post(
                "/api/sessions",
                json={"case_id": cid},
                headers={**h, "Idempotency-Key": "session-" + cid},
            )
            assert res.status_code == 201
            sessions[cid] = res.json()
        for cid, s in sessions.items():
            assert c.get("/api/sessions/" + s["session_id"]).status_code == 200
        conflict = c.post(
            "/api/sessions",
            json={"case_id": "aes_cipher_system_hard"},
            headers={**h, "Idempotency-Key": "session-e203"},
        )
        assert conflict.status_code == 409
        aes = sessions["aes_cipher_system_hard"]
        ctx = {k: v for k, v in aes["selection"].items() if k != "browsing_mode"}
        wrong = c.post(
            "/api/sessions/" + sessions["e203"]["session_id"] + "/operations",
            json={"kind": "verify", "context_ref": ctx},
            headers={**h, "Idempotency-Key": "wrong-case"},
        )
        assert wrong.status_code == 422
        accepted = c.post(
            "/api/sessions/" + aes["session_id"] + "/operations",
            json={"kind": "verify", "context_ref": ctx},
            headers={**h, "Idempotency-Key": "actual-case"},
        )
        assert accepted.status_code == 202
        assert (
            ledger.get("run", accepted.json()["run_id"], aes["session_id"])["case_id"]
            == "aes_cipher_system_hard"
        )
        check = c.get(
            "/api/runs/" + accepted.json()["run_id"],
            headers={"X-Demo-Case": "aes_cipher_system_hard"},
        )
        assert check.status_code == 200
        final = catalog["sdc_controller_system"]["validations"][0]
        w = c.get(
            "/api/validations/"
            + final["validation_id"]
            + "/waveform?start_ticks=69900&end_ticks=70100"
        )
        assert w.status_code == 200
        assert (
            w.json()["start_ticks"] == "69900"
            and w.json()["signals"][0]["id"] == "wb_clk_i"
        )
        assert (
            c.get("/api/cases").json()["cases"][-1]["case_id"]
            == "sdc_controller_system"
        )


def test_saved_repair_contract_is_bound_to_reviewed_case(
    settings, ledger, catalog, tmp_path
):
    for cid in CASES:
        s = settings.for_case(cid)
        b = catalog[cid]
        ctx = {"run_id": b["versions"][0]["run_id"]}
        if cid == "aes_cipher_system_hard":
            with pytest.raises(DemoError, match="未保存完整接口契约"):
                repair_contracts(s, ledger, ctx, None)
            continue
        assert repair_contracts(s, ledger, ctx, None)["interface_contracts"]
        forged = (
            tmp_path / "changed-source/.zerorepo/module_planner/outputs/contracts.json"
        )
        forged.parent.mkdir(parents=True, exist_ok=True)
        forged.write_text("{}")
        s.source = tmp_path / "changed-source"
        with pytest.raises(DemoError, match="历史接口契约"):
            repair_contracts(s, ledger, ctx, None)
