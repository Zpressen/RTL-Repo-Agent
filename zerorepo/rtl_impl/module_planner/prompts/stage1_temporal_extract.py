SYSTEM_ROLE = """
You extract a small, explicit set of global cycle-level temporal facts from RTL specifications.

Do not plan modules and do not generate RTL. Preserve ambiguity instead of choosing a silent
interpretation. Use only a single clock domain in v1. Conditions and guards remain plain strings.
Return one JSON object following global_temporal_facts_v1 and no prose.
""".strip()


VALID_JSON_EXAMPLE = r"""
{
  "schema_version": "global_temporal_facts_v1",
  "task_id": "example_task",
  "input_fingerprint": "",
  "planning_status": "complete",
  "degradation_reasons": [],
  "clock": {
    "name": "clk",
    "edge": "posedge"
  },
  "reset": {
    "name": "rst_n",
    "polarity": "active_low",
    "kind": "asynchronous"
  },
  "events": [
    {
      "id": "EV_LOAD",
      "name": "load_request",
      "kind": "start",
      "trigger": "rise(ld)",
      "guard": "",
      "text_grounding": [
        {
          "source_md_file": "example_spec.md",
          "section_path": "2. Timing",
          "start_line_anchor": "",
          "end_line_anchor": ""
        }
      ]
    },
    {
      "id": "EV_DONE",
      "name": "completion",
      "kind": "completion",
      "trigger": "done == 1",
      "guard": "",
      "text_grounding": [
        {
          "source_md_file": "example_spec.md",
          "section_path": "2. Timing",
          "start_line_anchor": "",
          "end_line_anchor": ""
        }
      ]
    }
  ],
  "phases": [
    {
      "id": "PH_PROCESS",
      "name": "PROCESS",
      "order": 0,
      "trigger_event_id": "EV_LOAD",
      "cycles": 1,
      "guard": "",
      "text_grounding": [
        {
          "source_md_file": "example_spec.md",
          "section_path": "2. Timing",
          "start_line_anchor": "",
          "end_line_anchor": ""
        }
      ]
    }
  ],
  "latency_constraints": [
    {
      "id": "LAT_LOAD_DONE",
      "start_event_id": "EV_LOAD",
      "end_event_id": "EV_DONE",
      "cycles": 1,
      "counting_basis": "edge_distance",
      "raw_statement": "done is asserted one clock edge after ld",
      "status": "resolved",
      "text_grounding": [
        {
          "source_md_file": "example_spec.md",
          "section_path": "2. Timing",
          "start_line_anchor": "",
          "end_line_anchor": ""
        }
      ]
    }
  ],
  "logical_value_sequences": [
    {
      "object": "state",
      "tags": ["State0", "State1"],
      "text_grounding": [
        {
          "source_md_file": "example_spec.md",
          "section_path": "3. Operation",
          "start_line_anchor": "",
          "end_line_anchor": ""
        }
      ]
    }
  ],
  "relations": [
    {
      "id": "REL_PROCESS_DONE",
      "source_id": "PH_PROCESS",
      "target_id": "EV_DONE",
      "relation": "NEXT_EDGE",
      "delay_cycles": null,
      "guard": "",
      "text_grounding": [
        {
          "source_md_file": "example_spec.md",
          "section_path": "2. Timing",
          "start_line_anchor": "",
          "end_line_anchor": ""
        }
      ]
    }
  ],
  "invariants": [
    {
      "id": "INV_PROCESS_RESULT",
      "statement": "The process phase produces State1.",
      "event_id": "",
      "phase_id": "PH_PROCESS",
      "logical_object": "state",
      "required_value_tag": "State1",
      "operation": "process",
      "bypass_operations": [],
      "guard": "",
      "text_grounding": [
        {
          "source_md_file": "example_spec.md",
          "section_path": "3. Operation",
          "start_line_anchor": "",
          "end_line_anchor": ""
        }
      ]
    }
  ],
  "ambiguities": [
    {
      "id": "AMB_CYCLE_COUNT",
      "statement": "The document uses two possible cycle-counting bases.",
      "alternatives": ["edge distance", "inclusive cycle count"],
      "related_ids": ["LAT_LOAD_DONE"],
      "text_grounding": [
        {
          "source_md_file": "example_spec.md",
          "section_path": "2. Timing",
          "start_line_anchor": "",
          "end_line_anchor": ""
        }
      ]
    }
  ],
  "unsupported_features": [
    {
      "id": "UNSUP_SECOND_CLOCK",
      "feature": "multiple clock domains",
      "reason": "The v1 temporal planner supports only one clock domain.",
      "text_grounding": [
        {
          "source_md_file": "example_spec.md",
          "section_path": "1. Interface",
          "start_line_anchor": "",
          "end_line_anchor": ""
        }
      ]
    }
  ]
}
""".strip()


