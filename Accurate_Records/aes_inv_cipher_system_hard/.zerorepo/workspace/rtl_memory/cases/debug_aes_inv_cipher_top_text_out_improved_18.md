---
memory_id: debug_aes_inv_cipher_top_text_out_improved_18
type: repair_outcome
stage: debug
description: "aes_inv_cipher_top: text_out improved; Patch improved mismatch count or first fail time; continue from this direction."
module: aes_inv_cipher_top
module_family: aes
signals:
  - dcnt
  - fsm_state
  - key_expand_kld
  - restart_key_index
  - restart_key_valid
  - restart_state_load
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
  - key_expand_kld
  - restart_key_index
  - restart_key_valid
  - restart_state_load
  - state_matrix
  - text_out
trigger_failure_type: timing_bug
trigger_alignment: wrong_value
risk_signals:
  - dcnt
  - fsm_state
  - key_expand_kld
  - restart_key_index
  - restart_key_valid
  - restart_state_load
  - state_matrix
patch_pattern: "reg          restart_key_valid = 1'b0; reg [3:0]    restart_key_index = 4'd0; reg          restart_state_load = 1'b0;; always @(posedge clk) begin key_expand_kld    <= 1'b0; restar"
anti_trigger: "Do not reuse when current first divergence, affected signals, or timing alignment differ."
---

## 触发条件

- Module: `aes_inv_cipher_top`
- Signal: `text_out`
- Effect: `improved`
- First divergence: `{"signal": "text_out", "time": 775, "ref": "00001010100010110000110000101001011110111000110111100101111101011001100010100010000100011010000000011010101001111001111001101010", "dut": "10100010011111110010011000011110001001100101000001010011010110110000000110101111111011001011000011100110001111011000111100110110", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`

## 不适用条件

- Do not reuse if affected signals, timing alignment, or spec intent differ.
- Do not reuse without reading current RTL/spec evidence.

## 补丁模式

reg          restart_key_valid = 1'b0; reg [3:0]    restart_key_index = 4'd0; reg          restart_state_load = 1'b0;; always @(posedge clk) begin key_expand_kld    <= 1'b0; restart_state_load <= 1'b0;; FSM_STANDARD_ROUND: begin state_matrix <= restart_state_load ? (text_in ^ round_key) : nex
...<snip>...
tate_matrix     <= after_mix; restart_key_valid <= 1'b0; fsm_state        <= FSM_DONE; end

## 验证特征

- Before mismatch count: `66`
- After mismatch count: `32`
- Metric delta: `{"total_samples_mismatch": null, "per_signal": {"done": {"before": 3, "after": 1, "first_time_before": 715, "first_time_after": 1015, "direction": "improved"}, "text_out": {"before": 63, "after": 31, "first_time_before": 635, "first_time_after": 775, "direction": "improved"}}}`

## 复用约束

Patch improved mismatch count or first fail time; continue from this direction.

## Problem

`aes_inv_cipher_top` showed a debug failure around `text_out`.

## Evidence

- Effect: `improved`
- Before mismatch count: `66`
- After mismatch count: `32`
- First divergence: `{"signal": "text_out", "time": 775, "ref": "00001010100010110000110000101001011110111000110111100101111101011001100010100010000100011010000000011010101001111001111001101010", "dut": "10100010011111110010011000011110001001100101000001010011010110110000000110101111111011001011000011100110001111011000111100110110", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`
- Trace root failure: `{"signal": "text_out", "time": 775, "ref": "00001010100010110000110000101001011110111000110111100101111101011001100010100010000100011010000000011010101001111001111001101010", "dut": "10100010011111110010011000011110001001100101000001010011010110110000000110101111111011001011000011100110001111011000111100110110", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`
- Metric delta: `{"total_samples_mismatch": null, "per_signal": {"done": {"before": 3, "after": 1, "first_time_before": 715, "first_time_after": 1015, "direction": "improved"}, "text_out": {"before": 63, "after": 31, "first_time_before": 635, "first_time_after": 775, "direction": "improved"}}}`

## Patch Summary

reg          restart_key_valid = 1'b0; reg [3:0]    restart_key_index = 4'd0; reg          restart_state_load = 1'b0;; always @(posedge clk) begin key_expand_kld    <= 1'b0; restart_state_load <= 1'b0;; FSM_STANDARD_ROUND: begin state_matrix <= restart_state_load ? (text_in ^ round_key) : nex
...<snip>...
tate_matrix     <= after_mix; restart_key_valid <= 1'b0; fsm_state        <= FSM_DONE; end

## Lesson

Patch improved mismatch count or first fail time; continue from this direction.

## Reuse Constraints

- Read current RTL/spec evidence before applying a similar patch.
- Do not reuse if affected signals or timing alignment differ.
