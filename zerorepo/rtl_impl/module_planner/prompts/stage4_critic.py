SYSTEM_ROLE = "You are an RTL module planning critic."

EXAMPLE_OUTPUT = """
{
  "candidate_scores": [
    {
      "candidate_id": "BALANCED_2",
      "plan_style": "balanced",
      "spec_prior_fidelity": 9.1,
      "coupling_preservation": 8.8,
      "interface_naturalness": 8.4,
      "codegen_feasibility": 9.0,
      "granularity_economy": 8.7,
      "pros": ["Preserves explicit AES submodule names", "Avoids over-fragmenting the round datapath"],
      "cons": ["Top still keeps some orchestration burden"],
      "risk_flags": ["Round-control glue remains moderately dense"]
    }
  ],
  "recommended_candidate_id": "BALANCED_2"
}
""".strip()


def get_output_schema_hint() -> str:
    return (
        "Return JSON with keys `candidate_scores` and `recommended_candidate_id`. "
        "Each candidate score item must include candidate_id, plan_style, "
        "spec_prior_fidelity, coupling_preservation, interface_naturalness, "
        "codegen_feasibility, granularity_economy, pros, cons, risk_flags. "
        "Do not include a `score` field; the program will compute it locally."
    )


def build_prompt(
    ru_json: str,
    merge_hint_json: str,
    candidate_json: str,
    weight_json: str,
    stage_context: str = "",
) -> str:
    return f"""
Critique the candidate RTL module plans and recommend one.

Score only with these five hard dimensions:
1. Spec Prior Fidelity
2. Coupling Preservation
3. Interface Naturalness
4. Codegen Feasibility
5. Granularity Economy

Rules:
- Score each dimension from 0 to 10.
- Do not output a `score` field. The program will compute the weighted total locally using the provided fixed weights.
- pros, cons, and risk_flags must all be non-empty.
- recommended_candidate_id must refer to one of the provided candidates.
- Critique concrete fidelity, coupling, interface, and codegen consequences. Do not give vague overall impressions.
- Penalize candidates that rename explicit submodules, split strongly coupled round/state logic unnaturally, or invent interfaces not grounded in the spec.
- Do not penalize a candidate merely for introducing inferred modules when those modules are justified by strong structural evidence and are labeled `strong_implicit` or `invented_for_convenience`.
- Do penalize inferred modules that are mislabeled as explicit spec boundaries, or that lack a believable interface/state/timing boundary.
- Spec Prior Fidelity must explicitly check:
  - whether the top module name is preserved
  - whether explicit submodule names are preserved
  - whether explicit algorithm steps and responsibilities are still covered
- For any module with `boundary_authority = invented_for_convenience`, ask whether it truly has an independent interface/state/timing boundary; if not, penalize it and call it out in cons or risk_flags.

Responsibility units:
{ru_json}

Merge hints:
{merge_hint_json}

Candidates:
{candidate_json}

Fixed score weights:
{weight_json}

Additional stage context:
{stage_context or "None"}

{get_output_schema_hint()}

Example output:
{EXAMPLE_OUTPUT}
""".strip()
