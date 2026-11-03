from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from contextlib import suppress
from pathlib import Path
from typing import Any, Literal

import anyio
import mcp.types as mcp_types
from mcp.server.fastmcp import FastMCP
from mcp.shared.message import SessionMessage
from mcp.types import ToolAnnotations

from .session import CodexDebugSession


SERVER_INSTRUCTIONS = """
This server provides task-scoped RTL debugging tools. Codex may read and edit
only the visible spec/ and merged/ trees. After native RTL edits, call
validate_rtl_changes(action="evaluate"). Review the objective lint, simulation,
trace, and metric evidence, then explicitly accept or rollback the candidate.
Do not use expected/reference values as RTL constants.
""".strip()

mcp = FastMCP(
    "zerorepo-rtl-debug",
    instructions=SERVER_INSTRUCTIONS,
    log_level="WARNING",
)

_SESSION: CodexDebugSession | None = None


def configure_session(session: CodexDebugSession) -> None:
    global _SESSION
    _SESSION = session


async def _call(method: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
    if os.environ.get('ZEROREPO_TOOL_BRIDGE'):
        from zerorepo.rtl_impl.runtime_integration import workbench_integration
        return await asyncio.to_thread(workbench_integration().bridge_call,method,args,kwargs)
    if _SESSION is None:
        return {"status": "server_uninitialized", "tool": method}
    try:
        fn = getattr(_SESSION, method)
        result = await asyncio.to_thread(fn, *args, **kwargs)
        return result if isinstance(result, dict) else {"status": "ok", "result": result}
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "tool_error",
            "tool": method,
            "error": f"{type(exc).__name__}: {exc}",
        }


READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
OBSERVATION = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=False, openWorldHint=False)
TRANSACTION = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)

@mcp.tool(description='Query only the frozen, authorized RTL experience snapshot. A hit is not adoption.', annotations=OBSERVATION, structured_output=True)
async def query_rtl_memories(module_name: str | None = None, signals: list[str] | None = None, failure_type: str | None = None, limit: int = 5) -> dict[str, Any]:
    return await _call('query_rtl_memories', module_name, signals, failure_type, limit)

@mcp.tool(description='Read one authorized immutable experience revision and its limitations.', annotations=OBSERVATION, structured_output=True)
async def read_rtl_memory(revision_id: str, max_chars: int = 8000) -> dict[str, Any]:
    return await _call('read_rtl_memory', revision_id, max_chars)

@mcp.tool(description='Declare apply/reject/not_applicable for a provided memory. This declaration is not proof of adoption or PASS.', annotations=TRANSACTION, structured_output=True)
async def record_memory_application(revision_id: str, decision: Literal['apply','reject','not_applicable'], reason: str, target_files: list[str] | None = None, target_signals: list[str] | None = None) -> dict[str, Any]:
    return await _call('record_memory_application',revision_id,decision,reason,target_files,target_signals)


@mcp.tool(
    description="Read focused module planning semantics (spec, skeleton, and plan) with current RTL block alignment.",
    annotations=READ_ONLY,
    structured_output=True,
)
async def read_module_semantics(
    module_name: str,
    sections: list[str] | None = None,
    focus_signals: list[str] | None = None,
    focus_blocks: list[str] | None = None,
    max_chars: int = 12000,
) -> dict[str, Any]:
    return await _call(
        "read_module_semantics",
        module_name,
        sections,
        focus_signals,
        focus_blocks,
        max_chars,
    )


@mcp.tool(
    description="Query the task-scoped RTL KG through fixed templates for interfaces, hierarchy, connections, or signal drivers.",
    annotations=READ_ONLY,
    structured_output=True,
)
async def query_rtl_kg(
    query_type: Literal["module_interface", "module_instances", "instance_connections", "signal_drivers"],
    module_name: str,
    signal_name: str | None = None,
    instance_name: str | None = None,
) -> dict[str, Any]:
    return await _call("query_rtl_kg", query_type, module_name, signal_name, instance_name)


@mcp.tool(
    description="Trace one signal through current RTL drivers, waveform evidence, and module/port boundaries.",
    annotations=OBSERVATION,
    structured_output=True,
)
async def trace_signal_cause(
    module_name: str,
    signal_name: str,
    time: int | None = None,
    expected_value: str | None = None,
    max_candidates: int = 5,
) -> dict[str, Any]:
    return await _call(
        "trace_signal_cause",
        module_name,
        signal_name,
        time,
        expected_value,
        max_candidates,
    )


@mcp.tool(
    description="List VCD signal names matching an optional pattern and hierarchy scope for the active evidence revision.",
    annotations=READ_ONLY,
    structured_output=True,
)
async def list_vcd_signals(pattern: str = "", scope: str = "", limit: int = 100) -> dict[str, Any]:
    return await _call("list_vcd_signals", pattern, scope, limit)


