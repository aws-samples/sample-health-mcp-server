"""Debug utilities for AWS Health MCP Server."""

import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict

from .config import Config


def setup_logging(level: str = None) -> None:
    """Setup production logging configuration."""
    log_level = level or Config.LOG_LEVEL

    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format=Config.LOG_FORMAT,
        handlers=[
            logging.StreamHandler(sys.stderr),
            logging.FileHandler(Config.get_config_dir() / "aws-health-mcp.log", mode="a"),
        ],
    )

    # Set boto3 logging to WARNING to reduce noise
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def log_api_call(service: str, operation: str, params: Dict[str, Any] = None) -> None:
    """Log AWS API calls for debugging."""
    logger = logging.getLogger(__name__)
    logger.debug(f"AWS API Call - Service: {service}, Operation: {operation}")
    if params:
        # Sanitize sensitive data
        sanitized_params = _sanitize_params(params)
        logger.debug(f"Parameters: {json.dumps(sanitized_params, default=str, indent=2)}")


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


def _sanitize_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """Remove sensitive information from parameters."""
    sensitive_keys = {"password", "token", "key", "secret", "credential"}
    sanitized = {}

    for key, value in params.items():
        if any(sensitive in key.lower() for sensitive in sensitive_keys):
            sanitized[key] = "***REDACTED***"
        elif isinstance(value, dict):
            sanitized[key] = _sanitize_params(value)
        else:
            sanitized[key] = value

    return sanitized


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
        from botocore.exceptions import NoCredentialsError, PartialCredentialsError

        session = boto3.Session(profile_name=Config.AWS_PROFILE)
        credentials = session.get_credentials()

        if credentials is None:
            return False

        # Test credentials by making a simple call
        sts = session.client("sts")
        sts.get_caller_identity()

        return True

    except (NoCredentialsError, PartialCredentialsError) as e:
        logger = logging.getLogger(__name__)
        logger.error(f"AWS credentials validation failed: {e}")
        return False
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Unexpected error during credentials validation: {e}")
        return False


class HealthCheckError(Exception):
    """Custom exception for health check failures."""

    pass


def health_check() -> Dict[str, Any]:
    """Perform comprehensive health check."""
    logger = logging.getLogger(__name__)
    health_status = {"status": "healthy", "timestamp": datetime.utcnow().isoformat(), "checks": {}}

    try:
        # Check AWS credentials
        if validate_aws_credentials():
            health_status["checks"]["aws_credentials"] = "ok"
        else:
            health_status["checks"]["aws_credentials"] = "failed"
            health_status["status"] = "unhealthy"

        # Check Health API access
        import boto3
        from .client import health_client

        has_access, error_msg = health_client.check_health_api_access()
        if has_access:
            health_status["checks"]["health_api"] = "ok"
        else:
            health_status["checks"]["health_api"] = f"failed: {error_msg}"
            health_status["status"] = "degraded"

        # Check configuration
        if Config.validate():
            health_status["checks"]["configuration"] = "ok"
        else:
            health_status["checks"]["configuration"] = "failed"
            health_status["status"] = "unhealthy"

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        health_status["status"] = "unhealthy"
        health_status["error"] = str(e)

    return health_status
