from __future__ import annotations

import asyncio
import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from zerorepo.rtl_impl.artifact_layout import ArtifactLayout
from typing import Any

from agentscope.memory import InMemoryMemory
from agentscope.message import Msg
from agentscope.tool import ToolResponse, Toolkit

from zerorepo.rtl_impl.debug_agent.agents import SafeReActAgent, clear_memory_safely
from zerorepo.rtl_impl.debug_agent.sim_reviewer import check_syntax
from zerorepo.rtl_impl.debug_agent.trace_slicer import parse_rtl_blocks
from zerorepo.rtl_impl.process_observer import observed


_PREPROCESSOR_CONTROL_DIRECTIVES = {
    "begin_keywords",
    "celldefine",
    "default_nettype",
    "define",
    "else",
    "elsif",
    "end_keywords",
    "endcelldefine",
    "endif",
    "ifdef",
    "ifndef",
    "include",
    "line",
    "nounconnected_drive",
    "pragma",
    "resetall",
    "timescale",
    "unconnected_drive",
    "undef",
    "undefineall",
}
_PREDEFINED_MACROS = {"__FILE__", "__LINE__"}
_MACRO_TOKEN_RE = re.compile(r"`([A-Za-z_][A-Za-z0-9_$]*)")
_DEFINE_RE = re.compile(r"^\s*`define\s+([A-Za-z_][A-Za-z0-9_$]*)(?:\s*\([^\n)]*\))?(?P<body>.*)$")
_INCLUDE_RE = re.compile(r'^\s*`include\s+"([^"]+)"', re.MULTILINE)


# ---------------------------------------------------------------------------
# 保留的工具函数
# ---------------------------------------------------------------------------

def _clip(text: Any, max_chars: int = 12000) -> str:
    value = text if isinstance(text, str) else str(text)
    if len(value) <= max_chars:
        return value
    half = max(1, max_chars // 2)
    return value[:half] + "\n...<snip>...\n" + value[-half:]


def _extract_verilog_code(raw: str) -> str:
    text = raw if isinstance(raw, str) else str(raw)
    fenced = re.search(r"```(?:systemverilog|verilog|sv)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fenced:
        text = fenced.group(1)
    lines = []
    for line in text.splitlines():
        if line.strip().startswith("```"):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def _strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//.*", "", text)
    return text


def _assigned_signals(text: str) -> list[str]:
    clean = _strip_comments(text)
    signals: set[str] = set()
    for match in re.finditer(r"\b([A-Za-z_][A-Za-z0-9_$]*)\b\s*(?:\[[^\]]+\])?\s*(?:<=|(?<![=!<>])=(?![=]))", clean):
        lhs = match.group(1)
        if lhs not in {"if", "for", "while", "case", "assign"}:
            signals.add(lhs)
    return sorted(signals)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _tool_schema(name: str, description: str, properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    """构建 OpenAI function-calling 兼容的 JSON Schema。"""
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required or [],
            },
        },
    }


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

@dataclass
class SemanticMergeState:
    """跨 ReAct 步骤的共享状态。"""
    # 路径
    artifact_layout: ArtifactLayout
    module_name: str
    merged_file: Path           # Final output path (merged/{module}.v)
    draft_file: Path            # Temporary draft path outside merged/
    fragment_file: Path         # Stage5 输出
    contracts_file: Path | None
    global_defines_manifest: dict[str, Any]
    required_includes: list[str]
    lint_support_files: list[str] = field(default_factory=list)
    module_spec: str = ""
    module_skeleton: str = ""
    module_plan: str = ""
    kg_child_context: str = ""
    global_defines_context: str = ""

    # 跟踪
    action_calls: int = 0
    draft_generated: bool = False
    draft_committed: bool = False

    # 证据门控
    observed_fragments: bool = False
    observed_spec: bool = False
    observed_global_defines: bool = False
    observed_kg_child: bool = False
    observed_structure: bool = False

    # 上次检查结果
    last_static_check: dict[str, Any] = field(default_factory=dict)
    last_lint: dict[str, Any] = field(default_factory=dict)
    last_structure: dict[str, Any] = field(default_factory=dict)

    # Journal
    journal: Any = None


# ---------------------------------------------------------------------------
# Journal
# ---------------------------------------------------------------------------

class MergeJournal:
    """文件级日志，和 RepoReActJournal 相同模式。"""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "snapshots").mkdir(parents=True, exist_ok=True)

    def append_jsonl(self, name: str, payload: dict[str, Any]) -> None:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def write_json(self, relative_path: str, payload: dict[str, Any]) -> Path:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return path

    def snapshot_files(self, *, step: int, label: str, files: list[Path]) -> str:
        snap_dir = self.root / "snapshots" / f"step_{int(step):03d}_{label}"
        if snap_dir.exists():
            shutil.rmtree(snap_dir)
        snap_dir.mkdir(parents=True, exist_ok=True)
        for path in files:
            if not path.is_file():
                continue
            shutil.copyfile(path, snap_dir / path.name)
        return str(snap_dir)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

