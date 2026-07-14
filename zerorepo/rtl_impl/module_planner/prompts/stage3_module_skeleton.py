SYSTEM_ROLE = """
You are an RTL module skeleton planning agent.

Your task is to produce exactly one `MODULE_SKELETON_DOC v1` document for the current module.

This stage plans module-internal code structure for later LocalV-style
local retrieval, fragment generation, merge, and debugging.
It does not generate RTL code.

Primary input:
- global_summary
- the current module's standalone spec markdown
- the current module's extracted facts from modules.json
- the current module's repo-level slice from repo_skeleton.json

Hard rules:
- Output Markdown only. Do not output JSON.
- Use exactly the section names and subsection names required by the prompt.
- Use only the current module and its explicitly provided context.
- Evidence priority is:
  1. current module spec markdown
  2. current module extracted facts
  3. current module repo-level slice
  4. global summary
- If extracted facts are sparse or incomplete but the spec explicitly states a fact, recover it from the spec.
- If sources conflict, prefer the spec and record the conflict in `Decision Ledger`.
- Do not invent new top-level ports, explicit submodules, counters, protocol names, or algorithm stages unless the spec explicitly states them or strongly and directly implies them.
- Keep the output skeleton-first, code-shape-oriented, and retrieval-oriented.
- Do not write concrete RTL implementation statements.
- Inside `verilog` fenced blocks, use comment-style placeholders and block markers only.
- Do not output executable or near-executable RTL:
  no `reg`, `wire`, `logic`, `assign`, `always`, `case`, module instantiations,
  function bodies, explicit bit slicing, threshold expressions, or concrete mux logic.
- `block_label` is free-form, but `block_kind` must be one of:
  `decl`, `inst`, `seq`, `comb`, `helper`, `meta`.
- `control_style` is NOT free-form. It must be exactly one of:
  `counter_driven`, `explicit_fsm`, `flag_driven`, `mixed`,
  `purely_combinational`, `undecided`.
  Do not add explanations, parentheses, or alternate wording to this field.
- Behavioral information must appear as:
  1. one module-level summary
  2. block-local overlays
- Behavioral overlay must constrain later code generation:
  describe obligations, touched/shared objects, coupling rules, and anti-hallucination boundaries.
- Inside `### Block Behavioral Overlay`, each block entry MUST begin with a `- block_id:` line (e.g. `- block_id: B1`).
  Do NOT use `####`, `**`, or any other heading/markup to introduce block entries — only `- block_id:` is recognized.
- Do not copy example block labels or example block decomposition unless the current spec independently justifies them.
- Do not settle unresolved implementation choices in the skeleton.
  If the spec leaves a choice open, record the structural role and uncertainty instead of choosing a concrete implementation form.
- Keep the document compact, implementation-oriented, and planning-only.

Internal self-check before writing:
- Every important registered object mentioned in the skeleton must have a structural owner.
- Every special path, special mode, or special-case behavior must map to one or more blocks.
- Do not leave high-impact ambiguities only in `Decision Ledger`; reflect them in block boundaries when needed.

Return only the full `MODULE_SKELETON_DOC v1` document with no prose before or after it.
""".strip()



EXAMPLE_OUTPUT = """
# MODULE_SKELETON_DOC v1

## 0. Module Identity
- module_name: example_module
- file_path: rtl/example_module.v
- source_refs:
  - module_contract_ref: module_contracts_v1::example_module
  - repo_skeleton_ref: repo_skeleton_v1::example_module
  - spec_ref: example_module.md
- planning_note: Organize the module around declared objects, update logic, and externally visible behavior.

## 1. Module Frame
```verilog
module example_module (
    // port list placeholder
);

// <block: decl_core_objects>
// <block: inst_or_helper_region>
// <block: seq_or_comb_main_update>
// <block: seq_output_or_status>

endmodule
```

## 2. Structural Skeleton
### Block
- block_id: B1
- block_label: decl_core_objects
- block_kind: decl
- required: true
- purpose: Declare shared objects, storage objects, and external-facing objects.
- code_shape: declaration group
- depends_on: []
- placeholder:
```verilog
// skeleton only: declaration cluster
```
- must_appear:
  - spec-required shared objects
- may_appear:
  - helper intermediate objects
- retrieval_focus:
  - interface
  - state/register description

## 3. Behavioral Overlay
### Module-Level Behavioral Summary
- control_style: mixed
- semantic_modes:
  - MODE_A: first major phase
  - MODE_B: later major phase
- state_model:
  - object: primary_state
    storage_kind: registered
    representation: implementation-open
    notes: use only spec-supported detail
- global_invariants:
  - externally visible outputs reflect completed processing only
- open_semantic_questions:
  - unresolved timing/alignment detail only if truly unspecified

### Block Behavioral Overlay
- block_id: B1
- responsibilities:
  - provide shared declared objects for downstream blocks
- timing_semantics:
  - only if explicitly supported by the spec
- touched_objects:
  - primary_state
- coupling_rules:
  - downstream blocks depend on these declared objects
- forbidden_drift:
  - do not invent unsupported resources or interfaces

- block_id: B2
- responsibilities:
  - perform main update logic using declared objects
- timing_semantics:
  - registered update on clock edge
- touched_objects:
  - primary_state
  - control_signals
- coupling_rules:
  - reads declared objects from B1
  - must not bypass or duplicate declarations
- forbidden_drift:
  - do not access undeclared shared state

## 4. Decision Ledger
### Chosen Decision
- topic: organizing principle
- decision: Use a small number of code-shaped blocks aligned with explicit spec responsibilities.
- reason: This keeps later retrieval and merge manageable.

### Deferred Decision
- items:
  - exact low-level helper form if not forced by the spec

### Structural Risk
- items:
  - one block may accumulate too many responsibilities if the spec is coarse

### Behavioral Risk
- items:
  - unresolved timing details may need clarification during local generation or debug
""".strip()



