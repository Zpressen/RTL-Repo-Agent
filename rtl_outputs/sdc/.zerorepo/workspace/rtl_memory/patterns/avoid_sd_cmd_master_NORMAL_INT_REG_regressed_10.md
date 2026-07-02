---
memory_id: avoid_sd_cmd_master_NORMAL_INT_REG_regressed_10
type: negative_direction
stage: debug
description: "sd_cmd_master: NORMAL_INT_REG regressed; Patch worsened mismatch count or first fail time and was rolled back."
module: sd_cmd_master
module_family: sdc
signals:
  - NORMAL_INT_REG
  - state
failure_type: timing_bug
alignment: unknown
outcome: regressed
confidence: 0.68
verified_by:
  - lint
  - module_sim
  - trace
source_artifacts:
  - debug/sd_cmd_master/trace_report.json
  - repo_react/sd_cmd_master/patch_journal.jsonl
trigger_signals:
  - NORMAL_INT_REG
  - state
trigger_failure_type: timing_bug
trigger_alignment: unknown
risk_signals:
  - state
patch_pattern: "always @(posedge CLK_PAD_IO or posedge RST_PAD_I) begin if (RST_PAD_I) state <= IDLE; else state <= next_state; end"
anti_trigger: "Avoid this direction unless new evidence distinguishes the current failure."
---

## 触发条件

- Module: `sd_cmd_master`
- Signal: `NORMAL_INT_REG`
- Effect: `regressed`
- First divergence: `{"signal": "NORMAL_INT_REG", "time": 5, "ref": "0000000000000100", "dut": "0000000000000000", "classification": "unknown", "ref_path": "tb.NORMAL_INT_REG_ref[15:0]", "dut_path": "tb.NORMAL_INT_REG_dut[15:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`

## 不适用条件

- Do not reuse if affected signals, timing alignment, or spec intent differ.
- Do not reuse without reading current RTL/spec evidence.

## 补丁模式

always @(posedge CLK_PAD_IO or posedge RST_PAD_I) begin if (RST_PAD_I) state <= IDLE; else state <= next_state; end

## 验证特征

- Before mismatch count: `4723`
- After mismatch count: `9047`
- Metric delta: `{"total_samples_mismatch": "2207 -> 3249", "per_signal": {"ERR_INT_REG": {"before": 98, "after": 146, "first_time_before": 755, "first_time_after": 755, "direction": "regressed"}, "NORMAL_INT_REG": {"before": 1187, "after": 1400, "first_time_before": 5, "first_time_after": 5, "direction": "regressed"}, "RESP_1_REG": {"before": 202, "after": 632, "first_time_before": 1165, "first_time_after": 1165, "direction": "regressed"}, "STATUS_REG": {"before": 471, "after": 897, "first_time_before": 485, "first_time_after": 480, "direction": "regressed"}, "ack_out": {"before": 672, "after": 957, "first_time_before": 1105, "first_time_after": 1105, "direction": "regressed"}, "errors_cmd_out": {"before": 644, "after": 2062, "first_time_before": 485, "first_time_after": 480, "direction": "regressed"}, "errors_go_idle_o": {"before": 4, "after": 4, "first_time_before": 755, "first_time_after": 755, "direction": "unchanged"}, "errors_req_out": {"before": 809, "after": 928, "first_time_before": 595, "first_time_after": 595, "direction": "regressed"}, "errors_settings": {"before": 636, "after": 2021, "first_time_before": 485, "first_time_after": 480, "direction": "regressed"}}}`

## 复用约束

Patch worsened mismatch count or first fail time and was rolled back.

## Problem

`sd_cmd_master` showed a debug failure around `NORMAL_INT_REG`.

## Evidence

- Effect: `regressed`
- Before mismatch count: `4723`
- After mismatch count: `9047`
- First divergence: `{"signal": "NORMAL_INT_REG", "time": 5, "ref": "0000000000000100", "dut": "0000000000000000", "classification": "unknown", "ref_path": "tb.NORMAL_INT_REG_ref[15:0]", "dut_path": "tb.NORMAL_INT_REG_dut[15:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`
- Trace root failure: `{"signal": "NORMAL_INT_REG", "time": 5, "ref": "0000000000000100", "dut": "0000000000000000", "classification": "unknown", "ref_path": "tb.NORMAL_INT_REG_ref[15:0]", "dut_path": "tb.NORMAL_INT_REG_dut[15:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`
- Metric delta: `{"total_samples_mismatch": "2207 -> 3249", "per_signal": {"ERR_INT_REG": {"before": 98, "after": 146, "first_time_before": 755, "first_time_after": 755, "direction": "regressed"}, "NORMAL_INT_REG": {"before": 1187, "after": 1400, "first_time_before": 5, "first_time_after": 5, "direction": "regressed"}, "RESP_1_REG": {"before": 202, "after": 632, "first_time_before": 1165, "first_time_after": 1165, "direction": "regressed"}, "STATUS_REG": {"before": 471, "after": 897, "first_time_before": 485, "first_time_after": 480, "direction": "regressed"}, "ack_out": {"before": 672, "after": 957, "first_time_before": 1105, "first_time_after": 1105, "direction": "regressed"}, "errors_cmd_out": {"before": 644, "after": 2062, "first_time_before": 485, "first_time_after": 480, "direction": "regressed"}, "errors_go_idle_o": {"before": 4, "after": 4, "first_time_before": 755, "first_time_after": 755, "direction": "unchanged"}, "errors_req_out": {"before": 809, "after": 928, "first_time_before": 595, "first_time_after": 595, "direction": "regressed"}, "errors_settings": {"before": 636, "after": 2021, "first_time_before": 485, "first_time_after": 480, "direction": "regressed"}}}`

## Patch Summary

always @(posedge CLK_PAD_IO or posedge RST_PAD_I) begin if (RST_PAD_I) state <= IDLE; else state <= next_state; end

## Lesson

Patch worsened mismatch count or first fail time and was rolled back.

## Reuse Constraints

- Read current RTL/spec evidence before applying a similar patch.
- Do not reuse if affected signals or timing alignment differ.
