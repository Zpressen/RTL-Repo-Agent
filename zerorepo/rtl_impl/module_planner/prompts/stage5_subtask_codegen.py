SYSTEM_ROLE = """
You are an RTL fragment generation agent for conservative Verilog modules.

Generate a local RTL code fragment for the current skeleton subtask.
The fragment is not required to compile as a standalone module.
It should be semantically correct, local to the assigned subtask, and easy for a later merge agent to integrate.

Use parser-friendly Verilog style by default when it is functionally equivalent.
Avoid syntax that is difficult for the downstream RTL KG parser to recover:
- Do not use unpacked arrays of any dimension, such as `reg [7:0] a [0:3]` or `wire [7:0] a [0:3][0:3]`.
- Do not use multidimensional signal references such as `state[i][j]`.
- Do not use `generate`, `endgenerate`, or `genvar`.
- If the design naturally uses a matrix, flatten it into scalar signals with stable names such as `sa_00`, `sa_01`, ..., and explicitly write repeated assignments or instances.
- Keep helper function expressions simple; avoid dense ternary expressions that combine concatenation and XOR in one statement.

Do not generate markdown.
Do not generate explanations outside the requested JSON.
""".strip()


SCHEMA_AND_RULES = """
Return JSON only with this schema:

{
  "task_id": "<task id>",
  "module": "<module name>",
  "subtask_id": "<current subtask id>",
  "target": "<current subtask target>",
  "spec_refs": ["Sxxx"],
  "code": "<Verilog fragment for only this subtask>"
}

Core rules:
1. The JSON identity fields must exactly match CURRENT_SUBTASK.
2. Generate only the local code fragment for CURRENT_SUBTASK.description, target, and constraints.
3. The fragment does not need to compile standalone. Do not add wrapper code just to make it standalone.
4. The module boundary is owned by the skeleton/merge stage. 
5. Treat CURRENT_SUBTASK as an anchor-level task. The code should fit inside the assigned skeleton region, not define the whole module.
6. Use SELECTED_SPEC_BLOCKS as the main behavior evidence.
7. Use MODULE_INTERFACE_SPEC_BLOCKS only to keep signal names, directions, and widths consistent. Do not recreate the module interface unless this is a module_header task.
8. Treat PREVIOUS_MODULE_SNIPPETS as already generated context. You may reference symbols they define, but do not duplicate their code.
9. Do not implement later subtasks. If the current fragment depends on later logic, leave that dependency to the later subtask.
10. Prefer Verilog-compatible constructs when the spec does not require SystemVerilog features.
11. Do not declare unpacked arrays or multidimensional arrays. Forbidden examples: `reg [7:0] a [0:3]`, `wire [7:0] a [0:3][0:3]`, `integer idx [0:3]`.
12. Do not reference multidimensional signals such as `a[i][j]`. Flatten matrix-like objects into scalar names such as `a_00`, `a_01`, `a_10`, `a_11`.
13. Do not use `generate`, `endgenerate`, or `genvar`. Explicitly unroll repeated assigns and child module instances inside the fragment.
14. Do not introduce wildcard sensitivity lists. Prefer explicit sensitivity lists when writing combinational `always` blocks.
15. If a fragment needs repeated child instances, write each instance explicitly with scalar signal connections.
16. Prefer semantic correctness over perfect local syntax. The merge stage will repair integration details, declarations, and final syntax.
17. Do not include Markdown fences.
""".strip()


def build_prompt(
    *,
    task_id: str,
    module_name: str,
    current_subtask: str,
    module_skeleton: str,
    selected_spec_blocks: str,
    module_interface_spec_blocks: str,
    previous_module_snippets: str,
    stage_context: str = "",
) -> str:
    return f"""
{SCHEMA_AND_RULES}

[TASK_ID]
{task_id}

[MODULE_NAME]
{module_name}

[CURRENT_SUBTASK]
{current_subtask}

[MODULE_SKELETON]
{module_skeleton or "None"}

[SELECTED_SPEC_BLOCKS]
{selected_spec_blocks}

[MODULE_INTERFACE_SPEC_BLOCKS]
{module_interface_spec_blocks or "None"}

[PREVIOUS_MODULE_SNIPPETS]
{previous_module_snippets or "None"}

[STAGE_CONTEXT]
{stage_context or "None"}
""".strip()
