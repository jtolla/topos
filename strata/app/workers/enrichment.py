import logging
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import (
    Chunk,
    ChunkEmbedding,
    Document,
    DocumentExposure,
    Job,
    JobType,
    SensitivityFinding,
)
from app.services.exposure import compute_exposure
from app.services.sensitivity import detect_sensitivity
from app.workers.base import BaseWorker

logger = logging.getLogger(__name__)


class EnrichmentWorker(BaseWorker):
    """Worker that enriches chunks with embeddings, sensitivity detection, and exposure."""

    job_type = JobType.ENRICH_CHUNKS

    async def process_job(self, session: AsyncSession, job: Job) -> None:
        """
        Process an ENRICH_CHUNKS job:
        1. Load chunks for document
        2. Compute embeddings (optional)
        3. Run sensitivity detection
        4. Compute exposure score
        """
        if not job.document_id:
            raise ValueError("ENRICH_CHUNKS job requires document_id")

        # Load document
        document = await session.get(Document, job.document_id)
        if not document:
            raise ValueError(f"Document {job.document_id} not found")

        # Load chunks
        result = await session.execute(
            select(Chunk).where(Chunk.document_id == document.id).order_by(Chunk.chunk_index)
        )
        chunks = list(result.scalars().all())

        if not chunks:
            logger.warning(f"No chunks found for document {document.id}")
            return

        logger.info(f"Enriching {len(chunks)} chunks for document {document.id}")

        # Optional: Compute embeddings
        if settings.enable_embeddings and settings.openai_api_key:
            await self._compute_embeddings(session, job.tenant_id, chunks)

        # Run sensitivity detection
        await self._detect_sensitivity(session, job.tenant_id, document.id, chunks)

        # Compute exposure
        await self._compute_exposure(session, job.tenant_id, document.id, document.file_id)

        await session.commit()
        logger.info(f"Enrichment complete for document {document.id}")

    async def _compute_embeddings(
        self,
        session: AsyncSession,
        tenant_id,
        chunks: list[Chunk],
    ) -> None:
        """Compute embeddings for chunks using OpenAI."""
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=settings.openai_api_key)

            # Batch chunks for embedding
            texts = [chunk.text for chunk in chunks]

            response = await client.embeddings.create(
                model=settings.embedding_model,
                input=texts,
            )

            for i, chunk in enumerate(chunks):
                embedding_data = response.data[i].embedding

                # Check for existing embedding
                result = await session.execute(
                    select(ChunkEmbedding).where(ChunkEmbedding.chunk_id == chunk.id)
                )
                existing = result.scalar_one_or_none()

                if existing:
                    existing.embedding = embedding_data
                else:
                    chunk_embedding = ChunkEmbedding(
                        chunk_id=chunk.id,
                        tenant_id=tenant_id,
                        embedding=embedding_data,
                    )
                    session.add(chunk_embedding)

            logger.info(f"Computed embeddings for {len(chunks)} chunks")

        except Exception as e:
            logger.exception(f"Failed to compute embeddings: {e}")
            # Don't fail the job, embeddings are optional

    async def _detect_sensitivity(
        self,
        session: AsyncSession,
        tenant_id,
        document_id,
        chunks: list[Chunk],
    ) -> None:
        """Run sensitivity detection on chunks."""
        # Delete existing findings for this document
        await session.execute(
            delete(SensitivityFinding).where(SensitivityFinding.document_id == document_id)
        )

        total_findings = 0

        for chunk in chunks:
            matches = detect_sensitivity(chunk.text, chunk.char_start)

            for match in matches:
                finding = SensitivityFinding(
                    id=uuid4(),
                    tenant_id=tenant_id,
                    document_id=document_id,
                    chunk_id=chunk.id,
                    sensitivity_type=match.sensitivity_type,
                    sensitivity_level=match.sensitivity_level,
                    snippet=match.snippet,
                )
                session.add(finding)
                total_findings += 1

        logger.info(f"Detected {total_findings} sensitivity findings")

    async def _compute_exposure(
        self,
        session: AsyncSession,
        tenant_id,
        document_id,
        file_id,
    ) -> None:
        """Compute and store document exposure."""
        exposure_level, exposure_score, access_summary = await compute_exposure(
            session, tenant_id, document_id, file_id
        )

        # Delete existing exposure
        await session.execute(
            delete(DocumentExposure).where(DocumentExposure.document_id == document_id)
        )

        # Create new exposure record
        exposure = DocumentExposure(
            id=uuid4(),
            tenant_id=tenant_id,
            document_id=document_id,
            exposure_level=exposure_level,
            exposure_score=exposure_score,
            access_summary=access_summary,
        )
        session.add(exposure)

        logger.info(f"Computed exposure: level={exposure_level.value}, score={exposure_score}")
