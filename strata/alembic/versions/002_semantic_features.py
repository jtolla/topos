"""Add v0.1 semantic features: versioning, doc types, extraction, policies, traces

Revision ID: 002
Revises: 001
Create Date: 2024-12-09

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create new enums
    op.execute("""
        CREATE TYPE doctype AS ENUM ('CONTRACT', 'POLICY', 'RFC', 'OTHER');
    """)

    # Add version tracking to document
    op.add_column(
        "document", sa.Column("version_number", sa.Integer(), nullable=True, server_default="1")
    )
    op.add_column("document", sa.Column("previous_version_id", sa.UUID(), nullable=True))
    op.add_column(
        "document",
        sa.Column(
            "doc_type",
            sa.Enum("CONTRACT", "POLICY", "RFC", "OTHER", name="doctype", create_type=False),
            nullable=True,
        ),
    )
    op.add_column("document", sa.Column("structured_fields", JSONB(), nullable=True))

    op.create_foreign_key(
        "fk_document_previous_version",
        "document",
        "document",
        ["previous_version_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Add section_path to chunk for hierarchical structure
    op.add_column("chunk", sa.Column("section_path", JSONB(), nullable=True))
    op.add_column("chunk", sa.Column("redacted_text", sa.Text(), nullable=True))
    op.add_column("chunk", sa.Column("summary_text", sa.Text(), nullable=True))

    # Create agent table for policy enforcement
    op.create_table(
        "agent",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("api_key_hash", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_agent_name"),
    )

    # Create policy table
    op.create_table(
        "policy",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("config", JSONB(), nullable=False),  # Full policy config
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_policy_name"),
    )

    # Create agent_policy join table
    op.create_table(
        "agent_policy",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("policy_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id"], ["agent.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["policy_id"], ["policy.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id", "policy_id", name="uq_agent_policy"),
    )

    # Create interaction table for RAG observability
    op.create_table(
        "interaction",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=True),
        sa.Column("user_id", sa.Text(), nullable=True),  # External user identifier
        sa.Column(
            "interaction_type", sa.Text(), nullable=False
        ),  # search_chunks, answer_with_evidence, etc.
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("scope", JSONB(), nullable=True),  # Filters applied
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("evidence_coverage", sa.Float(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id"], ["agent.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_interaction_tenant_created", "interaction", ["tenant_id", "created_at"])
    op.create_index("ix_interaction_agent", "interaction", ["tenant_id", "agent_id"])

    # Create interaction_chunk for retrieval trace
    op.create_table(
        "interaction_chunk",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("interaction_id", sa.UUID(), nullable=False),
        sa.Column("chunk_id", sa.UUID(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column(
            "view_type", sa.Text(), nullable=False, server_default="raw"
        ),  # raw, redacted, summary
        sa.Column("was_filtered", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("filter_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["interaction_id"], ["interaction.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chunk_id"], ["chunk.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_interaction_chunk_interaction", "interaction_chunk", ["interaction_id"])

    # Create semantic_diff_result for caching diff results
    op.create_table(
        "semantic_diff_result",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("from_version_id", sa.UUID(), nullable=False),
        sa.Column("to_version_id", sa.UUID(), nullable=False),
        sa.Column("field_changes", JSONB(), nullable=False),  # Structured field diffs
        sa.Column("section_changes", JSONB(), nullable=False),  # Section-level changes
        sa.Column("summary", sa.Text(), nullable=False),  # Natural language summary
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["document.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["from_version_id"], ["document.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["to_version_id"], ["document.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("from_version_id", "to_version_id", name="uq_semantic_diff_versions"),
    )

    # Add new job types
    op.execute("""
        ALTER TYPE jobtype ADD VALUE 'CLASSIFY_DOCUMENT';
        ALTER TYPE jobtype ADD VALUE 'EXTRACT_SEMANTICS';
        ALTER TYPE jobtype ADD VALUE 'COMPUTE_DIFF';
    """)


def downgrade() -> None:
    op.drop_table("semantic_diff_result")
    op.drop_table("interaction_chunk")
    op.drop_table("interaction")
    op.drop_table("agent_policy")
    op.drop_table("policy")
    op.drop_table("agent")

    op.drop_constraint("fk_document_previous_version", "document", type_="foreignkey")
    op.drop_column("document", "structured_fields")
    op.drop_column("document", "doc_type")
    op.drop_column("document", "previous_version_id")
    op.drop_column("document", "version_number")

    op.drop_column("chunk", "summary_text")
    op.drop_column("chunk", "redacted_text")
    op.drop_column("chunk", "section_path")

    op.execute("DROP TYPE doctype")

    # Note: Cannot remove values from enums in PostgreSQL easily
    # Would need to recreate the type
