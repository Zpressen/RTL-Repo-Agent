---
memory_id: avoid_sd_bd_dat_out_s_regressed_2
type: negative_direction
stage: debug
description: "sd_bd: dat_out_s regressed; Patch worsened mismatch count or first fail time and was rolled back."
module: sd_bd
module_family: sdc
signals:
  - ack_o_s
  - dat_out_s
failure_type: local_logic_bug
alignment: dut_early
outcome: regressed
confidence: 0.68
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

- Effect: `regressed`
- Before mismatch count: `4075`
- After mismatch count: `4346`
- First divergence: `{"signal": "dat_out_s", "time": 155, "ref": "0000000000000000", "dut": "0101110110011100", "classification": "dut_early", "ref_path": "tb_sd_bd.dat_out_s_ref[15:0]", "dut_path": "tb_sd_bd.dat_out_s_dut[15:0]", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "blocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`
- Trace root failure: `{"signal": "dat_out_s", "time": 155, "ref": "0000000000000000", "dut": "0101110110011100", "classification": "dut_early", "ref_path": "tb_sd_bd.dat_out_s_ref[15:0]", "dut_path": "tb_sd_bd.dat_out_s_dut[15:0]", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "blocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`
- Metric delta: `{"total_samples_mismatch": null, "per_signal": {"ack_o_s": {"before": 18, "after": 18, "first_time_before": 16855, "first_time_after": 16855, "direction": "unchanged"}, "dat_out_s": {"before": 2638, "after": 2909, "first_time_before": 165, "first_time_after": 235, "direction": "regressed"}, "free_bd": {"before": 1419, "after": 1419, "first_time_before": 195, "first_time_after": 195, "direction": "unchanged"}}}`

## Patch Summary

// STAGE5_SUBTASK_BEGIN B4_comb_output: Combinational output block always @(s_rd_pnt or bd
...<snip>...
ck_o_s = re_s; end else begin ack_o_s = 1'b0; end end // STAGE5_SUBTASK_END B4_comb_output

## Lesson

Patch worsened mismatch count or first fail time and was rolled back.

## Reuse Constraints

- Read current RTL/spec evidence before applying a similar patch.
- Do not reuse if affected signals or timing alignment differ.
