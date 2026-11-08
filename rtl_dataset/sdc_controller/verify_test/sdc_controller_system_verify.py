#!/usr/bin/env python3
"""
System-level verification of an agent-generated SDC controller.

The script compiles every top-level Verilog/SystemVerilog source in the
provided directory together with the public testbench and a private golden
reference hierarchy.  The generated sources must collectively define the
module ``sdc_controller``.

Usage:
    python sdc_controller_system_verify.py <path_to_agent_src_dir>

Example:
    python sdc_controller_system_verify.py /tmp/agent_output/
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile


# ---------------------------------------------------------------------------
# Path and source configuration
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REALBENCH_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", ".."))
SYSTEM_TEST_DIR = os.path.join(
    REALBENCH_ROOT, "sdc", "sdc_controller", "verification"
)
CONDA_REALBENCH_BIN = "/home/mokita/miniconda3/envs/realbench/bin"

TESTBENCH_FILE = "sdc_controller_testbench.sv"
STIMULUS_FILE = "sdc_controller_stimulus_gen.sv"
CANONICAL_HEADER = "sd_defines.v"
RESERVED_AGENT_FILES = {CANONICAL_HEADER}

# The official DUT sdc_controller_top.sv is intentionally absent.  The
# reference top defines ref_sdc_controller; all of its dependencies are copied
# and namespaced below so that an agent may freely reuse the original names.
GOLDEN_REF_FILES = (
    "sdc_controller_ref.sv",
    "sd_bd.v",
    "sd_clock_divider.v",
    "sd_controller_wb.v",
    "sd_data_master.v",
    "sd_cmd_master.v",
    "sd_fifo_rx_filler.v",
    "sd_rx_fifo.v",
    "sd_fifo_tx_filler.v",
    "sd_tx_fifo.v",
    "sd_data_serial_host.v",
    "sd_crc_16.v",
    "sd_cmd_serial_host.v",
    "sd_crc_7.v",
)

AGENT_SOURCE_EXTENSIONS = (".v", ".sv")
AGENT_HEADER_EXTENSIONS = (".vh", ".svh")
MODULE_DECLARATION_RE = re.compile(
    r"^\s*module\s+([A-Za-z_][A-Za-z0-9_$]*)\b", re.MULTILINE
)

VERILATOR_FLAGS = [
    "-cc",
    "--exe",
    "--binary",
    "--trace",
    "--assert",
    "--coverage-line",
    "-fno-table",
    "-Wno-CASEOVERLAP",
    "-Wno-LATCH",
    "-Wno-UNOPTFLAT",
    "-Wno-MULTIDRIVEN",
    "-Wno-WIDTHEXPAND",
    "-Wno-ASCRANGE",
    "-Wno-IMPLICIT",
    "-Wno-CASEINCOMPLETE",
    "-Wno-PINMISSING",
    "-Wno-WIDTHTRUNC",
    "-Wno-EOFNEWLINE",
    "-Wno-DECLFILENAME",
    "-j",
    "4",
    "--timing",
    "--top",
    "tb",
]


# ===========================================================================
# Helpers
# ===========================================================================


def temp_parent_dir():
    """Prefer RealBench's tmpfs convention, with a portable fallback."""
    run_user_dir = f"/run/user/{os.getuid()}"
    if os.path.isdir(run_user_dir) and os.access(run_user_dir, os.W_OK):
        return run_user_dir
    return None


def run_command(command, cwd, env, timeout):
    """Run a command and convert timeout into a normal verification result."""
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            timeout=timeout,
            capture_output=True,
            env=env,
            text=True,
            errors="replace",
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
        return None, stdout, stderr
    return result.returncode, result.stdout, result.stderr


