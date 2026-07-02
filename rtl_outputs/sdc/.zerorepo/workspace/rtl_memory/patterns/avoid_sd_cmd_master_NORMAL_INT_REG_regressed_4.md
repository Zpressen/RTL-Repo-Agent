---
memory_id: avoid_sd_cmd_master_NORMAL_INT_REG_regressed_4
type: negative_direction
stage: debug
description: "sd_cmd_master: NORMAL_INT_REG regressed; Patch worsened mismatch count or first fail time and was rolled back."
module: sd_cmd_master
module_family: sdc
signals:
  - ERR_INT_REG
  - NORMAL_INT_REG
  - RESP_1_REG
  - Watchdog_Cnt
  - ack_out
  - complete
  - go_idle_o
  - req_out
  - status
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
  - ERR_INT_REG
  - NORMAL_INT_REG
  - RESP_1_REG
  - Watchdog_Cnt
  - ack_out
  - complete
  - go_idle_o
  - req_out
  - status
trigger_failure_type: timing_bug
trigger_alignment: unknown
risk_signals:
  - ERR_INT_REG
  - NORMAL_INT_REG
  - RESP_1_REG
  - Watchdog_Cnt
  - ack_out
  - complete
  - go_idle_o
  - req_out
  - status
patch_pattern: "EXECUTE: begin Watchdog_Cnt <= Watchdog_Cnt + 16'b0000000000000001; if (Watchdog_Cnt > TIM\n...<snip>...\nT_REG[CC] <= 1'b1; if (response_present) begin RESP_1_REG <= cmd_in[31:0]; e"
anti_trigger: "Avoid this direction unless new evidence distinguishes the current failure."
---

## 触发条件

- Module: `sd_cmd_master`
- Signal: `NORMAL_INT_REG`
- Effect: `regressed`
- First divergence: `{"signal": "NORMAL_INT_REG", "time": 5, "ref": "0000000000000100", "dut": "0000000000000000", "classification": "unknown", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "ref_path": "tb.NORMAL_INT_REG_ref[15:0]", "dut_path": "tb.NORMAL_INT_REG_dut[15:0]"}`

## 不适用条件

- Do not reuse if affected signals, timing alignment, or spec intent differ.
- Do not reuse without reading current RTL/spec evidence.

## 补丁模式

EXECUTE: begin Watchdog_Cnt <= Watchdog_Cnt + 16'b0000000000000001; if (Watchdog_Cnt > TIM
...<snip>...
T_REG[CC] <= 1'b1; if (response_present) begin RESP_1_REG <= cmd_in[31:0]; end end end end

## 验证特征

- Before mismatch count: `4723`
- After mismatch count: `4739`
- Metric delta: `{"total_samples_mismatch": "2207 -> 2215", "per_signal": {"ERR_INT_REG": {"before": 98, "after": 100, "first_time_before": 755, "first_time_after": 755, "direction": "regressed"}, "NORMAL_INT_REG": {"before": 1187, "after": 1189, "first_time_before": 5, "first_time_after": 5, "direction": "regressed"}, "RESP_1_REG": {"before": 202, "after": 202, "first_time_before": 1165, "first_time_after": 1165, "direction": "unchanged"}, "STATUS_REG": {"before": 471, "after": 473, "first_time_before": 485, "first_time_after": 485, "direction": "regressed"}, "ack_out": {"before": 672, "after": 672, "first_time_before": 1105, "first_time_after": 1105, "direction": "unchanged"}, "errors_cmd_out": {"before": 644, "after": 644, "first_time_before": 485, "first_time_after": 485, "direction": "unchanged"}, "errors_go_idle_o": {"before": 4, "after": 10, "first_time_before": 755, "first_time_after": 755, "direction": "regressed"}, "errors_req_out": {"before": 809, "after": 813, "first_time_before": 595, "first_time_after": 595, "direction": "regressed"}, "errors_settings": {"before": 636, "after": 636, "first_time_before": 485, "first_time_after": 485, "direction": "unchanged"}}}`

## 复用约束

Patch worsened mismatch count or first fail time and was rolled back.

## Problem

`sd_cmd_master` showed a debug failure around `NORMAL_INT_REG`.

## Evidence

- Effect: `regressed`
- Before mismatch count: `4723`
- After mismatch count: `4739`
- First divergence: `{"signal": "NORMAL_INT_REG", "time": 5, "ref": "0000000000000100", "dut": "0000000000000000", "classification": "unknown", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "ref_path": "tb.NORMAL_INT_REG_ref[15:0]", "dut_path": "tb.NORMAL_INT_REG_dut[15:0]"}`
- Trace root failure: `{"signal": "NORMAL_INT_REG", "time": 5, "ref": "0000000000000100", "dut": "0000000000000000", "classification": "unknown", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "ref_path": "tb.NORMAL_INT_REG_ref[15:0]", "dut_path": "tb.NORMAL_INT_REG_dut[15:0]"}`
- Metric delta: `{"total_samples_mismatch": "2207 -> 2215", "per_signal": {"ERR_INT_REG": {"before": 98, "after": 100, "first_time_before": 755, "first_time_after": 755, "direction": "regressed"}, "NORMAL_INT_REG": {"before": 1187, "after": 1189, "first_time_before": 5, "first_time_after": 5, "direction": "regressed"}, "RESP_1_REG": {"before": 202, "after": 202, "first_time_before": 1165, "first_time_after": 1165, "direction": "unchanged"}, "STATUS_REG": {"before": 471, "after": 473, "first_time_before": 485, "first_time_after": 485, "direction": "regressed"}, "ack_out": {"before": 672, "after": 672, "first_time_before": 1105, "first_time_after": 1105, "direction": "unchanged"}, "errors_cmd_out": {"before": 644, "after": 644, "first_time_before": 485, "first_time_after": 485, "direction": "unchanged"}, "errors_go_idle_o": {"before": 4, "after": 10, "first_time_before": 755, "first_time_after": 755, "direction": "regressed"}, "errors_req_out": {"before": 809, "after": 813, "first_time_before": 595, "first_time_after": 595, "direction": "regressed"}, "errors_settings": {"before": 636, "after": 636, "first_time_before": 485, "first_time_after": 485, "direction": "unchanged"}}}`

## Patch Summary

EXECUTE: begin Watchdog_Cnt <= Watchdog_Cnt + 16'b0000000000000001; if (Watchdog_Cnt > TIM
...<snip>...
T_REG[CC] <= 1'b1; if (response_present) begin RESP_1_REG <= cmd_in[31:0]; end end end end

## Lesson

Patch worsened mismatch count or first fail time and was rolled back.

## Reuse Constraints

- Read current RTL/spec evidence before applying a similar patch.
- Do not reuse if affected signals or timing alignment differ.
