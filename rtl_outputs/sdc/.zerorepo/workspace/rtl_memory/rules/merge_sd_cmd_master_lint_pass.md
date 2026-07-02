---
memory_id: merge_sd_cmd_master_lint_pass
type: merge_rule
stage: stage6_merge
description: "sd_cmd_master: Stage6 merge warning; Stage5 contracts have multiple writers for response_size: ['B4_comb_cmd_settings_assembly', 'B7_seq_fsm_state_operations"
module: sd_cmd_master
module_family: sdc
signals:
  - CMDI
  - WORD_SELECT
  - CICE
  - CRCE
  - RTS
  - dat_ava
  - crc_valid
  - command_index_mismatch
  - timeout_expired
  - response_present
  - next_state
  - state
failure_type: ""
alignment: ""
outcome: lint_pass
confidence: 0.72
verified_by:
  - stage6_static_check
  - lint
source_artifacts:
  - merge_reports/sd_cmd_master_merge_report.json
trigger_signals: []
trigger_failure_type: ""
trigger_alignment: ""
risk_signals: []
patch_pattern: ""
anti_trigger: ""
---

## Pattern

Stage6 merge for `sd_cmd_master` produced outcome `lint_pass`.

## Evidence

- Static warning: Stage5 contracts have multiple writers for response_size: ['B4_comb_cmd_settings_assembly', 'B7_seq_fsm_state_operations'].
- Static warning: Block A6 drives outputs (ERR_INT_REG, NORMAL_INT_REG, RESP_1_REG, STATUS_REG, ack_out, cmd_out, go_idle_o, req_out, settings) using only nonblocking assignments. If the reference testbench samples on clock edges, this will cause edge_active sampling mismatches. Consider using blocking assignments (=) for output signals in sequential always blocks.
- Required include: `sd_defines.v`
- Ownership signal: `CMDI`
- Ownership signal: `WORD_SELECT`
- Ownership signal: `CICE`
- Ownership signal: `CRCE`
- Ownership signal: `RTS`
- Ownership signal: `dat_ava`
- Ownership signal: `crc_valid`
- Ownership signal: `command_index_mismatch`

## How To Use

- Read fragments, fragment contracts, spec, global defines, and KG child context before drafting.
- Preserve single-owner semantics for status/control outputs when possible.
- Re-run static structure checks and lint before commit.
