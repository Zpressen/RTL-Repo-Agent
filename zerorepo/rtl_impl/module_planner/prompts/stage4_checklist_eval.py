from __future__ import annotations

from ..schemas import CHECKLIST_RUBRIC

SYSTEM_ROLE = "You are an RTL module planning checklist evaluator."

EXAMPLE_OUTPUT = """
{
  "candidate_id": "BALANCED_2",
  "plan_style": "balanced",
  "checklists": {
    "spec_prior_fidelity": [
      {
        "check_id": "SPF-1",
        "answer": "yes",
        "evidence": "The candidate preserves the explicit top module name aes_cipher_top."
      },
      {
        "check_id": "SPF-2",
        "answer": "yes",
        "evidence": "Explicit submodule names aes_key_expand_128 and aes_sbox are preserved."
      },
      {
        "check_id": "SPF-3",
        "answer": "uncertain",
        "evidence": "Most explicit round responsibilities are present, but one special-case detail is underspecified."
      },
      {
        "check_id": "SPF-4",
        "answer": "yes",
        "evidence": "Explicit submodules remain first-class modules rather than wrappers."
      },
      {
        "check_id": "SPF-5",
        "answer": "uncertain",
        "evidence": "One inferred helper boundary is introduced, but it may still be structurally justified."
      },
      {
        "check_id": "SPF-6",
        "answer": "yes",
        "evidence": "Responsibilities map back to the cited RU evidence."
      },
      {
        "check_id": "SPF-7",
        "answer": "yes",
        "evidence": "Top-level input/output duties remain covered."
      },
      {
        "check_id": "SPF-8",
        "answer": "yes",
        "evidence": "The top module still acts as the orchestrator/integrator."
      }
    ],
    "coupling_preservation": [
      {
        "check_id": "CP-1",
        "answer": "yes",
        "evidence": "High-strength merge hints remain mostly grouped."
      },
      {
        "check_id": "CP-2",
        "answer": "yes",
        "evidence": "State-heavy logic remains within a natural module boundary."
      },
      {
        "check_id": "CP-3",
        "answer": "yes",
        "evidence": "Timing-critical round logic is not split unnaturally."
      },
      {
        "check_id": "CP-4",
        "answer": "yes",
        "evidence": "Same-stage control and update actions remain close."
      },
      {
        "check_id": "CP-5",
        "answer": "uncertain",
        "evidence": "Special-path handling is present but not deeply detailed."
      },
      {
        "check_id": "CP-6",
        "answer": "yes",
        "evidence": "Critical control and update logic stay coupled."
      },
      {
        "check_id": "CP-7",
        "answer": "yes",
        "evidence": "The datapath is not over-fragmented."
      },
      {
        "check_id": "CP-8",
        "answer": "yes",
        "evidence": "The split is not purely cosmetic."
      }
    ],
    "codegen_feasibility": [
      {
        "check_id": "CF-1",
        "answer": "yes",
        "evidence": "Module count is moderate for this design."
      },
      {
        "check_id": "CF-2",
        "answer": "yes",
        "evidence": "Each module can be justified with explicit RU evidence."
      },
      {
        "check_id": "CF-3",
        "answer": "yes",
        "evidence": "No module appears gratuitously tiny."
      },
      {
        "check_id": "CF-4",
        "answer": "uncertain",
        "evidence": "The top module still carries notable orchestration responsibility."
      },
      {
        "check_id": "CF-5",
        "answer": "yes",
        "evidence": "Cross-module interface count stays manageable."
      },
      {
        "check_id": "CF-6",
        "answer": "yes",
        "evidence": "Implementation order is natural from leaves to top."
      },
      {
        "check_id": "CF-7",
        "answer": "yes",
        "evidence": "Adjacent modules are separable enough for staged generation."
      },
      {
        "check_id": "CF-8",
        "answer": "yes",
        "evidence": "The partitioning reduces downstream codegen burden."
      }
    ],
    "interface_naturalness": [
      {
        "check_id": "IN-1",
        "answer": "yes",
        "evidence": "Interfaces largely reflect spec-facing signals and responsibilities."
      },
      {
        "check_id": "IN-2",
        "answer": "yes",
        "evidence": "No abstract convenience bus names dominate the interfaces."
      },
      {
        "check_id": "IN-3",
        "answer": "yes",
        "evidence": "Generic placeholder-style interface names are avoided."
      },
      {
        "check_id": "IN-4",
        "answer": "yes",
        "evidence": "Interfaces follow the candidate's responsibility boundaries."
      },
      {
        "check_id": "IN-5",
        "answer": "yes",
        "evidence": "No extra intermediate interface shell is added just for neatness."
      },
      {
        "check_id": "IN-6",
        "answer": "yes",
        "evidence": "Interfaces map to concrete data/control responsibilities."
      },
      {
        "check_id": "IN-7",
        "answer": "uncertain",
        "evidence": "One inferred interface improves decomposition but has limited spec grounding."
      },
      {
        "check_id": "IN-8",
        "answer": "yes",
        "evidence": "Interface granularity remains balanced."
      }
    ],
    "granularity_economy": [
      {
        "check_id": "GE-1",
        "answer": "yes",
        "evidence": "The candidate avoids unnecessary convenience wrappers."
      },
      {
        "check_id": "GE-2",
        "answer": "yes",
        "evidence": "Strongly coupled responsibilities are not hard-split."
      },
      {
        "check_id": "GE-3",
        "answer": "yes",
        "evidence": "Only clear boundaries are elevated to modules."
      },
      {
        "check_id": "GE-4",
        "answer": "yes",
        "evidence": "Granularity stays in a stable middle range."
      },
      {
        "check_id": "GE-5",
        "answer": "yes",
        "evidence": "Explicit primitives are not wrapped unnecessarily."
      },
      {
        "check_id": "GE-6",
        "answer": "yes",
        "evidence": "Responsibilities remain complete enough per module."
      },
      {
        "check_id": "GE-7",
        "answer": "yes",
        "evidence": "Spec fidelity is not traded away for modularity aesthetics."
      },
      {
        "check_id": "GE-8",
        "answer": "uncertain",
        "evidence": "A slightly finer variant might still be comparable in clarity."
      }
    ]
  }
}
""".strip()


