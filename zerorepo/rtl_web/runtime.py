"""Runs ONLY in the existing agent interpreter; never imported by API startup."""

from __future__ import annotations
import argparse
import hashlib
import json
import logging
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace
import yaml
from .artifacts import Artifacts, atomic_json, parse_report, sha, tree_manifest
from .schemas import DemoError, now
from .settings import Settings
from .store import Store, dump


def load_agent(settings):
    from zerorepo.rpg_gen.base.llm_client import LLMConfig

    data = yaml.safe_load(settings.agent_config.read_text()) or {}
    cfg = LLMConfig.from_dict(data.get("llm", {}))
    cfg.log = False
    from .artifacts import PRIVATE_VALUES
    if isinstance(cfg.api_key,str) and len(cfg.api_key)>=8:PRIVATE_VALUES.add(cfg.api_key)
    return data, cfg


def verifier_manifest(settings):
    if (
        not settings.verify_script
        or not settings.verify_script.is_file()
        or not settings.oracle
    ):
        raise DemoError("verifier_missing", "请配置完整受信RealBench环境。", 503)
    dirs = [settings.verify_script.parent, *settings.reference_dirs]
    items = []
    for directory in dirs:
        if not directory.is_dir():
            raise DemoError("reference_missing", "受信参考设计或刺激文件不完整。", 503)
        for p in sorted(directory.rglob("*")):
            if any(x in {"obj_dir", "__pycache__", ".git"} for x in p.parts):
                continue
            if p.is_file() and p.suffix in {
                ".py",
                ".v",
                ".sv",
                ".vh",
                ".svh",
                ".cpp",
                ".h",
                ".f",
            }:
                if p.is_symlink():
                    raise DemoError(
                        "unsafe_reference", "参考资源不能包含符号链接。", 422
                    )
                items.append(
                    {
                        "path": p.relative_to(settings.oracle).as_posix(),
                        "sha256": sha(p),
                    }
                )
    return items


def final_verdict(report: str, verifier_pass: bool) -> str:
    parsed = parse_report(report)
    if parsed["verdict"] == "pass" and not verifier_pass:
        return "unverified"
    return parsed["verdict"]


