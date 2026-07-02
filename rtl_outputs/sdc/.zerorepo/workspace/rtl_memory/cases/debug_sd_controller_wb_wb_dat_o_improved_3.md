---
memory_id: debug_sd_controller_wb_wb_dat_o_improved_3
type: repair_outcome
stage: debug
description: "sd_controller_wb: wb_dat_o improved; Patch improved mismatch count or first fail time; continue from this direction."
module: sd_controller_wb
module_family: sdc
signals:
  - Bd_isr_enable_reg_next
  - Bd_isr_reset_next
  - argument_reg_next
  - clock_divider_next
  - cmd_setting_reg_next
  - error_int_signal_enable_reg_next
  - error_isr_reset_next
  - int_busy_next
  - new_cmd_next
  - normal_int_signal_enable_reg_next
  - normal_isr_reset_next
  - software_reset_reg_next
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
  - Bd_isr_enable_reg_next
  - Bd_isr_reset_next
  - argument_reg_next
  - clock_divider_next
  - cmd_setting_reg_next
  - error_int_signal_enable_reg_next
  - error_isr_reset_next
  - int_busy_next
  - new_cmd_next
  - normal_int_signal_enable_reg_next
  - normal_isr_reset_next
  - software_reset_reg_next
trigger_failure_type: local_logic_bug
trigger_alignment: dut_late
risk_signals:
  - Bd_isr_enable_reg_next
  - Bd_isr_reset_next
  - argument_reg_next
  - clock_divider_next
  - cmd_setting_reg_next
  - error_int_signal_enable_reg_next
  - error_isr_reset_next
  - int_busy_next
  - new_cmd_next
  - normal_int_signal_enable_reg_next
  - normal_isr_reset_next
  - software_reset_reg_next
  - time_out_reg_next
patch_pattern: "if (wb_write_access) begin if (addr_argument) begin argument_reg_next[7:0]   = wb_dat_i[7:\n...<snip>...\nb1; end else if (addr_bd_isr_enable) begin Bd_isr_enable_reg_next = wb_dat_i"
anti_trigger: "Do not reuse when current first divergence, affected signals, or timing alignment differ."
---

## 触发条件

- Module: `sd_controller_wb`
- Signal: `wb_dat_o`
- Effect: `improved`
- First divergence: `{"signal": "wb_dat_o", "time": 325, "ref": "00000000000000000000000000000010", "dut": "00000000000000000000000000000000", "classification": "dut_late", "ref_path": "tb.wb_dat_o_ref[31:0]", "dut_path": "tb.wb_dat_o_dut[31:0]", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "nonblocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`

## 不适用条件

- Do not reuse if affected signals, timing alignment, or spec intent differ.
- Do not reuse without reading current RTL/spec evidence.

## 补丁模式

