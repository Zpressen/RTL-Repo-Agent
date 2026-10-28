from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re
from typing import Any
from .artifacts import (
    Artifacts,
    atomic_json,
    parse_report,
    redact,
    safe_path,
    sha,
    tree_manifest,
)
from .schemas import DemoError
from .settings import Settings
from .store import Store, dump, uid
from .waveform import waveform_data, KNOWN_TB_HASH


def validate_candidate(entry: dict, trial: int) -> dict:
    result = entry.get("result", {})
    if (
        entry.get("event") != "evaluate"
        or result.get("validation_trial") != trial
        or not result.get("sim_completed")
        or not result.get("lint_pass")
    ):
        raise DemoError(
            "candidate_unverified",
            "该候选没有完成对应的真实仿真，不能使用继承的波形。",
            422,
        )
    return result


def public(record: Any) -> Any:
    if isinstance(record, list):
        return [public(x) for x in record]
    if isinstance(record, dict):
        return {
            k: public(v)
            for k, v in record.items()
            if k
            not in {
                "storage_key",
                "private_root",
                "owner_session",
                "spec_source",
                "raw_report_path",
            }
        }
    return record


def publish_validation(
    settings: Settings,
    store: Store,
    art: Artifacts,
    version: dict,
    report: Path,
    wave: Path | None,
    fields: list[str],
    ident: str,
    kind: str,
    owner: str | None = None,
    recorded_signal_report: bool = False,
    **extra,
) -> dict:
    stats = parse_report(report.read_text())
    if recorded_signal_report:
        from .artifacts import signal_mismatches
        counts = signal_mismatches(stats['text'])
        if stats['verdict'] == 'fail' and counts and re.search(r'^\s*system_verify:\s*FAIL\s*$', stats['text'], re.M):
            stats['simulation_completed'] = True
        stats['signal_mismatches'] = counts
    report_art = art.add(report, "report", owner, display=True)
    val = {
        "signal_names": settings.case["signals"],
        "comparison_policy_id": settings.case["case_id"] + "-stats-v1",
        "validation_id": ident,
        "run_id": version["run_id"],
        "version_id": version["version_id"],
        "kind": kind,
        **{k: v for k, v in stats.items() if k != "text"},
        "report_artifact_id": report_art["artifact_id"],
        "waveform_artifact_id": None,
        "waveform_sha256": None,
        "marker_status": "unsupported",
        **extra,
    }
    if wave and wave.is_file() and stats["simulation_completed"]:
        wave_art = art.add(wave, "vcd", owner)
        val.update(
            waveform_artifact_id=wave_art["artifact_id"],
            waveform_sha256=wave_art["sha256"],
        )

        def window(start, end):
            return waveform_data(
                art.file(wave_art),
                wave_art["sha256"],
                fields,
                val,
                start,
                end,
                signal_names=settings.case["signals"],
            )

        from .waveform import read_vcd, counter_markers

        vcd = read_vcd(str(art.file(wave_art)), wave_art["sha256"])
        if recorded_signal_report:
            from .waveform import verify_signal_counters
            val['signal_counter_status'] = verify_signal_counters(vcd, fields, val['signal_mismatches'], val['verdict'])
        full_end = int(vcd.endtime) + 1
        marker_status, markers = counter_markers(
            vcd, fields, val["total_samples"], val["mismatched_samples"]
        )
        if stats["verdict"] == "pass" and any(m["verdict"] == "fail" for m in markers):
            raise DemoError(
                "evidence_inconsistent", "通过报告与波形失败采样冲突。", 422
            )
        tiles = []

        def archive(start, end):
            try:
                data = window(start, end)
            except DemoError as error:
                if error.code != "window_too_large" or end - start <= 1:
                    raise
                middle = (start + end) // 2
                archive(start, middle)
                archive(middle, end)
                return
            path = settings.data / "indexes" / f"{ident}-{start}-{end}.json"
            atomic_json(path, data)
            item = art.add(path, "waveform_tile", owner, display=True)
            tiles.append(
                {
                    "start_ticks": str(start),
                    "end_ticks": str(end),
                    "artifact_id": item["artifact_id"],
                }
            )

        try:
            data = window(0, full_end)
        except DemoError as error:
            if error.code != "window_too_large":
                raise
            archive(0, full_end)
            data = {
                "tiled": True,
                "validation_id": ident,
                "version_id": version["version_id"],
                "waveform_sha256": wave_art["sha256"],
                "start_ticks": "0",
                "end_ticks": str(full_end),
                "full_end_ticks": str(full_end),
                "tiles": tiles,
            }
        index = settings.data / "indexes" / f"{ident}.json"
        atomic_json(index, data)
        idx = art.add(index, "waveform", owner, display=True)
        val.update(
            marker_status=marker_status,
            waveform_index_artifact_id=idx["artifact_id"],
            full_end_ticks=str(full_end),
            waveform_tile_artifact_ids=[t["artifact_id"] for t in tiles],
        )
    store.put("validation", ident, val, owner, immutable=True)
    return val


