"""Tests for AWS Health MCP Server."""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from awslabs.aws_health_mcp_server.client import HealthClient
from awslabs.aws_health_mcp_server.formatters import format_timestamp, validate_service_name


class TestFormatters:
    """Test formatting utilities."""

    def test_validate_service_name_valid(self):
        """Test validation of valid service names."""
        is_valid, normalized = validate_service_name("EC2")
        assert is_valid is True
        assert normalized == "EC2"

        is_valid, normalized = validate_service_name("ec2")
        assert is_valid is True
        assert normalized == "EC2"

    def test_validate_service_name_invalid(self):
        """Test validation of invalid service names."""
        is_valid, suggestion = validate_service_name("INVALID_SERVICE")
        assert is_valid is False

    def test_validate_service_name_mapping(self):
        """Test service name mappings."""
        is_valid, normalized = validate_service_name("ELB")
        assert is_valid is True
        assert normalized == "ELASTICLOADBALANCING"

    def test_format_timestamp(self):
        """Test timestamp formatting."""
        dt = datetime(2023, 1, 1, 12, 0, 0)
        formatted = format_timestamp(dt)
        assert "2023-01-01 12:00:00 UTC" == formatted

        formatted = format_timestamp(None)
        assert formatted == "Not specified"


class TestHealthClient:
    """Test AWS Health client."""

    @patch("boto3.client")
    def test_health_client_initialization(self, mock_boto_client):
        """Test health client initialization."""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client

        client = HealthClient()
        assert client.client == mock_client
        mock_boto_client.assert_called_with("health", region_name="us-east-1")


@pytest.mark.asyncio
class TestMCPTools:
    """Test MCP tool functions."""

    @patch("awslabs.aws_health_mcp_server.server.health_client")
    async def test_get_service_health_no_events(self, mock_health_client):
        """Test get_service_health with no events."""
        from awslabs.aws_health_mcp_server.server import get_service_health

        mock_health_client.client.describe_events.return_value = {"events": []}

        result = await get_service_health()
        assert "No active AWS health events found" in result

    @patch("awslabs.aws_health_mcp_server.server.health_client")
    async def test_get_service_events_invalid_service(self, mock_health_client):
        """Test get_service_events with invalid service."""
        from awslabs.aws_health_mcp_server.server import get_service_events

        mock_health_client.check_health_api_access.return_value = (True, None)

        result = await get_service_events("INVALID_SERVICE")
        assert "Invalid service name" in result
