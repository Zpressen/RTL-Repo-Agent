---
memory_id: debug_aes_inv_cipher_top_text_out_improved_2
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
- First divergence: `{"signal": "text_out", "time": 245, "ref": "01001110010011000100000000100010101111101100100100010111010010101010111001011010111110101101011000010000011101100110110110011000", "dut": "01011101010111010101110101011101010111010101110101011101010111010101110101011101010111010101110101011101010111010101110101011101", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`

## 不适用条件

- Do not reuse if affected signals, timing alignment, or spec intent differ.
- Do not reuse without reading current RTL/spec evidence.

## 补丁模式

always @(posedge clk) begin done <= 1'b0; case (fsm_state) FSM_IDLE, FSM_KEY_LOAD, FSM_KEY
...<snip>...
efault: text_out <= after_sub; endcase if (fsm_state == FSM_FINAL_ROUND) done <= 1'b1; end

## 验证特征

- Before mismatch count: `109`
- After mismatch count: `89`
- Metric delta: `{"total_samples_mismatch": null, "per_signal": {"done": {"before": 3, "after": 3, "first_time_before": 665, "first_time_after": 665, "direction": "unchanged"}, "text_out": {"before": 106, "after": 86, "first_time_before": 195, "first_time_after": 245, "direction": "improved"}}}`

## 复用约束

Patch improved mismatch count or first fail time; continue from this direction.

## Problem

`aes_inv_cipher_top` showed a debug failure around `text_out`.

## Evidence

- Effect: `improved`
- Before mismatch count: `109`
- After mismatch count: `89`
- First divergence: `{"signal": "text_out", "time": 245, "ref": "01001110010011000100000000100010101111101100100100010111010010101010111001011010111110101101011000010000011101100110110110011000", "dut": "01011101010111010101110101011101010111010101110101011101010111010101110101011101010111010101110101011101010111010101110101011101", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`
- Trace root failure: `{"signal": "text_out", "time": 245, "ref": "01001110010011000100000000100010101111101100100100010111010010101010111001011010111110101101011000010000011101100110110110011000", "dut": "01011101010111010101110101011101010111010101110101011101010111010101110101011101010111010101110101011101010111010101110101011101", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`
- Metric delta: `{"total_samples_mismatch": null, "per_signal": {"done": {"before": 3, "after": 3, "first_time_before": 665, "first_time_after": 665, "direction": "unchanged"}, "text_out": {"before": 106, "after": 86, "first_time_before": 195, "first_time_after": 245, "direction": "improved"}}}`

## Patch Summary

always @(posedge clk) begin done <= 1'b0; case (fsm_state) FSM_IDLE, FSM_KEY_LOAD, FSM_KEY
...<snip>...
efault: text_out <= after_sub; endcase if (fsm_state == FSM_FINAL_ROUND) done <= 1'b1; end

## Lesson

Patch improved mismatch count or first fail time; continue from this direction.

## Reuse Constraints

- Read current RTL/spec evidence before applying a similar patch.
- Do not reuse if affected signals or timing alignment differ.
