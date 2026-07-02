---
memory_id: debug_sd_controller_wb_int_busy_improved_14
type: repair_outcome
stage: debug
description: "sd_controller_wb: int_busy improved; Patch improved mismatch count or first fail time; continue from this direction."
module: sd_controller_wb
module_family: sdc
signals:
  - int_busy
  - new_cmd_next
failure_type: interface_bug
alignment: dut_late
outcome: improved
confidence: 0.72
verified_by:
  - lint
  - module_sim
  - trace
source_artifacts:
  - debug/sd_controller_wb/trace_report.json
  - repo_react/sd_controller_wb/patch_journal.jsonl
trigger_signals:
  - int_busy
  - new_cmd_next
trigger_failure_type: interface_bug
trigger_alignment: dut_late
risk_signals:
  - new_cmd_next
patch_pattern: "new_cmd_next                      = write_req_s;"
anti_trigger: "Do not reuse when current first divergence, affected signals, or timing alignment differ."
---

## 触发条件

- Module: `sd_controller_wb`
- Signal: `int_busy`
- Effect: `improved`
- First divergence: `{"signal": "int_busy", "time": 1015, "ref": "0", "dut": "1", "classification": "dut_late", "ref_path": "tb.int_busy_ref", "dut_path": "tb.int_busy_dut", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "nonblocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`

## 不适用条件

- Do not reuse if affected signals, timing alignment, or spec intent differ.
- Do not reuse without reading current RTL/spec evidence.

## 补丁模式

new_cmd_next                      = write_req_s;

## 验证特征

- Before mismatch count: `30298`
- After mismatch count: `29182`
- Metric delta: `{"total_samples_mismatch": "9252 -> 9228", "per_signal": {"Bd_isr_enable_reg": {"before": 354, "after": 354, "first_time_before": 4420, "first_time_after": 4420, "direction": "unchanged"}, "Bd_isr_reset": {"before": 154, "after": 154, "first_time_before": 5450, "first_time_after": 5450, "direction": "unchanged"}, "argument_reg": {"before": 8194, "after": 8194, "first_time_before": 2860, "first_time_after": 2860, "direction": "unchanged"}, "clock_divider": {"before": 422, "after": 422, "first_time_before": 3180, "first_time_after": 3180, "direction": "unchanged"}, "cmd_int_busy": {"before": 1880, "after": 1880, "first_time_before": 2880, "first_time_after": 2880, "direction": "unchanged"}, "cmd_setting_reg": {"before": 8178, "after": 8178, "first_time_before": 2860, "first_time_after": 2860, "direction": "unchanged"}, "dat_in_m_rx_bd": {"before": 502, "after": 502, "first_time_before": 3000, "first_time_after": 3000, "direction": "unchanged"}, "dat_in_m_tx_bd": {"before": 888, "after": 888, "first_time_before": 4600, "first_time_after": 4600, "direction": "unchanged"}, "error_int_signal_enable_reg": {"before": 526, "after": 526, "first_time_before": 3620, "first_time_after": 3620, "direction": "unchanged"}, "error_isr_reset": {"before": 142, "after": 142, "first_time_before": 12520, "first_time_after": 12520, "direction": "unchanged"}, "int_ack": {"before": 194, "after": 194, "first_time_before": 3010, "first_time_after": 3010, "direction": "unchanged"}, "int_busy": {"before": 1088, "after": 1088, "first_time_before": 1020, "first_time_after": 1020, "direction": "unchanged"}, "new_cmd": {"before": 2962, "after": 1846, "first_time_before": 820, "first_time_after": 2610, "direction": "improved"}, "normal_int_signal_enable_reg": {"before": 462, "after": 462, "first_time_before": 7310, "first_time_after": 7310, "direction": "unchanged"}, "normal_isr_reset": {"before": 124, "after": 124, "first_time_before": 3790, "first_time_after": 3790, "direction": "unchanged"}, "software_reset_reg": {"before": 242, "after": 242, "first_time_before": 4280, "first_time_after": 4280, "direction": "unchanged"}, "time_out_reg": {"before": 554, "after": 554, "first_time_before": 8580, "first_time_after": 8580, "direction": "unchanged"}, "wb_ack_o": {"before": 34, "after": 34, "first_time_before": 12670, "first_time_after": 12670, "direction": "unchanged"}, "wb_dat_o": {"before": 1414, "after": 1414, "first_time_before": 3300, "first_time_after": 3300, "direction": "unchanged"}, "we_ack": {"before": 1880, "after": 1880, "first_time_before": 2880, "first_time_after": 2880, "direction": "unchanged"}, "we_m_rx_bd": {"before": 32, "after": 32, "first_time_before": 3000, "first_time_after": 3000, "direction": "unchanged"}, "we_m_tx_bd": {"before": 72, "after": 72, "first_time_before": 4600, "first_time_after": 4600, "direction": "unchanged"}}}`

