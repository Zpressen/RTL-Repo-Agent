---
memory_id: avoid_sd_controller_wb_int_busy_regressed_15
type: negative_direction
stage: debug
description: "sd_controller_wb: int_busy regressed; Patch worsened mismatch count or first fail time and was rolled back."
module: sd_controller_wb
module_family: sdc
signals:
  - int_busy
  - int_busy_next
failure_type: interface_bug
alignment: dut_late
outcome: regressed
confidence: 0.68
verified_by:
  - lint
  - module_sim
  - trace
source_artifacts:
  - debug/sd_controller_wb/trace_report.json
  - repo_react/sd_controller_wb/patch_journal.jsonl
trigger_signals:
  - int_busy
  - int_busy_next
trigger_failure_type: interface_bug
trigger_alignment: dut_late
risk_signals:
  - int_busy_next
patch_pattern: "int_busy_next                     = write_req_s;"
anti_trigger: "Avoid this direction unless new evidence distinguishes the current failure."
---

## 触发条件

- Module: `sd_controller_wb`
- Signal: `int_busy`
- Effect: `regressed`
- First divergence: `{"signal": "int_busy", "time": 1015, "ref": "0", "dut": "1", "classification": "dut_late", "ref_path": "tb.int_busy_ref", "dut_path": "tb.int_busy_dut", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "nonblocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`

## 不适用条件

- Do not reuse if affected signals, timing alignment, or spec intent differ.
- Do not reuse without reading current RTL/spec evidence.

## 补丁模式

int_busy_next                     = write_req_s;

## 验证特征

- Before mismatch count: `29182`
- After mismatch count: `33116`
- Metric delta: `{"total_samples_mismatch": "9228 -> 9214", "per_signal": {"Bd_isr_enable_reg": {"before": 354, "after": 354, "first_time_before": 4420, "first_time_after": 4420, "direction": "unchanged"}, "Bd_isr_reset": {"before": 154, "after": 154, "first_time_before": 5450, "first_time_after": 5450, "direction": "unchanged"}, "argument_reg": {"before": 8194, "after": 8194, "first_time_before": 2860, "first_time_after": 2860, "direction": "unchanged"}, "clock_divider": {"before": 422, "after": 422, "first_time_before": 3180, "first_time_after": 3180, "direction": "unchanged"}, "cmd_int_busy": {"before": 1880, "after": 1880, "first_time_before": 2880, "first_time_after": 2880, "direction": "unchanged"}, "cmd_setting_reg": {"before": 8178, "after": 8178, "first_time_before": 2860, "first_time_after": 2860, "direction": "unchanged"}, "dat_in_m_rx_bd": {"before": 502, "after": 502, "first_time_before": 3000, "first_time_after": 3000, "direction": "unchanged"}, "dat_in_m_tx_bd": {"before": 888, "after": 888, "first_time_before": 4600, "first_time_after": 4600, "direction": "unchanged"}, "error_int_signal_enable_reg": {"before": 526, "after": 526, "first_time_before": 3620, "first_time_after": 3620, "direction": "unchanged"}, "error_isr_reset": {"before": 142, "after": 142, "first_time_before": 12520, "first_time_after": 12520, "direction": "unchanged"}, "int_ack": {"before": 194, "after": 194, "first_time_before": 3010, "first_time_after": 3010, "direction": "unchanged"}, "int_busy": {"before": 1088, "after": 5022, "first_time_before": 1020, "first_time_after": 90, "direction": "regressed"}, "new_cmd": {"before": 1846, "after": 1846, "first_time_before": 2610, "first_time_after": 2610, "direction": "unchanged"}, "normal_int_signal_enable_reg": {"before": 462, "after": 462, "first_time_before": 7310, "first_time_after": 7310, "direction": "unchanged"}, "normal_isr_reset": {"before": 124, "after": 124, "first_time_before": 3790, "first_time_after": 3790, "direction": "unchanged"}, "software_reset_reg": {"before": 242, "after": 242, "first_time_before": 4280, "first_time_after": 4280, "direction": "unchanged"}, "time_out_reg": {"before": 554, "after": 554, "first_time_before": 8580, "first_time_after": 8580, "direction": "unchanged"}, "wb_ack_o": {"before": 34, "after": 34, "first_time_before": 12670, "first_time_after": 12670, "direction": "unchanged"}, "wb_dat_o": {"before": 1414, "after": 1414, "first_time_before": 3300, "first_time_after": 3300, "direction": "unchanged"}, "we_ack": {"before": 1880, "after": 1880, "first_time_before": 2880, "first_time_after": 2880, "direction": "unchanged"}, "we_m_rx_bd": {"before": 32, "after": 32, "first_time_before": 3000, "first_time_after": 3000, "direction": "unchanged"}, "we_m_tx_bd": {"before": 72, "after": 72, "first_time_before": 4600, "first_time_after": 4600, "direction": "unchanged"}}}`

