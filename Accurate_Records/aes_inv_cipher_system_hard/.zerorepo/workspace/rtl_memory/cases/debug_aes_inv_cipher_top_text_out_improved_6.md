---
memory_id: debug_aes_inv_cipher_top_text_out_improved_6
type: repair_outcome
stage: debug
description: "aes_inv_cipher_top: text_out improved; Patch improved mismatch count or first fail time; continue from this direction."
module: aes_inv_cipher_top
module_family: aes
signals:
  - round_key
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
  - round_key
  - state_matrix
  - text_out
trigger_failure_type: timing_bug
trigger_alignment: wrong_value
risk_signals:
  - round_key
  - state_matrix
patch_pattern: "assign round_key = (fsm_state == FSM_DONE) ? 128'd0 :; state_matrix <= after_mix;"
anti_trigger: "Do not reuse when current first divergence, affected signals, or timing alignment differ."
---

## 触发条件

- Module: `aes_inv_cipher_top`
- Signal: `text_out`
- Effect: `improved`
- First divergence: `{"signal": "text_out", "time": 385, "ref": "00100110111010101100011101110010000100010010000110110101010111111010111101001110001011001100010101010011100001001111111001000101", "dut": "01110001101011110000010101100111001101000001100001010100111111010100001110111110001111110101000100100111100000101100100110110001", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`

## 不适用条件

- Do not reuse if affected signals, timing alignment, or spec intent differ.
- Do not reuse without reading current RTL/spec evidence.

## 补丁模式

assign round_key = (fsm_state == FSM_DONE) ? 128'd0 :; state_matrix <= after_mix;

## 验证特征

- Before mismatch count: `87`
- After mismatch count: `85`
- Metric delta: `{"total_samples_mismatch": null, "per_signal": {"done": {"before": 3, "after": 3, "first_time_before": 665, "first_time_after": 665, "direction": "unchanged"}, "text_out": {"before": 84, "after": 82, "first_time_before": 365, "first_time_after": 385, "direction": "improved"}}}`

## 复用约束

Patch improved mismatch count or first fail time; continue from this direction.

## Problem

`aes_inv_cipher_top` showed a debug failure around `text_out`.

## Evidence

- Effect: `improved`
- Before mismatch count: `87`
- After mismatch count: `85`
- First divergence: `{"signal": "text_out", "time": 385, "ref": "00100110111010101100011101110010000100010010000110110101010111111010111101001110001011001100010101010011100001001111111001000101", "dut": "01110001101011110000010101100111001101000001100001010100111111010100001110111110001111110101000100100111100000101100100110110001", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`
- Trace root failure: `{"signal": "text_out", "time": 385, "ref": "00100110111010101100011101110010000100010010000110110101010111111010111101001110001011001100010101010011100001001111111001000101", "dut": "01110001101011110000010101100111001101000001100001010100111111010100001110111110001111110101000100100111100000101100100110110001", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`
- Metric delta: `{"total_samples_mismatch": null, "per_signal": {"done": {"before": 3, "after": 3, "first_time_before": 665, "first_time_after": 665, "direction": "unchanged"}, "text_out": {"before": 84, "after": 82, "first_time_before": 365, "first_time_after": 385, "direction": "improved"}}}`

## Patch Summary

assign round_key = (fsm_state == FSM_DONE) ? 128'd0 :; state_matrix <= after_mix;

## Lesson

Patch improved mismatch count or first fail time; continue from this direction.

## Reuse Constraints

- Read current RTL/spec evidence before applying a similar patch.
- Do not reuse if affected signals or timing alignment differ.
