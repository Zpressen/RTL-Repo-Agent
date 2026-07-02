---
memory_id: avoid_sd_controller_wb_argument_reg_syntax_failed_2
type: negative_direction
stage: debug
description: "sd_controller_wb: argument_reg syntax_failed; Patch failed lint and was rolled back; fix syntax before retrying this idea."
module: sd_controller_wb
module_family: sdc
signals:
  - Bd_isr_enable_reg_next
  - Bd_isr_reset_next
  - argument_reg
  - argument_reg_next
  - clock_divider_next
  - cmd_setting_reg_next
  - error_int_signal_enable_reg_next
  - error_isr_reset_next
  - int_busy_next
  - new_cmd_next
  - normal_int_signal_enable_reg_next
  - normal_isr_reset_next
failure_type: local_logic_bug
alignment: wrong_value
outcome: syntax_failed
confidence: 0.68
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
  - argument_reg
  - argument_reg_next
  - clock_divider_next
  - cmd_setting_reg_next
  - error_int_signal_enable_reg_next
  - error_isr_reset_next
  - int_busy_next
  - new_cmd_next
  - normal_int_signal_enable_reg_next
  - normal_isr_reset_next
trigger_failure_type: local_logic_bug
trigger_alignment: wrong_value
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
anti_trigger: "Avoid this direction unless new evidence distinguishes the current failure."
---

## 触发条件

- Module: `sd_controller_wb`
- Signal: `argument_reg`
- Effect: `syntax_failed`
- First divergence: `{"signal": "argument_reg", "time": 285, "ref": "10011110111111011101010100000010", "dut": "10011110111111010000000000000000", "classification": "wrong_value", "ref_path": "tb.argument_reg_ref[31:0]", "dut_path": "tb.argument_reg_dut[31:0]", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "nonblocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`

## 不适用条件

- Do not reuse if affected signals, timing alignment, or spec intent differ.
- Do not reuse without reading current RTL/spec evidence.

## 补丁模式

