import logging

import httpx

from strata_agent.config import AgentSettings
from strata_agent.scanner import FileInfo

logger = logging.getLogger(__name__)


class StrataClient:
    """HTTP client for the Strata API."""

    def __init__(self, settings: AgentSettings):
        self.settings = settings
        self.base_url = settings.api_base_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {settings.tenant_api_key}",
            "Content-Type": "application/json",
        }

    async def send_events(self, files: list[FileInfo], event_type: str = "FILE_DISCOVERED") -> dict:
        """
        Send file events to the Strata API.

        Args:
            files: List of FileInfo objects to send
            event_type: Type of event (FILE_DISCOVERED, FILE_MODIFIED, FILE_DELETED)

        Returns:
            Response from the API
        """
        events = []
        for file in files:
            event = {
                "type": event_type,
                "share_name": file.share_name,
                "relative_path": file.relative_path,
                "size_bytes": file.size_bytes,
                "mtime": file.mtime.isoformat(),
                "file_type": file.file_type,
                "content_hash": file.content_hash,
                "acl_hash": file.acl_hash,
                "acl_entries": [
                    {
                        "principal_external_id": entry.principal_external_id,
                        "principal_display_name": entry.principal_display_name,
                        "principal_type": entry.principal_type,
                        "rights": entry.rights,
                        "source": entry.source,
                    }
                    for entry in file.acl_entries
                ],
            }
            events.append(event)

        payload = {
            "agent_id": self.settings.agent_id,
            "events": events,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/v0/ingest/events",
                headers=self.headers,
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    async def send_events_batched(
        self,
        files: list[FileInfo],
        event_type: str = "FILE_DISCOVERED",
    ) -> tuple[int, int]:
        """
        Send file events in batches.

        Returns:
            Tuple of (total_processed, total_jobs_created)
        """
        total_processed = 0
        total_jobs = 0
        batch_size = self.settings.batch_size

        for i in range(0, len(files), batch_size):
            batch = files[i : i + batch_size]
            try:
                result = await self.send_events(batch, event_type)
                total_processed += result.get("processed", 0)
                total_jobs += result.get("jobs_created", 0)
                logger.info(
                    f"Sent batch {i // batch_size + 1}: "
                    f"processed={result.get('processed', 0)}, "
                    f"jobs={result.get('jobs_created', 0)}"
                )
            except httpx.HTTPStatusError as e:
                logger.error(f"Failed to send batch: {e.response.status_code} - {e.response.text}")
                raise
            except Exception as e:
                logger.exception(f"Error sending batch: {e}")
                raise

        return total_processed, total_jobs
