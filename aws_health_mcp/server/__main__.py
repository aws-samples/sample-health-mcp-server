"""Main entry point for AWS Health MCP Server."""

import logging
import signal
import sys
from typing import NoReturn

from .config import Config
from .debug_helper import setup_logging, validate_aws_credentials, health_check
from .server import run_server


def signal_handler(signum: int, frame) -> NoReturn:
    """Handle shutdown signals gracefully."""
    logger = logging.getLogger(__name__)
    logger.info(f"Received signal {signum}, shutting down gracefully...")
    sys.exit(0)


def main() -> None:
    """Main entry point."""
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Setup logging first
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info(f"Starting AWS Health MCP Server v{Config.SERVER_VERSION}")
    
    # Validate configuration
    if not Config.validate():
        logger.error("Configuration validation failed")
        sys.exit(1)
    
    # Perform health check
    health_status = health_check()
    if health_status["status"] == "unhealthy":
        logger.error("Health check failed:")
        for check, status in health_status["checks"].items():
            if "failed" in str(status):
                logger.error(f"  - {check}: {status}")
        
        if "aws_credentials" in health_status["checks"] and "failed" in health_status["checks"]["aws_credentials"]:
            print("Error: AWS credentials not found or invalid.", file=sys.stderr)
            print("Please configure your AWS credentials using:", file=sys.stderr)
            print("  - AWS CLI: aws configure", file=sys.stderr)
            print("  - Environment variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY", file=sys.stderr)
            print("  - IAM roles (for EC2 instances)", file=sys.stderr)
        
        sys.exit(1)
    
    elif health_status["status"] == "degraded":
        logger.warning("Health check shows degraded status:")
        for check, status in health_status["checks"].items():
            if "failed" in str(status):
                logger.warning(f"  - {check}: {status}")
        logger.warning("Continuing with limited functionality...")
    
    logger.info("Health check passed, starting server...")
    
    try:
        # Run the server
        run_server()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