def build_prompt(*, task_id: str, source_specs_json: str, stage_context: str = "") -> str:
    return f"""
Extract global temporal requirements for task `{task_id}`.

Return JSON with these top-level fields:
- schema_version: "global_temporal_facts_v1"
- task_id: "{task_id}"
- input_fingerprint: ""
- planning_status: "complete"
- degradation_reasons: []
- clock: name and edge (posedge, negedge, or unspecified)
- reset: name, polarity, and kind
- events: stable IDs plus name, kind, trigger, guard, text_grounding
- phases: stable IDs plus name, order, trigger_event_id, cycles, guard, text_grounding
- latency_constraints: start/end event IDs, cycles, counting_basis, raw_statement, status
- logical_value_sequences: logical object and explicit value tags
- relations: SAME_EDGE, NEXT_EDGE, EXACT_CYCLES, or BEFORE
- invariants: operation/phase/value-tag obligations
- ambiguities
- unsupported_features

Rules:
1. Extract only facts supported by the source text.
2. Keep IDs globally unique and stable-looking, for example EV_LD, PH_FINAL, LAT_LD_DONE, INV_FINAL_KEY.
3. Create event IDs before referencing them from phases or latency constraints.
4. Use edge_distance only when the text clearly describes distance between clock edges.
5. If two statements use different counting conventions, retain both evidence statements and create an ambiguity.
6. Expand short finite logical sequences when the spec identifies versions, such as RK0 through RK10.
7. Do not create modules, physical signal names, blocks, state machines, or implementation counters.
8. Do not parse arbitrary Boolean guards; copy them as strings.
9. If multiple clocks or CDC behavior are required, record an unsupported feature.
10. Every grounded item should cite source_md_file and section_path when available.
11. Empty categories must be returned as empty arrays.
12. `text_grounding` is always an array, even when there is only one source.
13. `guard`, `event_id`, `phase_id`, `logical_object`, `required_value_tag`, and `operation`
    must use an empty string when absent. Do not use null for string fields.
14. `cycles` and `delay_cycles` may use null when the numeric value is unknown.
15. Event `kind` describes the event's transaction role, not its trigger syntax.
16. Return JSON only.

Allowed enum values:
- clock.edge: "posedge" | "negedge" | "unspecified"
- reset.polarity: "active_high" | "active_low" | "unspecified"
- reset.kind: "synchronous" | "asynchronous" | "unspecified"
- events[].kind: "start" | "completion" | "reset" | "status" | "other"
- latency_constraints[].counting_basis: "edge_distance" | "inclusive_cycles" | "unspecified"
- latency_constraints[].status: "resolved" | "ambiguous" | "unsupported"
- relations[].relation: "SAME_EDGE" | "NEXT_EDGE" | "EXACT_CYCLES" | "BEFORE"

Important formatting constraints:
- Do not use "signal_edge", "signal_level", or "condition" as events[].kind.
  Put edge/level/condition syntax in events[].trigger.
- Do not return a single object for text_grounding; always wrap it in a JSON array.
- Do not use null for guard or other string fields.
- EXACT_CYCLES requires a non-negative integer delay_cycles.

Complete valid JSON example:
{VALID_JSON_EXAMPLE}

[SOURCE_SPECS]
{source_specs_json}

[STAGE_CONTEXT]
{stage_context or "None"}
""".strip()
