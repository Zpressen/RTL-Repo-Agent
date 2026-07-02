---
memory_id: debug_sd_cmd_master_NORMAL_INT_REG_improved_5
type: repair_outcome
stage: debug
description: "sd_cmd_master: NORMAL_INT_REG improved; Patch improved mismatch count or first fail time; continue from this direction."
module: sd_cmd_master
module_family: sdc
signals:
  - ERR_INT_REG
  - NORMAL_INT_REG
failure_type: interface_bug
alignment: wrong_value
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
  - ERR_INT_REG
  - NORMAL_INT_REG
trigger_failure_type: interface_bug
trigger_alignment: wrong_value
risk_signals:
  - ERR_INT_REG
  - NORMAL_INT_REG
patch_pattern: "endcase if (ERR_INT_RST) ERR_INT_REG <= 5'b00000; if (NORMAL_INT_RST) NORMAL_INT_REG <= 16'b0000000000000000;"
anti_trigger: "Do not reuse when current first divergence, affected signals, or timing alignment differ."
---

## 触发条件

- Module: `sd_cmd_master`
- Signal: `NORMAL_INT_REG`
- Effect: `improved`
- First divergence: `{"signal": "NORMAL_INT_REG", "time": 1105, "ref": "0000000000000011", "dut": "0000000000000101", "classification": "wrong_value", "ref_path": "tb.NORMAL_INT_REG_ref[15:0]", "dut_path": "tb.NORMAL_INT_REG_dut[15:0]", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "nonblocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`

## 不适用条件

- Do not reuse if affected signals, timing alignment, or spec intent differ.
- Do not reuse without reading current RTL/spec evidence.

## 补丁模式

endcase if (ERR_INT_RST) ERR_INT_REG <= 5'b00000; if (NORMAL_INT_RST) NORMAL_INT_REG <= 16'b0000000000000000;

## 验证特征

- Before mismatch count: `6564`
- After mismatch count: `4724`
- Metric delta: `{"total_samples_mismatch": "3331 -> 2208", "per_signal": {"ERR_INT_REG": {"before": 555, "after": 98, "first_time_before": 755, "first_time_after": 755, "direction": "improved"}, "NORMAL_INT_REG": {"before": 2571, "after": 1188, "first_time_before": 5, "first_time_after": 5, "direction": "improved"}, "RESP_1_REG": {"before": 202, "after": 202, "first_time_before": 1165, "first_time_after": 1165, "direction": "unchanged"}, "STATUS_REG": {"before": 471, "after": 471, "first_time_before": 485, "first_time_after": 485, "direction": "unchanged"}, "ack_out": {"before": 672, "after": 672, "first_time_before": 1105, "first_time_after": 1105, "direction": "unchanged"}, "errors_cmd_out": {"before": 644, "after": 644, "first_time_before": 485, "first_time_after": 485, "direction": "unchanged"}, "errors_go_idle_o": {"before": 4, "after": 4, "first_time_before": 755, "first_time_after": 755, "direction": "unchanged"}, "errors_req_out": {"before": 809, "after": 809, "first_time_before": 595, "first_time_after": 595, "direction": "unchanged"}, "errors_settings": {"before": 636, "after": 636, "first_time_before": 485, "first_time_after": 485, "direction": "unchanged"}}}`

## 复用约束

Patch improved mismatch count or first fail time; continue from this direction.

## Problem

`sd_cmd_master` showed a debug failure around `NORMAL_INT_REG`.

## Evidence

- Effect: `improved`
- Before mismatch count: `6564`
- After mismatch count: `4724`
- First divergence: `{"signal": "NORMAL_INT_REG", "time": 1105, "ref": "0000000000000011", "dut": "0000000000000101", "classification": "wrong_value", "ref_path": "tb.NORMAL_INT_REG_ref[15:0]", "dut_path": "tb.NORMAL_INT_REG_dut[15:0]", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "nonblocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`
- Trace root failure: `{"signal": "NORMAL_INT_REG", "time": 1105, "ref": "0000000000000011", "dut": "0000000000000101", "classification": "wrong_value", "ref_path": "tb.NORMAL_INT_REG_ref[15:0]", "dut_path": "tb.NORMAL_INT_REG_dut[15:0]", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "nonblocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`
- Metric delta: `{"total_samples_mismatch": "3331 -> 2208", "per_signal": {"ERR_INT_REG": {"before": 555, "after": 98, "first_time_before": 755, "first_time_after": 755, "direction": "improved"}, "NORMAL_INT_REG": {"before": 2571, "after": 1188, "first_time_before": 5, "first_time_after": 5, "direction": "improved"}, "RESP_1_REG": {"before": 202, "after": 202, "first_time_before": 1165, "first_time_after": 1165, "direction": "unchanged"}, "STATUS_REG": {"before": 471, "after": 471, "first_time_before": 485, "first_time_after": 485, "direction": "unchanged"}, "ack_out": {"before": 672, "after": 672, "first_time_before": 1105, "first_time_after": 1105, "direction": "unchanged"}, "errors_cmd_out": {"before": 644, "after": 644, "first_time_before": 485, "first_time_after": 485, "direction": "unchanged"}, "errors_go_idle_o": {"before": 4, "after": 4, "first_time_before": 755, "first_time_after": 755, "direction": "unchanged"}, "errors_req_out": {"before": 809, "after": 809, "first_time_before": 595, "first_time_after": 595, "direction": "unchanged"}, "errors_settings": {"before": 636, "after": 636, "first_time_before": 485, "first_time_after": 485, "direction": "unchanged"}}}`

## Patch Summary

endcase if (ERR_INT_RST) ERR_INT_REG <= 5'b00000; if (NORMAL_INT_RST) NORMAL_INT_REG <= 16'b0000000000000000;

## Lesson

Patch improved mismatch count or first fail time; continue from this direction.

## Reuse Constraints

- Read current RTL/spec evidence before applying a similar patch.
- Do not reuse if affected signals or timing alignment differ.
