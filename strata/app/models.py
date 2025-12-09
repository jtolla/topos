import enum
from datetime import datetime
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ============================================================================
# Enums
# ============================================================================


class PrincipalType(str, enum.Enum):
    USER = "USER"
    GROUP = "GROUP"
    SERVICE = "SERVICE"


class SensitivityType(str, enum.Enum):
    PERSONAL_DATA = "PERSONAL_DATA"
    HEALTH_DATA = "HEALTH_DATA"
    FINANCIAL_DATA = "FINANCIAL_DATA"
    SECRETS = "SECRETS"
    OTHER = "OTHER"


class SensitivityLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ExposureLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class JobType(str, enum.Enum):
    EXTRACT_CONTENT = "EXTRACT_CONTENT"
    ENRICH_CHUNKS = "ENRICH_CHUNKS"
    CLASSIFY_DOCUMENT = "CLASSIFY_DOCUMENT"
    EXTRACT_SEMANTICS = "EXTRACT_SEMANTICS"
    COMPUTE_DIFF = "COMPUTE_DIFF"


class DocType(str, enum.Enum):
    CONTRACT = "CONTRACT"
    POLICY = "POLICY"
    RFC = "RFC"
    OTHER = "OTHER"


class JobStatus(str, enum.Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class FileEventType(str, enum.Enum):
    FILE_DISCOVERED = "FILE_DISCOVERED"
    FILE_MODIFIED = "FILE_MODIFIED"
    FILE_DELETED = "FILE_DELETED"
    ACL_CHANGED = "ACL_CHANGED"


# ============================================================================
# Core Multi-Tenancy
# ============================================================================


class Tenant(Base):
    __tablename__ = "tenant"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    api_key_hash: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationships
    estates: Mapped[list["Estate"]] = relationship(back_populates="tenant", cascade="all, delete")
    shares: Mapped[list["Share"]] = relationship(back_populates="tenant", cascade="all, delete")
    principals: Mapped[list["Principal"]] = relationship(
        back_populates="tenant", cascade="all, delete"
    )


# ============================================================================
# Estates, Shares, Files
# ============================================================================


class Estate(Base):
    __tablename__ = "estate"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="estates")
    shares: Mapped[list["Share"]] = relationship(back_populates="estate", cascade="all, delete")


class Share(Base):
    __tablename__ = "share"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False
    )
    estate_id: Mapped[UUID] = mapped_column(
        ForeignKey("estate.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    share_type: Mapped[str] = mapped_column(Text, nullable=False)  # 'SMB'
    root_path: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="shares")
    estate: Mapped["Estate"] = relationship(back_populates="shares")
    files: Mapped[list["File"]] = relationship(back_populates="share", cascade="all, delete")


class File(Base):
    __tablename__ = "file"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False
    )
    share_id: Mapped[UUID] = mapped_column(
        ForeignKey("share.id", ondelete="CASCADE"), nullable=False
    )
    relative_path: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mtime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    file_type: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    acl_hash: Mapped[str] = mapped_column(Text, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "share_id", "relative_path", name="uq_file_path"),
        Index("ix_file_tenant_share", "tenant_id", "share_id"),
    )

    # Relationships
    share: Mapped["Share"] = relationship(back_populates="files")
    acl_entries: Mapped[list["FileAclEntry"]] = relationship(
        back_populates="file", cascade="all, delete"
    )
    effective_access: Mapped[list["FileEffectiveAccess"]] = relationship(
        back_populates="file", cascade="all, delete"
    )
    documents: Mapped[list["Document"]] = relationship(back_populates="file", cascade="all, delete")


# ============================================================================
# Principals, Groups, ACLs
# ============================================================================


class Principal(Base):
    __tablename__ = "principal"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[PrincipalType] = mapped_column(Enum(PrincipalType), nullable=False)
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "external_id", name="uq_principal_external_id"),
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="principals")


class GroupMembership(Base):
    __tablename__ = "group_membership"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False
    )
    group_id: Mapped[UUID] = mapped_column(
        ForeignKey("principal.id", ondelete="CASCADE"), nullable=False
    )
    member_principal_id: Mapped[UUID] = mapped_column(
        ForeignKey("principal.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "group_id", "member_principal_id", name="uq_group_membership"
        ),
    )


class FileAclEntry(Base):
    __tablename__ = "file_acl_entry"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False
    )
    file_id: Mapped[UUID] = mapped_column(ForeignKey("file.id", ondelete="CASCADE"), nullable=False)
    principal_id: Mapped[UUID] = mapped_column(ForeignKey("principal.id"), nullable=False)
    rights: Mapped[str] = mapped_column(Text, nullable=False)  # 'R', 'RW', 'FULL'
    source: Mapped[str] = mapped_column(Text, nullable=False)  # 'FILE' | 'INHERITED'
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    # Relationships
    file: Mapped["File"] = relationship(back_populates="acl_entries")


