"""Basic tests for AWS Health MCP Server."""

import pytest
from aws_health_mcp.server.config import Config


def test_config_validation():
    """Test configuration validation."""
    assert Config.validate() is True


def test_config_defaults():
    """Test default configuration values."""
    assert Config.AWS_REGION == "us-east-1"
    assert Config.LOG_LEVEL == "INFO"
    assert Config.HEALTH_API_TIMEOUT == 30


def test_server_version():
    """Test server version is set."""
    from aws_health_mcp.server import __version__
    assert __version__ == "1.0.0"
