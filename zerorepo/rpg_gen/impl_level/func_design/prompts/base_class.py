DESIGN_BASE_CLASSES = """
You are designing the smallest necessary set of reusable shared definitions for a repository implementation phase.

Your objective is to introduce only the minimum shared definitions that remove immediate duplication and clarify cross-file contracts.
Default stance: **do not add a shared definition unless it is clearly needed now**.

## Mode Selection
Infer the repository mode from the provided context.

### If the repository is an RTL project
Treat this phase as **shared RTL definitions design**, not Python inheritance design.

Requirements:
- Prefer writing or extending a SystemVerilog `package` file.
- Only add shared definitions that are immediately reused by multiple RTL modules or verification artifacts.
- Focus on shared typedefs, enums, localparams, constants, and small declarations that clarify contracts.
- Keep content minimal and implementation-free.
- Respect the provided target package files. Do not create module, testbench, script, build, or documentation content in this phase.

Hard brakes (do NOT do these):
- Do not invent speculative abstraction layers.
- Do not generate module implementations, procedural datapath logic, or testbench bodies.
- Do not write Python syntax into RTL files.

### If the repository is a Python project
Treat this phase as minimal base-class / shared-type design.

Requirements:
- Only introduce a base class or shared type when it removes duplication across at least two concrete modules.
- Prefer narrow, stable contracts over generic helper hierarchies.
- Keep business logic out of shared abstractions.

Hard brakes (do NOT do these):
- Do not create speculative abstractions.
- Do not create generic Manager/Handler/Util bases.

## Decision Checklist (must apply before adding anything)
For each proposed shared definition:
1) Which **two+** concrete modules/files/features will use it immediately?
2) What duplication/inconsistency does it remove *now*?
3) Why is this the smallest correct shared definition?
If any answer is weak, **do not add it**.

## Action Space
{Tool_Description}

## Output Format
Your response must contain exactly one <think> block and exactly one <tool_call> block, with no other content outside these two blocks:
<think>
Your internal reasoning and drafts — this is scratch space for evaluating tradeoffs, alternatives, and incremental refinements.
</think>
<tool_call>
{{
  "tool_name": "...",
  "parameters": {{...}}
}}
</tool_call>
""".strip()


DESIGN_BASE_CLASSES_REVIEW = """
You are reviewing minimal shared definitions for a repository implementation phase.
You must infer the repository mode from the provided context.

For RTL projects, review the proposal as shared package-level definitions.
For Python projects, review the proposal as minimal base classes or shared types.

You must judge both what is present and what is missing.

## Review Criteria
1) Design Quality
- Are the shared definitions conceptually clean, internally consistent, and easy to reason about?
- Do they reflect real cross-file responsibilities instead of one-off needs?
- Are concerns separated appropriately?
2) Reusability
- Can the definitions be meaningfully reused in at least two concrete consumers?
- Do they actually reduce duplication and simplify implementation?
- Are there clear opportunities for reuse that were missed?
3) Abstraction Level
- Is the shared definition at the right level: neither too local nor too speculative?
- For RTL, does the package content stay within shared-definition scope instead of drifting into implementation logic?
- Are there definitions that are too tightly coupled to a single use case?
4) Interface Clarity
- Is the intended role of each shared definition clear from its naming and structure?
- For RTL, is it obvious how modules should consume the package contents?
- Is it easy for a new contributor to know how to use the shared definitions correctly?

## Output Format
Return **only** a valid JSON object in the following format:
{
  "review": {
    "Design Quality": {
      "feedback": "<Your detailed comments here>",
      "pass": true/false
    },
    "Reusability": {
      "feedback": "<Your detailed comments here>",
      "pass": true/false
    },
    "Abstraction Level": {
      "feedback": "<Your detailed comments here>",
      "pass": true/false
    },
    "Interface Clarity": {
      "feedback": "<Your detailed comments here>",
      "pass": true/false
    }
  },
  "final_pass": true/false
}

Rules:
- `final_pass` should be `true` only if all four dimensions pass, or if remaining issues are minor and easily fixable.
- All `feedback` fields must provide concrete, actionable guidance.
- Do not add new fields or categories beyond the four listed.
"""

GENERATE_BASE_CLASS_TOOL = """
## Tool Name: generate_base_classes
### Description
Generate and register shared-definition source text for repository files before integration.
### When to Use
Use this tool when you have finalized the shared-definition content for one or more target files and want it validated before integration.
### Parameters
{
  "tool_name": "generate_base_classes",
  "parameters": {
    "base_classes": [
      {
        "file_path": "Path to the target file where the shared definitions should live (string).",
        "code": "Full source text for that file, such as a Python shared abstraction file or a SystemVerilog package file (string)."
      }
    ]
  }
}
### Returns
On success, confirms the shared definitions are valid and ready to be added; on failure, returns validation details for the problematic files.
"""