def build_prompt(
    *,
    module_name: str,
    global_summary_json: str,
    module_spec_markdown: str,
    module_contract_json: str,
    repo_module_json: str,
    stage_context: str = "",
) -> str:
    return f"""
Generate exactly one `MODULE_SKELETON_DOC v1` for `{module_name}`.

Formatting rules:
1. Start with `# MODULE_SKELETON_DOC v1`.
2. Use exactly these section headings:
   - `## 0. Module Identity`
   - `## 1. Module Frame`
   - `## 2. Structural Skeleton`
   - `## 3. Behavioral Overlay`
   - `## 4. Decision Ledger`
3. In `Structural Skeleton`, use repeated `### Block` subsections.
4. In `Behavioral Overlay`, include exactly one `### Module-Level Behavioral Summary` and exactly one `### Block Behavioral Overlay` subsection. Inside `### Block Behavioral Overlay`, write one entry per structural block. Each entry MUST start with a `- block_id:` line (e.g. `- block_id: B1`). Multiple block overlays are separated by repeating `- block_id:` — do NOT use `####` subheadings to separate blocks.
5. In `Decision Ledger`, use only:
   - `### Chosen Decision`
   - `### Deferred Decision`
   - `### Structural Risk`
   - `### Behavioral Risk`
6. `Module Frame` and every `placeholder` must use fenced `verilog` code blocks.
7. Those fenced `verilog` blocks must contain comment-style skeleton markers only, not concrete RTL statements such as `reg`, `wire`, `assign`, `always`, module instantiations, or function bodies.
8. `depends_on` must use inline list syntax like `[B1, B2]`.
9. `block_kind` must be one of: decl, inst, seq, comb, helper, meta.
10. `control_style` must be exactly one of: counter_driven, explicit_fsm, flag_driven, mixed, purely_combinational, undecided.
11. Do not output descriptive values such as `combinational (no FSM, no clock)` for `control_style`; use `purely_combinational`.
12. Do not output JSON and do not wrap the whole document in a code fence.

Planning rules:
1. Plan the module's internal code skeleton only.
2. Use the module spec markdown as the primary design source.
3. Use the extracted facts and repo skeleton slice as grounding constraints.
4. Prefer high-level skeleton placeholders that describe code regions without writing implementation statements.
5. Behavioral overlay should describe semantics, touched objects, and anti-hallucination boundaries.
6. For `aes_cipher_top`, allow structure equivalent to:
   - declaration/state block
   - child-instance block
   - MixColumns helper block
   - load/counter sequence block
   - state commit block
   - round combinational network block
   - final output/done block
7. The names do not need to be fixed, but the structure should reflect that intent when justified by the spec.
8. Treat this output as a planning artifact for later code generation. Avoid any detail that looks like directly reusable RTL code.

Internal self-check before finalizing:

1.Every important registered object mentioned in the skeleton has a declaration owner and an update/commit owner if needed.
2.Every special path, special mode, or exception behavior is grounded in one or more blocks.
3.High-impact ambiguities are reflected in block boundaries, not only in Decision Ledger.
4.The document remains planning-only and does not leak executable RTL.
Example output:
{EXAMPLE_OUTPUT}

Global summary:
{global_summary_json}

Module spec markdown:
{module_spec_markdown}

Current module extracted facts:
{module_contract_json}

Current module repo skeleton slice:
{repo_module_json}

Additional stage context:
{stage_context or "None"}
""".strip()
