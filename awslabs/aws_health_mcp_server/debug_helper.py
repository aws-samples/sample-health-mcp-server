"""Debug utilities for AWS Health MCP Server."""

import json
import logging
from datetime import datetime
from typing import Any, Dict


def setup_logging(level: str = "INFO") -> None:
    """Setup logging configuration."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def log_api_call(service: str, operation: str, params: Dict[str, Any] = None) -> None:
    """Log AWS API calls for debugging."""
    logger = logging.getLogger(__name__)
    logger.debug(f"AWS API Call - Service: {service}, Operation: {operation}")
    if params:
        logger.debug(f"Parameters: {json.dumps(params, default=str, indent=2)}")


def log_event_processing(event: Dict[str, Any]) -> None:
    """Log health event processing for debugging."""
    logger = logging.getLogger(__name__)
    logger.debug(f"Processing health event: {event.get('arn', 'Unknown ARN')}")
    logger.debug(f"Service: {event.get('service', 'Unknown')}")
    logger.debug(f"Status: {event.get('statusCode', 'Unknown')}")


def format_debug_output(data: Any) -> str:
    """Format data for debug output."""
    if isinstance(data, dict):
        return json.dumps(data, default=str, indent=2)
    return str(data)


class DebugTimer:
    """Context manager for timing operations."""

    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.start_time = None
        self.logger = logging.getLogger(__name__)

    def __enter__(self):
        self.start_time = datetime.now()
        self.logger.debug(f"Starting operation: {self.operation_name}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = datetime.now() - self.start_time
            self.logger.debug(
                f"Completed operation: {self.operation_name} in {duration.total_seconds():.2f}s"
            )

        if exc_type:
            self.logger.error(f"Operation {self.operation_name} failed: {exc_val}")


def validate_aws_credentials() -> bool:
    """Validate AWS credentials are available."""
    try:
        import boto3

        session = boto3.Session()
        credentials = session.get_credentials()
        return credentials is not None
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"AWS credentials validation failed: {e}")
        return False
