SYSTEM_ROLE = """
You bind global temporal facts to an already fixed RTL repository architecture.

Do not add, remove, rename, split, or merge modules. Produce abstract module responsibilities,
cross-module timing transfers, and cycle obligations only. Do not generate physical RTL signals,
blocks, code, or an implementation state machine.
Return one architecture_timing_contract_v1 JSON object and no prose.
""".strip()


VALID_JSON_EXAMPLE = r"""
{
  "schema_version": "architecture_timing_contract_v1",
  "task_id": "example_task",
  "input_fingerprint": "",
  "planning_status": "complete",
  "degradation_reasons": [],
  "module_set": ["producer", "consumer"],
  "architecture_logical_objects": ["payload", "result"],
  "module_assignments": [
    {
      "module": "producer",
      "owns_logical_state": [],
      "handles_event_ids": ["EV_START"],
      "handles_phase_ids": ["PH_RUN"]
    },
    {
      "module": "consumer",
      "owns_logical_state": ["result"],
      "handles_event_ids": ["EV_DONE"],
      "handles_phase_ids": ["PH_RUN"]
    }
  ],
  "cross_module_transfers": [
    {
      "id": "XFER_PAYLOAD",
      "producer": "producer",
      "consumer": "consumer",
      "logical_object": "payload",
      "delivery": "REGISTERED",
      "visible_at": "POST_EDGE",
      "sampled_at": "PRE_EDGE",
      "required_cycle_offset": 1,
      "source_temporal_ids": ["PH_RUN"]
    }
  ],
  "module_obligations": [
    {
      "id": "OBL_CONSUME",
      "module": "consumer",
      "event_id": "EV_DONE",
      "phase_id": "PH_RUN",
      "reads": [
        {
          "logical_object": "payload",
          "logical_value_tag": "",
          "at": "PRE_EDGE"
        }
      ],
      "writes": [
        {
          "logical_object": "result",
          "logical_value_tag": "",
          "at": "POST_EDGE"
        }
      ],
      "combinational_outputs": [],
      "latency_cycles": 1,
      "guard": "",
      "source_temporal_ids": ["EV_DONE", "PH_RUN"]
    }
  ],
  "assumptions": []
}
""".strip()


def build_prompt(
    *,
    task_id: str,
    temporal_facts_json: str,
    repo_skeleton_json: str,
    global_logical_objects_json: str = "[]",
    stage_context: str = "",
) -> str:
    return f"""
Create the architecture-level temporal contract for task `{task_id}`.

Required top-level fields:
- schema_version: "architecture_timing_contract_v1"
- task_id: "{task_id}"
- input_fingerprint: ""
- planning_status: "complete"
- degradation_reasons: []
- module_set: exactly the modules from the repository skeleton, in generation order
- architecture_logical_objects: architecture-local logical object names not already declared globally
- module_assignments
- cross_module_transfers
- module_obligations
- assumptions

Exact object fields:
- module_assignments[]:
  - module
  - owns_logical_state: array of logical object names
  - handles_event_ids: array of existing event IDs
  - handles_phase_ids: array of existing phase IDs
- cross_module_transfers[]:
  - id, producer, consumer, logical_object
  - delivery: REGISTERED or COMBINATIONAL
  - visible_at, sampled_at: PRE_EDGE, POST_EDGE, or COMB
  - required_cycle_offset: non-negative integer
  - source_temporal_ids: non-empty array of existing temporal IDs
- module_obligations[]:
  - id, module, event_id, phase_id
  - reads, writes, combinational_outputs: arrays of timing access objects
  - latency_cycles: non-negative integer or null
  - guard: string, using "" when absent
  - source_temporal_ids: non-empty array of existing temporal IDs
- Each timing access object:
  - logical_object: declared global or architecture-local logical object
  - logical_value_tag: existing global value tag, or "" when no tag applies
  - at: PRE_EDGE, POST_EDGE, or COMB
- assumptions: array of strings

Rules:
1. module_set must exactly equal the existing module set. Do not redesign architecture.
2. module_assignments must contain exactly one entry for every module.
3. Assign ownership only where the temporal facts or module responsibilities justify it.
4. Every logical object used by an assignment, transfer, or obligation must either appear in
   GLOBAL_LOGICAL_OBJECTS or be declared once in architecture_logical_objects.
5. Architecture-local objects may represent cross-module data, control, status, or addresses when
   justified by the fixed repository responsibilities. They are logical names, not Verilog signals.
6. For a registered value produced at POST_EDGE and consumed at PRE_EDGE, set
   required_cycle_offset to 1 unless source facts establish another alignment.
7. Give every transfer and obligation a unique stable ID.
8. Every transfer and obligation must cite at least one source_temporal_id.
9. Do not invent physical signal names or block IDs.
10. Preserve unresolved choices as assumptions; do not call for architecture repair.
11. Use the exact field name required_cycle_offset. Do not use cycle_offset.
12. Return JSON only, with no descriptive or interface-only fields outside this schema.

Complete valid JSON example:
{VALID_JSON_EXAMPLE}

[GLOBAL_LOGICAL_OBJECTS]
{global_logical_objects_json}

[GLOBAL_TEMPORAL_FACTS]
{temporal_facts_json}

[FIXED_REPO_SKELETON]
{repo_skeleton_json}

[STAGE_CONTEXT]
{stage_context or "None"}
""".strip()
