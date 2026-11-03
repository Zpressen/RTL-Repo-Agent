from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable, List

from pydantic import BaseModel

from zerorepo.rtl_impl.port_contracts import extract_markdown_port_sections
from zerorepo.rtl_impl.process_observer import observed

from .prompts import module_spec_context_select
from .schemas import ModuleSpecContextBlock, ModuleSpecContextRetrievalResult, ModuleSpecSelectionResult
from .source_context import POLICY_VERSION, atomic_json, digest, source_ranges, strict_payload


class ModuleSpecContextRetriever:
    """Retrieve source spec passages for a planned module from unified specs."""

    def __init__(self, llm_client: Any, logger: Any | None = None, max_chunks: int = 24,
                 cache_root: str | Path | None = None, limits: dict | None = None):
        self.llm_client = llm_client
        self.logger = logger
        limits = limits or {}
        self.max_chunks = max(1, int(limits.get("max_chunks", max_chunks)))
        self.chunk_chars = int(limits.get("chunk_chars", 6000))
        self.candidate_chars = int(limits.get("candidate_chars", 48000))
        self.fact_chars = int(limits.get("fact_chars", 8000))
        self.prompt_chars = int(limits.get("prompt_chars", 64000))
        if min(self.chunk_chars, self.candidate_chars, self.fact_chars, self.prompt_chars) < 1:
            raise ValueError("Retrieval character budgets must be positive")
        self.cache_root = Path(cache_root) if cache_root is not None else None
        self.cache_enabled = True
        self.stage_name = "stage3_spec_retrieval"
        self.last_input_summary = {}

    @observed('tool', '检索模块规格原文', tool='retrieve_spec_block',
              summarize=lambda r: f'返回{len(r.blocks)}个规格片段；'+('使用保留原文的降级检索，相关性未确认。' if r.fallback_used else '已检查引用与原文一致。'))
    def select_module_spec_context(
        self, *, module_name: str, spec_md_files: Iterable[str], repo_module: Any | None = None,
        fact_ledger: Any | None = None, skeleton_context: str = "", is_top_module: bool = False,
        primary_spec_file: str = "",
    ) -> ModuleSpecContextRetrievalResult:
        sources = self._read_sources(spec_md_files)
        chunks = self._build_source_chunks(sources)
        ranked = self._rank_chunks(module_name, chunks, repo_module=repo_module, fact_ledger=fact_ledger)
        mandatory = self._mandatory_port_chunks(chunks, is_top_module=is_top_module, primary_spec_file=primary_spec_file)
        pool = []
        used = set()
        for chunk in [*mandatory, *(ranked or chunks)]:
            if chunk["chunk_id"] in used:
                continue
            if len(pool) >= self.max_chunks or sum(len(c["text"]) for c in pool) + len(chunk["text"]) > self.candidate_chars:
                continue
            used.add(chunk["chunk_id"])
            pool.append(chunk)
        facts = self._fact_context(module_name, fact_ledger)
        repo_context = self._json_ready(repo_module) if repo_module is not None else {}
        if isinstance(repo_context, dict):
            repo_context = {k: v for k, v in repo_context.items() if k in {
                "module", "role", "parents", "children", "instance_hints", "rationale", "module_decision"}}
        hint = skeleton_context if len(skeleton_context) <= 4000 else ""
        def build():
            return module_spec_context_select.build_prompt(
                module_name=module_name, repo_module_json=self._to_pretty_json(repo_context),
                fact_context_json=self._to_pretty_json(facts),
                source_chunks_json=self._to_pretty_json(self._format_chunks(self._sort_chunks_by_source_order(pool))),
                skeleton_context=hint)
        prompt = build()
        # Drop lowest-priority optional inputs; never cut source text mid-prompt.
        while len(prompt) + len(module_spec_context_select.SYSTEM_ROLE) > self.prompt_chars and pool:
            pool.pop()
            prompt = build()
        prompt_chunks = self._sort_chunks_by_source_order(pool)
        self.last_input_summary = {
            "policy": POLICY_VERSION, "prompt_chars": len(prompt) + len(module_spec_context_select.SYSTEM_ROLE),
            "candidate_count": len(pool), "candidate_chars": sum(len(c["text"]) for c in pool),
            "fact_chars": len(self._to_pretty_json(facts)),
            "omitted_fact_ids": list(self.omitted_fact_ids),
            "omitted_chunk_ids": [c["chunk_id"] for c in chunks if c not in pool],
            "mandatory_local_ids": [c["chunk_id"] for c in mandatory if c not in pool],
        }
        config = getattr(self.llm_client, "config", None)
        model = {name: getattr(config, name, None) for name in ("model", "provider", "base_url", "temperature", "top_p", "max_tokens")}
        model["reasoning_effort"] = getattr(config, "extra", {}).get("reasoning_effort") if config else None
        key = digest({"policy": POLICY_VERSION, "sources": sources, "module": module_name,
                      "repo": repo_context, "facts": self._related_facts, "candidates": pool,
                      "mandatory": mandatory, "prompt": prompt, "model": model,
                      "request_policy": getattr(self.llm_client, "request_policy", {})})
        safe_module = re.sub(r"[^A-Za-z0-9_.-]", "_", module_name)
        path = self.cache_root / f"{safe_module}.json" if self.cache_root else None
        if path and self.cache_enabled and path.exists():
            try:
                cached = strict_payload(path.read_text())
                if cached["input_fingerprint"] != key or cached["result_digest"] != digest(cached["result"]):
                    raise ValueError("Retrieval cache fingerprint/digest mismatch")
                result = ModuleSpecContextRetrievalResult.model_validate(cached["result"])
                self._validate_result(result, module_name=module_name, all_chunks=chunks, allow_fallback=True)
                if not {c["chunk_id"] for c in mandatory} <= {i for b in result.blocks for i in b.source_chunk_ids}:
                    raise ValueError("Cached mandatory port sections missing")
                if self.logger:
                    self.logger.info("[module_spec_context_retrieval] Reusing cache for %s (degraded=%s)", module_name, result.fallback_used)
                return result
            except (ValueError, KeyError, TypeError) as exc:
                if self.logger:
                    self.logger.info("[module_spec_context_retrieval] Ignoring cache for %s: %s", module_name, exc)
        if self.logger:
            self.logger.info("[module_spec_context_retrieval] Input budget for %s: %s", module_name, self.last_input_summary)
        try:
            if not prompt_chunks or len(prompt) + len(module_spec_context_select.SYSTEM_ROLE) > self.prompt_chars:
                raise ValueError("No source candidates fit the retrieval input budget")
            self._print_console(title=f"MODULE SPEC CONTEXT RETRIEVAL PROMPT [{module_name}]",
                                body=f"System Role:\n{module_spec_context_select.SYSTEM_ROLE}\n\nUser Prompt:\n{prompt}")
            arguments = dict(system_prompt=module_spec_context_select.SYSTEM_ROLE, user_prompt=prompt, images=None)
            options = getattr(self.llm_client, "request_options", None)
            if options:
                arguments["request_options"] = options(stage=self.stage_name, module=module_name,
                    output_root=self.cache_root.parent.parent if self.cache_root else None, retrieval=True)
            raw = self.llm_client.complete(**arguments)
            self._print_console(title=f"MODULE SPEC CONTEXT RETRIEVAL RAW OUTPUT [{module_name}]",
                                body=raw if isinstance(raw, str) else self._to_pretty_json(raw))
            result = self._coerce_result(raw, module_name=module_name, chunks=prompt_chunks)
            result = self._ensure_mandatory_chunks(result, mandatory_chunks=mandatory)
            self._validate_result(result, module_name=module_name, all_chunks=chunks)
        except Exception as exc:
            if self.logger:
                self.logger.warning("[module_spec_context_retrieval] DEGRADE %s: %s", module_name, exc)
            result = self.fallback_result(module_name=module_name, chunks=chunks,
                ranked_chunks=prompt_chunks, mandatory_chunks=mandatory, reason=str(exc))
        if path:
            atomic_json(path, {"input_fingerprint": key, "result_digest": digest(result.model_dump()),
                              "result": result.model_dump(), "input_summary": self.last_input_summary})
        self._print_console(title=f"MODULE SPEC CONTEXT RETRIEVAL {'FALLBACK' if result.fallback_used else 'VALIDATED'} OUTPUT [{module_name}]",
                            body=self._to_pretty_json(result))
        return result

    def fallback_result(
        self,
        *,
        module_name: str,
        chunks: List[dict[str, str]],
        ranked_chunks: List[dict[str, str]] | None = None,
        mandatory_chunks: List[dict[str, str]] | None = None,
        reason: str = "",
    ) -> ModuleSpecContextRetrievalResult:
        mandatory = list(mandatory_chunks or [])
        mandatory_ids = {chunk["chunk_id"] for chunk in mandatory}
        selected = self._sort_chunks_by_source_order(
            [
                *mandatory,
                *[
                    chunk
                    for chunk in list(ranked_chunks or [])
                    if chunk["chunk_id"] not in mandatory_ids
                ],
            ]
        )
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
                    source_ranges=self._ranges([chunk]),
                    relevance_reason=["Heuristic fallback selected this source passage."],
                    confidence="low" if reason else "medium",
                )
                for index, chunk in enumerate(selected, start=1)
            ],
            open_issues=[f"module context uncertain for {module_name}"],
            fallback_used=True,
            fallback_reason=fallback_reason,
        )

    def _mandatory_port_chunks(
        self,
        chunks: List[dict[str, str]],
        *,
        is_top_module: bool,
        primary_spec_file: str,
    ) -> List[dict[str, str]]:
        if not is_top_module or not str(primary_spec_file or "").strip():
            return []
        primary = str(Path(primary_spec_file).resolve())
        return [
            chunk
            for chunk in chunks
            if str(Path(chunk["source_file"]).resolve()) == primary
            and (chunk.get("port_section") or bool(extract_markdown_port_sections(chunk["text"])))
        ]

    def _ensure_mandatory_chunks(
        self,
        result: ModuleSpecContextRetrievalResult,
        *,
        mandatory_chunks: List[dict[str, str]],
    ) -> ModuleSpecContextRetrievalResult:
        selected_ids = {
            chunk_id
            for block in result.blocks
            for chunk_id in block.source_chunk_ids
        }
        blocks = [block.model_dump() for block in result.blocks]
        for chunk in mandatory_chunks:
            if chunk["chunk_id"] in selected_ids:
                continue
            blocks.append(
                {
                    "block_id": "",
                    "text": chunk["text"],
                    "source_file": chunk["source_file"],
                    "source_chunk_ids": [chunk["chunk_id"]],
                    "source_ranges": self._ranges([chunk]),
                    "relevance_reason": ["Mandatory top-level port-table section."],
                    "confidence": "high",
                }
            )
        blocks.sort(
            key=lambda block: min(
                (self._chunk_sort_key(chunk_id) for chunk_id in block.get("source_chunk_ids") or []),
                default=(10**9, ""),
            )
        )
        for index, block in enumerate(blocks, start=1):
            block["block_id"] = f"S{index:03d}"
        payload = result.model_dump()
        payload["blocks"] = blocks
        return ModuleSpecContextRetrievalResult.model_validate(payload)

    def _coerce_result(self, raw: Any, *, module_name: str, chunks: List[dict[str, str]]) -> ModuleSpecContextRetrievalResult:
        payload = strict_payload(raw)
        if payload.get("module") != module_name:
            raise ValueError(f"module must equal {module_name}")
        chunk_by_id = {chunk["chunk_id"]: chunk for chunk in chunks}
        if "selections" in payload:
            selection = ModuleSpecSelectionResult.model_validate(payload)
            selected = {}
            for item in selection.selections:
                if item.source_chunk_id not in chunk_by_id:
                    raise ValueError(f"Unknown source_chunk_id: {item.source_chunk_id}")
                selected.setdefault(item.source_chunk_id, item)
            blocks = []
            for chunk in chunks:
                item = selected.get(chunk["chunk_id"])
                if item is not None:
                    blocks.append(ModuleSpecContextBlock(block_id=f"S{len(blocks)+1:03d}",
                        text=chunk["text"], source_file=chunk["source_file"], source_chunk_ids=[chunk["chunk_id"]],
                        source_ranges=self._ranges([chunk]),
                        relevance_reason=item.relevance_reason, confidence=item.confidence))
            return ModuleSpecContextRetrievalResult(module=module_name, blocks=blocks, open_issues=selection.open_issues)
        # Legacy full responses still require verifiable source attribution.
        if payload.get("fallback_used"):
            raise ValueError("LLM result must not set fallback_used=true")
        normalized = []
        for block in payload.get("blocks") or []:
            item = dict(block)
            ids = item.get("source_chunk_ids") or []
            if any(i not in chunk_by_id for i in ids):
                raise ValueError("Unknown legacy source_chunk_ids")
            if ids:
                source_files = {chunk_by_id[i]["source_file"] for i in ids}
                if len(source_files) != 1:
                    raise ValueError("A source block cannot combine different files")
                file = next(iter(source_files))
                if item.get("source_file") and item["source_file"] != file:
                    raise ValueError("Legacy source_file does not match cited chunks")
                expected = "\n\n".join(chunk_by_id[i]["text"] for i in ids)
                text = str(item.get("text") or "")
                if text and text.strip() != expected.strip() and not any(text.strip() in chunk_by_id[i]["text"] for i in ids):
                    raise ValueError("Legacy text must be copied from its cited source specs")
                item["text"] = text or expected
                item["source_file"] = file
            else:
                # Older backends supplied exact passages without chunk IDs.
                text = str(item.get("text") or "").strip()
                file = item.get("source_file") or ""
                by_file = {}
                for c in chunks:
                    by_file.setdefault(c["source_file"], []).append(c)
                matches = [(f, cs) for f, cs in by_file.items()
                           if (not file or f == file) and text and text in "".join(c["text"] for c in cs)]
                if len(matches) != 1:
                    raise ValueError("Legacy text must be copied from source specs")
                file, cs = matches[0]
                combined = "".join(c["text"] for c in cs)
                first = combined.index(text)
                last = first + len(text)
                position = 0
                ids = []
                for c in cs:
                    if position < last and position + len(c["text"]) > first:
                        ids.append(c["chunk_id"])
                    position += len(c["text"])
                item.update(text=text, source_file=file, source_chunk_ids=ids)
            item["block_id"] = f"S{len(normalized)+1:03d}"
            item["source_ranges"] = self._ranges([chunk_by_id[i] for i in ids])
            normalized.append(item)
        payload["blocks"] = normalized
        return ModuleSpecContextRetrievalResult.model_validate(payload)

    def _validate_result(self, result, *, module_name, all_chunks, allow_fallback=False):
        if result.schema_version != "module_spec_context_retrieval_v1" or result.module != module_name:
            raise ValueError("Retrieval schema/module mismatch")
        if result.fallback_used and not allow_fallback:
            raise ValueError("LLM result must not set fallback_used=true")
        by_id = {c["chunk_id"]: c for c in all_chunks}
        for index, block in enumerate(result.blocks, 1):
            if not block.text.strip():
                raise ValueError("Source block text must be nonempty")
            if block.block_id != f"S{index:03d}" or not block.source_chunk_ids:
                raise ValueError("Invalid source block identity")
            cited = [by_id[i] for i in block.source_chunk_ids if i in by_id]
            if len(cited) != len(block.source_chunk_ids) or any(c["source_file"] != block.source_file for c in cited):
                raise ValueError("Unknown or mismatched source references")
            if block.source_ranges and block.source_ranges != self._ranges(cited):
                raise ValueError("Source ranges do not match cited chunks")
            # Exact substring checks support legacy selected excerpts, without accepting altered wording.
            contiguous = "".join(c["text"] for c in cited)
            joined = "\n\n".join(c["text"] for c in cited)
            if block.text.strip() not in contiguous and block.text.strip() != joined.strip():
                raise ValueError(f"{block.block_id}: text must be copied from its cited source specs")

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
                        "text": candidate.read_text(encoding="utf-8").replace("\r\n", "\n"),
                    }
                )
        return sources

    def _build_source_chunks(self, sources):
        chunks = []
        for source in sources:
            text = source["text"]
            mandatory_spans = []
            for section in extract_markdown_port_sections(text):
                first = text.find(section.text)
                if first >= 0:
                    mandatory_spans.append((first, first + len(section.text)))
            for span in source_ranges(text, self.chunk_chars):
                chunk = {"chunk_id": f"C{len(chunks)+1:03d}", "source_file": source["source_file"],
                         "text": text[span["start"]:span["end"]], **span,
                         "port_section": any(span["start"] < last and span["end"] > first for first, last in mandatory_spans)}
                if chunk["text"].strip():
                    chunks.append(chunk)
        return chunks

    def _split_markdown_chunks(self, text):
        normalized = text.replace("\r\n", "\n").strip()
        return [normalized[s["start"]:s["end"]].strip() for s in source_ranges(normalized, self.chunk_chars)]

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

    def _fact_context(self, module_name, fact_ledger):
        facts = self._get_list(fact_ledger, "facts")
        terms = set(self._module_name_terms(module_name)) - {"sdc", "aes", "controller", "system"}
        related = []
        for index, fact in enumerate(facts):
            payload = self._json_ready(fact)
            haystack = json.dumps(payload, ensure_ascii=False).lower()
            direct = str(payload.get("module") or "").strip() == module_name
            if direct or any(term and term in haystack for term in terms):
                compact = {k: v for k, v in payload.items() if k not in {"text_grounding", "image_grounding", "notes"}}
                related.append((not direct, index, compact))
        result = []
        self._related_facts = [fact for _, _, fact in sorted(related)]
        self.omitted_fact_ids = []
        for _, _, fact in sorted(related):
            if len(result) < 24 and len(self._to_pretty_json([*result, fact])) <= self.fact_chars:
                result.append(fact)
            else:
                self.omitted_fact_ids.append(fact.get("fact_id", ""))
        return result

    def _format_chunks(self, chunks):
        return [{k: c[k] for k in ("chunk_id", "source_file", "text", "start", "end", "heading_path") if k in c}
                for c in chunks]

    @staticmethod
    def _ranges(chunks):
        return [{"source_chunk_id": c["chunk_id"], **{k: c[k] for k in ("start", "end", "heading_path") if k in c}}
                for c in chunks]

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
