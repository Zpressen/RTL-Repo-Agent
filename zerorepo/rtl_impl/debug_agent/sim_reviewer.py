from __future__ import annotations

import glob
import os
import re
import shlex
import shutil
from typing import Tuple

from .bash_tools import CommandResult, run_bash_command


def _require_executable(name: str) -> None:
    if shutil.which(name) is None:
        raise FileNotFoundError(f"Required executable '{name}' not found in PATH.")


def _verilator_has_fatal(stdout: str, stderr: str) -> bool:
    # Verilator typically reports as "%Error:" / "%Error-<TAG>:".
    fatal_re = re.compile(r"^%Error", re.MULTILINE)
    if fatal_re.search(stderr) or fatal_re.search(stdout):
        return True
    # Some toolchains may prefix with "Error:" without the % marker.
    text = f"{stdout}\n{stderr}".lower()
    return ("syntax error" in text) or ("error:" in text)


def check_syntax(
    rtl_path: str,
    top_module: str | None = None,
    include_dirs: list[str] | None = None,
    support_files: list[str] | None = None,
) -> Tuple[bool, str]:
    _require_executable("verilator")
    rtl_path = os.path.abspath(rtl_path)
    rtl_dir = os.path.dirname(rtl_path)
    if support_files is None:
        # Legacy/debug workdirs are self-contained and intentionally compile
        # rtl.sv together with sibling support/testbench sources.
        src_files = sorted(glob.glob(os.path.join(rtl_dir, "*.sv")) + glob.glob(os.path.join(rtl_dir, "*.v")))
    else:
        # Merge workdirs contain unrelated module drafts.  An explicit support
        # list keeps target lint isolated from broken sibling drafts.
        src_files = [rtl_path, *(os.path.abspath(item) for item in support_files if item)]
        src_files = list(dict.fromkeys(src_files))
    if not src_files:
        src_files = [rtl_path]
    srcs = " ".join(shlex.quote(item) for item in src_files)
    top_flag = f"--top-module {shlex.quote(top_module)} " if top_module else ""
    # Verilator does not implicitly search the current working directory for
    # nested `include files.  Every syntax/debug workdir is self-contained, so
    # make the RTL directory the first canonical include location and then add
    # any caller-provided directories without duplication.
    unique_dirs: list[str] = []
    seen_dirs: set[str] = set()
    for include_dir in [rtl_dir, *(include_dirs or [])]:
        if not include_dir:
            continue
        abs_dir = os.path.abspath(include_dir)
        if abs_dir in seen_dirs:
            continue
        seen_dirs.add(abs_dir)
        unique_dirs.append(abs_dir)
    include_flags = " ".join(f"-I{shlex.quote(item)}" for item in unique_dirs)
    if include_flags:
        include_flags += " "
    cmd = f"verilator --lint-only --sv --timing -Wall -Wno-fatal --assert {include_flags}{top_flag}{srcs}"
    is_pass, sim_output = run_bash_command(cmd, timeout=60, cwd=rtl_dir)
    sim_output_obj = CommandResult.model_validate_json(sim_output)
    stdout = sim_output_obj.stdout or ""
    stderr = sim_output_obj.stderr or ""

    # Be permissive about warnings: syntax check should fail only on actual errors.
    is_pass = bool(is_pass) and not _verilator_has_fatal(stdout, stderr)
    return is_pass, sim_output


def sim_review_mismatch_cnt(stdout: str) -> int:
    mismatch_cnt = 0
    if "SIMULATION FAILED" in stdout:
        re_str = r"SIMULATION FAILED - (\d*) MISMATCHES DETECTED"
        m = re.search(re_str, stdout)
        if m is not None:
            mismatch_cnt = int(m.group(1))
            return mismatch_cnt
    counts = [
        int(item)
        for item in re.findall(
            r"(?:Hint:\s+Output\s+)?(?:'[^']+'|[A-Za-z_][A-Za-z0-9_]*(?:\s+signal)?)\s+has\s+(\d+)\s+mismatches",
            stdout,
        )
    ]
    if counts:
        return sum(counts)
    # Fallback for VerilogEval-style golden testbenches.
    m2 = re.search(r"^Mismatches:\s*(\d+)\s*in\s*(\d+)\s*samples$", stdout, re.MULTILINE)
    if m2:
        mismatch_cnt = int(m2.group(1))
        return mismatch_cnt
    m3 = re.search(r"Hint:\s+Total mismatched samples is\s*(\d+)\s*out of\s*(\d+)\s*samples", stdout)
    if m3:
        mismatch_cnt = int(m3.group(1))
        return mismatch_cnt
    return mismatch_cnt


def _local_include_sources(output_path_per_run: str, source_paths: list[str]) -> list[str]:
    include_re = re.compile(r"^\s*`include\s+\"(.+?)\"", re.MULTILINE)
    root = os.path.abspath(output_path_per_run)
    found: list[str] = []
    seen: set[str] = set()
    queue = [path for path in source_paths if path and os.path.isfile(path)]
    for source_path in queue:
        try:
            with open(source_path, "r", encoding="utf-8") as fh:
                text = fh.read()
        except OSError:
            continue
        for m in include_re.finditer(text):
            include_name = m.group(1)
            include_path = os.path.abspath(os.path.join(root, include_name))
            if not include_path.startswith(root + os.sep):
                continue
            if not os.path.isfile(include_path) or include_path in seen:
                continue
            seen.add(include_path)
            found.append(include_path)
            queue.append(include_path)
    return found


