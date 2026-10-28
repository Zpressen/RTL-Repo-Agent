"""Exercise real HTTP keep-alives and SSE, the two sources of the outage."""
import asyncio
import socket

import httpx
import uvicorn
from starlette.applications import Starlette
from starlette.responses import JSONResponse, StreamingResponse
from starlette.routing import Route

from zerorepo.rtl_web.tunnel_gateway import RequestCapacity


def test_idle_connections_and_full_stream_lane_leave_pages_available():
    async def scenario():
        async def page(request):
            return JSONResponse({"ok": True})

        async def events(request):
            async def stream():
                while True:
                    yield ": heartbeat\n\n"
                    await asyncio.sleep(0.05)
            return StreamingResponse(stream(), media_type="text/event-stream")

        app = RequestCapacity(Starlette(routes=[Route("/", page),
            Route("/api/health", page), Route("/api/sessions/test/events", events)]))
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, log_level="error", timeout_graceful_shutdown=1))
        running = asyncio.create_task(server.serve(sockets=[sock]))
        clients, streams = [], []
        try:
            for _ in range(200):
                if server.started:
                    break
                await asyncio.sleep(0.01)
            assert server.started
            origin = f"http://127.0.0.1:{port}"
            # Each client retains its own idle TCP connection, beyond the old
            # global limit of 16. These must not count as active request work.
            clients = [httpx.AsyncClient(base_url=origin, timeout=5, trust_env=False) for _ in range(24)]
            responses = await asyncio.gather(*(c.get("/") for c in clients))
            assert all(r.status_code == 200 for r in responses)
            assert len(server.server_state.connections) >= 24
            stream_client = httpx.AsyncClient(base_url=origin, timeout=5, trust_env=False)
            clients.append(stream_client)
            for _ in range(16):
                streams.append(await stream_client.send(stream_client.build_request(
                    "GET", "/api/sessions/test/events"), stream=True))
            assert all(r.status_code == 200 for r in streams)
            overflow = await clients[0].get("/api/sessions/test/events")
            assert overflow.status_code == 429
            assert overflow.headers["retry-after"] == "3"
            assert (await clients[0].get("/")).status_code == 200
            assert (await clients[1].get("/api/health")).status_code == 200
            await streams.pop().aclose()
            for _ in range(200):
                if app.active["stream"] == 15:
                    break
                await asyncio.sleep(0.01)
            assert app.active["stream"] == 15
            streams.append(await stream_client.send(stream_client.build_request(
                "GET", "/api/sessions/test/events"), stream=True))
            assert streams[-1].status_code == 200
        finally:
            await asyncio.gather(*(r.aclose() for r in streams))
            await asyncio.gather(*(c.aclose() for c in clients))
            server.should_exit = True
            await asyncio.wait_for(running, 5)
            sock.close()
        assert app.active == {"request": 0, "stream": 0}

    asyncio.run(scenario())


def test_request_capacity_releases_cancelled_work_and_isolates_lanes():
    async def scenario():
        started, release = asyncio.Event(), asyncio.Event()

        async def block(scope, receive, send):
            started.set()
            await release.wait()

        app = RequestCapacity(block, requests=1, streams=1)
        async def receive():
            return {"type": "http.disconnect"}
        sent = []
        async def send(message):
            sent.append(message)
        scope = {"type": "http", "path": "/"}
        first = asyncio.create_task(app(scope, receive, send))
        await started.wait()
        await app(scope, receive, send)
        assert sent[0]["status"] == 429
        stream = asyncio.create_task(app({**scope, "path": "/api/sessions/x/events"}, receive, send))
        await asyncio.sleep(0)
        assert app.active == {"request": 1, "stream": 1}
        first.cancel()
        await asyncio.gather(first, return_exceptions=True)
        assert app.active["request"] == 0
        release.set()
        await stream
        assert app.active == {"request": 0, "stream": 0}

    asyncio.run(scenario())
