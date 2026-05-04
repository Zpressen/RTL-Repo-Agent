REPO_SKELETON_SYSTEM_ROLE = """
You are a repository skeleton planning agent for RTL spec-to-repo generation.

Your task is to construct a compact repo_skeleton_v1 object from a stage1 modules.json input.

This stage only builds the repository-level skeleton.
Do not design module-internal code skeletons.

Primary input:
- modules.json from stage1 extraction

Your job is to:
1. preserve stable stage1 facts
2. organize global invariants
3. assign simple file paths
4. decide generation order
5. assign lightweight module kinds
6. summarize repo-level instance hints
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
- preserve extracted facts unless there is a strong inconsistency
- use leaf-first generation order by default
- mark shared reusable modules explicitly
- if something is uncertain, put it into open_issues instead of over-planning

Before output, internally check:
- every module appears in file_map
- hierarchy references only known modules
- generation_order respects dependencies
- shared modules are consistent with hierarchy and instance hints

Output exactly one JSON object that follows repo_skeleton_v1.
Do not output prose before or after the JSON.
""".strip()


REPO_SKELETON_EXAMPLE = """
{
  "schema_version": "repo_skeleton_v1",
  "task_id": "packet_router_top",
  "source_schema_version": "module_contracts_v1",
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
        "child": "route_table"
      },
      {
        "parent": "packet_router_top",
        "child": "output_scheduler"
      }
    ],
    "file_map": {
      "packet_router_top": "rtl/packet_router_top.v",
      "route_table": "rtl/route_table.v",
      "output_scheduler": "rtl/output_scheduler.v"
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
      "file_path": "rtl/route_table.v",
      "role": "routing lookup helper",
      "kind": "leaf_stateful",
      "parents": ["packet_router_top"],
      "children": [],
      "instance_hints": [],
      "repo_notes": []
    },
    {
      "module": "output_scheduler",
      "file_path": "rtl/output_scheduler.v",
      "role": "output scheduling helper",
      "kind": "leaf_stateful",
      "parents": ["packet_router_top"],
      "children": [],
      "instance_hints": [],
      "repo_notes": []
    },
    {
      "module": "packet_router_top",
      "file_path": "rtl/packet_router_top.v",
      "role": "top-level packet routing controller",
      "kind": "top_controller",
      "parents": [],
      "children": ["route_table", "output_scheduler"],
      "instance_hints": [
        {
          "module": "route_table",
          "count": 1,
          "usage": "destination lookup"
        },
        {
          "module": "output_scheduler",
          "count": 1,
          "usage": "egress arbitration"
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


def build_repo_skeleton_prompt(modules_json: str, stage_context: str = "") -> str:
    return f"""
Input:
A stage1 modules.json object.

Task:
Build repo_skeleton_v1 from this input only.

Requirements:
1. Use modules.json as the primary source of truth.
2. Produce repository-level planning only.
3. Keep the schema compact and directly usable in a research prototype.
4. Preserve stage1 extracted facts whenever possible.
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
- File paths should be simple and consistent, e.g. rtl/<module>.v
- Do not emit a separate `module_order` field. Use `planning_decisions.generation_order` as the only execution order.
- Keep `modules` in the same order as `planning_decisions.generation_order`.
- If something is uncertain, put it into open_issues instead of inventing details.

Field guidance:
- global_invariants: stable facts reused in later stages
- modules[].role/kind: lightweight planning hints only
- planning_decisions: repo-level decisions made in this stage
- open_issues: unresolved repo-level uncertainties

Return exactly one JSON object and no prose.

Example:
{REPO_SKELETON_EXAMPLE}

modules.json input:
{modules_json}

Additional stage context:
{stage_context or "None"}
""".strip()
