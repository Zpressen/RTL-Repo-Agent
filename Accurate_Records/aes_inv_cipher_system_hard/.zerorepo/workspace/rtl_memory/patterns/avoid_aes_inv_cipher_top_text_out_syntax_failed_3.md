---
memory_id: avoid_aes_inv_cipher_top_text_out_syntax_failed_3
type: negative_direction
stage: debug
description: "aes_inv_cipher_top: text_out syntax_failed; Patch failed lint and was rolled back; fix syntax before retrying this idea."
module: aes_inv_cipher_top
module_family: aes
signals:
  - dcnt
  - fsm_state
  - initial_key_reg
  - key_expand_kld
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
  - dcnt
  - fsm_state
  - initial_key_reg
  - key_expand_kld
  - state_matrix
  - text_out
trigger_failure_type: timing_bug
trigger_alignment: wrong_value
risk_signals:
  - dcnt
  - fsm_state
  - initial_key_reg
  - key_expand_kld
  - state_matrix
  - text_out
patch_pattern: "FSM_KEY_STORED: begin state_matrix <= after_sub; if (kld_latched) begin initial_key_reg <=\n...<snip>...\nround_key_buffer[1407:1280]; dcnt         <= 4'd1; fsm_state    <= FSM_STAND"
anti_trigger: "Avoid this direction unless new evidence distinguishes the current failure."
---

## 触发条件

- Module: `aes_inv_cipher_top`
- Signal: `text_out`
- Effect: `syntax_failed`
- First divergence: `{"signal": "text_out", "time": 255, "ref": "00110110001011110001001101000100100100100101010011010001101111000000111011011110100011000101001110110000010000111010110101011110", "dut": "11001010110011100000101010111000001010011001000111101000001101000110110110011011001101110111100100100011001100101111011101011111", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`

## 不适用条件

- Do not reuse if affected signals, timing alignment, or spec intent differ.
- Do not reuse without reading current RTL/spec evidence.

## 补丁模式

FSM_KEY_STORED: begin state_matrix <= after_sub; if (kld_latched) begin initial_key_reg <=
...<snip>...
round_key_buffer[1407:1280]; dcnt         <= 4'd1; fsm_state    <= FSM_STANDARD_ROUND; end; FSM_INITIAL_ROUND: text_out <= state_matrix ^ round_key_buffer[1407:1280];

## 验证特征

- Before mismatch count: `88`
- After mismatch count: `None`
- Metric delta: `{"total_samples_mismatch": null, "per_signal": {"done": {"before": 3, "after": 0, "first_time_before": 665, "first_time_after": null, "direction": "improved"}, "text_out": {"before": 85, "after": 0, "first_time_before": 255, "first_time_after": null, "direction": "improved"}}}`

## 复用约束

Patch failed lint and was rolled back; fix syntax before retrying this idea.

## Problem

`aes_inv_cipher_top` showed a debug failure around `text_out`.

## Evidence

- Effect: `syntax_failed`
- Before mismatch count: `88`
- After mismatch count: `None`
- First divergence: `{"signal": "text_out", "time": 255, "ref": "00110110001011110001001101000100100100100101010011010001101111000000111011011110100011000101001110110000010000111010110101011110", "dut": "11001010110011100000101010111000001010011001000111101000001101000110110110011011001101110111100100100011001100101111011101011111", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`
- Trace root failure: `{"signal": "text_out", "time": 255, "ref": "00110110001011110001001101000100100100100101010011010001101111000000111011011110100011000101001110110000010000111010110101011110", "dut": "11001010110011100000101010111000001010011001000111101000001101000110110110011011001101110111100100100011001100101111011101011111", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`
- Metric delta: `{"total_samples_mismatch": null, "per_signal": {"done": {"before": 3, "after": 0, "first_time_before": 665, "first_time_after": null, "direction": "improved"}, "text_out": {"before": 85, "after": 0, "first_time_before": 255, "first_time_after": null, "direction": "improved"}}}`

## Patch Summary

FSM_KEY_STORED: begin state_matrix <= after_sub; if (kld_latched) begin initial_key_reg <=
...<snip>...
round_key_buffer[1407:1280]; dcnt         <= 4'd1; fsm_state    <= FSM_STANDARD_ROUND; end; FSM_INITIAL_ROUND: text_out <= state_matrix ^ round_key_buffer[1407:1280];

## Lesson

Patch failed lint and was rolled back; fix syntax before retrying this idea.

## Reuse Constraints

- Read current RTL/spec evidence before applying a similar patch.
- Do not reuse if affected signals or timing alignment differ.
