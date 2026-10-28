"""Import the reviewed AES/SDC final snapshots without inventing repair history."""

import hashlib
import json
from pathlib import Path
from .artifacts import (
    Artifacts,
    atomic_json,
    sha,
    tree_manifest,
    safe_path,
    parse_report,
)
from .import_case import public, publish_validation
from .schemas import DemoError
from .store import dump


def import_recorded_case(settings, store, source, bundle_id):
    case = settings.case
    cid = case["case_id"]
    expected = json.loads(
        (settings.repo / "configs/rtl_demo_cases.evidence.json").read_text()
    )[cid]
    base = safe_path(source, ".zerorepo/workspace/debug_system/" + case["planner_top"])
    rtl = safe_path(base, "generated")
    planner = safe_path(source, ".zerorepo/module_planner/outputs/repo_skeleton.json")
    report = safe_path(base, "debug_sim_output.json")
    wave = safe_path(base, "wave.vcd")
    tb = safe_path(base, case["testbench_filename"])
    inputs = safe_path(base, "debug_input_manifest.json")
    current = {
        "tree_sha256": tree_manifest(rtl)[0],
        "spec_sha256": sha(settings.spec),
        "planner_sha256": sha(planner),
        "report_sha256": sha(report),
        "waveform_sha256": sha(wave),
        "testbench_sha256": sha(tb),
        "input_manifest_sha256": sha(inputs),
    }
    if any(current[k] != expected[k] for k in current):
        raise DemoError(
            "evidence_inconsistent", "案例快照、报告或波形与审查记录不一致。", 422
        )
    # Generated is the verifier's isolated input, not an unrelated mutable latest directory.
    recorded = json.loads(inputs.read_text())
    if recorded.get("top_module") != case["planner_top"] or {
        Path(p).name for p in recorded.get("generated_files", [])
    } != {f["path"] for f in tree_manifest(rtl)[1]}:
        raise DemoError("binding_missing", "缺少完整的受测RTL输入清单。", 422)
    fingerprint = hashlib.sha256(dump(current).encode()).hexdigest()
    target = settings.data / "bundles" / bundle_id / "manifest.json"
    art = Artifacts(settings.data, store)
    if target.is_file():
        previous = json.loads(target.read_text())
        if previous["source_fingerprint"] != fingerprint:
            raise DemoError("immutable_conflict", "同一演示包不能覆盖不同来源。", 409)
        for a in previous["artifacts"]:
            art.file(store.get("artifact", a["artifact_id"]))
        for v in previous["versions"]:
            art.version_path(store.get("version", v["version_id"]))
        return previous
    run_id = bundle_id + "-history"
    version = art.snapshot(rtl, bundle_id + "-final", run_id)
    spec = art.add(settings.spec, "spec", display=True)
    planning = art.add(planner, "planning", display=True)
    verifier_fp = hashlib.sha256(
        dump(
            {
                "testbench_sha256": expected["testbench_sha256"],
                "input_manifest_sha256": expected["input_manifest_sha256"],
            }
        ).encode()
    ).hexdigest()
    val = publish_validation(
        settings,
        store,
        art,
        version,
        report,
        wave,
        expected["stats_fields"],
        bundle_id + "-final-check",
        "final_system",
        binding_level="recorded_candidate",
        verifier_fingerprint=verifier_fp,
    )
    modules = [
        {
            "module_id": m["module"],
            "role": m.get("role", ""),
            "parents": m.get("parents", []),
            "children": m.get("children", []),
        }
        for m in json.loads(planner.read_text())["modules"]
    ]
    children = {c for m in modules for c in m["children"]}
    for m in modules:
        if not m["parents"]:
            m["parents"] = [
                p["module_id"] for p in modules if m["module_id"] in p["children"]
            ]
    events = []
    for stage, text, ref in [
        ("spec", "读取已保存的系统规格", {"artifact_id": spec["artifact_id"]}),
        (
            "architecture",
            f"已保存规划：{len(modules)} 个模块",
            {"artifact_id": planning["artifact_id"]},
        ),
        ("rtl", "查看已生成的RTL快照", {"version_id": version["version_id"]}),
        (
            "complete",
            "已保存的系统复验" + ("通过" if val["verdict"] == "pass" else "未通过"),
            {"validation_id": val["validation_id"]},
        ),
    ]:
        events.append(
            {
                "sequence": len(events) + 1,
                "stage": stage,
                "text": text,
                "origin": "historical",
                "observed_at": None,
                "replay_delay_ms": 1800,
                **ref,
            }
        )
    ids = {
        spec["artifact_id"],
        planning["artifact_id"],
        val["report_artifact_id"],
        val["waveform_artifact_id"],
        val["waveform_index_artifact_id"],
        *val.get("waveform_tile_artifact_ids", []),
        *(m["artifact_id"] for m in version["modules"]),
    }
    bundle = {
        "schema_version": "rtl-demo-bundle-v1",
        "bundle_id": bundle_id,
        "case_id": cid,
        "source_run_id": run_id,
        "origin": "historical",
        "title": case["title"],
        "subtitle": case["subtitle"],
        "summary": case["summary"],
        "spec_artifact_id": spec["artifact_id"],
        "planner_artifact_id": planning["artifact_id"],
        "source_fingerprint": fingerprint,
        "verifier_fingerprint": verifier_fp,
        "binding_level": "recorded_candidate",
        "binding_note": "展示已保存的真实受测快照、系统报告和波形；未保存可配对的修复前波形，采样统计缺失时不填零。",
        "modules": modules,
        "versions": [public(version)],
        "validations": [public(val)],
        "artifacts": public([store.get("artifact", i) for i in sorted(ids) if i]),
        "events": events,
        "stats_fields": expected["stats_fields"],
        "trial_count": None,
        "comparison_pair": {
            "before_validation_id": None,
            "after_validation_id": val["validation_id"],
        },
    }
    bundle["manifest_sha256"] = hashlib.sha256(dump(bundle).encode()).hexdigest()
    store.put(
        "run",
        run_id,
        {
            "run_id": run_id,
            "case_id": cid,
            "origin": "historical",
            "state": "completed",
            "versions": [version["version_id"]],
            "validations": [val["validation_id"]],
            "events": events,
        },
        immutable=True,
    )
    store.put("bundle", bundle_id, bundle, immutable=True)
    atomic_json(target, bundle)
    return bundle
