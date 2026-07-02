---
memory_id: debug_aes_cipher_top_text_out_improved_4
type: repair_outcome
stage: debug
description: "aes_cipher_top: text_out improved; Patch improved mismatch count or first fail time; continue from this direction."
module: aes_cipher_top
module_family: aes
signals:
  - text_out
  - text_out_next
failure_type: interface_bug
alignment: dut_late
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
  - text_out
  - text_out_next
trigger_failure_type: interface_bug
trigger_alignment: dut_late
risk_signals:
  - text_out_next
patch_pattern: "assign text_out_next = shiftrows_bus ^ round_key_bus;"
anti_trigger: "Do not reuse when current first divergence, affected signals, or timing alignment differ."
---

## 触发条件

- Module: `aes_cipher_top`
- Signal: `text_out`
- Effect: `improved`
- First divergence: `{"signal": "text_out", "time": 55, "ref": "11010011101000001001010001110110010101101001110101000001011001101111011011111111111001100000100001010111001101111000010111101000", "dut": "01000111010111000001110010101100100000000011010011001000101010111000101110011101011111111011101001000111000110100100001011111011", "classification": "dut_late", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "nonblocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`

## 不适用条件

- Do not reuse if affected signals, timing alignment, or spec intent differ.
- Do not reuse without reading current RTL/spec evidence.

## 补丁模式

assign text_out_next = shiftrows_bus ^ round_key_bus;

## 验证特征

- Before mismatch count: `284`
- After mismatch count: `282`
- Metric delta: `{"total_samples_mismatch": null, "per_signal": {}}`

## 复用约束

Patch improved mismatch count or first fail time; continue from this direction.

## Problem

`aes_cipher_top` showed a debug failure around `text_out`.

## Evidence

- Effect: `improved`
- Before mismatch count: `284`
- After mismatch count: `282`
- First divergence: `{"signal": "text_out", "time": 55, "ref": "11010011101000001001010001110110010101101001110101000001011001101111011011111111111001100000100001010111001101111000010111101000", "dut": "01000111010111000001110010101100100000000011010011001000101010111000101110011101011111111011101001000111000110100100001011111011", "classification": "dut_late", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "nonblocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`
- Trace root failure: `{"signal": "text_out", "time": 55, "ref": "11010011101000001001010001110110010101101001110101000001011001101111011011111111111001100000100001010111001101111000010111101000", "dut": "01000111010111000001110010101100100000000011010011001000101010111000101110011101011111111011101001000111000110100100001011111011", "classification": "dut_late", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "nonblocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`
- Metric delta: `{"total_samples_mismatch": null, "per_signal": {}}`

## Patch Summary

assign text_out_next = shiftrows_bus ^ round_key_bus;

## Lesson

Patch improved mismatch count or first fail time; continue from this direction.

## Reuse Constraints

- Read current RTL/spec evidence before applying a similar patch.
- Do not reuse if affected signals or timing alignment differ.
