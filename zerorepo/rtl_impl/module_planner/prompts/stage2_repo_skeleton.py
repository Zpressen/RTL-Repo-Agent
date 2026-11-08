REPO_SKELETON_SYSTEM_ROLE = """
You are a repository skeleton planning agent for RTL spec-to-repo generation.

Your task is to infer a compact repo_skeleton_v1 architecture from source specs.

This stage only builds the repository-level skeleton.
Do not design module-internal code skeletons.

Primary input:
- stage2_prompt_context_v1 containing the primary source spec, compact architecture facts, and module hints

Your job is to:
1. decide the final RTL module decomposition
2. assign each module a responsibility and lightweight kind
3. infer hierarchy and instance hints from explicit facts plus justified data/resource dependencies
4. organize global invariants
5. assign simple file paths
6. decide generation order
7. record cross-module alignment
8. record unresolved repo-level issues

Allowed module kinds:
- top_controller
- iterative_engine
- leaf_combinational
- leaf_stateful

Do NOT include:
- always block planning
- FSM detailed transition tables
- register transfer rules
- internal wiring maps
- byte-level or bit-level code skeleton hints
- module pseudocode

Planning policy:
- prefer simple repository layout suitable for a research prototype
- do not create one module per phase, round, cycle, or logical value version
- preserve optional extracted facts unless there is a strong inconsistency
- use leaf-first generation order by default
- mark shared reusable modules explicitly
- if something is uncertain, put it into open_issues instead of over-planning

Before output, internally check:
- every planned module appears in file_map
- hierarchy references only known modules
- generation_order respects dependencies
- shared modules are consistent with hierarchy and instance hints
- inferred hierarchy or instance hints cite supporting fact IDs only when they come from fact_ledger evidence
- source spec file stems are not treated as RTL modules unless supported by module facts or RTL behavior evidence

Output exactly one JSON object that follows repo_skeleton_v1.
Do not output prose before or after the JSON.
""".strip()


REPO_SKELETON_EXAMPLE = """
{
  "schema_version": "repo_skeleton_v1",
  "task_id": "packet_router_top",
  "source_schema_version": "stage2_planning_input_v1",
  "stage2_status": "repo_skeleton_planned",
  "top_module": "packet_router_top",
  "global_invariants": {
    "system_role": "Packet routing system with top-level flow control and reusable lookup helpers",
    "clocking_model": {
      "primary_clock": "clk",
      "reset_signal": "rst",
      "reset_style": "top-level active-high reset; helper blocks follow the same primary clock domain"
    },
    "hierarchy": [
      {
        "parent": "packet_router_top",
        "child": "route_table",
        "source_kind": "explicit",
        "supporting_fact_ids": [],
        "rationale": "Preserved from explicit source-spec hierarchy."
      },
      {
        "parent": "packet_router_top",
        "child": "output_scheduler",
        "source_kind": "explicit",
        "supporting_fact_ids": [],
        "rationale": "Preserved from explicit source-spec hierarchy."
      }
    ],
    "file_map": {
      "packet_router_top": "generate/rtl/packet_router_top.v",
      "route_table": "generate/rtl/route_table.v",
      "output_scheduler": "generate/rtl/output_scheduler.v"
    },
    "cross_module_alignment": [
      "packet_router_top, route_table, and output_scheduler share the same primary clock domain",
      "route lookup results feed output scheduling in the top module"
    ],
    "global_data_conventions": [
      "packet headers are interpreted before output selection"
    ]
  },
  "modules": [
    {
      "module": "route_table",
      "file_path": "generate/rtl/route_table.v",
      "role": "routing lookup helper",
      "kind": "leaf_stateful",
      "parents": ["packet_router_top"],
      "children": [],
      "instance_hints": [],
      "repo_notes": []
    },
    {
      "module": "output_scheduler",
      "file_path": "generate/rtl/output_scheduler.v",
      "role": "output scheduling helper",
      "kind": "leaf_stateful",
      "parents": ["packet_router_top"],
      "children": [],
      "instance_hints": [],
      "repo_notes": []
    },
    {
      "module": "packet_router_top",
      "file_path": "generate/rtl/packet_router_top.v",
      "role": "top-level packet routing controller",
      "kind": "top_controller",
      "parents": [],
      "children": ["route_table", "output_scheduler"],
      "instance_hints": [
        {
          "module": "route_table",
          "count": 1,
          "usage": "destination lookup",
          "source_kind": "explicit",
          "supporting_fact_ids": [],
          "rationale": "Preserved from explicit source-spec planning evidence."
        },
        {
          "module": "output_scheduler",
          "count": 1,
          "usage": "egress arbitration",
          "source_kind": "explicit",
          "supporting_fact_ids": [],
          "rationale": "Preserved from explicit source-spec planning evidence."
        }
      ],
      "repo_notes": [
        "Owns top-level integration of lookup and scheduling helpers"
      ]
    }
  ],
  "planning_decisions": {
    "generation_order": ["route_table", "output_scheduler", "packet_router_top"],
    "leaf_first": true,
    "shared_modules": [],
    "top_level_integration_notes": [
      "Integrate route lookup before output arbitration in the top module"
    ]
  },
  "open_issues": []
}
""".strip()