class FileEffectiveAccess(Base):
    __tablename__ = "file_effective_access"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False
    )
    file_id: Mapped[UUID] = mapped_column(ForeignKey("file.id", ondelete="CASCADE"), nullable=False)
    principal_id: Mapped[UUID] = mapped_column(ForeignKey("principal.id"), nullable=False)
    can_read: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "file_id", "principal_id", name="uq_file_effective_access"),
        Index("ix_file_effective_access_file", "tenant_id", "file_id"),
    )

    # Relationships
    file: Mapped["File"] = relationship(back_populates="effective_access")


# ============================================================================
# Documents, Chunks, Embeddings
# ============================================================================


class Document(Base):
    __tablename__ = "document"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False
    )
    file_id: Mapped[UUID] = mapped_column(ForeignKey("file.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    file_type: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    last_indexed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    # v0.1: Versioning
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    previous_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("document.id", ondelete="SET NULL"), nullable=True
    )

    # v0.1: Document type classification
    doc_type: Mapped[DocType | None] = mapped_column(Enum(DocType), nullable=True)

    # v0.1: Structured semantic fields (JSON)
    structured_fields = mapped_column(JSONB, nullable=True)

    # Relationships
    file: Mapped["File"] = relationship(back_populates="documents")
    chunks: Mapped[list["Chunk"]] = relationship(back_populates="document", cascade="all, delete")
    sensitivity_findings: Mapped[list["SensitivityFinding"]] = relationship(
        back_populates="document", cascade="all, delete"
    )
    exposure: Mapped["DocumentExposure | None"] = relationship(
        back_populates="document", cascade="all, delete", uselist=False
    )
    previous_version: Mapped["Document | None"] = relationship(
        "Document", remote_side="Document.id", uselist=False
    )


class Chunk(Base):
    __tablename__ = "chunk"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("document.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    section_heading: Mapped[str | None] = mapped_column(Text, nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    # v0.1: Section path for hierarchical structure ["Section 1", "1.2", "Termination"]
    section_path = mapped_column(JSONB, nullable=True)

    # v0.1: LLM-safe views
    redacted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "document_id", "chunk_index", name="uq_chunk_index"),
        Index("ix_chunk_document", "tenant_id", "document_id"),
    )

    # Relationships
    document: Mapped["Document"] = relationship(back_populates="chunks")
    embedding: Mapped["ChunkEmbedding | None"] = relationship(
        back_populates="chunk", cascade="all, delete", uselist=False
    )


class ChunkEmbedding(Base):
    __tablename__ = "chunk_embedding"

    chunk_id: Mapped[UUID] = mapped_column(
        ForeignKey("chunk.id", ondelete="CASCADE"), primary_key=True
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False
    )
    embedding = mapped_column(Vector(1536), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    # Relationships
    chunk: Mapped["Chunk"] = relationship(back_populates="embedding")


# ============================================================================
# Sensitivity & Exposure
# ============================================================================


class SensitivityFinding(Base):
    __tablename__ = "sensitivity_finding"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("document.id", ondelete="CASCADE"), nullable=False
    )
    chunk_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chunk.id", ondelete="CASCADE"), nullable=True
    )
    sensitivity_type: Mapped[SensitivityType] = mapped_column(Enum(SensitivityType), nullable=False)
    sensitivity_level: Mapped[SensitivityLevel] = mapped_column(
        Enum(SensitivityLevel), nullable=False
    )
    snippet: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    __table_args__ = (Index("ix_sensitivity_finding_document", "tenant_id", "document_id"),)

    # Relationships
    document: Mapped["Document"] = relationship(back_populates="sensitivity_findings")


class DocumentExposure(Base):
    __tablename__ = "document_exposure"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("document.id", ondelete="CASCADE"), nullable=False
    )
    exposure_level: Mapped[ExposureLevel] = mapped_column(Enum(ExposureLevel), nullable=False)
    exposure_score: Mapped[int] = mapped_column(
        Integer,
        CheckConstraint("exposure_score >= 0 AND exposure_score <= 100"),
        nullable=False,
    )
    access_summary = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    __table_args__ = (UniqueConstraint("tenant_id", "document_id", name="uq_document_exposure"),)

    # Relationships
    document: Mapped["Document"] = relationship(back_populates="exposure")


# ============================================================================
# Jobs & Events
# ============================================================================


class Job(Base):
    __tablename__ = "job"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False
    )
    job_type: Mapped[JobType] = mapped_column(Enum(JobType), nullable=False)
    file_id: Mapped[UUID | None] = mapped_column(ForeignKey("file.id"), nullable=True)
    document_id: Mapped[UUID | None] = mapped_column(ForeignKey("document.id"), nullable=True)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus), nullable=False, default=JobStatus.PENDING
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (Index("ix_job_pending", "status", "created_at"),)


