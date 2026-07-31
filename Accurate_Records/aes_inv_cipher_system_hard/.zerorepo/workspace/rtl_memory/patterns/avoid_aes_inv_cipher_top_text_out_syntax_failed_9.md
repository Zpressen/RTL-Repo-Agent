---
memory_id: avoid_aes_inv_cipher_top_text_out_syntax_failed_9
type: negative_direction
stage: debug
description: "aes_inv_cipher_top: text_out syntax_failed; Patch failed lint and was rolled back; fix syntax before retrying this idea."
module: aes_inv_cipher_top
module_family: aes
signals:
  - round_key
  - state_matrix
  - text_out
failure_type: timing_bug
alignment: wrong_value
outcome: syntax_failed
confidence: 0.68
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
patch_pattern: "(fsm_state == FSM_DONE) ? 128'd0 : ((fsm_state == FSM_KEY_STORED) || (fsm_state == FSM_INITIAL_ROUND)) ? round_key_buffer[1407:1280] :; state_matrix <= after_mix;"
anti_trigger: "Avoid this direction unless new evidence distinguishes the current failure."
---

## 触发条件

- Module: `aes_inv_cipher_top`
- Signal: `text_out`
- Effect: `syntax_failed`
- First divergence: `{"signal": "text_out", "time": 365, "ref": "01100010011001100101001011111001100110010111110110000110111011011001010011111110100101111110001111010011000000100010011111001001", "dut": "01010010110010000110000000000001100000101110011010011111111110011001111111100100100111100111011000101011111101001101110101101001", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`

## 不适用条件

- Do not reuse if affected signals, timing alignment, or spec intent differ.
- Do not reuse without reading current RTL/spec evidence.

## 补丁模式

(fsm_state == FSM_DONE) ? 128'd0 : ((fsm_state == FSM_KEY_STORED) || (fsm_state == FSM_INITIAL_ROUND)) ? round_key_buffer[1407:1280] :; state_matrix <= after_mix;

## 验证特征

- Before mismatch count: `87`
- After mismatch count: `None`
- Metric delta: `{"total_samples_mismatch": null, "per_signal": {"done": {"before": 3, "after": 0, "first_time_before": 665, "first_time_after": null, "direction": "improved"}, "text_out": {"before": 84, "after": 0, "first_time_before": 365, "first_time_after": null, "direction": "improved"}}}`

## 复用约束

Patch failed lint and was rolled back; fix syntax before retrying this idea.

## Problem

`aes_inv_cipher_top` showed a debug failure around `text_out`.

## Evidence

- Effect: `syntax_failed`
- Before mismatch count: `87`
- After mismatch count: `None`
- First divergence: `{"signal": "text_out", "time": 365, "ref": "01100010011001100101001011111001100110010111110110000110111011011001010011111110100101111110001111010011000000100010011111001001", "dut": "01010010110010000110000000000001100000101110011010011111111110011001111111100100100111100111011000101011111101001101110101101001", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`
- Trace root failure: `{"signal": "text_out", "time": 365, "ref": "01100010011001100101001011111001100110010111110110000110111011011001010011111110100101111110001111010011000000100010011111001001", "dut": "01010010110010000110000000000001100000101110011010011111111110011001111111100100100111100111011000101011111101001101110101101001", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`
- Metric delta: `{"total_samples_mismatch": null, "per_signal": {"done": {"before": 3, "after": 0, "first_time_before": 665, "first_time_after": null, "direction": "improved"}, "text_out": {"before": 84, "after": 0, "first_time_before": 365, "first_time_after": null, "direction": "improved"}}}`

## Patch Summary

(fsm_state == FSM_DONE) ? 128'd0 : ((fsm_state == FSM_KEY_STORED) || (fsm_state == FSM_INITIAL_ROUND)) ? round_key_buffer[1407:1280] :; state_matrix <= after_mix;

## Lesson

Patch failed lint and was rolled back; fix syntax before retrying this idea.

## Reuse Constraints

- Read current RTL/spec evidence before applying a similar patch.
- Do not reuse if affected signals or timing alignment differ.
