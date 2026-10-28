import os
import subprocess
import sys
import time
from zerorepo.rtl_web.worker import terminate_group


def test_timeout_stops_process_group(tmp_path):
    marker = tmp_path / "child.pid"
    script = (
        "import subprocess,time; p=subprocess.Popen(['sleep','30']); open("
        + repr(str(marker))
        + ",'w').write(str(p.pid)); time.sleep(30)"
    )
    proc = subprocess.Popen([sys.executable, "-c", script], start_new_session=True)
    try:
        deadline = time.monotonic() + 3
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        terminate_group(proc)
        assert proc.poll() is not None
        if marker.exists():
            pid = int(marker.read_text())
            stat = "/proc/" + str(pid) + "/stat"
            assert not os.path.exists(stat) or open(stat).read().split()[2] == "Z"
    finally:
        if proc.poll() is None:
            terminate_group(proc)


def test_worker_timeout_keeps_terminal_and_releases_slot(settings, ledger, monkeypatch):
    import subprocess, sys
    from zerorepo.rtl_web.worker import Worker

    settings.timeout = 0.01
    sid = ledger.create_session("timeout-session", {})["session_id"]
    op, _ = ledger.accept_operation(
        sid, "timeout-op", {"kind": "verify", "context_ref": {}}
    )
    op = ledger.claim()
    original = subprocess.Popen
    spawned = []
    # This test isolates process timeout handling; job authorization/material
    # preparation is covered separately by test_job_runtime.
    import zerorepo.rtl_web.jobs as jobs
    root=settings.data/'jobs'/op['run_id']
    root.mkdir(parents=True)
    descriptor=root/'job.json'
    descriptor.write_text('{}')
    monkeypatch.setattr(jobs,'prepare_job',lambda *args:descriptor)

    def bounded_child(argv, **kwargs):
        proc = original([sys.executable, "-c", "import time;time.sleep(30)"], **kwargs)
        spawned.append(proc)
        return proc

    monkeypatch.setattr(subprocess, "Popen", bounded_child)
    Worker(settings).execute(op)
    assert ledger.operation(op["operation_id"])["state"] == "timed_out"
    assert ledger.get("run", op["run_id"], sid)["state"] == "timed_out"
    assert spawned[0].poll() is not None
    assert ledger.claim() is None


def test_api_restart_does_not_reclaim_running_operation(settings, ledger, bundle):
    from fastapi.testclient import TestClient
    from zerorepo.rtl_web.api import create_app

    sid = ledger.create_session("restart-session", {})["session_id"]
    op, _ = ledger.accept_operation(
        sid, "restart-op", {"kind": "verify", "context_ref": {}}
    )
    ledger.claim()
    m, _ = ledger.add_message(
        sid,
        "pending-message",
        {"text": "explain", "context_ref": {}, "client_message_id": "x"},
    )
    with TestClient(create_app(settings)):
        assert ledger.operation(op["operation_id"])["state"] == "running"
        message = ledger.session(sid)["messages"][-1]
        assert message["state"] == "interrupted" and message["text"] == "explain"
        assert ledger.claim() is None


def test_candidate_revisions_are_distinct_and_rollback_is_durable(settings, ledger):
    import json
    from zerorepo.rtl_web.worker import Worker

    sid = ledger.create_session("revisions", {})["session_id"]
    op, _ = ledger.accept_operation(
        sid, "fix-revisions", {"kind": "fix", "context_ref": {}}
    )
    private = (
        settings.data
        / "runs"
        / op["run_id"]
        / ".zerorepo/workspace/debug_system/e203/codex_private"
    )
    rows = []
    for rev in (1, 2):
        path = private / f"candidates/candidate_test/revision_{rev:03d}/merged"
        path.mkdir(parents=True)
        (path / "unit.v").write_text(f"module unit; wire x={rev}; endmodule\n")
        rows.append(
            {
                "event": "evaluate",
                "candidate_id": "candidate_test",
                "revision": rev,
                "result": {
                    "validation_trial": rev,
                    "lint_pass": False,
                    "sim_completed": False,
                },
            }
        )
        rows.append(
            {"event": "rollback", "candidate_id": "candidate_test", "revision": rev}
        )
    journal = private / "journal/codex_validation_journal.jsonl"
    journal.parent.mkdir()
    journal.write_text("\n".join(json.dumps(r) for r in rows))
    worker = Worker(settings)
    seen = set()
    worker.collect_attempts(op, seen)
    attempts = ledger.list_records("attempt", sid)
    assert (
        len(attempts) == 2 and len({a["candidate_version_id"] for a in attempts}) == 2
    )
    assert all(
        a["decision"] == "rolled_back" and a["validation_id"] is None for a in attempts
    )
    assert all(
        ledger.get("version", a["candidate_version_id"], sid)["disposition"]
        == "rolled_back"
        for a in attempts
    )
    count = len(ledger.events(sid, 0))
    worker.collect_attempts(op, seen)
    assert len(ledger.events(sid, 0)) == count


