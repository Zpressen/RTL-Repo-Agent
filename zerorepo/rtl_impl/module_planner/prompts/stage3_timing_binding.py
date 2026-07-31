SYSTEM_ROLE = """
You bind an existing module's abstract temporal obligations to its existing skeleton blocks and
planned physical signal names.

Do not change the module architecture or skeleton. Do not add blocks. Do not generate RTL.
Return one module_timing_binding_v1 JSON object and no prose.
""".strip()


VALID_JSON_EXAMPLE = r"""
{
  "schema_version": "module_timing_binding_v1",
  "task_id": "example_task",
  "module": "key_expansion",
  "input_fingerprint": "",
  "signal_bindings": [
    {
      "logical_object": "round_key",
      "physical_signal": "round_key_reg",
      "kind": "register",
      "owner_block_id": "B5",
      "logical_value_tags": ["RK0", "RK1", "RK2"]
    },
    {
      "logical_object": "round_key",
      "physical_signal": "next_round_key",
      "kind": "wire",
      "owner_block_id": "B4",
      "logical_value_tags": ["RK1", "RK2"]
    },
    {
      "logical_object": "round_key",
      "physical_signal": "round_key_out",
      "kind": "output",
      "owner_block_id": "B6",
      "logical_value_tags": ["RK0", "RK1", "RK2"]
    },
    {
      "logical_object": "cipher_key",
      "physical_signal": "key_in",
      "kind": "input",
      "owner_block_id": "",
      "logical_value_tags": ["RK0"]
    }
  ],
  "transfer_bindings": [
    {
      "transfer_id": "TR_ROUND_KEY",
      "endpoint": "producer",
      "physical_signal": "round_key_out",
      "block_id": "B6"
    }
  ],
  "block_obligations": [
    {
      "obligation_id": "OB_KEY_UPDATE",
      "block_id": "B5",
      "reads": [
        {
          "signal": "next_round_key",
          "at": "PRE_EDGE",
          "logical_object": "round_key",
          "logical_value_tag": "RK1"
        }
      ],
      "writes": [
        {
          "signal": "round_key_reg",
          "at": "POST_EDGE",
          "logical_object": "round_key",
          "logical_value_tag": "RK1"
        }
      ],
      "combinational_outputs": [
        {
          "signal": "next_round_key",
          "at": "COMB",
          "logical_object": "round_key",
          "logical_value_tag": "RK1"
        }
      ],
      "guard": "active_round"
    }
  ],
  "assumptions": [
    "key_in is stable at PRE_EDGE when the load event is active"
  ]
}
""".strip()


def build_prompt(
    *,
    task_id: str,
    module_name: str,
    temporal_facts_json: str,
    architecture_slice_json: str,
    module_skeleton_json: str,
    module_spec_context_json: str,
    stage_context: str = "",
) -> str:
    return f"""
Bind timing obligations for module `{module_name}` in task `{task_id}`.

Required top-level fields:
- schema_version: "module_timing_binding_v1"
- task_id: "{task_id}"
- module: "{module_name}"
- input_fingerprint: ""
- signal_bindings
- transfer_bindings
- block_obligations
- assumptions

Exact object fields:
- signal_bindings[]:
  - logical_object: non-empty logical object name from the architecture contract
  - physical_signal: non-empty planned Verilog signal name
  - kind: input, output, register, or wire
  - owner_block_id: existing block ID, or "" when no block owns the signal
  - logical_value_tags: array of logical value tag strings
- transfer_bindings[]:
  - transfer_id: existing cross-module transfer ID
  - endpoint: producer or consumer
  - physical_signal: planned signal or port name
  - block_id: existing block ID, or "" when no block binding is needed
- block_obligations[]:
  - obligation_id: existing module obligation ID
  - block_id: exactly one existing primary owner block
  - reads: array of timing access objects
  - writes: array of timing access objects
  - combinational_outputs: array of timing access objects
  - guard: string, using "" when absent
- Each timing access object:
  - signal: non-empty planned physical signal name
  - at: PRE_EDGE, POST_EDGE, or COMB
  - logical_object: non-empty logical object name
  - logical_value_tag: one tag string, using "" when no specific tag applies
- assumptions: array of strings

Allowed enum values:
- signal_bindings[].kind: "input" | "output" | "register" | "wire"
- transfer_bindings[].endpoint: "producer" | "consumer"
- reads[].at: "PRE_EDGE" | "POST_EDGE" | "COMB"
- writes[].at: "PRE_EDGE" | "POST_EDGE" | "COMB"
- combinational_outputs[].at: "PRE_EDGE" | "POST_EDGE" | "COMB"

Rules:
1. Use only block IDs present in MODULE_SKELETON.
2. Bind every architecture obligation owned by this module exactly once.
3. Bind every related transfer endpoint exactly once with endpoint producer or consumer.
4. Choose stable Verilog-compatible planned signal names.
5. Register state ownership should normally point to a declaration block; registered writes must
   bind to a sequential block.
6. Preserve PRE_EDGE, POST_EDGE, and COMB semantics from the architecture contract.
7. Preserve logical object and logical value tag identity; do not collapse RK3 into an untagged key.
8. If one physical signal carries multiple value versions over time, list all relevant tags in its
   signal binding and preserve the exact tag on each obligation access.
9. Do not add ports, blocks, modules, obligations, or transfers.
10. `signal_bindings` is not a complete module signal inventory. Include only signals needed to
    bind architecture logical objects, module obligations, or cross-module transfers.
11. Do not include clk, reset, control inputs, or unrelated implementation signals unless they are
    explicitly represented by an architecture logical object or required by an obligation/transfer.
12. Never use "internal" as kind. Use "register" for clocked stored state and "wire" for an
    internal combinational value.
13. Do not use null for string or array fields. Use "" for an absent string and [] for an empty list.
14. Use the exact field names shown above. Do not substitute:
    - signal_name for physical_signal
    - direction for kind
    - tags for logical_value_tags or logical_value_tag
    - access or timing for at
    - nested objects for endpoint
15. Each architecture obligation produces exactly one block_obligations entry and one block_id.
    Do not repeat one obligation ID across several blocks. Choose its primary responsible block.
16. Return JSON only.

Complete valid JSON example:
{VALID_JSON_EXAMPLE}

[GLOBAL_TEMPORAL_FACTS]
{temporal_facts_json}

[MODULE_ARCHITECTURE_TIMING_SLICE]
{architecture_slice_json}

[MODULE_SKELETON]
{module_skeleton_json}

[MODULE_SPEC_CONTEXT]
{module_spec_context_json or "None"}

[STAGE_CONTEXT]
{stage_context or "None"}
""".strip()
