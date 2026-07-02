---
memory_id: debug_sd_bd_free_bd_pass_5
type: repair_outcome
stage: debug
description: "sd_bd: free_bd passed; Patch fixed all observed mismatches."
module: sd_bd
module_family: sdc
signals:
  - bd_mem_0
  - bd_mem_1
  - bd_mem_10
  - bd_mem_11
  - bd_mem_12
  - bd_mem_13
  - bd_mem_14
  - bd_mem_15
  - bd_mem_16
  - bd_mem_17
  - bd_mem_18
  - bd_mem_19
failure_type: timing_bug
alignment: dut_early
outcome: pass
confidence: 0.9
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

- Effect: `passed`
- Before mismatch count: `950`
- After mismatch count: `0`
- First divergence: `{"signal": "free_bd", "time": 14755, "ref": "00110", "dut": "00111", "classification": "dut_early", "ref_path": "tb_sd_bd.free_bd_ref[4:0]", "dut_path": "tb_sd_bd.free_bd_dut[4:0]", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "continuous", "active_region_model": "settled VCD ref/dut values at sample/change times"}`
- Trace root failure: `{"signal": "free_bd", "time": 14755, "ref": "00110", "dut": "00111", "classification": "dut_early", "ref_path": "tb_sd_bd.free_bd_ref[4:0]", "dut_path": "tb_sd_bd.free_bd_dut[4:0]", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "continuous", "active_region_model": "settled VCD ref/dut values at sample/change times"}`
- Metric delta: `{"total_samples_mismatch": null, "per_signal": {"dat_out_s": {"before": 12, "after": null, "first_time_before": 32215, "first_time_after": null, "direction": "unknown"}, "free_bd": {"before": 938, "after": null, "first_time_before": 14765, "first_time_after": null, "direction": "unknown"}}}`

## Patch Summary

// STAGE5_SUBTASK_BEGIN B2_write_sequence_B5_release: Merged sequential block — // write o
...<snip>...
 begin last_a_cmp <= a_cmp; end end end // STAGE5_SUBTASK_END B2_write_sequence_B5_release

## Lesson

Patch fixed all observed mismatches.

## Reuse Constraints

- Read current RTL/spec evidence before applying a similar patch.
- Do not reuse if affected signals or timing alignment differ.
