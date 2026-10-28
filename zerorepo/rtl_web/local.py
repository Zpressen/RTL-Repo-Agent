"""Start the real local demo services together; never used by production systemd."""

from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import shlex
import signal
import socket
import subprocess
import sys
import time
import urllib.request


def environment_file(path: Path) -> dict[str, str]:
    """Read KEY=value without executing shell substitutions or printing values."""
    values = {}
    for line_no, raw in enumerate(path.read_text().splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:]
        name, sep, value = line.partition("=")
        name, value = name.strip(), value.strip()
        if not sep or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise ValueError(f"环境文件第{line_no}行格式无效；请使用 KEY=value。")
        if value.startswith(("'", '"')):
            try:
                tokens = shlex.split(value, comments=True)
            except ValueError:
                raise ValueError(f"环境文件第{line_no}行引号未闭合。") from None
            if len(tokens) != 1:
                raise ValueError(f"环境文件第{line_no}行值无效。")
            value = tokens[0]
        values[name] = value
    return values


def free_port(port):
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            raise RuntimeError(
                f"本机{port}端口已占用，请先关闭原服务再统一启动。"
            ) from None


def stop(children):
    # Only process groups created by this launcher are signalled.
    for proc in reversed(children):
        if proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
    for proc in children:
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()


def main():
    from .settings import REPO, Settings

    parser = argparse.ArgumentParser(description="统一启动真实网页、API和单一worker")
    parser.add_argument("--config", default=str(REPO / "configs/rtl_demo.local.yaml"))
    parser.add_argument("--env-file", type=Path)
    parser.add_argument(
        "--no-web", action="store_true", help="已有Vite时仅启动API/worker"
    )
    parser.add_argument(
        "--require-chat", action="store_true", help="问答依赖未就绪则拒绝启动"
    )
    args = parser.parse_args()
    if args.env_file:
        os.environ.update(environment_file(args.env_file))
    settings = Settings(args.config)
    if not settings.development:
        parser.error("此命令仅用于本地development配置；服务器使用systemd和Caddy。")
    free_port(8000)
    if not args.no_web:
        free_port(5173)
    env = settings.tool_env()
    base = [sys.executable, "-m", "zerorepo.rtl_web.cli"]
    preflight = subprocess.run(
        [*base, "preflight", "--config", str(settings.config_path)],
        cwd=settings.repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if preflight.returncode:
        raise RuntimeError("运行环境预检失败，请检查现有Agent解释器和Web配置。")
    health = json.loads(preflight.stdout)
    if args.require_chat and not health["capabilities"]["chat"]["available"]:
        raise RuntimeError(
            "问答尚未就绪："
            + "、".join(health["capabilities"]["chat"]["missing"])
            + "；请通过--env-file传入现有模型凭据后重试。"
        )
    subprocess.run(
        [
            *base,
            "prepare-cases",
            "--config",
            str(settings.config_path),
            "--out",
            str(settings.repo / "web/rtl-demo/public/cases"),
        ],
        cwd=settings.repo,
        env=env,
        check=True,
    )
    children, logs = [], []
    try:
        commands = [
            (
                "worker",
                [
                    sys.executable,
                    "-m",
                    "zerorepo.rtl_web.worker",
                    "--config",
                    str(settings.config_path),
                ],
            ),
            (
                "api",
                [
                    *base,
                    "serve",
                    "--config",
                    str(settings.config_path),
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8000",
                ],
            ),
        ]
        if not args.no_web:
            commands.append(
                (
                    "web",
                    [
                        "npm",
                        "--prefix",
                        str(settings.repo / "web/rtl-demo"),
                        "run",
                        "dev",
                        "--",
                        "--host",
                        "127.0.0.1",
                        "--strictPort",
                    ],
                )
            )
        for name, command in commands:
            log_path = settings.data / (name + ".log")
            fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            os.chmod(log_path, 0o600)
            logs.append(os.fdopen(fd, "ab"))
            children.append(
                subprocess.Popen(
                    command,
                    cwd=settings.repo,
                    env=env,
                    stdout=logs[-1],
                    stderr=logs[-1],
                    start_new_session=True,
                )
            )
        deadline = time.monotonic() + 25
        ready = False
        while time.monotonic() < deadline:
            if any(p.poll() is not None for p in children):
                raise RuntimeError(
                    f"服务启动失败；请查看{settings.data}下的api.log/worker.log/web.log。"
                )
            try:
                url = (
                    "http://127.0.0.1:8000/api/health"
                    if args.no_web
                    else "http://127.0.0.1:5173/api/health"
                )
                with urllib.request.urlopen(url, timeout=1) as response:
                    health = json.load(response)
                if health["checks"].get("worker"):
                    ready = True
                    break
            except (OSError, ValueError):
                pass
            time.sleep(0.2)
        if not ready:
            raise RuntimeError("API/worker未在25秒内就绪，请检查本地服务日志。")
        print("真实API和worker已就绪。网页：http://127.0.0.1:5173/", flush=True)
        print(
            "问答依赖："
            + (
                "已就绪，仍需真实问答验收"
                if health["capabilities"]["chat"]["available"]
                else "未就绪：" + "、".join(health["capabilities"]["chat"]["missing"])
            ),
            flush=True,
        )
        print("Ctrl+C停止本次启动的服务。", flush=True)
        while True:
            if any(p.poll() is not None for p in children):
                raise RuntimeError(
                    "服务意外退出，正在停止本次启动的其他服务，请检查日志。"
                )
            time.sleep(0.5)
    finally:
        stop(children)
        for log in logs:
            log.close()


if __name__ == "__main__":

    def interrupted(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupted)
    try:
        main()
    except KeyboardInterrupt:
        pass
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
