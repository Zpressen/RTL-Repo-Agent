from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class AtomType(str, Enum):
    INTERFACE = "interface"
    STATE = "state"
    BEHAVIOR = "behavior"
    PROTOCOL = "protocol"
    CONTROL = "control"
    SUBMODULE_HINT = "submodule_hint"
    CONFIG = "config"
    CONSTRAINT = "constraint"


class SourceModality(str, Enum):
    TEXT = "text"
    TABLE = "table"
    IMAGE = "image"


class DocumentArchetype(str, Enum):
    ALGORITHMIC_PIPELINE = "algorithmic_pipeline"
    MULTI_INTERFACE_CONTROLLER = "multi_interface_controller"
    GENERIC = "generic"


class EvidenceSpanKind(str, Enum):
    PARAGRAPH = "paragraph"
    LIST_BLOCK = "list_block"
    TABLE_GROUP = "table_group"
    IMAGE_REGION = "image_region"


class EvidenceRole(str, Enum):
    CONTENT = "content"
    HEADER_ONLY = "header_only"
    IMAGE_REF = "image_ref"
    IMAGE_REGION = "image_region"


class AtomScope(str, Enum):
    BUNDLE = "bundle"
    CLUSTER = "cluster"
    MODE = "mode"
    STEP = "step"
    HINT = "hint"
    CONSTRAINT = "constraint"


class LocalDomainTag(str, Enum):
    CONTROL_FSM = "control_fsm"
    STATE_STORAGE = "state_storage"
    DATAPATH_TRANSFORM = "datapath_transform"
    PROTOCOL_CMD = "protocol_cmd"
    PROTOCOL_DATA = "protocol_data"
    BUS_SLAVE = "bus_slave"
    BUS_MASTER_DMA = "bus_master_dma"
    DESCRIPTOR_MANAGEMENT = "descriptor_management"
    FIFO_BUFFERING = "fifo_buffering"
    CLOCK_RESET = "clock_reset"
    INTERRUPT_STATUS = "interrupt_status"
    EXPLICIT_SUBMODULE = "explicit_submodule"
    TOP_GLUE = "top_glue"


class ResponsibilityAtomType(str, Enum):
    INTERFACE_BUNDLE = "interface_bundle"
    STATE_CLUSTER = "state_cluster"
    CONTROL_MODE = "control_mode"
    PROTOCOL_EXCHANGE = "protocol_exchange"
    BEHAVIOR_STEP = "behavior_step"
    CONFIG_GATE = "config_gate"
    SUBMODULE_HINT = "submodule_hint"
    CONSTRAINT_OR_TEMPORAL = "constraint_or_temporal"


class PlannerTaskInput(BaseModel):
    task_id: str = Field(..., min_length=1)
    spec_md_files: List[str] = Field(..., min_length=1)
    spec_images: List[str] = Field(default_factory=list)
    project_type: str = Field(default="light_repo_spec2rtl")
    notes: str = Field(default="")
    required_top_module: str = Field(default="", pattern=r"^(?:[A-Za-z_][A-Za-z0-9_$]*)?$")
    top_spec_file: str = Field(default="")

    @model_validator(mode="after")
    def validate_inputs(self) -> "PlannerTaskInput":
        self.spec_md_files = [item.strip() for item in self.spec_md_files if str(item).strip()]
        self.spec_images = [item.strip() for item in self.spec_images if str(item).strip()]
        if not self.spec_md_files:
            raise ValueError("spec_md_files must contain at least one Markdown file path.")
        return self


class DocumentOrganizationLabel(str, Enum):
    INTERFACE_CENTRIC = "interface-centric"
    STATEFUL_CONTROL_CENTRIC = "stateful-control-centric"
    PIPELINE_STEP_CENTRIC = "pipeline-step-centric"
    EXPLICIT_DECOMPOSITION_CENTRIC = "explicit-decomposition-centric"
    OPERATION_PROCEDURE_CENTRIC = "operation-procedure-centric"
    PHYSICAL_IO_CENTRIC = "physical-io-centric"