def test_detached_codex_style_child_is_also_stopped(tmp_path):
    marker = tmp_path / "detached.pid"
    script = (
        "import subprocess,time; p=subprocess.Popen(['sleep','30'],start_new_session=True); open("
        + repr(str(marker))
        + ",'w').write(str(p.pid)); time.sleep(30)"
    )
    proc = subprocess.Popen([sys.executable, "-c", script], start_new_session=True)
    try:
        deadline = time.monotonic() + 3
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert marker.exists()
        child = int(marker.read_text())
        terminate_group(proc)
        deadline = time.monotonic() + 2
        while (
            os.path.exists(f"/proc/{child}/stat")
            and open(f"/proc/{child}/stat").read().split()[2] != "Z"
            and time.monotonic() < deadline
        ):
            time.sleep(0.02)
        assert (
            not os.path.exists(f"/proc/{child}/stat")
            or open(f"/proc/{child}/stat").read().split()[2] == "Z"
        )
    finally:
        if proc.poll() is None:
            terminate_group(proc)


def test_worker_start_interrupts_previous_accepted_request(settings,ledger):
    from zerorepo.rtl_web.worker import Worker
    sid=ledger.create_session('previous-worker',{})['session_id']
    op,_=ledger.accept_operation(sid,'queued-before-restart',{'kind':'verify','context_ref':{}})
    Worker(settings).recover()
    assert ledger.operation(op['operation_id'])['state']=='interrupted'
    assert ledger.claim() is None


def test_maintenance_refuses_new_calls_but_returns_idempotent_record(ledger):
    from zerorepo.rtl_web.schemas import DemoError
    import pytest
    sid=ledger.create_session('maintenance',{})['session_id']
    op,_=ledger.accept_operation(sid,'one',{'kind':'verify','context_ref':{}})
    ledger.control('maintenance',True)
    assert ledger.accept_operation(sid,'one',{'kind':'verify','context_ref':{}})[0]['operation_id']==op['operation_id']
    with pytest.raises(DemoError) as e:ledger.accept_operation(sid,'two',{'kind':'verify','context_ref':{}})
    assert e.value.status==503
    with pytest.raises(DemoError) as e:ledger.add_message(sid,'chat',{'text':'hello','context_ref':{}})
    assert e.value.status==503


def test_pid_reuse_is_not_killed(monkeypatch):
    import signal
    import zerorepo.rtl_web.worker as worker
    killed=[]
    monkeypatch.setattr(worker,'process_start',lambda pid:'new-process-start')
    monkeypatch.setattr(os,'kill',lambda *args:killed.append(args))
    monkeypatch.setattr(os,'killpg',lambda *args:killed.append(args))
    worker.signal_owned({123456:'previous-process-start'},signal.SIGKILL)
    assert killed==[]


def test_recovery_flag_rejects_execution_before_worker_ready(ledger):
    import pytest
    from zerorepo.rtl_web.schemas import DemoError
    sid=ledger.create_session('recovering',{})['session_id']
    ledger.control('worker_recovering',True)
    with pytest.raises(DemoError) as e:ledger.accept_operation(sid,'new-while-recovering',{'kind':'verify','context_ref':{}})
    assert e.value.status==503
    assert ledger.claim() is None
    ledger.control('worker_recovering',False)
    op,_=ledger.accept_operation(sid,'new-after-recovery',{'kind':'verify','context_ref':{}})
    assert ledger.claim()['operation_id']==op['operation_id']
