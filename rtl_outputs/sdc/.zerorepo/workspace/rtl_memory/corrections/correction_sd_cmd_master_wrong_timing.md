---
memory_id: correction_sd_cmd_master_wrong_timing
type: planning_correction
stage: planning
description: "sd_cmd_master: One unexplored repair direction: perform an exact line-by-line logic comparison between reference A6 and DUT A6, fix any logic differences f"
module: sd_cmd_master
module_family: sdc
signals: []
failure_type: plan_bug
alignment: ""
outcome: correction
confidence: 0.62
verified_by:
  - record_correction
source_artifacts:
  - /home/mokita/RPG-ZeroRepo/rtl_outputs/sdc/.zerorepo/module_planner/outputs/planning_corrections/correction_journal.jsonl
trigger_signals: []
trigger_failure_type: ""
trigger_alignment: ""
risk_signals: []
patch_pattern: ""
anti_trigger: ""
---

## Problem

One unexplored repair direction: perform an exact line-by-line logic comparison between reference A6 and DUT A6, fix any logic differences found, and THEN attempt full blocking conversion. If the regression from 2207→4246 during full blocking conversion is caused by logic differences (not just scheduling), fixing those differences first could enable a successful blocking conversion.

## Evidence

- Full A6 blocking conversion regressed 2207→4246, suggesting logic differences exist beyond scheduling
- Stable values match at key times, so functional behavior is similar but may differ in edge cases
- Previous comparisons were not exhaustive

## Corrective Rule

{
  "next_strategy": "Compare reference A6 and DUT A6 line by line to find logic differences. Fix any differences found. Then attempt full blocking conversion."
}