def import_case(
    settings: Settings,
    store: Store,
    source: Path | None = None,
    bundle_id: str | None = None,
) -> dict:
    source = (source or settings.source).resolve()
    bundle_id = bundle_id or settings.bundle_id
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", bundle_id):
        raise DemoError("invalid_bundle", "演示包标识无效。", 422)
    if settings.case["case_id"] != "e203":
        from .import_catalog import import_recorded_case

        return import_recorded_case(settings, store, source, bundle_id)
    target = settings.data / "bundles" / bundle_id / "manifest.json"
    expected = json.loads(
        (settings.repo / "configs/rtl_demo_e203.evidence.json").read_text()
    )
    base = safe_path(source, ".zerorepo/workspace/debug_system/e203_exu_alu_system")
    private = safe_path(base, "codex_private")
    journal = [
        json.loads(line)
        for line in safe_path(private, "journal/codex_validation_journal.jsonl")
        .read_text()
        .splitlines()
        if line.strip()
    ]
    if (
        sha(safe_path(base, "e203_exu_alu_testbench.sv"))
        != expected["testbench_sha256"]
    ):
        raise DemoError("testbench_mismatch", "测试平台与已记录来源不一致。", 422)
    planner_path = safe_path(
        source, ".zerorepo/module_planner/outputs/repo_skeleton.json"
    )
    if (
        sha(planner_path) != expected["planner_sha256"]
        or sha(settings.spec) != expected["spec_sha256"]
    ):
        raise DemoError("source_mismatch", "规格或架构规划与预置记录不匹配。", 422)
    checked = []
    for role, want in expected["candidates"].items():
        entry = next(
            (
                x
                for x in journal
                if x.get("event") == "evaluate"
                and x.get("candidate_id") == want["candidate_id"]
                and x.get("result", {}).get("validation_trial") == want["trial"]
            ),
            None,
        )
        result = validate_candidate(entry or {}, want["trial"])
        candidate = safe_path(
            private,
            f"candidates/{want['candidate_id']}/revision_{want['revision']:03d}",
        )
        rtl = safe_path(candidate, "merged")
        report = safe_path(candidate, "artifacts/debug_sim_output.json")
        wave = safe_path(candidate, "artifacts/wave.vcd")
        if (
            tree_manifest(rtl)[0] != want["tree_sha256"]
            or sha(report) != want["report_sha256"]
            or sha(wave) != want["waveform_sha256"]
        ):
            raise DemoError(
                "evidence_inconsistent", "候选快照、报告或波形与已审查记录不一致。", 422
            )
        checked.append((role, want, result, rtl, report, wave))
    accepted = safe_path(private, "accepted_baseline/merged")
    if tree_manifest(accepted)[0] != expected["candidates"]["after"]["tree_sha256"]:
        raise DemoError("accepted_mismatch", "最终接受的RTL与成功候选不一致。", 422)
    final_report = safe_path(private, "final_sim_output.json")
    final_wave = safe_path(private, "final_verify/wave.vcd")
    final_stats = parse_report(final_report.read_text())
    if (
        final_stats["verdict"] != "pass"
        or sha(final_wave) != expected["candidates"]["after"]["waveform_sha256"]
    ):
        raise DemoError(
            "final_verification_missing", "最终独立复验及波形尚未核实。", 422
        )
    binding = json.loads(safe_path(base, "latest_debug_result.json").read_text()).get(
        "binding", {}
    )
    if (
        binding.get("verifier", {}).get("e203_exu_alu_testbench.sv")
        != expected["testbench_sha256"]
    ):
        raise DemoError("binding_missing", "最终复验缺少匹配的测试平台绑定。", 422)
    source_fingerprint = hashlib.sha256(
        dump(
            {
                "expected": {
                    k: v for k, v in expected.items() if k != "contracts_sha256"
                },
                "final_report": sha(final_report),
                "binding": binding,
            }
        ).encode()
    ).hexdigest()
    if target.exists():
        previous = json.loads(target.read_text())
        if previous.get("source_fingerprint") != source_fingerprint:
            raise DemoError(
                "immutable_conflict", "同一演示包标识不能覆盖不同来源。", 409
            )
        # Check all registered bytes before considering the previous import reusable.
        art = Artifacts(settings.data, store)
        for item in previous["artifacts"]:
            art.file(store.get("artifact", item["artifact_id"]))
        for version in previous["versions"]:
            art.version_path(store.get("version", version["version_id"]))
        return previous
    art = Artifacts(settings.data, store)
    run_id = f"{bundle_id}-history"
    fields = expected["stats_fields"]
    versions = []
    validations = []
    spec_art = art.add(settings.spec, "spec", display=True)
    planner_art = art.add(planner_path, "planning", display=True)
    verifier_fp = hashlib.sha256(dump(binding.get("verifier", {})).encode()).hexdigest()
    for role, want, result, rtl, report, wave in checked:
        version = art.snapshot(rtl, f"{bundle_id}-{role}", run_id)
        val = publish_validation(
            settings,
            store,
            art,
            version,
            report,
            wave,
            fields,
            f'{bundle_id}-trial{want["trial"]}',
            "candidate",
            trial_no=want["trial"],
            internal_mismatch_count=result.get("mismatch_count"),
            source_candidate=want["candidate_id"],
            binding_level="recorded_candidate",
            verifier_fingerprint=verifier_fp,
        )
        versions.append(version)
        validations.append(val)
    final = publish_validation(
        settings,
        store,
        art,
        versions[-1],
        final_report,
        final_wave,
        fields,
        f"{bundle_id}-final",
        "final_system",
        internal_mismatch_count=0,
        binding_level="recorded_candidate",
        verifier_fingerprint=verifier_fp,
    )
    validations.append(final)
    planner = json.loads(planner_path.read_text())
    modules = [
        {
            "module_id": m["module"],
            "role": m.get("role", ""),
            "children": m.get("children", []),
            "parents": m.get("parents", []),
        }
        for m in planner["modules"]
    ]
    events = [
        {
            "sequence": 1,
            "stage": "spec",
            "text": "读取系统规格",
            "artifact_id": spec_art["artifact_id"],
            "origin": "historical",
            "observed_at": None,
            "replay_delay_ms": 1600,
        },
        {
            "sequence": 2,
            "stage": "architecture",
            "text": f"规划 {len(modules)} 个RTL模块",
            "artifact_id": planner_art["artifact_id"],
            "origin": "historical",
            "observed_at": None,
            "replay_delay_ms": 2200,
        },
        {
            "sequence": 3,
            "stage": "rtl",
            "text": "生成并整合多模块RTL",
            "version_id": versions[0]["version_id"],
            "origin": "historical",
            "observed_at": None,
            "replay_delay_ms": 2200,
        },
    ]
    for row in journal:
        if row.get("event") != "evaluate":
            continue
        result = row["result"]
        trial = result.get("validation_trial")
        events.append(
            {
                "sequence": len(events) + 1,
                "stage": "verify" if trial == 1 else "repair",
                "text": f"候选验证 {trial} · "
                + (
                    "语法检查未通过"
                    if not result.get("lint_pass")
                    else ("仿真通过" if result.get("is_pass") else "仿真存在差异")
                ),
                "trial_no": trial,
                "validation_id": next(
                    (
                        v["validation_id"]
                        for v in validations
                        if v.get("trial_no") == trial
                    ),
                    None,
                ),
                "origin": "historical",
                "observed_at": None,
                "replay_delay_ms": 1500,
            }
        )
    events.append(
        {
            "sequence": len(events) + 1,
            "stage": "complete",
            "text": "独立系统复验通过",
            "validation_id": final["validation_id"],
            "origin": "historical",
            "observed_at": None,
            "replay_delay_ms": 1800,
        }
    )
    artifact_ids = {spec_art["artifact_id"], planner_art["artifact_id"]}
    for v in versions:
        artifact_ids.update(m["artifact_id"] for m in v["modules"])
    for v in validations:
        artifact_ids.update(
            v[k]
            for k in [
                "report_artifact_id",
                "waveform_artifact_id",
                "waveform_index_artifact_id",
            ]
            if v.get(k)
        )
    artifact_records = [store.get("artifact", i) for i in sorted(artifact_ids)]
    bundle = {
        "schema_version": "rtl-demo-bundle-v1",
        "bundle_id": bundle_id,
        "case_id": "e203",
        "source_run_id": run_id,
        "origin": "historical",
        "title": "E203 执行单元",
        "summary": "从系统规格推导多模块架构，生成RTL，并使用参考设计进行仿真和自动修复。",
        "spec_artifact_id": spec_art["artifact_id"],
        "planner_artifact_id": planner_art["artifact_id"],
        "source_fingerprint": source_fingerprint,
        "verifier_fingerprint": verifier_fp,
        "binding_level": "recorded_candidate",
        "binding_note": "历史候选和最终报告可追溯；未记录的全部外部依赖不作为已复现证明。",
        "modules": modules,
        "versions": public(versions),
        "validations": public(validations),
        "artifacts": public(artifact_records),
        "events": events,
        "stats_fields": fields,
        "trial_count": sum(x.get("event") == "evaluate" for x in journal),
        "comparison_pair": {
            "before_validation_id": validations[0]["validation_id"],
            "after_validation_id": final["validation_id"],
        },
    }
    bundle["manifest_sha256"] = hashlib.sha256(dump(bundle).encode()).hexdigest()
    store.put(
        "run",
        run_id,
        {
            "run_id": run_id,
            "case_id": "e203",
            "origin": "historical",
            "state": "completed",
            "versions": [v["version_id"] for v in versions],
            "validations": [v["validation_id"] for v in validations],
            "events": events,
        },
        immutable=True,
    )
    store.put("bundle", bundle_id, bundle, immutable=True)
    atomic_json(target, bundle)
    return bundle