def sim_review(
    output_path_per_run: str,
    golden_rtl_path: str | None = None,
) -> Tuple[bool, int, str]:
    _require_executable("verilator")
    output_path_per_run = os.path.abspath(output_path_per_run)
    rtl_path = f"{output_path_per_run}/rtl.sv"
    sim_bin = f"{output_path_per_run}/sim_output.bin"
    tb_path = f"{output_path_per_run}/tb.sv"
    if golden_rtl_path is None:
        golden_rtl_path = ""
    elif golden_rtl_path:
        golden_rtl_path = os.path.abspath(golden_rtl_path)
    if os.path.isfile(sim_bin):
        os.remove(sim_bin)

    # Build + run with Verilator.
    # Notes:
    # - Use --timing to support delays/event controls in testbenches.
    # - Use --trace so $dumpfile/$dumpvars can generate wave.vcd for debugging.
    # - Use --assert (or default-on in newer versions) for assertion support.
    primary_sources = [tb_path, rtl_path]
    if golden_rtl_path:
        primary_sources.append(golden_rtl_path)
    include_sources = _local_include_sources(output_path_per_run, primary_sources)
    ordered_sources: list[str] = []
    seen_sources: set[str] = set()
    for src in [*include_sources, *primary_sources]:
        if not src or src in seen_sources:
            continue
        seen_sources.add(src)
        ordered_sources.append(src)
    srcs = " ".join(ordered_sources)
    # Auto-detect testbench top module name (most oracle testbenches use `tb`,
    # but some use `tb_{module_name}`).
    tb_top = "tb"
    if os.path.isfile(tb_path):
        try:
            with open(tb_path, "r", encoding="utf-8") as fh:
                tb_text = fh.read()
            m = re.search(r"^\s*module\s+(\w+)", tb_text, re.MULTILINE)
            if m:
                tb_top = m.group(1)
        except OSError:
            pass
    realbench_warning_flags = (
        "-Wno-CASEOVERLAP -Wno-LATCH -Wno-UNOPTFLAT -Wno-MULTIDRIVEN "
        "-Wno-ASCRANGE -Wno-IMPLICIT -Wno-CASEINCOMPLETE -Wno-PINMISSING "
        "-Wno-WIDTHTRUNC -Wno-EOFNEWLINE -Wno-DECLFILENAME -Wno-WIDTHEXPAND"
    )
    cmd = (
        "verilator -cc --exe --binary --sv --timing --trace --assert --coverage-line -fno-table "
        f"{realbench_warning_flags} -j 4 -fno-table --top {tb_top} -Wall -Wno-fatal "
        f"-y {output_path_per_run} --Mdir obj_dir -o {sim_bin} {srcs}; "
        f"{sim_bin}"
    )
    cmd_ok, sim_output = run_bash_command(cmd, timeout=120, cwd=output_path_per_run)
    sim_output_obj = CommandResult.model_validate_json(sim_output)
    stdout = sim_output_obj.stdout or ""
    stderr = sim_output_obj.stderr or ""

    mismatch_cnt = sim_review_mismatch_cnt(stdout)
    if mismatch_cnt == 0 and re.search(r"assertion failed", f"{stdout}\n{stderr}", re.IGNORECASE):
        # Treat assertion failures as mismatches so the debugger loop can engage.
        mismatch_cnt = 1

    # Determine pass/fail primarily from the testbench's explicit result markers,
    # instead of the process return code. Some testbenches may exit non-zero
    # despite printing "SIMULATION PASSED" (or "Mismatches: 0 ...").
    has_pass_marker = "SIMULATION PASSED" in stdout
    has_mismatch_summary = bool(
        re.search(r"^Mismatches:\s*\d+\s*in\s*\d+\s*samples$", stdout, re.MULTILINE)
    )
    has_total_hint = bool(
        re.search(r"Hint:\s+Total mismatched samples is\s*\d+\s*out of\s*\d+\s*samples", stdout)
    )
    # Only treat *harness* timeouts as fatal. Many VerilogEval testbenches print
    # "TIMEOUT" as a watchdog message even for successful runs (they still emit
    # the "Mismatches: ..." summary). The harness timeout is surfaced in stderr
    # by `run_bash_command` as "Timeout ... reached.".
    has_timeout_marker = "Timeout" in stderr

    # Treat warnings as non-fatal; only block on clear compile/runtime errors.
    has_fatal = _verilator_has_fatal(stdout, stderr)

    is_pass_by_log = has_pass_marker or ((has_mismatch_summary or has_total_hint) and mismatch_cnt == 0)
    is_pass = is_pass_by_log and not (has_timeout_marker or has_fatal)

    # If the command timed out or crashed without printing any summary, keep it failed.
    if not is_pass and not (has_pass_marker or has_mismatch_summary) and cmd_ok:
        # cmd_ok with no markers is ambiguous; treat as failed and keep mismatch_cnt as-is.
        pass

    assert isinstance(sim_output, str) and isinstance(is_pass, bool)
    return is_pass, mismatch_cnt, sim_output


class SimReviewer:
    def __init__(
        self,
        output_path_per_run: str,
        golden_rtl_path: str | None = None,
    ):
        self.output_path_per_run = output_path_per_run
        self.golden_rtl_path = golden_rtl_path

    def review(self) -> Tuple[bool, int, str]:
        return sim_review(
            self.output_path_per_run,
            self.golden_rtl_path,
        )
