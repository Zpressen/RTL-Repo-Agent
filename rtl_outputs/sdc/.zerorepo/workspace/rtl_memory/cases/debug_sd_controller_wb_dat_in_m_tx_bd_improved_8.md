---
memory_id: debug_sd_controller_wb_dat_in_m_tx_bd_improved_8
type: repair_outcome
stage: debug
description: "sd_controller_wb: dat_in_m_tx_bd improved; Patch improved mismatch count or first fail time; continue from this direction."
module: sd_controller_wb
module_family: sdc
signals:
  - bd_fsm_state_next
  - bd_rx_high_word_next
  - bd_rx_low_word_next
  - bd_tx_high_word_next
  - bd_tx_low_word_next
  - dat_in_m_rx_bd_next
  - dat_in_m_tx_bd
  - dat_in_m_tx_bd_next
  - int_ack_next
  - we_m_rx_bd_next
  - we_m_tx_bd_next
failure_type: timing_bug
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
  - bd_fsm_state_next
  - bd_rx_high_word_next
  - bd_rx_low_word_next
  - bd_tx_high_word_next
  - bd_tx_low_word_next
  - dat_in_m_rx_bd_next
  - dat_in_m_tx_bd
  - dat_in_m_tx_bd_next
  - int_ack_next
  - we_m_rx_bd_next
  - we_m_tx_bd_next
trigger_failure_type: timing_bug
trigger_alignment: dut_late
risk_signals:
  - bd_fsm_state_next
  - bd_rx_high_word_next
  - bd_rx_low_word_next
  - bd_tx_high_word_next
  - bd_tx_low_word_next
  - dat_in_m_rx_bd_next
  - dat_in_m_tx_bd_next
  - int_ack_next
  - we_m_rx_bd_next
  - we_m_tx_bd_next
patch_pattern: "// BD multi-cycle write FSM — handles int_ack and wb_ack_o timing only // we_m_* and dat_i\n...<snip>...\nBD_FSM_IDLE; end else begin int_ack_next      = 1'b1; bd_fsm_state_next = BD"
anti_trigger: "Do not reuse when current first divergence, affected signals, or timing alignment differ."
---

## 触发条件

- Module: `sd_controller_wb`
- Signal: `dat_in_m_tx_bd`
- Effect: `improved`
- First divergence: `{"signal": "dat_in_m_tx_bd", "time": 475, "ref": "1111111011110111", "dut": "0000000000000000", "classification": "dut_late", "ref_path": "tb.dat_in_m_tx_bd_ref[15:0]", "dut_path": "tb.dat_in_m_tx_bd_dut[15:0]", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "nonblocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`

## 不适用条件

- Do not reuse if affected signals, timing alignment, or spec intent differ.
- Do not reuse without reading current RTL/spec evidence.

## 补丁模式

// BD multi-cycle write FSM — handles int_ack and wb_ack_o timing only // we_m_* and dat_i
...<snip>...
BD_FSM_IDLE; end else begin int_ack_next      = 1'b1; bd_fsm_state_next = BD_FSM_IDLE; end

## 验证特征

- Before mismatch count: `30994`
- After mismatch count: `30714`
- Metric delta: `{"total_samples_mismatch": "9492 -> 9486", "per_signal": {"Bd_isr_enable_reg": {"before": 354, "after": 354, "first_time_before": 4420, "first_time_after": 4420, "direction": "unchanged"}, "Bd_isr_reset": {"before": 154, "after": 154, "first_time_before": 5450, "first_time_after": 5450, "direction": "unchanged"}, "argument_reg": {"before": 8194, "after": 8194, "first_time_before": 2860, "first_time_after": 2860, "direction": "unchanged"}, "clock_divider": {"before": 422, "after": 422, "first_time_before": 3180, "first_time_after": 3180, "direction": "unchanged"}, "cmd_int_busy": {"before": 1880, "after": 1880, "first_time_before": 2880, "first_time_after": 2880, "direction": "unchanged"}, "cmd_setting_reg": {"before": 8178, "after": 8178, "first_time_before": 2860, "first_time_after": 2860, "direction": "unchanged"}, "dat_in_m_rx_bd": {"before": 572, "after": 502, "first_time_before": 470, "first_time_after": 3000, "direction": "improved"}, "dat_in_m_tx_bd": {"before": 940, "after": 824, "first_time_before": 480, "first_time_after": 480, "direction": "improved"}, "error_int_signal_enable_reg": {"before": 526, "after": 526, "first_time_before": 3620, "first_time_after": 3620, "direction": "unchanged"}, "error_isr_reset": {"before": 142, "after": 142, "first_time_before": 12520, "first_time_after": 12520, "direction": "unchanged"}, "int_ack": {"before": 72, "after": 194, "first_time_before": 480, "first_time_after": 3010, "direction": "regressed"}, "int_busy": {"before": 1088, "after": 1088, "first_time_before": 1020, "first_time_after": 1020, "direction": "unchanged"}, "new_cmd": {"before": 2962, "after": 2962, "first_time_before": 820, "first_time_after": 820, "direction": "unchanged"}, "normal_int_signal_enable_reg": {"before": 462, "after": 462, "first_time_before": 7310, "first_time_after": 7310, "direction": "unchanged"}, "normal_isr_reset": {"before": 124, "after": 124, "first_time_before": 3790, "first_time_after": 3790, "direction": "unchanged"}, "software_reset_reg": {"before": 242, "after": 242, "first_time_before": 4280, "first_time_after": 4280, "direction": "unchanged"}, "time_out_reg": {"before": 554, "after": 554, "first_time_before": 8580, "first_time_after": 8580, "direction": "unchanged"}, "wb_ack_o": {"before": 44, "after": 34, "first_time_before": 480, "first_time_after": 12670, "direction": "improved"}, "wb_dat_o": {"before": 1948, "after": 1948, "first_time_before": 670, "first_time_after": 670, "direction": "unchanged"}, "we_ack": {"before": 1880, "after": 1880, "first_time_before": 2880, "first_time_after": 2880, "direction": "unchanged"}, "we_m_rx_bd": {"before": 114, "after": 32, "first_time_before": 470, "first_time_after": 3000, "direction": "improved"}, "we_m_tx_bd": {"before": 142, "after": 18, "first_time_before": 480, "first_time_after": 480, "direction": "improved"}}}`

