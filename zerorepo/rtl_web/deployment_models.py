"""Private deployment contracts, separate from browser payload models."""
from __future__ import annotations
from pathlib import PurePosixPath
import re
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

PACKAGES = {'design','runtime','seed','verifier','ops'}
RECORD_KINDS = {'bundle','run','version','validation','artifact','story'}


def relative_path(value: str) -> str:
    if (not isinstance(value,str) or not value or '\\' in value or '\x00' in value
        or any(ord(c)<32 for c in value) or PurePosixPath(value).is_absolute()
        or any(p in {'','.', '..'} for p in value.split('/'))):
        raise ValueError('Unsafe relative path')
    return value


class Contract(BaseModel):
    model_config=ConfigDict(extra='forbid')


class FileEntry(Contract):
    package: Literal['design','runtime','seed','verifier','ops']
    source_relative_path: str
    target_relative_path: str
    purpose: str
    visibility: Literal['design_protected','runtime_private','ops_private']
    size_bytes: int=Field(ge=0)
    sha256: str=Field(pattern=r'^[0-9a-f]{64}$')
    mode: int=Field(default=0o600,ge=0,le=0o755)
    _paths=field_validator('source_relative_path','target_relative_path')(relative_path)


class HistoricalInput(Contract):
    case_id: str
    run_id: str
    kind: Literal['contracts','audit']
    artifact_id: str|None=None
    expected_sha256: str|None=None
    status: Literal['present','missing']


class HistoricalSeed(Contract):
    schema_version: Literal['rtl-demo-seed-v1','rtl-demo-seed-v2']='rtl-demo-seed-v1'
    stories: dict[str,str] | None = None
    seed_id: str
    cases: dict[str,str]
    records: list[dict[str,Any]]
    files: list[dict[str,Any]]
    historical_inputs: list[HistoricalInput]=Field(default_factory=list)
    evidence_hashes: dict[str,str]=Field(default_factory=dict)
    total_bytes: int=Field(ge=0)
    export_tool_version: str='1'


class DeploymentRelease(Contract):
    schema_version: Literal['rtl-demo-deploy-v1']='rtl-demo-deploy-v1'
    target_origin: Literal['https://agent.deepvalleychip.cn','https://design.deepvalleychip.cn']='https://design.deepvalleychip.cn'
    release_id: str=Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$')
    created_at: str
    source_revision: str
    source_dirty: bool
    platform: dict[str,Any]
    cases: dict[str,Any]
    files: list[FileEntry]
    lock_hashes: dict[str,str]
    state: Literal['staged','prepared','active_unverified','accepted','failed','rolled_back']='staged'


class JobDescriptor(Contract):
    schema_version: Literal['rtl-demo-job-v1']='rtl-demo-job-v1'
    operation_id: str
    run_id: str
    case_id: str
    kind: Literal['verify','fix','generate_and_verify']
    release_id: str
    inputs: dict[str,Any]
    budgets: dict[str,int]
    kg_partition: str


class JobResult(Contract):
    operation_id: str
    run_id: str
    release_id: str
    verdict: Literal['pass','fail','unverified']
    artifacts: dict[str,Any]


class CapabilityCheck(Contract):
    readiness: Literal['ready','blocked']
    missing: list[str]
    acceptance: Literal['not_run','passed','failed']='not_run'
    checked_at: str
    release_id: str
    evidence_refs: list[str]=Field(default_factory=list)


class AcceptanceRecord(Contract):
    criterion: str=Field(pattern=r'^SC-00[1-9]$|^SC-01[0-2]$')
    release_id: str
    host: str
    origin: Literal['https://agent.deepvalleychip.cn','https://design.deepvalleychip.cn']
    state: Literal['passed','failed','not_run']
    evidence: list[dict[str,Any]]
