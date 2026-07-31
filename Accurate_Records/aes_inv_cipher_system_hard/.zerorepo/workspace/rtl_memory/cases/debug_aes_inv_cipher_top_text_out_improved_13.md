---
memory_id: debug_aes_inv_cipher_top_text_out_improved_13
type: repair_outcome
stage: debug
description: "aes_inv_cipher_top: text_out improved; Patch improved mismatch count or first fail time; continue from this direction."
module: aes_inv_cipher_top
module_family: aes
signals:
  - dcnt
  - fsm_state
  - state_matrix
  - text_out
failure_type: timing_bug
alignment: wrong_value
outcome: improved
confidence: 0.72
verified_by:
  - lint
  - module_sim
  - trace
source_artifacts:
  - debug_system/aes_inv_cipher_top/trace_report.json
  - repo_react/aes_inv_cipher_top/patch_journal.jsonl
trigger_signals:
  - dcnt
  - fsm_state
  - state_matrix
  - text_out
trigger_failure_type: timing_bug
trigger_alignment: wrong_value
risk_signals:
  - dcnt
  - fsm_state
  - state_matrix
  - text_out
patch_pattern: "FSM_KEY_LOAD: begin state_matrix <= schedule_valid ? after_mix : after_sub; dcnt          <= 4'd0; fsm_state     <= FSM_KEY_EXPANSION; end; FSM_KEY_LOAD: text_out <= schedule_valid"
anti_trigger: "Do not reuse when current first divergence, affected signals, or timing alignment differ."
---

## 触发条件

- Module: `aes_inv_cipher_top`
- Signal: `text_out`
- Effect: `improved`
- First divergence: `{"signal": "text_out", "time": 445, "ref": "01010111001110001000100001001011100100001100011011000001111000001110001001100110001011001000010011000101000101101111011101110000", "dut": "01000100001010011001010100110100011100110101001010001011111101110001000101100001100010110000111110001000001111011100011110110101", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`

## 不适用条件

- Do not reuse if affected signals, timing alignment, or spec intent differ.
- Do not reuse without reading current RTL/spec evidence.

## 补丁模式

FSM_KEY_LOAD: begin state_matrix <= schedule_valid ? after_mix : after_sub; dcnt          <= 4'd0; fsm_state     <= FSM_KEY_EXPANSION; end; FSM_KEY_LOAD: text_out <= schedule_valid ? after_add : after_sub; FSM_KEY_EXPANSION: text_out <= after_sub;

## 验证特征

- Before mismatch count: `80`
- After mismatch count: `79`
- Metric delta: `{"total_samples_mismatch": null, "per_signal": {"done": {"before": 3, "after": 3, "first_time_before": 665, "first_time_after": 665, "direction": "unchanged"}, "text_out": {"before": 77, "after": 76, "first_time_before": 435, "first_time_after": 445, "direction": "improved"}}}`

## 复用约束

Patch improved mismatch count or first fail time; continue from this direction.

## Problem

`aes_inv_cipher_top` showed a debug failure around `text_out`.

## Evidence

- Effect: `improved`
- Before mismatch count: `80`
- After mismatch count: `79`
- First divergence: `{"signal": "text_out", "time": 445, "ref": "01010111001110001000100001001011100100001100011011000001111000001110001001100110001011001000010011000101000101101111011101110000", "dut": "01000100001010011001010100110100011100110101001010001011111101110001000101100001100010110000111110001000001111011100011110110101", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`
- Trace root failure: `{"signal": "text_out", "time": 445, "ref": "01010111001110001000100001001011100100001100011011000001111000001110001001100110001011001000010011000101000101101111011101110000", "dut": "01000100001010011001010100110100011100110101001010001011111101110001000101100001100010110000111110001000001111011100011110110101", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`
- Metric delta: `{"total_samples_mismatch": null, "per_signal": {"done": {"before": 3, "after": 3, "first_time_before": 665, "first_time_after": 665, "direction": "unchanged"}, "text_out": {"before": 77, "after": 76, "first_time_before": 435, "first_time_after": 445, "direction": "improved"}}}`

## Patch Summary

FSM_KEY_LOAD: begin state_matrix <= schedule_valid ? after_mix : after_sub; dcnt          <= 4'd0; fsm_state     <= FSM_KEY_EXPANSION; end; FSM_KEY_LOAD: text_out <= schedule_valid ? after_add : after_sub; FSM_KEY_EXPANSION: text_out <= after_sub;

## Lesson

Patch improved mismatch count or first fail time; continue from this direction.

## Reuse Constraints

- Read current RTL/spec evidence before applying a similar patch.
- Do not reuse if affected signals or timing alignment differ.