class FileEvent(Base):
    __tablename__ = "file_event"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False
    )
    file_id: Mapped[UUID | None] = mapped_column(ForeignKey("file.id"), nullable=True)
    share_id: Mapped[UUID | None] = mapped_column(ForeignKey("share.id"), nullable=True)
    event_type: Mapped[FileEventType] = mapped_column(Enum(FileEventType), nullable=False)
    payload = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )


# ============================================================================
# Query Log (optional audit)
# ============================================================================


class QueryLog(Base):
    __tablename__ = "query_log"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False
    )
    principal_id: Mapped[UUID | None] = mapped_column(ForeignKey("principal.id"), nullable=True)
    endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    parameters = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )


# ============================================================================
# v0.1: Agents & Policies
# ============================================================================


class Agent(Base):
    """An AI agent that can access the semantic layer."""

    __tablename__ = "agent"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_key_hash: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_agent_name"),)

    # Relationships
    policies: Mapped[list["AgentPolicy"]] = relationship(
        back_populates="agent", cascade="all, delete"
    )
    interactions: Mapped[list["Interaction"]] = relationship(back_populates="agent")


class Policy(Base):
    """A policy that controls what agents can see and how."""

    __tablename__ = "policy"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    config = mapped_column(JSONB, nullable=False)  # Full policy configuration
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_policy_name"),)

    # Relationships
    agents: Mapped[list["AgentPolicy"]] = relationship(
        back_populates="policy", cascade="all, delete"
    )


class AgentPolicy(Base):
    """Many-to-many relationship between agents and policies."""

    __tablename__ = "agent_policy"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent.id", ondelete="CASCADE"), nullable=False
    )
    policy_id: Mapped[UUID] = mapped_column(
        ForeignKey("policy.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    __table_args__ = (UniqueConstraint("agent_id", "policy_id", name="uq_agent_policy"),)

    # Relationships
    agent: Mapped["Agent"] = relationship(back_populates="policies")
    policy: Mapped["Policy"] = relationship(back_populates="agents")


# ============================================================================
# v0.1: RAG Observability & Interaction Traces
# ============================================================================


class Interaction(Base):
    """A single interaction with the semantic layer (search, answer, etc.)."""

    __tablename__ = "interaction"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agent.id", ondelete="SET NULL"), nullable=True
    )
    user_id: Mapped[str | None] = mapped_column(Text, nullable=True)  # External user ID
    interaction_type: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # search_chunks, answer_with_evidence
    query: Mapped[str] = mapped_column(Text, nullable=False)
    scope = mapped_column(JSONB, nullable=True)  # Filters applied
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_coverage: Mapped[float | None] = mapped_column(nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    __table_args__ = (
        Index("ix_interaction_tenant_created", "tenant_id", "created_at"),
        Index("ix_interaction_agent", "tenant_id", "agent_id"),
    )

    # Relationships
    agent: Mapped["Agent | None"] = relationship(back_populates="interactions")
    chunks: Mapped[list["InteractionChunk"]] = relationship(
        back_populates="interaction", cascade="all, delete"
    )


class InteractionChunk(Base):
    """A chunk retrieved during an interaction (part of the retrieval trace)."""

    __tablename__ = "interaction_chunk"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    interaction_id: Mapped[UUID] = mapped_column(
        ForeignKey("interaction.id", ondelete="CASCADE"), nullable=False
    )
    chunk_id: Mapped[UUID] = mapped_column(
        ForeignKey("chunk.id", ondelete="CASCADE"), nullable=False
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[float | None] = mapped_column(nullable=True)
    view_type: Mapped[str] = mapped_column(
        Text, nullable=False, default="raw"
    )  # raw, redacted, summary
    was_filtered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    filter_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (Index("ix_interaction_chunk_interaction", "interaction_id"),)

    # Relationships
    interaction: Mapped["Interaction"] = relationship(back_populates="chunks")


# ============================================================================
# v0.1: Semantic Diff Results
# ============================================================================


class SemanticDiffResult(Base):
    """Cached result of a semantic diff between two document versions."""

    __tablename__ = "semantic_diff_result"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("document.id", ondelete="CASCADE"), nullable=False
    )
    from_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("document.id", ondelete="CASCADE"), nullable=False
    )
    to_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("document.id", ondelete="CASCADE"), nullable=False
    )
    field_changes = mapped_column(JSONB, nullable=False)  # Changes to structured fields
    section_changes = mapped_column(JSONB, nullable=False)  # Section-level changes
    summary: Mapped[str] = mapped_column(Text, nullable=False)  # Natural language summary
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    __table_args__ = (
        UniqueConstraint("from_version_id", "to_version_id", name="uq_semantic_diff_versions"),
    )
