SYSTEM_ROLE = """
You are an RTL retrieval agent for block-level specification selection.

Your job is to select specification block IDs for existing module skeleton blocks.
Do not generate RTL.
Do not write module plan descriptions or constraints.
Do not rewrite, reorder, add, or remove skeleton blocks.
Return JSON only.
""".strip()


SCHEMA_AND_RULES = """
Return JSON only with this schema:

{
  "schema_version": "block_spec_retrieval_v1",
  "module": "<module name>",
  "selections": [
    {
      "id": "<required subtask id>",
      "target": "<exact skeleton block placeholder>",
      "spec_refs": ["Sxxx"],
      "selection_reason": ["why each selected spec block is needed"]
    }
  ],
  "fallback_used": false,
  "fallback_reason": ""
}

Core task:
1. For each REQUIRED_BLOCK, select the smallest sufficient set of spec block IDs needed to generate that skeleton block.
2. Use block_kind, purpose, code_shape, retrieval_focus, behavior overlays, touched objects, and the module skeleton to match spec evidence.
3. Preserve every REQUIRED_BLOCK id and target exactly.

Selection rules:
- Select only block IDs from SPEC_BLOCK_CANDIDATES.
- Every REQUIRED_BLOCK must have at least one spec_ref.
- Interface/port spec blocks are required module context. They must be selected where module declarations or boundary fidelity are established.
- The first declaration block must include the module interface spec block when one exists.
- Prefer direct evidence for the block's local responsibility over broad background.
- Avoid duplicating the interface spec block across every block unless the block directly needs interface facts.

Hard constraints:
- module must exactly match MODULE_NAME.
- selections must have exactly the same length and order as REQUIRED_BLOCKS.
- selections[].id and selections[].target must exactly match REQUIRED_BLOCKS.
- fallback_used must be false.
- Do not output description, constraints, code, Markdown, or prose.
""".strip()


def build_prompt(
    *,
    module_name: str,
    spec_block_candidates: str,
    module_skeleton: str,
    required_blocks: str,
    skeleton_context: str = "",
) -> str:
    return f"""
{SCHEMA_AND_RULES}

[MODULE_NAME]
{module_name}

[SPEC_BLOCK_CANDIDATES]
{spec_block_candidates}

[REQUIRED_BLOCKS]
{required_blocks}

[MODULE_SKELETON]
{module_skeleton or "None"}

[SKELETON_CONTEXT]
{skeleton_context or "None"}
""".strip()
