import os

import yaml
from pydantic import BaseModel
from pydantic_settings import BaseSettings


class ShareConfig(BaseModel):
    """Configuration for a single SMB share."""

    name: str
    smb_uri: str  # e.g., \\\\server\\share
    mount_point: str  # Local mount path, e.g., /mnt/hrshare
    include_paths: list[str] = ["/"]
    exclude_patterns: list[str] = ["*.tmp", "~*", ".DS_Store", "Thumbs.db"]
    max_file_size_bytes: int = 104857600  # 100MB


class AgentSettings(BaseSettings):
    """Agent configuration settings."""

    agent_id: str = "strata-agent-1"
    tenant_api_key: str = ""
    api_base_url: str = "http://localhost:8000"
    scan_interval_seconds: int = 600
    batch_size: int = 100

    # Shares are loaded from config file
    shares: list[ShareConfig] = []

    class Config:
        env_prefix = "STRATA_"
        env_file = ".env"

    @classmethod
    def from_yaml(cls, path: str) -> "AgentSettings":
        """Load settings from a YAML config file."""
        with open(path) as f:
            data = yaml.safe_load(f)

        # Convert shares to ShareConfig objects
        shares = [ShareConfig(**s) for s in data.get("shares", [])]

        return cls(
            agent_id=data.get("agent_id", cls.model_fields["agent_id"].default),
            tenant_api_key=os.environ.get("STRATA_API_KEY", data.get("tenant_api_key", "")),
            api_base_url=os.environ.get(
                "STRATA_API_BASE_URL",
                data.get("api_base_url", cls.model_fields["api_base_url"].default),
            ),
            scan_interval_seconds=data.get(
                "scan_interval_seconds", cls.model_fields["scan_interval_seconds"].default
            ),
            batch_size=data.get("batch_size", cls.model_fields["batch_size"].default),
            shares=shares,
        )
