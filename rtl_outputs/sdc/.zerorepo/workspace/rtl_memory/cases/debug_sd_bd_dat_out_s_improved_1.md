---
memory_id: debug_sd_bd_dat_out_s_improved_1
type: repair_outcome
stage: debug
description: "sd_bd: dat_out_s improved; Patch improved mismatch count or first fail time; continue from this direction."
module: sd_bd
module_family: sdc
signals:
  - MODE_16BIT
  - dat_out_s
failure_type: local_logic_bug
alignment: dut_early
outcome: improved
confidence: 0.72
verified_by:
  - lint
  - module_sim
  - trace
source_artifacts:
  - debug/sd_bd/trace_report.json
  - repo_react/sd_bd/patch_journal.jsonl
---

## Problem

`sd_bd` showed a debug failure around `dat_out_s`.

## Evidence

- Effect: `improved`
- Before mismatch count: `6803`
- After mismatch count: `4075`
- First divergence: `{"signal": "dat_out_s", "time": 155, "ref": "0000000000000000", "dut": "0101110110011100", "classification": "dut_early", "ref_path": "tb_sd_bd.dat_out_s_ref[15:0]", "dut_path": "tb_sd_bd.dat_out_s_dut[15:0]", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "blocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`
- Trace root failure: `{"signal": "dat_out_s", "time": 155, "ref": "0000000000000000", "dut": "0101110110011100", "classification": "dut_early", "ref_path": "tb_sd_bd.dat_out_s_ref[15:0]", "dut_path": "tb_sd_bd.dat_out_s_dut[15:0]", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "blocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`
- Metric delta: `{"total_samples_mismatch": null, "per_signal": {"ack_o_s": {"before": 1132, "after": 18, "first_time_before": 135, "first_time_after": 16855, "direction": "improved"}, "dat_out_s": {"before": 2744, "after": 2638, "first_time_before": 165, "first_time_after": 165, "direction": "improved"}, "free_bd": {"before": 2927, "after": 1419, "first_time_before": 105, "first_time_after": 195, "direction": "improved"}}}`

## Patch Summary

parameter MODE_16BIT = 1'b1;

## Lesson

Patch improved mismatch count or first fail time; continue from this direction.

## Reuse Constraints

- Read current RTL/spec evidence before applying a similar patch.
- Do not reuse if affected signals or timing alignment differ.