def build_repo_skeleton_prompt(stage2_prompt_context_json: str, stage_context: str = "") -> str:
    return f"""
Input:
A compact stage2_prompt_context_v1 object containing:
- one complete primary source spec
- supplemental source file metadata
- compact architecture facts and explicit hierarchy
- top-module and compatibility module hints

Task:
Infer repo_skeleton_v1 from the evidence.

Requirements:
1. Treat source spec markdown as the primary evidence.
2. Treat architecture facts and module candidates as hints unless they carry explicit structural evidence.
3. Produce repository-level architecture planning only.
4. Keep the schema compact and directly usable in a research prototype.
5. Fill the following fields:
   - top_module
   - global_invariants
   - modules
   - planning_decisions
   - open_issues

Important constraints:
- Do not generate module-internal skeletons.
- Do not add detailed FSM, always blocks, or register update rules.
- Keep cross-module alignment at a repository level.
- File paths should be simple and consistent, e.g. generate/rtl/<module>.v
- Do not emit a separate `module_order` field. Use `planning_decisions.generation_order` as the only execution order.
- Keep `modules` in the same order as `planning_decisions.generation_order`.
- If something is uncertain, put it into open_issues instead of inventing details.
- Architecture facts may be absent; when they are absent, infer final module decomposition from `primary_source_spec.markdown`.
- For system-level specs, derive modules from functional decomposition, resource reuse, state ownership, clocked boundaries, and explicit partitioning guidance.
- Temporal phases and logical versions are not module candidates by themselves. Do not create one module per phase, round, cycle, or value tag.
- If explicit hierarchy is sparse or empty, derive likely dependencies from inferred relations, dataflow facts, submodule_facts, module roles, resource_requirement, data_dependency, datapath, and source spec behavior.
- Only infer hierarchy or instance_hints from grounded facts or source-spec evidence such as resource_requirement, data_dependency, module_identity, algorithm_step, or explicit module role facts.
- Mark fact-derived hierarchy and instance_hints with `source_kind: "inferred_from_fact_ledger"`, cite `supporting_fact_ids`, and explain the rationale.
- Preserve explicit fact-ledger instantiates/contains hierarchy as `source_kind: "explicit"`.
- Do not treat a fact-derived relation as explicit; if supporting facts are weak, include an open_issue.
- Source document stems are not treated as RTL modules just because they are filenames. For example, `aes_unified_functional_spec` is a spec document name unless facts/spec text support an RTL module with that name.
- Decide whether resource requirements become child modules, repeated instances, local helper functions, or internal unrolled logic; record low-confidence decisions in open_issues.
- Prefer compact module sets; localize simple single-use combinational helpers such as xtime or MixColumns when spec guidance says so.
- For every modules[] entry, fill `source_kind`, `supporting_fact_ids`, `rationale`, `confidence`, and `module_decision` when the module is inferred or selected from weak evidence.

Field guidance:
- global_invariants: stable facts reused in later stages
- modules[].role/kind: lightweight planning hints only
- modules[].source_kind: explicit, inferred_from_fact_ledger, inferred_from_spec, or compatibility_hint
- modules[].module_decision: required, optional, internalized, rejected, or uncertain
- planning_decisions: repo-level decisions made in this stage
- open_issues: unresolved repo-level uncertainties

Return exactly one JSON object and no prose.

Example:
{REPO_SKELETON_EXAMPLE}

stage2_prompt_context:
{stage2_prompt_context_json}

Additional stage context:
{stage_context or "None"}
""".strip()
