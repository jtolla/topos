"""RAG observability service.

Tracks interactions with the semantic layer for audit, debugging, and analytics.
"""

import logging
import time
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Interaction, InteractionChunk

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    """A chunk retrieved during an interaction."""

    chunk_id: UUID
    rank: int
    score: float | None = None
    view_type: str = "raw"
    was_filtered: bool = False
    filter_reason: str | None = None


@dataclass
class InteractionTrace:
    """Complete trace of an interaction for observability."""

    interaction_id: UUID
    interaction_type: str
    query: str
    scope: dict[str, Any] | None
    chunks_retrieved: list[RetrievedChunk]
    answer: str | None = None
    evidence_coverage: float | None = None
    latency_ms: int | None = None
    agent_id: UUID | None = None
    user_id: str | None = None


class InteractionTracker:
    """
    Context manager for tracking interactions.

    Usage:
        async with InteractionTracker(session, tenant_id, "search_chunks", query) as tracker:
            # Perform the operation
            results = await do_search(query)

            # Record retrieved chunks
            for i, result in enumerate(results):
                tracker.add_chunk(result.chunk_id, rank=i, score=result.score)

            # Optionally record answer
            tracker.set_answer(answer)
    """

    def __init__(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        interaction_type: str,
        query: str,
        scope: dict[str, Any] | None = None,
        agent_id: UUID | None = None,
        user_id: str | None = None,
    ):
        self.session = session
        self.tenant_id = tenant_id
        self.interaction_type = interaction_type
        self.query = query
        self.scope = scope
        self.agent_id = agent_id
        self.user_id = user_id

        self.interaction_id = uuid4()
        self.chunks: list[RetrievedChunk] = []
        self.answer: str | None = None
        self.evidence_coverage: float | None = None
        self._start_time: float | None = None

    def add_chunk(
        self,
        chunk_id: UUID,
        rank: int,
        score: float | None = None,
        view_type: str = "raw",
        was_filtered: bool = False,
        filter_reason: str | None = None,
    ) -> None:
        """Record a chunk retrieved during this interaction."""
        self.chunks.append(
            RetrievedChunk(
                chunk_id=chunk_id,
                rank=rank,
                score=score,
                view_type=view_type,
                was_filtered=was_filtered,
                filter_reason=filter_reason,
            )
        )

    def set_answer(
        self,
        answer: str,
        evidence_coverage: float | None = None,
    ) -> None:
        """Record the answer generated for this interaction."""
        self.answer = answer
        self.evidence_coverage = evidence_coverage

    async def __aenter__(self) -> "InteractionTracker":
        self._start_time = time.perf_counter()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        # Calculate latency
        latency_ms = None
        if self._start_time:
            latency_ms = int((time.perf_counter() - self._start_time) * 1000)

        # Create interaction record
        interaction = Interaction(
            id=self.interaction_id,
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            user_id=self.user_id,
            interaction_type=self.interaction_type,
            query=self.query,
            scope=self.scope,
            answer=self.answer,
            evidence_coverage=self.evidence_coverage,
            latency_ms=latency_ms,
        )
        self.session.add(interaction)

        # Create chunk records
        for chunk in self.chunks:
            interaction_chunk = InteractionChunk(
                id=uuid4(),
                interaction_id=self.interaction_id,
                chunk_id=chunk.chunk_id,
                rank=chunk.rank,
                score=chunk.score,
                view_type=chunk.view_type,
                was_filtered=chunk.was_filtered,
                filter_reason=chunk.filter_reason,
            )
            self.session.add(interaction_chunk)

        await self.session.commit()

        logger.info(
            f"Recorded interaction {self.interaction_id}: "
            f"type={self.interaction_type}, chunks={len(self.chunks)}, "
            f"latency={latency_ms}ms"
        )


