from __future__ import annotations


TOP_RESOLVER_SYSTEM_ROLE = """
You resolve an RTL repository's top-module identity from conflicting or incomplete grounded evidence.
Return JSON only. Do not invent a top name from convenience or filename alone.
The selected module must cite at least one source-spec section; cite fact IDs when available.
""".strip()


RESPONSIBILITY_SYSTEM_ROLE = """
You extract implementation responsibilities for RTL repository decomposition.
Return JSON only. Describe required behavior, state ownership, dependencies, protocol, and timing.
Do not choose module boundaries or create module names in this step.
Every responsibility must cite at least one source-spec section.
""".strip()


CANDIDATE_SYSTEM_ROLE = """
You produce one evidence-grounded RTL module-decomposition candidate.
Return JSON only. Use the supplied locked top and responsibility IDs exactly.
Do not invent implementation phases as modules and do not omit required responsibilities.
Every dependency crossing a module boundary needs one logical boundary contract.
""".strip()


PAIRWISE_SYSTEM_ROLE = """
You break a near-tie between two already validated RTL decomposition candidates.
Return JSON only. Select exactly one presented candidate ID.
Prioritize specification fidelity, coupling preservation, interface naturalness,
standalone code-generation feasibility, and economical granularity equally.
""".strip()


SELECTION_SYSTEM_ROLE = """
You are the architecture judge for an RTL repository-level code-generation pipeline.
Return JSON only. Rank every eligible decomposition candidate using qualitative architectural
judgment; deterministic risk findings are evidence, not scores or automatic disqualifiers.
Do not prefer a candidate merely because it has fewer or more modules.
""".strip()


ADJUDICATION_SYSTEM_ROLE = """
You adjudicate between two RTL decomposition candidates selected by conflicting independent rankings.
Return JSON only. Select exactly one presented candidate using the responsibility baseline,
candidate boundaries, risk evidence, and prior ranking rationales.
""".strip()


def build_top_resolver_prompt(*, prompt_context_json: str, candidate_names_json: str) -> str:
    return f"""
Resolve one top module from the source evidence.

Candidate names gathered by deterministic code:
{candidate_names_json}

Return exactly:
{{
  "module": "grounded_module_name",
  "evidence_fact_ids": ["fact ids when available"],
  "evidence_sections": ["source section containing top/interface evidence"],
  "rationale": "why this is the external integration module"
}}

The module must be supported by the source markdown or a grounded Stage1 fact.
Do not use a filename or task_id as the sole evidence.

Stage2 prompt context:
{prompt_context_json}
""".strip()


def build_responsibility_prompt(*, prompt_context_json: str, locked_top_json: str) -> str:
    return f"""
Extract one shared responsibility ledger for later module-decomposition candidates.

Locked top:
{locked_top_json}

Rules:
- Extract behavior/state/protocol responsibilities, not modules.
- Use stable IDs like RU_FETCH_CONTROL.
- Mark externally required behavior and implementation behavior as ownership_required=true.
- Constraints that do not need an owner may use ownership_required=false.
- owned_state lists only persistent state controlled by the responsibility.
- Each dependency means the current responsibility produces transferred_objects consumed by
  target_responsibility_id; do not reverse producer and consumer semantics.
- coupling_strength is strong for shared state, same-cycle timing, same FSM, flush/reset atomicity,
  medium for a natural protocol/data dependency, and weak for loose ordering or reuse.
- explicit_module_hint is allowed only when the spec/facts name a real RTL module.
- iterative=true only for explicitly iterative or multi-cycle owned behavior.
- Every responsibility must cite evidence_sections; cite evidence_fact_ids when available.

Return exactly one JSON object with:
{{
  "responsibilities": [
    {{
      "responsibility_id": "RU_...",
      "description": "...",
      "ownership_required": true,
      "evidence_fact_ids": [],
      "evidence_sections": ["..."],
      "inputs": [],
      "outputs": [],
      "owned_state": [],
      "clock_domain": "",
      "reset_behavior": "",
      "protocol": "",
      "timing_class": "",
      "dependencies": [
        {{
          "target_responsibility_id": "RU_...",
          "coupling_strength": "strong|medium|weak",
          "transferred_objects": ["..."],
          "rationale": "..."
        }}
      ],
      "explicit_module_hint": "",
      "reusable": false,
      "iterative": false
    }}
  ],
  "global_clocking_notes": [],
  "global_data_conventions": []
}}

Stage2 prompt context:
{prompt_context_json}
""".strip()


