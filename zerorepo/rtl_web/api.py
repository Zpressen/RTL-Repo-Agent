from __future__ import annotations
import asyncio
import fcntl
from contextlib import asynccontextmanager
import difflib
import hmac
import json
import time
from uuid import uuid4
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from .artifacts import Artifacts
from .chat import respond, submit_operation, validate_context
from .import_case import public
from .schemas import (
    DemoError,
    MessageRequest,
    OperationRequest,
    Selection,
    SessionRequest,
)
from .settings import Settings
from .store import Store
from .waveform import waveform_data

EVENT_STREAM_SECONDS = 60


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    store = Store(settings.data)
    art = Artifacts(settings.data, store)
    tasks: set[asyncio.Task] = set()
    from .evidence import ExportManager
    exports=ExportManager(settings,store)

    @asynccontextmanager
    async def lifespan(app):
        lock=(settings.data/'api.lock').open('a')
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            lock.close()
            raise RuntimeError('Another API owns this data directory')
        exports.startup()
        store.interrupt(messages=True)
        yield
        for task in list(tasks):
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        lock.close()

    app = FastAPI(
        title="Deep Valley Chip RTL Studio",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.store = store
    app.state.settings = settings
    app.state.decision_provider = None

    def error_response(req, error):
        return JSONResponse(
            status_code=error.status,
            headers={'Retry-After':str(error.details.get('retry_after',2))} if error.status==429 else {},
            content={
                "error": {
                    "code": error.code,
                    "message": error.message,
                    "request_id": getattr(req.state, "request_id", ""),
                    **error.details,
                }
            },
        )

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        request.state.request_id = uuid4().hex
        try:
            local = (
                settings.development
                and request.url.hostname in {"localhost", "127.0.0.1", "::1"}
                and request.client
                and request.client.host
                in {"localhost", "127.0.0.1", "::1", "testclient"}
            )
            if not local:
                key = request.headers.get("X-Demo-Gateway-Key", "")
                if not settings.gateway_key or not hmac.compare_digest(
                    key, settings.gateway_key
                ):
                    raise DemoError(
                        "gateway_required", "请通过受保护的演示入口访问。", 401
                    )
            if request.method in {"POST", "PATCH", "PUT", "DELETE"}:
                if (
                    request.headers.get("Origin") not in settings.origins
                    or request.headers.get("X-Demo-Request") != "1"
                ):
                    raise DemoError("origin_forbidden", "请求来源未获允许。", 403)
                if (
                    request.headers.get("content-type", "").split(";")[0]
                    != "application/json"
                ):
                    raise DemoError("json_required", "请使用JSON请求。", 415)
                length = request.headers.get("content-length")
                if length:
                    try:
                        size = int(length)
                    except ValueError:
                        raise DemoError("invalid_length", "请求长度无效。", 422)
                    if size > 20000:
                        raise DemoError("request_too_large", "请求内容过长。", 413)
                chunks=[]
                actual_size=0
                async for chunk in request.stream():
                    actual_size+=len(chunk)
                    if actual_size>20000:
                        raise DemoError('request_too_large','请求内容过长。',413)
                    chunks.append(chunk)
                request._body=b''.join(chunks)
            response = await call_next(request)
        except DemoError as error:
            response = error_response(request, error)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(DemoError)
    async def domain_error(request, error):
        return error_response(request, error)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, error):
        return error_response(
            request, DemoError("invalid_request", "请求字段或格式无效。", 422)
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request, error):
        return error_response(
            request,
            DemoError(
                "not_found" if error.status_code == 404 else "http_error",
                (
                    "请求的接口不存在。"
                    if error.status_code == 404
                    else "请求暂时无法处理。"
                ),
                error.status_code,
            ),
        )

    def ok(req, data):
        return {**public(data), "request_id": req.state.request_id}

    def cookie_name(cid):
        return "rtl_demo_session" if cid == "e203" else "rtl_demo_session_" + cid

    def sid(req, ident=None, required=True):
        cid = (
            store.session(ident).get("case_id", "e203")
            if ident
            else req.headers.get("X-Demo-Case", req.query_params.get("case_id", "e203"))
        )
        settings.for_case(cid)
        cookie = req.cookies.get(cookie_name(cid))
        return store.authenticate(cookie, ident) if required or cookie else None

    def idem(req):
        value = req.headers.get("Idempotency-Key", "")
        if not 1 <= len(value) <= 128:
            raise DemoError("idempotency_required", "请求缺少有效标识。", 422)
        return value

    def bundle(case_id=None):
        selected = settings.for_case(case_id or settings.case["case_id"])
        return store.get("bundle", selected.bundle_id)

    @app.get("/api/health")
    def health(request: Request, case_id: str = "e203"):
        return ok(request, settings.for_case(case_id).preflight())

    @app.get("/api/cases")
    def cases(request: Request):
        from .cases import CASES

        available = {b["case_id"] for b in store.list_records("bundle")}
        return ok(
            request,
            {
                "cases": [
                    {
                        "case_id": cid,
                        "title": c["title"],
                        "subtitle": c["subtitle"],
                        "available": cid in available,
                    }
                    for cid, c in CASES.items()
                ]
            },
        )

    @app.get('/api/cases/{case_id}/evidence.zip')
    def download_evidence(request: Request,case_id:str,validation_id:str,before_validation_id:str|None=None):
        settings.for_case(case_id)
        if any(value and value!=case_id for value in [request.headers.get('X-Demo-Case'),request.query_params.get('case_id')]):
            raise DemoError('case_mismatch','请求案例不一致。',422)
        try:path=exports.create(case_id,validation_id,before_validation_id)
        except (OSError,ValueError,KeyError,TypeError):
            raise DemoError('evidence_inconsistent','证据材料不可导出。',409) from None
        class ExportResponse(FileResponse):
            async def __call__(self,scope,receive,send):
                try:await super().__call__(scope,receive,send)
                finally:exports.remove(path)
        return ExportResponse(path,media_type='application/zip',filename=case_id+'-evidence.zip',headers={'X-Content-Type-Options':'nosniff','Cache-Control':'no-store'})

    @app.get("/api/cases/{case_id}")
    def case(request: Request, case_id: str):
        from .recorded_history import expanded_bundle
        return ok(request, expanded_bundle(store, bundle(case_id)))

    @app.get('/api/cases/{case_id}/stories')
    def case_stories(request: Request, case_id: str):
        from .stories import story_view
        return ok(request, story_view(store, case_id))

    @app.get('/api/stories/{story_id}')
    def get_story(request: Request, story_id: str):
        from .stories import load_story, story_view
        data = load_story(store, story_id)
        return ok(request, story_view(store, data['case_id'], story_id))

    @app.post("/api/sessions", status_code=201)
    def new_session(request: Request, body: SessionRequest):
        from .recorded_history import expanded_bundle
        b = expanded_bundle(store, bundle(body.case_id))
        history = b.get("debug_history", {}).get("runs", [])
        vid = history[0]["initial_validation_id"] if history else b["comparison_pair"]["after_validation_id"]
        validation = store.get("validation", vid)
        selection = {
            "case_id": body.case_id,
            "run_id": validation["run_id"],
            "version_id": validation["version_id"],
            "validation_id": vid,
            "browsing_mode": "historical",
        }
        if history:
            selection["workspace_panel"] = "verify"
        data = store.create_session(idem(request), selection)
        response = JSONResponse(
            status_code=201, content=ok(request, store.session(data["session_id"]))
        )
        response.set_cookie(
            cookie_name(body.case_id),
            store.cookie(data["session_id"]),
            httponly=True,
            secure=settings.secure_cookies,
            samesite="strict",
            max_age=86400,
        )
        return response

    @app.get("/api/sessions/{ident}")
    def session(request: Request, ident: str):
        return ok(request, store.session(sid(request, ident)))

    @app.patch("/api/sessions/{ident}/selection")
    def selection(request: Request, ident: str, body: Selection):
        session_id = sid(request, ident)
        ctx = validate_context(
            store,
            session_id,
            body.model_dump(exclude={"browsing_mode"}, exclude_none=True),
        )
        return ok(
            request,
            store.selection(session_id, {**ctx, "browsing_mode": body.browsing_mode}),
        )

    @app.post("/api/sessions/{ident}/messages", status_code=202)
    async def message(request: Request, ident: str, body: MessageRequest):
        session_id = sid(request, ident)
        ctx = validate_context(
            store, session_id, body.context_ref.model_dump(exclude_none=True)
        )
        if not body.text.strip():
            raise DemoError("empty_message", "请输入问题或执行指令。", 422)
        data, new = store.add_message(
            session_id,
            idem(request),
            {
                "text": body.text.strip(),
                "context_ref": ctx,
                "client_message_id": body.client_message_id,
            },
        )
        if new:
            task = asyncio.create_task(
                respond(settings, store, data, app.state.decision_provider)
            )
            tasks.add(task)
            task.add_done_callback(tasks.discard)
        return ok(request, data)

    @app.post("/api/sessions/{ident}/operations", status_code=202)
    def operation(request: Request, ident: str, body: OperationRequest):
        session_id = sid(request, ident)
        op, _ = submit_operation(
            settings,
            store,
            session_id,
            idem(request),
            body.kind,
            body.context_ref.model_dump(exclude_none=True),
        )
        return ok(request, op)

    @app.get("/api/operations/{ident}")
    def get_operation(request: Request, ident: str):
        return ok(request, store.operation(ident, sid(request)))

    @app.get("/api/runs/{ident}")
    def run(request: Request, ident: str):
        session_id = sid(request)
        data = store.get("run", ident, session_id)
        data["versions"] = [
            v for v in store.list_records("version", session_id) if v["run_id"] == ident
        ]
        data["validations"] = [
            v
            for v in store.list_records("validation", session_id)
            if v["run_id"] == ident
        ]
        data["attempts"] = data.get("attempts") or [
            a for a in store.list_records("attempt", session_id) if a["run_id"] == ident
        ]
        return ok(request, data)

    @app.get("/api/versions/{ident}/modules")
    def modules(request: Request, ident: str):
        return ok(request, store.get("version", ident, sid(request, required=False)))

    @app.get("/api/versions/{ident}/diff")
    def diff(request: Request, ident: str, base_version_id: str):
        session_id = sid(request)
        a = store.get("version", base_version_id, session_id)
        b = store.get("version", ident, session_id)
        if (
            store.get("run", a["run_id"], session_id)["case_id"]
            != store.get("run", b["run_id"], session_id)["case_id"]
        ):
            raise DemoError("case_mismatch", "不能跨任务比较RTL版本。", 422)
        aa = art.version_path(a)
        bb = art.version_path(b)
        chunks = []
        names = sorted(
            set(x["path"] for x in a["file_manifest"])
            | set(x["path"] for x in b["file_manifest"])
        )
        for name in names:
            left = (
                (aa / name).read_text().splitlines(keepends=True)
                if (aa / name).is_file()
                else []
            )
            right = (
                (bb / name).read_text().splitlines(keepends=True)
                if (bb / name).is_file()
                else []
            )
            chunks.extend(
                difflib.unified_diff(
                    left, right, fromfile="before/" + name, tofile="after/" + name
                )
            )
        return ok(
            request,
            {
                "content": "".join(chunks),
                "base_version_id": base_version_id,
                "version_id": ident,
            },
        )

    @app.get("/api/validations/{ident}")
    def validation(request: Request, ident: str):
        return ok(request, store.get("validation", ident, sid(request, required=False)))

    @app.get("/api/validations/{ident}/waveform")
    def wave(
        request: Request,
        ident: str,
        start_ticks: str | None = None,
        end_ticks: str | None = None,
        signal_group: str = "key",
    ):
        session_id = sid(request, required=False)
        v = store.get("validation", ident, session_id)
        if signal_group != "key":
            raise DemoError("invalid_group", "首版只提供固定关键波形组。", 422)
        if not v.get("waveform_artifact_id"):
            raise DemoError("waveform_missing", "该次验证没有可用波形。", 404)
        try:
            start = int(start_ticks) if start_ticks is not None else None
            end = int(end_ticks) if end_ticks is not None else None
        except ValueError:
            raise DemoError("invalid_window", "时间必须为整数tick。", 422)
        a = store.get("artifact", v["waveform_artifact_id"], session_id)
        case_id = store.get("run", v["run_id"], session_id)["case_id"]
        fields = (
            bundle(case_id)["stats_fields"] if v["marker_status"] == "verified" else []
        )
        if start is None and end is None and v.get("waveform_index_artifact_id"):
            index = store.get("artifact", v["waveform_index_artifact_id"], session_id)
            meta = json.loads(art.file(index).read_text())
            if meta.get("tiled"):
                start = 0
                end = int(meta["tiles"][0]["end_ticks"])
        return ok(
            request,
            waveform_data(
                art.file(a),
                a["sha256"],
                fields,
                v,
                start,
                end,
                signal_names=settings.for_case(case_id).case["signals"],
            ),
        )

    @app.get("/api/artifacts/{ident}/content")
    def content(request: Request, ident: str):
        a = store.get("artifact", ident, sid(request, required=False))
        if a["exposure"] != "display":
            raise DemoError("private_artifact", "该产物不对演示页面开放。", 403)
        if a["size_bytes"] > 4 * 1024 * 1024:
            raise DemoError("artifact_too_large", "请使用对应的窗口接口。", 413)
        return ok(
            request,
            {
                "artifact_id": ident,
                "content": art.file(a).read_text(),
                "sha256": a["sha256"],
            },
        )

    @app.get("/api/sessions/{ident}/events")
    async def events(request: Request, ident: str, after: int = 0):
        session_id = sid(request, ident)
        try:
            cursor = int(request.headers.get("Last-Event-ID", after))
        except ValueError:
            raise DemoError("invalid_cursor", "事件游标无效。", 422)

        async def stream():
            nonlocal cursor
            heartbeat = time.monotonic()
            deadline = heartbeat + EVENT_STREAM_SECONDS
            # EventSource resumes with Last-Event-ID after a normal close.
            # Bound each connection's lifetime without losing durable events.
            yield "retry: 3000\n\n"
            while time.monotonic() < deadline and not await request.is_disconnected():
                items = store.events(session_id, cursor)
                for item in items:
                    cursor = item["event_id"]
                    yield "id: " + str(cursor) + "\nevent: " + item[
                        "type"
                    ] + "\ndata: " + json.dumps(
                        public(item), ensure_ascii=False
                    ) + "\n\n"
                if time.monotonic() - heartbeat >= 15:
                    heartbeat = time.monotonic()
                    yield ": heartbeat\n\n"
                await asyncio.sleep(0.25)

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app
