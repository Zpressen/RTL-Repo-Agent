---
memory_id: debug_sd_cmd_master_NORMAL_INT_REG_improved_6
type: repair_outcome
stage: debug
description: "sd_cmd_master: NORMAL_INT_REG improved; Patch improved mismatch count or first fail time; continue from this direction."
module: sd_cmd_master
module_family: sdc
signals:
  - NORMAL_INT_REG
  - card_present
  - debounce
failure_type: timing_bug
alignment: unknown
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
  - NORMAL_INT_REG
  - card_present
  - debounce
trigger_failure_type: timing_bug
trigger_alignment: unknown
risk_signals:
  - card_present
  - debounce
patch_pattern: "end else begin debounce     <= 4'b0000; end"
anti_trigger: "Do not reuse when current first divergence, affected signals, or timing alignment differ."
---

## 触发条件

- Module: `sd_cmd_master`
- Signal: `NORMAL_INT_REG`
- Effect: `improved`
- First divergence: `{"signal": "NORMAL_INT_REG", "time": 5, "ref": "0000000000000100", "dut": "0000000000000000", "classification": "unknown", "ref_path": "tb.NORMAL_INT_REG_ref[15:0]", "dut_path": "tb.NORMAL_INT_REG_dut[15:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`

## 不适用条件

- Do not reuse if affected signals, timing alignment, or spec intent differ.
- Do not reuse without reading current RTL/spec evidence.

## 补丁模式

end else begin debounce     <= 4'b0000; end

## 验证特征

- Before mismatch count: `4724`
- After mismatch count: `4723`
- Metric delta: `{"total_samples_mismatch": "2208 -> 2207", "per_signal": {"ERR_INT_REG": {"before": 98, "after": 98, "first_time_before": 755, "first_time_after": 755, "direction": "unchanged"}, "NORMAL_INT_REG": {"before": 1188, "after": 1187, "first_time_before": 5, "first_time_after": 5, "direction": "improved"}, "RESP_1_REG": {"before": 202, "after": 202, "first_time_before": 1165, "first_time_after": 1165, "direction": "unchanged"}, "STATUS_REG": {"before": 471, "after": 471, "first_time_before": 485, "first_time_after": 485, "direction": "unchanged"}, "ack_out": {"before": 672, "after": 672, "first_time_before": 1105, "first_time_after": 1105, "direction": "unchanged"}, "errors_cmd_out": {"before": 644, "after": 644, "first_time_before": 485, "first_time_after": 485, "direction": "unchanged"}, "errors_go_idle_o": {"before": 4, "after": 4, "first_time_before": 755, "first_time_after": 755, "direction": "unchanged"}, "errors_req_out": {"before": 809, "after": 809, "first_time_before": 595, "first_time_after": 595, "direction": "unchanged"}, "errors_settings": {"before": 636, "after": 636, "first_time_before": 485, "first_time_after": 485, "direction": "unchanged"}}}`

## 复用约束

Patch improved mismatch count or first fail time; continue from this direction.

## Problem

`sd_cmd_master` showed a debug failure around `NORMAL_INT_REG`.

## Evidence

- Effect: `improved`
- Before mismatch count: `4724`
- After mismatch count: `4723`
- First divergence: `{"signal": "NORMAL_INT_REG", "time": 5, "ref": "0000000000000100", "dut": "0000000000000000", "classification": "unknown", "ref_path": "tb.NORMAL_INT_REG_ref[15:0]", "dut_path": "tb.NORMAL_INT_REG_dut[15:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`
- Trace root failure: `{"signal": "NORMAL_INT_REG", "time": 5, "ref": "0000000000000100", "dut": "0000000000000000", "classification": "unknown", "ref_path": "tb.NORMAL_INT_REG_ref[15:0]", "dut_path": "tb.NORMAL_INT_REG_dut[15:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`
- Metric delta: `{"total_samples_mismatch": "2208 -> 2207", "per_signal": {"ERR_INT_REG": {"before": 98, "after": 98, "first_time_before": 755, "first_time_after": 755, "direction": "unchanged"}, "NORMAL_INT_REG": {"before": 1188, "after": 1187, "first_time_before": 5, "first_time_after": 5, "direction": "improved"}, "RESP_1_REG": {"before": 202, "after": 202, "first_time_before": 1165, "first_time_after": 1165, "direction": "unchanged"}, "STATUS_REG": {"before": 471, "after": 471, "first_time_before": 485, "first_time_after": 485, "direction": "unchanged"}, "ack_out": {"before": 672, "after": 672, "first_time_before": 1105, "first_time_after": 1105, "direction": "unchanged"}, "errors_cmd_out": {"before": 644, "after": 644, "first_time_before": 485, "first_time_after": 485, "direction": "unchanged"}, "errors_go_idle_o": {"before": 4, "after": 4, "first_time_before": 755, "first_time_after": 755, "direction": "unchanged"}, "errors_req_out": {"before": 809, "after": 809, "first_time_before": 595, "first_time_after": 595, "direction": "unchanged"}, "errors_settings": {"before": 636, "after": 636, "first_time_before": 485, "first_time_after": 485, "direction": "unchanged"}}}`

## Patch Summary

end else begin debounce     <= 4'b0000; end

## Lesson

Patch improved mismatch count or first fail time; continue from this direction.

## Reuse Constraints

- Read current RTL/spec evidence before applying a similar patch.
- Do not reuse if affected signals or timing alignment differ.
