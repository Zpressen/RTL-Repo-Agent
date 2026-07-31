---
memory_id: debug_aes_inv_cipher_top_text_out_improved_20
type: repair_outcome
stage: debug
description: "aes_inv_cipher_top: text_out improved; Patch was kept by acceptance judge: The patch is a plausible and spec-backed stepping stone: IDLE must accept ld, the fi"
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
patch_pattern: "FSM_IDLE: begin state_matrix <= after_mix; idle_rk10    <= 1'b1; if (kld_latched) begin in\n...<snip>...\n state_matrix <= text_in; dcnt         <= 4'd0; fsm_state    <= FSM_INITIAL_"
anti_trigger: "Do not reuse when current first divergence, affected signals, or timing alignment differ."
---

## 触发条件

- Module: `aes_inv_cipher_top`
- Signal: `text_out`
- Effect: `improved`
- First divergence: `{"signal": "text_out", "time": 865, "ref": "10100111001111100100011001110100011001110000100100111001100001001000101010010111100111011001000111111000111001001011100000011111", "dut": "10100011111011100000100010000100100000101011001111001010010010100011110111110001010010010001100111111100101110011000000001001111", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`

## 不适用条件

- Do not reuse if affected signals, timing alignment, or spec intent differ.
- Do not reuse without reading current RTL/spec evidence.

## 补丁模式

FSM_IDLE: begin state_matrix <= after_mix; idle_rk10    <= 1'b1; if (kld_latched) begin in
...<snip>...
 state_matrix <= text_in; dcnt         <= 4'd0; fsm_state    <= FSM_INITIAL_ROUND; end end

## 验证特征

- Before mismatch count: `32`
- After mismatch count: `40`
- Metric delta: `{"total_samples_mismatch": null, "per_signal": {"done": {"before": 1, "after": 0, "first_time_before": 1015, "first_time_after": null, "direction": "improved"}, "text_out": {"before": 31, "after": 40, "first_time_before": 775, "first_time_after": 865, "direction": "regressed"}}}`

## 复用约束

Patch was kept by acceptance judge: The patch is a plausible and spec-backed stepping stone: IDLE must accept ld, the first real text_out failure moves substantially later from t775 to t865, all samples through t855 now match, and the done mismatch is eliminated. The text_out count rises from 31 to 40, but that aggregate regression is outweighed by fixing the original failure and exposing a later wrong-value issue in the launched round datapath.

## Problem

`aes_inv_cipher_top` showed a debug failure around `text_out`.

## Evidence

- Effect: `improved`
- Before mismatch count: `32`
- After mismatch count: `40`
- First divergence: `{"signal": "text_out", "time": 865, "ref": "10100111001111100100011001110100011001110000100100111001100001001000101010010111100111011001000111111000111001001011100000011111", "dut": "10100011111011100000100010000100100000101011001111001010010010100011110111110001010010010001100111111100101110011000000001001111", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`
- Trace root failure: `{"signal": "text_out", "time": 865, "ref": "10100111001111100100011001110100011001110000100100111001100001001000101010010111100111011001000111111000111001001011100000011111", "dut": "10100011111011100000100010000100100000101011001111001010010010100011110111110001010010010001100111111100101110011000000001001111", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`
- Metric delta: `{"total_samples_mismatch": null, "per_signal": {"done": {"before": 1, "after": 0, "first_time_before": 1015, "first_time_after": null, "direction": "improved"}, "text_out": {"before": 31, "after": 40, "first_time_before": 775, "first_time_after": 865, "direction": "regressed"}}}`

## Patch Summary

FSM_IDLE: begin state_matrix <= after_mix; idle_rk10    <= 1'b1; if (kld_latched) begin in
...<snip>...
 state_matrix <= text_in; dcnt         <= 4'd0; fsm_state    <= FSM_INITIAL_ROUND; end end

## Lesson

Patch was kept by acceptance judge: The patch is a plausible and spec-backed stepping stone: IDLE must accept ld, the first real text_out failure moves substantially later from t775 to t865, all samples through t855 now match, and the done mismatch is eliminated. The text_out count rises from 31 to 40, but that aggregate regression is outweighed by fixing the original failure and exposing a later wrong-value issue in the launched round datapath.

## Reuse Constraints

- Read current RTL/spec evidence before applying a similar patch.
- Do not reuse if affected signals or timing alignment differ.
