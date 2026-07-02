---
memory_id: avoid_sd_controller_wb_dat_in_m_tx_bd_syntax_failed_9
type: negative_direction
stage: debug
description: "sd_controller_wb: dat_in_m_tx_bd syntax_failed; Patch failed lint and was rolled back; fix syntax before retrying this idea."
module: sd_controller_wb
module_family: sdc
signals:
  - bd_fsm_state_next
  - dat_in_m_tx_bd
  - dat_in_m_tx_bd_next
  - int_ack_next
  - wb_ack_o_next
  - we_m_tx_bd
  - we_m_tx_bd_next
failure_type: local_logic_bug
alignment: dut_late
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
  - bd_fsm_state_next
  - dat_in_m_tx_bd
  - dat_in_m_tx_bd_next
  - int_ack_next
  - wb_ack_o_next
  - we_m_tx_bd
  - we_m_tx_bd_next
trigger_failure_type: local_logic_bug
trigger_alignment: dut_late
risk_signals:
  - bd_fsm_state_next
  - dat_in_m_tx_bd
  - dat_in_m_tx_bd_next
  - int_ack_next
  - wb_ack_o_next
  - we_m_tx_bd
  - we_m_tx_bd_next
patch_pattern: "// BD multi-cycle write FSM — handles int_ack and wb_ack_o timing // RX: int_ack low 2 cyc\n...<snip>...\nBD_FSM_IDLE; end else begin int_ack_next      = 1'b1; bd_fsm_state_next = BD"
anti_trigger: "Avoid this direction unless new evidence distinguishes the current failure."
---

## 触发条件

- Module: `sd_controller_wb`
- Signal: `dat_in_m_tx_bd`
- Effect: `syntax_failed`
- First divergence: `{"signal": "dat_in_m_tx_bd", "time": 475, "ref": "1111111011110111", "dut": "0000000000000000", "classification": "dut_late", "ref_path": "tb.dat_in_m_tx_bd_ref[15:0]", "dut_path": "tb.dat_in_m_tx_bd_dut[15:0]", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "nonblocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`

## 不适用条件

- Do not reuse if affected signals, timing alignment, or spec intent differ.
- Do not reuse without reading current RTL/spec evidence.

## 补丁模式

// BD multi-cycle write FSM — handles int_ack and wb_ack_o timing // RX: int_ack low 2 cyc
...<snip>...
BD_FSM_IDLE; end else begin int_ack_next      = 1'b1; bd_fsm_state_next = BD_FSM_IDLE; end

## 验证特征

- Before mismatch count: `30714`
- After mismatch count: `None`
- Metric delta: `{"total_samples_mismatch": "9486 -> None", "per_signal": {"Bd_isr_enable_reg": {"before": 354, "after": 0, "first_time_before": 4420, "first_time_after": null, "direction": "improved"}, "Bd_isr_reset": {"before": 154, "after": 0, "first_time_before": 5450, "first_time_after": null, "direction": "improved"}, "argument_reg": {"before": 8194, "after": 0, "first_time_before": 2860, "first_time_after": null, "direction": "improved"}, "clock_divider": {"before": 422, "after": 0, "first_time_before": 3180, "first_time_after": null, "direction": "improved"}, "cmd_int_busy": {"before": 1880, "after": 0, "first_time_before": 2880, "first_time_after": null, "direction": "improved"}, "cmd_setting_reg": {"before": 8178, "after": 0, "first_time_before": 2860, "first_time_after": null, "direction": "improved"}, "dat_in_m_rx_bd": {"before": 502, "after": 0, "first_time_before": 3000, "first_time_after": null, "direction": "improved"}, "dat_in_m_tx_bd": {"before": 824, "after": 0, "first_time_before": 480, "first_time_after": null, "direction": "improved"}, "error_int_signal_enable_reg": {"before": 526, "after": 0, "first_time_before": 3620, "first_time_after": null, "direction": "improved"}, "error_isr_reset": {"before": 142, "after": 0, "first_time_before": 12520, "first_time_after": null, "direction": "improved"}, "int_ack": {"before": 194, "after": 0, "first_time_before": 3010, "first_time_after": null, "direction": "improved"}, "int_busy": {"before": 1088, "after": 0, "first_time_before": 1020, "first_time_after": null, "direction": "improved"}, "new_cmd": {"before": 2962, "after": 0, "first_time_before": 820, "first_time_after": null, "direction": "improved"}, "normal_int_signal_enable_reg": {"before": 462, "after": 0, "first_time_before": 7310, "first_time_after": null, "direction": "improved"}, "normal_isr_reset": {"before": 124, "after": 0, "first_time_before": 3790, "first_time_after": null, "direction": "improved"}, "software_reset_reg": {"before": 242, "after": 0, "first_time_before": 4280, "first_time_after": null, "direction": "improved"}, "time_out_reg": {"before": 554, "after": 0, "first_time_before": 8580, "first_time_after": null, "direction": "improved"}, "wb_ack_o": {"before": 34, "after": 0, "first_time_before": 12670, "first_time_after": null, "direction": "improved"}, "wb_dat_o": {"before": 1948, "after": 0, "first_time_before": 670, "first_time_after": null, "direction": "improved"}, "we_ack": {"before": 1880, "after": 0, "first_time_before": 2880, "first_time_after": null, "direction": "improved"}, "we_m_rx_bd": {"before": 32, "after": 0, "first_time_before": 3000, "first_time_after": null, "direction": "improved"}, "we_m_tx_bd": {"before": 18, "after": 0, "first_time_before": 480, "first_time_after": null, "direction": "improved"}}}`

