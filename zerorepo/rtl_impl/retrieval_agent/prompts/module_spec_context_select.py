SYSTEM_ROLE = """
You are an RTL specification context retrieval agent.

Your job is to select source specification passages that are relevant to one planned RTL module.
Do not redesign the repository.
Do not infer new module boundaries.
Return JSON only.
""".strip()


SCHEMA_AND_RULES = """
Return JSON only with this schema:

{
  "schema_version": "module_spec_context_retrieval_v1",
  "module": "<module name>",
  "blocks": [
    {
      "block_id": "S001",
      "text": "<exact copied text from one SOURCE_CHUNK>",
      "source_file": "<source file path>",
      "source_chunk_ids": ["C001"],
      "relevance_reason": ["why this source passage matters for the module"],
      "confidence": "high | medium | low"
    }
  ],
  "open_issues": [],
  "fallback_used": false,
  "fallback_reason": ""
}

Core task:
1. Select every source chunk that is relevant to describing, implementing, wiring, or validating MODULE_NAME.
2. Use module role, parent/child relationships, instance hints, facts, and skeleton hints to judge relevance.
3. Prefer exact module/interface/behavior descriptions, but keep parent usage context and shared algorithm context when they constrain the module.
4. Include parent usage context when a leaf module has no standalone section.
5. Do not drop relevant chunks just because another selected chunk is more specific.
6. Treat this as the first-pass retrieval for both Stage3 skeleton planning and Stage4 spec-block generation. Stage4 will split and re-select from your returned passages, so include a bounded superset of passages that may constrain implementation.
7. Keep the superset relevant: include parent/shared algorithm context only when it defines this module's interface, timing, data semantics, instantiation usage, or correctness constraints.
8. Exclude chunks that merely mention the same project, algorithm, parent module, sibling module, examples, background, or verification intent without constraining MODULE_NAME.
9. If unsure, prefer a small number of medium-confidence directly related chunks over many low-confidence surrounding chunks.

Hard constraints:
- module must exactly match MODULE_NAME.
- block_id values must be contiguous S001, S002, ...
- text must be copied exactly from SOURCE_CHUNKS. Do not paraphrase or synthesize text.
- source_chunk_ids must refer only to ids in SOURCE_CHUNKS.
- fallback_used must be false.
- Do not output Markdown or prose outside JSON.
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
