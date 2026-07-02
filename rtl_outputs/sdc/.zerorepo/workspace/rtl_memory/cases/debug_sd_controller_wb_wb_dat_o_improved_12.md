---
memory_id: debug_sd_controller_wb_wb_dat_o_improved_12
type: repair_outcome
stage: debug
description: "sd_controller_wb: wb_dat_o improved; Patch was kept by acceptance judge: Patch successfully fixes the original first failure: dat_in_m_tx_bd no longer clears"
module: sd_controller_wb
module_family: sdc
signals:
  - dat_in_m_rx_bd_next
  - dat_in_m_tx_bd_next
  - wb_dat_o
failure_type: timing_bug
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
  - dat_in_m_rx_bd_next
  - dat_in_m_tx_bd_next
  - wb_dat_o
trigger_failure_type: timing_bug
trigger_alignment: dut_early
risk_signals:
  - dat_in_m_rx_bd_next
  - dat_in_m_tx_bd_next
patch_pattern: "dat_in_m_tx_bd_next               = dat_in_m_tx_bd; dat_in_m_rx_bd_next               = dat_in_m_rx_bd;"
anti_trigger: "Do not reuse when current first divergence, affected signals, or timing alignment differ."
---

## 触发条件

- Module: `sd_controller_wb`
- Signal: `wb_dat_o`
- Effect: `improved`
- First divergence: `{"signal": "wb_dat_o", "time": 665, "ref": "00000000000000000000000001100011", "dut": "00000000000000000000000000000000", "classification": "dut_early", "ref_path": "tb.wb_dat_o_ref[31:0]", "dut_path": "tb.wb_dat_o_dut[31:0]", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "nonblocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`

## 不适用条件

- Do not reuse if affected signals, timing alignment, or spec intent differ.
- Do not reuse without reading current RTL/spec evidence.

## 补丁模式

dat_in_m_tx_bd_next               = dat_in_m_tx_bd; dat_in_m_rx_bd_next               = dat_in_m_rx_bd;

## 验证特征

- Before mismatch count: `30822`
- After mismatch count: `30832`
- Metric delta: `{"total_samples_mismatch": "9488 -> 9320", "per_signal": {"Bd_isr_enable_reg": {"before": 354, "after": 354, "first_time_before": 4420, "first_time_after": 4420, "direction": "unchanged"}, "Bd_isr_reset": {"before": 154, "after": 154, "first_time_before": 5450, "first_time_after": 5450, "direction": "unchanged"}, "argument_reg": {"before": 8194, "after": 8194, "first_time_before": 2860, "first_time_after": 2860, "direction": "unchanged"}, "clock_divider": {"before": 422, "after": 422, "first_time_before": 3180, "first_time_after": 3180, "direction": "unchanged"}, "cmd_int_busy": {"before": 1880, "after": 1880, "first_time_before": 2880, "first_time_after": 2880, "direction": "unchanged"}, "cmd_setting_reg": {"before": 8178, "after": 8178, "first_time_before": 2860, "first_time_after": 2860, "direction": "unchanged"}, "dat_in_m_rx_bd": {"before": 502, "after": 502, "first_time_before": 3000, "first_time_after": 3000, "direction": "unchanged"}, "dat_in_m_tx_bd": {"before": 878, "after": 888, "first_time_before": 490, "first_time_after": 4600, "direction": "regressed"}, "error_int_signal_enable_reg": {"before": 526, "after": 526, "first_time_before": 3620, "first_time_after": 3620, "direction": "unchanged"}, "error_isr_reset": {"before": 142, "after": 142, "first_time_before": 12520, "first_time_after": 12520, "direction": "unchanged"}, "int_ack": {"before": 194, "after": 194, "first_time_before": 3010, "first_time_after": 3010, "direction": "unchanged"}, "int_busy": {"before": 1088, "after": 1088, "first_time_before": 1020, "first_time_after": 1020, "direction": "unchanged"}, "new_cmd": {"before": 2962, "after": 2962, "first_time_before": 820, "first_time_after": 820, "direction": "unchanged"}, "normal_int_signal_enable_reg": {"before": 462, "after": 462, "first_time_before": 7310, "first_time_after": 7310, "direction": "unchanged"}, "normal_isr_reset": {"before": 124, "after": 124, "first_time_before": 3790, "first_time_after": 3790, "direction": "unchanged"}, "software_reset_reg": {"before": 242, "after": 242, "first_time_before": 4280, "first_time_after": 4280, "direction": "unchanged"}, "time_out_reg": {"before": 554, "after": 554, "first_time_before": 8580, "first_time_after": 8580, "direction": "unchanged"}, "wb_ack_o": {"before": 34, "after": 34, "first_time_before": 12670, "first_time_after": 12670, "direction": "unchanged"}, "wb_dat_o": {"before": 1948, "after": 1948, "first_time_before": 670, "first_time_after": 670, "direction": "unchanged"}, "we_ack": {"before": 1880, "after": 1880, "first_time_before": 2880, "first_time_after": 2880, "direction": "unchanged"}, "we_m_rx_bd": {"before": 32, "after": 32, "first_time_before": 3000, "first_time_after": 3000, "direction": "unchanged"}, "we_m_tx_bd": {"before": 72, "after": 72, "first_time_before": 4600, "first_time_after": 4600, "direction": "unchanged"}}}`

## 复用约束