class ImageRegionType(str, Enum):
    DOMAIN_REGION = "domain_region"
    SUBMODULE_BOX = "submodule_box"
    CLUSTER_REGION = "cluster_region"
    STATE_GROUP = "state_group"
    PIPELINE_CHAIN = "pipeline_chain"
    INTERFACE_REGION = "interface_region"
    HELPER_REGION = "helper_region"


_IMAGE_REGION_TYPE_ALIASES = {
    "interface_boundary": ImageRegionType.INTERFACE_REGION.value,
    "interface_block": ImageRegionType.INTERFACE_REGION.value,
    "io_boundary": ImageRegionType.INTERFACE_REGION.value,
    "interface_box": ImageRegionType.INTERFACE_REGION.value,
    "abstract_module": ImageRegionType.SUBMODULE_BOX.value,
    "datapath_block": ImageRegionType.SUBMODULE_BOX.value,
    "key_block": ImageRegionType.SUBMODULE_BOX.value,
    "module_box": ImageRegionType.SUBMODULE_BOX.value,
    "module_region": ImageRegionType.SUBMODULE_BOX.value,
    "component_box": ImageRegionType.SUBMODULE_BOX.value,
    "state_machine": ImageRegionType.STATE_GROUP.value,
    "fsm": ImageRegionType.STATE_GROUP.value,
    "pipeline_stage": ImageRegionType.PIPELINE_CHAIN.value,
    "pipeline_region": ImageRegionType.PIPELINE_CHAIN.value,
    "control_cluster": ImageRegionType.CLUSTER_REGION.value,
    "control_block": ImageRegionType.CLUSTER_REGION.value,
}


def _normalize_image_region_type(value: Any) -> Any:
    if isinstance(value, ImageRegionType):
        return value
    text = str(value or "").strip()
    if not text:
        return value
    normalized = text.lower()
    mapped = _IMAGE_REGION_TYPE_ALIASES.get(normalized, normalized)
    return mapped


class PlannerImageType(str, Enum):
    BLOCK_DIAGRAM = "block_diagram"
    FLOW_DIAGRAM = "flow_diagram"
    TIMING_DIAGRAM = "timing_diagram"
    STATE_MACHINE = "state_machine"
    TABLE = "table"
    MIXED = "mixed"


class DocumentOrganizationProfile(BaseModel):
    labels: List[DocumentOrganizationLabel] = Field(..., min_length=1)
    rationale: str = Field(..., min_length=1)


class GroundedGlobalAssertion(BaseModel):
    statement: str = Field(..., min_length=1)
    provenance_tags: List[Literal["spec", "image"]] = Field(..., min_length=1)
    supporting_fragment_ids: List[str] = Field(default_factory=list)
    supporting_image_ids: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_grounding(self) -> "GroundedGlobalAssertion":
        provenance = set(self.provenance_tags)
        if "spec" in provenance and not self.supporting_fragment_ids:
            raise ValueError("spec-grounded assertions must include supporting_fragment_ids")
        if "image" in provenance and not self.supporting_image_ids:
            raise ValueError("image-grounded assertions must include supporting_image_ids")
        return self


class ProjectMemoryCard(BaseModel):
    project_name: str = Field(..., min_length=1)
    top_goal: str = Field(..., min_length=1)
    main_modules: List[str] = Field(default_factory=list)
    top_interfaces: List[str] = Field(default_factory=list)
    clock_reset: str = Field(default="")
    dataflow_keywords: List[str] = Field(default_factory=list)
    protocol_keywords: List[str] = Field(default_factory=list)
    global_constraints: List[str] = Field(default_factory=list)
    terminology_map: Dict[str, str] = Field(default_factory=dict)
    functional_domains: List[str] = Field(default_factory=list)
    control_states: List[str] = Field(default_factory=list)
    round_structure: List[str] = Field(default_factory=list)
    global_timing_styles: List[GroundedGlobalAssertion] = Field(default_factory=list)
    global_control_constraints: List[GroundedGlobalAssertion] = Field(default_factory=list)
    global_implementation_hints: List[GroundedGlobalAssertion] = Field(default_factory=list)
    future_annotations: Dict[str, Any] = Field(default_factory=dict)