async def get_interaction_trace(
    session: AsyncSession,
    tenant_id: UUID,
    interaction_id: UUID,
) -> InteractionTrace | None:
    """Get a complete interaction trace by ID."""
    result = await session.execute(
        select(Interaction).where(
            Interaction.id == interaction_id,
            Interaction.tenant_id == tenant_id,
        )
    )
    interaction = result.scalar_one_or_none()

    if not interaction:
        return None

    # Load chunk records
    result = await session.execute(
        select(InteractionChunk)
        .where(InteractionChunk.interaction_id == interaction_id)
        .order_by(InteractionChunk.rank)
    )
    chunk_records = result.scalars().all()

    chunks_retrieved = [
        RetrievedChunk(
            chunk_id=c.chunk_id,
            rank=c.rank,
            score=c.score,
            view_type=c.view_type,
            was_filtered=c.was_filtered,
            filter_reason=c.filter_reason,
        )
        for c in chunk_records
    ]

    return InteractionTrace(
        interaction_id=interaction.id,
        interaction_type=interaction.interaction_type,
        query=interaction.query,
        scope=interaction.scope,
        chunks_retrieved=chunks_retrieved,
        answer=interaction.answer,
        evidence_coverage=interaction.evidence_coverage,
        latency_ms=interaction.latency_ms,
        agent_id=interaction.agent_id,
        user_id=interaction.user_id,
    )


async def list_interactions(
    session: AsyncSession,
    tenant_id: UUID,
    agent_id: UUID | None = None,
    interaction_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Interaction]:
    """List interactions with optional filtering."""
    query = select(Interaction).where(Interaction.tenant_id == tenant_id)

    if agent_id:
        query = query.where(Interaction.agent_id == agent_id)
    if interaction_type:
        query = query.where(Interaction.interaction_type == interaction_type)

    query = query.order_by(Interaction.created_at.desc())
    query = query.offset(offset).limit(limit)

    result = await session.execute(query)
    return list(result.scalars().all())


async def get_agent_interaction_stats(
    session: AsyncSession,
    tenant_id: UUID,
    agent_id: UUID,
) -> dict[str, Any]:
    """Get interaction statistics for an agent."""
    from sqlalchemy import func

    # Total interactions
    result = await session.execute(
        select(func.count(Interaction.id)).where(
            Interaction.tenant_id == tenant_id,
            Interaction.agent_id == agent_id,
        )
    )
    total_interactions = result.scalar() or 0

    # Interactions by type
    result = await session.execute(
        select(
            Interaction.interaction_type,
            func.count(Interaction.id),
        )
        .where(
            Interaction.tenant_id == tenant_id,
            Interaction.agent_id == agent_id,
        )
        .group_by(Interaction.interaction_type)
    )
    by_type = {row[0]: row[1] for row in result.fetchall()}

    # Average latency
    result = await session.execute(
        select(func.avg(Interaction.latency_ms)).where(
            Interaction.tenant_id == tenant_id,
            Interaction.agent_id == agent_id,
            Interaction.latency_ms.isnot(None),
        )
    )
    avg_latency = result.scalar()

    # Total chunks retrieved
    result = await session.execute(
        select(func.count(InteractionChunk.id))
        .join(Interaction, Interaction.id == InteractionChunk.interaction_id)
        .where(
            Interaction.tenant_id == tenant_id,
            Interaction.agent_id == agent_id,
        )
    )
    total_chunks = result.scalar() or 0

    # Filtered chunks
    result = await session.execute(
        select(func.count(InteractionChunk.id))
        .join(Interaction, Interaction.id == InteractionChunk.interaction_id)
        .where(
            Interaction.tenant_id == tenant_id,
            Interaction.agent_id == agent_id,
            InteractionChunk.was_filtered == True,  # noqa: E712
        )
    )
    filtered_chunks = result.scalar() or 0

    return {
        "total_interactions": total_interactions,
        "interactions_by_type": by_type,
        "avg_latency_ms": round(avg_latency, 2) if avg_latency else None,
        "total_chunks_retrieved": total_chunks,
        "filtered_chunks": filtered_chunks,
    }
