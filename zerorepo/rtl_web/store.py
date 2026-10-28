"""Small durable ledger. Transactions are the authority for execution, not SSE."""

from __future__ import annotations
from contextlib import contextmanager
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import sqlite3
import time
from typing import Any
from uuid import uuid4
from .schemas import DemoError, now


def uid(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class Store:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db = root / "state.sqlite3"
        self.key_path = root / "session.key"
        try:
            fd = os.open(self.key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(secrets.token_bytes(32))
        except FileExistsError:
            pass
        self.key = self.key_path.read_bytes()
        self.epoch=uid('api')
        with self.connect() as c:
            c.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, idem TEXT UNIQUE NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS records(kind TEXT NOT NULL,id TEXT NOT NULL,owner TEXT,payload TEXT NOT NULL,PRIMARY KEY(kind,id));
                CREATE TABLE IF NOT EXISTS operations(id TEXT PRIMARY KEY,session_id TEXT NOT NULL REFERENCES sessions(id),idem TEXT NOT NULL,digest TEXT NOT NULL,state TEXT NOT NULL,payload TEXT NOT NULL,UNIQUE(session_id,idem));
                CREATE UNIQUE INDEX IF NOT EXISTS single_operation ON operations((1)) WHERE state IN ('accepted','running');
                CREATE TABLE IF NOT EXISTS messages(id TEXT PRIMARY KEY,session_id TEXT NOT NULL REFERENCES sessions(id),seq INTEGER NOT NULL,idem TEXT NOT NULL,digest TEXT NOT NULL,state TEXT NOT NULL,payload TEXT NOT NULL,UNIQUE(session_id,seq),UNIQUE(session_id,idem));
                CREATE UNIQUE INDEX IF NOT EXISTS single_reply ON messages(session_id) WHERE state='replying';
                CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,session_id TEXT NOT NULL REFERENCES sessions(id),type TEXT NOT NULL,payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS seed_imports(seed_id TEXT PRIMARY KEY,manifest_sha256 TEXT NOT NULL,imported_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS historical_inputs(case_id TEXT NOT NULL,run_id TEXT NOT NULL,kind TEXT NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(case_id,run_id,kind));
                CREATE TABLE IF NOT EXISTS chat_leases(slot INTEGER PRIMARY KEY CHECK(slot=1),message_id TEXT NOT NULL,payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS controls(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            """)

    @contextmanager
    def connect(self, write: bool = False):
        c = sqlite3.connect(self.db, timeout=10)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        try:
            if write:
                c.execute("BEGIN IMMEDIATE")
            yield c
            c.commit()
        except BaseException:
            c.rollback()
            raise
        finally:
            c.close()

    def register_seed(self, c, data):
        """One caller-owned transaction; historical records are strictly immutable."""
        for row in data['records']:
            old=c.execute('SELECT owner,payload FROM records WHERE kind=? AND id=?',
                          (row['kind'],row['id'])).fetchone()
            payload=dump(row['payload'])
            if old and (old[0] is not None or old[1]!=payload):
                raise ValueError('Immutable seed conflict')
            if not old:
                c.execute('INSERT INTO records VALUES(?,?,NULL,?)',(row['kind'],row['id'],payload))
        for item in data['historical_inputs']:
            key=(item['case_id'],item['run_id'],item['kind'])
            old=c.execute('SELECT payload FROM historical_inputs WHERE case_id=? AND run_id=? AND kind=?',key).fetchone()
            if old and old[0]!=dump(item): raise ValueError('Immutable historical input conflict')
            if not old: c.execute('INSERT INTO historical_inputs VALUES(?,?,?,?)',(*key,dump(item)))
        digest=hashlib.sha256(dump(data).encode()).hexdigest()
        old=c.execute('SELECT manifest_sha256 FROM seed_imports WHERE seed_id=?',(data['seed_id'],)).fetchone()
        if old and old[0]!=digest: raise ValueError('Immutable seed manifest conflict')
        if not old:c.execute('INSERT INTO seed_imports VALUES(?,?,?)',(data['seed_id'],digest,now()))

    def historical_input(self, case_id, run_id, kind='contracts'):
        with self.connect() as c:
            row=c.execute('SELECT payload FROM historical_inputs WHERE case_id=? AND run_id=? AND kind=?',
                          (case_id,run_id,kind)).fetchone()
            return json.loads(row[0]) if row else None

    def control(self,key,value=None):
        with self.connect(value is not None) as c:
            if value is not None:
                c.execute('INSERT INTO controls VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,dump(value)))
            row=c.execute('SELECT value FROM controls WHERE key=?',(key,)).fetchone()
            return json.loads(row[0]) if row else None

    @staticmethod
    def check_admission(c, *, execution=False):
        keys=['maintenance']+(['worker_recovering'] if execution else [])
        for key in keys:
            row=c.execute('SELECT value FROM controls WHERE key=?',(key,)).fetchone()
            if row and json.loads(row[0]):
                raise DemoError('service_recovering','服务正在恢复或维护，请稍后重新发送。',503)

    def cookie(self, sid: str) -> str:
        return sid + "." + hmac.new(self.key, sid.encode(), hashlib.sha256).hexdigest()

    def authenticate(self, cookie: str | None, sid: str | None = None) -> str:
        if not cookie or "." not in cookie:
            raise DemoError("session_required", "请重新连接演示会话。", 401)
        actual = cookie.split(".", 1)[0]
        if (sid and actual != sid) or not hmac.compare_digest(
            cookie, self.cookie(actual)
        ):
            raise DemoError("session_forbidden", "无权访问该会话。", 403)
        self.session(actual)
        return actual

    @staticmethod
    def emit(c: sqlite3.Connection, sid: str, typ: str, payload: dict) -> int:
        data = {"origin": "live", **payload, "session_id": sid, "observed_at": now()}
        cur = c.execute(
            "INSERT INTO events(session_id,type,payload) VALUES(?,?,?)",
            (sid, typ, dump(data)),
        )
        return int(cur.lastrowid)

    def create_session(self, idem: str, selection: dict) -> dict:
        with self.connect(True) as c:
            old = c.execute(
                "SELECT payload FROM sessions WHERE idem=?", (idem,)
            ).fetchone()
            if old:
                saved = json.loads(old[0])
                if saved.get("case_id", "e203") != selection.get("case_id", "e203"):
                    raise DemoError(
                        "idempotency_conflict", "该请求标识已用于其他任务。", 409
                    )
                return saved
            sid = uid("session")
            data = {
                "session_id": sid,
                "case_id": selection.get("case_id", "e203"),
                "selection": selection,
                "created_at": now(),
            }
            c.execute("INSERT INTO sessions VALUES(?,?,?)", (sid, idem, dump(data)))
            self.emit(c, sid, "session.created", data)
            return data

    def session(self, sid: str) -> dict:
        with self.connect() as c:
            row = c.execute(
                "SELECT payload FROM sessions WHERE id=?", (sid,)
            ).fetchone()
            if not row:
                raise DemoError("not_found", "会话不存在。", 404)
            data = json.loads(row[0])
            data["messages"] = [
                json.loads(r[0])
                for r in c.execute(
                    "SELECT payload FROM messages WHERE session_id=? ORDER BY seq",
                    (sid,),
                )
            ]
            active = c.execute(
                "SELECT payload FROM operations WHERE session_id=? ORDER BY rowid DESC LIMIT 1",
                (sid,),
            ).fetchone()
            data["operation"] = json.loads(active[0]) if active else None
            data["operations"] = [
                json.loads(r[0])
                for r in c.execute(
                    "SELECT payload FROM operations WHERE session_id=? ORDER BY rowid",
                    (sid,),
                )
            ]
            data["last_event_id"] = c.execute(
                "SELECT COALESCE(MAX(id),0) FROM events WHERE session_id=?", (sid,)
            ).fetchone()[0]
            return data

    def selection(self, sid: str, selection: dict) -> dict:
        with self.connect(True) as c:
            data = json.loads(
                c.execute("SELECT payload FROM sessions WHERE id=?", (sid,)).fetchone()[
                    0
                ]
            )
            data["selection"] = selection
            c.execute("UPDATE sessions SET payload=? WHERE id=?", (dump(data), sid))
            self.emit(c, sid, "selection.updated", selection)
        return selection

    def put(
        self,
        kind: str,
        ident: str,
        payload: dict,
        owner: str | None = None,
        immutable: bool = False,
    ) -> dict:
        with self.connect(True) as c:
            old = c.execute(
                "SELECT payload FROM records WHERE kind=? AND id=?", (kind, ident)
            ).fetchone()
            if immutable and old and old[0] != dump(payload):
                raise DemoError("immutable_conflict", "已归档证据不能覆盖。", 409)
            c.execute(
                "INSERT INTO records VALUES(?,?,?,?) ON CONFLICT(kind,id) DO UPDATE SET payload=excluded.payload",
                (kind, ident, owner, dump(payload)),
            )
        return payload

    def get(self, kind: str, ident: str, sid: str | None = None) -> dict:
        with self.connect() as c:
            row = c.execute(
                "SELECT owner,payload FROM records WHERE kind=? AND id=?", (kind, ident)
            ).fetchone()
            if not row:
                raise DemoError("not_found", "所选记录不存在。", 404)
            if row[0] and row[0] != sid:
                raise DemoError("forbidden", "无权访问该运行。", 403)
            return json.loads(row[1])

    def list_records(self, kind: str, sid: str | None = None) -> list[dict]:
        with self.connect() as c:
            return [
                json.loads(r[0])
                for r in c.execute(
                    "SELECT payload FROM records WHERE kind=? AND (owner IS NULL OR owner=?) ORDER BY rowid",
                    (kind, sid),
                )
            ]

    def accept_operation(self, sid: str, idem: str, request: dict) -> tuple[dict, bool]:
        digest = hashlib.sha256(dump(request).encode()).hexdigest()
        with self.connect(True) as c:
            old = c.execute(
                "SELECT digest,payload FROM operations WHERE session_id=? AND idem=?",
                (sid, idem),
            ).fetchone()
            if old:
                if old[0] != digest:
                    raise DemoError(
                        "idempotency_conflict", "相同请求标识不能用于不同操作。", 409
                    )
                return json.loads(old[1]), False
            self.check_admission(c,execution=True)
            busy = c.execute(
                "SELECT id FROM operations WHERE state IN ('accepted','running')"
            ).fetchone()
            if busy:
                raise DemoError(
                    "busy",
                    "已有执行任务正在进行，请稍后重试；仍可继续提问。",
                    409,
                    active_operation_id=busy[0],
                )
            op = {
                "operation_id": uid("op"),
                "session_id": sid,
                "run_id": uid("run"),
                "kind": request["kind"],
                "context_ref": request["context_ref"],
                "state": "accepted",
                "origin": "live",
                "stage": "accepted",
                "created_at": now(),
                "verdict": "unverified",
            }
            c.execute(
                "INSERT INTO operations VALUES(?,?,?,?,?,?)",
                (op["operation_id"], sid, idem, digest, "accepted", dump(op)),
            )
            run = {
                "run_id": op["run_id"],
                "case_id": request["context_ref"].get("case_id", "e203"),
                "origin": "live",
                "state": "created",
                "operation_id": op["operation_id"],
                "source_run_id": request["context_ref"].get("run_id"),
                "versions": [],
                "validations": [],
            }
            c.execute(
                "INSERT INTO records VALUES(?,?,?,?)",
                ("run", run["run_id"], sid, dump(run)),
            )
            self.emit(c, sid, "operation.accepted", op)
            return op, True

    def operation(self, ident: str, sid: str | None = None) -> dict:
        with self.connect() as c:
            row = c.execute(
                "SELECT payload,session_id FROM operations WHERE id=?", (ident,)
            ).fetchone()
            if not row:
                raise DemoError("not_found", "操作不存在。", 404)
            if sid and row[1] != sid:
                raise DemoError("forbidden", "无权访问此操作。", 403)
            return json.loads(row[0])

    def claim(self) -> dict | None:
        with self.connect(True) as c:
            for key in ['maintenance','worker_recovering']:
                state=c.execute('SELECT value FROM controls WHERE key=?',(key,)).fetchone()
                if state and json.loads(state[0]):return None
            row = c.execute(
                "SELECT payload FROM operations WHERE state='accepted' ORDER BY rowid LIMIT 1"
            ).fetchone()
            if not row:
                return None
            data = json.loads(row[0])
            data.update(state="running", started_at=now())
            c.execute(
                "UPDATE operations SET state='running',payload=? WHERE id=?",
                (dump(data), data["operation_id"]),
            )
            row = c.execute(
                "SELECT payload FROM records WHERE kind='run' AND id=?",
                (data["run_id"],),
            ).fetchone()
            if row:
                run = json.loads(row[0])
                run.update(
                    state=data["state"],
                    stage=data.get("stage"),
                    verdict=data.get("verdict", "unverified"),
                )
                c.execute(
                    "UPDATE records SET payload=? WHERE kind='run' AND id=?",
                    (dump(run), data["run_id"]),
                )
            self.emit(c, data["session_id"], "operation.updated", data)
            return data

    def update_operation(self, ident: str, **changes) -> dict:
        with self.connect(True) as c:
            row = c.execute(
                "SELECT payload FROM operations WHERE id=?", (ident,)
            ).fetchone()
            data = {**json.loads(row[0]), **changes}
            c.execute(
                "UPDATE operations SET state=?,payload=? WHERE id=?",
                (data["state"], dump(data), ident),
            )
            row = c.execute(
                "SELECT payload FROM records WHERE kind='run' AND id=?",
                (data["run_id"],),
            ).fetchone()
            if row:
                run = json.loads(row[0])
                run.update(
                    state=data["state"],
                    stage=data.get("stage"),
                    verdict=data.get("verdict", "unverified"),
                )
                c.execute(
                    "UPDATE records SET payload=? WHERE kind='run' AND id=?",
                    (dump(run), data["run_id"]),
                )
            self.emit(c, data["session_id"], "operation.updated", data)
            return data

    def interrupt(self, messages: bool = False, operations: bool = False) -> None:
        if operations:
            with self.connect() as c:
                ids = [
                    r[0]
                    for r in c.execute(
                        "SELECT id FROM operations WHERE state='running'"
                    )
                ]
            for ident in ids:
                self.update_operation(
                    ident,
                    state="interrupted",
                    error="执行服务已重启，请确认结果后重新发起。",
                    finished_at=now(),
                )
        if messages:
            with self.connect() as c:
                ids = [
                    r[0]
                    for r in c.execute("SELECT id FROM messages WHERE state='replying'")
                ]
            for ident in ids:
                self.update_message(
                    ident,
                    state="interrupted",
                    answer="对话服务已重启，请重新发送问题。",
                )

    def add_message(self, sid: str, idem: str, request: dict) -> tuple[dict, bool]:
        digest = hashlib.sha256(dump(request).encode()).hexdigest()
        with self.connect(True) as c:
            old = c.execute(
                "SELECT digest,payload FROM messages WHERE session_id=? AND idem=?",
                (sid, idem),
            ).fetchone()
            if old:
                if old[0] != digest:
                    raise DemoError(
                        "idempotency_conflict", "请求标识已用于其他消息。", 409
                    )
                return json.loads(old[1]), False
            if c.execute(
                "SELECT 1 FROM messages WHERE session_id=? AND state='replying'", (sid,)
            ).fetchone():
                raise DemoError("chat_busy", "Agent正在回答，请稍后发送。", 409)
            self.check_admission(c)
            if c.execute("SELECT 1 FROM messages WHERE state='replying' LIMIT 1").fetchone() or c.execute('SELECT 1 FROM chat_leases').fetchone():
                raise DemoError('chat_busy','问答服务正在处理另一条消息，请稍后发送。',429,retry_after=2)
            seq = c.execute(
                "SELECT COALESCE(MAX(seq),0)+1 FROM messages WHERE session_id=?", (sid,)
            ).fetchone()[0]
            data = {
                "message_id": uid("message"),
                "sequence": seq,
                "session_id": sid,
                "text": request["text"],
                "context_ref": request["context_ref"],
                "state": "replying",
                "answer": None,
                "evidence_refs": [],
                "created_at": now(),
                "origin": "live",
                "client_message_id": request.get("client_message_id"),
            }
            c.execute(
                "INSERT INTO messages VALUES(?,?,?,?,?,?,?)",
                (data["message_id"], sid, seq, idem, digest, "replying", dump(data)),
            )
            try:
                start=Path(f'/proc/{os.getpid()}/stat').read_text().rsplit(')',1)[1].split()[19]
            except (OSError,IndexError):start=None
            c.execute('INSERT INTO chat_leases VALUES(1,?,?)',(data['message_id'],dump({
                'epoch':self.epoch,'pid':os.getpid(),'start':start,'deadline':time.time()+120})))
            self.emit(c, sid, "message.received", data)
            return data, True

    def update_message(self, ident: str, **changes) -> dict:
        with self.connect(True) as c:
            row = c.execute(
                "SELECT payload FROM messages WHERE id=?", (ident,)
            ).fetchone()
            data = {**json.loads(row[0]), **changes}
            c.execute(
                "UPDATE messages SET state=?,payload=? WHERE id=?",
                (data["state"], dump(data), ident),
            )
            if data['state']!='replying':c.execute('DELETE FROM chat_leases WHERE message_id=?',(ident,))
            self.emit(c, data["session_id"], "message.updated", data)
            return data

    def events(self, sid: str, after: int = 0) -> list[dict]:
        with self.connect() as c:
            return [
                {"event_id": r["id"], "type": r["type"], **json.loads(r["payload"])}
                for r in c.execute(
                    "SELECT * FROM events WHERE session_id=? AND id>? ORDER BY id LIMIT 500",
                    (sid, after),
                )
            ]