def verify_only(settings, rtl: Path, out: Path):
    from zerorepo.rtl_impl.debug_agent.system_debug_runner import SystemSimReviewer

    inputs = verifier_manifest(settings)
    input_hash = tree_manifest(rtl)[0]
    reviewer = SystemSimReviewer(
        generated_dir=rtl,
        verify_script=settings.verify_script,
        output_dir=out,
        timeout=settings.verifier_timeout,
    )
    passed, internal, report = reviewer.review()
    path = out / "system_report.json"
    path.write_text(report)
    if input_hash != tree_manifest(rtl)[0] or verifier_manifest(settings) != inputs:
        raise DemoError("input_changed", "验证过程中输入或受信资源发生了变化。", 409)
    verdict = final_verdict(report, passed)
    import subprocess

    tools = {}
    for tool in ("verilator", "g++"):
        try:
            r = subprocess.run(
                [tool, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                env=settings.tool_env(),
            )
            tools[tool] = r.stdout.splitlines()[0] if r.stdout else "unavailable"
        except (OSError, subprocess.TimeoutExpired):
            tools[tool] = "unavailable"
    manifest = {
        "schema_version": "rtl-demo-input-v1",
        "rtl_tree_sha256": input_hash,
        "rtl_files": tree_manifest(rtl)[1],
        "spec_sha256": sha(settings.spec),
        "verifier_files": inputs,
        "reviewer_sha256": (
            sha(Path(sys.modules[SystemSimReviewer.__module__].__file__))
            if getattr(sys.modules.get(SystemSimReviewer.__module__), "__file__", None)
            else None
        ),
        "wrapper_sha256": (
            sha(out / "system_verify_wrapper.py")
            if (out / "system_verify_wrapper.py").is_file()
            else None
        ),
        "python_version": sys.version.split()[0],
        "tools": tools,
        "verifier_timeout": settings.verifier_timeout,
        "deployment_adaptation_sha256": (
            sha(out / 'deployment_adaptation.json') if (out / 'deployment_adaptation.json').is_file() else None
        ),
        "compile_jobs":int(settings.runtime.get('compile_jobs',1)),
    }
    manifest_path = out / "input_manifest.json"
    atomic_json(manifest_path, manifest)
    return {
        "rtl_dir": str(rtl),
        "report": str(path),
        "waveform": str(out / "wave.vcd"),
        "verdict": verdict,
        "internal_mismatch_count": internal,
        "verifier_fingerprint": sha(manifest_path),
        "input_manifest": str(manifest_path),
        "testbench_sha256": sha(
            settings.verify_script.parent / settings.case["testbench_filename"]
        ),
    }


class EventSink:
    def __init__(self, root: Path):
        self.path = root / "runtime_events.jsonl"

    def send(self, stage: str, **data):
        with self.path.open("a") as f:
            f.write(dump({"stage": stage, "observed_at": now(), **data}) + "\n")

    def record_stage_output(self, stage_name, artifact, task_input):
        data = artifact.model_dump() if hasattr(artifact, "model_dump") else {}
        stage = (
            "spec"
            if "stage1" in stage_name
            else (
                "rtl"
                if any(x in stage_name for x in ["stage5", "stage6"])
                else "architecture"
            )
        )
        modules = [
            {"module_id": m.get("module"), "status": m.get("status", "planned")}
            for m in data.get("module_files", data.get("modules", []))
            if isinstance(m, dict)
        ]
        self.send(stage, source_stage=stage_name, modules=modules)


def configure_agent(settings, run_root, merged):
    from zerorepo.rtl_impl.debug_agent.adapters import (
        debug_openai_config_from_planner_config,
    )
    from zerorepo.rtl_impl.debug_agent.debug_runner import RtlDebugConfig
    from zerorepo.rtl_impl.module_planner import PlannerTaskInput

    data, llm = load_agent(settings)
    if settings.oracle is None:
        raise DemoError("oracle_missing", "实时运行需要明确配置受信验证资源目录。", 503)
    debug = dict(data.get("rtl_debug", {}))
    debug["oracle_root"] = str(settings.oracle)
    memory_path = run_root/'job_inputs/memory/snapshot.json'
    if memory_path.is_file():
        from zerorepo.rtl_impl.rtl_memory.ledger import digest
        debug.update(memory_snapshot_path=str(memory_path), memory_snapshot_sha256=digest(json.loads(memory_path.read_text())),
                     outer_run_id=run_root.name, case_id=settings.case['case_id'], memory_profile_sha256=sha(settings.agent_config))
    cfg = RtlDebugConfig.from_mapping(
        debug, openai_config=debug_openai_config_from_planner_config(llm)
    )
    # The existing runner infers the RealBench project from rtl_dataset/<project>.
    # Preserve spec bytes while providing the registered oracle project in an isolated path.
    task_spec = (
        run_root
        / "inputs"
        / "rtl_dataset"
        / settings.case["project_hint"]
        / settings.spec.name
    )
    task_spec.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(settings.spec, task_spec)
    task = PlannerTaskInput(
        task_id=settings.case.get("planner_top", "e203_exu_alu_system"),
        spec_md_files=[str(task_spec)],
        project_type="light_repo_spec2rtl",
        notes="Web isolated " + settings.case["case_id"] + " run",
    )
    kg = None
    kgcfg = data.get("rtl_kg", {}) or {}
    if kgcfg.get("enabled"):
        from zerorepo.config.checkpoint_config import CheckpointManager
        from zerorepo.rtl_impl.rtl_kg import RTLKgService

        try:
            kg = RTLKgService(
                repo_path=merged,
                checkpoint_manager=CheckpointManager(run_root / ".zerorepo"),
                repo_data={},
                config=kgcfg,
                logger=logging.getLogger("rtl_demo.runtime"),
            )
            kg.initialize()
        except Exception:
            if kgcfg.get("mode", "required") == "required":
                raise
            kg = None
    return data, llm, cfg, task, kg


def repair_contracts(settings, store, context, sid):
    run = store.get("run", context["run_id"], sid)
    if run["origin"] == "historical":
        path = settings.source / ".zerorepo/module_planner/outputs/contracts.json"
        if settings.case["case_id"] == "e203":
            expected = json.loads(
                (settings.repo / "configs/rtl_demo_e203.evidence.json").read_text()
            )["contracts_sha256"]
        else:
            expected = json.loads(
                (settings.repo / "configs/rtl_demo_cases.evidence.json").read_text()
            )[settings.case["case_id"]]["contracts_sha256"]
        if not path.is_file() or not expected:
            raise DemoError(
                "contracts_missing",
                "该历史任务未保存完整接口契约，请从预置规格新建运行。",
                422,
            )
        if sha(path) != expected:
            raise DemoError("contract_changed", "历史接口契约与已审查记录不一致。", 409)
    else:
        path = (
            settings.data
            / "runs"
            / run["run_id"]
            / ".zerorepo/module_planner/outputs/contracts.json"
        )
        if not path.is_file() and run.get("source_run_id"):
            return repair_contracts(
                settings, store, {"run_id": run["source_run_id"]}, sid
            )
    if not path.is_file():
        raise DemoError("contracts_missing", "该运行缺少可追溯的接口契约。", 422)
    return json.loads(path.read_text())


def execute(settings: Settings, operation: dict, *, job: dict | None = None, run_root: Path | None = None) -> dict:
    settings = settings.for_case(operation["context_ref"].get("case_id", "e203"))
    store = None if job else Store(settings.data)
    art = None if job else Artifacts(settings.data, store)
    root = run_root or (settings.data / "runs" / operation["run_id"])
    root.mkdir(parents=True, exist_ok=True)
    sink = EventSink(root)
    spec_hash = sha(settings.spec)
    reference_before = verifier_manifest(settings)
    merged = root / ".zerorepo/workspace/merged"
    merged.mkdir(parents=True, exist_ok=True)
    kind = operation["kind"]
    sid = operation["session_id"]
    context = operation["context_ref"]
    if not job and kind in {"verify", "fix"}:
        version = store.get("version", context["version_id"], sid)
        src = art.version_path(version)
        for item in version["file_manifest"]:
            dst = merged / item["path"]
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src / item["path"], dst)
    if kind == "verify":
        sink.send("verify")
        result = verify_only(settings, merged, root / "final_verify")
    else:
        data, llm, debug, task, kg = configure_agent(settings, root, merged)
        outputs = root / ".zerorepo/module_planner/outputs"
        outputs.mkdir(parents=True, exist_ok=True)
        if kind == "generate_and_verify":
            from zerorepo.rtl_impl.module_planner import PlannerRunner

            sink.send("spec")
            pc = data.get("rtl_module_planner", {}) or {}
            runner = PlannerRunner(
                output_root=outputs,
                llm_config=llm,
                debug_config=debug,
                kg_service=kg,
                checkpoint_dir=root / ".zerorepo",
                artifact_sink=sink,
                request_policy=pc.get("request_policy"),
                retrieval_limits=pc.get("retrieval_limits"),
                temporal_planning_enabled=bool(
                    pc.get("temporal_planning", {}).get("enabled", False)
                ),
                temporal_failure_policy=pc.get("temporal_planning", {}).get(
                    "failure_policy", "degrade"
                ),
            )
            outcome = runner.run(task, resume=False, end_stage="stage6")
            if str(outcome.status) != "completed":
                raise DemoError(
                    "generation_incomplete", "RTL生成未全部完成，已保留中间产物。", 422
                )
        elif kind == "fix":
            from zerorepo.rtl_impl.debug_agent.system_debug_runner import (
                SystemDebugRunner,
            )
            from zerorepo.rtl_impl.debug_agent.adapters import build_debug_contract_json

            sink.send("repair")
            records = [
                SimpleNamespace(module=p.stem, merged_file=str(p), status="completed")
                for p in merged.iterdir()
                if p.suffix in {".v", ".sv"}
            ]
            contracts = (json.loads((root / "job_inputs/contracts.json").read_text())
                         if job else repair_contracts(settings, store, context, sid))
            atomic_json(outputs / "contracts.json", contracts)
            contract = build_debug_contract_json(
                module_name=settings.case.get("planner_top", "e203_exu_alu_system"),
                stage1_contracts=contracts,
                spec_text=settings.spec.read_text(),
            )
            runner = SystemDebugRunner(
                config=debug,
                workspace_root=root / ".zerorepo/workspace",
                output_root=outputs,
                repo_root=settings.repo,
                kg_service=kg,
            )
            outcome = runner.run_system(
                top_module=settings.case.get("planner_top", "e203_exu_alu_system"),
                task=task,
                spec_text=settings.spec.read_text(),
                contract_json=contract,
                merged_records=records,
            )
            if outcome.status in {"error", "disabled", "skipped"}:
                raise DemoError(
                    "repair_error", "修复流程未完成，请查看私有运行日志。", 422
                )
        else:
            raise DemoError("unsupported_operation", "不支持该操作。", 422)
        sink.send("verify")
        result = verify_only(settings, merged, root / "final_verify")
    if (
        sha(settings.spec) != spec_hash
        or verifier_manifest(settings) != reference_before
    ):
        raise DemoError("input_changed", "规格或受信验证输入发生了变化。", 409)
    sink.send("complete", verdict=result["verdict"])
    if kind != 'verify':
        for descriptor_path in (root/'.zerorepo/workspace').rglob('codex_private/run_descriptor.json'):
            from zerorepo.rtl_impl.rtl_memory.adapter import MemoryAdapter
            descriptor=json.loads(descriptor_path.read_text())
            if descriptor.get('memory_snapshot_path') and descriptor.get('outer_run_id')==operation['run_id']:
                adapter=MemoryAdapter(descriptor['memory_snapshot_path'],descriptor['memory_snapshot_sha256'],descriptor_path.parent/'memory',operation['run_id'],descriptor['run_id'])
                adapter.final_validation(tree_manifest(merged)[0],result['verdict'],sha(Path(result['report'])),result['verifier_fingerprint'])
    result["run_id"] = operation["run_id"]
    atomic_json(root / "result.json", result)
    return result