## 复用约束

Patch improved mismatch count or first fail time; continue from this direction.

## Problem

`sd_controller_wb` showed a debug failure around `int_busy`.

## Evidence

- Effect: `improved`
- Before mismatch count: `30298`
- After mismatch count: `29182`
- First divergence: `{"signal": "int_busy", "time": 1015, "ref": "0", "dut": "1", "classification": "dut_late", "ref_path": "tb.int_busy_ref", "dut_path": "tb.int_busy_dut", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "nonblocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`
- Trace root failure: `{"signal": "int_busy", "time": 1015, "ref": "0", "dut": "1", "classification": "dut_late", "ref_path": "tb.int_busy_ref", "dut_path": "tb.int_busy_dut", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "nonblocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`
- Metric delta: `{"total_samples_mismatch": "9252 -> 9228", "per_signal": {"Bd_isr_enable_reg": {"before": 354, "after": 354, "first_time_before": 4420, "first_time_after": 4420, "direction": "unchanged"}, "Bd_isr_reset": {"before": 154, "after": 154, "first_time_before": 5450, "first_time_after": 5450, "direction": "unchanged"}, "argument_reg": {"before": 8194, "after": 8194, "first_time_before": 2860, "first_time_after": 2860, "direction": "unchanged"}, "clock_divider": {"before": 422, "after": 422, "first_time_before": 3180, "first_time_after": 3180, "direction": "unchanged"}, "cmd_int_busy": {"before": 1880, "after": 1880, "first_time_before": 2880, "first_time_after": 2880, "direction": "unchanged"}, "cmd_setting_reg": {"before": 8178, "after": 8178, "first_time_before": 2860, "first_time_after": 2860, "direction": "unchanged"}, "dat_in_m_rx_bd": {"before": 502, "after": 502, "first_time_before": 3000, "first_time_after": 3000, "direction": "unchanged"}, "dat_in_m_tx_bd": {"before": 888, "after": 888, "first_time_before": 4600, "first_time_after": 4600, "direction": "unchanged"}, "error_int_signal_enable_reg": {"before": 526, "after": 526, "first_time_before": 3620, "first_time_after": 3620, "direction": "unchanged"}, "error_isr_reset": {"before": 142, "after": 142, "first_time_before": 12520, "first_time_after": 12520, "direction": "unchanged"}, "int_ack": {"before": 194, "after": 194, "first_time_before": 3010, "first_time_after": 3010, "direction": "unchanged"}, "int_busy": {"before": 1088, "after": 1088, "first_time_before": 1020, "first_time_after": 1020, "direction": "unchanged"}, "new_cmd": {"before": 2962, "after": 1846, "first_time_before": 820, "first_time_after": 2610, "direction": "improved"}, "normal_int_signal_enable_reg": {"before": 462, "after": 462, "first_time_before": 7310, "first_time_after": 7310, "direction": "unchanged"}, "normal_isr_reset": {"before": 124, "after": 124, "first_time_before": 3790, "first_time_after": 3790, "direction": "unchanged"}, "software_reset_reg": {"before": 242, "after": 242, "first_time_before": 4280, "first_time_after": 4280, "direction": "unchanged"}, "time_out_reg": {"before": 554, "after": 554, "first_time_before": 8580, "first_time_after": 8580, "direction": "unchanged"}, "wb_ack_o": {"before": 34, "after": 34, "first_time_before": 12670, "first_time_after": 12670, "direction": "unchanged"}, "wb_dat_o": {"before": 1414, "after": 1414, "first_time_before": 3300, "first_time_after": 3300, "direction": "unchanged"}, "we_ack": {"before": 1880, "after": 1880, "first_time_before": 2880, "first_time_after": 2880, "direction": "unchanged"}, "we_m_rx_bd": {"before": 32, "after": 32, "first_time_before": 3000, "first_time_after": 3000, "direction": "unchanged"}, "we_m_tx_bd": {"before": 72, "after": 72, "first_time_before": 4600, "first_time_after": 4600, "direction": "unchanged"}}}`

## Patch Summary

new_cmd_next                      = write_req_s;

## Lesson

Patch improved mismatch count or first fail time; continue from this direction.

## Reuse Constraints

- Read current RTL/spec evidence before applying a similar patch.
- Do not reuse if affected signals or timing alignment differ.
