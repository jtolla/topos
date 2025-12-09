"""Semantic diff service.

Computes semantic differences between document versions.
"""

import logging
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Document, SemanticDiffResult

logger = logging.getLogger(__name__)


@dataclass
class FieldChange:
    """A change to a structured field."""

    field_name: str
    old_value: Any
    new_value: Any
    change_type: str  # added, removed, modified


@dataclass
class SectionChange:
    """A change to a document section."""

    section_path: list[str]
    change_type: str  # added, removed, modified
    old_content: str | None = None
    new_content: str | None = None
    summary: str | None = None


@dataclass
class SemanticDiff:
    """Result of semantic diff between two document versions."""

    from_version_id: UUID
    to_version_id: UUID
    field_changes: list[FieldChange] = field(default_factory=list)
    section_changes: list[SectionChange] = field(default_factory=list)
    summary: str = ""


def compare_structured_fields(
    old_fields: dict[str, Any] | None,
    new_fields: dict[str, Any] | None,
) -> list[FieldChange]:
    """Compare structured fields between two document versions."""
    changes = []

    old_fields = old_fields or {}
    new_fields = new_fields or {}

    all_keys = set(old_fields.keys()) | set(new_fields.keys())

    for key in all_keys:
        old_val = old_fields.get(key)
        new_val = new_fields.get(key)

        if old_val is None and new_val is not None:
            changes.append(
                FieldChange(
                    field_name=key,
                    old_value=old_val,
                    new_value=new_val,
                    change_type="added",
                )
            )
        elif old_val is not None and new_val is None:
            changes.append(
                FieldChange(
                    field_name=key,
                    old_value=old_val,
                    new_value=new_val,
                    change_type="removed",
                )
            )
        elif old_val != new_val:
            changes.append(
                FieldChange(
                    field_name=key,
                    old_value=old_val,
                    new_value=new_val,
                    change_type="modified",
                )
            )

    return changes


async def generate_diff_summary_llm(
    old_doc: Document,
    new_doc: Document,
    field_changes: list[FieldChange],
) -> str:
    """Generate a natural language summary of the diff using LLM."""
    if not settings.openai_api_key:
        return generate_diff_summary_simple(field_changes)

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.openai_api_key)

        # Build change description
        changes_desc = []
        for change in field_changes:
            if change.change_type == "added":
                changes_desc.append(f"- Added {change.field_name}: {change.new_value}")
            elif change.change_type == "removed":
                changes_desc.append(f"- Removed {change.field_name} (was: {change.old_value})")
            else:
                changes_desc.append(
                    f"- Changed {change.field_name}: {change.old_value} → {change.new_value}"
                )

        changes_text = (
            "\n".join(changes_desc) if changes_desc else "No structured field changes detected."
        )

        doc_type_str = new_doc.doc_type.value if new_doc.doc_type else "document"
        prompt = (
            f"Summarize the changes between two versions of a {doc_type_str}.\n\n"
            f"Document: {new_doc.title}\n"
            f"Version {old_doc.version_number} → Version {new_doc.version_number}\n\n"
            f"Key changes detected:\n{changes_text}\n\n"
            "Write a concise 2-3 sentence summary of what changed in this document, "
            "suitable for a change report. Focus on the business impact of the changes."
        )

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.3,
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.exception(f"LLM summary generation failed: {e}")
        return generate_diff_summary_simple(field_changes)


def generate_diff_summary_simple(field_changes: list[FieldChange]) -> str:
    """Generate a simple summary without LLM."""
    if not field_changes:
        return "No significant changes detected between versions."

    added = [c for c in field_changes if c.change_type == "added"]
    removed = [c for c in field_changes if c.change_type == "removed"]
    modified = [c for c in field_changes if c.change_type == "modified"]

    parts = []
    if added:
        parts.append(f"{len(added)} field(s) added")
    if removed:
        parts.append(f"{len(removed)} field(s) removed")
    if modified:
        parts.append(f"{len(modified)} field(s) modified")

    return f"Changes: {', '.join(parts)}."


async def compute_semantic_diff(
    session: AsyncSession,  # noqa: ARG001
    from_version: Document,
    to_version: Document,
) -> SemanticDiff:
    """
    Compute semantic diff between two document versions.

    Args:
        session: Database session
        from_version: Earlier document version
        to_version: Later document version

    Returns:
        SemanticDiff with field changes, section changes, and summary
    """
    # Compare structured fields
    field_changes = compare_structured_fields(
        from_version.structured_fields,
        to_version.structured_fields,
    )

    # Generate summary
    summary = await generate_diff_summary_llm(from_version, to_version, field_changes)

    return SemanticDiff(
        from_version_id=from_version.id,
        to_version_id=to_version.id,
        field_changes=field_changes,
        section_changes=[],  # TODO: Implement section-level diff
        summary=summary,
    )


async def get_or_compute_diff(
    session: AsyncSession,
    tenant_id: UUID,
    from_version_id: UUID,
    to_version_id: UUID,
) -> SemanticDiff | None:
    """
    Get cached diff or compute a new one.

    Returns None if versions not found.
    """
    # Check for cached result
    result = await session.execute(
        select(SemanticDiffResult).where(
            SemanticDiffResult.from_version_id == from_version_id,
            SemanticDiffResult.to_version_id == to_version_id,
        )
    )
    cached = result.scalar_one_or_none()

    if cached:
        # Return cached result
        return SemanticDiff(
            from_version_id=from_version_id,
            to_version_id=to_version_id,
            field_changes=[FieldChange(**fc) for fc in cached.field_changes],
            section_changes=[SectionChange(**sc) for sc in cached.section_changes],
            summary=cached.summary,
        )

    # Load document versions
    from_doc = await session.get(Document, from_version_id)
    to_doc = await session.get(Document, to_version_id)

    if not from_doc or not to_doc:
        return None

    # Verify same document lineage
    if from_doc.file_id != to_doc.file_id:
        logger.warning(
            f"Documents {from_version_id} and {to_version_id} are not versions of the same file"
        )

    # Compute diff
    diff = await compute_semantic_diff(session, from_doc, to_doc)

    # Cache the result
    from uuid import uuid4

    cache_entry = SemanticDiffResult(
        id=uuid4(),
        tenant_id=tenant_id,
        document_id=to_doc.id,  # Use the newer version's document
        from_version_id=from_version_id,
        to_version_id=to_version_id,
        field_changes=[
            {
                "field_name": fc.field_name,
                "old_value": fc.old_value,
                "new_value": fc.new_value,
                "change_type": fc.change_type,
            }
            for fc in diff.field_changes
        ],
        section_changes=[],
        summary=diff.summary,
    )
    session.add(cache_entry)
    await session.commit()

    return diff
