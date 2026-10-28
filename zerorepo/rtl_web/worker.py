from __future__ import annotations
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from .artifacts import tree_manifest, Artifacts, atomic_json, safe_path
from .import_case import publish_validation
from .schemas import now
from .settings import Settings
from .store import Store
from .waveform import KNOWN_TB_HASH


def process_start(pid: int) -> str | None:
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]
    except (OSError, IndexError):
        return None


def descendants(root: int) -> dict[int, str]:
    """Only PID relationships/start times, never command lines or environments."""
    rows = {}
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            fields = (entry / "stat").read_text().rsplit(")", 1)[1].split()
            rows[int(entry.name)] = (int(fields[1]), fields[19])
        except (OSError, IndexError, ValueError):
            continue
    found = {}
    parents = {root}
    while parents:
        children = {
            pid
            for pid, (ppid, start) in rows.items()
            if ppid in parents and pid not in found
        }
        found.update({pid: rows[pid][1] for pid in children})
        parents = children
    return found


def signal_owned(owned: dict[int, str], sig: int):
    for pid, start in owned.items():
        if process_start(pid) != start:
            continue
        try:
            pgid = os.getpgid(pid)
            if pgid != os.getpgrp():
                os.killpg(pgid, sig)
            else:
                os.kill(pid, sig)
        except ProcessLookupError:
            pass


def reap_owned(owned: dict[int, str]):
    pending = set(owned)
    deadline = time.monotonic() + 1
    while pending and time.monotonic() < deadline:
        for pid in tuple(pending):
            try:
                waited, _ = os.waitpid(pid, os.WNOHANG)
                if waited or process_start(pid) != owned[pid]:
                    pending.discard(pid)
            except ChildProcessError:
                pending.discard(pid)
        if pending:
            time.sleep(0.01)


def terminate_group(
    proc: subprocess.Popen, grace: float = 2, owned: dict[int, str] | None = None
):
    known = dict(owned or {})
    known.update(descendants(proc.pid))
    signal_owned(known, signal.SIGTERM)
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        proc.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        pass
    signal_owned(known, signal.SIGKILL)
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    try:
        proc.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        pass


