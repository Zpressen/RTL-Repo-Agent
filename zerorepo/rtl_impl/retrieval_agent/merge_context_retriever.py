from __future__ import annotations
from zerorepo.rtl_impl.process_observer import observed

import json
from zerorepo.rtl_impl.artifact_layout import ArtifactLayout
from typing import Any

from pydantic import BaseModel

from .prompts import merge_context_select
from .schemas import MergeContextRetrievalResult
from .utils import block_id, block_text, blocks, interface_block_refs, repair_json_payload


class MergeContextRetriever:
    """Select module spec blocks needed by Stage6 merge."""

    def __init__(self, llm_client: Any, logger: Any | None = None, output_root=None):
        self.llm_client = llm_client
        self.logger = logger
        self.output_root = output_root

    @observed('tool', '检索RTL合并的规格与依赖上下文', tool='retrieve_spec_block',
              summarize=lambda r: f'选择{len(r.selected_spec_refs)}个规格引用、{len(r.kg_child_modules)}个子模块上下文；'+('使用降级结果。' if r.fallback_used else '已检查引用。'))
    def select_spec_refs(
        self,
        *,
        module_name: str,
        module_spec: Any,
        module_skeleton: str,
        generated_fragments: str,
        module_plan: Any | None = None,
        dependency_context: Any | None = None,
    ) -> MergeContextRetrievalResult:
        prompt = merge_context_select.build_prompt(
            module_name=module_name,
            spec_block_candidates=self._format_spec_candidates(module_spec),
            module_skeleton=module_skeleton,
            module_plan=self._to_pretty_json(module_plan),
            dependency_context=self._to_pretty_json(dependency_context),
            generated_fragments=generated_fragments,
        )
        self._print_console(
            title=f"MERGE CONTEXT RETRIEVAL PROMPT [{module_name}]",
            body=(
                f"System Role:\n{merge_context_select.SYSTEM_ROLE}\n\n"
                f"User Prompt:\n{prompt}"
            ),
        )
        try:
            raw = self.llm_client.complete(
                system_prompt=merge_context_select.SYSTEM_ROLE,
                user_prompt=prompt,
                images=None,
            )
            self._print_console(
                title=f"MERGE CONTEXT RETRIEVAL RAW OUTPUT [{module_name}]",
                body=raw if isinstance(raw, str) else self._to_pretty_json(raw),
            )
            result = self._coerce_result(raw)
            self._validate_result(result, module_name=module_name, module_spec=module_spec)
            self._print_console(
                title=f"MERGE CONTEXT RETRIEVAL VALIDATED OUTPUT [{module_name}]",
                body=self._to_pretty_json(result),
            )
            return result
        except Exception as exc:  # noqa: BLE001 - retrieval fallback should preserve Stage6 behavior.
            if self.logger is not None:
                self.logger.warning(
                    "[merge_context_retrieval] Falling back to full spec for %s: %s",
                    module_name,
                    exc,
                )
            fallback = self.fallback_result(module_name=module_name, module_spec=module_spec, reason=str(exc))
            self._print_console(
                title=f"MERGE CONTEXT RETRIEVAL FALLBACK OUTPUT [{module_name}]",
                body=self._to_pretty_json(fallback),
            )
            return fallback

    def fallback_result(
        self,
        *,
        module_name: str,
        module_spec: Any,
        reason: str = "",
    ) -> MergeContextRetrievalResult:
        refs = [block_id(block) for block in blocks(module_spec)]
        return MergeContextRetrievalResult(
            module=module_name,
            selected_spec_refs=refs,
            use_kg_child_context=False,
            kg_child_modules=[],
            kg_child_context_reason="Retrieval failed; do not request extra KG child context during fallback.",
            code_gap_notes=[f"Retrieval failed; using full module spec. {reason}".strip()],
            selection_reason=["Fallback to full current-module spec blocks."],
            fallback_used=True,
        )

    def _coerce_result(self, raw: Any) -> MergeContextRetrievalResult:
        if isinstance(raw, MergeContextRetrievalResult):
            return raw
        if isinstance(raw, BaseModel):
            payload = raw.model_dump()
        else:
            payload = repair_json_payload(raw)
        return MergeContextRetrievalResult.model_validate(payload)

    def _validate_result(
        self,
        result: MergeContextRetrievalResult,
        *,
        module_name: str,
        module_spec: Any,
    ) -> None:
        if result.schema_version != "merge_context_retrieval_v1":
            raise ValueError("schema_version must remain merge_context_retrieval_v1")
        if result.module != module_name:
            raise ValueError(f"module must equal {module_name}, got {result.module}")
        if result.fallback_used:
            raise ValueError("LLM result must not set fallback_used=true")
        valid_refs = {block_id(block) for block in blocks(module_spec)}
        unknown = [ref for ref in result.selected_spec_refs if ref not in valid_refs]
        if unknown:
            raise ValueError(f"unknown selected_spec_refs: {unknown}")
        if not result.selected_spec_refs:
            raise ValueError("selected_spec_refs must not be empty")
        interface_refs = interface_block_refs(module_spec)
        if interface_refs and not any(ref in result.selected_spec_refs for ref in interface_refs):
            raise ValueError(f"selected_spec_refs must include an interface block: {interface_refs}")

    def _format_spec_candidates(self, module_spec: Any) -> str:
        payload = [
            {
                "block_id": block_id(block),
                "text": block_text(block),
            }
            for block in blocks(module_spec)
        ]
        return self._to_pretty_json(payload)

    def _to_pretty_json(self, payload: Any) -> str:
        if payload is None:
            return ""
        return json.dumps(self._json_ready(payload), ensure_ascii=False, indent=2)

    def _print_console(self, *, title: str, body: str) -> None:
        if self.logger:
            self.logger.info("[%s] %s (%d chars)", type(self).__name__, title, len(body))
        root = getattr(self, "output_root", None)
        if root is not None and getattr(self.llm_client, "retention", "compact") == "full":
            path = ArtifactLayout(root).traces(getattr(self, "stage_name", "stage6_retrieval"), "events") / "retrieval.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({"title": title, "body": body}, ensure_ascii=False) + "\n")

    def _json_ready(self, payload: Any) -> Any:
        if isinstance(payload, BaseModel):
            return payload.model_dump()
        if isinstance(payload, list):
            return [self._json_ready(item) for item in payload]
        if isinstance(payload, dict):
            return {key: self._json_ready(value) for key, value in payload.items()}
        if isinstance(payload, tuple):
            return [self._json_ready(item) for item in payload]
        if isinstance(payload, set):
            return sorted(self._json_ready(item) for item in payload)
        return payload