Patch was kept by acceptance judge: Patch successfully fixes the original first failure: dat_in_m_tx_bd no longer clears to 0 at t=485, and its first mismatch moves from t=490→t=4600. The new first failure is wb_dat_o at t=670 (unchanged from baseline). Total mismatch samples improved (9488→9320). The slight regression in dat_in_m_tx_bd count (878→888, +10) is at much later times and likely a different scenario unmasked by the fix. This is a clear stepping stone that eliminates the earliest divergence without harming any other signal.

## Problem

`sd_controller_wb` showed a debug failure around `wb_dat_o`.

## Evidence

- Effect: `improved`
- Before mismatch count: `30822`
- After mismatch count: `30832`
- First divergence: `{"signal": "wb_dat_o", "time": 665, "ref": "00000000000000000000000001100011", "dut": "00000000000000000000000000000000", "classification": "dut_early", "ref_path": "tb.wb_dat_o_ref[31:0]", "dut_path": "tb.wb_dat_o_dut[31:0]", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "nonblocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`
- Trace root failure: `{"signal": "wb_dat_o", "time": 665, "ref": "00000000000000000000000001100011", "dut": "00000000000000000000000000000000", "classification": "dut_early", "ref_path": "tb.wb_dat_o_ref[31:0]", "dut_path": "tb.wb_dat_o_dut[31:0]", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "nonblocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`
- Metric delta: `{"total_samples_mismatch": "9488 -> 9320", "per_signal": {"Bd_isr_enable_reg": {"before": 354, "after": 354, "first_time_before": 4420, "first_time_after": 4420, "direction": "unchanged"}, "Bd_isr_reset": {"before": 154, "after": 154, "first_time_before": 5450, "first_time_after": 5450, "direction": "unchanged"}, "argument_reg": {"before": 8194, "after": 8194, "first_time_before": 2860, "first_time_after": 2860, "direction": "unchanged"}, "clock_divider": {"before": 422, "after": 422, "first_time_before": 3180, "first_time_after": 3180, "direction": "unchanged"}, "cmd_int_busy": {"before": 1880, "after": 1880, "first_time_before": 2880, "first_time_after": 2880, "direction": "unchanged"}, "cmd_setting_reg": {"before": 8178, "after": 8178, "first_time_before": 2860, "first_time_after": 2860, "direction": "unchanged"}, "dat_in_m_rx_bd": {"before": 502, "after": 502, "first_time_before": 3000, "first_time_after": 3000, "direction": "unchanged"}, "dat_in_m_tx_bd": {"before": 878, "after": 888, "first_time_before": 490, "first_time_after": 4600, "direction": "regressed"}, "error_int_signal_enable_reg": {"before": 526, "after": 526, "first_time_before": 3620, "first_time_after": 3620, "direction": "unchanged"}, "error_isr_reset": {"before": 142, "after": 142, "first_time_before": 12520, "first_time_after": 12520, "direction": "unchanged"}, "int_ack": {"before": 194, "after": 194, "first_time_before": 3010, "first_time_after": 3010, "direction": "unchanged"}, "int_busy": {"before": 1088, "after": 1088, "first_time_before": 1020, "first_time_after": 1020, "direction": "unchanged"}, "new_cmd": {"before": 2962, "after": 2962, "first_time_before": 820, "first_time_after": 820, "direction": "unchanged"}, "normal_int_signal_enable_reg": {"before": 462, "after": 462, "first_time_before": 7310, "first_time_after": 7310, "direction": "unchanged"}, "normal_isr_reset": {"before": 124, "after": 124, "first_time_before": 3790, "first_time_after": 3790, "direction": "unchanged"}, "software_reset_reg": {"before": 242, "after": 242, "first_time_before": 4280, "first_time_after": 4280, "direction": "unchanged"}, "time_out_reg": {"before": 554, "after": 554, "first_time_before": 8580, "first_time_after": 8580, "direction": "unchanged"}, "wb_ack_o": {"before": 34, "after": 34, "first_time_before": 12670, "first_time_after": 12670, "direction": "unchanged"}, "wb_dat_o": {"before": 1948, "after": 1948, "first_time_before": 670, "first_time_after": 670, "direction": "unchanged"}, "we_ack": {"before": 1880, "after": 1880, "first_time_before": 2880, "first_time_after": 2880, "direction": "unchanged"}, "we_m_rx_bd": {"before": 32, "after": 32, "first_time_before": 3000, "first_time_after": 3000, "direction": "unchanged"}, "we_m_tx_bd": {"before": 72, "after": 72, "first_time_before": 4600, "first_time_after": 4600, "direction": "unchanged"}}}`

## Patch Summary

dat_in_m_tx_bd_next               = dat_in_m_tx_bd; dat_in_m_rx_bd_next               = dat_in_m_rx_bd;

## Lesson

Patch was kept by acceptance judge: Patch successfully fixes the original first failure: dat_in_m_tx_bd no longer clears to 0 at t=485, and its first mismatch moves from t=490→t=4600. The new first failure is wb_dat_o at t=670 (unchanged from baseline). Total mismatch samples improved (9488→9320). The slight regression in dat_in_m_tx_bd count (878→888, +10) is at much later times and likely a different scenario unmasked by the fix. This is a clear stepping stone that eliminates the earliest divergence without harming any other signal.

## Reuse Constraints

- Read current RTL/spec evidence before applying a similar patch.
- Do not reuse if affected signals or timing alignment differ.
