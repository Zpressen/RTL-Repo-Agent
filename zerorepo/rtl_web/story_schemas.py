"""Versioned, bounded story contracts. No execution or model dependencies."""
from typing import Literal
from pydantic import Field, model_validator
from .schemas import Model, CaseId

class Evidence(Model):
    kind: Literal['run', 'version', 'validation', 'artifact']
    id: str = Field(min_length=1, max_length=240, pattern=r'^[A-Za-z0-9_.-]+$')
    sha256: str | None = Field(default=None, pattern=r'^[0-9a-f]{64}$')

class Review(Model):
    status: Literal['draft', 'approved'] = 'draft'
    reviewer: str = Field(default='', max_length=120)
    evidence_refs: list[Evidence] = Field(default_factory=list, max_length=100)

class Optimization(Model):
    state: Literal['awaiting_data'] = 'awaiting_data'
    message: str = 'PPA 数据待接入'
    missing_evidence: list[str] = Field(default_factory=lambda: ['同条件版本测量', '测量报告与功能验证绑定'], max_length=12)

class MemoryRevision(Model):
    memory_id: str = Field(min_length=1, max_length=240)
    revision_id: str = Field(min_length=1, max_length=240)
    content_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    parent_revision_id: str | None = None
    title: str = Field(max_length=300)
    lesson: str = Field(max_length=8000)
    applicability: list[str] = Field(default_factory=list, max_length=30)
    limitations: list[str] = Field(default_factory=list, max_length=30)
    source_run_id: str
    source_version_id: str | None = None
    backend: str = Field(max_length=80)
    validation_level: Literal['unverified', 'syntax', 'module_sim', 'final_system', 'formal'] = 'unverified'
    state: Literal['draft', 'approved_active', 'superseded', 'retired'] = 'draft'
    evidence_refs: list[Evidence] = Field(default_factory=list, max_length=100)

class UseEvent(Model):
    event_id: str = Field(max_length=240)
    kind: Literal['retrieved', 'provided', 'application_declared', 'applied', 'validation_observed']
    event_artifact_id: str
    candidate_version_id: str | None = None
    validation_id: str | None = None
    decision: Literal['apply', 'reject', 'not_applicable'] | None = None
    reason: str = Field(default='', max_length=2000)

class MemoryUse(Model):
    use_id: str
    revision_id: str
    run_id: str
    internal_run_id: str = ''
    backend: str
    snapshot_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    events: list[UseEvent] = Field(default_factory=list, max_length=200)

class LifecycleEvent(Model):
    event_id: str
    revision_id: str
    kind: Literal['approved', 'superseded', 'retired']
    replacement_revision_id: str | None = None
    reason: str = Field(min_length=1, max_length=2000)
    evidence_refs: list[Evidence] = Field(default_factory=list, max_length=100)

class Comparison(Model):
    comparison_id: str
    with_memory_run_id: str
    without_memory_run_id: str
    with_conditions: dict[str, str]
    without_conditions: dict[str, str]
    sample_count: Literal[1] = 1
    limitations: list[str] = Field(default_factory=list)
    evidence_refs: list[Evidence] = Field(default_factory=list, max_length=100)

class StoryBundle(Model):
    schema_version: Literal['rtl-demo-story-v1'] = 'rtl-demo-story-v1'
    story_id: str | None = None
    case_id: CaseId
    origin: Literal['historical'] = 'historical'
    material_kind: Literal['real', 'synthetic']
    source_fingerprint: str = Field(pattern=r'^[0-9a-f]{64}$')
    review: Review
    optimization: Optimization = Field(default_factory=Optimization)
    memories: list[MemoryRevision] = Field(default_factory=list, max_length=100)
    uses: list[MemoryUse] = Field(default_factory=list, max_length=100)
    lifecycle_events: list[LifecycleEvent] = Field(default_factory=list, max_length=200)
    comparisons: list[Comparison] = Field(default_factory=list, max_length=20)
    evidence_refs: list[Evidence] = Field(default_factory=list, max_length=1000)

    @model_validator(mode='after')
    def relationships(self):
        revisions = {m.revision_id: m for m in self.memories}
        if len(revisions) != len(self.memories) or len({u.use_id for u in self.uses}) != len(self.uses):
            raise ValueError('Duplicate story entity')
        for m in self.memories:
            if m.parent_revision_id and (m.parent_revision_id not in revisions or revisions[m.parent_revision_id].memory_id != m.memory_id):
                raise ValueError('Missing or foreign parent revision')
            seen = {m.revision_id}
            parent = m.parent_revision_id
            while parent:
                if parent in seen:
                    raise ValueError('Cyclic memory revisions')
                if parent not in revisions:
                    raise ValueError('Missing parent revision')
                seen.add(parent)
                parent = revisions[parent].parent_revision_id
        for use in self.uses:
            if use.revision_id not in revisions:
                raise ValueError('Missing memory revision')
        for event in self.lifecycle_events:
            if event.revision_id not in revisions or (event.replacement_revision_id and event.replacement_revision_id not in revisions):
                raise ValueError('Missing lifecycle revision')
        return self

class StoryFile(Model):
    source: str
    storage_key: str
    sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    size_bytes: int = Field(ge=0, le=128*1024**2)

class StoryInput(Model):
    schema_version: Literal['rtl-demo-story-input-v1'] = 'rtl-demo-story-input-v1'
    story: StoryBundle
    records: list[dict] = Field(default_factory=list, max_length=5000)
    files: list[StoryFile] = Field(default_factory=list, max_length=10000)
