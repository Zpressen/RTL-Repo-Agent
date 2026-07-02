---
memory_id: debug_sd_bd_dat_out_s_improved_3
type: repair_outcome
stage: debug
description: "sd_bd: dat_out_s improved; Patch improved mismatch count or first fail time; continue from this direction."
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
- Before mismatch count: `4075`
- After mismatch count: `3568`
- First divergence: `{"signal": "dat_out_s", "time": 155, "ref": "0000000000000000", "dut": "0101110110011100", "classification": "dut_early", "ref_path": "tb_sd_bd.dat_out_s_ref[15:0]", "dut_path": "tb_sd_bd.dat_out_s_dut[15:0]", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "blocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`
- Trace root failure: `{"signal": "dat_out_s", "time": 155, "ref": "0000000000000000", "dut": "0101110110011100", "classification": "dut_early", "ref_path": "tb_sd_bd.dat_out_s_ref[15:0]", "dut_path": "tb_sd_bd.dat_out_s_dut[15:0]", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "blocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`
- Metric delta: `{"total_samples_mismatch": null, "per_signal": {"ack_o_s": {"before": 18, "after": 18, "first_time_before": 16855, "first_time_after": 16855, "direction": "unchanged"}, "dat_out_s": {"before": 2638, "after": 2612, "first_time_before": 165, "first_time_after": 165, "direction": "improved"}, "free_bd": {"before": 1419, "after": 938, "first_time_before": 195, "first_time_after": 14765, "direction": "improved"}}}`

## Patch Summary

// STAGE5_SUBTASK_BEGIN B2_write_sequence_B5_release: Merged sequential block — // write o
...<snip>...
_reg <= free_bd_reg - 1'b1; end end end // STAGE5_SUBTASK_END B2_write_sequence_B5_release

## Lesson

Patch improved mismatch count or first fail time; continue from this direction.

## Reuse Constraints

- Read current RTL/spec evidence before applying a similar patch.
- Do not reuse if affected signals or timing alignment differ.
