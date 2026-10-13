"""Per-call budgets and durable progress; independent of planner artifact schemas."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import tempfile
import time
from typing import Callable
from uuid import uuid4


@dataclass(frozen=True)
class LLMRequestOptions:
    total_timeout_seconds: float = 600
    first_content_timeout_seconds: float = 120
    idle_timeout_seconds: float = 120
    progress_interval_seconds: float = 30
    slow_window_seconds: float = 120
    slow_chars_per_second: float = 2
    max_retries: int = 1
    retry_first_content_timeout: bool = False
    max_tokens: int | None = None
    stage: str = ""
    module: str = ""
    repair_attempt: int = 1
    draft_root: str | Path | None = None
    progress_callback: Callable[[dict], None] | None = None

    def __post_init__(self):
        for name in ("total_timeout_seconds", "first_content_timeout_seconds", "idle_timeout_seconds",
                     "progress_interval_seconds", "slow_window_seconds"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if self.max_retries < 0 or self.max_tokens is not None and self.max_tokens < 1:
            raise ValueError("Invalid request retry/token budget")


def atomic_text(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


class RequestProgress:
    def __init__(self, options, log=True):
        self.options = options
        self.log = log
        self.started = time.monotonic()
        self.deadline = self.started + options.total_timeout_seconds
        self.request_id = uuid4().hex
        self.status = "started"
        self.phase = "awaiting_headers"
        self.attempt = 0
        self.text = ""
        self.chunks = 0
        self.effective_chars = 0
        self.first_content = None
        self.last_content = self.started
        self.attempt_started = self.started
        self.samples = deque([(self.started, 0)])
        self.next_progress = self.started + options.progress_interval_seconds
        self.diagnostics = {}
        safe = lambda value: re.sub(r"[^A-Za-z0-9_.-]", "_", value).strip(".") or "unknown"
        self.directory = (Path(options.draft_root) / safe(options.stage) / safe(options.module) / self.request_id
                          if options.draft_root is not None else None)

    def begin_attempt(self):
        self.diagnostics = {}
        self.attempt += 1
        self.text = ""
        self.chunks = 0
        self.effective_chars = 0
        self.first_content = None
        self.attempt_started = self.last_content = time.monotonic()
        self.samples = deque([(self.attempt_started, 0)])
        self.phase = "awaiting_headers"
        self.status = "running"
        self.publish()

    def content(self, text):
        self.chunks += 1
        if text:
            self.text += text
        # Preserve whitespace verbatim, but it is not evidence that generation
        # has started or is progressing. Heartbeats cannot extend a deadline.
        if text and text.strip():
            now = time.monotonic()
            if self.first_content is None:
                self.first_content = now
            self.last_content = now
            self.effective_chars += len(text)
            self.phase = "streaming"
            self.samples.append((now, self.effective_chars))

    def publish(self, status=None):
        if status:
            self.status = status
        now = time.monotonic()
        cutoff = now - self.options.slow_window_seconds
        while len(self.samples) > 1 and self.samples[1][0] <= cutoff:
            self.samples.popleft()
        first, count = self.samples[0]
        rate = (self.effective_chars - count) / max(now - first, 0.001)
        slow = (self.first_content is not None and now - self.first_content >= self.options.slow_window_seconds
                and rate < self.options.slow_chars_per_second)
        snapshot = {
            "request_id": self.request_id, "stage": self.options.stage, "module": self.options.module,
            "repair_attempt": self.options.repair_attempt, "attempt": self.attempt,
            "status": self.status, "waiting_phase": self.phase, "chunks": self.chunks,
            "content_chars": len(self.text), "elapsed_seconds": round(now - self.started, 3),
            "effective_content_chars": self.effective_chars,
            "attempt_elapsed_seconds": round(now - self.attempt_started, 3),
            "first_content_timeout_seconds": self.options.first_content_timeout_seconds,
            "idle_timeout_seconds": self.options.idle_timeout_seconds,
            "remaining_seconds": round(max(0, self.deadline - now), 3),
            "recent_chars_per_second": round(rate, 3), "slow": slow, **self.diagnostics,
        }
        if self.directory is not None:
            atomic_text(self.directory / f"attempt_{self.attempt}.partial.txt", self.text)
            atomic_text(self.directory / "status.json", json.dumps(snapshot, ensure_ascii=False, indent=2))
            atomic_text(self.directory / f"attempt_{self.attempt}.status.json", json.dumps(snapshot, ensure_ascii=False, indent=2))
        if self.log:
            print("[LLMClient] " + ("Slow stream: " if slow else "Request progress: ") +
                  json.dumps(snapshot, ensure_ascii=False), flush=True)
        if self.options.progress_callback is not None:
            self.options.progress_callback({**snapshot, "content": self.text})
        self.next_progress = now + self.options.progress_interval_seconds

    def timeout(self):
        now = time.monotonic()
        if now >= self.deadline:
            return "total_timeout"
        if self.phase == "retry_delay":
            return None
        if self.first_content is None and now - self.attempt_started >= self.options.first_content_timeout_seconds:
            return "first_content_timeout"
        if self.first_content is not None and now - self.last_content >= self.options.idle_timeout_seconds:
            return "content_idle_timeout"
        return None

    def next_wakeup(self):
        content_deadline = (self.attempt_started + self.options.first_content_timeout_seconds
                            if self.first_content is None else self.last_content + self.options.idle_timeout_seconds)
        if self.phase == "retry_delay":
            content_deadline = self.deadline
        return max(0.001, min(self.deadline, content_deadline, self.next_progress) - time.monotonic())
