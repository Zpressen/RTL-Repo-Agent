"""Exact VCD transitions and independently observed testbench counters."""

from __future__ import annotations
from bisect import bisect_right
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
import signal
import threading
from typing import Any
# vcdvcd installs the CLI default for SIGPIPE at import time. Preserve the
# host application's handler so a disconnected HTTP/SDK pipe cannot kill it.
_sigpipe_handler = (signal.getsignal(signal.SIGPIPE)
                    if hasattr(signal, 'SIGPIPE') and threading.current_thread() is threading.main_thread()
                    else None)
try:
    from vcdvcd import VCDVCD
finally:
    if _sigpipe_handler is not None:
        signal.signal(signal.SIGPIPE, _sigpipe_handler)
from .artifacts import sha
from .schemas import DemoError

LAYOUT_HASH = "7e5618937902926343edd8bcda8e2d6a13c6c6b0c1f50da5fa165612bb923f41"
KNOWN_TB_HASH = "9b0ed0a069b71bdfc4b1a3132b355b36a8bd87210ac969e1b4b327e0a9f25a2e"
KEY_SIGNALS = [
    "clk",
    "rst_n",
    "i_valid",
    "i_ready_dut",
    "i_ready_ref",
    "cmt_o_ready",
    "wbck_o_ready",
    "wbck_o_valid_dut",
    "wbck_o_valid_ref",
    "wbck_o_wdat_dut",
    "wbck_o_wdat_ref",
]


def stats_layout(text: str) -> list[str]:
    m = re.search(r"typedef\s+struct\s+packed\s*\{(.*?)\}\s*stats\s*;", text, re.S)
    return re.findall(r"\bint\s+(\w+)\s*;", m.group(1)) if m else []


@lru_cache(maxsize=4)
def read_vcd(path: str, digest: str):
    p = Path(path)
    if p.stat().st_size > 256 * 1024 * 1024:
        raise DemoError("waveform_too_large", "波形超过首版解析上限。", 413)
    if sha(p) != digest:
        raise DemoError("evidence_inconsistent", "波形摘要与验证记录不一致。", 409)
    try:
        from .cases import CASES

        wanted = {name for c in CASES.values() for name in c["signals"]} | {"stats1"}
        wanted.update(name + suffix for name in ['sd_cmd_oe_o', 'int_a', 'int_b'] for suffix in ['_dut', '_ref'])
        header = VCDVCD(str(p), only_sigs=True)
        selected = [
            name
            for name in header.signals
            if name.split("[")[0].strip() in {"tb." + n for n in wanted}
        ]
        return VCDVCD(str(p), signals=selected, store_tvs=True)
    except Exception as error:
        raise DemoError("waveform_invalid", "波形文件无法解析。", 422) from error


def signal(vcd, name: str):
    matches = [n for n in vcd.signals if n.split("[")[0].strip() == "tb." + name]
    if not matches:
        return None, None
    if len(matches) > 1:
        raise DemoError("signal_ambiguous", "波形信号映射不唯一。", 422)
    return matches[0], vcd[matches[0]]


def counter_markers(vcd, fields: list[str], total: int | None, mismatches: int | None):
    return _counter_markers(vcd, tuple(fields), total, mismatches)


def verify_signal_counters(vcd, fields: list[str], reported: list[dict], verdict: str):
    """Check every per-output terminal counter and first error against a report."""
    status, _ = counter_markers(vcd, fields, None, None)
    _, stats = signal(vcd, 'stats1')
    if status != 'verified' or not stats or not stats.tv or re.search('[xz]', stats.tv[-1][1], re.I):
        raise DemoError('evidence_inconsistent', '缺少可核对的测试平台输出计数。', 422)
    bits = int(stats.tv[-1][1], 2)
    values = {name: (bits >> ((len(fields) - 1 - i) * 32)) & 0xffffffff for i, name in enumerate(fields)}
    actual = {name[7:]: count for name, count in values.items() if name.startswith('errors_') and count}
    expected = {r['signal']: r['count'] for r in reported}
    if actual != expected or len(expected) != len(reported) or (verdict == 'pass' and (actual or values['errors'])):
        raise DemoError('evidence_inconsistent', '报告与波形的各输出差异计数不一致。', 422)
    for r in reported:
        if values.get('errortime_' + r['signal']) != int(r['first_failure_ticks']):
            raise DemoError('evidence_inconsistent', '报告与波形的输出首次差异时刻不一致。', 422)
    return 'verified'


