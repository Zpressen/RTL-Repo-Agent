---
memory_id: debug_aes_cipher_top_text_out_improved_1
type: repair_outcome
stage: debug
description: "aes_cipher_top: text_out improved; Patch improved mismatch count or first fail time; continue from this direction."
module: aes_cipher_top
module_family: aes
signals:
  - aes_state
  - aes_state_next
  - dcnt_next_mux
  - mixcolumns_bypass
  - round_data_bus
  - sa_00
  - sa_01
  - sa_02
  - sa_03
  - sa_10
  - sa_11
  - sa_12
failure_type: plan_bug
alignment: wrong_value
outcome: improved
confidence: 0.72
verified_by:
  - lint
  - module_sim
  - trace
source_artifacts:
  - debug/aes_cipher_top/trace_report.json
  - repo_react/aes_cipher_top/patch_journal.jsonl
trigger_signals:
  - aes_state
  - aes_state_next
  - dcnt_next_mux
  - mixcolumns_bypass
  - round_data_bus
  - sa_00
  - sa_01
  - sa_02
  - sa_03
  - sa_10
  - sa_11
  - sa_12
trigger_failure_type: plan_bug
trigger_alignment: wrong_value
risk_signals:
  - aes_state
  - aes_state_next
  - dcnt_next_mux
  - mixcolumns_bypass
  - round_data_bus
  - sa_00
  - sa_01
  - sa_02
  - sa_03
  - sa_10
  - sa_11
  - sa_12
  - sa_13
  - sa_20
  - sa_21
  - sa_22
  - sa_23
  - sa_30
  - sa_31
  - sa_32
  - sa_33
  - text_out_next
patch_pattern: "// FSM state register. Reset returns the controller to ROUND_OP for free-running operation\n...<snip>...\n1) begin aes_state <= AES_ST_ROUND_OP; end else begin aes_state <= aes_state"
anti_trigger: "Do not reuse when current first divergence, affected signals, or timing alignment differ."
---

## 触发条件

- Module: `aes_cipher_top`
- Signal: `text_out`
- Effect: `improved`
- First divergence: `{"signal": "text_out", "time": 35, "ref": "00010111111011011000101001111011011000000111000100010110111001110111010010001110111010010001100000000011000100100111010110000100", "dut": "01101111101110001101111100000011001110001100110110101010101111110000110011011011101111000110000001011011101011101100100111011100", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "nonblocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`

## 不适用条件

- Do not reuse if affected signals, timing alignment, or spec intent differ.
- Do not reuse without reading current RTL/spec evidence.

## 补丁模式

// FSM state register. Reset returns the controller to ROUND_OP for free-running operation
...<snip>...
1) begin aes_state <= AES_ST_ROUND_OP; end else begin aes_state <= aes_state_next; end end; AES_ST_IDLE: begin dcnt_next_mux = 4'h0; aes_state_next = AES_ST_ROUND_OP; end; AES_ST_ROUND_OP: begin if (ld == 1'b1) begin dcnt_next_mux = 4'hb; end else if (dcnt > 4'h
...<snip>...
cnt - 4'h1; end else begin dcnt_next_mux = 4'h0; end aes_state_next = AES_ST_ROUND_OP; end; // Final round bypasses MixColumns. Detect final round when dcnt==1. assign mixcolumns_bypass = (dcnt == 4'h1);; assign round_data_bus = (dcnt == 4'h1) ? shiftrows_bus : mixcolumns_bus;; assign text_out_next = final_data_bus;; if (ld_r == 1'b1) begin sa_00 <= text_in_r[127:120] ^ round_key_bus[127:120]; sa_10 <= tex
...<snip>...
]; sa_13 <= sa_next_bus[23:16]; sa_23 <= sa_next_bus[15:8]; sa_33 <= sa_next_bus[7:0]; end

## 验证特征

- Before mismatch count: `287`
- After mismatch count: `284`
- Metric delta: `{"total_samples_mismatch": null, "per_signal": {}}`

## 复用约束

Patch improved mismatch count or first fail time; continue from this direction.

## Problem

`aes_cipher_top` showed a debug failure around `text_out`.

## Evidence

- Effect: `improved`
- Before mismatch count: `287`
- After mismatch count: `284`
- First divergence: `{"signal": "text_out", "time": 35, "ref": "00010111111011011000101001111011011000000111000100010110111001110111010010001110111010010001100000000011000100100111010110000100", "dut": "01101111101110001101111100000011001110001100110110101010101111110000110011011011101111000110000001011011101011101100100111011100", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "nonblocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`
- Trace root failure: `{"signal": "text_out", "time": 35, "ref": "00010111111011011000101001111011011000000111000100010110111001110111010010001110111010010001100000000011000100100111010110000100", "dut": "01101111101110001101111100000011001110001100110110101010101111110000110011011011101111000110000001011011101011101100100111011100", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "nonblocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`
- Metric delta: `{"total_samples_mismatch": null, "per_signal": {}}`

## Patch Summary

// FSM state register. Reset returns the controller to ROUND_OP for free-running operation
...<snip>...
1) begin aes_state <= AES_ST_ROUND_OP; end else begin aes_state <= aes_state_next; end end; AES_ST_IDLE: begin dcnt_next_mux = 4'h0; aes_state_next = AES_ST_ROUND_OP; end; AES_ST_ROUND_OP: begin if (ld == 1'b1) begin dcnt_next_mux = 4'hb; end else if (dcnt > 4'h
...<snip>...
cnt - 4'h1; end else begin dcnt_next_mux = 4'h0; end aes_state_next = AES_ST_ROUND_OP; end; // Final round bypasses MixColumns. Detect final round when dcnt==1. assign mixcolumns_bypass = (dcnt == 4'h1);; assign round_data_bus = (dcnt == 4'h1) ? shiftrows_bus : mixcolumns_bus;; assign text_out_next = final_data_bus;; if (ld_r == 1'b1) begin sa_00 <= text_in_r[127:120] ^ round_key_bus[127:120]; sa_10 <= tex
...<snip>...
]; sa_13 <= sa_next_bus[23:16]; sa_23 <= sa_next_bus[15:8]; sa_33 <= sa_next_bus[7:0]; end

## Lesson

Patch improved mismatch count or first fail time; continue from this direction.

## Reuse Constraints

- Read current RTL/spec evidence before applying a similar patch.
- Do not reuse if affected signals or timing alignment differ.
