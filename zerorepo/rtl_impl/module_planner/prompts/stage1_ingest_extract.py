STRUCTURE_SYSTEM_ROLE = "You extract explicit RTL repository structure facts only. If the spec does not state a fact, leave it blank."
INTERFACE_SYSTEM_ROLE = "You extract explicit RTL module interface facts only. If the spec does not state a fact, leave it blank."
TIMING_SYSTEM_ROLE = (
    "You are extracting timing semantics from an RTL module specification. "
    "Extract only explicit timing facts and record unclear timing details as underspecified."
)
CONTROL_SYSTEM_ROLE = "You extract explicit RTL control facts only. If the spec does not state a fact, leave it blank."
DATAPATH_SYSTEM_ROLE = "You extract explicit RTL datapath facts only. If the spec does not state a fact, leave it blank."
PLANNING_FACTS_SYSTEM_ROLE = "You extract explicit RTL planning facts only. If the spec does not state a fact, leave it blank."
SYSTEM_ROLE = STRUCTURE_SYSTEM_ROLE

TEXT_GROUNDING_EXAMPLE = """
{
  "source_md_file": "/abs/path/packet_router_top.md",
  "section_path": "Packet Router Specification > 6. Submodules",
  "start_line_anchor": "The top module instantiates route_table and output_scheduler.",
  "end_line_anchor": "The top module instantiates route_table and output_scheduler."
}
""".strip()

IMAGE_GROUNDING_EXAMPLE = """
{
  "image_id": "IMG_001",
  "image_file": "/abs/path/packet_router_fsm.png",
  "visible_text": ["IDLE", "LOOKUP", "FORWARD", "DONE"]
}
""".strip()

STRUCTURE_EXAMPLE = """
{
  "structure_contract": {
    "system": "Packet Router Repository",
    "top_module": "packet_router_top",
    "files": ["packet_router_top.v", "route_table.v", "output_scheduler.v"],
    "modules": ["packet_router_top", "route_table", "output_scheduler"],
    "file_map": {
      "packet_router_top.v": ["packet_router_top"],
      "route_table.v": ["route_table"],
      "output_scheduler.v": ["output_scheduler"]
    },
    "hierarchy": [
      {
        "parent": "packet_router_top",
        "child": "route_table",
        "text_grounding": [
          {
            "source_md_file": "/abs/path/packet_router_top.md",
            "section_path": "Packet Router Specification > 6. Submodules",
            "start_line_anchor": "The top module instantiates route_table and output_scheduler.",
            "end_line_anchor": "The top module instantiates route_table and output_scheduler."
          }
        ],
        "image_grounding": []
      }
    ],
    "instantiation_graph": [],
    "generation_order_candidate": [],
    "text_grounding": [
      {
        "source_md_file": "/abs/path/packet_router_top.md",
        "section_path": "Packet Router Specification > 1. Overview",
        "start_line_anchor": "Top module: packet_router_top",
        "end_line_anchor": "Modules: packet_router_top, route_table, output_scheduler"
      }
    ],
    "image_grounding": []
  }
}
""".strip()

INTERFACE_EXAMPLE = """
{
  "interface_contracts": [
    {
      "module": "packet_router_top",
      "ports": [
        {
          "name": "in_valid",
          "direction": "input",
          "width": "1",
          "role": "packet_valid",
          "active": "",
          "meaning": "input packet valid flag"
        },
        {
          "name": "clk",
          "direction": "input",
          "width": "1",
          "role": "clock",
          "active": "",
          "meaning": "clock input"
        }
      ],
      "params": [],
      "clock": "clk",
      "reset": "rst",
      "reset_polarity": "high",
      "handshakes": ["in_valid to out_valid"],
      "parameter_constraints": [],
      "bus_roles": [],
      "text_grounding": [
        {
          "source_md_file": "/abs/path/packet_router_top.md",
          "section_path": "Packet Router Specification > 2. Interface",
          "start_line_anchor": "The module exposes clk, rst, in_valid, in_data, out_valid, and out_port.",
          "end_line_anchor": "The module exposes clk, rst, in_valid, in_data, out_valid, and out_port."
        }
      ],
      "image_grounding": []
    }
  ]
}
""".strip()

TIMING_EXAMPLE = """
{
  "timing_contracts": [
    {
      "module": "packet_router_top",
      "clocking": {
        "clock": "clk",
        "update_edge": "rising clock edge",
        "statement": "in_valid is sampled on the rising clock edge"
      },
      "reset_behavior": {
        "signal": "rst",
        "active": "high",
        "effect": "returns the router control to IDLE"
      },
      "registered_objects": [
        {
          "name": "route_state",
          "timing_role": "registered state",
          "timing": "updated on the rising clock edge and held between cycles"
        }
      ],
      "phase_timing": [
        {
          "phase": "DONE",
          "timing": "out_valid is asserted for one cycle after forwarding completes"
        }
      ],
      "timing_rules": [
        "in_valid is sampled on the rising clock edge",
        "out_valid is asserted for one cycle after forwarding completes",
        "route decode remains combinational between registered updates"
      ],
      "underspecified": [
        "reset release timing is not stated"
      ]
    }
  ]
}
""".strip()