def execute_job(path: Path):
    from .jobs import load_job
    path=Path(path).absolute()
    job=load_job(path)
    import os
    from .artifacts import PRIVATE_VALUES
    PRIVATE_VALUES.update(os.environ[name] for name in job['inputs'].get('environment_names',[])
                          if len(os.environ.get(name,''))>=8)
    os.environ['ZEROREPO_RTL_KG_PARTITION']=job['kg_partition']
    os.environ['ZEROREPO_WEB_JOB']='1'
    if (path.parent/'job_inputs/tool-profile').is_dir():
        os.environ['CODEX_HOME']=str(path.parent/'job_inputs/tool-profile')
    config=path.parent / job['inputs']['config']
    settings=Settings(config,create_data=False).for_case(job['case_id'])
    if verifier_manifest(settings)!=job['inputs']['oracle_manifest']:
        raise DemoError('input_changed','受信验证材料发生变化。',409)
    operation={'operation_id':job['operation_id'],'run_id':job['run_id'],
               'kind':job['kind'],'context_ref':job['inputs']['context_ref'],'session_id':None}
    result=execute(settings,operation,job=job,run_root=path.parent)
    result.update(operation_id=job['operation_id'],release_id=job['release_id'])
    load_job(path)  # Check immutable inputs again before publishing the result.
    atomic_json(path.parent/'result.json',result)
    return result