def get_output_schema_hint() -> str:
    return (
        "Return JSON with keys `candidate_id`, `plan_style`, and `checklists`. "
        "Under `checklists`, return all five dimensions. "
        "Each dimension must contain exactly eight checklist items in rubric order. "
        "Each checklist item must include `check_id`, `answer`, and `evidence`. "
        "Allowed answers are only `yes`, `uncertain`, and `no`."
    )


def _format_rubric() -> str:
    blocks = []
    for dimension, items in CHECKLIST_RUBRIC.items():
        lines = [f"- {dimension}:"]
        lines.extend([f"  - {check_id}: {question}" for check_id, question in items.items()])
        blocks.append("\n".join(lines))
    return "\n".join(blocks)


def build_prompt(
    *,
    candidate_json: str,
    ru_json: str,
    merge_hint_json: str,
    split_hint_json: str,
    boundary_signal_json: str,
    granularity_profile_json: str,
    top_module_name: str,
    explicit_submodules_json: str,
    stage_context: str = "",
) -> str:
    return f"""
Evaluate exactly one RTL module candidate using the fixed checklist rubric below.

Rules:
- Evaluate this candidate independently. Do not compare it to other candidates.
- Do not output numeric scores.
- Do not omit any checklist item.
- Use only `yes`, `uncertain`, or `no` for each answer.
- Evidence must be concrete and reference module structure, interfaces, merge hints, split hints, RU locality, or explicit spec priors.
- Be strict about top-module identity, explicit submodule identity, strong coupling, and invented interfaces.
- Use RU `primary_span_ids`, RU `boundary_signals`, RU `anti_merge_signals`, and RU `locality_score` as structural priors when judging whether a module boundary is natural.

Top module name:
`{top_module_name}`

Markdown-explicit submodule names:
{explicit_submodules_json}

Checklist rubric:
{_format_rubric()}

Responsibility units:
{ru_json}

Merge hints:
{merge_hint_json}

Split hints:
{split_hint_json}

Top-level boundary signals:
{boundary_signal_json}

Granularity profile:
{granularity_profile_json}

Candidate:
{candidate_json}

Additional stage context:
{stage_context or "None"}

{get_output_schema_hint()}

Example output:
{EXAMPLE_OUTPUT}
""".strip()