if (wb_write_access) begin if (addr_argument) begin argument_reg_next[7:0]   = wb_dat_i[7:
...<snip>...
b1; end else if (addr_bd_isr_enable) begin Bd_isr_enable_reg_next = wb_dat_i[7:0]; end end

## 验证特征

- Before mismatch count: `38148`
- After mismatch count: `31462`
- Metric delta: `{"total_samples_mismatch": "9676 -> 9552", "per_signal": {"Bd_isr_enable_reg": {"before": 830, "after": 354, "first_time_before": 4420, "first_time_after": 4420, "direction": "improved"}, "Bd_isr_reset": {"before": 154, "after": 154, "first_time_before": 5450, "first_time_after": 5450, "direction": "unchanged"}, "argument_reg": {"before": 8540, "after": 8194, "first_time_before": 290, "first_time_after": 2860, "direction": "improved"}, "clock_divider": {"before": 1290, "after": 422, "first_time_before": 430, "first_time_after": 3180, "direction": "improved"}, "cmd_int_busy": {"before": 1880, "after": 1880, "first_time_before": 2880, "first_time_after": 2880, "direction": "unchanged"}, "cmd_setting_reg": {"before": 8472, "after": 8178, "first_time_before": 300, "first_time_after": 2860, "direction": "improved"}, "dat_in_m_rx_bd": {"before": 572, "after": 572, "first_time_before": 470, "first_time_after": 470, "direction": "unchanged"}, "dat_in_m_tx_bd": {"before": 940, "after": 940, "first_time_before": 480, "first_time_after": 480, "direction": "unchanged"}, "error_int_signal_enable_reg": {"before": 1872, "after": 526, "first_time_before": 410, "first_time_after": 3620, "direction": "improved"}, "error_isr_reset": {"before": 142, "after": 142, "first_time_before": 12520, "first_time_after": 12520, "direction": "unchanged"}, "int_ack": {"before": 72, "after": 72, "first_time_before": 480, "first_time_after": 480, "direction": "unchanged"}, "int_busy": {"before": 1088, "after": 1088, "first_time_before": 1020, "first_time_after": 1020, "direction": "unchanged"}, "new_cmd": {"before": 2962, "after": 2962, "first_time_before": 820, "first_time_after": 820, "direction": "unchanged"}, "normal_int_signal_enable_reg": {"before": 1824, "after": 462, "first_time_before": 400, "first_time_after": 7310, "direction": "improved"}, "normal_isr_reset": {"before": 124, "after": 124, "first_time_before": 3790, "first_time_after": 3790, "direction": "unchanged"}, "software_reset_reg": {"before": 670, "after": 242, "first_time_before": 4280, "first_time_after": 4280, "direction": "improved"}, "time_out_reg": {"before": 1860, "after": 554, "first_time_before": 370, "first_time_after": 8580, "direction": "improved"}, "wb_ack_o": {"before": 44, "after": 44, "first_time_before": 480, "first_time_after": 480, "direction": "unchanged"}, "wb_dat_o": {"before": 2676, "after": 2416, "first_time_before": 330, "first_time_after": 330, "direction": "improved"}, "we_ack": {"before": 1880, "after": 1880, "first_time_before": 2880, "first_time_after": 2880, "direction": "unchanged"}, "we_m_rx_bd": {"before": 114, "after": 114, "first_time_before": 470, "first_time_after": 470, "direction": "unchanged"}, "we_m_tx_bd": {"before": 142, "after": 142, "first_time_before": 480, "first_time_after": 480, "direction": "unchanged"}}}`

## 复用约束

Patch improved mismatch count or first fail time; continue from this direction.

## Problem

`sd_controller_wb` showed a debug failure around `wb_dat_o`.

## Evidence

- Effect: `improved`
- Before mismatch count: `38148`
- After mismatch count: `31462`
- First divergence: `{"signal": "wb_dat_o", "time": 325, "ref": "00000000000000000000000000000010", "dut": "00000000000000000000000000000000", "classification": "dut_late", "ref_path": "tb.wb_dat_o_ref[31:0]", "dut_path": "tb.wb_dat_o_dut[31:0]", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "nonblocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`
- Trace root failure: `{"signal": "wb_dat_o", "time": 325, "ref": "00000000000000000000000000000010", "dut": "00000000000000000000000000000000", "classification": "dut_late", "ref_path": "tb.wb_dat_o_ref[31:0]", "dut_path": "tb.wb_dat_o_dut[31:0]", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "nonblocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`
- Metric delta: `{"total_samples_mismatch": "9676 -> 9552", "per_signal": {"Bd_isr_enable_reg": {"before": 830, "after": 354, "first_time_before": 4420, "first_time_after": 4420, "direction": "improved"}, "Bd_isr_reset": {"before": 154, "after": 154, "first_time_before": 5450, "first_time_after": 5450, "direction": "unchanged"}, "argument_reg": {"before": 8540, "after": 8194, "first_time_before": 290, "first_time_after": 2860, "direction": "improved"}, "clock_divider": {"before": 1290, "after": 422, "first_time_before": 430, "first_time_after": 3180, "direction": "improved"}, "cmd_int_busy": {"before": 1880, "after": 1880, "first_time_before": 2880, "first_time_after": 2880, "direction": "unchanged"}, "cmd_setting_reg": {"before": 8472, "after": 8178, "first_time_before": 300, "first_time_after": 2860, "direction": "improved"}, "dat_in_m_rx_bd": {"before": 572, "after": 572, "first_time_before": 470, "first_time_after": 470, "direction": "unchanged"}, "dat_in_m_tx_bd": {"before": 940, "after": 940, "first_time_before": 480, "first_time_after": 480, "direction": "unchanged"}, "error_int_signal_enable_reg": {"before": 1872, "after": 526, "first_time_before": 410, "first_time_after": 3620, "direction": "improved"}, "error_isr_reset": {"before": 142, "after": 142, "first_time_before": 12520, "first_time_after": 12520, "direction": "unchanged"}, "int_ack": {"before": 72, "after": 72, "first_time_before": 480, "first_time_after": 480, "direction": "unchanged"}, "int_busy": {"before": 1088, "after": 1088, "first_time_before": 1020, "first_time_after": 1020, "direction": "unchanged"}, "new_cmd": {"before": 2962, "after": 2962, "first_time_before": 820, "first_time_after": 820, "direction": "unchanged"}, "normal_int_signal_enable_reg": {"before": 1824, "after": 462, "first_time_before": 400, "first_time_after": 7310, "direction": "improved"}, "normal_isr_reset": {"before": 124, "after": 124, "first_time_before": 3790, "first_time_after": 3790, "direction": "unchanged"}, "software_reset_reg": {"before": 670, "after": 242, "first_time_before": 4280, "first_time_after": 4280, "direction": "improved"}, "time_out_reg": {"before": 1860, "after": 554, "first_time_before": 370, "first_time_after": 8580, "direction": "improved"}, "wb_ack_o": {"before": 44, "after": 44, "first_time_before": 480, "first_time_after": 480, "direction": "unchanged"}, "wb_dat_o": {"before": 2676, "after": 2416, "first_time_before": 330, "first_time_after": 330, "direction": "improved"}, "we_ack": {"before": 1880, "after": 1880, "first_time_before": 2880, "first_time_after": 2880, "direction": "unchanged"}, "we_m_rx_bd": {"before": 114, "after": 114, "first_time_before": 470, "first_time_after": 470, "direction": "unchanged"}, "we_m_tx_bd": {"before": 142, "after": 142, "first_time_before": 480, "first_time_after": 480, "direction": "unchanged"}}}`

## Patch Summary

if (wb_write_access) begin if (addr_argument) begin argument_reg_next[7:0]   = wb_dat_i[7:
...<snip>...
b1; end else if (addr_bd_isr_enable) begin Bd_isr_enable_reg_next = wb_dat_i[7:0]; end end

## Lesson

Patch improved mismatch count or first fail time; continue from this direction.

## Reuse Constraints

- Read current RTL/spec evidence before applying a similar patch.
- Do not reuse if affected signals or timing alignment differ.