TIMING_NEGATIVE_EXAMPLE = """
{
  "timing_contracts": []
}
""".strip()

CONTROL_EXAMPLE = """
{
  "control_contracts": [
    {
      "module": "packet_router_top",
      "abstract_states": ["IDLE", "LOOKUP", "FORWARD", "DONE"],
      "transitions": [
        {
          "from_state": "IDLE",
          "to_state": "LOOKUP",
          "condition": "in_valid is asserted",
          "text_grounding": [
            {
              "source_md_file": "/abs/path/packet_router_top.md",
              "section_path": "Packet Router Specification > 5. Control",
              "start_line_anchor": "Transition: IDLE -> LOOKUP when in_valid is asserted.",
              "end_line_anchor": "Transition: IDLE -> LOOKUP when in_valid is asserted."
            }
          ]
        }
      ],
      "control_signals": [
        {
          "name": "out_valid",
          "meaning": "forwarding result valid pulse",
          "text_grounding": [
            {
              "source_md_file": "/abs/path/packet_router_top.md",
              "section_path": "Packet Router Specification > 5. Control",
              "start_line_anchor": "out_valid means forwarding result valid pulse.",
              "end_line_anchor": "out_valid means forwarding result valid pulse."
            }
          ]
        }
      ],
      "bypass_conditions": [],
      "exception_conditions": [],
      "counter_rules": [
        {
          "counter": "lookup_cnt",
          "rule": "increments by one on each successful route lookup",
          "text_grounding": [
            {
              "source_md_file": "/abs/path/packet_router_top.md",
              "section_path": "Packet Router Specification > 5. Control",
              "start_line_anchor": "lookup_cnt increments by one on each successful route lookup.",
              "end_line_anchor": "lookup_cnt increments by one on each successful route lookup."
            }
          ]
        }
      ],
      "text_grounding": [
        {
          "source_md_file": "/abs/path/packet_router_top.md",
          "section_path": "Packet Router Specification > 5. Control",
          "start_line_anchor": "States: IDLE, LOOKUP, FORWARD, DONE",
          "end_line_anchor": "States: IDLE, LOOKUP, FORWARD, DONE"
        }
      ],
      "image_grounding": []
    }
  ]
}
""".strip()

DATAPATH_EXAMPLE = """
{
  "datapath_contracts": [
    {
      "module": "packet_router_top",
      "input_data": ["in_header", "in_payload"],
      "main_flow": ["header_decode", "route_lookup", "port_select", "output_forward"],
      "intermediate_objects": [
        {
          "name": "route_index",
          "role": "selected route table entry index",
          "text_grounding": [
            {
              "source_md_file": "/abs/path/packet_router_top.md",
              "section_path": "Packet Router Specification > 6. Datapath",
              "start_line_anchor": "route_index stores the selected route table entry index.",
              "end_line_anchor": "route_index stores the selected route table entry index."
            }
          ]
        }
      ],
      "path_annotations": [],
      "registered_paths": [],
      "combinational_paths": [],
      "special_paths": [],
      "text_grounding": [
        {
          "source_md_file": "/abs/path/packet_router_top.md",
          "section_path": "Packet Router Specification > 6. Datapath",
          "start_line_anchor": "Main flow: header_decode, route_lookup, port_select, output_forward",
          "end_line_anchor": "Main flow: header_decode, route_lookup, port_select, output_forward"
        }
      ],
      "image_grounding": []
    }
  ]
}
""".strip()

PLANNING_FACTS_EXAMPLE = """
{
  "planning_facts": [
    {
      "module": "packet_router_top",
      "registers": [
        {
          "name": "route_index_r",
          "width": "4",
          "role": "selected route table index register"
        }
      ],
      "state_names": ["IDLE", "LOOKUP", "FORWARD", "DONE"],
      "submodule_facts": [
        {
          "module": "route_table",
          "count": 1,
          "usage": "destination lookup"
        },
        {
          "module": "output_scheduler",
          "count": 1,
          "usage": "egress arbitration"
        }
      ],
      "local_mappings": [
        "in_header[15:12] -> route_index lookup key",
        "header decode output maps to output port selector"
      ],
      "text_grounding": [
        {
          "source_md_file": "/abs/path/packet_router_top.md",
          "section_path": "Packet Router Specification > 6. Datapath",
          "start_line_anchor": "Registers: route_index_r tracks selected route entries.",
          "end_line_anchor": "The module uses route_table and output_scheduler."
        }
      ],
      "image_grounding": []
    }
  ]
}
""".strip()

