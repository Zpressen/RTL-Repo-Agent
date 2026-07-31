---
memory_id: debug_aes_inv_cipher_top_text_out_improved_4
type: repair_outcome
stage: debug
description: "aes_inv_cipher_top: text_out improved; Patch was kept by acceptance judge: The patch is a plausible causal stepping stone: it makes the FSM consume the already"
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
anti_trigger: "Do not reuse when current first divergence, affected signals, or timing alignment differ."
---

## 触发条件

- Module: `aes_inv_cipher_top`
- Signal: `text_out`
- Effect: `improved`
- First divergence: `{"signal": "text_out", "time": 195, "ref": "01101111011011110110111101101111011011110110111101101111011011110110111101101111011011110110111101101111011011110110111101101111", "dut": "11000111110011011001101001101011001000101000110110101000100110100110010100010001100110001111011100000110000010000111110111111011", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`

## 不适用条件

- Do not reuse if affected signals, timing alignment, or spec intent differ.
- Do not reuse without reading current RTL/spec evidence.

## 补丁模式

always @(posedge clk) begin key_expand_kld <= 1'b0; case (fsm_state) FSM_IDLE: begin state
...<snip>...
matrix <= next_state_comb; dcnt         <= 4'd0; fsm_state    <= FSM_IDLE; end endcase end

## 验证特征

- Before mismatch count: `106`
- After mismatch count: `109`
- Metric delta: `{"total_samples_mismatch": null, "per_signal": {"done": {"before": 4, "after": 3, "first_time_before": 355, "first_time_after": 665, "direction": "improved"}, "text_out": {"before": 102, "after": 106, "first_time_before": 245, "first_time_after": 195, "direction": "regressed"}}}`

## 复用约束

Patch was kept by acceptance judge: The patch is a plausible causal stepping stone: it makes the FSM consume the already-captured half-cycle requests and materially improves the real DUT done output, reducing mismatches from 4 to 3 and delaying its first failure from 355 to 665. Although text_out regresses from 102 mismatches at 245 to 106 at 195, the new trace shows the controller progressing through key expansion with a populated round_key_buffer instead of remaining blocked in IDLE, exposing the next upstream sequencing/value defect rather than masking the original bug.

## Problem

`aes_inv_cipher_top` showed a debug failure around `text_out`.

## Evidence

- Effect: `improved`
- Before mismatch count: `106`
- After mismatch count: `109`
- First divergence: `{"signal": "text_out", "time": 195, "ref": "01101111011011110110111101101111011011110110111101101111011011110110111101101111011011110110111101101111011011110110111101101111", "dut": "11000111110011011001101001101011001000101000110110101000100110100110010100010001100110001111011100000110000010000111110111111011", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`
- Trace root failure: `{"signal": "text_out", "time": 195, "ref": "01101111011011110110111101101111011011110110111101101111011011110110111101101111011011110110111101101111011011110110111101101111", "dut": "11000111110011011001101001101011001000101000110110101000100110100110010100010001100110001111011100000110000010000111110111111011", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`
- Metric delta: `{"total_samples_mismatch": null, "per_signal": {"done": {"before": 4, "after": 3, "first_time_before": 355, "first_time_after": 665, "direction": "improved"}, "text_out": {"before": 102, "after": 106, "first_time_before": 245, "first_time_after": 195, "direction": "regressed"}}}`

## Patch Summary

always @(posedge clk) begin key_expand_kld <= 1'b0; case (fsm_state) FSM_IDLE: begin state
...<snip>...
matrix <= next_state_comb; dcnt         <= 4'd0; fsm_state    <= FSM_IDLE; end endcase end

## Lesson

Patch was kept by acceptance judge: The patch is a plausible causal stepping stone: it makes the FSM consume the already-captured half-cycle requests and materially improves the real DUT done output, reducing mismatches from 4 to 3 and delaying its first failure from 355 to 665. Although text_out regresses from 102 mismatches at 245 to 106 at 195, the new trace shows the controller progressing through key expansion with a populated round_key_buffer instead of remaining blocked in IDLE, exposing the next upstream sequencing/value defect rather than masking the original bug.

## Reuse Constraints

- Read current RTL/spec evidence before applying a similar patch.
- Do not reuse if affected signals or timing alignment differ.
