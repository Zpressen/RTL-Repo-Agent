FACTS_SYSTEM_ROLE = (
    "You extract explicit RTL specification facts into a flexible fact ledger. "
    "Do not infer hierarchy, missing ports, or implementation choices."
)
TOP_INTERFACE_SYSTEM_ROLE = (
    "You extract the complete explicit top-level RTL interface from authoritative port sections. "
    "Do not invent, omit, rename, or reinterpret ports."
)
SYSTEM_ROLE = FACTS_SYSTEM_ROLE

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

FACT_LEDGER_EXAMPLE = """
{
  "fact_ledger": {
    "source_files": ["/abs/path/aes_cipher_top.md"],
    "facts": [
      {
        "fact_id": "",
        "module": "aes_cipher_top",
        "category": "module_identity",
        "subject": "aes_cipher_top",
        "predicate": "is_top_module",
        "object": {"module": "aes_cipher_top"},
        "source_kind": "explicit_text",
        "text_grounding": [
          {
            "source_md_file": "/abs/path/aes_cipher_top.md",
            "section_path": "AES Cipher > Introduction",
            "start_line_anchor": "The aes_cipher_top module is the core control module",
            "end_line_anchor": "The aes_cipher_top module is the core control module"
          }
        ],
        "image_grounding": [],
        "notes": ""
      },
      {
        "fact_id": "",
        "module": "aes_cipher_top",
        "category": "interface",
        "subject": "clk",
        "predicate": "is_port",
        "object": {
          "name": "clk",
          "direction": "input",
          "width": "1",
          "role": "clock",
          "meaning": "Clock signal"
        },
        "source_kind": "table_row",
        "text_grounding": [
          {
            "source_md_file": "/abs/path/aes_cipher_top.md",
            "section_path": "AES Cipher > Interface",
            "start_line_anchor": "| clk | input | 1 | Clock signal |",
            "end_line_anchor": "| clk | input | 1 | Clock signal |"
          }
        ],
        "image_grounding": [],
        "notes": ""
      },
      {
        "fact_id": "",
        "module": "aes_cipher_top",
        "category": "resource_requirement",
        "subject": "SubBytes",
        "predicate": "uses_parallel_units",
        "object": {
          "unit": "S-box",
          "count": 16,
          "purpose": "process all state matrix bytes simultaneously"
        },
        "source_kind": "explicit_text",
        "text_grounding": [
          {
            "source_md_file": "/abs/path/aes_cipher_top.md",
            "section_path": "AES Cipher > SubBytes Transformation",
            "start_line_anchor": "16 parallel S-box units",
            "end_line_anchor": "Process all state matrix bytes simultaneously"
          }
        ],
        "image_grounding": [],
        "notes": "Do not infer aes_cipher_top instantiates aes_sbox in Stage 1; keep this as a resource fact."
      },
      {
        "fact_id": "",
        "module": "aes_cipher_top",
        "category": "data_dependency",
        "subject": "AddRoundKey",
        "predicate": "uses_provider_output",
        "object": {
          "data": "round key",
          "provider": "key expansion module"
        },
        "source_kind": "explicit_text",
        "text_grounding": [
          {
            "source_md_file": "/abs/path/aes_cipher_top.md",
            "section_path": "AES Cipher > AddRoundKey Transformation",
            "start_line_anchor": "Round key provided by key expansion module",
            "end_line_anchor": "Round key provided by key expansion module"
          }
        ],
        "image_grounding": [],
        "notes": "Do not infer key expansion module ports in Stage 1."
      }
    ],
    "ambiguous_items": []
  }
}
""".strip()

def _shared_prompt_prefix(*, round_name: str, current_contracts_json: str, stage_context: str) -> str:
    return f"""
Stage1 round: {round_name}

Rules:
- Extract only facts directly supported by the provided spec text.
- The provided markdown is one batch of the full repository specification, not necessarily the complete repository.
- Emit complete module-local facts only for modules whose primary specification appears in this batch.
- If this batch mentions modules whose primary specification is outside the batch, record them only as referenced submodules or relationship candidates, not as full contracts.
- Do not delete, overwrite, or reinterpret previously completed batch results; use existing contracts only for terminology consistency.
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


def build_facts_prompt(
    *,
    document_markdown: str,
    current_contracts_json: str,
    stage_context: str = "",
) -> str:
    return f"""
{_shared_prompt_prefix(round_name="facts", current_contracts_json=current_contracts_json, stage_context=stage_context)}

Return JSON with exactly one key: `fact_ledger`.

Stage 1 now produces a flexible evidence-backed fact ledger. Do not force facts into a rigid contract shape.
Extract explicit facts and clear textual hints from this batch. Do not perform design inference.

Fact object schema:
- fact_id: leave blank; the runner will assign stable IDs.
- module: the module the fact belongs to, or empty for repository/system facts.
- category: free-form string. Prefer these category names when they fit:
  module_identity, interface, register, state_machine, control_behavior, datapath,
  timing, resource_requirement, data_dependency, mapping_rule, algorithm_step,
  special_case, open_question.
- subject: concrete signal, module, state, datapath step, resource, or behavior.
- predicate: concise relation/action such as is_port, has_width, uses_parallel_units, transitions_to.
- object: JSON object with the extracted attributes. Keep useful details here instead of inventing new schema fields.
- source_kind: one of explicit_text, table_row, figure_text, section_heading, ambiguous_text.
- text_grounding: grounding objects supporting this fact.
- image_grounding: leave empty unless image-derived text is represented.
- notes: short clarification when useful.

Important boundaries:
- Extract "16 parallel S-box units" as a resource_requirement fact. Do not infer a parent-child hierarchy.
- Extract "round key provided by key expansion module" as a data_dependency fact. Do not infer an instantiation relation.
- Extract only explicitly listed ports. Do not infer missing child module ports.
- Only create hierarchy/instantiation-like facts when the text explicitly says instantiates, contains, includes, is composed of, or an equivalent direct structural statement.
- Put unclear but potentially useful text into `ambiguous_items`, not into a forced contract field.

Every fact and ambiguous item must include at least one grounding object.
If no facts are present, return an empty fact_ledger with source_files populated when possible.

Example:
{FACT_LEDGER_EXAMPLE}

Current batch markdown source:
{document_markdown}
""".strip()


def build_top_interface_prompt(
    *,
    top_module: str,
    port_sections_markdown: str,
    expected_ports_json: str,
    current_contracts_json: str,
    stage_context: str = "",
) -> str:
    return f"""
Stage1 round: top_interface

Extract exactly one complete interface contract for top module \u0060{top_module}\u0060.

Hard rules:
- Return valid JSON with exactly one key: \u0060interface_contract\u0060.
- \u0060interface_contract.module\u0060 must be \u0060{top_module}\u0060.
- Include every port listed in Expected explicit ports exactly once.
- Preserve each port name, direction, and width exactly as specified.
- Do not add ports that are not present in the supplied authoritative sections.
- Optional or macro-controlled ports are still interface ports and must be included.
- Module-level \u0060text_grounding\u0060 must cite the supplied interface sections.
- Do not put grounding fields inside individual ports or parameters.
- Use empty lists or strings for unsupported metadata; never guess it.

Interface contract schema:
- module
- ports: list of name, direction, width, role, active, meaning
- params: list of name, value, meaning
- clock, reset, reset_polarity
- handshakes, parameter_constraints, bus_roles
- text_grounding, image_grounding

Expected explicit ports:
{expected_ports_json}

Authoritative top-level interface sections:
{port_sections_markdown}

Current contracts context:
{current_contracts_json}

Additional stage context:
{stage_context or "None"}
""".strip()
