---
memory_id: debug_sd_controller_wb_new_cmd_improved_13
type: repair_outcome
stage: debug
description: "sd_controller_wb: new_cmd improved; Patch improved mismatch count or first fail time; continue from this direction."
module: sd_controller_wb
module_family: sdc
signals:
  - new_cmd
  - wb_dat_o_next
failure_type: local_logic_bug
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
  - new_cmd
  - wb_dat_o_next
trigger_failure_type: local_logic_bug
trigger_alignment: dut_late
risk_signals:
  - wb_dat_o_next
patch_pattern: "default: ;"
anti_trigger: "Do not reuse when current first divergence, affected signals, or timing alignment differ."
---

## 触发条件

- Module: `sd_controller_wb`
- Signal: `new_cmd`
- Effect: `improved`
- First divergence: `{"signal": "new_cmd", "time": 815, "ref": "1", "dut": "0", "classification": "dut_late", "ref_path": "tb.new_cmd_ref", "dut_path": "tb.new_cmd_dut", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "nonblocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`

## 不适用条件

- Do not reuse if affected signals, timing alignment, or spec intent differ.
- Do not reuse without reading current RTL/spec evidence.

## 补丁模式

default: ;

## 验证特征

- Before mismatch count: `30832`
- After mismatch count: `30298`
- Metric delta: `{"total_samples_mismatch": "9320 -> 9252", "per_signal": {"Bd_isr_enable_reg": {"before": 354, "after": 354, "first_time_before": 4420, "first_time_after": 4420, "direction": "unchanged"}, "Bd_isr_reset": {"before": 154, "after": 154, "first_time_before": 5450, "first_time_after": 5450, "direction": "unchanged"}, "argument_reg": {"before": 8194, "after": 8194, "first_time_before": 2860, "first_time_after": 2860, "direction": "unchanged"}, "clock_divider": {"before": 422, "after": 422, "first_time_before": 3180, "first_time_after": 3180, "direction": "unchanged"}, "cmd_int_busy": {"before": 1880, "after": 1880, "first_time_before": 2880, "first_time_after": 2880, "direction": "unchanged"}, "cmd_setting_reg": {"before": 8178, "after": 8178, "first_time_before": 2860, "first_time_after": 2860, "direction": "unchanged"}, "dat_in_m_rx_bd": {"before": 502, "after": 502, "first_time_before": 3000, "first_time_after": 3000, "direction": "unchanged"}, "dat_in_m_tx_bd": {"before": 888, "after": 888, "first_time_before": 4600, "first_time_after": 4600, "direction": "unchanged"}, "error_int_signal_enable_reg": {"before": 526, "after": 526, "first_time_before": 3620, "first_time_after": 3620, "direction": "unchanged"}, "error_isr_reset": {"before": 142, "after": 142, "first_time_before": 12520, "first_time_after": 12520, "direction": "unchanged"}, "int_ack": {"before": 194, "after": 194, "first_time_before": 3010, "first_time_after": 3010, "direction": "unchanged"}, "int_busy": {"before": 1088, "after": 1088, "first_time_before": 1020, "first_time_after": 1020, "direction": "unchanged"}, "new_cmd": {"before": 2962, "after": 2962, "first_time_before": 820, "first_time_after": 820, "direction": "unchanged"}, "normal_int_signal_enable_reg": {"before": 462, "after": 462, "first_time_before": 7310, "first_time_after": 7310, "direction": "unchanged"}, "normal_isr_reset": {"before": 124, "after": 124, "first_time_before": 3790, "first_time_after": 3790, "direction": "unchanged"}, "software_reset_reg": {"before": 242, "after": 242, "first_time_before": 4280, "first_time_after": 4280, "direction": "unchanged"}, "time_out_reg": {"before": 554, "after": 554, "first_time_before": 8580, "first_time_after": 8580, "direction": "unchanged"}, "wb_ack_o": {"before": 34, "after": 34, "first_time_before": 12670, "first_time_after": 12670, "direction": "unchanged"}, "wb_dat_o": {"before": 1948, "after": 1414, "first_time_before": 670, "first_time_after": 3300, "direction": "improved"}, "we_ack": {"before": 1880, "after": 1880, "first_time_before": 2880, "first_time_after": 2880, "direction": "unchanged"}, "we_m_rx_bd": {"before": 32, "after": 32, "first_time_before": 3000, "first_time_after": 3000, "direction": "unchanged"}, "we_m_tx_bd": {"before": 72, "after": 72, "first_time_before": 4600, "first_time_after": 4600, "direction": "unchanged"}}}`