class ImageStructuralRegion(BaseModel):
    region_id: str = Field(..., min_length=1)
    region_type: ImageRegionType
    label: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)
    entities: List[str] = Field(default_factory=list)
    canonical_entities: List[str] = Field(default_factory=list)
    related_sections: List[str] = Field(default_factory=list)
    fragmentation_hints: List[str] = Field(default_factory=list)

    @field_validator("region_type", mode="before")
    @classmethod
    def normalize_region_type(cls, value: Any) -> Any:
        return _normalize_image_region_type(value)


class ImageDigest(BaseModel):
    image_id: str = Field(..., min_length=1)
    image_file: str = Field(..., min_length=1)
    global_summary: str = Field(..., min_length=1)
    structural_regions: List[ImageStructuralRegion] = Field(default_factory=list)
    entities: List[str] = Field(default_factory=list)
    canonical_entities: List[str] = Field(default_factory=list)
    spec_grounding: List[str] = Field(default_factory=list)
    fragmentation_hints: List[str] = Field(default_factory=list)


class EntityAliasGroup(BaseModel):
    canonical_name: str = Field(..., min_length=1)
    aliases: List[str] = Field(..., min_length=1)


class ImagePrescan(BaseModel):
    image_id: str = Field(..., min_length=1)
    image_file: str = Field(..., min_length=1)
    image_type: PlannerImageType
    visible_text: List[str] = Field(default_factory=list)
    suspected_modules: List[str] = Field(default_factory=list)
    candidate_sections: List[str] = Field(default_factory=list)
    suspected_topics: List[str] = Field(default_factory=list)
    caption_text: str = Field(default="")
    figure_ref: str = Field(default="")


class ImageCardRegion(BaseModel):
    region_id: str = Field(..., min_length=1)
    region_type: ImageRegionType
    label: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)
    entities: List[str] = Field(default_factory=list)
    canonical_entities: List[str] = Field(default_factory=list)
    related_sections: List[str] = Field(default_factory=list)
    fragmentation_hints: List[str] = Field(default_factory=list)
    linked_fragment_ids: List[str] = Field(default_factory=list)

    @field_validator("region_type", mode="before")
    @classmethod
    def normalize_region_type(cls, value: Any) -> Any:
        return _normalize_image_region_type(value)


class ImageCard(BaseModel):
    image_id: str = Field(..., min_length=1)
    image_file: str = Field(..., min_length=1)
    image_type: PlannerImageType
    global_summary: str = Field(..., min_length=1)
    structural_regions: List[ImageCardRegion] = Field(default_factory=list)
    visible_text: List[str] = Field(default_factory=list)
    entities: List[str] = Field(default_factory=list)
    canonical_entities: List[str] = Field(default_factory=list)
    spec_grounding: List[str] = Field(default_factory=list)
    linked_fragment_ids: List[str] = Field(default_factory=list)
    candidate_sections: List[str] = Field(default_factory=list)
    fragmentation_hints: List[str] = Field(default_factory=list)
    terminology_updates: Dict[str, str] = Field(default_factory=dict)


class SpecFragment(BaseModel):
    fragment_id: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)
    raw_text: str = Field(..., min_length=1)
    section_path: str = Field(..., min_length=1)
    source_md_file: str = Field(..., min_length=1)
    linked_image_ids: List[str] = Field(default_factory=list)
    linked_image_region_ids: List[str] = Field(default_factory=list)
    locality_rationale: str = Field(..., min_length=1)
    anchor_entities: List[str] = Field(default_factory=list)
    canonical_anchor_entities: List[str] = Field(default_factory=list)
    retrieval_terms: List[str] = Field(default_factory=list)
    section_keywords: List[str] = Field(default_factory=list)
    caption_refs: List[str] = Field(default_factory=list)
    ordering_index: int = Field(..., ge=1)