def _shared_prompt_prefix(*, round_name: str, current_contracts_json: str, stage_context: str) -> str:
    return f"""
Stage1 round: {round_name}

Rules:
- Extract only facts directly supported by the provided spec text.
- If a field is not explicitly supported, leave it blank or empty.
- Do not infer module hierarchy, instantiation, timing, or control semantics from naming style, file names, or diagram layout alone.
- Keep previously generated rounds unchanged. Use them only as context for terminology consistency.
- Return valid JSON only.
- `text_grounding` must be a list of objects, never a list of strings.
- `image_grounding` must be a list of objects, never a list of strings.
- No images are provided in this stage. Leave `image_grounding` empty unless a field is intentionally left as an empty list.
- Use this exact text grounding object shape:
{TEXT_GROUNDING_EXAMPLE}
- Use this exact image grounding object shape:
{IMAGE_GROUNDING_EXAMPLE}

Current contracts.json content:
{current_contracts_json}

Additional stage context:
{stage_context or "None"}
""".strip()


def build_structure_prompt(
    *,
    document_markdown: str,
    current_contracts_json: str,
    stage_context: str = "",
) -> str:
    return f"""
{_shared_prompt_prefix(round_name="structure", current_contracts_json=current_contracts_json, stage_context=stage_context)}

Return JSON with exactly one key: `structure_contract`.

Extract only explicitly stated structure facts:
- system
- top_module
- files
- modules
- file_map
- hierarchy
- instantiation_graph
- generation_order_candidate

For every relationship in `hierarchy` or `instantiation_graph`, include grounding.
If the spec does not explicitly describe a field, leave it empty.
Do not output section-path strings directly inside `text_grounding`; each item must be a grounding object.

Example:
{STRUCTURE_EXAMPLE}

Full markdown source:
{document_markdown}
""".strip()


def build_interface_prompt(
    *,
    document_markdown: str,
    current_contracts_json: str,
    stage_context: str = "",
) -> str:
    return f"""
{_shared_prompt_prefix(round_name="interface", current_contracts_json=current_contracts_json, stage_context=stage_context)}

Return JSON with exactly one key: `interface_contracts`.

Each list item must describe one module-level interface contract.
Extract only explicit facts about:
- module
- ports
- params
- clock
- reset
- reset_polarity
- handshakes
- parameter_constraints
- bus_roles

Put text evidence at the module level:
- `interface_contracts[*].text_grounding` should cover the interface table/section for the module.
- Do not add `text_grounding` inside individual `ports` or `params`.
- If all ports come from the same interface table, cite that table once at the module level instead of repeating evidence per signal.

If no module interface is explicitly described, return an empty list.
Every non-empty interface contract must include at least one grounding object in `text_grounding` or `image_grounding`.

Example:
{INTERFACE_EXAMPLE}

Full markdown source:
{document_markdown}
""".strip()


