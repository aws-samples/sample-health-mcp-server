"""Main entry point for AWS Health MCP Server."""

import logging
import sys

from .config import Config
from .server import run_server


def main() -> None:
    """Main entry point."""
    # Minimal logging to stderr (stdout is reserved for MCP JSON-RPC)
    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL.upper()),
        format=Config.LOG_FORMAT,
        handlers=[logging.StreamHandler(sys.stderr)],
    )
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    logger = logging.getLogger(__name__)
    logger.info(f"Starting AWS Health MCP Server v{Config.SERVER_VERSION}")

    run_server()


if __name__ == "__main__":
    main()