class Worker:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.store = Store(settings.data)
        self.art = Artifacts(settings.data, self.store)
        import yaml
        if settings.agent_config.is_file():
            private=yaml.safe_load(settings.agent_config.read_text()) or {}
            def values(value):
                if isinstance(value,dict):
                    for key,item in value.items():
                        if key in {'api_key','password','access_token'} and isinstance(item,str) and len(item)>=8 and not item.startswith('${'):
                            self.art.private_values.add(item)
                        else:values(item)
                elif isinstance(value,list):
                    for item in value:values(item)
            values(private)
        self.lock = None
        self.proc = None
        self.fields = json.loads(
            (settings.repo / "configs/rtl_demo_e203.evidence.json").read_text()
        )["stats_fields"]

    def workdir(self, op):
        from .jobs import job_root
        root=job_root(self.settings,op['run_id'])
        return root if (root/'job.json').is_file() else self.settings.data/'runs'/op['run_id']

    def heartbeat(self):
        (self.settings.data/'worker.heartbeat').touch()
        atomic_json(self.settings.data/'worker-state.json',{
            'release_id':self.settings.release_id,'code_root':str(Path(__file__).resolve().parents[2]),
            'checked_at':time.time(),'pid':os.getpid(),'start':process_start(os.getpid())})

    def recover(self):
        self.store.control('worker_recovering',True)
        with self.store.connect() as c:
            rows = [
                json.loads(r[0])
                for r in c.execute(
                    "SELECT payload FROM operations WHERE state IN ('accepted','running')"
                )
            ]
        for op in rows:
            p = self.workdir(op) / "process.json"
            if p.is_file():
                rec = json.loads(p.read_text())
                pid = rec["pid"]
                owned = {int(k): v for k, v in rec.get("descendants", {}).items()}
                if process_start(pid) == rec.get("start"):
                    owned[pid] = rec["start"]
                signal_owned(owned, signal.SIGKILL)
            self.store.update_operation(
                op["operation_id"],
                state="interrupted",
                error="执行服务已重启；请查看已保存结果后重新发起。",
                finished_at=now(),
            )
        self.store.control('worker_recovering',False)

    def collect_attempts(self, op: dict, seen: set):
        root = self.workdir(op)
        for journal in (root / ".zerorepo/workspace/debug_system").glob(
            "*/codex_private/journal/codex_validation_journal.jsonl"
        ):
            private = journal.parent.parent
            for line_index, line in enumerate(journal.read_text().splitlines()):
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                candidate = row.get("candidate_id")
                result = row.get("result", {})
                trial = result.get("validation_trial")
                if row.get("event") == "evaluate" and trial and trial not in seen:
                    rev = int(row.get("revision", result.get("candidate_revision", 1)))
                    path = safe_path(
                        private, f"candidates/{candidate}/revision_{rev:03d}"
                    )
                    if not (path / "merged").is_dir():
                        continue
                    vid = f'{op["run_id"]}-{candidate}-r{rev:03d}'
                    version = self.art.snapshot(
                        path / "merged",
                        vid,
                        op["run_id"],
                        op["session_id"],
                        op["context_ref"].get("version_id"),
                        disposition="candidate",
                    )
                    val = None
                    report = path / "artifacts/debug_sim_output.json"
                    if result.get("sim_completed") and report.is_file():
                        val = publish_validation(
                            self.settings,
                            self.store,
                            self.art,
                            version,
                            report,
                            path / "artifacts/wave.vcd",
                            self.fields,
                            f'{op["run_id"]}-trial-{trial}',
                            "candidate",
                            owner=op["session_id"],
                            trial_no=trial,
                            internal_mismatch_count=result.get("mismatch_count"),
                            binding_level="recorded_candidate",
                        )
                    attempt = {
                        "attempt_id": f'{op["run_id"]}-attempt-{trial}',
                        "run_id": op["run_id"],
                        "trial_no": trial,
                        "source_candidate": candidate,
                        "candidate_revision": rev,
                        "candidate_version_id": vid,
                        "validation_id": val["validation_id"] if val else None,
                        "decision": "pending",
                        "lint_pass": result.get("lint_pass"),
                        "simulation_completed": bool(result.get("sim_completed")),
                    }
                    self.store.put(
                        "attempt", attempt["attempt_id"], attempt, op["session_id"]
                    )
                    with self.store.connect(True) as c:
                        self.store.emit(
                            c,
                            op["session_id"],
                            "artifact.available",
                            {
                                "origin": "live",
                                "run_id": op["run_id"],
                                "operation_id": op["operation_id"],
                                "attempt": attempt,
                            },
                        )
                    seen.add(trial)
                elif row.get("event") in {"accept", "rollback"}:
                    decision_key = ("decision", str(journal), line_index)
                    if decision_key in seen:
                        continue
                    attempts = [
                        a
                        for a in self.store.list_records("attempt", op["session_id"])
                        if a["run_id"] == op["run_id"]
                        and a.get("source_candidate") == candidate
                        and (
                            not row.get("revision")
                            or a.get("candidate_revision") == row["revision"]
                        )
                    ]
                    for attempt in attempts:
                        decision = (
                            "accepted" if row["event"] == "accept" else "rolled_back"
                        )
                        if attempt["decision"] != decision:
                            attempt["decision"] = decision
                            self.store.put(
                                "attempt",
                                attempt["attempt_id"],
                                attempt,
                                op["session_id"],
                            )
                            version = self.store.get(
                                "version",
                                attempt["candidate_version_id"],
                                op["session_id"],
                            )
                            version["disposition"] = decision
                            self.store.put(
                                "version",
                                version["version_id"],
                                version,
                                op["session_id"],
                            )
                            with self.store.connect(True) as c:
                                self.store.emit(
                                    c,
                                    op["session_id"],
                                    "attempt.updated",
                                    {
                                        "origin": "live",
                                        "run_id": op["run_id"],
                                        "operation_id": op["operation_id"],
                                        "attempt": attempt,
                                    },
                                )
                    seen.add(decision_key)

    def publish_result(self, op: dict, result: dict):
        root = self.workdir(op)

        def local(value: str) -> Path:
            p = Path(value)
            if not p.resolve().is_relative_to(root.resolve()):
                raise ValueError("Result outside isolated run")
            return safe_path(root, p.relative_to(root).as_posix())

        if (root/'job.json').is_file():
            from .jobs import load_job
            from .artifacts import parse_report, sha
            job=load_job(root/'job.json')
            if result.get('operation_id')!=op['operation_id'] or result.get('release_id')!=self.settings.release_id:
                raise ValueError('Result identity mismatch')
            manifest=local(result['input_manifest'])
            if sha(manifest)!=result.get('verifier_fingerprint'):raise ValueError('Input manifest mismatch')
            inputs=json.loads(manifest.read_text())
            from .runtime import verifier_manifest
            if (inputs['rtl_tree_sha256']!=tree_manifest(local(result['rtl_dir']))[0]
                or inputs['spec_sha256']!=job['inputs']['spec_sha256']
                or inputs['verifier_files']!=job['inputs']['oracle_manifest']
                or verifier_manifest(self.settings)!=job['inputs']['oracle_manifest']):
                raise ValueError('Runtime inputs changed')
            stats=parse_report(local(result['report']).read_text())
            if result['verdict']=='pass' and stats['verdict']!='pass':raise ValueError('False pass result')
        version = self.art.snapshot(
            local(result["rtl_dir"]),
            op["run_id"] + "-final",
            op["run_id"],
            op["session_id"],
            op["context_ref"].get("version_id"),
        )
        expected_tb = (
            KNOWN_TB_HASH
            if self.settings.case["case_id"] == "e203"
            else json.loads(
                (
                    self.settings.repo / "configs/rtl_demo_cases.evidence.json"
                ).read_text()
            )[self.settings.case["case_id"]]["testbench_sha256"]
        )
        fields = self.fields if result.get("testbench_sha256") == expected_tb else []
        input_art = (
            self.art.add(
                local(result["input_manifest"]), "input_manifest", op["session_id"]
            )
            if result.get("input_manifest")
            else None
        )
        val = publish_validation(
            self.settings,
            self.store,
            self.art,
            version,
            local(result["report"]),
            local(result["waveform"]),
            fields,
            op["run_id"] + "-final-check",
            "final_system",
            owner=op["session_id"],
            internal_mismatch_count=result.get("internal_mismatch_count"),
            binding_level="full_input_manifest",
            verifier_fingerprint=result.get("verifier_fingerprint"),
            verdict=result["verdict"],
            input_manifest_artifact_id=input_art["artifact_id"] if input_art else None,
        )
        run = self.store.get("run", op["run_id"], op["session_id"])
        versions = [
            v["version_id"]
            for v in self.store.list_records("version", op["session_id"])
            if v["run_id"] == op["run_id"]
        ]
        validations = [
            v["validation_id"]
            for v in self.store.list_records("validation", op["session_id"])
            if v["run_id"] == op["run_id"]
        ]
        run.update(
            state="completed",
            versions=versions,
            validations=validations,
            completed_at=now(),
            verdict=val["verdict"],
        )
        planner = root / ".zerorepo/module_planner/outputs/repo_skeleton.json"
        if planner.is_file():
            data = json.loads(planner.read_text())
            run["modules"] = [
                {
                    "module_id": m["module"],
                    "role": m.get("role", ""),
                    "parents": m.get("parents", []),
                    "children": m.get("children", []),
                }
                for m in data.get("modules", [])
            ]
        self.store.put("run", op["run_id"], run, op["session_id"])
        with self.store.connect(True) as c:
            self.store.emit(
                c,
                op["session_id"],
                "validation.completed",
                {
                    "origin": "live",
                    "run_id": op["run_id"],
                    "operation_id": op["operation_id"],
                    "validation_id": val["validation_id"],
                    "version_id": version["version_id"],
                    "verdict": val["verdict"],
                },
            )
        self.store.update_operation(
            op["operation_id"],
            state="completed",
            stage="complete",
            verdict=val["verdict"],
            validation_id=val["validation_id"],
            version_id=version["version_id"],
            finished_at=now(),
        )

    def execute(self, op: dict):
        self.settings = self.settings.for_case(op["context_ref"].get("case_id", "e203"))
        self.fields = (
            json.loads(
                (self.settings.repo / "configs/rtl_demo_e203.evidence.json").read_text()
            )["stats_fields"]
            if self.settings.case["case_id"] == "e203"
            else json.loads(
                (
                    self.settings.repo / "configs/rtl_demo_cases.evidence.json"
                ).read_text()
            )[self.settings.case["case_id"]]["stats_fields"]
        )
        from .jobs import prepare_job
        try:
            # Recheck at execution time as well as admission: dependencies or
            # resource boundaries can disappear while a task is queued.
            if not self.settings.development:self.settings.require(op['kind'])
            from .budgets import disk_admission
            disk_admission(self.settings.data,min_free_bytes=int(self.settings.budgets.get('min_free_bytes',0)))
            job=prepare_job(self.settings,self.store,op)
            descriptor=json.loads(job.read_text())
            self.art.private_values.update(os.environ[name] for name in descriptor.get('inputs',{}).get('environment_names',[])
                                           if len(os.environ.get(name,''))>=8)
            command=[self.settings.python,'-m','zerorepo.rtl_web.runtime','--job',str(job)]
            if not self.settings.development:
                from .sandbox import job_command
                command=job_command(self.settings,job,command)
        except Exception as error:
            self.store.update_operation(op['operation_id'],state='failed',
                                        error=(str(error) if getattr(error,'code','')=='dependency_unavailable' else '执行输入或隔离未就绪。'),
                                        error_code=getattr(error,'code','job_unavailable'),finished_at=now())
            return
        root = self.workdir(op)
        root.mkdir(parents=True, exist_ok=True)
        log = (root / "runtime.log").open("ab")
        process_env=self.settings.tool_env()
        (root/'tmp').mkdir(exist_ok=True)
        process_env['TMPDIR']=str(root/'tmp')
        if not self.settings.development:
            from .sandbox import minimal_environment
            job_data=json.loads(job.read_text())
            process_env=minimal_environment(process_env,job_data['inputs'].get('environment_names',[]))
        proc = subprocess.Popen(
            command,
            cwd=self.settings.repo,
            env=process_env,
            stdout=log,
            stderr=log,
            start_new_session=True,
        )
        self.proc = proc
        atomic_json(
            root / "process.json", {"pid": proc.pid, "start": process_start(proc.pid)}
        )
        started = time.monotonic()
        seen = set()
        event_count = 0
        progress_hash = None
        owned = {}
        try:
            while proc.poll() is None:
                self.heartbeat()
                from .budgets import job_usage, disk_admission
                job_usage(root,int(self.settings.budgets.get('job_max_bytes',1024**3)))
                disk_admission(self.settings.data,min_free_bytes=int(self.settings.budgets.get('min_free_bytes',0)))
                owned.update(descendants(proc.pid))
                # run() is a subreaper, so detached grandchildren are also owned.
                if getattr(self, "subreaper", False):
                    owned.update(descendants(os.getpid()))
                atomic_json(
                    root / "process.json",
                    {
                        "pid": proc.pid,
                        "start": process_start(proc.pid),
                        "descendants": owned,
                    },
                )
                if time.monotonic() - started > self.settings.timeout:
                    terminate_group(proc, owned=owned)
                    self.store.update_operation(
                        op["operation_id"],
                        state="timed_out",
                        error="执行达到配置的时间上限。",
                        finished_at=now(),
                    )
                    return
                events = root / "runtime_events.jsonl"
                if events.is_file():
                    rows = events.read_text().splitlines()
                    for line in rows[event_count:]:
                        try:
                            event = json.loads(line)
                        except ValueError:
                            break
                        self.store.update_operation(
                            op["operation_id"], stage=event["stage"]
                        )
                        with self.store.connect(True) as c:
                            self.store.emit(
                                c,
                                op["session_id"],
                                "stage.updated",
                                {
                                    "origin": "live",
                                    "operation_id": op["operation_id"],
                                    "run_id": op["run_id"],
                                    **event,
                                },
                            )
                        event_count += 1
                planner = root / ".zerorepo/module_planner/outputs/repo_skeleton.json"
                progress = root / ".zerorepo/module_planner/outputs/stage5_codegen.json"
                if planner.is_file():
                    signature = hashlib.sha256(
                        planner.read_bytes()
                        + (progress.read_bytes() if progress.is_file() else b"")
                    ).hexdigest()
                    if signature != progress_hash:
                        planning = json.loads(planner.read_text())
                        records = (
                            json.loads(progress.read_text()).get("module_files", [])
                            if progress.is_file()
                            else []
                        )
                        statuses = {
                            m["module"]: m.get("status", "unknown") for m in records
                        }
                        run = self.store.get("run", op["run_id"], op["session_id"])
                        run["modules"] = [
                            {
                                "module_id": m["module"],
                                "role": m.get("role", ""),
                                "parents": m.get("parents", []),
                                "children": m.get("children", []),
                                "status": statuses.get(m["module"], "planned"),
                            }
                            for m in planning.get("modules", [])
                        ]
                        self.store.put("run", op["run_id"], run, op["session_id"])
                        with self.store.connect(True) as c:
                            self.store.emit(
                                c,
                                op["session_id"],
                                "module.updated",
                                {
                                    "origin": "live",
                                    "run_id": op["run_id"],
                                    "operation_id": op["operation_id"],
                                    "modules": run["modules"],
                                },
                            )
                        progress_hash = signature
                try:
                    self.collect_attempts(op, seen)
                except Exception as error:
                    # No unverified candidate is published. Keep evidence error in private log.
                    log.write(
                        (
                            f"Candidate evidence pending: {type(error).__name__}\n"
                        ).encode()
                    )
                    log.flush()
                time.sleep(0.5)
            self.collect_attempts(op, seen)
            result = root / "result.json"
            if proc.returncode == 0 and result.is_file():
                self.publish_result(op, json.loads(result.read_text()))
            else:
                error = root / "error.json"
                detail = json.loads(error.read_text()) if error.is_file() else {}
                self.store.update_operation(
                    op["operation_id"],
                    state="failed",
                    error=detail.get("message", "执行失败，请查看服务器运行记录。"),
                    error_code=detail.get("code", "runtime_error"),
                    finished_at=now(),
                )
        except Exception as error:
            terminate_group(proc, owned=owned)
            self.store.update_operation(
                op["operation_id"],
                state="failed",
                error=(str(error) if getattr(error,'code','').startswith('resource_') else "运行证据无法归档：" + type(error).__name__),
                error_code=getattr(error,'code','evidence_invalid'),
                finished_at=now(),
            )
        except BaseException:
            terminate_group(proc, owned=owned)
            self.store.update_operation(
                op["operation_id"],
                state="interrupted",
                error="运行中断，已保留产物。",
                finished_at=now(),
            )
            raise
        finally:
            if proc.poll() is None:
                terminate_group(proc, owned=owned)
            signal_owned(owned, signal.SIGKILL)
            if getattr(self, "subreaper", False):
                owned.update(descendants(os.getpid()))
                signal_owned(owned, signal.SIGKILL)
                reap_owned(owned)
            self.proc = None
            log.close()

    def run(self, once: bool = False):
        self.lock = (self.settings.data / "worker.lock").open("a")
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit("Another worker holds the execution lock")
        import ctypes

        libc = ctypes.CDLL(None, use_errno=True)
        self.subreaper = (
            libc.prctl(36, 1, 0, 0, 0) == 0
        )  # PR_SET_CHILD_SUBREAPER, Linux.
        self.recover()
        try:
            while True:
                self.heartbeat()
                op = self.store.claim()
                if op:
                    self.execute(op)
                if once:
                    return
                time.sleep(0.5)
        finally:
            if self.proc:
                terminate_group(self.proc)
            (self.settings.data / "worker.heartbeat").unlink(missing_ok=True)
            (self.settings.data / 'worker-state.json').unlink(missing_ok=True)
            self.lock.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    worker = Worker(Settings(args.config))

    def stop(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)
    try:
        worker.run(args.once)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