## 复用约束

Patch worsened mismatch count or first fail time and was rolled back.

## Problem

`sd_controller_wb` showed a debug failure around `int_busy`.

## Evidence

- Effect: `regressed`
- Before mismatch count: `29182`
- After mismatch count: `33116`
- First divergence: `{"signal": "int_busy", "time": 1015, "ref": "0", "dut": "1", "classification": "dut_late", "ref_path": "tb.int_busy_ref", "dut_path": "tb.int_busy_dut", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "nonblocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`
- Trace root failure: `{"signal": "int_busy", "time": 1015, "ref": "0", "dut": "1", "classification": "dut_late", "ref_path": "tb.int_busy_ref", "dut_path": "tb.int_busy_dut", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "nonblocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`
- Metric delta: `{"total_samples_mismatch": "9228 -> 9214", "per_signal": {"Bd_isr_enable_reg": {"before": 354, "after": 354, "first_time_before": 4420, "first_time_after": 4420, "direction": "unchanged"}, "Bd_isr_reset": {"before": 154, "after": 154, "first_time_before": 5450, "first_time_after": 5450, "direction": "unchanged"}, "argument_reg": {"before": 8194, "after": 8194, "first_time_before": 2860, "first_time_after": 2860, "direction": "unchanged"}, "clock_divider": {"before": 422, "after": 422, "first_time_before": 3180, "first_time_after": 3180, "direction": "unchanged"}, "cmd_int_busy": {"before": 1880, "after": 1880, "first_time_before": 2880, "first_time_after": 2880, "direction": "unchanged"}, "cmd_setting_reg": {"before": 8178, "after": 8178, "first_time_before": 2860, "first_time_after": 2860, "direction": "unchanged"}, "dat_in_m_rx_bd": {"before": 502, "after": 502, "first_time_before": 3000, "first_time_after": 3000, "direction": "unchanged"}, "dat_in_m_tx_bd": {"before": 888, "after": 888, "first_time_before": 4600, "first_time_after": 4600, "direction": "unchanged"}, "error_int_signal_enable_reg": {"before": 526, "after": 526, "first_time_before": 3620, "first_time_after": 3620, "direction": "unchanged"}, "error_isr_reset": {"before": 142, "after": 142, "first_time_before": 12520, "first_time_after": 12520, "direction": "unchanged"}, "int_ack": {"before": 194, "after": 194, "first_time_before": 3010, "first_time_after": 3010, "direction": "unchanged"}, "int_busy": {"before": 1088, "after": 5022, "first_time_before": 1020, "first_time_after": 90, "direction": "regressed"}, "new_cmd": {"before": 1846, "after": 1846, "first_time_before": 2610, "first_time_after": 2610, "direction": "unchanged"}, "normal_int_signal_enable_reg": {"before": 462, "after": 462, "first_time_before": 7310, "first_time_after": 7310, "direction": "unchanged"}, "normal_isr_reset": {"before": 124, "after": 124, "first_time_before": 3790, "first_time_after": 3790, "direction": "unchanged"}, "software_reset_reg": {"before": 242, "after": 242, "first_time_before": 4280, "first_time_after": 4280, "direction": "unchanged"}, "time_out_reg": {"before": 554, "after": 554, "first_time_before": 8580, "first_time_after": 8580, "direction": "unchanged"}, "wb_ack_o": {"before": 34, "after": 34, "first_time_before": 12670, "first_time_after": 12670, "direction": "unchanged"}, "wb_dat_o": {"before": 1414, "after": 1414, "first_time_before": 3300, "first_time_after": 3300, "direction": "unchanged"}, "we_ack": {"before": 1880, "after": 1880, "first_time_before": 2880, "first_time_after": 2880, "direction": "unchanged"}, "we_m_rx_bd": {"before": 32, "after": 32, "first_time_before": 3000, "first_time_after": 3000, "direction": "unchanged"}, "we_m_tx_bd": {"before": 72, "after": 72, "first_time_before": 4600, "first_time_after": 4600, "direction": "unchanged"}}}`

## Patch Summary

int_busy_next                     = write_req_s;

## Lesson

Patch worsened mismatch count or first fail time and was rolled back.

## Reuse Constraints

- Read current RTL/spec evidence before applying a similar patch.
- Do not reuse if affected signals or timing alignment differ.
