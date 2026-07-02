---
memory_id: debug_sd_cmd_master_req_out_improved_2
type: repair_outcome
stage: debug
description: "sd_cmd_master: req_out improved; Patch improved mismatch count or first fail time; continue from this direction."
module: sd_cmd_master
module_family: sdc
signals:
  - req_out
  - state
failure_type: timing_bug
alignment: dut_late
outcome: improved
confidence: 0.72
verified_by:
  - lint
  - module_sim
  - trace
source_artifacts:
  - debug/sd_cmd_master/trace_report.json
  - repo_react/sd_cmd_master/patch_journal.jsonl
trigger_signals:
  - req_out
  - state
trigger_failure_type: timing_bug
trigger_alignment: dut_late
risk_signals:
  - state
patch_pattern: "state <= #1 next_state;"
anti_trigger: "Do not reuse when current first divergence, affected signals, or timing alignment differ."
---

## 触发条件

- Module: `sd_cmd_master`
- Signal: `req_out`
- Effect: `improved`
- First divergence: `{"signal": "req_out", "time": 685, "ref": "0", "dut": "1", "classification": "dut_late", "ref_path": "tb.req_out_ref", "dut_path": "tb.req_out_dut", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "nonblocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`

## 不适用条件

- Do not reuse if affected signals, timing alignment, or spec intent differ.
- Do not reuse without reading current RTL/spec evidence.

## 补丁模式

state <= #1 next_state;

## 验证特征

- Before mismatch count: `12515`
- After mismatch count: `8114`
- Metric delta: `{"total_samples_mismatch": "4286 -> 3890", "per_signal": {"ERR_INT_REG": {"before": 683, "after": 557, "first_time_before": 755, "first_time_after": 755, "direction": "improved"}, "NORMAL_INT_REG": {"before": 2789, "after": 2573, "first_time_before": 5, "first_time_after": 5, "direction": "improved"}, "RESP_1_REG": {"before": 632, "after": 202, "first_time_before": 1165, "first_time_after": 1165, "direction": "improved"}, "STATUS_REG": {"before": 899, "after": 473, "first_time_before": 480, "first_time_after": 485, "direction": "improved"}, "ack_out": {"before": 1910, "after": 1639, "first_time_before": 1105, "first_time_after": 1105, "direction": "improved"}, "errors_cmd_out": {"before": 2062, "after": 644, "first_time_before": 480, "first_time_after": 485, "direction": "improved"}, "errors_go_idle_o": {"before": 10, "after": 10, "first_time_before": 755, "first_time_after": 755, "direction": "unchanged"}, "errors_req_out": {"before": 1509, "after": 1380, "first_time_before": 595, "first_time_after": 595, "direction": "improved"}, "errors_settings": {"before": 2021, "after": 636, "first_time_before": 480, "first_time_after": 485, "direction": "improved"}}}`

## 复用约束

Patch improved mismatch count or first fail time; continue from this direction.

## Problem

`sd_cmd_master` showed a debug failure around `req_out`.

## Evidence

- Effect: `improved`
- Before mismatch count: `12515`
- After mismatch count: `8114`
- First divergence: `{"signal": "req_out", "time": 685, "ref": "0", "dut": "1", "classification": "dut_late", "ref_path": "tb.req_out_ref", "dut_path": "tb.req_out_dut", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "nonblocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`
- Trace root failure: `{"signal": "req_out", "time": 685, "ref": "0", "dut": "1", "classification": "dut_late", "ref_path": "tb.req_out_ref", "dut_path": "tb.req_out_dut", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "nonblocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`
- Metric delta: `{"total_samples_mismatch": "4286 -> 3890", "per_signal": {"ERR_INT_REG": {"before": 683, "after": 557, "first_time_before": 755, "first_time_after": 755, "direction": "improved"}, "NORMAL_INT_REG": {"before": 2789, "after": 2573, "first_time_before": 5, "first_time_after": 5, "direction": "improved"}, "RESP_1_REG": {"before": 632, "after": 202, "first_time_before": 1165, "first_time_after": 1165, "direction": "improved"}, "STATUS_REG": {"before": 899, "after": 473, "first_time_before": 480, "first_time_after": 485, "direction": "improved"}, "ack_out": {"before": 1910, "after": 1639, "first_time_before": 1105, "first_time_after": 1105, "direction": "improved"}, "errors_cmd_out": {"before": 2062, "after": 644, "first_time_before": 480, "first_time_after": 485, "direction": "improved"}, "errors_go_idle_o": {"before": 10, "after": 10, "first_time_before": 755, "first_time_after": 755, "direction": "unchanged"}, "errors_req_out": {"before": 1509, "after": 1380, "first_time_before": 595, "first_time_after": 595, "direction": "improved"}, "errors_settings": {"before": 2021, "after": 636, "first_time_before": 480, "first_time_after": 485, "direction": "improved"}}}`

## Patch Summary

state <= #1 next_state;

## Lesson

Patch improved mismatch count or first fail time; continue from this direction.

## Reuse Constraints

- Read current RTL/spec evidence before applying a similar patch.
- Do not reuse if affected signals or timing alignment differ.
