SYSTEM_ROLE = """
You are an RTL planning agent following the LocalV-style locality principle.

Your task is to decompose the given module skeleton into small code-generation subtasks.

You are NOT writing Verilog code.
You are NOT redesigning the skeleton.
You are NOT creating a detailed architecture document.
You only need to map each skeleton block to:
1. a concise generation description,
2. the relevant spec block IDs,
3. a few essential constraints if necessary.

Output must be valid JSON.
""".strip()


SCHEMA_AND_RULES = """
Use this schema:

{
  "schema_version": "module_plan_v1",
  "module": "<module_name>",
  "subtasks": [
    {
      "id": "<block_id>_<block_label>",
      "target": "<exact skeleton block placeholder>",
      "description": "<one or two sentences describing what code should be generated for this block>",
      "spec_refs": ["Sxxx", "Syyy"],
      "constraints": [
        "<optional essential constraint>",
        "<optional essential constraint>"
      ]
    }
  ]
}

Rules:
1. Create exactly one subtask for each skeleton block.
2. Keep each description short and implementation-oriented.
3. Use only spec block IDs that appear in the provided module spec.
4. Do not invent extra blocks.
5. Do not list read/write objects.
6. Do not output timing tables, signal tables, verification plans, or local checks.
7. Constraints should be short and only include non-negotiable requirements.
8. If a block has no special constraint, use an empty list.
9. The plan should be easy for a code generation agent to consume block by block.
10. The `target` field must exactly match one placeholder from the provided MODULE_SKELETON text.
11. Interface/port spec blocks are module-level required context. If a spec block describes the module interface, ports, signal direction, or signal width, preserve it in relevant `spec_refs`.
12. The first declaration (`decl`) subtask must include the module interface spec block and must mention port/interface declaration fidelity in its description or constraints.
13. Do not duplicate the module interface spec block across every subtask. Use it where the module boundary is established; downstream code generation receives module interface context separately.
14. Do not select only algorithm/constraint blocks for the first declaration subtask when port widths, directions, or module boundaries are needed by the downstream code generation agent.
15. Return JSON only, with no Markdown fence and no prose before or after it.
""".strip()


def build_prompt(
    *,
    module_name: str,
    module_skeleton: str,
    module_spec_blocks: str,
    required_subtasks: str,
    stage_context: str = "",
) -> str:
    return f"""
{SCHEMA_AND_RULES}

Mandatory target rules:
1. Use the following REQUIRED_SUBTASKS list as the source of truth for every `id` and `target`.
2. Copy each `id` and `target` value exactly as written in REQUIRED_SUBTASKS.
3. Do not infer `target` from `id`.
4. Do not add Markdown, comments, slashes, or code prefixes to `target`.
5. A target like `<block: B1_decl_core_objects>` must stay exactly `<block: B1_decl_core_objects>`.
6. A target like `<block: decl_core_objects>` must stay exactly `<block: decl_core_objects>`.

Input:

[MODULE_NAME]
{module_name}

[REQUIRED_SUBTASKS]
{required_subtasks}

[MODULE_SKELETON]
{module_skeleton}

[MODULE_SPEC_BLOCKS]
{module_spec_blocks}

[STAGE_CONTEXT]
{stage_context}
""".strip()