@mcp.tool(
    description="Sample VCD signals at a time or over a window for the active accepted or validated candidate revision.",
    annotations=READ_ONLY,
    structured_output=True,
)
async def probe_vcd(
    signals: list[str],
    time: int | None = None,
    time_range: list[int] | None = None,
    edge: str | None = None,
    mode: Literal["sample", "changes"] = "sample",
    max_rows: int = 80,
) -> dict[str, Any]:
    return await _call("probe_vcd", signals, time, time_range, edge, mode, max_rows)


@mcp.tool(
    description="Run an observation check; lint/top_sim require a clean accepted baseline, while trace modes use active revision evidence.",
    annotations=OBSERVATION,
    structured_output=True,
)
async def run_check(
    mode: Literal["lint", "top_sim", "trace_summary", "first_divergence"],
    signals: list[str] | None = None,
    time_window: list[int] | None = None,
) -> dict[str, Any]:
    return await _call("run_check", mode, signals, time_window)


@mcp.tool(
    description=(
        "Manage native Codex RTL edits transactionally. Use action=evaluate after edits, then explicitly "
        "accept or rollback the returned candidate_id."
    ),
    annotations=TRANSACTION,
    structured_output=True,
)
async def validate_rtl_changes(
    action: Literal["evaluate", "accept", "rollback"],
    candidate_id: str | None = None,
    reason: str = "",
    expected_effect: str = "",
) -> dict[str, Any]:
    return await _call("validate_rtl_changes", action, candidate_id, reason, expected_effect)


@mcp.tool(
    description="Return the current baseline/candidate phase, latest metrics, advisory trace hint, statistics, and allowed next actions.",
    annotations=READ_ONLY,
    structured_output=True,
)
async def get_debug_status() -> dict[str, Any]:
    return await _call("get_debug_status")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the ZeroRepo RTL Debug MCP server over stdio.")
    parser.add_argument('--bridge',action='store_true')
    parser.add_argument(
        "--run-descriptor",
        default=os.environ.get("ZEROREPO_CODEX_DEBUG_RUN_DESCRIPTOR", ""),
        help="Private CodexDebugRunDescriptor JSON path.",
    )
    return parser.parse_args(argv)


async def _run_stdio() -> None:
    """Run stdio without ``anyio.wrap_file``.

    The MCP 1.12 stdio helper can block forever while reading a pipe on
    Python 3.13 with newer AnyIO releases.  Codex always starts this server
    behind pipes, so use asyncio's native pipe reader and retain MCP's normal
    in-memory message streams and protocol server.
    """

    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    transport, _ = await loop.connect_read_pipe(lambda: protocol, sys.stdin)
    incoming_send, incoming_receive = anyio.create_memory_object_stream(0)
    outgoing_send, outgoing_receive = anyio.create_memory_object_stream(0)

    async def read_stdin() -> None:
        async with incoming_send:
            while line := await reader.readline():
                try:
                    message = mcp_types.JSONRPCMessage.model_validate_json(line)
                    await incoming_send.send(SessionMessage(message))
                except Exception as exc:  # noqa: BLE001
                    await incoming_send.send(exc)

    async def write_stdout() -> None:
        async with outgoing_receive:
            async for session_message in outgoing_receive:
                payload = session_message.message.model_dump_json(by_alias=True, exclude_none=True)
                sys.stdout.write(payload + "\n")
                sys.stdout.flush()

    reader_task = asyncio.create_task(read_stdin())
    writer_task = asyncio.create_task(write_stdout())
    try:
        await mcp._mcp_server.run(  # noqa: SLF001 - pinned MCP compatibility shim
            incoming_receive,
            outgoing_send,
            mcp._mcp_server.create_initialization_options(),  # noqa: SLF001
        )
    finally:
        reader_task.cancel()
        writer_task.cancel()
        for task in (reader_task, writer_task):
            with suppress(asyncio.CancelledError):
                await task
        transport.close()


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if not args.run_descriptor and not args.bridge:
        print("Missing --run-descriptor or ZEROREPO_CODEX_DEBUG_RUN_DESCRIPTOR.", file=sys.stderr)
        return 2
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    descriptor_path = Path(args.run_descriptor).resolve()
    session: CodexDebugSession | None = None
    try:
        if args.bridge:
            if not os.environ.get('ZEROREPO_TOOL_BRIDGE'):
                raise ValueError('Missing private tool bridge')
            asyncio.run(_run_stdio())
            return 0
        session = CodexDebugSession.from_descriptor_path(descriptor_path)
        configure_session(session)
        asyncio.run(_run_stdio())
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"ZeroRepo RTL Debug MCP startup failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        if session is not None:
            session.close()


if __name__ == "__main__":
    raise SystemExit(main())
