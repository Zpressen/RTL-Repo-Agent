---
memory_id: debug_aes_inv_cipher_top_text_out_improved_1
type: repair_outcome
stage: debug
description: "aes_inv_cipher_top: text_out improved; Patch improved mismatch count or first fail time; continue from this direction."
module: aes_inv_cipher_top
module_family: aes
signals:
  - done
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
  - done
  - text_out
trigger_failure_type: timing_bug
trigger_alignment: wrong_value
risk_signals:
  - done
  - text_out
patch_pattern: "always @(posedge clk) begin done <= 1'b0; case (fsm_state) FSM_IDLE, FSM_KEY_LOAD, FSM_KEY\n...<snip>...\nefault: text_out <= after_sub; endcase if (fsm_state == FSM_FINAL_ROUND) don"
anti_trigger: "Do not reuse when current first divergence, affected signals, or timing alignment differ."
---

## 触发条件

- Module: `aes_inv_cipher_top`
- Signal: `text_out`
- Effect: `improved`
- First divergence: `{"signal": "text_out", "time": 255, "ref": "00110110001011110001001101000100100100100101010011010001101111000000111011011110100011000101001110110000010000111010110101011110", "dut": "01111010110101011111110110100111100010011110111101001110001001110010101111001010000100000000101100111101100111111111010110011111", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`

## 不适用条件

- Do not reuse if affected signals, timing alignment, or spec intent differ.
- Do not reuse without reading current RTL/spec evidence.

## 补丁模式

always @(posedge clk) begin done <= 1'b0; case (fsm_state) FSM_IDLE, FSM_KEY_LOAD, FSM_KEY
...<snip>...
efault: text_out <= after_sub; endcase if (fsm_state == FSM_FINAL_ROUND) done <= 1'b1; end

## 验证特征

- Before mismatch count: `89`
- After mismatch count: `88`
- Metric delta: `{"total_samples_mismatch": null, "per_signal": {"done": {"before": 3, "after": 3, "first_time_before": 665, "first_time_after": 665, "direction": "unchanged"}, "text_out": {"before": 86, "after": 85, "first_time_before": 245, "first_time_after": 255, "direction": "improved"}}}`

## 复用约束

Patch improved mismatch count or first fail time; continue from this direction.

## Problem

`aes_inv_cipher_top` showed a debug failure around `text_out`.

## Evidence

- Effect: `improved`
- Before mismatch count: `89`
- After mismatch count: `88`
- First divergence: `{"signal": "text_out", "time": 255, "ref": "00110110001011110001001101000100100100100101010011010001101111000000111011011110100011000101001110110000010000111010110101011110", "dut": "01111010110101011111110110100111100010011110111101001110001001110010101111001010000100000000101100111101100111111111010110011111", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`
- Trace root failure: `{"signal": "text_out", "time": 255, "ref": "00110110001011110001001101000100100100100101010011010001101111000000111011011110100011000101001110110000010000111010110101011110", "dut": "01111010110101011111110110100111100010011110111101001110001001110010101111001010000100000000101100111101100111111111010110011111", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`
- Metric delta: `{"total_samples_mismatch": null, "per_signal": {"done": {"before": 3, "after": 3, "first_time_before": 665, "first_time_after": 665, "direction": "unchanged"}, "text_out": {"before": 86, "after": 85, "first_time_before": 245, "first_time_after": 255, "direction": "improved"}}}`

## Patch Summary

always @(posedge clk) begin done <= 1'b0; case (fsm_state) FSM_IDLE, FSM_KEY_LOAD, FSM_KEY
...<snip>...
efault: text_out <= after_sub; endcase if (fsm_state == FSM_FINAL_ROUND) done <= 1'b1; end

## Lesson

Patch improved mismatch count or first fail time; continue from this direction.

## Reuse Constraints

- Read current RTL/spec evidence before applying a similar patch.
- Do not reuse if affected signals or timing alignment differ.