class Stage6MergeTools:
    """Stage6 Semantic Merge 的 6 个工具实现。每个工具返回 dict[str, Any]。"""

    def __init__(self, state: SemanticMergeState, *, logger: Any | None = None) -> None:
        self.state = state
        self.logger = logger

    # ---- 路径辅助 ----

    def _resolve_target_path(self, target: str) -> Path | None:
        if target == "draft":
            return self.state.draft_file
        if target == "merged":
            return self.state.merged_file
        return None

    def _read_target(self, target: str) -> str:
        path = self._resolve_target_path(target)
        if path is None or not path.is_file():
            return ""
        return path.read_text(encoding="utf-8", errors="replace")

    # ---- 工具: read_merge_context ----

    @observed('tool', '读取RTL合并所需材料', tool='read_context',
              summarize=lambda r: f'已读取材料，正文{len(r.get("content") or "")}字。' if r.get('status')=='ok' else '材料读取未完成。')
    def read_merge_context(self, kind: str, max_chars: int = 12000) -> dict[str, Any]:
        ctx = self.state
        result: dict[str, Any] = {"status": "ok", "kind": kind, "module": ctx.module_name}

        if kind == "fragments":
            text = ctx.fragment_file.read_text(encoding="utf-8", errors="replace") if ctx.fragment_file.is_file() else ""
            result["content"] = _clip(text, max_chars)
            self.state.observed_fragments = True

        elif kind == "fragment_contracts":
            contracts = _read_json(ctx.contracts_file) if ctx.contracts_file else {}
            result["contracts"] = contracts
            self.state.observed_fragments = True

        elif kind == "module_plan":
            result["content"] = _clip(ctx.module_plan, max_chars)

        elif kind == "module_skeleton":
            result["content"] = _clip(ctx.module_skeleton, max_chars)

        elif kind == "spec":
            result["content"] = _clip(ctx.module_spec, max_chars)
            self.state.observed_spec = True

        elif kind == "kg_child_context":
            result["content"] = _clip(ctx.kg_child_context, max_chars)
            self.state.observed_kg_child = True

        elif kind == "global_defines":
            result["manifest"] = ctx.global_defines_manifest
            result["required_includes"] = ctx.required_includes
            result["content"] = _clip(ctx.global_defines_context, max_chars)
            self.state.observed_global_defines = True

        elif kind == "learned_merge_rules":
            rules = self._load_learned_rules()
            result["rules"] = rules
            result["rule_count"] = len(rules)

        else:
            result["status"] = "error"
            result["error"] = f"Unknown kind: {kind}. Valid: fragments, fragment_contracts, module_plan, module_skeleton, spec, kg_child_context, global_defines, learned_merge_rules"

        return result

    def _load_learned_rules(self) -> list[dict[str, Any]]:
        """加载前序模块的 merge report 作为跨模块经验。"""
        reports_dir = self.state.artifact_layout.directory("merge_reports")
        if not reports_dir.is_dir():
            return []
        rules: list[dict[str, Any]] = []
        for report_path in sorted(reports_dir.glob("*.json")):
            # 跳过当前模块自己的报告
            if report_path.stem == self.state.module_name:
                continue
            try:
                report = json.loads(report_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(report, dict):
                continue
            summary = {
                "module": report.get("module", report_path.stem),
                "required_includes": report.get("required_includes", []),
                "static_check_errors": (report.get("static_check_summary") or {}).get("errors", []),
                "static_check_warnings": (report.get("static_check_summary") or {}).get("warnings", []),
                "lint_passed": (report.get("lint_summary") or {}).get("is_pass", False),
            }
            rules.append(summary)
        return rules

    # ---- 工具: inspect_rtl_structure ----

    @observed('tool', '分析RTL声明、结构块与驱动关系', tool='inspect_rtl_structure', registered_tool=False,
              summarize=lambda r: f'识别{r.get("module_count",0)}个模块声明、{len(r.get("blocks") or [])}个结构块、{len(r.get("outputs") or [])}个输出。' if r.get('status')=='ok' else 'RTL结构读取未完成。')
    def inspect_rtl_structure(self, target: str = "draft") -> dict[str, Any]:
        text = self._read_target(target)
        if not text.strip():
            return {"status": "missing_target", "target": target, "error": f"No RTL found for target '{target}'."}

        includes = re.findall(r'^\s*`include\s+"([^"]+)"', text, flags=re.MULTILINE)
        module_count = len(re.findall(r"^\s*module\s+\w+", text, flags=re.MULTILINE))
        outputs = self._extract_outputs(text)
        declarations = sorted(set(re.findall(
            r"\b(?:wire|reg|integer)\s+(?:\[[^\]]+\]\s*)?([A-Za-z_][A-Za-z0-9_$]*)", text
        )))

        blocks = []
        driver_map: dict[str, list[str]] = {}
        try:
            parsed = parse_rtl_blocks(text)
        except Exception as exc:
            result = {
                "status": "parse_error",
                "target": target,
                "module": self.state.module_name,
                "error": f"{type(exc).__name__}: {exc}",
            }
            self.state.last_structure = result
            self.state.observed_structure = False
            return result
        for block in parsed:
            block_text = getattr(block, "text", "") or "\n".join(
                text.splitlines()[block.start_line - 1 : block.end_line]
            )
            writes = _assigned_signals(block_text)
            item = {
                "id": block.id,
                "kind": block.kind,
                "start_line": block.start_line,
                "end_line": block.end_line,
                "writes": writes,
                "uses_nonblocking": "<=" in block_text,
                "uses_blocking": bool(re.search(r"(?<![<>=!])=(?![=])", _strip_comments(block_text))),
            }
            blocks.append(item)
            for sig in writes:
                driver_map.setdefault(sig, []).append(block.id)

        self.state.observed_structure = True
        structure = {
            "status": "ok",
            "target": target,
            "module": self.state.module_name,
            "includes": includes,
            "module_count": module_count,
            "outputs": outputs,
            "declarations": declarations[:200],
            "blocks": blocks,
            "driver_map": driver_map,
            "output_drivers": {sig: driver_map.get(sig, []) for sig in outputs},
            "forbidden_wildcard_always": bool(re.search(r"always\s*@\s*\(\s*\*\s*\)|always\s*@\s*\*", text)),
        }
        self.state.last_structure = structure
        return structure

    # ---- 工具: run_lint ----

    @observed('tool', '执行Verilator语法检查', tool='run_check',
              summarize=lambda r: 'Verilator语法检查通过。' if r.get('status')=='ok' and r.get('is_pass') else 'Verilator语法检查未通过或未能执行，诊断保留在合并报告中。')
    def run_lint(self, target: str = "draft") -> dict[str, Any]:
        path = self._resolve_target_path(target)
        if path is None or not path.is_file():
            return {"status": "missing_target", "target": target, "is_pass": False, "output_excerpt": f"No RTL file for target '{target}'."}
        try:
            ok, output = self._check_syntax(path)
        except FileNotFoundError:
            return {"status": "tool_unavailable", "target": target, "is_pass": True, "output_excerpt": "Verilator not available; skipping lint check."}
        except Exception as exc:
            return {"status": "error", "target": target, "is_pass": False, "output_excerpt": f"{type(exc).__name__}: {exc}"}
        result = {"status": "ok", "target": target, "is_pass": bool(ok), "output_excerpt": _clip(output, 5000)}
        self.state.last_lint = result
        return result

    def _check_syntax(self, path: Path) -> tuple[bool, str]:
        include_dirs = [str(self.state.merged_file.parent)]
        for entry in self.state.global_defines_manifest.get("global_define_files", []) or []:
            if not isinstance(entry, dict):
                continue
            workspace_path = Path(str(entry.get("workspace_path") or ""))
            if workspace_path.is_file():
                include_dirs.append(str(workspace_path.parent))
        include_dirs = list(dict.fromkeys(include_dirs))
        try:
            return check_syntax(
                str(path),
                top_module=self.state.module_name,
                include_dirs=include_dirs,
                support_files=self.state.lint_support_files,
            )
        except TypeError as exc:
            if "include_dirs" not in str(exc) and "support_files" not in str(exc):
                raise
            return check_syntax(str(path), top_module=self.state.module_name)

    # ---- 工具: run_static_rtl_check ----

    @observed('tool', '检查RTL宏、模块声明与输出驱动', tool='run_check',
              summarize=lambda r: f'静态检查：{len(r.get("errors") or [])}项问题、{len(r.get("warnings") or [])}项提醒；'+('通过。' if r.get('status')=='pass' else '未通过。'))
    def run_static_rtl_check(self, target: str = "draft") -> dict[str, Any]:
        structure = self.inspect_rtl_structure(target)
        if structure.get("status") != "ok":
            result = {
                "status": "fail",
                "target": target,
                "errors": [structure.get("error", "Cannot inspect target")],
                "warnings": [],
                "structure": structure,
            }
            self.state.last_static_check = result
            return result

        errors: list[str] = []
        warnings: list[str] = []

        macro_redefinitions = self._authoritative_macro_redefinitions(self._read_target(target))
        if macro_redefinitions:
            errors.append(
                "Draft redefines authoritative global macro(s): "
                + ", ".join(macro_redefinitions)
                + ". Include the official define file instead of adding fallback definitions."
            )

        unresolved_macros = self._unresolved_macro_references(self._read_target(target))
        if unresolved_macros:
            errors.append(
                "Draft references unresolved macro(s): " + ", ".join(unresolved_macros) + "."
            )

        # module 数量
        if structure["module_count"] != 1:
            errors.append(f"Expected exactly one module declaration, found {structure['module_count']}.")

        # required includes
        missing = [name for name in self.state.required_includes if name not in structure["includes"]]
        if missing:
            errors.append(f"Missing required include(s): {missing}.")

        # 通配符 always
        if structure["forbidden_wildcard_always"]:
            errors.append("Final RTL contains forbidden always @(*) or always @*.")

        # output driver 检查
        for output, drivers in structure["output_drivers"].items():
            if not drivers:
                warnings.append(f"Output {output} is not visibly driven by parsed always/assign blocks.")
            if len(drivers) > 1:
                errors.append(f"Output {output} has multiple parsed drivers: {drivers}.")

        # Stage5 contract 多 writer 冲突
        contracts = _read_json(self.state.contracts_file) if self.state.contracts_file else {}
        writer_map: dict[str, list[str]] = {}
        for item in contracts.get("contracts", []) if isinstance(contracts, dict) else []:
            contract = item.get("contract") if isinstance(item, dict) else {}
            for sig in contract.get("writes", []) if isinstance(contract, dict) else []:
                writer_map.setdefault(str(sig), []).append(str(item.get("subtask_id")))
        for sig, writers in sorted(writer_map.items()):
            if len(set(writers)) > 1:
                warnings.append(f"Stage5 contracts have multiple writers for {sig}: {writers}.")

        # 赋值惯例检测
        assignment_warnings = self._check_assignment_convention(structure)
        warnings.extend(assignment_warnings)

        result = {
            "status": "fail" if errors else "pass",
            "target": target,
            "errors": errors,
            "warnings": warnings[:50],
            "structure": structure,
        }
        self.state.last_static_check = result
        return result

    def _check_assignment_convention(self, structure: dict[str, Any]) -> list[str]:
        """检测草稿的 blocking/nonblocking 使用模式。

        如果某个 always 块同时使用阻塞和非阻塞赋值（混合风格），产生 ERROR。
        如果输出信号所在的 always 块全部使用非阻塞赋值，产生 WARNING
        （因为参考设计通常要求阻塞赋值以确保 testbench 边沿采样一致性）。
        """
        warnings: list[str] = []
        for block in structure.get("blocks", []) or []:
            if block.get("kind") != "always":
                continue
            if block.get("uses_blocking") and block.get("uses_nonblocking"):
                warnings.append(
                    f"Block {block['id']} (L{block['start_line']}-{block['end_line']}) "
                    f"mixes blocking and nonblocking assignments — consider using one convention consistently."
                )
            # 对于驱动 output 信号的 always 块，检查是否全部为 nonblocking
            block_writes = set(block.get("writes", []) or [])
            output_set = set(structure.get("outputs", []) or [])
            driven_outputs = block_writes & output_set
            if driven_outputs and not block.get("uses_blocking") and block.get("uses_nonblocking"):
                warnings.append(
                    f"Block {block['id']} drives outputs ({', '.join(sorted(driven_outputs))}) "
                    f"using only nonblocking assignments. If the reference testbench samples on clock edges, "
                    f"this will cause edge_active sampling mismatches. Consider using blocking assignments (=) "
                    f"for output signals in sequential always blocks."
                )
        return warnings

    # ---- 工具: generate_merge_draft ----

    def _ensure_journal(self) -> None:
        if self.state.journal is None:
            self.state.journal = MergeJournal(
                self.state.artifact_layout.directory("merge_journal") / self.state.module_name
            )

    @observed('tool', '写入并预检模块合并候选', tool='write_rtl', registered_tool=False,
              summarize=lambda r: '候选未接受，保留检查记录。' if r.get('status') in {'error','rejected'} else '已生成合并候选并记录预检结果；尚未代表正式接受。')
    def generate_merge_draft(self, code: str, reason: str = "", expected_effect: str = "") -> dict[str, Any]:
        del expected_effect
        self._ensure_journal()
        # 证据门控
        if not self.state.observed_fragments:
            return {"status": "rejected", "reason": "Must call read_merge_context(kind=\"fragments\") before generating a draft."}
        if not self.state.observed_spec:
            return {"status": "rejected", "reason": "Must call read_merge_context(kind=\"spec\") before generating a draft."}
        has_global_defines = bool(
            self.state.global_defines_manifest.get("global_define_files", [])
        )
        if has_global_defines and not self.state.observed_global_defines:
            return {
                "status": "rejected",
                "reason": "Must call read_merge_context(kind=\"global_defines\") before generating a draft — authoritative global defines are available.",
            }

        if not str(code).strip():
            return {"status": "rejected", "reason": "code must be non-empty"}

        extracted = _extract_verilog_code(code)
        if not extracted.strip():
            return {"status": "rejected", "reason": "No Verilog code found in the provided input."}

        macro_redefinitions = self._authoritative_macro_redefinitions(extracted)
        if macro_redefinitions:
            return {
                "status": "rejected",
                "reason": (
                    "Draft redefines authoritative global macro(s): "
                    + ", ".join(macro_redefinitions)
                    + ". Use the official include rather than local fallback definitions."
                ),
            }

        candidate = self._ensure_required_includes(extracted)
        step = self.state.action_calls + 1
        self.state.action_calls = step
        self.state.draft_file.parent.mkdir(parents=True, exist_ok=True)

        # 保存旧草稿（如果存在）
        before = ""
        if self.state.draft_file.is_file():
            before = self.state.draft_file.read_text(encoding="utf-8", errors="replace")
            self.state.journal.snapshot_files(step=step, label="before", files=[self.state.draft_file])

        # 写入新草稿
        self.state.draft_file.write_text(candidate.rstrip() + "\n", encoding="utf-8")
        from zerorepo.rtl_impl.material_observer import code_saved
        code_saved(self.state.draft_file,'merge_draft')
        self.state.draft_generated = True
        self.state.journal.snapshot_files(step=step, label="after", files=[self.state.draft_file])

        # 草稿日志
        self.state.journal.append_jsonl("draft_journal.jsonl", {
            "step": step,
            "reason": reason,
            "code_chars": len(candidate),
            "before_chars": len(before),
        })

        # 快速预检查
        lint = self.run_lint("draft")

        result: dict[str, Any] = {
            "status": "kept",
            "step": step,
            "reason": reason,
            "draft_path": str(self.state.draft_file),
            "code_chars": len(candidate),
            "pre_check_lint_pass": lint.get("is_pass", False),
            "pre_check_lint_excerpt": lint.get("output_excerpt", ""),
        }

        # 如果预检查发现致命 Verilator 错误，拒绝
        if not lint.get("is_pass") and lint.get("status") != "tool_unavailable":
            output_text = lint.get("output_excerpt", "")
            if "%Error" in output_text:
                # 恢复旧草稿
                if before:
                    self.state.draft_file.write_text(before, encoding="utf-8")
                self.state.draft_generated = False
                result["status"] = "rejected"
                result["reason"] = f"Draft rejected: Verilator fatal error in pre-check. Fix the error and retry."
                result["pre_check_lint_excerpt"] = _clip(output_text, 3000)

        self.state.journal.append_jsonl("draft_journal.jsonl", result)
        return result

    # ---- 工具: commit_merge_draft ----

    @observed('tool', '检查并接受模块合并候选', tool='write_rtl', registered_tool=False,
              summarize=lambda r: '已写入接受版本，功能结果仍以本轮仿真为准。' if r.get('status')=='committed' else '候选未接受，已有接受版本保留。')
    def commit_merge_draft(self, reason: str = "") -> dict[str, Any]:
        self._ensure_journal()
        # 证据门控
        if not self.state.draft_generated:
            return {"status": "rejected", "reason": "No draft has been generated. Call generate_merge_draft first."}
        if not self.state.draft_file.is_file():
            return {"status": "rejected", "reason": "Draft file does not exist on disk."}
        if not self.state.observed_structure:
            return {"status": "rejected", "reason": "Must call inspect_rtl_structure(target=\"draft\") before committing."}

        # 运行最终检查
        static = self.run_static_rtl_check("draft")
        lint = self.run_lint("draft")

        if static.get("status") != "pass":
            return {
                "status": "rejected",
                "reason": "run_static_rtl_check did not pass. Fix the errors before committing.",
                "static_check": static,
            }
        # lint: 允许 tool_unavailable（没有 Verilator 时跳过）
        if not lint.get("is_pass") and lint.get("status") != "tool_unavailable":
            return {
                "status": "rejected",
                "reason": "run_lint did not pass. Fix the lint errors before committing.",
                "lint": lint,
            }

        # 提交：复制草稿到正式文件
        draft_code = self.state.draft_file.read_text(encoding="utf-8", errors="replace")
        self.state.merged_file.parent.mkdir(parents=True, exist_ok=True)
        self.state.merged_file.write_text(draft_code, encoding="utf-8")
        from zerorepo.rtl_impl.material_observer import code_saved
        code_saved(self.state.merged_file,'module')
        self.state.draft_committed = True

        result = {
            "status": "committed",
            "reason": reason,
            "merged_file": str(self.state.merged_file),
            "static_check": static,
            "lint": lint,
        }
        self.state.journal.append_jsonl("draft_journal.jsonl", result)
        return result

    # ---- 辅助 ----

    def _ensure_required_includes(self, code: str) -> str:
        lines = code.splitlines()
        existing = set(re.findall(r'^\s*`include\s+"([^"]+)"', code, flags=re.MULTILINE))
        missing = [name for name in self.state.required_includes if name not in existing]
        if not missing:
            return code
        insert = [f'`include "{name}"' for name in missing]
        idx = 0
        while idx < len(lines) and (
            lines[idx].strip().startswith("`timescale") or lines[idx].strip().startswith("`include")
        ):
            idx += 1
        return "\n".join(lines[:idx] + insert + lines[idx:])

    def _authoritative_macro_redefinitions(self, code: str) -> list[str]:
        if not code or not self.state.global_defines_context:
            return []
        official_names = set(
            re.findall(
                r"(?m)^\s*`define\s+([A-Za-z_][A-Za-z0-9_$]*)\b",
                _strip_comments(self.state.global_defines_context),
            )
        )
        if not official_names:
            return []
        draft_names = set(
            re.findall(
                r"(?m)^\s*`define\s+([A-Za-z_][A-Za-z0-9_$]*)\b",
                _strip_comments(code),
            )
        )
        return sorted(official_names & draft_names)

    def _unresolved_macro_references(self, code: str) -> list[str]:
        references, local_definitions = self._macro_references_and_definitions(code)
        available = set(local_definitions)
        available.update(self._manifest_macro_definitions())
        available.update(_PREDEFINED_MACROS)
        return sorted(references - available)

    def _manifest_macro_definitions(self) -> set[str]:
        definitions: set[str] = set()
        visited: set[Path] = set()
        include_dirs = {
            Path(str(entry.get("workspace_path") or "")).resolve().parent
            for entry in self.state.global_defines_manifest.get("global_define_files", []) or []
            if isinstance(entry, dict) and Path(str(entry.get("workspace_path") or "")).is_file()
        }

        def visit(path: Path) -> None:
            resolved = path.resolve()
            if resolved in visited or not resolved.is_file():
                return
            visited.add(resolved)
            text = resolved.read_text(encoding="utf-8", errors="replace")
            _references, local = self._macro_references_and_definitions(text)
            definitions.update(local)
            for match in _INCLUDE_RE.finditer(_strip_comments(text)):
                include_name = match.group(1)
                candidates = [resolved.parent / include_name]
                candidates.extend(directory / include_name for directory in sorted(include_dirs, key=str))
                dependency = next((item for item in candidates if item.is_file()), None)
                if dependency is not None:
                    visit(dependency)

        for entry in self.state.global_defines_manifest.get("global_define_files", []) or []:
            if not isinstance(entry, dict):
                continue
            path = Path(str(entry.get("workspace_path") or ""))
            if path.is_file():
                visit(path)
        return definitions

    @staticmethod
    def _macro_references_and_definitions(code: str) -> tuple[set[str], set[str]]:
        references: set[str] = set()
        definitions: set[str] = set()
        for line in _strip_comments(code).splitlines():
            define_match = _DEFINE_RE.match(line)
            if define_match:
                definitions.add(define_match.group(1))
                references.update(_MACRO_TOKEN_RE.findall(define_match.group("body") or ""))
                continue
            directive = re.match(r"^\s*`([A-Za-z_][A-Za-z0-9_$]*)", line)
            if directive and directive.group(1) in _PREPROCESSOR_CONTROL_DIRECTIVES:
                continue
            references.update(_MACRO_TOKEN_RE.findall(line))
        return references, definitions

    def _extract_outputs(self, text: str) -> list[str]:
        names: set[str] = set()
        for match in re.finditer(
            r"\boutput(?:\s+reg|\s+wire)?\s*(?:\[[^\]]+\]\s*)?([A-Za-z_][A-Za-z0-9_$]*)", text
        ):
            names.add(match.group(1))
        return sorted(names)

    # ---- merge report ----

    def write_merge_report(self, path: Path) -> dict[str, Any]:
        path.parent.mkdir(parents=True, exist_ok=True)
        static = self.run_static_rtl_check("draft") if self.state.draft_file.is_file() else self.run_static_rtl_check("merged")
        lint = self.run_lint("draft") if self.state.draft_file.is_file() else self.run_lint("merged")
        report = {
            "schema_version": "stage6_semantic_merge_report_v2",
            "module": self.state.module_name,
            "required_includes": self.state.required_includes,
            "signal_ownership": self._signal_ownership(static.get("structure", {})),
            "always_block_responsibility": static.get("structure", {}).get("blocks", []),
            "static_check_summary": {
                "status": static.get("status"),
                "errors": static.get("errors", []),
                "warnings": static.get("warnings", []),
            },
            "lint_summary": {
                "status": lint.get("status"),
                "is_pass": lint.get("is_pass"),
                "output_excerpt": lint.get("output_excerpt", ""),
            },
            "draft_committed": self.state.draft_committed,
            "total_action_calls": self.state.action_calls,
        }
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return report

    def _signal_ownership(self, structure: dict[str, Any]) -> dict[str, Any]:
        ownership: dict[str, Any] = {}
        for sig, drivers in (structure.get("driver_map") or {}).items():
            ownership[sig] = {"drivers": drivers, "owner_block": drivers[0] if len(drivers) == 1 else None}
        # 如果 spec/contract 中有可见的 bit 映射，可以从 contracts 中推断
        # 目前保持简单：只从 structure 提取 driver 信息
        return ownership


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

class Stage6MergeRunner:
    """用 SafeReActAgent + Toolkit 驱动的渐进式信息暴露 Merge Runner。"""

    READONLY_TOOLS = {
        "read_merge_context",
        "inspect_rtl_structure",
        "run_static_rtl_check",
        "run_lint",
    }
    ACTION_TOOLS = {"generate_merge_draft", "commit_merge_draft"}

    def __init__(
        self,
        model: Any,
        formatter: Any,
        tools: Stage6MergeTools,
        *,
        logger: Any | None = None,
        max_steps: int = 8,
    ) -> None:
        self.model = model
        self.tools = tools
        self.logger = logger
        self.max_steps = max(1, int(max_steps))
        self._state: SemanticMergeState = tools.state
        self._readonly_calls_since_action = 0
        self._max_readonly_calls = 16

        # 构建 AgentScope Toolkit
        toolkit = Toolkit()
        toolkit.register_tool_function(
            self.read_merge_context,
            json_schema=_tool_schema(
                "read_merge_context",
                "读取合并上下文。必须在使用其他工具前先调用此工具获取 spec/fragments/global_defines 等内容。",
                {
                    "kind": {
                        "type": "string",
                        "enum": [
                            "fragments",
                            "fragment_contracts",
                            "module_plan",
                            "module_skeleton",
                            "spec",
                            "kg_child_context",
                            "global_defines",
                            "learned_merge_rules",
                        ],
                    },
                    "max_chars": {"type": "integer"},
                },
                ["kind"],
            ),
        )
        toolkit.register_tool_function(
            self.inspect_rtl_structure,
            json_schema=_tool_schema(
                "inspect_rtl_structure",
                "解析 RTL 草稿/merged 文件的结构：include 列表、always/assign block、driver map、赋值风格。",
                {
                    "target": {"type": "string", "enum": ["draft", "merged"]},
                },
                ["target"],
            ),
        )
        toolkit.register_tool_function(
            self.run_static_rtl_check,
            json_schema=_tool_schema(
                "run_static_rtl_check",
                "对草稿/merged 文件运行静态结构验证：module 数量、required includes、多驱动、通配符 always、赋值惯例。",
                {
                    "target": {"type": "string", "enum": ["draft", "merged"]},
                },
                ["target"],
            ),
        )
        toolkit.register_tool_function(
            self.run_lint,
            json_schema=_tool_schema(
                "run_lint",
                "对草稿/merged 文件运行 Verilator lint 检查。",
                {
                    "target": {"type": "string", "enum": ["draft", "merged"]},
                },
                ["target"],
            ),
        )
        toolkit.register_tool_function(
            self.generate_merge_draft,
            json_schema={
                "type": "function",
                "function": {
                    "name": "generate_merge_draft",
                    "description": "生成合并草稿并写入临时草稿文件。必须先通过 read_merge_context 读取过 fragments、spec、global_defines。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "string", "description": "完整的 SystemVerilog 模块代码"},
                            "reason": {"type": "string", "description": "合并决策说明"},
                            "expected_effect": {"type": "string", "description": "预期效果"},
                        },
                        "required": ["code", "reason", "expected_effect"],
                    },
                },
            },
        )
        toolkit.register_tool_function(
            self.commit_merge_draft,
            json_schema={
                "type": "function",
                "function": {
                    "name": "commit_merge_draft",
                    "description": "将检查通过的草稿提交为正式 merged 文件。必须在 run_static_rtl_check 和 run_lint 都通过后才能调用。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "reason": {"type": "string", "description": "提交理由"},
                        },
                        "required": ["reason"],
                    },
                },
            },
        )

        from zerorepo.rtl_impl.module_planner.prompts.stage6_merge import MERGE_SYSTEM_PROMPT

        self._agent = SafeReActAgent(
            name="Stage6MergeAgent",
            sys_prompt=MERGE_SYSTEM_PROMPT,
            model=model,
            formatter=formatter,
            toolkit=toolkit,
            memory=InMemoryMemory(),
            max_iters=12,
        )

    def reset(self) -> None:
        clear_memory_safely(self._agent)
        self._readonly_calls_since_action = 0

    # ---- ToolResponse 包装 ----

    def _tool_response(self, name: str, payload: dict[str, Any]) -> ToolResponse:
        if self._state.journal is not None:
            self._state.journal.append_jsonl(
                "merge_trace.jsonl",
                {"role": "tool", "tool_name": name, "tool_result": payload},
            )
        text = json.dumps(payload, indent=2, ensure_ascii=False)
        if name in self.ACTION_TOOLS:
            self._readonly_calls_since_action = 0
        elif name in self.READONLY_TOOLS:
            self._readonly_calls_since_action += 1
        return ToolResponse(content=[{"type": "text", "text": text}])

    def _readonly_budget_exceeded_response(self, tool_name: str) -> ToolResponse | None:
        if self._readonly_calls_since_action < self._max_readonly_calls:
            return None
        payload: dict[str, Any] = {
            "status": "observation_budget_exhausted",
            "tool_name": tool_name,
            "readonly_calls_since_action": self._readonly_calls_since_action,
            "max_readonly_calls": self._max_readonly_calls,
            "required_next_action": ["generate_merge_draft", "commit_merge_draft", "generate_response"],
            "message": (
                "观察预算已用尽。请基于已有的证据采取行动（generate_merge_draft 或 commit_merge_draft），"
                "或调用 generate_response 结束。"
            ),
        }
        return self._tool_response(tool_name, payload)

    # ---- AgentScope 工具方法（async，被 Toolkit 调用） ----

    async def read_merge_context(self, kind: str, max_chars: int = 12000) -> ToolResponse:
        blocked = self._readonly_budget_exceeded_response("read_merge_context")
        if blocked is not None:
            return blocked
        result = await asyncio.to_thread(self.tools.read_merge_context, kind, max_chars)
        return self._tool_response("read_merge_context", result)

    async def inspect_rtl_structure(self, target: str = "draft") -> ToolResponse:
        blocked = self._readonly_budget_exceeded_response("inspect_rtl_structure")
        if blocked is not None:
            return blocked
        result = await asyncio.to_thread(self.tools.inspect_rtl_structure, target)
        return self._tool_response("inspect_rtl_structure", result)

    async def run_static_rtl_check(self, target: str = "draft") -> ToolResponse:
        blocked = self._readonly_budget_exceeded_response("run_static_rtl_check")
        if blocked is not None:
            return blocked
        result = await asyncio.to_thread(self.tools.run_static_rtl_check, target)
        return self._tool_response("run_static_rtl_check", result)

    async def run_lint(self, target: str = "draft") -> ToolResponse:
        blocked = self._readonly_budget_exceeded_response("run_lint")
        if blocked is not None:
            return blocked
        result = await asyncio.to_thread(self.tools.run_lint, target)
        return self._tool_response("run_lint", result)

    async def generate_merge_draft(self, code: str, reason: str = "", expected_effect: str = "") -> ToolResponse:
        result = await asyncio.to_thread(self.tools.generate_merge_draft, code, reason, expected_effect)
        return self._tool_response("generate_merge_draft", result)

    async def commit_merge_draft(self, reason: str = "") -> ToolResponse:
        result = await asyncio.to_thread(self.tools.commit_merge_draft, reason)
        return self._tool_response("commit_merge_draft", result)

    # ---- 主入口 ----

    def _memory_summary(self) -> dict[str, Any]:
        state = self._state
        return {
            "schema": "semantic_merge_memory_brief.v1",
            "module": state.module_name,
            "draft_generated": state.draft_generated,
            "draft_committed": state.draft_committed,
            "action_calls": state.action_calls,
            "max_steps": self.max_steps,
            "observed": {
                "fragments": state.observed_fragments,
                "spec": state.observed_spec,
                "global_defines": state.observed_global_defines,
                "kg_child": state.observed_kg_child,
                "structure": state.observed_structure,
            },
            "last_static_check_status": state.last_static_check.get("status"),
            "last_static_check_errors": state.last_static_check.get("errors", []),
            "last_static_check_warnings": state.last_static_check.get("warnings", []),
            "last_lint_pass": state.last_lint.get("is_pass"),
            "required_includes": state.required_includes,
            "includes_status": (
                "satisfied"
                if not state.required_includes
                or (
                    state.last_structure
                    and all(
                        name in (state.last_structure.get("includes") or [])
                        for name in state.required_includes
                    )
                )
                else "missing"
            ),
        }

    def _call_agent(self, msg: Msg) -> Any:
        """安全地调用 agent，处理已有 event loop 的情况。"""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self._agent(msg))

        # 已有 running loop：在新线程中运行
        import threading
        result: dict[str, Any] = {}

        def _runner() -> None:
            try:
                result["value"] = asyncio.run(self._agent(msg))
            except BaseException as exc:
                result["error"] = exc

        thread = threading.Thread(target=_runner)
        thread.start()
        thread.join()
        if "error" in result:
            raise result["error"]
        return result["value"]

    def run(self, initial_prompt: str, *, fallback_raw_merge: Any) -> str:
        self.reset()
        state = self._state

        # 确保 journal 初始化
        if state.journal is None:
            state.journal = MergeJournal(
                state.artifact_layout.directory("merge_journal") / state.module_name
            )

        from zerorepo.rtl_impl.module_planner.prompts.stage6_merge import (
            build_merge_continue_prompt,
        )

        state.journal.append_jsonl("merge_trace.jsonl", {"role": "user", "content": initial_prompt})

        try:
            msg = self._call_agent(Msg("user", initial_prompt, role="user"))
            text = msg.get_text_content() or ""
            state.journal.append_jsonl("merge_trace.jsonl", {"role": "assistant", "content": text})

            for step in range(1, self.max_steps + 1):
                if state.draft_committed:
                    break
                if state.action_calls >= self.max_steps:
                    break

                summary = self._memory_summary()
                prompt = build_merge_continue_prompt(
                    memory_summary=summary,
                    readonly_calls_since_action=self._readonly_calls_since_action,
                    max_readonly_calls=self._max_readonly_calls,
                )
                state.journal.append_jsonl("merge_trace.jsonl", {"role": "user", "content": prompt, "step": step})
                msg = self._call_agent(Msg("user", prompt, role="user"))
                text = msg.get_text_content() or ""
                state.journal.append_jsonl(
                    "merge_trace.jsonl",
                    {"role": "assistant", "content": text, "step": step},
                )

                if state.draft_committed:
                    break
                if state.action_calls >= self.max_steps:
                    break

            # 循环结束后的处理
            if state.draft_committed and state.merged_file.is_file():
                return state.merged_file.read_text(encoding="utf-8").strip()

            # 如果有草稿但未提交，尝试最终提交
            if state.draft_generated and state.draft_file.is_file() and not state.draft_committed:
                commit_result = self.tools.commit_merge_draft("Auto-commit at end of merge loop.")
                if commit_result.get("status") == "committed":
                    return state.merged_file.read_text(encoding="utf-8").strip()

            # Fallback 到 raw merge
            return fallback_raw_merge(None)

        except Exception as exc:
            if self.logger is not None:
                self.logger.warning(
                    "Semantic merge ReAct loop failed for %s: %s; falling back to raw merge",
                    state.module_name,
                    exc,
                )
            state.journal.append_jsonl(
                "merge_trace.jsonl",
                {"role": "error", "content": f"{type(exc).__name__}: {exc}"},
            )
            return fallback_raw_merge(None)
        finally:
            clear_memory_safely(self._agent)
