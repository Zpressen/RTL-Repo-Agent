from __future__ import annotations
import os
import hashlib
import re
import time
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any
import yaml
from .schemas import DemoError

REPO = Path(__file__).resolve().parents[2]


class Settings:
    def __init__(self, config: str | Path | None = None, *, create_data: bool = True):
        self.config_path = Path(
            config
            or os.environ.get("RTL_DEMO_CONFIG", REPO / "configs/rtl_demo.example.yaml")
        ).resolve()
        try:
            self.raw: dict[str, Any] = yaml.safe_load(self.config_path.read_text()) or {}
        except yaml.YAMLError:
            raise ValueError('Invalid private runtime configuration') from None
        self.repo = (
            self.config_path.parent / self.raw.get("repo_root", "..")
        ).resolve()
        self.data = self.path(self.raw.get("data_root", ".rtl-demo"))
        if create_data:
            self.data.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.bundle_id = self.raw.get("bundle_id", "e203-demo-v1")
        self.development = (
            bool(self.raw.get("development", False))
            or os.environ.get("RTL_DEMO_DEVELOPMENT") == "1"
        )
        if self.raw.get('release_id') and os.environ.get('RTL_DEMO_DEVELOPMENT')=='1':
            raise ValueError('Production release cannot enable development bypass')
        self.gateway_key = os.environ.get("RTL_DEMO_GATEWAY_KEY", "")
        self.origins = set(
            self.raw.get("allowed_origins", ["https://design.deepvalleychip.cn"])
        )
        self.access_mode=self.raw.get('access_mode','public')
        if self.access_mode not in {'public','ssh_tunnel'}:raise ValueError('Unknown access mode')
        if self.access_mode=='ssh_tunnel':
            from urllib.parse import urlparse
            for origin in self.origins:
                url=urlparse(origin)
                if (url.scheme!='http' or url.hostname not in {'127.0.0.1','localhost','::1'}
                    or url.username or url.password or url.path or url.query or url.fragment):
                    raise ValueError('SSH preview requires loopback HTTP origins')
        self.secure_cookies=not self.development and self.access_mode!='ssh_tunnel'
        self.runtime = self.raw.get("runtime", {})
        self.memory_library = self.path(self.raw.get('memory_library', str(self.data/'memory-library')))
        self.bounded_chat = self.access_mode=='ssh_tunnel' or self.runtime.get('bounded_chat') is True
        from .cases import case_config

        self.case = {**case_config("e203"), **self.raw.get("case", {})}
        bindings=self.raw.get('cases', {})
        from .cases import CASES
        if not isinstance(bindings, dict) or set(bindings)-set(CASES):
            raise ValueError('Unknown deployment case')
        for binding in bindings.values():
            if set(binding)-{'bundle_id','spec'}:
                raise ValueError('Unsupported deployment override')
        self.case.update(bindings.get(self.case['case_id'], {}))
        self.bundle_id=self.case.get('bundle_id',self.bundle_id) if bindings else self.bundle_id
        self.release_id=self.raw.get('release_id','development')
        self.budgets=self.raw.get('budgets',{})
        self.python = shutil.which(
            str(self.runtime.get("python", sys.executable))
        ) or str(self.runtime.get("python", sys.executable))
        self.oracle = (
            self.path(self.runtime["oracle_root"])
            if self.runtime.get("oracle_root")
            else None
        )
        self.spec = self.path(
            self.case.get(
                "spec", "rtl_dataset/e203_exu_alu_hard/e203_exu_alu_system.md"
            )
        )
        self.agent_config = self.path(
            self.runtime.get("agent_config", "configs/zerorepo_config.yaml")
        )
        self.source = self.path(
            self.raw.get("source_output", "rtl_outputs/e203_exu_alu_system")
        )
        self.timeout = int(self.runtime.get("timeout", 10800))
        self.chat_timeout = int(self.runtime.get("chat_timeout", 120))
        self.verifier_timeout = int(self.runtime.get("verifier_timeout", 300))

    def for_case(self, case_id):
        base = getattr(self, "_base_settings", self)
        if case_id == base.case["case_id"]:
            return base
        from copy import copy
        from .cases import case_config

        selected = copy(base)
        selected._base_settings = base
        selected.case = {**case_config(case_id), **base.raw.get('cases',{}).get(case_id,{})}
        selected.source = self.path(selected.case["source_output"])
        selected.spec = self.path(selected.case["spec"])
        selected.bundle_id = selected.case["bundle_id"]
        return selected

    @property
    def reference_dirs(self):
        return (
            [self.oracle / name for name in self.case["reference_roots"]]
            if self.oracle
            else []
        )

    def path(self, value: str | Path) -> Path:
        p = Path(value).expanduser()
        return p.resolve() if p.is_absolute() else (self.repo / p).resolve()

    @property
    def verify_script(self) -> Path | None:
        if self.oracle is None:
            return None
        return (
            self.oracle
            / "system_task"
            / self.case.get("project_hint", "e203_exu_alu_hard")
            / "verify_test"
            / self.case["verify_filename"]
        )

    def tool_env(self) -> dict[str, str]:
        env = dict(os.environ)
        if self.oracle:
            env['ZEROREPO_DEPLOY_ORACLE_ROOT']=str(self.oracle)
            env['ZEROREPO_DEPLOY_COMPILE_JOBS']=str(int(self.runtime.get('compile_jobs',1)))
        if self.runtime.get("toolchain_bin"):
            env["PATH"] = (
                str(self.path(self.runtime["toolchain_bin"]))
                + os.pathsep
                + env.get("PATH", "")
            )
            env['ZEROREPO_DEPLOY_TOOLCHAIN_BIN']=str(self.path(self.runtime['toolchain_bin']))
        env["PYTHONPATH"] = str(self.repo) + os.pathsep + env.get("PYTHONPATH", "")
        if self.runtime.get('parser_library'):
            env['RTL_TS_LANG_SO']=str(self.path(self.runtime['parser_library']))
        return env

    def preflight(self, probe_runtime: bool = False, *, candidate: bool = False) -> dict[str, Any]:
        env = self.tool_env()
        verifier_ok = bool(self.verify_script and self.verify_script.is_file())
        full_oracle = bool(self.oracle and all(p.is_dir() for p in self.reference_dirs))
        verilator = bool(shutil.which("verilator", path=env.get("PATH")))
        compiler = bool(shutil.which("g++", path=env.get("PATH")))
        config_ok = self.agent_config.is_file()
        checks: dict[str, Any] = {
            "bundle": (
                self.data / "bundles" / self.bundle_id / "manifest.json"
            ).is_file(),
            "runtime_python": Path(self.python).is_file(),
            "agent_config": config_ok,
            "verifier": verifier_ok,
            "reference_resources": full_oracle,
            "verilator": verilator,
            "compiler": compiler,
            "spec": self.spec.is_file(),
        }
        runtime_check = self.data / ("runtime-preflight-"+self.case["case_id"]+".json")
        agent_bytes = self.agent_config.read_bytes() if config_ok else b""
        refs = set(re.findall(rb"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", agent_bytes))
        refs.update(
            k.encode()
            for k in (
                "OPENAI_API_KEY",
                "ANTHROPIC_API_KEY",
                "AZURE_OPENAI_API_KEY",
                "GOOGLE_API_KEY",
            )
        )
        presence = str(
            sorted((k.decode(), bool(env.get(k.decode()))) for k in refs)
        ).encode()
        signature = hashlib.sha256(
            self.config_path.read_bytes()
            + agent_bytes
            + presence
            + str(self.python).encode()
            + self.release_id.encode() + self.case['case_id'].encode()
            + str(self.oracle).encode()
            + (self.spec.read_bytes() if self.spec.is_file() else b'missing_spec')
            + (self.verify_script.read_bytes() if self.verify_script and self.verify_script.is_file() else b'missing_verifier')
            + repr([(name, str(shutil.which(name,path=env.get('PATH'))),
                     (Path(p).stat().st_mtime_ns,Path(p).stat().st_size) if (p:=shutil.which(name,path=env.get('PATH'))) else None)
                    for name in ['verilator','g++','codex','bwrap']]).encode()
        ).hexdigest()
        if probe_runtime:
            try:
                proc = subprocess.run(
                    [
                        self.python,
                        "-m",
                        "zerorepo.rtl_web.runtime",
                        "--probe",
                        "--config",
                        str(self.config_path),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=45,
                    env=env,
                    cwd=self.repo,
                )
                checks["runtime_probe"] = proc.returncode == 0
                if proc.returncode == 0:
                    import json

                    checks.update(json.loads(proc.stdout.splitlines()[-1]))
            except (OSError, subprocess.TimeoutExpired, ValueError):
                checks["runtime_probe"] = False
            import json

            from .artifacts import atomic_json

            atomic_json(
                runtime_check,
                {"signature": signature, "checked_at": time.time(), "checks": checks},
            )
        elif runtime_check.is_file():
            import json

            try:
                cached = json.loads(runtime_check.read_text())
                stale=time.time()-cached.get('checked_at',0)>3600
                if cached.get("signature") != signature:
                    cached = {}
                elif stale:
                    # The private preview can retain static import/credential
                    # presence facts for the same immutable release/config.
                    # Live execution/KG readiness still expires normally.
                    cached['checks']={k:v for k,v in cached.get('checks',{}).items()
                                      if self.bounded_chat and k in {'chat_import','model_credentials'}}
                checks.update(
                    {
                        k: v
                        for k, v in cached.get("checks", {}).items()
                        if k
                        in {
                            "runtime_probe",
                            "kg",
                            "backend",
                            "chat_import",
                            "model_credentials",
                            "backend_cli",
                            "backend_auth",
                            "backend_profile",
                        }
                    }
                )
            except ValueError:
                pass

        def capability(keys: list[str]) -> dict[str, Any]:
            missing = [k for k in keys if not checks.get(k)]
            return {"available": not missing, "missing": missing}

        capabilities = {
            "replay": capability(["bundle"]),
            "chat": capability(
                ["runtime_python", "agent_config", "chat_import", "model_credentials"]
            ),
            "verify": capability(
                [
                    "runtime_python",
                    "verifier",
                    "reference_resources",
                    "verilator",
                    "compiler",
                    "runtime_probe",
                ]
            ),
            "generate": capability(
                [
                    "runtime_python",
                    "agent_config",
                    "spec",
                    "verifier",
                    "reference_resources",
                    "verilator",
                    "compiler",
                    "runtime_probe",
                    "kg",
                    "backend",
                    "model_credentials",
                ]
            ),
            "fix": capability(
                [
                    "runtime_python",
                    "agent_config",
                    "spec",
                    "verifier",
                    "reference_resources",
                    "verilator",
                    "compiler",
                    "runtime_probe",
                    "kg",
                    "backend",
                    "model_credentials",
                ]
            ),
        }
        heartbeat = self.data / "worker.heartbeat"
        checks["worker"] = (
            heartbeat.is_file() and time.time() - heartbeat.stat().st_mtime < 15
        )
        checks['api_release']=self.repo==REPO
        checks['worker_release']=False
        import json
        try:
            worker=json.loads((self.data/'worker-state.json').read_text())
            checks['worker_release']=(worker['release_id']==self.release_id
                and worker['code_root']==str(self.repo) and time.time()-worker['checked_at']<15)
        except (OSError,ValueError,KeyError):pass
        if not self.development:
            from .budgets import production_checks
            from .sandbox import native_probe
            extra=production_checks(self)
            extra['sandbox']=native_probe()
            checks.update(extra)
            for name,cap in capabilities.items():
                if not checks['api_release']:
                    cap['missing'].append('api_release')
                if name in {'verify','generate','fix'} and not candidate and not checks['worker_release']:
                    cap['missing'].append('worker_release')
                if name in {'verify','generate','fix'} and not candidate:
                    cap['missing'].extend(k for k,v in extra.items() if not v)
                if name=='chat' and not candidate:
                    cap['missing'].extend(k for k in ['disk_space','sandbox'] if not extra[k])
                    if self.bounded_chat:
                        from .budgets import bounded_chat_memory_ready
                        checks['chat_memory_budget']=bounded_chat_memory_ready()
                        if not checks['chat_memory_budget']:cap['missing'].append('chat_memory_budget')
                    elif not extra['memory_budget']:cap['missing'].append('memory_budget')
                cap['available']=not cap['missing']
        for name in ["verify", "generate", "fix"]:
            if not checks["worker"]:
                capabilities[name]["available"] = False
                capabilities[name]["missing"].append("worker")
        if candidate:
            for cap in capabilities.values():
                cap['missing']=[x for x in cap['missing'] if x!='worker']
                cap['available']=not cap['missing']
        for cap in capabilities.values():
            cap.update(readiness='ready' if cap['available'] else 'blocked',acceptance='not_run')
        return {"status": "ok", "release_id": self.release_id,
                "phase":'candidate' if candidate else ('ssh_preview' if self.access_mode=='ssh_tunnel' else 'production'),
                "checked_at":time.time(),"capabilities": capabilities, "checks": checks}

    def require(self, kind: str) -> None:
        name = "generate" if kind == "generate_and_verify" else kind
        cap = self.preflight()["capabilities"][name]
        if not cap["available"]:
            names = {
                "model_credentials": "模型凭据未配置",
                "kg": "知识图谱服务未连接",
                "worker": "执行服务未启动",
                "verifier": "验证资源未配置",
                "reference_resources": "参考设计不完整",
                "verilator": "仿真工具未就绪",
                "compiler": "编译工具未就绪",
                "runtime_python": "Agent环境未就绪",
                "agent_config": "Agent配置未就绪",
                "runtime_probe": "请先运行能力预检",
                "chat_import": "问答依赖未就绪",
                "backend": "现有Agent后端未就绪",
                "worker_release": "执行服务版本未同步",
                "api_release": "网页服务版本未同步",
                "job_volume": "任务存储限制未配置",
                "cgroup_memory": "执行内存限制未生效",
                "cgroup_cpu": "执行CPU限制未生效",
                "cgroup_tasks": "执行进程数限制未生效",
                "memory_budget": "完整执行的内存预算不足",
                "chat_memory_budget": "当前内存余量不足以启动问答",
                "disk_space": "可用磁盘空间不足",
                "sandbox": "任务隔离环境未就绪",
                "spec": "规格缺失",
            }
            raise DemoError(
                "dependency_unavailable",
                "当前能力未就绪：" + "、".join(names.get(k, k) for k in cap["missing"]),
                503,
            )
