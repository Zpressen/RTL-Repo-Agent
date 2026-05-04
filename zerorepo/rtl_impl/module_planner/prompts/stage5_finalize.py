SYSTEM_ROLE = "You are an RTL module planning summarizer."

EXAMPLE_OUTPUT = """
{
  "task_id": "aes_demo_001",
  "summary": "Selected a balanced modularization with 4 primary modules.",
  "modules": [
    {
      "module_name": "aes_cipher_top",
      "role": "top orchestrator",
      "boundary_authority": "explicit_from_spec",
      "responsibilities": ["Top-level control", "Submodule wiring"],
      "interfaces": ["clk", "rst", "ld", "done", "key", "text_in", "text_out"],
      "depends_on": ["aes_key_expand_128", "aes_round_datapath"],
      "optional": false,
      "evidence_ru_ids": ["RU_01", "RU_02"]
    }
  ],
  "design_rationale": [
    "Preserves explicit key-expansion structure.",
    "Separates round datapath from orchestration."
  ],
  "codegen_hints": [
    "Implement leaf submodules first.",
    "Implement the main datapath next.",
    "Integrate and wire the top module last."
  ]
}
""".strip()


def get_output_schema_hint() -> str:
    return (
        "Return JSON with task_id, summary, modules, design_rationale, and codegen_hints. "
        "codegen_hints must contain at least 3 items."
    )


def build_prompt(
    task_id: str,
    ru_json: str,
    critic_json: str,
    chosen_evaluation_json: str,
    chosen_candidate_json: str,
    stage_context: str = "",
) -> str:
    return f"""
Summarize the chosen RTL module plan into the final planning artifact.

Rules:
- task_id must be `{task_id}`.
- Keep module responsibilities concise and implementation-oriented.
- Preserve the chosen candidate's module count and module identities.
- Preserve the top module identity exactly when it is explicit in the chosen candidate.
- Do not describe `invented_for_convenience` modules as if they were explicit spec boundaries.
- Explicitly distinguish spec-explicit boundaries from inferred boundaries in the rationale.
- If shortlist or pairwise tie-break information is present, reflect the real decision reason rather than inventing a new one.
- Provide at least 3 codegen_hints describing a sensible implementation order.

Responsibility units:
{ru_json}

Critic result:
{critic_json}

Chosen candidate evaluation detail:
{chosen_evaluation_json}

Chosen candidate:
{chosen_candidate_json}

Additional stage context:
{stage_context or "None"}

{get_output_schema_hint()}

Example output:
{EXAMPLE_OUTPUT}
""".strip()
