---
memory_id: debug_sd_controller_wb_argument_reg_improved_1
type: repair_outcome
stage: debug
description: "sd_controller_wb: argument_reg improved; Patch improved mismatch count or first fail time; continue from this direction."
module: sd_controller_wb
module_family: sdc
signals:
  - argument_reg
  - wb_dat_o
failure_type: local_logic_bug
alignment: wrong_value
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
  - argument_reg
  - wb_dat_o
trigger_failure_type: local_logic_bug
trigger_alignment: wrong_value
risk_signals:
  - wb_dat_o
patch_pattern: "wb_dat_o                     <= wb_dat_o_next;"
anti_trigger: "Do not reuse when current first divergence, affected signals, or timing alignment differ."
---

## 触发条件

- Module: `sd_controller_wb`
- Signal: `argument_reg`
- Effect: `improved`
- First divergence: `{"signal": "argument_reg", "time": 285, "ref": "10011110111111011101010100000010", "dut": "10011110111111010000000000000000", "classification": "wrong_value", "ref_path": "tb.argument_reg_ref[31:0]", "dut_path": "tb.argument_reg_dut[31:0]", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "nonblocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`

## 不适用条件

- Do not reuse if affected signals, timing alignment, or spec intent differ.
- Do not reuse without reading current RTL/spec evidence.

## 补丁模式

wb_dat_o                     <= wb_dat_o_next;

## 验证特征

- Before mismatch count: `38730`
- After mismatch count: `38148`
- Metric delta: `{"total_samples_mismatch": "9928 -> 9676", "per_signal": {"Bd_isr_enable_reg": {"before": 830, "after": 830, "first_time_before": 4420, "first_time_after": 4420, "direction": "unchanged"}, "Bd_isr_reset": {"before": 154, "after": 154, "first_time_before": 5450, "first_time_after": 5450, "direction": "unchanged"}, "argument_reg": {"before": 8540, "after": 8540, "first_time_before": 290, "first_time_after": 290, "direction": "unchanged"}, "clock_divider": {"before": 1290, "after": 1290, "first_time_before": 430, "first_time_after": 430, "direction": "unchanged"}, "cmd_int_busy": {"before": 1880, "after": 1880, "first_time_before": 2880, "first_time_after": 2880, "direction": "unchanged"}, "cmd_setting_reg": {"before": 8472, "after": 8472, "first_time_before": 300, "first_time_after": 300, "direction": "unchanged"}, "dat_in_m_rx_bd": {"before": 572, "after": 572, "first_time_before": 470, "first_time_after": 470, "direction": "unchanged"}, "dat_in_m_tx_bd": {"before": 940, "after": 940, "first_time_before": 480, "first_time_after": 480, "direction": "unchanged"}, "error_int_signal_enable_reg": {"before": 1872, "after": 1872, "first_time_before": 410, "first_time_after": 410, "direction": "unchanged"}, "error_isr_reset": {"before": 142, "after": 142, "first_time_before": 12520, "first_time_after": 12520, "direction": "unchanged"}, "int_ack": {"before": 72, "after": 72, "first_time_before": 480, "first_time_after": 480, "direction": "unchanged"}, "int_busy": {"before": 1088, "after": 1088, "first_time_before": 1020, "first_time_after": 1020, "direction": "unchanged"}, "new_cmd": {"before": 2962, "after": 2962, "first_time_before": 820, "first_time_after": 820, "direction": "unchanged"}, "normal_int_signal_enable_reg": {"before": 1824, "after": 1824, "first_time_before": 400, "first_time_after": 400, "direction": "unchanged"}, "normal_isr_reset": {"before": 124, "after": 124, "first_time_before": 3790, "first_time_after": 3790, "direction": "unchanged"}, "software_reset_reg": {"before": 670, "after": 670, "first_time_before": 4280, "first_time_after": 4280, "direction": "unchanged"}, "time_out_reg": {"before": 1860, "after": 1860, "first_time_before": 370, "first_time_after": 370, "direction": "unchanged"}, "wb_ack_o": {"before": 44, "after": 44, "first_time_before": 480, "first_time_after": 480, "direction": "unchanged"}, "wb_dat_o": {"before": 3258, "after": 2676, "first_time_before": 150, "first_time_after": 330, "direction": "improved"}, "we_ack": {"before": 1880, "after": 1880, "first_time_before": 2880, "first_time_after": 2880, "direction": "unchanged"}, "we_m_rx_bd": {"before": 114, "after": 114, "first_time_before": 470, "first_time_after": 470, "direction": "unchanged"}, "we_m_tx_bd": {"before": 142, "after": 142, "first_time_before": 480, "first_time_after": 480, "direction": "unchanged"}}}`

