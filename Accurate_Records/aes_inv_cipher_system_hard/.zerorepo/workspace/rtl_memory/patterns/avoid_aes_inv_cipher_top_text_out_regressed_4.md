---
memory_id: avoid_aes_inv_cipher_top_text_out_regressed_4
type: negative_direction
stage: debug
description: "aes_inv_cipher_top: text_out regressed; Patch worsened mismatch count or first fail time and was rolled back."
module: aes_inv_cipher_top
module_family: aes
signals:
  - after_shift
  - dcnt
  - fsm_state
  - launch_state
  - round_key
  - state_matrix
  - text_out
  - transform_state
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
  - after_shift
  - dcnt
  - fsm_state
  - launch_state
  - round_key
  - state_matrix
  - text_out
  - transform_state
trigger_failure_type: timing_bug
trigger_alignment: wrong_value
risk_signals:
  - after_shift
  - dcnt
  - fsm_state
  - launch_state
  - round_key
  - state_matrix
  - text_out
  - transform_state
patch_pattern: "reg [127:0]  state_matrix     = 128'd0; reg [127:0]  launch_state     = 128'd0;; wire [127:0] transform_state;; assign round_key = ((fsm_state == FSM_KEY_STORED) || (fsm_state == F"
anti_trigger: "Avoid this direction unless new evidence distinguishes the current failure."
---

## 触发条件

- Module: `aes_inv_cipher_top`
- Signal: `text_out`
- Effect: `regressed`
- First divergence: `{"signal": "text_out", "time": 255, "ref": "00110110001011110001001101000100100100100101010011010001101111000000111011011110100011000101001110110000010000111010110101011110", "dut": "01111010110101011111110110100111100010011110111101001110001001110010101111001010000100000000101100111101100111111111010110011111", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`

## 不适用条件

- Do not reuse if affected signals, timing alignment, or spec intent differ.
- Do not reuse without reading current RTL/spec evidence.

## 补丁模式

reg [127:0]  state_matrix     = 128'd0; reg [127:0]  launch_state     = 128'd0;; wire [127:0] transform_state;; assign round_key = ((fsm_state == FSM_KEY_STORED) || (fsm_state == FSM_INITIAL_ROUND)) ? r
...<snip>...
)  ? round_key_buffer[255:128]   : (dcnt == 4'd10) ? round_key_buffer[127:0]     : 128'd0;; assign transform_state = (fsm_state == FSM_INITIAL_ROUND) ? launch_state : state_matrix; /
...<snip>...
ate[31:24],   transform_state[55:48],   transform_state[79:72], transform_state[103:96] };; launch_state <= after_mix; state_matrix <= text_in; dcnt         <= 4'd0; fsm_state    <= FSM_INITIAL_ROUND; end end; text_out <= after_add; FSM_STANDARD_ROUND,

## 验证特征

- Before mismatch count: `88`
- After mismatch count: `128`
- Metric delta: `{"total_samples_mismatch": null, "per_signal": {"done": {"before": 3, "after": 3, "first_time_before": 665, "first_time_after": 665, "direction": "unchanged"}, "text_out": {"before": 85, "after": 125, "first_time_before": 255, "first_time_after": 15, "direction": "regressed"}}}`

## 复用约束

Patch worsened mismatch count or first fail time and was rolled back.

## Problem

`aes_inv_cipher_top` showed a debug failure around `text_out`.

## Evidence

- Effect: `regressed`
- Before mismatch count: `88`
- After mismatch count: `128`
- First divergence: `{"signal": "text_out", "time": 255, "ref": "00110110001011110001001101000100100100100101010011010001101111000000111011011110100011000101001110110000010000111010110101011110", "dut": "01111010110101011111110110100111100010011110111101001110001001110010101111001010000100000000101100111101100111111111010110011111", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`
- Trace root failure: `{"signal": "text_out", "time": 255, "ref": "00110110001011110001001101000100100100100101010011010001101111000000111011011110100011000101001110110000010000111010110101011110", "dut": "01111010110101011111110110100111100010011110111101001110001001110010101111001010000100000000101100111101100111111111010110011111", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`
- Metric delta: `{"total_samples_mismatch": null, "per_signal": {"done": {"before": 3, "after": 3, "first_time_before": 665, "first_time_after": 665, "direction": "unchanged"}, "text_out": {"before": 85, "after": 125, "first_time_before": 255, "first_time_after": 15, "direction": "regressed"}}}`

## Patch Summary

reg [127:0]  state_matrix     = 128'd0; reg [127:0]  launch_state     = 128'd0;; wire [127:0] transform_state;; assign round_key = ((fsm_state == FSM_KEY_STORED) || (fsm_state == FSM_INITIAL_ROUND)) ? r
...<snip>...
)  ? round_key_buffer[255:128]   : (dcnt == 4'd10) ? round_key_buffer[127:0]     : 128'd0;; assign transform_state = (fsm_state == FSM_INITIAL_ROUND) ? launch_state : state_matrix; /
...<snip>...
ate[31:24],   transform_state[55:48],   transform_state[79:72], transform_state[103:96] };; launch_state <= after_mix; state_matrix <= text_in; dcnt         <= 4'd0; fsm_state    <= FSM_INITIAL_ROUND; end end; text_out <= after_add; FSM_STANDARD_ROUND,

## Lesson

Patch worsened mismatch count or first fail time and was rolled back.

## Reuse Constraints

- Read current RTL/spec evidence before applying a similar patch.
- Do not reuse if affected signals or timing alignment differ.
