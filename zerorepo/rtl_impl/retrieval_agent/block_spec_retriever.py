from __future__ import annotations

import json
from typing import Any, List

from pydantic import BaseModel
from zerorepo.rtl_impl.process_observer import observed

from .prompts import block_spec_select
from .schemas import BlockSpecRetrievalResult, BlockSpecSelection
from .utils import block_id, block_text, blocks, interface_block_refs, repair_json_payload


class BlockSpecRetriever:
    """Select module spec blocks for each Stage3 skeleton block."""

    def __init__(self, llm_client: Any, logger: Any | None = None, output_root=None):
        self.llm_client = llm_client
        self.logger = logger
        self.output_root = output_root

    @observed('tool', '检索结构块的规格引用', tool='retrieve_spec_block',
              summarize=lambda r: f'为{len(r.selections)}个结构块整理规格引用；'+('使用降级检索。' if r.fallback_used else '已检查引用。'))
    def select_block_spec_refs(
        self,
        *,
        module_name: str,
        module_spec: Any,
        module_skeleton: str,
        skeleton_blocks: List[Any],
        skeleton_context: Any | None = None,
    ) -> BlockSpecRetrievalResult:
        prompt = block_spec_select.build_prompt(
            module_name=module_name,
            spec_block_candidates=self._format_spec_candidates(module_spec),
            module_skeleton=module_skeleton,
            required_blocks=self._to_pretty_json(self._format_required_blocks(skeleton_blocks, skeleton_context)),
            skeleton_context=self._to_pretty_json(skeleton_context),
        )
        self._print_console(
            title=f"BLOCK SPEC RETRIEVAL PROMPT [{module_name}]",
            body=(
                f"System Role:\n{block_spec_select.SYSTEM_ROLE}\n\n"
                f"User Prompt:\n{prompt}"
            ),
        )
        try:
            arguments = dict(system_prompt=block_spec_select.SYSTEM_ROLE, user_prompt=prompt, images=None)
            options = getattr(self.llm_client, "request_options", None)
            if options:
                arguments["request_options"] = options(stage="stage4_block_spec_retrieval", module=module_name,
                                                       output_root=self.output_root, retrieval=True)
            raw = self.llm_client.complete(**arguments)
            self._print_console(
                title=f"BLOCK SPEC RETRIEVAL RAW OUTPUT [{module_name}]",
                body=raw if isinstance(raw, str) else self._to_pretty_json(raw),
            )
            result = self._coerce_result(raw)
            self._validate_result(
                result,
                module_name=module_name,
                module_spec=module_spec,
                skeleton_blocks=skeleton_blocks,
            )
            self._print_console(
                title=f"BLOCK SPEC RETRIEVAL VALIDATED OUTPUT [{module_name}]",
                body=self._to_pretty_json(result),
            )
            return result
        except Exception as exc:  # noqa: BLE001 - retrieval fallback should preserve Stage4 behavior.
            if self.logger is not None:
                self.logger.warning(
                    "[block_spec_retrieval] Falling back to full spec for %s: %s",
                    module_name,
                    exc,
                )
            fallback = self.fallback_result(
                module_name=module_name,
                module_spec=module_spec,
                skeleton_blocks=skeleton_blocks,
                reason=str(exc),
            )
            self._print_console(
                title=f"BLOCK SPEC RETRIEVAL FALLBACK OUTPUT [{module_name}]",
                body=self._to_pretty_json(fallback),
            )
            return fallback

    def fallback_result(
        self,
        *,
        module_name: str,
        module_spec: Any,
        skeleton_blocks: List[Any],
        reason: str = "",
    ) -> BlockSpecRetrievalResult:
        refs = [block_id(item) for item in blocks(module_spec) if block_id(item)]
        return BlockSpecRetrievalResult(
            module=module_name,
            selections=[
                BlockSpecSelection(
                    id=self._subtask_id(block),
                    target=self._target(block),
                    spec_refs=list(refs),
                    selection_reason=["Fallback to full current-module spec blocks."],
                )
                for block in skeleton_blocks
            ],
            fallback_used=True,
            fallback_reason=f"Retrieval failed; using full module spec for every block. {reason}".strip(),
        )

    def _coerce_result(self, raw: Any) -> BlockSpecRetrievalResult:
        if isinstance(raw, BlockSpecRetrievalResult):
            return raw
        if isinstance(raw, BaseModel):
            payload = raw.model_dump()
        else:
            payload = repair_json_payload(raw)
        return BlockSpecRetrievalResult.model_validate(payload)

    def _validate_result(
        self,
        result: BlockSpecRetrievalResult,
        *,
        module_name: str,
        module_spec: Any,
        skeleton_blocks: List[Any],
    ) -> None:
        if result.schema_version != "block_spec_retrieval_v1":
            raise ValueError("schema_version must remain block_spec_retrieval_v1")
        if result.module != module_name:
            raise ValueError(f"module must equal {module_name}, got {result.module}")
        if result.fallback_used:
            raise ValueError("LLM result must not set fallback_used=true")
        if len(result.selections) != len(skeleton_blocks):
            raise ValueError(f"expected {len(skeleton_blocks)} selections, got {len(result.selections)}")

        valid_refs = {block_id(item) for item in blocks(module_spec)}
        interface_refs = set(interface_block_refs(module_spec))

        for index, (selection, expected_block) in enumerate(zip(result.selections, skeleton_blocks)):
            expected_id = self._subtask_id(expected_block)
            expected_target = self._target(expected_block)
            if selection.id != expected_id:
                raise ValueError(f"selection {index + 1}: id must be {expected_id}, got {selection.id}")
            if selection.target != expected_target:
                raise ValueError(f"{selection.id}: target must be {expected_target}, got {selection.target}")
            if not selection.spec_refs:
                raise ValueError(f"{selection.id}: spec_refs must not be empty")
            unknown_refs = [ref for ref in selection.spec_refs if ref not in valid_refs]
            if unknown_refs:
                raise ValueError(f"{selection.id}: unknown spec_refs {unknown_refs}")
            if index == 0 and self._block_kind(expected_block) == "decl":
                missing_interface_refs = sorted(interface_refs - set(selection.spec_refs))
                if missing_interface_refs:
                    raise ValueError(
                        f"{selection.id}: first declaration block must include interface spec_refs {missing_interface_refs}"
                    )

    def _format_spec_candidates(self, module_spec: Any) -> str:
        payload = [
            {
                "block_id": block_id(item),
                "text": block_text(item),
            }
            for item in blocks(module_spec)
        ]
        return self._to_pretty_json(payload)

    def _format_required_blocks(self, skeleton_blocks: List[Any], skeleton_context: Any | None) -> List[dict[str, Any]]:
        context_by_block_id = self._context_by_block_id(skeleton_context)
        payload: List[dict[str, Any]] = []
        for block in skeleton_blocks:
            block_id_value = self._attr(block, "block_id")
            entry = {
                "id": self._subtask_id(block),
                "target": self._target(block),
                "block_id": block_id_value,
                "block_label": self._attr(block, "block_label"),
                "block_kind": self._block_kind(block),
                "raw_text": self._attr(block, "raw_text"),
            }
            if block_id_value in context_by_block_id:
                entry["structured_context"] = context_by_block_id[block_id_value]
            payload.append(entry)
        return payload

    def _context_by_block_id(self, skeleton_context: Any | None) -> dict[str, dict[str, Any]]:
        if skeleton_context is None:
            return {}
        structural_blocks = self._get_list(skeleton_context, "structural_blocks")
        overlays = {
            str(self._get_value(item, "block_id")): item
            for item in self._get_list(skeleton_context, "block_behavior_overlays")
            if self._get_value(item, "block_id")
        }
        result: dict[str, dict[str, Any]] = {}
        for block in structural_blocks:
            block_id_value = str(self._get_value(block, "block_id"))
            if not block_id_value:
                continue
            result[block_id_value] = {
                "purpose": self._get_value(block, "purpose"),
                "code_shape": self._get_value(block, "code_shape"),
                "must_appear": self._get_value(block, "must_appear") or [],
                "may_appear": self._get_value(block, "may_appear") or [],
                "retrieval_focus": self._get_value(block, "retrieval_focus") or [],
                "behavior_overlay": overlays.get(block_id_value),
            }
        return result

    def _get_list(self, payload: Any, key: str) -> list[Any]:
        value = self._get_value(payload, key)
        return list(value or [])

    def _get_value(self, payload: Any, key: str) -> Any:
        if isinstance(payload, dict):
            return payload.get(key)
        return getattr(payload, key, None)

    def _subtask_id(self, block: Any) -> str:
        value = getattr(block, "subtask_id", None)
        if value is not None:
            return str(value)
        block_id_value = self._attr(block, "block_id")
        block_label = self._attr(block, "block_label")
        return f"{block_id_value}_{block_label}"

    def _target(self, block: Any) -> str:
        return self._attr(block, "target")

    def _block_kind(self, block: Any) -> str:
        return self._attr(block, "block_kind")

    def _attr(self, block: Any, key: str) -> str:
        if isinstance(block, dict):
            return str(block.get(key, ""))
        return str(getattr(block, key, ""))

    def _to_pretty_json(self, payload: Any) -> str:
        if payload is None:
            return ""
        return json.dumps(self._json_ready(payload), ensure_ascii=False, indent=2)

    def _print_console(self, *, title: str, body: str) -> None:
        print(f"\n========== {title} ==========\n{body}\n========== END {title} ==========\n", flush=True)

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
