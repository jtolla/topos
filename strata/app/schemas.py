from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models import ExposureLevel, FileEventType, SensitivityLevel, SensitivityType

# ============================================================================
# Admin Schemas
# ============================================================================


class TenantCreate(BaseModel):
    name: str


class TenantResponse(BaseModel):
    id: UUID
    name: str
    created_at: datetime
    api_key: str | None = None  # Only returned on creation


class EstateCreate(BaseModel):
    name: str


class EstateResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    created_at: datetime


class ShareCreate(BaseModel):
    estate_id: UUID
    name: str
    share_type: str = "SMB"
    root_path: str


class ShareResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    estate_id: UUID
    name: str
    share_type: str
    root_path: str
    created_at: datetime


# ============================================================================
# Ingestion Schemas
# ============================================================================


class AclEntryInput(BaseModel):
    principal_external_id: str
    principal_display_name: str | None = None
    principal_type: str = "USER"  # USER, GROUP, SERVICE
    rights: str  # R, RW, FULL
    source: str = "FILE"  # FILE, INHERITED


class FileEventInput(BaseModel):
    type: FileEventType
    share_name: str
    relative_path: str
    size_bytes: int | None = None
    mtime: datetime | None = None
    file_type: str | None = None
    content_hash: str | None = None
    acl_hash: str | None = None
    acl_entries: list[AclEntryInput] | None = None


class IngestEventsRequest(BaseModel):
    agent_id: str
    events: list[FileEventInput]


class IngestEventsResponse(BaseModel):
    processed: int
    jobs_created: int


# ============================================================================
# Query Schemas
# ============================================================================


class QueryScope(BaseModel):
    share_id: UUID | None = None
    path_prefix: str | None = None


class FindSensitiveContentRequest(BaseModel):
    scope: QueryScope | None = None
    sensitivity_types: list[SensitivityType] | None = None
    exposure_levels: list[ExposureLevel] | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=100)


class SensitivitySummary(BaseModel):
    PERSONAL_DATA: int = 0
    HEALTH_DATA: int = 0
    FINANCIAL_DATA: int = 0
    SECRETS: int = 0
    OTHER: int = 0


class AccessSummary(BaseModel):
    broad_groups: list[str] = []
    principal_count_bucket: str = "0-10"


class SensitiveContentItem(BaseModel):
    document_id: UUID
    file_id: UUID
    share_id: UUID
    relative_path: str
    file_type: str
    sensitivity_summary: dict[str, int]
    exposure_level: ExposureLevel
    exposure_score: int
    access_summary: AccessSummary


class FindSensitiveContentResponse(BaseModel):
    items: list[SensitiveContentItem]
    page: int
    page_size: int
    total: int


class SearchChunksRequest(BaseModel):
    query: str
    scope: QueryScope | None = None
    k: int = Field(default=20, ge=1, le=100)


class ChunkSearchResult(BaseModel):
    chunk_id: UUID
    document_id: UUID
    file_id: UUID
    relative_path: str
    snippet: str
    score: float


class SearchChunksResponse(BaseModel):
    results: list[ChunkSearchResult]


# ============================================================================
# Dashboard Schemas
# ============================================================================


class DashboardMetrics(BaseModel):
    total_files: int
    total_documents: int
    documents_with_findings: int
    high_exposure_documents: int
    findings_by_type: dict[str, int]
    documents_by_exposure: dict[str, int]


# ============================================================================
# Document Detail Schemas
# ============================================================================


class SensitivityFindingDetail(BaseModel):
    id: UUID
    sensitivity_type: SensitivityType
    sensitivity_level: SensitivityLevel
    snippet: str
    created_at: datetime


class DocumentDetailResponse(BaseModel):
    id: UUID
    file_id: UUID
    share_id: UUID
    relative_path: str
    title: str
    file_type: str
    size_bytes: int
    last_indexed_at: datetime
    exposure_level: ExposureLevel | None
    exposure_score: int | None
    access_summary: AccessSummary | None
    findings: list[SensitivityFindingDetail]


# ============================================================================
# v0.1: Agent Schemas
# ============================================================================


class AgentCreate(BaseModel):
    name: str
    description: str | None = None


class AgentResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    description: str | None
    api_key: str | None = None  # Only returned on creation
    created_at: datetime


class AgentSearchChunksRequest(BaseModel):
    """Search request with agent identity for policy enforcement."""

    query: str
    scope: QueryScope | None = None
    k: int = Field(default=20, ge=1, le=100)
    agent_id: UUID | None = None  # Optional agent ID for policy enforcement
    user_id: str | None = None  # External user ID for audit


class AgentSearchChunksResponse(BaseModel):
    """Search response with interaction trace ID."""

    results: list[ChunkSearchResult]
    interaction_id: UUID | None = None  # For observability trace


# ============================================================================
# v0.1: Observability Schemas
# ============================================================================


class RetrievedChunkDetail(BaseModel):
    chunk_id: UUID
    rank: int
    score: float | None
    view_type: str
    was_filtered: bool
    filter_reason: str | None = None


class InteractionTraceResponse(BaseModel):
    interaction_id: UUID
    interaction_type: str
    query: str
    scope: dict | None
    chunks_retrieved: list[RetrievedChunkDetail]
    answer: str | None
    evidence_coverage: float | None
    latency_ms: int | None
    agent_id: UUID | None
    user_id: str | None
    created_at: datetime | None = None


class InteractionListItem(BaseModel):
    interaction_id: UUID
    interaction_type: str
    query: str
    chunk_count: int
    latency_ms: int | None
    created_at: datetime


class InteractionListResponse(BaseModel):
    items: list[InteractionListItem]
    total: int


class AgentStatsResponse(BaseModel):
    total_interactions: int
    interactions_by_type: dict[str, int]
    avg_latency_ms: float | None
    total_chunks_retrieved: int
    filtered_chunks: int


# ============================================================================
# v0.1: Answer with Evidence Schemas
# ============================================================================


class AnswerWithEvidenceRequest(BaseModel):
    question: str
    scope: QueryScope | None = None
    agent_id: UUID | None = None
    user_id: str | None = None
    k: int = Field(default=10, ge=1, le=50)  # Number of chunks to retrieve


class EvidenceChunk(BaseModel):
    chunk_id: UUID
    document_id: UUID
    file_id: UUID
    relative_path: str
    section_path: list[str] | None = None
    text: str
    score: float | None


class AnswerWithEvidenceResponse(BaseModel):
    answer: str
    evidence: list[EvidenceChunk]
    evidence_coverage: float | None  # How well the evidence supports the answer
    interaction_id: UUID  # For observability trace


# ============================================================================
# v0.1: Semantic Diff Schemas
# ============================================================================


class SemanticDiffRequest(BaseModel):
    from_version_id: UUID
    to_version_id: UUID


class FieldChangeDetail(BaseModel):
    field_name: str
    old_value: str | None
    new_value: str | None
    change_type: str  # added, removed, modified


class SemanticDiffResponse(BaseModel):
    from_version_id: UUID
    to_version_id: UUID
    field_changes: list[FieldChangeDetail]
    summary: str
