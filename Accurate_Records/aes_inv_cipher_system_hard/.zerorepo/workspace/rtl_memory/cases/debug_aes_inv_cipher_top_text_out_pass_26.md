---
memory_id: debug_aes_inv_cipher_top_text_out_pass_26
type: repair_outcome
stage: debug
description: "aes_inv_cipher_top: text_out passed; Patch fixed all observed mismatches."
module: aes_inv_cipher_top
module_family: aes
signals:
  - text_out
failure_type: timing_bug
alignment: wrong_value
outcome: pass
confidence: 0.9
verified_by:
  - lint
  - module_sim
  - trace
source_artifacts:
  - debug_system/aes_inv_cipher_top/trace_report.json
  - repo_react/aes_inv_cipher_top/patch_journal.jsonl
trigger_signals:
  - text_out
trigger_failure_type: timing_bug
trigger_alignment: wrong_value
risk_signals: []
patch_pattern: "(bg_key_old_valid && (((fsm_state == FSM_STANDARD_ROUND) || (fsm_state == FSM_FINAL_ROUND)\n...<snip>...\n == FSM_IDLE) && idle_rk10)) && (round_key_index == bg_key_old_index)) ? bg_"
anti_trigger: "Do not reuse when current first divergence, affected signals, or timing alignment differ."
---

## 触发条件

- Module: `aes_inv_cipher_top`
- Signal: `text_out`
- Effect: `passed`
- First divergence: `{"signal": "text_out", "time": 1055, "ref": "11111011000001100111001001100101111111011101100111000100111001001100101111101100110010111001101101001111110011000110100110000100", "dut": "00111110000111010101101010010010111110100011111101111110100010001011101000111001101110111001010110001110001100001001101001100111", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`

## 不适用条件

- Do not reuse if affected signals, timing alignment, or spec intent differ.
- Do not reuse without reading current RTL/spec evidence.

## 补丁模式

(bg_key_old_valid && (((fsm_state == FSM_STANDARD_ROUND) || (fsm_state == FSM_FINAL_ROUND)
...<snip>...
 == FSM_IDLE) && idle_rk10)) && (round_key_index == bg_key_old_index)) ? bg_key_old_data :

## 验证特征

- Before mismatch count: `3`
- After mismatch count: `0`
- Metric delta: `{"total_samples_mismatch": null, "per_signal": {"text_out": {"before": 3, "after": 0, "first_time_before": 1055, "first_time_after": null, "direction": "improved"}}}`

## 复用约束

Patch fixed all observed mismatches.

## Problem

`aes_inv_cipher_top` showed a debug failure around `text_out`.

## Evidence

- Effect: `passed`
- Before mismatch count: `3`
- After mismatch count: `0`
- First divergence: `{"signal": "text_out", "time": 1055, "ref": "11111011000001100111001001100101111111011101100111000100111001001100101111101100110010111001101101001111110011000110100110000100", "dut": "00111110000111010101101010010010111110100011111101111110100010001011101000111001101110111001010110001110001100001001101001100111", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`
- Trace root failure: `{"signal": "text_out", "time": 1055, "ref": "11111011000001100111001001100101111111011101100111000100111001001100101111101100110010111001101101001111110011000110100110000100", "dut": "00111110000111010101101010010010111110100011111101111110100010001011101000111001101110111001010110001110001100001001101001100111", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`
- Metric delta: `{"total_samples_mismatch": null, "per_signal": {"text_out": {"before": 3, "after": 0, "first_time_before": 1055, "first_time_after": null, "direction": "improved"}}}`

## Patch Summary

(bg_key_old_valid && (((fsm_state == FSM_STANDARD_ROUND) || (fsm_state == FSM_FINAL_ROUND)
...<snip>...
 == FSM_IDLE) && idle_rk10)) && (round_key_index == bg_key_old_index)) ? bg_key_old_data :

## Lesson

Patch fixed all observed mismatches.

## Reuse Constraints

- Read current RTL/spec evidence before applying a similar patch.
- Do not reuse if affected signals or timing alignment differ.
