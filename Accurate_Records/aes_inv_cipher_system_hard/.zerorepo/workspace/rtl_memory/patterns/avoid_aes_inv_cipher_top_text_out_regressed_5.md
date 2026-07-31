---
memory_id: avoid_aes_inv_cipher_top_text_out_regressed_5
type: negative_direction
stage: debug
description: "aes_inv_cipher_top: text_out regressed; Patch worsened mismatch count or first fail time and was rolled back."
module: aes_inv_cipher_top
module_family: aes
signals:
  - dcnt
  - fsm_state
  - initial_key_reg
  - key_expand_kld
  - round_key_buffer
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
  - initial_key_reg
  - key_expand_kld
  - round_key_buffer
  - state_matrix
  - text_out
trigger_failure_type: timing_bug
trigger_alignment: wrong_value
risk_signals:
  - dcnt
  - fsm_state
  - initial_key_reg
  - key_expand_kld
  - round_key_buffer
  - state_matrix
patch_pattern: "always @(posedge clk) begin key_expand_kld <= 1'b0; case (fsm_state) FSM_IDLE: begin state\n...<snip>...\nmatrix <= next_state_comb; dcnt         <= 4'd0; fsm_state    <= FSM_IDLE; e"
anti_trigger: "Avoid this direction unless new evidence distinguishes the current failure."
---

## 触发条件

- Module: `aes_inv_cipher_top`
- Signal: `text_out`
- Effect: `regressed`
- First divergence: `{"signal": "text_out", "time": 195, "ref": "01101111011011110110111101101111011011110110111101101111011011110110111101101111011011110110111101101111011011110110111101101111", "dut": "11000111110011011001101001101011001000101000110110101000100110100110010100010001100110001111011100000110000010000111110111111011", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`

## 不适用条件

- Do not reuse if affected signals, timing alignment, or spec intent differ.
- Do not reuse without reading current RTL/spec evidence.

## 补丁模式

always @(posedge clk) begin key_expand_kld <= 1'b0; case (fsm_state) FSM_IDLE: begin state
...<snip>...
matrix <= next_state_comb; dcnt         <= 4'd0; fsm_state    <= FSM_IDLE; end endcase end

## 验证特征

- Before mismatch count: `109`
- After mismatch count: `126`
- Metric delta: `{"total_samples_mismatch": null, "per_signal": {"done": {"before": 3, "after": 3, "first_time_before": 665, "first_time_after": 665, "direction": "unchanged"}, "text_out": {"before": 106, "after": 123, "first_time_before": 195, "first_time_after": 25, "direction": "regressed"}}}`

## 复用约束

Patch worsened mismatch count or first fail time and was rolled back.

## Problem

`aes_inv_cipher_top` showed a debug failure around `text_out`.

## Evidence

- Effect: `regressed`
- Before mismatch count: `109`
- After mismatch count: `126`
- First divergence: `{"signal": "text_out", "time": 195, "ref": "01101111011011110110111101101111011011110110111101101111011011110110111101101111011011110110111101101111011011110110111101101111", "dut": "11000111110011011001101001101011001000101000110110101000100110100110010100010001100110001111011100000110000010000111110111111011", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`
- Trace root failure: `{"signal": "text_out", "time": 195, "ref": "01101111011011110110111101101111011011110110111101101111011011110110111101101111011011110110111101101111011011110110111101101111", "dut": "11000111110011011001101001101011001000101000110110101000100110100110010100010001100110001111011100000110000010000111110111111011", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`
- Metric delta: `{"total_samples_mismatch": null, "per_signal": {"done": {"before": 3, "after": 3, "first_time_before": 665, "first_time_after": 665, "direction": "unchanged"}, "text_out": {"before": 106, "after": 123, "first_time_before": 195, "first_time_after": 25, "direction": "regressed"}}}`

## Patch Summary

always @(posedge clk) begin key_expand_kld <= 1'b0; case (fsm_state) FSM_IDLE: begin state
...<snip>...
matrix <= next_state_comb; dcnt         <= 4'd0; fsm_state    <= FSM_IDLE; end endcase end

## Lesson

Patch worsened mismatch count or first fail time and was rolled back.

## Reuse Constraints

- Read current RTL/spec evidence before applying a similar patch.
- Do not reuse if affected signals or timing alignment differ.
