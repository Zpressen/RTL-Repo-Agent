SYSTEM_ROLE = "You are an RTL module planning pairwise tie-break judge."

EXAMPLE_OUTPUT = """
{
  "winner": "candidate_a",
  "rationale": [
    "Candidate A preserves stronger coupling around the round-control/state-update path.",
    "Candidate B introduces a weaker inferred boundary without enough independent interface evidence."
  ]
}
""".strip()


def get_output_schema_hint() -> str:
    return (
        "Return JSON with keys `winner` and `rationale`. "
        "`winner` must be exactly one of `candidate_a`, `candidate_b`, or `tie`. "
        "`rationale` must be a non-empty list of concrete structural reasons."
    )


def build_prompt(
    *,
    candidate_a_json: str,
    candidate_b_json: str,
    ru_json: str,
    merge_hint_json: str,
    top_module_name: str,
    explicit_submodules_json: str,
    stage_context: str = "",
) -> str:
    return f"""
Break a near-tie between two RTL module planning candidates.

Rules:
- Compare only these two candidates.
- Prefer the candidate with better spec fidelity, stronger coupling preservation, and cleaner codegen structure.
- You may return `tie` if neither candidate is clearly better.
- Ignore presentation style, wording polish, and summary quality. Judge structure only.
- Base your rationale on module boundaries, merge-hint preservation, explicit top/submodule identity, interface naturalness, and implementation feasibility.

Top module name:
`{top_module_name}`

Markdown-explicit submodule names:
{explicit_submodules_json}

Responsibility units:
{ru_json}

Merge hints:
{merge_hint_json}

Candidate A:
{candidate_a_json}

Candidate B:
{candidate_b_json}

Additional stage context:
{stage_context or "None"}

{get_output_schema_hint()}

Example output:
{EXAMPLE_OUTPUT}
""".strip()
