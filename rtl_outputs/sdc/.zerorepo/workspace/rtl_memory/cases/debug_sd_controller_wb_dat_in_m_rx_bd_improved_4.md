---
memory_id: debug_sd_controller_wb_dat_in_m_rx_bd_improved_4
type: repair_outcome
stage: debug
description: "sd_controller_wb: dat_in_m_rx_bd improved; Patch improved mismatch count or first fail time; continue from this direction."
module: sd_controller_wb
module_family: sdc
signals:
  - controller_setting_value
  - dat_in_m_rx_bd
failure_type: plan_bug
alignment: dut_early
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
  - controller_setting_value
  - dat_in_m_rx_bd
trigger_failure_type: plan_bug
trigger_alignment: dut_early
risk_signals:
  - controller_setting_value
patch_pattern: "assign controller_setting_value = 16'h0002;"
anti_trigger: "Do not reuse when current first divergence, affected signals, or timing alignment differ."
---

## 触发条件

- Module: `sd_controller_wb`
- Signal: `dat_in_m_rx_bd`
- Effect: `improved`
- First divergence: `{"signal": "dat_in_m_rx_bd", "time": 465, "ref": "0000000000000000", "dut": "1011111001101111", "classification": "dut_early", "ref_path": "tb.dat_in_m_rx_bd_ref[15:0]", "dut_path": "tb.dat_in_m_rx_bd_dut[15:0]", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "nonblocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`

## 不适用条件

- Do not reuse if affected signals, timing alignment, or spec intent differ.
- Do not reuse without reading current RTL/spec evidence.

## 补丁模式

assign controller_setting_value = 16'h0002;

## 验证特征

- Before mismatch count: `31462`
- After mismatch count: `30994`
- Metric delta: `{"total_samples_mismatch": "9552 -> 9492", "per_signal": {"Bd_isr_enable_reg": {"before": 354, "after": 354, "first_time_before": 4420, "first_time_after": 4420, "direction": "unchanged"}, "Bd_isr_reset": {"before": 154, "after": 154, "first_time_before": 5450, "first_time_after": 5450, "direction": "unchanged"}, "argument_reg": {"before": 8194, "after": 8194, "first_time_before": 2860, "first_time_after": 2860, "direction": "unchanged"}, "clock_divider": {"before": 422, "after": 422, "first_time_before": 3180, "first_time_after": 3180, "direction": "unchanged"}, "cmd_int_busy": {"before": 1880, "after": 1880, "first_time_before": 2880, "first_time_after": 2880, "direction": "unchanged"}, "cmd_setting_reg": {"before": 8178, "after": 8178, "first_time_before": 2860, "first_time_after": 2860, "direction": "unchanged"}, "dat_in_m_rx_bd": {"before": 572, "after": 572, "first_time_before": 470, "first_time_after": 470, "direction": "unchanged"}, "dat_in_m_tx_bd": {"before": 940, "after": 940, "first_time_before": 480, "first_time_after": 480, "direction": "unchanged"}, "error_int_signal_enable_reg": {"before": 526, "after": 526, "first_time_before": 3620, "first_time_after": 3620, "direction": "unchanged"}, "error_isr_reset": {"before": 142, "after": 142, "first_time_before": 12520, "first_time_after": 12520, "direction": "unchanged"}, "int_ack": {"before": 72, "after": 72, "first_time_before": 480, "first_time_after": 480, "direction": "unchanged"}, "int_busy": {"before": 1088, "after": 1088, "first_time_before": 1020, "first_time_after": 1020, "direction": "unchanged"}, "new_cmd": {"before": 2962, "after": 2962, "first_time_before": 820, "first_time_after": 820, "direction": "unchanged"}, "normal_int_signal_enable_reg": {"before": 462, "after": 462, "first_time_before": 7310, "first_time_after": 7310, "direction": "unchanged"}, "normal_isr_reset": {"before": 124, "after": 124, "first_time_before": 3790, "first_time_after": 3790, "direction": "unchanged"}, "software_reset_reg": {"before": 242, "after": 242, "first_time_before": 4280, "first_time_after": 4280, "direction": "unchanged"}, "time_out_reg": {"before": 554, "after": 554, "first_time_before": 8580, "first_time_after": 8580, "direction": "unchanged"}, "wb_ack_o": {"before": 44, "after": 44, "first_time_before": 480, "first_time_after": 480, "direction": "unchanged"}, "wb_dat_o": {"before": 2416, "after": 1948, "first_time_before": 330, "first_time_after": 670, "direction": "improved"}, "we_ack": {"before": 1880, "after": 1880, "first_time_before": 2880, "first_time_after": 2880, "direction": "unchanged"}, "we_m_rx_bd": {"before": 114, "after": 114, "first_time_before": 470, "first_time_after": 470, "direction": "unchanged"}, "we_m_tx_bd": {"before": 142, "after": 142, "first_time_before": 480, "first_time_after": 480, "direction": "unchanged"}}}`

