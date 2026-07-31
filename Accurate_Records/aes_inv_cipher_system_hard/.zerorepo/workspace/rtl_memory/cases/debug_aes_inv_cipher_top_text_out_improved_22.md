---
memory_id: debug_aes_inv_cipher_top_text_out_improved_22
type: repair_outcome
stage: debug
description: "aes_inv_cipher_top: text_out improved; Patch improved mismatch count or first fail time; continue from this direction."
module: aes_inv_cipher_top
module_family: aes
signals:
  - bg_key_capture_active
  - bg_key_capture_index
  - key_expand_kld
  - restart_key_index
  - restart_key_valid
  - restart_state_load
  - round_key_buffer
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
  - bg_key_capture_active
  - bg_key_capture_index
  - key_expand_kld
  - restart_key_index
  - restart_key_valid
  - restart_state_load
  - round_key_buffer
  - text_out
trigger_failure_type: timing_bug
trigger_alignment: wrong_value
risk_signals:
  - bg_key_capture_active
  - bg_key_capture_index
  - key_expand_kld
  - restart_key_index
  - restart_key_valid
  - restart_state_load
  - round_key_buffer
patch_pattern: "reg          restart_key_valid = 1'b0; reg [3:0]    restart_key_index = 4'd0; reg         \n...<snip>...\n1'b0; reg          bg_key_capture_active = 1'b0; reg [3:0]    bg_key_capture"
anti_trigger: "Do not reuse when current first divergence, affected signals, or timing alignment differ."
---

## 触发条件

- Module: `aes_inv_cipher_top`
- Signal: `text_out`
- Effect: `improved`
- First divergence: `{"signal": "text_out", "time": 985, "ref": "11101100101101011101100110101010100110110000001101000110111011101001001100011111111011010010000100101010111001000000000011110110", "dut": "11001010110111011001100110110100001000001010110101000000101010110000110110110010101101101010110100100101100000100001001100101110", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`

## 不适用条件

- Do not reuse if affected signals, timing alignment, or spec intent differ.
- Do not reuse without reading current RTL/spec evidence.

## 补丁模式

reg          restart_key_valid = 1'b0; reg [3:0]    restart_key_index = 4'd0; reg         
...<snip>...
1'b0; reg          bg_key_capture_active = 1'b0; reg [3:0]    bg_key_capture_index = 4'd0;; aes_key_expand inst_key_expand ( .clk         (clk), .rst         (rst), .kld         (key
...<snip>...
 .kld         (kld_latched), .initial_key (key), .round_key   (bg_key_expand_round_key) );; always @(posedge clk) begin key_expand_kld     <= 1'b0; restart_state_load <= 1'b0; if (bg
...<snip>...
1'b1; bg_key_capture_index  <= 4'd0; end else begin bg_key_capture_active <= 1'b0; end end

## 验证特征

- Before mismatch count: `29`
- After mismatch count: `10`
- Metric delta: `{"total_samples_mismatch": null, "per_signal": {"text_out": {"before": 29, "after": 10, "first_time_before": 975, "first_time_after": 985, "direction": "improved"}}}`

## 复用约束

Patch improved mismatch count or first fail time; continue from this direction.

## Problem

`aes_inv_cipher_top` showed a debug failure around `text_out`.

## Evidence

- Effect: `improved`
- Before mismatch count: `29`
- After mismatch count: `10`
- First divergence: `{"signal": "text_out", "time": 985, "ref": "11101100101101011101100110101010100110110000001101000110111011101001001100011111111011010010000100101010111001000000000011110110", "dut": "11001010110111011001100110110100001000001010110101000000101010110000110110110010101101101010110100100101100000100001001100101110", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`
- Trace root failure: `{"signal": "text_out", "time": 985, "ref": "11101100101101011101100110101010100110110000001101000110111011101001001100011111111011010010000100101010111001000000000011110110", "dut": "11001010110111011001100110110100001000001010110101000000101010110000110110110010101101101010110100100101100000100001001100101110", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`
- Metric delta: `{"total_samples_mismatch": null, "per_signal": {"text_out": {"before": 29, "after": 10, "first_time_before": 975, "first_time_after": 985, "direction": "improved"}}}`

## Patch Summary

reg          restart_key_valid = 1'b0; reg [3:0]    restart_key_index = 4'd0; reg         
...<snip>...
1'b0; reg          bg_key_capture_active = 1'b0; reg [3:0]    bg_key_capture_index = 4'd0;; aes_key_expand inst_key_expand ( .clk         (clk), .rst         (rst), .kld         (key
...<snip>...
 .kld         (kld_latched), .initial_key (key), .round_key   (bg_key_expand_round_key) );; always @(posedge clk) begin key_expand_kld     <= 1'b0; restart_state_load <= 1'b0; if (bg
...<snip>...
1'b1; bg_key_capture_index  <= 4'd0; end else begin bg_key_capture_active <= 1'b0; end end

## Lesson

Patch improved mismatch count or first fail time; continue from this direction.

## Reuse Constraints

- Read current RTL/spec evidence before applying a similar patch.
- Do not reuse if affected signals or timing alignment differ.