## 复用约束

Patch improved mismatch count or first fail time; continue from this direction.

## Problem

`sd_controller_wb` showed a debug failure around `new_cmd`.

## Evidence

- Effect: `improved`
- Before mismatch count: `30832`
- After mismatch count: `30298`
- First divergence: `{"signal": "new_cmd", "time": 815, "ref": "1", "dut": "0", "classification": "dut_late", "ref_path": "tb.new_cmd_ref", "dut_path": "tb.new_cmd_dut", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "nonblocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`
- Trace root failure: `{"signal": "new_cmd", "time": 815, "ref": "1", "dut": "0", "classification": "dut_late", "ref_path": "tb.new_cmd_ref", "dut_path": "tb.new_cmd_dut", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "nonblocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`
- Metric delta: `{"total_samples_mismatch": "9320 -> 9252", "per_signal": {"Bd_isr_enable_reg": {"before": 354, "after": 354, "first_time_before": 4420, "first_time_after": 4420, "direction": "unchanged"}, "Bd_isr_reset": {"before": 154, "after": 154, "first_time_before": 5450, "first_time_after": 5450, "direction": "unchanged"}, "argument_reg": {"before": 8194, "after": 8194, "first_time_before": 2860, "first_time_after": 2860, "direction": "unchanged"}, "clock_divider": {"before": 422, "after": 422, "first_time_before": 3180, "first_time_after": 3180, "direction": "unchanged"}, "cmd_int_busy": {"before": 1880, "after": 1880, "first_time_before": 2880, "first_time_after": 2880, "direction": "unchanged"}, "cmd_setting_reg": {"before": 8178, "after": 8178, "first_time_before": 2860, "first_time_after": 2860, "direction": "unchanged"}, "dat_in_m_rx_bd": {"before": 502, "after": 502, "first_time_before": 3000, "first_time_after": 3000, "direction": "unchanged"}, "dat_in_m_tx_bd": {"before": 888, "after": 888, "first_time_before": 4600, "first_time_after": 4600, "direction": "unchanged"}, "error_int_signal_enable_reg": {"before": 526, "after": 526, "first_time_before": 3620, "first_time_after": 3620, "direction": "unchanged"}, "error_isr_reset": {"before": 142, "after": 142, "first_time_before": 12520, "first_time_after": 12520, "direction": "unchanged"}, "int_ack": {"before": 194, "after": 194, "first_time_before": 3010, "first_time_after": 3010, "direction": "unchanged"}, "int_busy": {"before": 1088, "after": 1088, "first_time_before": 1020, "first_time_after": 1020, "direction": "unchanged"}, "new_cmd": {"before": 2962, "after": 2962, "first_time_before": 820, "first_time_after": 820, "direction": "unchanged"}, "normal_int_signal_enable_reg": {"before": 462, "after": 462, "first_time_before": 7310, "first_time_after": 7310, "direction": "unchanged"}, "normal_isr_reset": {"before": 124, "after": 124, "first_time_before": 3790, "first_time_after": 3790, "direction": "unchanged"}, "software_reset_reg": {"before": 242, "after": 242, "first_time_before": 4280, "first_time_after": 4280, "direction": "unchanged"}, "time_out_reg": {"before": 554, "after": 554, "first_time_before": 8580, "first_time_after": 8580, "direction": "unchanged"}, "wb_ack_o": {"before": 34, "after": 34, "first_time_before": 12670, "first_time_after": 12670, "direction": "unchanged"}, "wb_dat_o": {"before": 1948, "after": 1414, "first_time_before": 670, "first_time_after": 3300, "direction": "improved"}, "we_ack": {"before": 1880, "after": 1880, "first_time_before": 2880, "first_time_after": 2880, "direction": "unchanged"}, "we_m_rx_bd": {"before": 32, "after": 32, "first_time_before": 3000, "first_time_after": 3000, "direction": "unchanged"}, "we_m_tx_bd": {"before": 72, "after": 72, "first_time_before": 4600, "first_time_after": 4600, "direction": "unchanged"}}}`

## Patch Summary

default: ;

## Lesson

Patch improved mismatch count or first fail time; continue from this direction.

## Reuse Constraints

- Read current RTL/spec evidence before applying a similar patch.
- Do not reuse if affected signals or timing alignment differ.
