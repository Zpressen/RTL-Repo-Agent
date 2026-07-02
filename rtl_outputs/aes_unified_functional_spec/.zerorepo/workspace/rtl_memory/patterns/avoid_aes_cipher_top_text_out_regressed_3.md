---
memory_id: avoid_aes_cipher_top_text_out_regressed_3
type: negative_direction
stage: debug
description: "aes_cipher_top: text_out regressed; Patch worsened mismatch count or first fail time and was rolled back."
module: aes_cipher_top
module_family: aes
signals:
  - text_out
  - text_out_next
failure_type: local_logic_bug
alignment: wrong_value
outcome: regressed
confidence: 0.68
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
trigger_failure_type: local_logic_bug
trigger_alignment: wrong_value
risk_signals:
  - text_out_next
patch_pattern: "assign text_out_next = round_data_bus;"
anti_trigger: "Avoid this direction unless new evidence distinguishes the current failure."
---

## 触发条件

- Module: `aes_cipher_top`
- Signal: `text_out`
- Effect: `regressed`
- First divergence: `{"signal": "text_out", "time": 35, "ref": "00010111111011011000101001111011011000000111000100010110111001110111010010001110111010010001100000000011000100100111010110000100", "dut": "01101111101110001101111100000011001110001100110110101010101111110000110011011011101111000110000001011011101011101100100111011100", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "nonblocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`

## 不适用条件

- Do not reuse if affected signals, timing alignment, or spec intent differ.
- Do not reuse without reading current RTL/spec evidence.

## 补丁模式

assign text_out_next = round_data_bus;

## 验证特征

- Before mismatch count: `284`
- After mismatch count: `286`
- Metric delta: `{"total_samples_mismatch": null, "per_signal": {}}`

## 复用约束

Patch worsened mismatch count or first fail time and was rolled back.

## Problem

`aes_cipher_top` showed a debug failure around `text_out`.

## Evidence

- Effect: `regressed`
- Before mismatch count: `284`
- After mismatch count: `286`
- First divergence: `{"signal": "text_out", "time": 35, "ref": "00010111111011011000101001111011011000000111000100010110111001110111010010001110111010010001100000000011000100100111010110000100", "dut": "01101111101110001101111100000011001110001100110110101010101111110000110011011011101111000110000001011011101011101100100111011100", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "nonblocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`
- Trace root failure: `{"signal": "text_out", "time": 35, "ref": "00010111111011011000101001111011011000000111000100010110111001110111010010001110111010010001100000000011000100100111010110000100", "dut": "01101111101110001101111100000011001110001100110110101010101111110000110011011011101111000110000001011011101011101100100111011100", "classification": "wrong_value", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "nonblocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`
- Metric delta: `{"total_samples_mismatch": null, "per_signal": {}}`

## Patch Summary

assign text_out_next = round_data_bus;

## Lesson

Patch worsened mismatch count or first fail time and was rolled back.

## Reuse Constraints

- Read current RTL/spec evidence before applying a similar patch.
- Do not reuse if affected signals or timing alignment differ.