## 复用约束

Patch failed lint and was rolled back; fix syntax before retrying this idea.

## Problem

`sd_controller_wb` showed a debug failure around `dat_in_m_tx_bd`.

## Evidence

- Effect: `syntax_failed`
- Before mismatch count: `30714`
- After mismatch count: `None`
- First divergence: `{"signal": "dat_in_m_tx_bd", "time": 475, "ref": "1111111011110111", "dut": "0000000000000000", "classification": "dut_late", "ref_path": "tb.dat_in_m_tx_bd_ref[15:0]", "dut_path": "tb.dat_in_m_tx_bd_dut[15:0]", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "nonblocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`
- Trace root failure: `{"signal": "dat_in_m_tx_bd", "time": 475, "ref": "1111111011110111", "dut": "0000000000000000", "classification": "dut_late", "ref_path": "tb.dat_in_m_tx_bd_ref[15:0]", "dut_path": "tb.dat_in_m_tx_bd_dut[15:0]", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "nonblocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`
- Metric delta: `{"total_samples_mismatch": "9486 -> None", "per_signal": {"Bd_isr_enable_reg": {"before": 354, "after": 0, "first_time_before": 4420, "first_time_after": null, "direction": "improved"}, "Bd_isr_reset": {"before": 154, "after": 0, "first_time_before": 5450, "first_time_after": null, "direction": "improved"}, "argument_reg": {"before": 8194, "after": 0, "first_time_before": 2860, "first_time_after": null, "direction": "improved"}, "clock_divider": {"before": 422, "after": 0, "first_time_before": 3180, "first_time_after": null, "direction": "improved"}, "cmd_int_busy": {"before": 1880, "after": 0, "first_time_before": 2880, "first_time_after": null, "direction": "improved"}, "cmd_setting_reg": {"before": 8178, "after": 0, "first_time_before": 2860, "first_time_after": null, "direction": "improved"}, "dat_in_m_rx_bd": {"before": 502, "after": 0, "first_time_before": 3000, "first_time_after": null, "direction": "improved"}, "dat_in_m_tx_bd": {"before": 824, "after": 0, "first_time_before": 480, "first_time_after": null, "direction": "improved"}, "error_int_signal_enable_reg": {"before": 526, "after": 0, "first_time_before": 3620, "first_time_after": null, "direction": "improved"}, "error_isr_reset": {"before": 142, "after": 0, "first_time_before": 12520, "first_time_after": null, "direction": "improved"}, "int_ack": {"before": 194, "after": 0, "first_time_before": 3010, "first_time_after": null, "direction": "improved"}, "int_busy": {"before": 1088, "after": 0, "first_time_before": 1020, "first_time_after": null, "direction": "improved"}, "new_cmd": {"before": 2962, "after": 0, "first_time_before": 820, "first_time_after": null, "direction": "improved"}, "normal_int_signal_enable_reg": {"before": 462, "after": 0, "first_time_before": 7310, "first_time_after": null, "direction": "improved"}, "normal_isr_reset": {"before": 124, "after": 0, "first_time_before": 3790, "first_time_after": null, "direction": "improved"}, "software_reset_reg": {"before": 242, "after": 0, "first_time_before": 4280, "first_time_after": null, "direction": "improved"}, "time_out_reg": {"before": 554, "after": 0, "first_time_before": 8580, "first_time_after": null, "direction": "improved"}, "wb_ack_o": {"before": 34, "after": 0, "first_time_before": 12670, "first_time_after": null, "direction": "improved"}, "wb_dat_o": {"before": 1948, "after": 0, "first_time_before": 670, "first_time_after": null, "direction": "improved"}, "we_ack": {"before": 1880, "after": 0, "first_time_before": 2880, "first_time_after": null, "direction": "improved"}, "we_m_rx_bd": {"before": 32, "after": 0, "first_time_before": 3000, "first_time_after": null, "direction": "improved"}, "we_m_tx_bd": {"before": 18, "after": 0, "first_time_before": 480, "first_time_after": null, "direction": "improved"}}}`

## Patch Summary

// BD multi-cycle write FSM — handles int_ack and wb_ack_o timing // RX: int_ack low 2 cyc
...<snip>...
BD_FSM_IDLE; end else begin int_ack_next      = 1'b1; bd_fsm_state_next = BD_FSM_IDLE; end

## Lesson

Patch failed lint and was rolled back; fix syntax before retrying this idea.

## Reuse Constraints

- Read current RTL/spec evidence before applying a similar patch.
- Do not reuse if affected signals or timing alignment differ.