def parse_realbench_result(stdout):
    """Return ``(passed, message)`` from the testbench's stable Hint lines."""
    output_checks = []
    output_mismatches = []
    total_mismatches = None

    for line in stdout.splitlines():
        if "Hint: Output" in line:
            stripped = line.strip()
            output_checks.append(stripped)
            if "mismatches" in line and "no mismatches" not in line:
                output_mismatches.append(stripped)

        match = re.search(
            r"Hint:\s+Total mismatched samples is\s+(\d+)\s+out of\s+(\d+)\s+samples",
            line,
        )
        if match:
            total_mismatches = int(match.group(1))

    if "TIMEOUT" in stdout:
        return False, "Simulation timeout"
    if output_mismatches:
        return False, "Functional mismatches:\n" + "\n".join(
            output_mismatches[:10]
        )
    if total_mismatches is None:
        return False, "No RealBench mismatch summary found; simulation may not have run"
    if total_mismatches != 0:
        return False, (
            "Functional mismatches: Total mismatched samples is "
            f"{total_mismatches}"
        )
    if not output_checks:
        return False, "No RealBench output checks found; simulation may not have run"
    return True, "Passed"


def summarize_failure(stdout, stderr):
    """Keep actionable compiler/simulator diagnostics without dumping sources."""
    lines = []
    for line in (stderr + "\n" + stdout).splitlines():
        if (
            "%Error" in line
            or "%Warning" in line
            or "Error" in line
            or "error:" in line
            or "TIMEOUT" in line
            or "Hint: Output" in line
            or "Hint: Total mismatched" in line
        ):
            lines.append(line)
    if lines:
        return "\n".join(lines[:20])
    return (stderr + stdout)[-2000:]


def require_file(path, description):
    if not os.path.isfile(path):
        return f"{description} missing: {path}"
    return None


def collect_agent_files(generated_dir):
    """Collect the flat RTLAagent output while reserving the canonical header."""
    source_files = []
    support_files = []

    for filename in sorted(os.listdir(generated_dir)):
        path = os.path.join(generated_dir, filename)
        if not os.path.isfile(path) or filename in RESERVED_AGENT_FILES:
            continue
        if filename.endswith(AGENT_SOURCE_EXTENSIONS):
            source_files.append(path)
            support_files.append(path)
        elif filename.endswith(AGENT_HEADER_EXTENSIONS):
            support_files.append(path)

    return source_files, support_files


def golden_module_namespace():
    """Discover and namespace every dependency module in the golden hierarchy."""
    module_names = set()
    for filename in GOLDEN_REF_FILES:
        if filename == "sdc_controller_ref.sv":
            continue
        path = os.path.join(SYSTEM_TEST_DIR, filename)
        with open(path, "r", encoding="utf-8") as source_file:
            module_names.update(MODULE_DECLARATION_RE.findall(source_file.read()))

    return {name: f"ref_{name}" for name in sorted(module_names)}


def namespace_source(source, namespace):
    """Rename module declarations and references using identifier boundaries."""
    if not namespace:
        return source
    names = sorted(namespace, key=len, reverse=True)
    identifier_re = re.compile(r"\b(?:" + "|".join(map(re.escape, names)) + r")\b")
    return identifier_re.sub(lambda match: namespace[match.group(0)], source)


def stage_verification_files(temp_dir, support_files):
    """Build an isolated source tree and return explicit Verilator source paths."""
    dut_dir = os.path.join(temp_dir, "dut")
    golden_dir = os.path.join(temp_dir, "golden")
    os.makedirs(dut_dir)
    os.makedirs(golden_dir)

    canonical_src = os.path.join(SYSTEM_TEST_DIR, CANONICAL_HEADER)
    err = require_file(canonical_src, "Canonical configuration file")
    if err:
        return None, None, err
    shutil.copy2(canonical_src, os.path.join(temp_dir, CANONICAL_HEADER))

    testbench_src = os.path.join(SCRIPT_DIR, TESTBENCH_FILE)
    err = require_file(testbench_src, "Public testbench")
    if err:
        return None, None, err
    testbench_dst = os.path.join(temp_dir, TESTBENCH_FILE)
    shutil.copy2(testbench_src, testbench_dst)

    stimulus_src = os.path.join(SYSTEM_TEST_DIR, STIMULUS_FILE)
    err = require_file(stimulus_src, "Golden stimulus")
    if err:
        return None, None, err
    stimulus_dst = os.path.join(golden_dir, STIMULUS_FILE)
    shutil.copy2(stimulus_src, stimulus_dst)

    try:
        namespace = golden_module_namespace()
    except OSError as exc:
        return None, None, f"Unable to read golden reference sources: {exc}"

    golden_sources = []
    for filename in GOLDEN_REF_FILES:
        src = os.path.join(SYSTEM_TEST_DIR, filename)
        err = require_file(src, "Golden reference file")
        if err:
            return None, None, err
        with open(src, "r", encoding="utf-8") as source_file:
            transformed = namespace_source(source_file.read(), namespace)
        dst = os.path.join(golden_dir, "golden_" + filename)
        with open(dst, "w", encoding="utf-8") as output_file:
            output_file.write(transformed)
        golden_sources.append(dst)

    for src in support_files:
        shutil.copy2(src, os.path.join(dut_dir, os.path.basename(src)))

    dut_sources = [
        os.path.join(dut_dir, os.path.basename(src))
        for src in support_files
        if src.endswith(AGENT_SOURCE_EXTENSIONS)
    ]
    all_sources = [testbench_dst, stimulus_dst] + golden_sources + dut_sources
    include_dirs = [temp_dir, dut_dir]
    return all_sources, include_dirs, None


