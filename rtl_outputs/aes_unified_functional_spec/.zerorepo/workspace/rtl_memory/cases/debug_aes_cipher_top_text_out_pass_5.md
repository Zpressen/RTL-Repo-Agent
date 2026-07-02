---
memory_id: debug_aes_cipher_top_text_out_pass_5
type: repair_outcome
stage: debug
description: "aes_cipher_top: text_out passed; Patch fixed all observed mismatches."
module: aes_cipher_top
module_family: aes
signals:
  - dcnt
  - ld_r
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
failure_type: timing_bug
alignment: dut_late
outcome: pass
confidence: 0.9
verified_by:
  - lint
  - module_sim
  - trace
source_artifacts:
  - debug/aes_cipher_top/trace_report.json
  - repo_react/aes_cipher_top/patch_journal.jsonl
trigger_signals:
  - dcnt
  - ld_r
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
trigger_failure_type: timing_bug
trigger_alignment: dut_late
risk_signals:
  - dcnt
  - ld_r
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
  - text_in_r
  - text_out
patch_pattern: "// Registered data/control commit. The done output is driven from the DONE state // by the\n...<snip>...\na_13 <= sa_next_bus[23:16]; sa_23 <= sa_next_bus[15:8]; sa_33 <= sa_next_bus"
anti_trigger: "Do not reuse when current first divergence, affected signals, or timing alignment differ."
---

## 触发条件

- Module: `aes_cipher_top`
- Signal: `text_out`
- Effect: `passed`
- First divergence: `{"signal": "text_out", "time": 55, "ref": "11010011101000001001010001110110010101101001110101000001011001101111011011111111111001100000100001010111001101111000010111101000", "dut": "01000111010111000001110010101100100000000011010011001000101010111000101110011101011111111011101001000111000110100100001011111011", "classification": "dut_late", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "nonblocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`

## 不适用条件

- Do not reuse if affected signals, timing alignment, or spec intent differ.
- Do not reuse without reading current RTL/spec evidence.

## 补丁模式

// Registered data/control commit. The done output is driven from the DONE state // by the
...<snip>...
a_13 <= sa_next_bus[23:16]; sa_23 <= sa_next_bus[15:8]; sa_33 <= sa_next_bus[7:0]; end end

## 验证特征

- Before mismatch count: `282`
- After mismatch count: `0`
- Metric delta: `{"total_samples_mismatch": null, "per_signal": {}}`

## 复用约束

Patch fixed all observed mismatches.

## Problem

`aes_cipher_top` showed a debug failure around `text_out`.

## Evidence

- Effect: `passed`
- Before mismatch count: `282`
- After mismatch count: `0`
- First divergence: `{"signal": "text_out", "time": 55, "ref": "11010011101000001001010001110110010101101001110101000001011001101111011011111111111001100000100001010111001101111000010111101000", "dut": "01000111010111000001110010101100100000000011010011001000101010111000101110011101011111111011101001000111000110100100001011111011", "classification": "dut_late", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "nonblocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`
- Trace root failure: `{"signal": "text_out", "time": 55, "ref": "11010011101000001001010001110110010101101001110101000001011001101111011011111111111001100000100001010111001101111000010111101000", "dut": "01000111010111000001110010101100100000000011010011001000101010111000101110011101011111111011101001000111000110100100001011111011", "classification": "dut_late", "ref_path": "tb.text_out_ref[127:0]", "dut_path": "tb.text_out_dut[127:0]", "sampling_mode": "stable", "edge": null, "driver_assignment_kind": "nonblocking", "active_region_model": "settled VCD ref/dut values at sample/change times"}`
- Metric delta: `{"total_samples_mismatch": null, "per_signal": {}}`

## Patch Summary

// Registered data/control commit. The done output is driven from the DONE state // by the
...<snip>...
a_13 <= sa_next_bus[23:16]; sa_23 <= sa_next_bus[15:8]; sa_33 <= sa_next_bus[7:0]; end end

## Lesson

Patch fixed all observed mismatches.

## Reuse Constraints

- Read current RTL/spec evidence before applying a similar patch.
- Do not reuse if affected signals or timing alignment differ.
