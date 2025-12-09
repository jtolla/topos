import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import async_session_factory
from app.models import Job, JobStatus, JobType

logger = logging.getLogger(__name__)


class BaseWorker(ABC):
    """Base class for job workers."""

    job_type: JobType

    def __init__(self):
        self.running = False

    @abstractmethod
    async def process_job(self, session: AsyncSession, job: Job) -> None:
        """Process a single job. Implement in subclass."""

    async def claim_job(self, session: AsyncSession) -> Job | None:
        """
        Claim a pending job using SELECT FOR UPDATE SKIP LOCKED.
        Returns the claimed job or None if no jobs available.
        """
        # Use raw SQL for the atomic claim pattern
        result = await session.execute(
            text("""
                UPDATE job
                SET status = 'IN_PROGRESS',
                    attempts = attempts + 1,
                    updated_at = now()
                WHERE id = (
                    SELECT id
                    FROM job
                    WHERE status = 'PENDING'
                      AND job_type = :job_type
                      AND attempts < :max_attempts
                    ORDER BY created_at
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                RETURNING id, tenant_id, job_type, file_id, document_id,
                          status, attempts, last_error, created_at, updated_at
            """),
            {
                "job_type": self.job_type.value,
                "max_attempts": settings.worker_max_attempts,
            },
        )
        row = result.fetchone()

        if row:
            await session.commit()
            # Fetch the actual Job object
            job = await session.get(Job, row.id)
            return job

        return None

    async def mark_succeeded(self, session: AsyncSession, job: Job) -> None:
        """Mark a job as succeeded."""
        job.status = JobStatus.SUCCEEDED
        job.updated_at = datetime.utcnow()
        await session.commit()
        logger.info(f"Job {job.id} succeeded")

    async def mark_failed(self, session: AsyncSession, job: Job, error: str) -> None:
        """Mark a job as failed."""
        job.status = JobStatus.FAILED
        job.last_error = error
        job.updated_at = datetime.utcnow()
        await session.commit()
        logger.error(f"Job {job.id} failed: {error}")

    async def run_once(self) -> bool:
        """
        Try to claim and process a single job.
        Returns True if a job was processed, False otherwise.
        """
        async with async_session_factory() as session:
            job = await self.claim_job(session)

            if not job:
                return False

            logger.info(f"Processing job {job.id} (type={job.job_type}, attempt={job.attempts})")

            try:
                await self.process_job(session, job)
                await self.mark_succeeded(session, job)
                return True
            except Exception as e:
                logger.exception(f"Error processing job {job.id}: {e}")
                await self.mark_failed(session, job, str(e))
                return True  # We did process (attempt) a job

    async def run(self) -> None:
        """Run the worker loop continuously."""
        self.running = True
        logger.info(f"Starting {self.__class__.__name__} worker")

        while self.running:
            try:
                processed = await self.run_once()

                if not processed:
                    # No jobs available, sleep before checking again
                    await asyncio.sleep(settings.worker_poll_interval_seconds)
            except Exception as e:
                logger.exception(f"Worker error: {e}")
                await asyncio.sleep(settings.worker_poll_interval_seconds)

    def stop(self) -> None:
        """Stop the worker loop."""
        self.running = False
        logger.info(f"Stopping {self.__class__.__name__} worker")
