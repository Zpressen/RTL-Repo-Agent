---
memory_id: avoid_aes_inv_cipher_top_text_out_regressed_8
type: negative_direction
stage: debug
description: "aes_inv_cipher_top: text_out regressed; Patch worsened mismatch count or first fail time and was rolled back."
module: aes_inv_cipher_top
module_family: aes
signals:
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
  - text_out
trigger_failure_type: timing_bug
trigger_alignment: wrong_value
risk_signals:
  - text_out
patch_pattern: "((fsm_state == FSM_IDLE) || (fsm_state == FSM_KEY_STORED) || (fsm_state == FSM_INITIAL_ROUND)) ? round_key_buffer[1407:1280] :; FSM_IDLE: text_out <= after_add; FSM_KEY_LOAD, FSM_K"
anti_trigger: "Avoid this direction unless new evidence distinguishes the current failure."
---

## 触发条件

- Module: `aes_inv_cipher_top`
- Signal: `text_out`
- Effect: `regressed`
- First divergence: `{"signal": "text_out", "time": 385, "ref": "00100110111010101100011101110010000100010010000110110101010111111010111101001110001011001100010101010011100001001111111001000101", "dut": "00110101111110111101101000001101111100101011010111111111010010000101110001001001100010110100111000011110101011111100111010000000", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`

## 不适用条件

- Do not reuse if affected signals, timing alignment, or spec intent differ.
- Do not reuse without reading current RTL/spec evidence.

## 补丁模式

((fsm_state == FSM_IDLE) || (fsm_state == FSM_KEY_STORED) || (fsm_state == FSM_INITIAL_ROUND)) ? round_key_buffer[1407:1280] :; FSM_IDLE: text_out <= after_add; FSM_KEY_LOAD, FSM_KEY_EXPANSION: text_out <= after_sub;

## 验证特征

- Before mismatch count: `85`
- After mismatch count: `86`
- Metric delta: `{"total_samples_mismatch": null, "per_signal": {"done": {"before": 3, "after": 3, "first_time_before": 665, "first_time_after": 665, "direction": "unchanged"}, "text_out": {"before": 82, "after": 83, "first_time_before": 385, "first_time_after": 375, "direction": "regressed"}}}`

## 复用约束

Patch worsened mismatch count or first fail time and was rolled back.

## Problem

`aes_inv_cipher_top` showed a debug failure around `text_out`.

## Evidence

- Effect: `regressed`
- Before mismatch count: `85`
- After mismatch count: `86`
- First divergence: `{"signal": "text_out", "time": 385, "ref": "00100110111010101100011101110010000100010010000110110101010111111010111101001110001011001100010101010011100001001111111001000101", "dut": "00110101111110111101101000001101111100101011010111111111010010000101110001001001100010110100111000011110101011111100111010000000", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`
- Trace root failure: `{"signal": "text_out", "time": 385, "ref": "00100110111010101100011101110010000100010010000110110101010111111010111101001110001011001100010101010011100001001111111001000101", "dut": "00110101111110111101101000001101111100101011010111111111010010000101110001001001100010110100111000011110101011111100111010000000", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`
- Metric delta: `{"total_samples_mismatch": null, "per_signal": {"done": {"before": 3, "after": 3, "first_time_before": 665, "first_time_after": 665, "direction": "unchanged"}, "text_out": {"before": 82, "after": 83, "first_time_before": 385, "first_time_after": 375, "direction": "regressed"}}}`

## Patch Summary

((fsm_state == FSM_IDLE) || (fsm_state == FSM_KEY_STORED) || (fsm_state == FSM_INITIAL_ROUND)) ? round_key_buffer[1407:1280] :; FSM_IDLE: text_out <= after_add; FSM_KEY_LOAD, FSM_KEY_EXPANSION: text_out <= after_sub;

## Lesson

Patch worsened mismatch count or first fail time and was rolled back.

## Reuse Constraints

- Read current RTL/spec evidence before applying a similar patch.
- Do not reuse if affected signals or timing alignment differ.