## 复用约束

Patch improved mismatch count or first fail time; continue from this direction.

## Problem

`sd_controller_wb` showed a debug failure around `dat_in_m_tx_bd`.

## Evidence

- Effect: `improved`
- Before mismatch count: `30994`
- After mismatch count: `30714`
- First divergence: `{"signal": "dat_in_m_tx_bd", "time": 475, "ref": "1111111011110111", "dut": "0000000000000000", "classification": "dut_late", "ref_path": "tb.dat_in_m_tx_bd_ref[15:0]", "dut_path": "tb.dat_in_m_tx_bd_dut[15:0]", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "nonblocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`
- Trace root failure: `{"signal": "dat_in_m_tx_bd", "time": 475, "ref": "1111111011110111", "dut": "0000000000000000", "classification": "dut_late", "ref_path": "tb.dat_in_m_tx_bd_ref[15:0]", "dut_path": "tb.dat_in_m_tx_bd_dut[15:0]", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "nonblocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`
- Metric delta: `{"total_samples_mismatch": "9492 -> 9486", "per_signal": {"Bd_isr_enable_reg": {"before": 354, "after": 354, "first_time_before": 4420, "first_time_after": 4420, "direction": "unchanged"}, "Bd_isr_reset": {"before": 154, "after": 154, "first_time_before": 5450, "first_time_after": 5450, "direction": "unchanged"}, "argument_reg": {"before": 8194, "after": 8194, "first_time_before": 2860, "first_time_after": 2860, "direction": "unchanged"}, "clock_divider": {"before": 422, "after": 422, "first_time_before": 3180, "first_time_after": 3180, "direction": "unchanged"}, "cmd_int_busy": {"before": 1880, "after": 1880, "first_time_before": 2880, "first_time_after": 2880, "direction": "unchanged"}, "cmd_setting_reg": {"before": 8178, "after": 8178, "first_time_before": 2860, "first_time_after": 2860, "direction": "unchanged"}, "dat_in_m_rx_bd": {"before": 572, "after": 502, "first_time_before": 470, "first_time_after": 3000, "direction": "improved"}, "dat_in_m_tx_bd": {"before": 940, "after": 824, "first_time_before": 480, "first_time_after": 480, "direction": "improved"}, "error_int_signal_enable_reg": {"before": 526, "after": 526, "first_time_before": 3620, "first_time_after": 3620, "direction": "unchanged"}, "error_isr_reset": {"before": 142, "after": 142, "first_time_before": 12520, "first_time_after": 12520, "direction": "unchanged"}, "int_ack": {"before": 72, "after": 194, "first_time_before": 480, "first_time_after": 3010, "direction": "regressed"}, "int_busy": {"before": 1088, "after": 1088, "first_time_before": 1020, "first_time_after": 1020, "direction": "unchanged"}, "new_cmd": {"before": 2962, "after": 2962, "first_time_before": 820, "first_time_after": 820, "direction": "unchanged"}, "normal_int_signal_enable_reg": {"before": 462, "after": 462, "first_time_before": 7310, "first_time_after": 7310, "direction": "unchanged"}, "normal_isr_reset": {"before": 124, "after": 124, "first_time_before": 3790, "first_time_after": 3790, "direction": "unchanged"}, "software_reset_reg": {"before": 242, "after": 242, "first_time_before": 4280, "first_time_after": 4280, "direction": "unchanged"}, "time_out_reg": {"before": 554, "after": 554, "first_time_before": 8580, "first_time_after": 8580, "direction": "unchanged"}, "wb_ack_o": {"before": 44, "after": 34, "first_time_before": 480, "first_time_after": 12670, "direction": "improved"}, "wb_dat_o": {"before": 1948, "after": 1948, "first_time_before": 670, "first_time_after": 670, "direction": "unchanged"}, "we_ack": {"before": 1880, "after": 1880, "first_time_before": 2880, "first_time_after": 2880, "direction": "unchanged"}, "we_m_rx_bd": {"before": 114, "after": 32, "first_time_before": 470, "first_time_after": 3000, "direction": "improved"}, "we_m_tx_bd": {"before": 142, "after": 18, "first_time_before": 480, "first_time_after": 480, "direction": "improved"}}}`

## Patch Summary

// BD multi-cycle write FSM — handles int_ack and wb_ack_o timing only // we_m_* and dat_i
...<snip>...
BD_FSM_IDLE; end else begin int_ack_next      = 1'b1; bd_fsm_state_next = BD_FSM_IDLE; end

## Lesson

Patch improved mismatch count or first fail time; continue from this direction.

## Reuse Constraints

- Read current RTL/spec evidence before applying a similar patch.
- Do not reuse if affected signals or timing alignment differ.