def probe(settings):
    checks = {
        "chat_import": False,
        "runtime_probe": False,
        "kg": False,
        "backend": False,
    }
    try:
        data, llm = load_agent(settings)
        checks["chat_import"] = True
        checks["model_credentials"] = bool(
            llm.api_key
            or any(
                __import__("os").environ.get(k)
                for k in (
                    "OPENAI_API_KEY",
                    "ANTHROPIC_API_KEY",
                    "AZURE_OPENAI_API_KEY",
                    "GOOGLE_API_KEY",
                )
            )
        )
        from zerorepo.rtl_impl.debug_agent.system_debug_runner import SystemSimReviewer
        from zerorepo.rtl_impl.module_planner import PlannerRunner

        checks["runtime_probe"] = True
        debug = data.get("rtl_debug", {})
        checks["backend_cli"] = (
            shutil.which(debug.get("codex_bin", "codex")) is not None
        )
        checks["backend"] = debug.get("backend") != "codex" or checks["backend_cli"]
        if checks["backend"] and debug.get("backend") == "codex":
            import subprocess

            login = subprocess.run(
                [debug.get("codex_bin", "codex"), "login", "status"],
                capture_output=True,
                timeout=8,
            )
            checks["backend_auth"] = login.returncode == 0
            checks["backend"] = checks["backend_auth"]
            import tomllib, os

            profile = os.environ.get(
                "ZEROREPO_CODEX_PROFILE", debug.get("codex_profile", "proxy-a")
            )
            if profile:
                from zerorepo.rtl_impl.codex_debug.runner import CodexDebugRunner
                try:
                    CodexDebugRunner(profile=profile).profile_layers()
                    checks['backend_profile']=True
                    # The runner requires API provider credentials in these layers;
                    # a different global ChatGPT login is not proof of this profile.
                    checks['backend_auth']=True
                    checks['backend']=checks['backend_cli']
                except (OSError,ValueError,RuntimeError):
                    checks['backend_profile']=False
                    checks['backend']=False
        cfg = data.get("rtl_kg", {})
        if not cfg.get("enabled"):
            checks["kg"] = settings.development
        else:
            from neo4j import GraphDatabase

            n = cfg.get("neo4j", {})
            with GraphDatabase.driver(
                n.get("uri"),
                auth=(n.get("user"), n.get("password")),
                connection_timeout=3,
            ) as driver:
                driver.verify_connectivity()
                with driver.session(database=n.get('database','neo4j')) as session:
                    checks['kg_query']=session.run('RETURN 1 AS ok').single()['ok']==1
                from zerorepo.rtl_impl.rtl_kg.rtl_file_graph_builder import VerilogTreeSitter
                checks['parser']=not VerilogTreeSitter.get_parser().parse(b'module probe; endmodule').root_node.has_error
                checks["kg"] = checks['kg_query'] and checks['parser']
    except Exception:
        pass
    return checks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config")
    parser.add_argument("--job",type=Path)
    parser.add_argument("--operation")
    parser.add_argument("--probe", action="store_true")
    args = parser.parse_args()
    if args.job:
        if args.config or args.operation or args.probe:parser.error('--job is exclusive')
        try:
            execute_job(args.job)
        except Exception as error:
            from .artifacts import redact
            atomic_json(args.job.parent/'error.json',{'code':getattr(error,'code','runtime_error'),
                        'message':redact(str(error))[:1000]})
            raise SystemExit(1)
        return
    if not args.config:parser.error('--config or --job is required')
    settings = Settings(args.config)
    if args.probe:
        print(dump(probe(settings)))
        return
    if not settings.development:
        parser.error("Production requires the isolated --job entry")
    store = Store(settings.data)
    op = store.operation(args.operation)
    try:
        execute(settings, op)
    except Exception as error:
        root = settings.data / "runs" / op["run_id"]
        root.mkdir(parents=True, exist_ok=True)
        from .artifacts import redact

        atomic_json(
            root / "error.json",
            {
                "code": getattr(error, "code", "runtime_error"),
                "message": redact(str(error))[:1800],
            },
        )
        logging.exception("RTL runtime failed")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
