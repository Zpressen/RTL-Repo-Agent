---
memory_id: merge_sd_bd_lint_pass
type: merge_rule
stage: stage6_merge
description: "sd_bd: Stage6 merge warning; Output block is not visibly driven by parsed always/assign blocks."
module: sd_bd
module_family: sdc
signals:
  - free_bd
  - bd_mem_0
  - bd_mem_1
  - bd_mem_10
  - bd_mem_11
  - bd_mem_12
  - bd_mem_13
  - bd_mem_14
  - bd_mem_15
  - bd_mem_16
  - bd_mem_17
  - bd_mem_18
failure_type: ""
alignment: ""
outcome: lint_pass
confidence: 0.72
verified_by:
  - stage6_static_check
  - lint
source_artifacts:
  - merge_reports/sd_bd_merge_report.json
---

## Pattern

Stage6 merge for `sd_bd` produced outcome `lint_pass`.

## Evidence

- Static warning: Output block is not visibly driven by parsed always/assign blocks.
- Required include: `sd_defines.v`
- Ownership signal: `free_bd`
- Ownership signal: `bd_mem_0`
- Ownership signal: `bd_mem_1`
- Ownership signal: `bd_mem_10`
- Ownership signal: `bd_mem_11`
- Ownership signal: `bd_mem_12`
- Ownership signal: `bd_mem_13`
- Ownership signal: `bd_mem_14`

## How To Use

- Read fragments, fragment contracts, spec, global defines, and KG child context before drafting.
- Preserve single-owner semantics for status/control outputs when possible.
- Re-run static structure checks and lint before commit.
