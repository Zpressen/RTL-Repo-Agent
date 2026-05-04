from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field, model_validator


class SpecBlock(BaseModel):
    block_id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)


class ModuleSpecBlocks(BaseModel):
    module: str = Field(..., min_length=1)
    source_spec_file: str = Field(..., min_length=1)
    blocks: List[SpecBlock] = Field(..., min_length=1)


class Stage4SpecBlocksArtifact(BaseModel):
    schema_version: str = Field(default="spec_blocks_v1")
    task_id: str = Field(..., min_length=1)
    module_order: List[str] = Field(..., min_length=1)
    modules: List[ModuleSpecBlocks] = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_structure(self) -> "Stage4SpecBlocksArtifact":
        module_names = [item.module for item in self.modules]
        if module_names != self.module_order:
            raise ValueError("modules[].module must exactly match module_order")
        for module in self.modules:
            for index, block in enumerate(module.blocks, start=1):
                expected_id = f"S{index:03d}"
                if block.block_id != expected_id:
                    raise ValueError(
                        f"{module.module}: block_id must be contiguous from S001; "
                        f"expected {expected_id}, got {block.block_id}"
                    )
                if not block.text.strip():
                    raise ValueError(f"{module.module}: block {block.block_id} text must not be empty")
        return self