@lru_cache(maxsize=16)
def _counter_markers(vcd, fields, total, mismatches):
    layout_hash = hashlib.sha256("\n".join(fields).encode()).hexdigest()
    _, stats = signal(vcd, "stats1")
    known = {LAYOUT_HASH}
    evidence_path = (
        Path(__file__).resolve().parents[2] / "configs/rtl_demo_cases.evidence.json"
    )
    if evidence_path.is_file():
        known.update(
            hashlib.sha256("\n".join(c["stats_fields"]).encode()).hexdigest()
            for c in json.loads(evidence_path.read_text()).values()
        )
    if stats is None or layout_hash not in known or int(stats.size) != len(fields) * 32:
        return "unsupported", []
    previous = {name: 0 for name in fields}
    markers = []
    for tick, binary in stats.tv:
        if re.search("[xz]", binary, re.I):
            continue
        bits = int(binary, 2)
        values = {
            field: (bits >> ((len(fields) - 1 - i) * 32)) & 0xFFFFFFFF
            for i, field in enumerate(fields)
        }
        dc = values["clocks"] - previous["clocks"]
        de = values["errors"] - previous["errors"]
        if dc < 0 or dc > 1 or de < 0 or de > dc:
            raise DemoError(
                "evidence_inconsistent", "采样计数变化无法与测试平台对齐。", 422
            )
        if dc:
            failures = [
                k[7:]
                for k in fields
                if k.startswith("errors_") and values[k] > previous[k]
            ]
            markers.append(
                {
                    "time_ticks": str(tick),
                    "sample_index": values["clocks"],
                    "verdict": "fail" if de else "pass",
                    "failed_signals": failures,
                    "source": "testbench_counter_delta",
                    "sampled_value_available": False,
                }
            )
        previous = values
    if total is not None and (
        previous["clocks"] != total or previous["errors"] != mismatches
    ):
        raise DemoError("evidence_inconsistent", "报告与波形的采样计数不一致。", 422)
    return "verified", markers


def waveform_data(
    path: Path,
    digest: str,
    fields: list[str],
    validation: dict,
    start: int | None = None,
    end: int | None = None,
    max_changes: int = 20000,
    signal_names: list[str] | None = None,
) -> dict:
    vcd = read_vcd(str(path), digest)
    start = 0 if start is None else start
    end = int(vcd.endtime) + 1 if end is None else end
    full_end = int(vcd.endtime) + 1
    if start >= full_end:
        raise DemoError(
            "invalid_window",
            "窗口超出本次仿真的时间范围。",
            422,
            full_end_ticks=str(full_end),
        )
    end = min(end, full_end)
    if start < 0 or end <= start:
        raise DemoError("invalid_window", "波形窗口范围无效。", 422)
    status, markers = counter_markers(
        vcd,
        fields,
        validation.get("total_samples"),
        validation.get("mismatched_samples"),
    )
    signals = []
    missing = []
    count = 0
    for name in signal_names or validation.get("signal_names") or KEY_SIGNALS:
        full, item = signal(vcd, name)
        if item is None:
            missing.append(name)
            continue
        tv = item.tv
        times = [t for t, _ in tv]
        idx = bisect_right(times, start)
        initial = tv[idx - 1][1] if idx else "x" * int(item.size)
        stop = bisect_right(times, end - 1)
        changes = [[str(t), value] for t, value in tv[idx:stop]]
        count += len(changes)
        if count > max_changes:
            raise DemoError(
                "window_too_large",
                "变化数量过多，请缩小波形窗口。",
                413,
                suggested_end_ticks=str(start + max(1, (end - start) // 2)),
            )
        signals.append(
            {
                "id": name,
                "full_path": full,
                "width": int(item.size),
                "initial_value": initial,
                "changes": changes,
            }
        )
    ts = vcd.timescale
    return {
        "validation_id": validation["validation_id"],
        "version_id": validation["version_id"],
        "waveform_sha256": digest,
        "timescale": {
            "value": int(ts.get("magnitude", 1)),
            "unit": str(ts.get("unit", "ps")),
        },
        "start_ticks": str(start),
        "end_ticks": str(end),
        "full_end_ticks": str(int(vcd.endtime) + 1),
        "signals": signals,
        "sample_markers": [m for m in markers if start <= int(m["time_ticks"]) < end],
        "marker_status": status,
        "missing_signals": missing,
        "comparison_policy_id": validation.get(
            "comparison_policy_id", "e203-posedge-stats-v1"
        ),
        "truncated": False,
    }
