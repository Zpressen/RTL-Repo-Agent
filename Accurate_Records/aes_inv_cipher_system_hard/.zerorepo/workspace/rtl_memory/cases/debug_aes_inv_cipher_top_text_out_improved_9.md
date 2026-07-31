---
memory_id: debug_aes_inv_cipher_top_text_out_improved_9
type: repair_outcome
stage: debug
description: "aes_inv_cipher_top: text_out improved; Patch improved mismatch count or first fail time; continue from this direction."
module: aes_inv_cipher_top
module_family: aes
signals:
  - dcnt
  - fsm_state
  - idle_rk10
  - ld_latched
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
  - ld_latched
  - state_matrix
  - text_out
trigger_failure_type: timing_bug
trigger_alignment: wrong_value
risk_signals:
  - dcnt
  - fsm_state
  - idle_rk10
  - ld_latched
  - state_matrix
  - text_out
patch_pattern: "reg          ld_latched       = 1'b0; reg          idle_rk10        = 1'b0;; ((fsm_state == FSM_IDLE) && idle_rk10) ? round_key_buffer[1407:1280] : ((fsm_state == FSM_KEY_STORED) |"
anti_trigger: "Do not reuse when current first divergence, affected signals, or timing alignment differ."
---

## 触发条件

- Module: `aes_inv_cipher_top`
- Signal: `text_out`
- Effect: `improved`
- First divergence: `{"signal": "text_out", "time": 435, "ref": "11011110100010010000010110100001111100010000001111011111100100110011010011011010010010010100000000101100101001001000000100100011", "dut": "11001101100110000001100011011110000100101001011110010101100001001100011111011101111011101100101101100001100011111011000111100110", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`

## 不适用条件

- Do not reuse if affected signals, timing alignment, or spec intent differ.
- Do not reuse without reading current RTL/spec evidence.

## 补丁模式

reg          ld_latched       = 1'b0; reg          idle_rk10        = 1'b0;; ((fsm_state == FSM_IDLE) && idle_rk10) ? round_key_buffer[1407:1280] : ((fsm_state == FSM_KEY_STORED) || (fsm_state == FSM_INITIAL_ROUND)) ? round_key_buffer[1407:1280] :; state_matrix <= after_mix; idle_rk10    <= 1'b1;; FSM_DONE: begin state_matrix <= after_mix; dcnt         <= 4'd0; idle_rk10    <= 1'b0; fsm_state    <= FSM_IDLE; end; FSM_IDLE: text_out <= after_add; FSM_KEY_LOAD, FSM_KEY_EXPANSION: text_out <= after_sub;

## 验证特征

- Before mismatch count: `85`
- After mismatch count: `80`
- Metric delta: `{"total_samples_mismatch": null, "per_signal": {"done": {"before": 3, "after": 3, "first_time_before": 665, "first_time_after": 665, "direction": "unchanged"}, "text_out": {"before": 82, "after": 77, "first_time_before": 385, "first_time_after": 435, "direction": "improved"}}}`

## 复用约束

Patch improved mismatch count or first fail time; continue from this direction.

## Problem

`aes_inv_cipher_top` showed a debug failure around `text_out`.

## Evidence

- Effect: `improved`
- Before mismatch count: `85`
- After mismatch count: `80`
- First divergence: `{"signal": "text_out", "time": 435, "ref": "11011110100010010000010110100001111100010000001111011111100100110011010011011010010010010100000000101100101001001000000100100011", "dut": "11001101100110000001100011011110000100101001011110010101100001001100011111011101111011101100101101100001100011111011000111100110", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`
- Trace root failure: `{"signal": "text_out", "time": 435, "ref": "11011110100010010000010110100001111100010000001111011111100100110011010011011010010010010100000000101100101001001000000100100011", "dut": "11001101100110000001100011011110000100101001011110010101100001001100011111011101111011101100101101100001100011111011000111100110", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`
- Metric delta: `{"total_samples_mismatch": null, "per_signal": {"done": {"before": 3, "after": 3, "first_time_before": 665, "first_time_after": 665, "direction": "unchanged"}, "text_out": {"before": 82, "after": 77, "first_time_before": 385, "first_time_after": 435, "direction": "improved"}}}`

## Patch Summary

reg          ld_latched       = 1'b0; reg          idle_rk10        = 1'b0;; ((fsm_state == FSM_IDLE) && idle_rk10) ? round_key_buffer[1407:1280] : ((fsm_state == FSM_KEY_STORED) || (fsm_state == FSM_INITIAL_ROUND)) ? round_key_buffer[1407:1280] :; state_matrix <= after_mix; idle_rk10    <= 1'b1;; FSM_DONE: begin state_matrix <= after_mix; dcnt         <= 4'd0; idle_rk10    <= 1'b0; fsm_state    <= FSM_IDLE; end; FSM_IDLE: text_out <= after_add; FSM_KEY_LOAD, FSM_KEY_EXPANSION: text_out <= after_sub;

## Lesson

Patch improved mismatch count or first fail time; continue from this direction.

## Reuse Constraints

- Read current RTL/spec evidence before applying a similar patch.
- Do not reuse if affected signals or timing alignment differ.
