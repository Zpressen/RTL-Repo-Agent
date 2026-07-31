---
memory_id: avoid_aes_inv_cipher_top_text_out_regressed_19
type: negative_direction
stage: debug
description: "aes_inv_cipher_top: text_out regressed; Patch worsened mismatch count or first fail time and was rolled back."
module: aes_inv_cipher_top
module_family: aes
signals:
  - dcnt
  - fsm_state
  - idle_rk10
  - initial_key_reg
  - key_expand_kld
  - launch_state
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
  - initial_key_reg
  - key_expand_kld
  - launch_state
  - state_matrix
  - text_out
trigger_failure_type: timing_bug
trigger_alignment: wrong_value
risk_signals:
  - dcnt
  - fsm_state
  - idle_rk10
  - initial_key_reg
  - key_expand_kld
  - launch_state
  - state_matrix
patch_pattern: "if (kld_latched) begin initial_key_reg <= key; key_expand_kld  <= 1'b1; dcnt            <=\n...<snip>...\nmix; state_matrix <= text_in; dcnt         <= 4'd0; fsm_state    <= FSM_INIT"
anti_trigger: "Avoid this direction unless new evidence distinguishes the current failure."
---

## 触发条件

- Module: `aes_inv_cipher_top`
- Signal: `text_out`
- Effect: `regressed`
- First divergence: `{"signal": "text_out", "time": 775, "ref": "00001010100010110000110000101001011110111000110111100101111101011001100010100010000100011010000000011010101001111001111001101010", "dut": "10100010011111110010011000011110001001100101000001010011010110110000000110101111111011001011000011100110001111011000111100110110", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`

## 不适用条件

- Do not reuse if affected signals, timing alignment, or spec intent differ.
- Do not reuse without reading current RTL/spec evidence.

## 补丁模式

if (kld_latched) begin initial_key_reg <= key; key_expand_kld  <= 1'b1; dcnt            <=
...<snip>...
mix; state_matrix <= text_in; dcnt         <= 4'd0; fsm_state    <= FSM_INITIAL_ROUND; end

## 验证特征

- Before mismatch count: `32`
- After mismatch count: `61`
- Metric delta: `{"total_samples_mismatch": null, "per_signal": {"done": {"before": 1, "after": 0, "first_time_before": 1015, "first_time_after": null, "direction": "improved"}, "text_out": {"before": 31, "after": 61, "first_time_before": 775, "first_time_after": 385, "direction": "regressed"}}}`

## 复用约束

Patch worsened mismatch count or first fail time and was rolled back.

## Problem

`aes_inv_cipher_top` showed a debug failure around `text_out`.

## Evidence

- Effect: `regressed`
- Before mismatch count: `32`
- After mismatch count: `61`
- First divergence: `{"signal": "text_out", "time": 775, "ref": "00001010100010110000110000101001011110111000110111100101111101011001100010100010000100011010000000011010101001111001111001101010", "dut": "10100010011111110010011000011110001001100101000001010011010110110000000110101111111011001011000011100110001111011000111100110110", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`
- Trace root failure: `{"signal": "text_out", "time": 775, "ref": "00001010100010110000110000101001011110111000110111100101111101011001100010100010000100011010000000011010101001111001111001101010", "dut": "10100010011111110010011000011110001001100101000001010011010110110000000110101111111011001011000011100110001111011000111100110110", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`
- Metric delta: `{"total_samples_mismatch": null, "per_signal": {"done": {"before": 1, "after": 0, "first_time_before": 1015, "first_time_after": null, "direction": "improved"}, "text_out": {"before": 31, "after": 61, "first_time_before": 775, "first_time_after": 385, "direction": "regressed"}}}`

## Patch Summary

if (kld_latched) begin initial_key_reg <= key; key_expand_kld  <= 1'b1; dcnt            <=
...<snip>...
mix; state_matrix <= text_in; dcnt         <= 4'd0; fsm_state    <= FSM_INITIAL_ROUND; end

## Lesson

Patch worsened mismatch count or first fail time and was rolled back.

## Reuse Constraints

- Read current RTL/spec evidence before applying a similar patch.
- Do not reuse if affected signals or timing alignment differ.