def build_timing_prompt(
    *,
    document_markdown: str,
    current_contracts_json: str,
    stage_context: str = "",
) -> str:
    return f"""
{_shared_prompt_prefix(round_name="timing", current_contracts_json=current_contracts_json, stage_context=stage_context)}

Return JSON with exactly one key: `timing_contracts`.

Each list item must use this schema exactly:
{{
  "module": "string",
  "clocking": {{}},
  "reset_behavior": {{}},
  "registered_objects": [],
  "phase_timing": [],
  "timing_rules": [],
  "underspecified": []
}}

You are extracting timing semantics from an RTL module specification.

Goal:
Extract only timing-related facts that are explicitly stated in the spec.
Do not infer implementation details that are not directly supported by the text.

Focus on:
- clocking and update edge
- reset behavior only if explicitly stated
- registered objects and their timing roles
- phase/state timing described in the spec
- timing rules such as one-round-per-cycle, synchronous update, combinational blocks, writeback behavior, completion behavior
- explicitly stated timing-related submodule interface meanings

Rules:
1. Be faithful to the text.
2. Do not invent cycle-by-cycle behavior unless the spec explicitly says so.
3. If the spec is unclear, record it in `underspecified`.
4. Prefer concrete textual rules over abstract labels.
5. Keep output concise and structured.

Field guidance:
- `clocking`: use a compact object for stated clock, domain, edge, synchronous/combinational wording, or update style.
- `reset_behavior`: use `{{}}` unless reset timing behavior is explicitly stated.
- `registered_objects`: use short objects that capture the object name and the timing role explicitly stated in the spec.
- `phase_timing`: use short objects for state, stage, or phase timing statements.
- `timing_rules`: use concise textual rules for explicit timing behaviors.
- `underspecified`: use short strings for timing details the spec leaves unclear.

Do not treat the following as timing evidence by themselves:
- signal names alone (`ld`, `start`, `done`, `enable`, `kld`)
- generic control-flow wording without update, hold, visibility, or cycle semantics
- module familiarity or domain knowledge
- figures, layouts, or section titles alone

Timing evidence may appear in:
- interface notes
- register or object descriptions
- state or phase descriptions
- data loading descriptions
- output generation descriptions
- timing constraints
- child module interface descriptions

If a state or phase description explicitly says something is loaded, held, updated, skipped, written back, or made visible in that phase, extract the timing-relevant part.

If timing is explicit but partial, extract the known part and place the missing detail in `underspecified`.
Do not drop a valid fact just because polarity, edge direction, or exact cycle count is only partially described.

Do not emit placeholder or shell contracts.
If a module has no explicit timing facts and no timing-related underspecification worth recording, omit that module from `timing_contracts`.
If no timing facts are explicitly described anywhere, return:
{TIMING_NEGATIVE_EXAMPLE}

Positive example:
{TIMING_EXAMPLE}

Additional positive examples of timing evidence:
- "synchronous loading to state matrix registers"
- "register updates on clock rising edge"
- "pure combinational logic implementation"
- "one round per clock cycle"
- "writeback occurs in the final state"
- "done is asserted for one cycle after completion"

Full markdown source:
{document_markdown}
""".strip()


def build_control_prompt(
    *,
    document_markdown: str,
    current_contracts_json: str,
    stage_context: str = "",
) -> str:
    return f"""
{_shared_prompt_prefix(round_name="control", current_contracts_json=current_contracts_json, stage_context=stage_context)}

Return JSON with exactly one key: `control_contracts`.

Each list item must describe one module-level control contract.
Extract only explicit facts about:
- module
- abstract_states
- transitions
- control_signals
- bypass_conditions
- exception_conditions
- counter_rules

Use the following object shapes:
- `bypass_conditions[*]`: `{{"condition": "...", "text_grounding": [{{...}}]}}`
- `exception_conditions[*]`: `{{"condition": "...", "text_grounding": [{{...}}]}}`
- `counter_rules[*]`: `{{"counter": "...", "rule": "...", "text_grounding": [{{...}}]}}`

If the spec only hints at control without explicit contract detail, leave the unsupported fields empty.
Every non-empty control contract must include at least one grounding object in `text_grounding` or `image_grounding`.

Example:
{CONTROL_EXAMPLE}

Full markdown source:
{document_markdown}
""".strip()


def build_datapath_prompt(
    *,
    document_markdown: str,
    current_contracts_json: str,
    stage_context: str = "",
) -> str:
    return f"""
{_shared_prompt_prefix(round_name="datapath", current_contracts_json=current_contracts_json, stage_context=stage_context)}

Return JSON with exactly one key: `datapath_contracts`.

Each list item must describe one module-level datapath contract.
Extract only explicit facts about:
- module
- input_data
- main_flow
- intermediate_objects
- path_annotations
- registered_paths
- combinational_paths
- special_paths

Do not infer hidden datapath stages from domain knowledge.
Every non-empty datapath contract must include at least one grounding object in `text_grounding` or `image_grounding`.

Example:
{DATAPATH_EXAMPLE}

Full markdown source:
{document_markdown}
""".strip()


def build_planning_facts_prompt(
    *,
    document_markdown: str,
    current_contracts_json: str,
    stage_context: str = "",
) -> str:
    return f"""
{_shared_prompt_prefix(round_name="planning_facts", current_contracts_json=current_contracts_json, stage_context=stage_context)}

Return JSON with exactly one key: `planning_facts`.

Each list item must describe one module-level planning facts contract.
Extract only explicit, local, implementation-helpful facts:
- module
- registers (name, width, role)
- state_names
- submodule_facts (module, count, usage)
- local_mappings

Rules specific to this round:
- Do not infer new facts from previously generated contracts.
- Do not rewrite high-level control summaries into register declarations.
- Do not infer submodule count from hierarchy alone.
- Do not rewrite high-level datapath flow as local mapping rules unless the mapping is explicitly stated.
- If the spec does not explicitly state a field, leave it empty.

Grounding requirements:
- Each non-empty `planning_facts` item must include module-level `text_grounding` (or `image_grounding`, though images are not provided in this stage).
- Do not add per-register or per-state grounding fields.

Example:
{PLANNING_FACTS_EXAMPLE}

Full markdown source:
{document_markdown}
""".strip()
