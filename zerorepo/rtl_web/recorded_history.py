"""Reviewed, immutable E203 chronology. Never run tools or reuse inherited VCDs."""
from __future__ import annotations

import hashlib
import json

from .agent_trace import project_debug_trace
from .artifacts import Artifacts, safe_path, sha, tree_manifest, parse_report, atomic_json
from .schemas import DemoError
from .store import dump

SUFFIX = "-chronology-v2"


def expanded_bundle(store, bundle):
    from .root_causes import with_root_causes
    try:
        extra = store.get("bundle", bundle["bundle_id"] + SUFFIX)
    except DemoError as error:
        if error.code != "not_found":
            raise
        return with_root_causes(bundle)
    if extra.get("base_bundle_id") != bundle["bundle_id"] or extra.get("source_fingerprint") != bundle["source_fingerprint"] or extra.get("case_id") != bundle["case_id"]:
        raise DemoError("history_mismatch", "历史记录与当前案例绑定不一致。", 409)
    return with_root_causes({**extra, "bundle_id": bundle["bundle_id"]})


def prepare_history(settings, store, bundle):
    if bundle['case_id'] in {'aes_cipher_system_hard', 'aes_inv_cipher_top_system'}:
        from .recorded_react_history import prepare_react_history
        return prepare_react_history(settings, store, bundle)
    if bundle["case_id"] not in {"e203", "sdc_controller_system"}:
        return bundle
    sdc = bundle['case_id'] == 'sdc_controller_system'
    config = json.loads((settings.repo / 'configs' / ('rtl_demo_sdc.history.json' if sdc else 'rtl_demo_e203.history.json')).read_text())
    base = safe_path(settings.source, '.zerorepo/workspace/debug_system/' + settings.case['planner_top'])
    # Public-seed-only deployments can keep using the already imported chronology.
    if not base.is_dir():
        return expanded_bundle(store, bundle)
    from .import_case import public, publish_validation
    art = Artifacts(settings.data, store)
    runs, artifacts = [], {a["artifact_id"]: a for a in bundle["artifacts"]}
    canonical_binding = config["runs"][-1]["binding"]
    evidence = json.loads((settings.repo / 'configs' / ('rtl_demo_cases.evidence.json' if sdc else 'rtl_demo_e203.evidence.json')).read_text())
    expected = evidence[bundle['case_id']] if sdc else evidence
    fields = expected['stats_fields']
    if sdc:
        from copy import copy
        settings = copy(settings)
        settings.case = {**settings.case, 'signals': config['signals']}

    def checked(item, rtl=False):
        path = safe_path(base, item["path"])
        if (tree_manifest(path)[0] if rtl else sha(path)) != item["sha256"]:
            raise DemoError("history_mismatch", "历史快照、日志或验证产物校验失败。", 409)
        return path

    if sdc:
        record = json.loads(checked(config['run_record']).read_text())
        if (record.get('binding') != canonical_binding or record.get('run_id') != config['runs'][0]['source_run_id']
            or sha(settings.spec) != expected['spec_sha256']
            or canonical_binding['verifier'].get(settings.case['testbench_filename']) != sha(safe_path(base, settings.case['testbench_filename']))
            or canonical_binding['verifier'].get(settings.case['testbench_filename']) != expected['testbench_sha256']
            or config['runs'][-1]['final']['rtl']['sha256'] != bundle['versions'][-1]['tree_sha256']
            or config['runs'][-1]['final']['wave']['sha256'] != bundle['validations'][-1]['waveform_sha256']):
            raise DemoError('history_mismatch', '系统调试历史与当前案例来源不一致。', 409)

    for source in config["runs"]:
        if source["binding"] != canonical_binding:
            raise DemoError("history_mismatch", "两次运行的规格与验证环境不同。", 409)
        run_id = source["source_run_id"] + "-archive-v2"
        rows = [json.loads(line) for line in checked(source["journal"]).read_text().splitlines() if line.strip()]
        evaluations = [r for r in rows if r.get("event") == "evaluate"]
        if len(evaluations) != len(source["candidates"]):
            raise DemoError("history_mismatch", "历史候选数量不一致。", 409)
        verifier_fp = hashlib.sha256(dump(source["binding"]["verifier"]).encode()).hexdigest()
        versions, validations, attempts = [], [], []

        def snapshot(item, ident, parent=None):
            v = art.snapshot(checked(item, True), ident, run_id, parent=parent)
            versions.append(v)
            return v

        def validate(item, version, ident, kind, **extra):
            # Wave is supplied only for an actual completed simulation.
            report = checked(item["report"])
            wave = checked(item["wave"]) if "wave" in item else None
            v = publish_validation(settings, store, art, version, report, wave, fields, ident, kind,
                                   recorded_signal_report=sdc,
                                   binding_level="recorded_candidate", verifier_fingerprint=verifier_fp, **extra)
            if wave and v["marker_status"] != "verified":
                raise DemoError("history_mismatch", "报告与波形采样统计未通过核对。", 409)
            validations.append(v)
            return v

        initial_version = snapshot(source["initial"]["rtl"], run_id + "-initial")
        initial = validate(source["initial"], initial_version, run_id + "-initial-check", "initial_system",
                           **({'waveform_note': '初始失败报告已保存，但该版本VCD已被后续仿真覆盖；不借用候选或最终波形。'} if sdc and 'wave' not in source['initial'] else {}))
        baseline_version, baseline_validation = initial_version, initial
        pending = {}
        all_debug = project_debug_trace({**bundle, "source_run_id": run_id,
                                        "events": [{"trial_no": c["trial_no"]} for c in source["candidates"]]},
                                       rows, source["journal"]["sha256"])["trials"]
        specs = {c["trial_no"]: c for c in source["candidates"]}
        for row in rows:
            action = row.get("event")
            if action == "evaluate":
                result = row["result"]
                no = result["validation_trial"]
                spec = specs[no]
                if spec["candidate_id"] != row["candidate_id"] or spec["revision"] != row.get("revision", 1):
                    raise DemoError("history_mismatch", "候选版本与日志不一致。", 409)
                version = snapshot(spec["rtl"], f"{run_id}-trial-{no}", baseline_version["version_id"])
                expected = {"added": [], "modified": [], "deleted": []}
                left = {f["path"]: f["sha256"] for f in baseline_version["file_manifest"]}
                right = {f["path"]: f["sha256"] for f in version["file_manifest"]}
                for name in sorted(set(left) | set(right)):
                    if left.get(name) != right.get(name):
                        expected["added" if name not in left else "deleted" if name not in right else "modified"].append(name)
                if expected != result.get("diff"):
                    raise DemoError("history_mismatch", "代码差异与当时接受基线不一致。", 409)
                if result.get("sim_completed"):
                    if not result.get("lint_pass") or "wave" not in spec:
                        raise DemoError("history_mismatch", "本轮没有可绑定的新仿真。", 409)
                    val = validate(spec, version, f"{run_id}-check-{no}", "candidate", trial_no=no,
                                   internal_mismatch_count=result.get("mismatch_count"))
                    if (val["verdict"] == "pass") != bool(result.get("is_pass")):
                        raise DemoError("history_mismatch", "日志与报告结论冲突。", 409)
                else:
                    # Never publish the report/VCD inherited by a lint-only candidate.
                    diagnostic = settings.data / "indexes" / f"{run_id}-lint-{no}.json"
                    atomic_json(diagnostic, {"stdout": "", "stderr": result.get("lint_output_excerpt", "未完成语法检查")})
                    report_art = art.add(diagnostic, "report", display=True)
                    val = {"validation_id": f"{run_id}-check-{no}", "run_id": run_id,
                           "version_id": version["version_id"], "kind": "syntax", "trial_no": no,
                           "verdict": "fail", "simulation_completed": False, "total_samples": None,
                           "mismatched_samples": None, "first_failure_ticks": None,
                           "report_artifact_id": report_art["artifact_id"], "marker_status": "unsupported",
                           "binding_level": "recorded_candidate", "verifier_fingerprint": verifier_fp}
                    store.put("validation", val["validation_id"], val, immutable=True)
                    validations.append(val)
                debug = next(d for d in all_debug if d["trial_no"] == no)
                attempt = {"trial_no": no, "candidate_revision": spec["revision"],
                           "candidate_id": spec["candidate_id"], "candidate_version_id": version["version_id"],
                           "baseline_version_id": baseline_version["version_id"],
                           "before_validation_id": baseline_validation["validation_id"],
                           "validation_id": val["validation_id"], "decision": "superseded",
                           "lint_pass": bool(result.get("lint_pass")), "simulation_completed": bool(result.get("sim_completed")),
                           "debug": debug}
                attempts.append(attempt)
                pending[(spec["candidate_id"], spec["revision"])] = (attempt, version, val)
            elif action in {"accept", "rollback"}:
                key = (row.get("candidate_id"), row.get("candidate_revision", row.get("revision", 1)))
                if key not in pending:
                    raise DemoError("history_mismatch", "候选决策缺少对应版本。", 409)
                attempt, ver, val = pending[key]
                attempt["decision"] = "accepted" if action == "accept" else "rolled_back"
                if action == "accept":
                    baseline_version, baseline_validation = ver, val
        if baseline_version["tree_sha256"] != source["final"]["rtl"]["sha256"]:
            raise DemoError("history_mismatch", "最终接受基线与快照不同。", 409)
        final = validate(source["final"], baseline_version, run_id + "-final-check", "final_system")
        events = [{"sequence": i + 1, "stage": stage, "text": text, "observed_at": None, "replay_delay_ms": 1400,
                   **refs} for i, (stage, text, refs) in enumerate([
                       ("spec", "读取系统规格", {"artifact_id": bundle["spec_artifact_id"]}),
                       ("architecture", f"规划 {len(bundle['modules'])} 个RTL模块", {"artifact_id": bundle["planner_artifact_id"]}),
                       ("rtl", "本轮起始 RTL 快照", {"version_id": initial_version["version_id"]}),
                       ("verify", '初始系统仿真未通过 · 各输出差异见报告' if sdc else "初始系统仿真 · " + str(initial["mismatched_samples"]) + "/" + str(initial["total_samples"]), {"validation_id": initial["validation_id"]}),
                   ])]
        for a in attempts:
            events.append({"sequence": len(events) + 1, "stage": "repair" if a["lint_pass"] else "syntax",
                           "text": f"候选验证 {a['trial_no']} · " + ("语法检查未通过" if not a["lint_pass"] else "仿真通过" if a["debug"]["verdict"] == "pass" else "仿真存在差异"),
                           "trial_no": a["trial_no"], "validation_id": a["validation_id"],
                           "version_id": a["candidate_version_id"], "observed_at": None, "replay_delay_ms": 1400})
        events.append({"sequence": len(events) + 1, "stage": "complete", "text": "本轮独立系统复验" + ("通过" if final["verdict"] == "pass" else "未通过"),
                       "validation_id": final["validation_id"], "observed_at": None, "replay_delay_ms": 1600})
        run = {"run_id": run_id, "source_run_id": source["source_run_id"], "case_id": bundle['case_id'], "origin": "historical", "round_no": source["round_no"],
               "label": '完整修复过程' if sdc else "第一轮运行" if source["round_no"] == 1 else "第二轮运行", "modules": bundle["modules"],
               "initial_validation_id": initial["validation_id"], "final_validation_id": final["validation_id"],
               "journal_sha256": source["journal"]["sha256"], "events": events,
               "versions": public(versions), "validations": public(validations), "attempts": attempts}
        store.put("run", run_id, run, immutable=True)
        runs.append(run)
        for version in versions:
            for module in version["modules"]:
                a = store.get("artifact", module["artifact_id"]); artifacts[a["artifact_id"]] = public(a)
        for val in validations:
            for key in ("report_artifact_id", "waveform_index_artifact_id", "waveform_artifact_id"):
                if val.get(key):
                    a = store.get("artifact", val[key]); artifacts[a["artifact_id"]] = public(a)
            for ident in val.get("waveform_tile_artifact_ids", []):
                a = store.get("artifact", ident); artifacts[ident] = public(a)
    expanded = {**bundle, "bundle_id": bundle["bundle_id"] + SUFFIX, "base_bundle_id": bundle["bundle_id"],
                "versions": bundle["versions"] + [v for r in runs for v in r["versions"]],
                "validations": bundle["validations"] + [v for r in runs for v in r["validations"]],
                "artifacts": list(artifacts.values()),
                "debug_history": {"schema_version": "rtl-debug-history-v1", "source_fingerprint": bundle["source_fingerprint"],
                                  "history_fingerprint": hashlib.sha256(dump({"projection": 2, "sources": config}).encode()).hexdigest(), "runs": runs}}
    if sdc:
        expanded['binding_note'] = '依据保存的系统级候选快照、验证报告与VCD展示修复；各输出差异分别计数，不相加为不匹配采样数。初始VCD未留存，17次候选及最终独立复验均使用各自绑定的真实波形。'
    store.put("bundle", expanded["bundle_id"], expanded, immutable=True)
    return expanded_bundle(store, bundle)
