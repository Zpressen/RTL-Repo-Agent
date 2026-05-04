SYSTEM_ROLE = "You are an RTL module candidate synthesis assistant."

EXAMPLE_OUTPUT = """
{
  "candidate": {
    "candidate_id": "CONSERVATIVE_1",
    "plan_style": "conservative",
    "summary": "Keep the top module responsible for round orchestration while preserving explicit leaf modules.",
    "modules": [
      {
        "module_name": "aes_cipher_top",
        "role": "top orchestrator",
        "boundary_authority": "explicit_from_spec",
        "responsibilities": ["Top-level I/O coordination", "Round sequencing", "Submodule wiring"],
        "interfaces": ["clk", "rst", "ld", "done", "key", "text_in", "text_out"],
        "depends_on": ["aes_key_expand_128", "aes_sbox"],
        "optional": false,
        "evidence_ru_ids": ["RU_01", "RU_02", "RU_03"]
      }
    ]
  }
}
""".strip()


def get_output_schema_hint() -> str:
    return (
        "Return JSON with key `candidate`. "
        "The candidate must include candidate_id, plan_style, summary, and modules. "
        "Each module must include module_name, role, boundary_authority, responsibilities, interfaces, "
        "depends_on, optional, evidence_ru_ids."
    )


def _style_rules(plan_style: str) -> str:
    if plan_style == "conservative":
        return (
            "- Minimize splitting.\n"
            "- Keep strongly coupled control/state logic close to the top when the spec implies tight orchestration.\n"
            "- Preserve explicit submodule names and avoid inventing extra helper modules unless forced by clear boundaries."
        )
    if plan_style == "balanced":
        return (
            "- Split only clearly independent datapath, submodule, or protocol blocks.\n"
            "- Optimize for stable downstream code generation and moderate top-level complexity.\n"
            "- Preserve explicit submodule names and keep interfaces natural to the spec."
        )
    return (
        "- Allow finer-grained decomposition when it improves reuse or testability.\n"
        "- Do not violate explicit spec boundaries or strong merge hints.\n"
        "- Avoid abstraction-only helper modules that have no natural spec support."
    )


def build_prompt(
    *,
    ru_json: str,
    merge_hint_json: str,
    split_hint_json: str,
    boundary_signal_json: str,
    granularity_profile_json: str,
    plan_style: str,
    candidate_id: str,
    top_module_name: str,
    same_band_summaries_json: str,
    global_summaries_json: str,
    stage_context: str = "",
) -> str:
    return f"""
Generate exactly one RTL module planning candidate.

Current target:
- candidate_id: {candidate_id}
- plan_style: {plan_style}

Style rules:
{_style_rules(plan_style)}

Global synthesis rules:
- Cover every RU in this candidate. Do not leave any RU unassigned.
- depends_on must only reference modules present in this candidate.
- Preserve the top-level module identity as `{top_module_name}`. Helper modules may be added, but they must not replace the top module name.
- Treat merge_hints, split_hints, boundary_signals, and granularity_profile as structural priors.
- `preserve_explicit_boundary` is a hard constraint only for the top module and markdown-explicit submodule names. Image-only groupings or diagram convenience labels are not automatically explicit module boundaries.
- You may still synthesize additional modules beyond the markdown-explicit names when the RU structure, image evidence, coupling pattern, or repeated datapath/control organization strongly justifies them.
- Inferred modules are expected when they improve fidelity to the implementation structure. Mark them as `strong_implicit` or `invented_for_convenience` instead of pretending they were explicit in the spec.
- `merge_preferred` and `high_overlap_keep_together` are strong priors; only split against them if there is very strong spec evidence.
- Treat `split_preferred` as a strong anti-collapse prior.
- Use RU-local structure aggressively:
  - `primary_span_ids` identify the most local evidence neighborhood for a RU
  - RU `boundary_signals` indicate why a RU may deserve an external boundary
  - RU `anti_merge_signals` indicate why a RU should not be casually absorbed
  - RU `locality_score` indicates how compact and self-contained the RU evidence is
- Prefer to externalize RUs with compact `primary_span_ids`, strong RU boundary_signals, or clear anti_merge_signals before absorbing them into the top module.
- Respect granularity_profile as a planning prior for reasonable module count and top-module load.
- Prefer natural interfaces from the spec. Do not invent abstract buses or wrapper layers unless clearly justified.
- Every module must declare `boundary_authority`:
  - `explicit_from_spec` for top module names and explicit submodule names directly present in the spec
  - `strong_implicit` for boundaries strongly implied by interface/state/timing structure
  - `invented_for_convenience` for planner-created helper modules added only for convenience
- Produce a candidate that is meaningfully different from prior candidates in the same plan_style.

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

Already generated candidates in the same plan_style:
{same_band_summaries_json}

Already generated candidates across all plan styles:
{global_summaries_json}

Additional stage context:
{stage_context or "None"}

{get_output_schema_hint()}

Example output:
{EXAMPLE_OUTPUT}
""".strip()
