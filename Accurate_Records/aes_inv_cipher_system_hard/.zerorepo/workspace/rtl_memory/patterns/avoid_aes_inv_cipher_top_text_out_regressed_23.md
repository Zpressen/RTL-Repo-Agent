---
memory_id: avoid_aes_inv_cipher_top_text_out_regressed_23
type: negative_direction
stage: debug
description: "aes_inv_cipher_top: text_out regressed; Patch worsened mismatch count or first fail time and was rolled back."
module: aes_inv_cipher_top
module_family: aes
signals:
  - bg_key_capture_active
  - bg_key_capture_index
  - bg_key_capture_wait
  - round_key_buffer
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
  - bg_key_capture_active
  - bg_key_capture_index
  - bg_key_capture_wait
  - round_key_buffer
  - text_out
trigger_failure_type: timing_bug
trigger_alignment: wrong_value
risk_signals:
  - bg_key_capture_active
  - bg_key_capture_index
  - bg_key_capture_wait
  - round_key_buffer
patch_pattern: "reg          bg_key_capture_active = 1'b0; reg          bg_key_capture_wait = 1'b0; reg [3:0]    bg_key_capture_index = 4'd0;; if (bg_key_capture_active) begin if (bg_key_capture_w"
anti_trigger: "Avoid this direction unless new evidence distinguishes the current failure."
---

## 触发条件

- Module: `aes_inv_cipher_top`
- Signal: `text_out`
- Effect: `regressed`
- First divergence: `{"signal": "text_out", "time": 985, "ref": "11101100101101011101100110101010100110110000001101000110111011101001001100011111111011010010000100101010111001000000000011110110", "dut": "11001010110111011001100110110100001000001010110101000000101010110000110110110010101101101010110100100101100000100001001100101110", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`

## 不适用条件

- Do not reuse if affected signals, timing alignment, or spec intent differ.
- Do not reuse without reading current RTL/spec evidence.

## 补丁模式

reg          bg_key_capture_active = 1'b0; reg          bg_key_capture_wait = 1'b0; reg [3:0]    bg_key_capture_index = 4'd0;; if (bg_key_capture_active) begin if (bg_key_capture_wait) begin bg_key_capture_wait <= 1'b
...<snip>...
_capture_active <= 1'b0; else bg_key_capture_index <= bg_key_capture_index + 4'd1; end end; if (kld_latched) begin if ((fsm_state != FSM_IDLE) && (fsm_state != FSM_KEY_STORED)) begin
...<snip>...
gin bg_key_capture_active <= 1'b0; bg_key_capture_wait   <= 1'b0; end end case (fsm_state)

## 验证特征

- Before mismatch count: `10`
- After mismatch count: `29`
- Metric delta: `{"total_samples_mismatch": null, "per_signal": {"text_out": {"before": 10, "after": 29, "first_time_before": 985, "first_time_after": 975, "direction": "regressed"}}}`

## 复用约束

Patch worsened mismatch count or first fail time and was rolled back.

## Problem

`aes_inv_cipher_top` showed a debug failure around `text_out`.

## Evidence

- Effect: `regressed`
- Before mismatch count: `10`
- After mismatch count: `29`
- First divergence: `{"signal": "text_out", "time": 985, "ref": "11101100101101011101100110101010100110110000001101000110111011101001001100011111111011010010000100101010111001000000000011110110", "dut": "11001010110111011001100110110100001000001010110101000000101010110000110110110010101101101010110100100101100000100001001100101110", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`
- Trace root failure: `{"signal": "text_out", "time": 985, "ref": "11101100101101011101100110101010100110110000001101000110111011101001001100011111111011010010000100101010111001000000000011110110", "dut": "11001010110111011001100110110100001000001010110101000000101010110000110110110010101101101010110100100101100000100001001100101110", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`
- Metric delta: `{"total_samples_mismatch": null, "per_signal": {"text_out": {"before": 10, "after": 29, "first_time_before": 985, "first_time_after": 975, "direction": "regressed"}}}`

## Patch Summary

reg          bg_key_capture_active = 1'b0; reg          bg_key_capture_wait = 1'b0; reg [3:0]    bg_key_capture_index = 4'd0;; if (bg_key_capture_active) begin if (bg_key_capture_wait) begin bg_key_capture_wait <= 1'b
...<snip>...
_capture_active <= 1'b0; else bg_key_capture_index <= bg_key_capture_index + 4'd1; end end; if (kld_latched) begin if ((fsm_state != FSM_IDLE) && (fsm_state != FSM_KEY_STORED)) begin
...<snip>...
gin bg_key_capture_active <= 1'b0; bg_key_capture_wait   <= 1'b0; end end case (fsm_state)

## Lesson

Patch worsened mismatch count or first fail time and was rolled back.

## Reuse Constraints

- Read current RTL/spec evidence before applying a similar patch.
- Do not reuse if affected signals or timing alignment differ.