# ===========================================================================
# Verification
# ===========================================================================


def verify_system(generated_dir):
    if not os.path.isdir(generated_dir):
        return False, f"Agent source directory not found: {generated_dir}"

    agent_sources, support_files = collect_agent_files(generated_dir)
    if not agent_sources:
        return False, f"No .sv or .v files found in {generated_dir}"

    with tempfile.TemporaryDirectory(dir=temp_parent_dir()) as temp_dir:
        all_sources, include_dirs, error = stage_verification_files(
            temp_dir, support_files
        )
        if error:
            return False, error

        env = os.environ.copy()
        env["PATH"] = CONDA_REALBENCH_BIN + ":" + env.get("PATH", "")

        verilator_cmd = ["verilator"] + VERILATOR_FLAGS
        verilator_cmd.extend("-I" + directory for directory in include_dirs)
        verilator_cmd.extend(all_sources)

        returncode, stdout, stderr = run_command(
            verilator_cmd, temp_dir, env, timeout=300
        )
        if returncode is None:
            return False, "Verilator compilation timeout"
        if returncode != 0:
            return False, "Verilator compilation failed:\n" + summarize_failure(
                stdout, stderr
            )

        syntax_lines = [
            line
            for line in stderr.splitlines()
            if line.startswith("%Error") or line.startswith("%Warning")
        ]
        if syntax_lines:
            return False, "Syntax errors/warnings:\n" + "\n".join(syntax_lines[:10])

        simulation_binary = os.path.join(temp_dir, "obj_dir", "Vtb")
        if not os.path.isfile(simulation_binary):
            return False, "Verilator binary not found after compilation"

        returncode, sim_stdout, sim_stderr = run_command(
            [simulation_binary], temp_dir, env, timeout=300
        )
        if returncode is None:
            return False, "Simulation process timeout"
        if returncode != 0:
            return False, "Simulation failed:\n" + summarize_failure(
                sim_stdout, sim_stderr
            )

        return parse_realbench_result(sim_stdout)


def main():
    if len(sys.argv) != 2:
        print("Usage: python sdc_controller_system_verify.py <path_to_agent_src_dir>")
        print()
        print("  path_to_agent_src_dir : Directory containing the agent's")
        print("                          generated .sv / .v source files.")
        print()
        print("  The files must collectively define a module named 'sdc_controller'")
        print("  with the interface shown in sdc_controller_testbench.sv.")
        print()
        print("  Example:")
        print("    python sdc_controller_system_verify.py /tmp/my_sdc_output/")
        sys.exit(1)

    generated_dir = os.path.abspath(sys.argv[1])
    if not os.path.isdir(generated_dir):
        print(f"Error: {generated_dir} is not a directory")
        sys.exit(1)

    print(f"Verifying SDC controller system from: {generated_dir}")
    print("=" * 60)
    print("\n[sdc_controller_system] ", end="", flush=True)

    passed, message = verify_system(generated_dir)
    if passed:
        print("PASS")
    else:
        print(f"FAIL: {message}")

    print("\n" + "=" * 60)
    print("Summary:")
    print(f"  sdc_controller_system: {'PASS' if passed else 'FAIL'}")
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