## 复用约束

Patch improved mismatch count or first fail time; continue from this direction.

## Problem

`sd_controller_wb` showed a debug failure around `dat_in_m_rx_bd`.

## Evidence

- Effect: `improved`
- Before mismatch count: `31462`
- After mismatch count: `30994`
- First divergence: `{"signal": "dat_in_m_rx_bd", "time": 465, "ref": "0000000000000000", "dut": "1011111001101111", "classification": "dut_early", "ref_path": "tb.dat_in_m_rx_bd_ref[15:0]", "dut_path": "tb.dat_in_m_rx_bd_dut[15:0]", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "nonblocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`
- Trace root failure: `{"signal": "dat_in_m_rx_bd", "time": 465, "ref": "0000000000000000", "dut": "1011111001101111", "classification": "dut_early", "ref_path": "tb.dat_in_m_rx_bd_ref[15:0]", "dut_path": "tb.dat_in_m_rx_bd_dut[15:0]", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "nonblocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`
- Metric delta: `{"total_samples_mismatch": "9552 -> 9492", "per_signal": {"Bd_isr_enable_reg": {"before": 354, "after": 354, "first_time_before": 4420, "first_time_after": 4420, "direction": "unchanged"}, "Bd_isr_reset": {"before": 154, "after": 154, "first_time_before": 5450, "first_time_after": 5450, "direction": "unchanged"}, "argument_reg": {"before": 8194, "after": 8194, "first_time_before": 2860, "first_time_after": 2860, "direction": "unchanged"}, "clock_divider": {"before": 422, "after": 422, "first_time_before": 3180, "first_time_after": 3180, "direction": "unchanged"}, "cmd_int_busy": {"before": 1880, "after": 1880, "first_time_before": 2880, "first_time_after": 2880, "direction": "unchanged"}, "cmd_setting_reg": {"before": 8178, "after": 8178, "first_time_before": 2860, "first_time_after": 2860, "direction": "unchanged"}, "dat_in_m_rx_bd": {"before": 572, "after": 572, "first_time_before": 470, "first_time_after": 470, "direction": "unchanged"}, "dat_in_m_tx_bd": {"before": 940, "after": 940, "first_time_before": 480, "first_time_after": 480, "direction": "unchanged"}, "error_int_signal_enable_reg": {"before": 526, "after": 526, "first_time_before": 3620, "first_time_after": 3620, "direction": "unchanged"}, "error_isr_reset": {"before": 142, "after": 142, "first_time_before": 12520, "first_time_after": 12520, "direction": "unchanged"}, "int_ack": {"before": 72, "after": 72, "first_time_before": 480, "first_time_after": 480, "direction": "unchanged"}, "int_busy": {"before": 1088, "after": 1088, "first_time_before": 1020, "first_time_after": 1020, "direction": "unchanged"}, "new_cmd": {"before": 2962, "after": 2962, "first_time_before": 820, "first_time_after": 820, "direction": "unchanged"}, "normal_int_signal_enable_reg": {"before": 462, "after": 462, "first_time_before": 7310, "first_time_after": 7310, "direction": "unchanged"}, "normal_isr_reset": {"before": 124, "after": 124, "first_time_before": 3790, "first_time_after": 3790, "direction": "unchanged"}, "software_reset_reg": {"before": 242, "after": 242, "first_time_before": 4280, "first_time_after": 4280, "direction": "unchanged"}, "time_out_reg": {"before": 554, "after": 554, "first_time_before": 8580, "first_time_after": 8580, "direction": "unchanged"}, "wb_ack_o": {"before": 44, "after": 44, "first_time_before": 480, "first_time_after": 480, "direction": "unchanged"}, "wb_dat_o": {"before": 2416, "after": 1948, "first_time_before": 330, "first_time_after": 670, "direction": "improved"}, "we_ack": {"before": 1880, "after": 1880, "first_time_before": 2880, "first_time_after": 2880, "direction": "unchanged"}, "we_m_rx_bd": {"before": 114, "after": 114, "first_time_before": 470, "first_time_after": 470, "direction": "unchanged"}, "we_m_tx_bd": {"before": 142, "after": 142, "first_time_before": 480, "first_time_after": 480, "direction": "unchanged"}}}`

## Patch Summary

assign controller_setting_value = 16'h0002;

## Lesson

Patch improved mismatch count or first fail time; continue from this direction.

## Reuse Constraints

- Read current RTL/spec evidence before applying a similar patch.
- Do not reuse if affected signals or timing alignment differ.
