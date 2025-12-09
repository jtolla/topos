"""Worker for semantic extraction from documents."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Document, Job, JobType
from app.services.semantic_extraction import extract_structured_fields
from app.workers.base import BaseWorker

logger = logging.getLogger(__name__)


class SemanticExtractionWorker(BaseWorker):
    """Worker that extracts structured semantic fields from documents."""

    job_type = JobType.EXTRACT_SEMANTICS

    async def process_job(self, session: AsyncSession, job: Job) -> None:
        """
        Process an EXTRACT_SEMANTICS job:
        1. Load document
        2. Extract structured fields based on doc_type
        3. Store results on document
        """
        if not job.document_id:
            raise ValueError("EXTRACT_SEMANTICS job requires document_id")

        # Load document
        document = await session.get(Document, job.document_id)
        if not document:
            raise ValueError(f"Document {job.document_id} not found")

        if not document.doc_type:
            logger.warning(f"Document {document.id} has no doc_type, skipping semantic extraction")
            return

        # Get document text from chunks
        from sqlalchemy import select

        from app.models import Chunk

        result = await session.execute(
            select(Chunk).where(Chunk.document_id == document.id).order_by(Chunk.chunk_index)
        )
        chunks = list(result.scalars().all())

        if not chunks:
            logger.warning(f"No chunks found for document {document.id}")
            return

        # Reconstruct full text from chunks (de-duplicate overlapping content)
        full_text = " ".join(chunk.text for chunk in chunks)

        logger.info(
            f"Extracting structured fields for {document.doc_type.value} document {document.id}"
        )

        # Extract structured fields
        structured_fields = await extract_structured_fields(
            full_text,
            document.doc_type,
            document.title,
        )

        if structured_fields:
            document.structured_fields = structured_fields
            await session.commit()
            logger.info(f"Extracted {len(structured_fields)} fields for document {document.id}")
        else:
            logger.info(f"No structured fields extracted for document {document.id}")