## 复用约束

Patch improved mismatch count or first fail time; continue from this direction.

## Problem

`sd_controller_wb` showed a debug failure around `argument_reg`.

## Evidence

- Effect: `improved`
- Before mismatch count: `38730`
- After mismatch count: `38148`
- First divergence: `{"signal": "argument_reg", "time": 285, "ref": "10011110111111011101010100000010", "dut": "10011110111111010000000000000000", "classification": "wrong_value", "ref_path": "tb.argument_reg_ref[31:0]", "dut_path": "tb.argument_reg_dut[31:0]", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "nonblocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`
- Trace root failure: `{"signal": "argument_reg", "time": 285, "ref": "10011110111111011101010100000010", "dut": "10011110111111010000000000000000", "classification": "wrong_value", "ref_path": "tb.argument_reg_ref[31:0]", "dut_path": "tb.argument_reg_dut[31:0]", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "nonblocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`
- Metric delta: `{"total_samples_mismatch": "9928 -> 9676", "per_signal": {"Bd_isr_enable_reg": {"before": 830, "after": 830, "first_time_before": 4420, "first_time_after": 4420, "direction": "unchanged"}, "Bd_isr_reset": {"before": 154, "after": 154, "first_time_before": 5450, "first_time_after": 5450, "direction": "unchanged"}, "argument_reg": {"before": 8540, "after": 8540, "first_time_before": 290, "first_time_after": 290, "direction": "unchanged"}, "clock_divider": {"before": 1290, "after": 1290, "first_time_before": 430, "first_time_after": 430, "direction": "unchanged"}, "cmd_int_busy": {"before": 1880, "after": 1880, "first_time_before": 2880, "first_time_after": 2880, "direction": "unchanged"}, "cmd_setting_reg": {"before": 8472, "after": 8472, "first_time_before": 300, "first_time_after": 300, "direction": "unchanged"}, "dat_in_m_rx_bd": {"before": 572, "after": 572, "first_time_before": 470, "first_time_after": 470, "direction": "unchanged"}, "dat_in_m_tx_bd": {"before": 940, "after": 940, "first_time_before": 480, "first_time_after": 480, "direction": "unchanged"}, "error_int_signal_enable_reg": {"before": 1872, "after": 1872, "first_time_before": 410, "first_time_after": 410, "direction": "unchanged"}, "error_isr_reset": {"before": 142, "after": 142, "first_time_before": 12520, "first_time_after": 12520, "direction": "unchanged"}, "int_ack": {"before": 72, "after": 72, "first_time_before": 480, "first_time_after": 480, "direction": "unchanged"}, "int_busy": {"before": 1088, "after": 1088, "first_time_before": 1020, "first_time_after": 1020, "direction": "unchanged"}, "new_cmd": {"before": 2962, "after": 2962, "first_time_before": 820, "first_time_after": 820, "direction": "unchanged"}, "normal_int_signal_enable_reg": {"before": 1824, "after": 1824, "first_time_before": 400, "first_time_after": 400, "direction": "unchanged"}, "normal_isr_reset": {"before": 124, "after": 124, "first_time_before": 3790, "first_time_after": 3790, "direction": "unchanged"}, "software_reset_reg": {"before": 670, "after": 670, "first_time_before": 4280, "first_time_after": 4280, "direction": "unchanged"}, "time_out_reg": {"before": 1860, "after": 1860, "first_time_before": 370, "first_time_after": 370, "direction": "unchanged"}, "wb_ack_o": {"before": 44, "after": 44, "first_time_before": 480, "first_time_after": 480, "direction": "unchanged"}, "wb_dat_o": {"before": 3258, "after": 2676, "first_time_before": 150, "first_time_after": 330, "direction": "improved"}, "we_ack": {"before": 1880, "after": 1880, "first_time_before": 2880, "first_time_after": 2880, "direction": "unchanged"}, "we_m_rx_bd": {"before": 114, "after": 114, "first_time_before": 470, "first_time_after": 470, "direction": "unchanged"}, "we_m_tx_bd": {"before": 142, "after": 142, "first_time_before": 480, "first_time_after": 480, "direction": "unchanged"}}}`

## Patch Summary

wb_dat_o                     <= wb_dat_o_next;

## Lesson

Patch improved mismatch count or first fail time; continue from this direction.

## Reuse Constraints

- Read current RTL/spec evidence before applying a similar patch.
- Do not reuse if affected signals or timing alignment differ.
