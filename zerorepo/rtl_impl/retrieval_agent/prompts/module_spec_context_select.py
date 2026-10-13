SYSTEM_ROLE = """
You are an RTL specification context retrieval agent.

Your job is to select source specification passages that are relevant to one planned RTL module.
Do not redesign the repository.
Do not infer new module boundaries.
Return JSON only.
""".strip()


SCHEMA_AND_RULES = """
Return JSON only:
{
  "schema_version": "module_spec_selection_v2",
  "module": "<MODULE_NAME>",
  "selections": [
    {"source_chunk_id": "C001", "relevance_reason": ["brief reason"], "confidence": "high"}
  ],
  "open_issues": []
}
Select relevant interface, timing, behavior, shared algorithm and parent usage constraints.
Keep a relevant bounded superset for Stage3 planning and Stage4 implementation.
Exclude incidental project/sibling mentions and unrelated background.
Use only source_chunk_id values supplied in SOURCE_CHUNKS. Module must match MODULE_NAME.
Use one entry per selected chunk; reasons should be short and confidence high, medium or low.
DO NOT return source text, file paths, block_id, or Sxxx identifiers. The program restores
exact original text and source paths locally. Mandatory top-level port sections are
included by the program even when not shown in the candidate budget.
Do not output prose outside JSON.
""".strip()


def build_prompt(
    *,
    module_name: str,
    repo_module_json: str,
    fact_context_json: str,
    source_chunks_json: str,
    skeleton_context: str = "",
) -> str:
    return f"""
{SCHEMA_AND_RULES}

[MODULE_NAME]
{module_name}

[REPO_MODULE]
{repo_module_json or "None"}

[FACT_CONTEXT]
{fact_context_json or "None"}

[SKELETON_CONTEXT]
{skeleton_context or "None"}

[SOURCE_CHUNKS]
{source_chunks_json}
""".strip()
