---
memory_id: debug_aes_inv_cipher_top_text_out_improved_21
type: repair_outcome
stage: debug
description: "aes_inv_cipher_top: text_out improved; Patch improved mismatch count or first fail time; continue from this direction."
module: aes_inv_cipher_top
module_family: aes
signals:
  - restart_key_index
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
  - restart_key_index
  - text_out
trigger_failure_type: timing_bug
trigger_alignment: wrong_value
risk_signals:
  - restart_key_index
patch_pattern: "restart_key_index  <= round_key_index + 4'd1;"
anti_trigger: "Do not reuse when current first divergence, affected signals, or timing alignment differ."
---

## 触发条件

- Module: `aes_inv_cipher_top`
- Signal: `text_out`
- Effect: `improved`
- First divergence: `{"signal": "text_out", "time": 975, "ref": "10011111111101001010100000100111100101011100010100101110101000100100101000100011101110010111100100100001111110110111101110100001", "dut": "10010000100110001100111101100010010000000111001100011100011001011000110010000110000101110001001101001000111100011111010100111100", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`

## 不适用条件

- Do not reuse if affected signals, timing alignment, or spec intent differ.
- Do not reuse without reading current RTL/spec evidence.

## 补丁模式

restart_key_index  <= round_key_index + 4'd1;

## 验证特征

- Before mismatch count: `40`
- After mismatch count: `29`
- Metric delta: `{"total_samples_mismatch": null, "per_signal": {"text_out": {"before": 40, "after": 29, "first_time_before": 865, "first_time_after": 975, "direction": "improved"}}}`

## 复用约束

Patch improved mismatch count or first fail time; continue from this direction.

## Problem

`aes_inv_cipher_top` showed a debug failure around `text_out`.

## Evidence

- Effect: `improved`
- Before mismatch count: `40`
- After mismatch count: `29`
- First divergence: `{"signal": "text_out", "time": 975, "ref": "10011111111101001010100000100111100101011100010100101110101000100100101000100011101110010111100100100001111110110111101110100001", "dut": "10010000100110001100111101100010010000000111001100011100011001011000110010000110000101110001001101001000111100011111010100111100", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`
- Trace root failure: `{"signal": "text_out", "time": 975, "ref": "10011111111101001010100000100111100101011100010100101110101000100100101000100011101110010111100100100001111110110111101110100001", "dut": "10010000100110001100111101100010010000000111001100011100011001011000110010000110000101110001001101001000111100011111010100111100", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "edge_active", "edge": "posedge", "driver_assignment_kind": "nonblocking", "active_region_model": "ref=edge settled value; DUT=pre-edge old value for nonblocking output drivers, edge settled value for blocking/continuous drivers"}`
- Metric delta: `{"total_samples_mismatch": null, "per_signal": {"text_out": {"before": 40, "after": 29, "first_time_before": 865, "first_time_after": 975, "direction": "improved"}}}`

## Patch Summary

restart_key_index  <= round_key_index + 4'd1;

## Lesson

Patch improved mismatch count or first fail time; continue from this direction.

## Reuse Constraints

- Read current RTL/spec evidence before applying a similar patch.
- Do not reuse if affected signals or timing alignment differ.
