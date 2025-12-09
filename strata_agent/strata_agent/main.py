import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path

from strata_agent.client import StrataClient
from strata_agent.config import AgentSettings
from strata_agent.scanner import scan_share

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class Agent:
    """Strata SMB Connector Agent."""

    def __init__(self, settings: AgentSettings):
        self.settings = settings
        self.client = StrataClient(settings)
        self.running = False

    async def scan_and_send(self) -> None:
        """Perform a full scan of all configured shares and send events."""
        logger.info("Starting scan cycle")

        for share_config in self.settings.shares:
            try:
                # Scan the share
                files = scan_share(share_config)

                if not files:
                    logger.info(f"No files found in share {share_config.name}")
                    continue

                # Send events to API
                processed, jobs = await self.client.send_events_batched(files)
                logger.info(
                    f"Share {share_config.name}: "
                    f"sent {len(files)} files, "
                    f"processed={processed}, "
                    f"jobs_created={jobs}"
                )
            except Exception as e:
                logger.exception(f"Error scanning share {share_config.name}: {e}")

        logger.info("Scan cycle complete")

    async def run(self) -> None:
        """Run the agent continuously."""
        self.running = True
        logger.info(
            f"Starting Strata agent {self.settings.agent_id} "
            f"(scan interval: {self.settings.scan_interval_seconds}s)"
        )

        while self.running:
            try:
                await self.scan_and_send()
            except Exception as e:
                logger.exception(f"Error in scan cycle: {e}")

            if self.running:
                logger.info(f"Sleeping for {self.settings.scan_interval_seconds} seconds")
                await asyncio.sleep(self.settings.scan_interval_seconds)

    def stop(self) -> None:
        """Stop the agent."""
        self.running = False
        logger.info("Agent stopping")


async def run_once(settings: AgentSettings) -> None:
    """Run a single scan cycle."""
    agent = Agent(settings)
    await agent.scan_and_send()


async def run_continuous(settings: AgentSettings) -> None:
    """Run the agent continuously."""
    agent = Agent(settings)

    # Handle shutdown signals
    def handle_shutdown(sig, frame):  # noqa: ARG001
        logger.info(f"Received signal {sig}")
        agent.stop()

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    await agent.run()


def main() -> None:
    """Main entry point for the agent."""
    parser = argparse.ArgumentParser(description="Strata SMB Connector Agent")
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default="config.yaml",
        help="Path to configuration file",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single scan cycle and exit",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Load configuration
    config_path = Path(args.config)
    if config_path.exists():
        logger.info(f"Loading configuration from {config_path}")
        settings = AgentSettings.from_yaml(str(config_path))
    else:
        logger.warning(f"Config file not found: {config_path}, using defaults")
        settings = AgentSettings()

    # Validate configuration
    if not settings.tenant_api_key:
        logger.error("No API key configured. Set STRATA_API_KEY or add to config file.")
        sys.exit(1)

    if not settings.shares:
        logger.error("No shares configured. Add shares to config file.")
        sys.exit(1)

    # Run agent
    if args.once:
        asyncio.run(run_once(settings))
    else:
        asyncio.run(run_continuous(settings))


if __name__ == "__main__":
    main()
