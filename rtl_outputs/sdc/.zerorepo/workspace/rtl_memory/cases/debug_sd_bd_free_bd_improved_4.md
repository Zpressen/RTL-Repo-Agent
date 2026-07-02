---
memory_id: debug_sd_bd_free_bd_improved_4
type: repair_outcome
stage: debug
description: "sd_bd: free_bd improved; Patch improved mismatch count or first fail time; continue from this direction."
module: sd_bd
module_family: sdc
signals:
  - ack_o_s
  - dat_out_s
  - free_bd
  - rd_cnt
  - s_rd_pnt
failure_type: timing_bug
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

`sd_bd` showed a debug failure around `free_bd`.

## Evidence

- Effect: `improved`
- Before mismatch count: `3568`
- After mismatch count: `950`
- First divergence: `{"signal": "free_bd", "time": 14755, "ref": "00110", "dut": "00111", "classification": "dut_early", "ref_path": "tb_sd_bd.free_bd_ref[4:0]", "dut_path": "tb_sd_bd.free_bd_dut[4:0]", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "continuous", "active_region_model": "settled VCD ref/dut values at sample/change times"}`
- Trace root failure: `{"signal": "free_bd", "time": 14755, "ref": "00110", "dut": "00111", "classification": "dut_early", "ref_path": "tb_sd_bd.free_bd_ref[4:0]", "dut_path": "tb_sd_bd.free_bd_dut[4:0]", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "continuous", "active_region_model": "settled VCD ref/dut values at sample/change times"}`
- Metric delta: `{"total_samples_mismatch": null, "per_signal": {"ack_o_s": {"before": 18, "after": null, "first_time_before": 16855, "first_time_after": null, "direction": "unknown"}, "dat_out_s": {"before": 2612, "after": 12, "first_time_before": 165, "first_time_after": 32215, "direction": "improved"}, "free_bd": {"before": 938, "after": 938, "first_time_before": 14765, "first_time_after": 14765, "direction": "unchanged"}}}`

## Patch Summary

// STAGE5_SUBTASK_BEGIN B3_read_sequence: Sequential block for read pointer // management,
...<snip>...
4_comb_output: Removed — outputs now registered in B3 // STAGE5_SUBTASK_END B4_comb_output

## Lesson

Patch improved mismatch count or first fail time; continue from this direction.

## Reuse Constraints

- Read current RTL/spec evidence before applying a similar patch.
- Do not reuse if affected signals or timing alignment differ.
