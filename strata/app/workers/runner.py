import asyncio
import logging
import signal

from app.workers.enrichment import EnrichmentWorker
from app.workers.extraction import ExtractionWorker
from app.workers.semantics import SemanticExtractionWorker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def run_workers():
    """Run all workers concurrently."""
    extraction_worker = ExtractionWorker()
    enrichment_worker = EnrichmentWorker()
    semantics_worker = SemanticExtractionWorker()

    # Handle shutdown signals
    def handle_shutdown(sig, frame):  # noqa: ARG001
        logger.info(f"Received shutdown signal: {sig}")
        extraction_worker.stop()
        enrichment_worker.stop()
        semantics_worker.stop()

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    # Run workers concurrently
    await asyncio.gather(
        extraction_worker.run(),
        enrichment_worker.run(),
        semantics_worker.run(),
    )


def main():
    """Entry point for the worker process."""
    logger.info("Starting Strata workers")
    asyncio.run(run_workers())


if __name__ == "__main__":
    main()
