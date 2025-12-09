"""Initial schema

Revision ID: 001
Revises:
Create Date: 2024-12-09

"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create enums
    op.execute("""
        CREATE TYPE principaltype AS ENUM ('USER', 'GROUP', 'SERVICE');
        CREATE TYPE sensitivitytype AS ENUM ('PERSONAL_DATA', 'HEALTH_DATA', 'FINANCIAL_DATA', 'SECRETS', 'OTHER');
        CREATE TYPE sensitivitylevel AS ENUM ('LOW', 'MEDIUM', 'HIGH');
        CREATE TYPE exposurelevel AS ENUM ('LOW', 'MEDIUM', 'HIGH');
        CREATE TYPE jobtype AS ENUM ('EXTRACT_CONTENT', 'ENRICH_CHUNKS');
        CREATE TYPE jobstatus AS ENUM ('PENDING', 'IN_PROGRESS', 'SUCCEEDED', 'FAILED');
        CREATE TYPE fileeventtype AS ENUM ('FILE_DISCOVERED', 'FILE_MODIFIED', 'FILE_DELETED', 'ACL_CHANGED');
    """)

    # tenant
    op.create_table(
        "tenant",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("api_key_hash", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # estate
    op.create_table(
        "estate",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # share
    op.create_table(
        "share",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("estate_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("share_type", sa.Text(), nullable=False),
        sa.Column("root_path", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["estate_id"], ["estate.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # principal
    op.create_table(
        "principal",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column(
            "type",
            sa.Enum("USER", "GROUP", "SERVICE", name="principaltype", create_type=False),
            nullable=False,
        ),
        sa.Column("external_id", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "external_id", name="uq_principal_external_id"),
    )

    # file
    op.create_table(
        "file",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("share_id", sa.UUID(), nullable=False),
        sa.Column("relative_path", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("mtime", sa.DateTime(timezone=True), nullable=False),
        sa.Column("file_type", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("acl_hash", sa.Text(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["share_id"], ["share.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "share_id", "relative_path", name="uq_file_path"),
    )
    op.create_index("ix_file_tenant_share", "file", ["tenant_id", "share_id"])

    # group_membership
    op.create_table(
        "group_membership",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("group_id", sa.UUID(), nullable=False),
        sa.Column("member_principal_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["group_id"], ["principal.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["member_principal_id"], ["principal.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "group_id", "member_principal_id", name="uq_group_membership"
        ),
    )

    # file_acl_entry
    op.create_table(
        "file_acl_entry",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("file_id", sa.UUID(), nullable=False),
        sa.Column("principal_id", sa.UUID(), nullable=False),
        sa.Column("rights", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["file_id"], ["file.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["principal_id"], ["principal.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # file_effective_access
    op.create_table(
        "file_effective_access",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("file_id", sa.UUID(), nullable=False),
        sa.Column("principal_id", sa.UUID(), nullable=False),
        sa.Column("can_read", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["file_id"], ["file.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["principal_id"], ["principal.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "file_id", "principal_id", name="uq_file_effective_access"
        ),
    )
    op.create_index(
        "ix_file_effective_access_file", "file_effective_access", ["tenant_id", "file_id"]
    )

    # document
    op.create_table(
        "document",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("file_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("file_type", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("last_indexed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["file_id"], ["file.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # chunk
    op.create_table(
        "chunk",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("section_heading", sa.Text(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["document.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "document_id", "chunk_index", name="uq_chunk_index"),
    )
    op.create_index("ix_chunk_document", "chunk", ["tenant_id", "document_id"])

    # chunk_embedding
    op.create_table(
        "chunk_embedding",
        sa.Column("chunk_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["chunk_id"], ["chunk.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("chunk_id"),
    )

    # sensitivity_finding
    op.create_table(
        "sensitivity_finding",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("chunk_id", sa.UUID(), nullable=True),
        sa.Column(
            "sensitivity_type",
            sa.Enum(
                "PERSONAL_DATA",
                "HEALTH_DATA",
                "FINANCIAL_DATA",
                "SECRETS",
                "OTHER",
                name="sensitivitytype",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "sensitivity_level",
            sa.Enum("LOW", "MEDIUM", "HIGH", name="sensitivitylevel", create_type=False),
            nullable=False,
        ),
        sa.Column("snippet", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["document.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chunk_id"], ["chunk.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_sensitivity_finding_document", "sensitivity_finding", ["tenant_id", "document_id"]
    )

    # document_exposure
    op.create_table(
        "document_exposure",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column(
            "exposure_level",
            sa.Enum("LOW", "MEDIUM", "HIGH", name="exposurelevel", create_type=False),
            nullable=False,
        ),
        sa.Column("exposure_score", sa.Integer(), nullable=False),
        sa.Column("access_summary", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["document.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "document_id", name="uq_document_exposure"),
        sa.CheckConstraint(
            "exposure_score >= 0 AND exposure_score <= 100", name="ck_exposure_score"
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    # job
    op.create_table(
        "job",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column(
            "job_type",
            sa.Enum("EXTRACT_CONTENT", "ENRICH_CHUNKS", name="jobtype", create_type=False),
            nullable=False,
        ),
        sa.Column("file_id", sa.UUID(), nullable=True),
        sa.Column("document_id", sa.UUID(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING", "IN_PROGRESS", "SUCCEEDED", "FAILED", name="jobstatus", create_type=False
            ),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["file_id"], ["file.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["document.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_job_pending", "job", ["status", "created_at"])

    # file_event
    op.create_table(
        "file_event",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("file_id", sa.UUID(), nullable=True),
        sa.Column("share_id", sa.UUID(), nullable=True),
        sa.Column(
            "event_type",
            sa.Enum(
                "FILE_DISCOVERED",
                "FILE_MODIFIED",
                "FILE_DELETED",
                "ACL_CHANGED",
                name="fileeventtype",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("payload", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["file_id"], ["file.id"]),
        sa.ForeignKeyConstraint(["share_id"], ["share.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # query_log
    op.create_table(
        "query_log",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("principal_id", sa.UUID(), nullable=True),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("parameters", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["principal_id"], ["principal.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("query_log")
    op.drop_table("file_event")
    op.drop_table("job")
    op.drop_table("document_exposure")
    op.drop_table("sensitivity_finding")
    op.drop_table("chunk_embedding")
    op.drop_table("chunk")
    op.drop_table("document")
    op.drop_table("file_effective_access")
    op.drop_table("file_acl_entry")
    op.drop_table("group_membership")
    op.drop_table("file")
    op.drop_table("principal")
    op.drop_table("share")
    op.drop_table("estate")
    op.drop_table("tenant")

    op.execute("DROP TYPE fileeventtype")
    op.execute("DROP TYPE jobstatus")
    op.execute("DROP TYPE jobtype")
    op.execute("DROP TYPE exposurelevel")
    op.execute("DROP TYPE sensitivitylevel")
    op.execute("DROP TYPE sensitivitytype")
    op.execute("DROP TYPE principaltype")
    op.execute("DROP EXTENSION IF EXISTS vector")