def build_candidate_prompt(
    *,
    plan_style: str,
    prompt_context_json: str,
    locked_top_json: str,
    responsibility_ledger_json: str,
) -> str:
    style_guidance = {
        "conservative": (
            "Use the smallest defensible module set. Keep responsibilities in the locked top unless an explicit "
            "module or exceptionally strong standalone boundary is evidenced."
        ),
        "balanced": (
            "Split at natural state-ownership, protocol, reusable-resource, or independently generatable boundaries "
            "while keeping strongly coupled behavior together."
        ),
        "modular": (
            "Explore more independently generatable and reusable boundaries, but reject convenience modules, "
            "phase-per-module designs, and boundaries without concrete logical contracts."
        ),
    }[plan_style]
    return f"""
Produce exactly one `{plan_style}` decomposition candidate.

Style policy:
{style_guidance}

Locked top:
{locked_top_json}

Shared responsibility ledger (authoritative behavior baseline):
{responsibility_ledger_json}

Requirements:
- Treat the shared responsibility ledger as the complete behavior baseline for decomposition.
- Do not re-extract, reinterpret, add, or remove responsibilities from source material.
- candidate_id must be `stage2_{plan_style}` and plan_style must be `{plan_style}`.
- top_module must exactly equal the locked top.
- Assign every ownership_required responsibility to exactly one module.
- Preserve explicitly named modules and explicit hierarchy.
- A boundary contract is required for every responsibility dependency whose endpoints are assigned to different modules.
- transferred_objects must use logical spec objects; do not invent RTL port names.
- width_status is explicit, derived, unresolved, or not_applicable. Uncertainty must be represented, not guessed.
- Use the literal `not_applicable` for protocol, timing, clock, or reset fields that genuinely do not
  apply to a combinational/logical transfer; do not leave those fields empty.
- hierarchy must be acyclic and reference only candidate modules.

Return exactly one object matching this shape:
{{
  "candidate_id": "stage2_{plan_style}",
  "plan_style": "{plan_style}",
  "top_module": "...",
  "summary": "...",
  "modules": [
    {{
      "module": "...",
      "role": "...",
      "responsibility_ids": ["RU_..."],
      "source_kind": "explicit|inferred_from_fact_ledger|inferred_from_spec|compatibility_hint",
      "supporting_fact_ids": [],
      "supporting_sections": [],
      "rationale": "...",
      "confidence": "high|medium|low",
      "reused": false
    }}
  ],
  "hierarchy": [
    {{
      "parent": "...",
      "child": "...",
      "source_kind": "explicit|inferred_from_fact_ledger|inferred_from_spec",
      "supporting_fact_ids": [],
      "rationale": "...",
      "confidence": "high|medium|low"
    }}
  ],
  "boundary_contracts": [
    {{
      "boundary_id": "BC_...",
      "producer_module": "...",
      "consumer_module": "...",
      "producer_responsibility_ids": ["RU_..."],
      "consumer_responsibility_ids": ["RU_..."],
      "transferred_objects": ["..."],
      "direction": "producer_to_consumer",
      "protocol": "...",
      "timing_class": "...",
      "clock_domain": "...",
      "reset_behavior": "...",
      "width_status": "explicit|derived|unresolved|not_applicable",
      "width_evidence": [],
      "evidence_fact_ids": [],
      "evidence_sections": [],
      "rationale": "..."
    }}
  ],
  "global_clocking_notes": [],
  "global_data_conventions": [],
  "open_issues": []
}}

Compact grounding context:
{prompt_context_json}

The original source markdown is intentionally omitted after responsibility extraction.
Use the compact architecture facts and explicit hierarchy only to ground module identity,
hierarchy, and evidence; they do not override the shared responsibility ledger.
""".strip()


def build_pairwise_prompt(
    *,
    responsibility_ledger_json: str,
    candidate_a_json: str,
    candidate_b_json: str,
    evaluations_json: str,
) -> str:
    return f"""
Select one of the two presented candidate IDs. Both are eligible under deterministic validation.
Treat all five dimensions equally. Do not select a candidate outside this pair.

Shared responsibilities:
{responsibility_ledger_json}

Candidate A:
{candidate_a_json}

Candidate B:
{candidate_b_json}

Deterministic evaluations:
{evaluations_json}

Return exactly:
{{
  "winner_candidate_id": "one presented candidate ID",
  "rationale": ["concise evidence-grounded reason"]
}}
""".strip()


def build_selection_prompt(
    *,
    responsibility_summary_json: str,
    candidate_views_json: str,
    presentation_order_json: str,
) -> str:
    return f"""
Rank every eligible RTL repository decomposition candidate in the exact presentation set.

Presentation order:
{presentation_order_json}

Shared responsibility baseline:
{responsibility_summary_json}

Candidate architecture views and deterministic risk evidence:
{candidate_views_json}

Judging policy:
- This is a repository-level RTL generation task. Judge independent code-generation,
  verification, integration, state ownership, timing cohesion, and interface naturalness together.
- A one-module candidate is not automatically safer because it has no cross-module contracts.
  It must justify why shared state, timing atomicity, or tight coupling outweighs codegen and
  verification burden.
- A multi-module candidate must have natural ownership boundaries and usable logical contracts;
  excessive glue, convenience modules, and unjustified strong-coupling cuts are real risks.
- Deterministic risk findings are advisory evidence. Do not count findings or derive a numeric score.
- Do not optimize module count. Select the architecture most likely to produce a coherent,
  independently generatable and integrable RTL repository.

Return exactly:
{{
  "ranked_candidate_ids": ["every presented candidate ID exactly once, best first"],
  "winner_candidate_id": "the first ranked candidate ID",
  "candidate_assessments": {{
    "candidate ID": ["concise strengths and risks"]
  }},
  "rationale": ["evidence-grounded reasons for the ordering"]
}}
""".strip()


def build_adjudication_prompt(
    *,
    responsibility_summary_json: str,
    candidate_views_json: str,
    prior_passes_json: str,
    candidate_ids_json: str,
) -> str:
    return f"""
Resolve the disagreement between exactly these two candidate IDs:
{candidate_ids_json}

Shared responsibility baseline:
{responsibility_summary_json}

Candidate architecture views and deterministic risk evidence:
{candidate_views_json}

Prior independent ranking results:
{prior_passes_json}

Apply the same repository-level architecture policy. Do not count risk findings, use a scalar
score, or select a candidate outside the presented pair.

Return exactly:
{{
  "winner_candidate_id": "one presented candidate ID",
  "rationale": ["concise evidence-grounded reasons resolving the disagreement"]
}}
""".strip()
