from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class MergeContextRetrievalResult(BaseModel):
    schema_version: str = Field(default="merge_context_retrieval_v1")
    module: str = Field(..., min_length=1)
    selected_spec_refs: List[str] = Field(..., min_length=1)
    use_kg_child_context: bool = Field(default=False)
    kg_child_modules: List[str] = Field(default_factory=list)
    kg_child_context_reason: str = Field(default="")
    code_gap_notes: List[str] = Field(default_factory=list)
    selection_reason: List[str] = Field(default_factory=list)
    fallback_used: bool = Field(default=False)


class BlockSpecSelection(BaseModel):
    id: str = Field(..., min_length=1)
    target: str = Field(..., min_length=1)
    spec_refs: List[str] = Field(..., min_length=1)
    selection_reason: List[str] = Field(default_factory=list)


class BlockSpecRetrievalResult(BaseModel):
    schema_version: str = Field(default="block_spec_retrieval_v1")
    module: str = Field(..., min_length=1)
    selections: List[BlockSpecSelection] = Field(..., min_length=1)
    fallback_used: bool = Field(default=False)
    fallback_reason: str = Field(default="")