if (wb_write_access) begin if (addr_argument) begin argument_reg_next[7:0]   = wb_dat_i[7:
...<snip>...
b1; end else if (addr_bd_isr_enable) begin Bd_isr_enable_reg_next = wb_dat_i[7:0]; end end

## 验证特征

- Before mismatch count: `38148`
- After mismatch count: `None`
- Metric delta: `{"total_samples_mismatch": "9676 -> None", "per_signal": {"Bd_isr_enable_reg": {"before": 830, "after": 0, "first_time_before": 4420, "first_time_after": null, "direction": "improved"}, "Bd_isr_reset": {"before": 154, "after": 0, "first_time_before": 5450, "first_time_after": null, "direction": "improved"}, "argument_reg": {"before": 8540, "after": 0, "first_time_before": 290, "first_time_after": null, "direction": "improved"}, "clock_divider": {"before": 1290, "after": 0, "first_time_before": 430, "first_time_after": null, "direction": "improved"}, "cmd_int_busy": {"before": 1880, "after": 0, "first_time_before": 2880, "first_time_after": null, "direction": "improved"}, "cmd_setting_reg": {"before": 8472, "after": 0, "first_time_before": 300, "first_time_after": null, "direction": "improved"}, "dat_in_m_rx_bd": {"before": 572, "after": 0, "first_time_before": 470, "first_time_after": null, "direction": "improved"}, "dat_in_m_tx_bd": {"before": 940, "after": 0, "first_time_before": 480, "first_time_after": null, "direction": "improved"}, "error_int_signal_enable_reg": {"before": 1872, "after": 0, "first_time_before": 410, "first_time_after": null, "direction": "improved"}, "error_isr_reset": {"before": 142, "after": 0, "first_time_before": 12520, "first_time_after": null, "direction": "improved"}, "int_ack": {"before": 72, "after": 0, "first_time_before": 480, "first_time_after": null, "direction": "improved"}, "int_busy": {"before": 1088, "after": 0, "first_time_before": 1020, "first_time_after": null, "direction": "improved"}, "new_cmd": {"before": 2962, "after": 0, "first_time_before": 820, "first_time_after": null, "direction": "improved"}, "normal_int_signal_enable_reg": {"before": 1824, "after": 0, "first_time_before": 400, "first_time_after": null, "direction": "improved"}, "normal_isr_reset": {"before": 124, "after": 0, "first_time_before": 3790, "first_time_after": null, "direction": "improved"}, "software_reset_reg": {"before": 670, "after": 0, "first_time_before": 4280, "first_time_after": null, "direction": "improved"}, "time_out_reg": {"before": 1860, "after": 0, "first_time_before": 370, "first_time_after": null, "direction": "improved"}, "wb_ack_o": {"before": 44, "after": 0, "first_time_before": 480, "first_time_after": null, "direction": "improved"}, "wb_dat_o": {"before": 2676, "after": 0, "first_time_before": 330, "first_time_after": null, "direction": "improved"}, "we_ack": {"before": 1880, "after": 0, "first_time_before": 2880, "first_time_after": null, "direction": "improved"}, "we_m_rx_bd": {"before": 114, "after": 0, "first_time_before": 470, "first_time_after": null, "direction": "improved"}, "we_m_tx_bd": {"before": 142, "after": 0, "first_time_before": 480, "first_time_after": null, "direction": "improved"}}}`

## 复用约束

Patch failed lint and was rolled back; fix syntax before retrying this idea.

## Problem

`sd_controller_wb` showed a debug failure around `argument_reg`.

## Evidence

- Effect: `syntax_failed`
- Before mismatch count: `38148`
- After mismatch count: `None`
- First divergence: `{"signal": "argument_reg", "time": 285, "ref": "10011110111111011101010100000010", "dut": "10011110111111010000000000000000", "classification": "wrong_value", "ref_path": "tb.argument_reg_ref[31:0]", "dut_path": "tb.argument_reg_dut[31:0]", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "nonblocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`
- Trace root failure: `{"signal": "argument_reg", "time": 285, "ref": "10011110111111011101010100000010", "dut": "10011110111111010000000000000000", "classification": "wrong_value", "ref_path": "tb.argument_reg_ref[31:0]", "dut_path": "tb.argument_reg_dut[31:0]", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "nonblocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`
- Metric delta: `{"total_samples_mismatch": "9676 -> None", "per_signal": {"Bd_isr_enable_reg": {"before": 830, "after": 0, "first_time_before": 4420, "first_time_after": null, "direction": "improved"}, "Bd_isr_reset": {"before": 154, "after": 0, "first_time_before": 5450, "first_time_after": null, "direction": "improved"}, "argument_reg": {"before": 8540, "after": 0, "first_time_before": 290, "first_time_after": null, "direction": "improved"}, "clock_divider": {"before": 1290, "after": 0, "first_time_before": 430, "first_time_after": null, "direction": "improved"}, "cmd_int_busy": {"before": 1880, "after": 0, "first_time_before": 2880, "first_time_after": null, "direction": "improved"}, "cmd_setting_reg": {"before": 8472, "after": 0, "first_time_before": 300, "first_time_after": null, "direction": "improved"}, "dat_in_m_rx_bd": {"before": 572, "after": 0, "first_time_before": 470, "first_time_after": null, "direction": "improved"}, "dat_in_m_tx_bd": {"before": 940, "after": 0, "first_time_before": 480, "first_time_after": null, "direction": "improved"}, "error_int_signal_enable_reg": {"before": 1872, "after": 0, "first_time_before": 410, "first_time_after": null, "direction": "improved"}, "error_isr_reset": {"before": 142, "after": 0, "first_time_before": 12520, "first_time_after": null, "direction": "improved"}, "int_ack": {"before": 72, "after": 0, "first_time_before": 480, "first_time_after": null, "direction": "improved"}, "int_busy": {"before": 1088, "after": 0, "first_time_before": 1020, "first_time_after": null, "direction": "improved"}, "new_cmd": {"before": 2962, "after": 0, "first_time_before": 820, "first_time_after": null, "direction": "improved"}, "normal_int_signal_enable_reg": {"before": 1824, "after": 0, "first_time_before": 400, "first_time_after": null, "direction": "improved"}, "normal_isr_reset": {"before": 124, "after": 0, "first_time_before": 3790, "first_time_after": null, "direction": "improved"}, "software_reset_reg": {"before": 670, "after": 0, "first_time_before": 4280, "first_time_after": null, "direction": "improved"}, "time_out_reg": {"before": 1860, "after": 0, "first_time_before": 370, "first_time_after": null, "direction": "improved"}, "wb_ack_o": {"before": 44, "after": 0, "first_time_before": 480, "first_time_after": null, "direction": "improved"}, "wb_dat_o": {"before": 2676, "after": 0, "first_time_before": 330, "first_time_after": null, "direction": "improved"}, "we_ack": {"before": 1880, "after": 0, "first_time_before": 2880, "first_time_after": null, "direction": "improved"}, "we_m_rx_bd": {"before": 114, "after": 0, "first_time_before": 470, "first_time_after": null, "direction": "improved"}, "we_m_tx_bd": {"before": 142, "after": 0, "first_time_before": 480, "first_time_after": null, "direction": "improved"}}}`

## Patch Summary

if (wb_write_access) begin if (addr_argument) begin argument_reg_next[7:0]   = wb_dat_i[7:
...<snip>...
b1; end else if (addr_bd_isr_enable) begin Bd_isr_enable_reg_next = wb_dat_i[7:0]; end end

## Lesson

Patch failed lint and was rolled back; fix syntax before retrying this idea.

## Reuse Constraints

- Read current RTL/spec evidence before applying a similar patch.
- Do not reuse if affected signals or timing alignment differ.
