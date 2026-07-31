#!/usr/bin/env python3
"""
System-level verification of agent-generated AES inverse cipher implementation.

Compiles the agent's complete AES-128 decryption implementation together
with the golden reference model and testbench, then runs Verilator
simulation to compare the agent's DUT output against the golden reference
cycle-by-cycle.

Usage:
    python aes_inv_cipher_system_verify.py <path_to_agent_src_dir>

Example:
    python aes_inv_cipher_system_verify.py /tmp/agent_output/

The agent's source directory must contain SystemVerilog (.sv) and/or
Verilog (.v) files that collectively define a module named
'aes_inv_cipher_top' with the interface shown in the testbench:
    aes_inv_cipher_top_testbench.sv (provided alongside this script).

Golden reference code is accessed from a separate system directory and
is never exposed to the agent through this script's arguments or output.
"""

import os
import re
import sys
import tempfile
import subprocess
import shutil

# ---------------------------------------------------------------------------
# Path configuration
# ---------------------------------------------------------------------------
REALBENCH_ROOT = "/home/mokita/RealBench"
SYSTEM_TEST_DIR = os.path.join(REALBENCH_ROOT, "system", "aes_inv_cipher_top")
CONDA_REALBENCH_BIN = "/home/mokita/miniconda3/envs/realbench/bin"
BUILD_ARTIFACTS = {"obj_dir", "logs", "coverage.dat", "wave.vcd"}

# ---------------------------------------------------------------------------
# Golden reference infrastructure files
# Copied from SYSTEM_TEST_DIR at runtime.  These implement the
# correct-behaviour oracle; they are NEVER shown to the agent.
#
# Files whose source filename (key) differs from the destination filename
# (value) are renamed at copy time.  All golden submodule files
# (aes_key_expand_128.v, aes_sbox.v, aes_rcon.v, aes_inv_sbox.v) define
# *ref_*-prefixed modules (e.g. ref_aes_key_expand_128) but share the same
# base filename the agent is likely to use for their own submodules.
# Renaming them avoids filename collisions while keeping both module
# name-spaces separate.
# ---------------------------------------------------------------------------
GOLDEN_REF_FILES = {
    "aes_inv_cipher_top_ref.sv":           "aes_inv_cipher_top_ref.sv",
    "aes_key_expand_128.v":                "ref_aes_key_expand_128.v",
    "aes_sbox.v":                          "ref_aes_sbox.v",
    "aes_rcon.v":                          "ref_aes_rcon.v",
    "aes_inv_sbox.v":                      "ref_aes_inv_sbox.v",
    "aes_inv_cipher_top_stimulus_gen.sv":  "aes_inv_cipher_top_stimulus_gen.sv",
}

# Testbench (also in SYSTEM_TEST_DIR); the agent may read a copy placed
# alongside this script to learn the expected DUT interface.
TESTBENCH_FILE = "aes_inv_cipher_top_testbench.sv"

# Files explicitly EXCLUDED from the build (golden DUT implementation).
# These must never be mixed with the agent's code.
GOLDEN_DUT_SOURCES = {
    "aes_inv_cipher_top_top.sv",
}

# Verilator flags matching the existing system-level Makefile
VERILATOR_FLAGS = [
    "-cc", "--exe", "--binary",
    "--trace", "--assert",
    "--coverage-line", "-fno-table",
    "-Wno-SIDEEFFECT", "-Wno-CASEOVERLAP", "-Wno-LATCH", "-Wno-UNOPTFLAT",
    "-Wno-MULTIDRIVEN", "-Wno-ASCRANGE", "-Wno-COMBDLY", "-Wno-IMPLICIT",
    "-Wno-CASEINCOMPLETE", "-Wno-PINMISSING", "-Wno-WIDTHTRUNC",
    "-Wno-TIMESCALEMOD", "-Wno-INITIALDLY", "-Wno-EOFNEWLINE",
    "-Wno-DECLFILENAME", "-Wno-WIDTHEXPAND",
    "-j", "4", "--timing", "-fno-table",
    "--top", "tb",
]


# ======================================================================
# Utility helpers
# ======================================================================

def temp_parent_dir():
    """Prefer RealBench's tmpfs convention, but fall back when it is unavailable."""
    run_user_dir = f"/run/user/{os.getuid()}"
    if os.path.isdir(run_user_dir) and os.access(run_user_dir, os.W_OK):
        return run_user_dir
    return None


def parse_realbench_result(stdout):
    """Return (passed: bool, message: str) from RealBench simulation output."""
    output_mismatches = []
    output_checks = []
    total_mismatches = None

    for line in stdout.splitlines():
        if "Hint: Output" in line:
            output_checks.append(line.strip())
            if "mismatches" in line and "no mismatches" not in line:
                output_mismatches.append(line.strip())

        match = re.search(
            r"Hint:\s+Total mismatched samples is\s+(\d+)\s+out of\s+(\d+)\s+samples",
            line,
        )
        if match:
            total_mismatches = int(match.group(1))

    if "TIMEOUT" in stdout:
        return False, "Simulation timeout"

    if output_mismatches:
        return False, "Functional mismatches:\n" + "\n".join(output_mismatches[:10])

    if total_mismatches is None:
        return False, "No RealBench mismatch summary found; simulation may not have run"

    if total_mismatches != 0:
        return False, f"Functional mismatches: Total mismatched samples is {total_mismatches}"

    if not output_checks:
        return False, "No RealBench output checks found; simulation may not have run"

    return True, "Passed"


