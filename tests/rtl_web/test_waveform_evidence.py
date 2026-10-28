from bisect import bisect_right
import pytest
from zerorepo.rtl_web.artifacts import Artifacts
from zerorepo.rtl_web.waveform import waveform_data
from zerorepo.rtl_web.schemas import DemoError


def wave(settings, ledger, bundle, which, start=1100, end=1160, **kw):
    ident = bundle["comparison_pair"][which + "_validation_id"]
    v = ledger.get("validation", ident)
    a = ledger.get("artifact", v["waveform_artifact_id"])
    return waveform_data(
        Artifacts(settings.data, ledger).file(a),
        a["sha256"],
        bundle["stats_fields"],
        v,
        start,
        end,
        **kw
    )


def test_real_sample_verdict_is_not_raw_combinational_match(settings, ledger, bundle):
    before = wave(settings, ledger, bundle, "before")
    after = wave(settings, ledger, bundle, "after")
    failures = [m for m in before["sample_markers"] if m["verdict"] == "fail"]
    assert [m["time_ticks"] for m in failures] == ["1125"]
    assert not [m for m in after["sample_markers"] if m["verdict"] == "fail"]
    assert all(m["sampled_value_available"] is False for m in after["sample_markers"])
    vals = {s["id"]: s for s in after["signals"]}

    def at(s, t):
        result = s["initial_value"]
        for tick, value in s["changes"]:
            if int(tick) <= t:
                result = value
        return result

    assert at(vals["wbck_o_wdat_dut"], 1125) != at(vals["wbck_o_wdat_ref"], 1125)


def test_window_carry_in_and_capacity(settings, ledger, bundle):
    w = wave(settings, ledger, bundle, "before", 1126, 1134)
    assert all(1126 < int(t) < 1134 for s in w["signals"] for t, _ in s["changes"])
    with pytest.raises(DemoError) as error:
        wave(settings, ledger, bundle, "before", 0, 2221, max_changes=1)
    assert error.value.code == "window_too_large"


def test_counts_must_match_report(settings, ledger, bundle):
    ident = bundle["comparison_pair"]["before_validation_id"]
    v = {**ledger.get("validation", ident), "mismatched_samples": 0}
    a = ledger.get("artifact", v["waveform_artifact_id"])
    with pytest.raises(DemoError):
        waveform_data(
            Artifacts(settings.data, ledger).file(a),
            a["sha256"],
            bundle["stats_fields"],
            v,
        )


def test_small_vcd_preserves_unknowns_missing_and_range(tmp_path):
    from zerorepo.rtl_web.artifacts import sha

    path = tmp_path / "small.vcd"
    path.write_text("""$timescale 10 ps $end
$scope module tb $end
$var wire 1 ! clk $end
$var wire 4 " wbck_o_wdat_dut $end
$upscope $end
$enddefinitions $end
#0
0!
bxxxx "
#5
1!
bzzzz "
#10
0!
b0011 "
""")
    v = {
        "validation_id": "small",
        "version_id": "v",
        "total_samples": None,
        "mismatched_samples": None,
    }
    data = waveform_data(path, sha(path), [], v, 6, 100)
    assert data["marker_status"] == "unsupported" and not data["sample_markers"]
    assert data["end_ticks"] == "11"
    assert data["timescale"] == {"value": 10, "unit": "ps"}
    assert data["signals"][1]["initial_value"] == "zzzz"
    assert data["signals"][1]["changes"] == [["10", "0011"]]
    assert "wbck_o_wdat_ref" in data["missing_signals"]
    with pytest.raises(DemoError, match="超出"):
        waveform_data(path, sha(path), [], v, 12, 14)


def test_unknown_layout_does_not_claim_sample_verdict(settings, ledger, bundle):
    from zerorepo.rtl_web.waveform import read_vcd, counter_markers

    ident = bundle["comparison_pair"]["before_validation_id"]
    v = ledger.get("validation", ident)
    a = ledger.get("artifact", v["waveform_artifact_id"])
    path = Artifacts(settings.data, ledger).file(a)
    assert counter_markers(
        read_vcd(str(path), a["sha256"]), ["invalid"] * 109, 222, 1
    ) == ("unsupported", [])
