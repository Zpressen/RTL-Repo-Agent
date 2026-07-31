from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable, List

from pydantic import BaseModel

from .prompts import module_spec_context_select
from .schemas import ModuleSpecContextBlock, ModuleSpecContextRetrievalResult
from .utils import repair_json_payload


class ModuleSpecContextRetriever:
    """Retrieve source spec passages for a planned module from unified specs."""

    def __init__(self, llm_client: Any, logger: Any | None = None, max_chunks: int = 24):
        self.llm_client = llm_client
        self.logger = logger
        self.max_chunks = max(4, max_chunks)

    def select_module_spec_context(
        self,
        *,
        module_name: str,
        spec_md_files: Iterable[str],
        repo_module: Any | None = None,
        fact_ledger: Any | None = None,
        skeleton_context: str = "",
    ) -> ModuleSpecContextRetrievalResult:
        sources = self._read_sources(spec_md_files)
        chunks = self._build_source_chunks(sources)
        ranked_chunks = self._rank_chunks(module_name, chunks, repo_module=repo_module, fact_ledger=fact_ledger)
        prompt_chunks = self._sort_chunks_by_source_order(ranked_chunks[: self.max_chunks] or chunks[: self.max_chunks])
        if not prompt_chunks:
            return self._empty_fallback(module_name)

        prompt = module_spec_context_select.build_prompt(
            module_name=module_name,
            repo_module_json=self._to_pretty_json(repo_module),
            fact_context_json=self._to_pretty_json(self._fact_context(module_name, fact_ledger)),
            source_chunks_json=self._to_pretty_json(self._format_chunks(prompt_chunks)),
            skeleton_context=skeleton_context,
        )
        self._print_console(
            title=f"MODULE SPEC CONTEXT RETRIEVAL PROMPT [{module_name}]",
            body=(
                f"System Role:\n{module_spec_context_select.SYSTEM_ROLE}\n\n"
                f"User Prompt:\n{prompt}"
            ),
        )
        try:
            raw = self.llm_client.complete(
                system_prompt=module_spec_context_select.SYSTEM_ROLE,
                user_prompt=prompt,
                images=None,
            )
            self._print_console(
                title=f"MODULE SPEC CONTEXT RETRIEVAL RAW OUTPUT [{module_name}]",
                body=raw if isinstance(raw, str) else self._to_pretty_json(raw),
            )
            result = self._coerce_result(raw, module_name=module_name, chunks=prompt_chunks)
            self._validate_result(result, module_name=module_name, all_chunks=chunks)
            self._print_console(
                title=f"MODULE SPEC CONTEXT RETRIEVAL VALIDATED OUTPUT [{module_name}]",
                body=self._to_pretty_json(result),
            )
            return result
        except Exception as exc:  # noqa: BLE001 - retrieval fallback should keep planning moving.
            if self.logger is not None:
                self.logger.warning(
                    "[module_spec_context_retrieval] Falling back for %s: %s",
                    module_name,
                    exc,
                )
            fallback = self.fallback_result(
                module_name=module_name,
                chunks=chunks,
                ranked_chunks=ranked_chunks,
                reason=str(exc),
            )
            self._print_console(
                title=f"MODULE SPEC CONTEXT RETRIEVAL FALLBACK OUTPUT [{module_name}]",
                body=self._to_pretty_json(fallback),
            )
            return fallback

    def fallback_result(
        self,
        *,
        module_name: str,
        chunks: List[dict[str, str]],
        ranked_chunks: List[dict[str, str]] | None = None,
        reason: str = "",
    ) -> ModuleSpecContextRetrievalResult:
        selected = self._sort_chunks_by_source_order(list(ranked_chunks or [])[:6])
        fallback_reason = f"Module context retrieval failed; using heuristic source chunks. {reason}".strip()
        if not selected and chunks:
            selected = chunks[:1]
            fallback_reason = f"No heuristic source chunk matched; using full/first source chunk. {reason}".strip()
        if not selected:
            return self._empty_fallback(module_name, reason=reason)
        return ModuleSpecContextRetrievalResult(
            module=module_name,
            blocks=[
                ModuleSpecContextBlock(
                    block_id=f"S{index:03d}",
                    text=chunk["text"],
                    source_file=chunk["source_file"],
                    source_chunk_ids=[chunk["chunk_id"]],
                    relevance_reason=["Heuristic fallback selected this source passage."],
                    confidence="low" if reason else "medium",
                )
                for index, chunk in enumerate(selected, start=1)
            ],
            open_issues=[f"module context uncertain for {module_name}"],
            fallback_used=True,
            fallback_reason=fallback_reason,
        )

    def _coerce_result(
        self,
        raw: Any,
        *,
        module_name: str,
        chunks: List[dict[str, str]],
    ) -> ModuleSpecContextRetrievalResult:
        if isinstance(raw, ModuleSpecContextRetrievalResult):
            payload = raw.model_dump()
        elif isinstance(raw, BaseModel):
            payload = raw.model_dump()
        else:
            payload = repair_json_payload(raw)
        payload.setdefault("module", module_name)
        chunk_by_id = {chunk["chunk_id"]: chunk for chunk in chunks}
        normalized_blocks: list[dict[str, Any]] = []
        for index, block in enumerate(payload.get("blocks") or [], start=1):
            item = dict(block)
            item["block_id"] = f"S{index:03d}"
            chunk_ids = [str(value) for value in item.get("source_chunk_ids") or [] if str(value).strip()]
            if chunk_ids and (not str(item.get("text") or "").strip()):
                item["text"] = "\n\n".join(
                    chunk_by_id[chunk_id]["text"] for chunk_id in chunk_ids if chunk_id in chunk_by_id
                ).strip()
            if not item.get("source_file") and chunk_ids:
                item["source_file"] = next(
                    (chunk_by_id[chunk_id]["source_file"] for chunk_id in chunk_ids if chunk_id in chunk_by_id),
                    "",
                )
            normalized_blocks.append(item)
        payload["blocks"] = normalized_blocks
        return ModuleSpecContextRetrievalResult.model_validate(payload)

    def _validate_result(
        self,
        result: ModuleSpecContextRetrievalResult,
        *,
        module_name: str,
        all_chunks: List[dict[str, str]],
    ) -> None:
        if result.schema_version != "module_spec_context_retrieval_v1":
            raise ValueError("schema_version must remain module_spec_context_retrieval_v1")
        if result.module != module_name:
            raise ValueError(f"module must equal {module_name}, got {result.module}")
        if result.fallback_used:
            raise ValueError("LLM result must not set fallback_used=true")
        source_text_by_file: dict[str, str] = {}
        for chunk in all_chunks:
            source_text_by_file.setdefault(chunk["source_file"], "")
            source_text_by_file[chunk["source_file"]] += "\n" + chunk["text"]
        valid_chunk_ids = {chunk["chunk_id"] for chunk in all_chunks}
        for index, block in enumerate(result.blocks, start=1):
            expected_id = f"S{index:03d}"
            if block.block_id != expected_id:
                raise ValueError(f"expected block_id {expected_id}, got {block.block_id}")
            unknown_chunk_ids = [chunk_id for chunk_id in block.source_chunk_ids if chunk_id not in valid_chunk_ids]
            if unknown_chunk_ids:
                raise ValueError(f"{block.block_id}: unknown source_chunk_ids {unknown_chunk_ids}")
            if not self._text_appears_in_sources(block.text, source_text_by_file):
                raise ValueError(f"{block.block_id}: text must be copied from source specs")

    def _read_sources(self, spec_md_files: Iterable[str]) -> List[dict[str, str]]:
        sources: list[dict[str, str]] = []
        seen: set[Path] = set()
        for item in spec_md_files:
            if not str(item).strip():
                continue
            path = Path(item).resolve()
            if path.is_dir():
                candidates = sorted(path.glob("*.md"))
            else:
                sibling_markdown = sorted(path.parent.glob("*.md"))
                candidates = [path, *[candidate for candidate in sibling_markdown if candidate != path]]
            for candidate in candidates:
                if candidate in seen or not candidate.exists() or not candidate.is_file():
                    continue
                seen.add(candidate)
                sources.append(
                    {
                        "source_file": str(candidate),
                        "text": candidate.read_text(encoding="utf-8").replace("\r\n", "\n").strip(),
                    }
                )
        return sources

    def _build_source_chunks(self, sources: List[dict[str, str]]) -> List[dict[str, str]]:
        chunks: list[dict[str, str]] = []
        for source in sources:
            for text in self._split_markdown_chunks(source["text"]):
                chunks.append(
                    {
                        "chunk_id": f"C{len(chunks) + 1:03d}",
                        "source_file": source["source_file"],
                        "text": text,
                    }
                )
        return chunks

    def _split_markdown_chunks(self, text: str) -> List[str]:
        normalized = text.replace("\r\n", "\n").strip()
        if not normalized:
            return []
        lines = normalized.splitlines()
        heading_indexes = [
            index
            for index, line in enumerate(lines)
            if re.match(r"^\s{0,3}#{1,4}\s+\S", line) or re.match(r"^\s*\*\*\s*\d+(?:\.\d+)*\.?\s+\S.*\*\*\s*$", line)
        ]
        if not heading_indexes:
            return [normalized]
        chunks: list[str] = []
        for heading_index, start in enumerate(heading_indexes):
            if heading_index == 0:
                start = 0
            end = heading_indexes[heading_index + 1] if heading_index + 1 < len(heading_indexes) else len(lines)
            chunk = "\n".join(lines[start:end]).strip()
            if chunk:
                chunks.append(chunk)
        return chunks or [normalized]

    def _rank_chunks(
        self,
        module_name: str,
        chunks: List[dict[str, str]],
        *,
        repo_module: Any | None,
        fact_ledger: Any | None,
    ) -> List[dict[str, str]]:
        terms = self._retrieval_terms(module_name, repo_module=repo_module, fact_ledger=fact_ledger)
        scored: list[tuple[int, int, dict[str, str]]] = []
        for index, chunk in enumerate(chunks):
            text = chunk["text"].lower()
            score = sum(1 for term in terms if term and term in text)
            if score:
                scored.append((score, -index, chunk))
        scored.sort(reverse=True)
        return [chunk for _, _, chunk in scored]

    def _sort_chunks_by_source_order(self, chunks: List[dict[str, str]]) -> List[dict[str, str]]:
        return sorted(chunks, key=lambda chunk: self._chunk_sort_key(chunk.get("chunk_id", "")))

    def _chunk_sort_key(self, chunk_id: str) -> tuple[int, str]:
        match = re.search(r"(\d+)$", str(chunk_id))
        if match:
            return int(match.group(1)), str(chunk_id)
        return 10**9, str(chunk_id)

    def _retrieval_terms(self, module_name: str, *, repo_module: Any | None, fact_ledger: Any | None) -> List[str]:
        terms: list[str] = []
        terms.extend(self._module_name_terms(module_name))
        for key in ["role", "rationale", "module_decision"]:
            terms.extend(self._words(self._get_value(repo_module, key)))
        for key in ["parents", "children"]:
            for value in self._get_list(repo_module, key):
                terms.extend(self._module_name_terms(str(value)))
        for hint in self._get_list(repo_module, "instance_hints"):
            terms.extend(self._module_name_terms(str(self._get_value(hint, "module") or "")))
            terms.extend(self._words(self._get_value(hint, "usage")))
        for fact in self._fact_context(module_name, fact_ledger):
            terms.extend(self._words(fact.get("category")))
            terms.extend(self._words(fact.get("subject")))
            terms.extend(self._words(fact.get("predicate")))
            terms.extend(self._words(json.dumps(fact.get("object") or {}, ensure_ascii=False)))
        seen: set[str] = set()
        result: list[str] = []
        for term in terms:
            normalized = str(term).strip().lower()
            if len(normalized) < 3 or normalized in seen:
                continue
            seen.add(normalized)
            result.append(normalized)
        return result

    def _module_name_terms(self, module_name: str) -> List[str]:
        name = module_name.strip().lower()
        if not name:
            return []
        pieces = [part for part in re.split(r"[_\W]+", name) if part]
        terms = [name, name.replace("_", " "), name.replace("_", "-")]
        terms.extend(part for part in pieces if part not in {"aes", "top", "module"})
        if "sbox" in name:
            terms.extend(["sbox", "s-box", "subbytes", "substitution"])
        if "rcon" in name:
            terms.extend(["rcon", "round constant", "round constants"])
        if "key" in pieces:
            terms.extend(["key expansion", "round key"])
        return terms

    def _words(self, value: Any) -> List[str]:
        text = str(value or "").lower()
        return [word for word in re.findall(r"[a-zA-Z_][\w-]{2,}", text) if word not in {"the", "and", "for", "with"}]

    def _fact_context(self, module_name: str, fact_ledger: Any | None) -> List[dict[str, Any]]:
        facts = self._get_list(fact_ledger, "facts")
        module_terms = set(self._module_name_terms(module_name))
        related: list[dict[str, Any]] = []
        for fact in facts:
            payload = self._json_ready(fact)
            haystack = json.dumps(payload, ensure_ascii=False).lower()
            fact_module = str(payload.get("module") or "").strip()
            if fact_module == module_name or any(term and term in haystack for term in module_terms):
                related.append(payload)
        return related[:24]

    def _format_chunks(self, chunks: List[dict[str, str]]) -> List[dict[str, str]]:
        return [
            {
                "chunk_id": chunk["chunk_id"],
                "source_file": chunk["source_file"],
                "text": chunk["text"],
            }
            for chunk in chunks
        ]

    def _text_appears_in_sources(self, text: str, source_text_by_file: dict[str, str]) -> bool:
        needle = self._normalize_text(text)
        if not needle:
            return False
        return any(needle in self._normalize_text(source_text) for source_text in source_text_by_file.values())

    def _empty_fallback(self, module_name: str, reason: str = "") -> ModuleSpecContextRetrievalResult:
        return ModuleSpecContextRetrievalResult(
            module=module_name,
            blocks=[
                ModuleSpecContextBlock(
                    block_id="S001",
                    text=f"No source specification text was available for {module_name}.",
                    source_file="",
                    relevance_reason=["Empty fallback block."],
                    confidence="low",
                )
            ],
            open_issues=[f"module context unavailable for {module_name}"],
            fallback_used=True,
            fallback_reason=reason or "No source specs were available.",
        )

    def _get_list(self, payload: Any, key: str) -> list[Any]:
        value = self._get_value(payload, key)
        return list(value or [])

    def _get_value(self, payload: Any, key: str) -> Any:
        if payload is None:
            return None
        if isinstance(payload, dict):
            return payload.get(key)
        return getattr(payload, key, None)

    def _to_pretty_json(self, payload: Any) -> str:
        if payload is None:
            return ""
        return json.dumps(self._json_ready(payload), ensure_ascii=False, indent=2)

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

    def _normalize_text(self, text: str) -> str:
        return re.sub(r"\s+", " ", str(text or "").strip())

    def _print_console(self, *, title: str, body: str) -> None:
        print(f"\n========== {title} ==========\n{body}\n========== END {title} ==========\n", flush=True)