def summarize_failure(stdout, stderr):
    """Extract the most relevant error lines from compilation / simulation output."""
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
    return "\n".join(lines[:20]) if lines else (stderr + stdout)[-2000:]


# ======================================================================
# Core verification logic
# ======================================================================

def verify_system(generated_dir):
    """Verify the agent's AES inverse cipher system against the golden reference.

    1. Create a temporary build directory.
    2. Copy golden reference infrastructure (NOT the golden DUT).
    3. Copy the testbench.
    4. Copy ALL of the agent's source files.
    5. Compile with Verilator.
    6. Run simulation.
    7. Parse and return the result.
    """
    if not os.path.isdir(generated_dir):
        return False, f"Agent source directory not found: {generated_dir}"

    # Collect agent source files
    agent_sources = []
    for ext in (".sv", ".v"):
        for f in sorted(os.listdir(generated_dir)):
            if f.endswith(ext):
                agent_sources.append(os.path.join(generated_dir, f))

    if not agent_sources:
        return False, f"No .sv or .v files found in {generated_dir}"

    with tempfile.TemporaryDirectory(dir=temp_parent_dir()) as temp_dir:
        # --- Stage 1: copy golden reference infrastructure ---
        for src_fname, dst_fname in GOLDEN_REF_FILES.items():
            src = os.path.join(SYSTEM_TEST_DIR, src_fname)
            if not os.path.exists(src):
                return False, f"Golden reference file missing: {src}"
            shutil.copy2(src, os.path.join(temp_dir, dst_fname))

        # --- Stage 2: copy testbench ---
        tb_src = os.path.join(SYSTEM_TEST_DIR, TESTBENCH_FILE)
        if not os.path.exists(tb_src):
            return False, f"Testbench file missing: {tb_src}"
        shutil.copy2(tb_src, os.path.join(temp_dir, TESTBENCH_FILE))

        # --- Stage 3: copy agent's source files ---
        for src in agent_sources:
            shutil.copy2(src, os.path.join(temp_dir, os.path.basename(src)))

        # --- Stage 4: compile with Verilator ---
        env = os.environ.copy()
        env["PATH"] = CONDA_REALBENCH_BIN + ":" + env.get("PATH", "")

        # Gather all source files in the temp directory
        all_sources = []
        for fname in sorted(os.listdir(temp_dir)):
            if fname.endswith(".sv") or fname.endswith(".v"):
                all_sources.append(fname)

        verilator_cmd = ["verilator"] + VERILATOR_FLAGS + all_sources

        result = subprocess.run(
            verilator_cmd,
            cwd=temp_dir,
            timeout=300,
            capture_output=True,
            env=env,
        )

        stderr = result.stderr.decode(errors="replace")
        stdout = result.stdout.decode(errors="replace")

        if result.returncode != 0:
            return False, "Verilator compilation failed:\n" + summarize_failure(stdout, stderr)

        # Check for syntax errors / warnings in stderr
        syntax_lines = [
            line for line in stderr.splitlines()
            if line.startswith("%Error") or line.startswith("%Warning")
        ]
        if syntax_lines:
            return False, "Syntax errors/warnings:\n" + "\n".join(syntax_lines[:10])

        # --- Stage 5: run simulation ---
        vtb_path = os.path.join(temp_dir, "obj_dir", "Vtb")
        if not os.path.exists(vtb_path):
            return False, "Verilator binary not found after compilation"

        sim_result = subprocess.run(
            [vtb_path],
            cwd=temp_dir,
            timeout=300,
            capture_output=True,
            env=env,
        )

        sim_stdout = sim_result.stdout.decode(errors="replace")

        return parse_realbench_result(sim_stdout)


# ======================================================================
# CLI entry point
# ======================================================================

def main():
    if len(sys.argv) != 2:
        print("Usage: python aes_inv_cipher_system_verify.py <path_to_agent_src_dir>")
        print()
        print("  path_to_agent_src_dir : Directory containing the agent's")
        print("                          generated .sv / .v source files.")
        print()
        print("  The agent's files must collectively define a module named")
        print("  'aes_inv_cipher_top' with the interface shown in the testbench:")
        print("    aes_inv_cipher_top_testbench.sv")
        print()
        print("  Expected DUT interface:")
        print("    aes_inv_cipher_top(clk, rst, kld, ld, done, key, text_in, text_out)")
        print("    - clk      : input  1")
        print("    - rst      : input  1")
        print("    - kld      : input  1     (key load enable)")
        print("    - ld       : input  1     (data load enable)")
        print("    - done     : output 1     (decryption complete)")
        print("    - key      : input  128   (cipher key)")
        print("    - text_in  : input  128   (ciphertext)")
        print("    - text_out : output 128   (plaintext)")
        print()
        print("  Example:")
        print("    python aes_inv_cipher_system_verify.py /tmp/my_aes_output/")
        sys.exit(1)

    generated_dir = sys.argv[1]

    if not os.path.isdir(generated_dir):
        print(f"Error: {generated_dir} is not a directory")
        sys.exit(1)

    print(f"Verifying AES inverse cipher system from: {generated_dir}")
    print("=" * 60)

    print("\n[aes_inv_cipher_top_system] ", end="", flush=True)
    passed, msg = verify_system(generated_dir)

    if passed:
        print("PASS")
    else:
        print(f"FAIL: {msg}")

    print("\n" + "=" * 60)
    print("Summary:")
    print(f"  aes_inv_cipher_top_system: {'PASS' if passed else 'FAIL'}")

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
