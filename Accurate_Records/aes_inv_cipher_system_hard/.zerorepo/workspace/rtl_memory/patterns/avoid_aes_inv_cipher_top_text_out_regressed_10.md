---
memory_id: avoid_aes_inv_cipher_top_text_out_regressed_10
type: negative_direction
stage: debug
description: "aes_inv_cipher_top: text_out regressed; Patch worsened mismatch count or first fail time and was rolled back."
module: aes_inv_cipher_top
module_family: aes
signals:
  - dcnt
  - fsm_state
  - idle_rk10
  - key_valid
  - state_matrix
  - text_out
failure_type: timing_bug
alignment: wrong_value
outcome: regressed
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
  - idle_rk10
  - key_valid
  - state_matrix
  - text_out
trigger_failure_type: timing_bug
trigger_alignment: wrong_value
risk_signals:
  - dcnt
  - fsm_state
  - idle_rk10
  - key_valid
  - state_matrix
  - text_out
patch_pattern: "reg          idle_rk10        = 1'b0; reg          key_valid        = 1'b0;; (((fsm_state == FSM_KEY_LOAD) || (fsm_state == FSM_KEY_EXPANSION)) && key_valid) ? round_k\n...<snip>..."
anti_trigger: "Avoid this direction unless new evidence distinguishes the current failure."
---

## 触发条件

- Module: `aes_inv_cipher_top`
- Signal: `text_out`
- Effect: `regressed`
- First divergence: `{"signal": "text_out", "time": 435, "ref": "11011110100010010000010110100001111100010000001111011111100100110011010011011010010010010100000000101100101001001000000100100011", "dut": "11001101100110000001100011011110000100101001011110010101100001001100011111011101111011101100101101100001100011111011000111100110", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`

## 不适用条件

- Do not reuse if affected signals, timing alignment, or spec intent differ.
- Do not reuse without reading current RTL/spec evidence.

## 补丁模式

reg          idle_rk10        = 1'b0; reg          key_valid        = 1'b0;; (((fsm_state == FSM_KEY_LOAD) || (fsm_state == FSM_KEY_EXPANSION)) && key_valid) ? round_k
...<snip>...
te == FSM_KEY_STORED) || (fsm_state == FSM_INITIAL_ROUND)) ? round_key_buffer[1407:1280] :; FSM_KEY_LOAD: begin state_matrix <= key_valid ? after_mix : after_sub; dcnt          <= 4'
...<snip>...
EXPANSION; end FSM_KEY_EXPANSION: begin state_matrix <= key_valid ? after_mix : after_sub;; if (dcnt == 4'd10) begin dcnt      <= 4'd0; key_valid <= 1'b1; fsm_state <= FSM_KEY_STORED;; FSM_KEY_LOAD, FSM_KEY_EXPANSION: text_out <= key_valid ? after_add : after_sub;

## 验证特征

- Before mismatch count: `80`
- After mismatch count: `106`
- Metric delta: `{"total_samples_mismatch": null, "per_signal": {"done": {"before": 3, "after": 4, "first_time_before": 665, "first_time_after": 355, "direction": "regressed"}, "text_out": {"before": 77, "after": 102, "first_time_before": 435, "first_time_after": 245, "direction": "regressed"}}}`

## 复用约束

Patch worsened mismatch count or first fail time and was rolled back.

## Problem

`aes_inv_cipher_top` showed a debug failure around `text_out`.

## Evidence

- Effect: `regressed`
- Before mismatch count: `80`
- After mismatch count: `106`
- First divergence: `{"signal": "text_out", "time": 435, "ref": "11011110100010010000010110100001111100010000001111011111100100110011010011011010010010010100000000101100101001001000000100100011", "dut": "11001101100110000001100011011110000100101001011110010101100001001100011111011101111011101100101101100001100011111011000111100110", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`
- Trace root failure: `{"signal": "text_out", "time": 435, "ref": "11011110100010010000010110100001111100010000001111011111100100110011010011011010010010010100000000101100101001001000000100100011", "dut": "11001101100110000001100011011110000100101001011110010101100001001100011111011101111011101100101101100001100011111011000111100110", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`
- Metric delta: `{"total_samples_mismatch": null, "per_signal": {"done": {"before": 3, "after": 4, "first_time_before": 665, "first_time_after": 355, "direction": "regressed"}, "text_out": {"before": 77, "after": 102, "first_time_before": 435, "first_time_after": 245, "direction": "regressed"}}}`

## Patch Summary

reg          idle_rk10        = 1'b0; reg          key_valid        = 1'b0;; (((fsm_state == FSM_KEY_LOAD) || (fsm_state == FSM_KEY_EXPANSION)) && key_valid) ? round_k
...<snip>...
te == FSM_KEY_STORED) || (fsm_state == FSM_INITIAL_ROUND)) ? round_key_buffer[1407:1280] :; FSM_KEY_LOAD: begin state_matrix <= key_valid ? after_mix : after_sub; dcnt          <= 4'
...<snip>...
EXPANSION; end FSM_KEY_EXPANSION: begin state_matrix <= key_valid ? after_mix : after_sub;; if (dcnt == 4'd10) begin dcnt      <= 4'd0; key_valid <= 1'b1; fsm_state <= FSM_KEY_STORED;; FSM_KEY_LOAD, FSM_KEY_EXPANSION: text_out <= key_valid ? after_add : after_sub;

## Lesson

Patch worsened mismatch count or first fail time and was rolled back.

## Reuse Constraints

- Read current RTL/spec evidence before applying a similar patch.
- Do not reuse if affected signals or timing alignment differ.