def export_static(settings: Settings, store: Store, bundle_id: str, out: Path) -> dict:
    bundle = json.loads(
        (settings.data / "bundles" / bundle_id / "manifest.json").read_text()
    )
    from .recorded_history import prepare_history
    bundle = prepare_history(settings, store, bundle)
    art = Artifacts(settings.data, store)
    dest = out / "bundles" / bundle_id
    dest.mkdir(parents=True, exist_ok=True)
    contents = {}
    waves = {}
    published = {"manifest.json"}
    for item in bundle["artifacts"]:
        a = store.get("artifact", item["artifact_id"])
        if a["exposure"] != "display":
            continue
        data = art.file(a).read_text()
        name = a["artifact_id"] + ".json"
        published.add(name)
        if a["kind"] == "waveform_tile":
            atomic_json(dest / name, json.loads(data))
            continue
        if a["kind"] == "waveform":
            wave = json.loads(data)
            if wave.get("tiled"):
                for tile in wave["tiles"]:
                    a_tile = store.get("artifact", tile["artifact_id"])
                    tile_name = a_tile["artifact_id"] + ".json"
                    published.add(tile_name)
                    atomic_json(
                        dest / tile_name, json.loads(art.file(a_tile).read_text())
                    )
                    tile["url"] = (
                        f"/cases/{bundle['case_id']}/bundles/{bundle_id}/{tile_name}"
                    )
            waves[wave["validation_id"]] = (
                f"/cases/{bundle['case_id']}/bundles/{bundle_id}/{name}"
            )
            atomic_json(dest / name, wave)
        else:
            contents[a["artifact_id"]] = (
                f"/cases/{bundle['case_id']}/bundles/{bundle_id}/{name}"
            )
            atomic_json(dest / name, {"content": data, "sha256": a["sha256"]})
    from .evidence import export_packages
    packages=export_packages(settings,store,bundle,out)
    from .agent_trace import export_debug_trace
    debug_trace = export_debug_trace(settings, bundle)
    exported = {
        **bundle,
        **({"debug_trace": debug_trace} if debug_trace else {}),
        "evidence_packages": packages,
        "content_urls": contents,
        "waveform_urls": waves,
        "artifacts": [a for a in bundle["artifacts"] if a["exposure"] == "display"],
    }
    atomic_json(dest / "manifest.json", exported)
    atomic_json(out / "manifest.json", exported)
    for old in dest.glob("artifact-*.json"):
        if old.name not in published:
            old.unlink()
    from .stories import export_story_static
    export_story_static(settings, store, bundle['case_id'], out)
    return exported
