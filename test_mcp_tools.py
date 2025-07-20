#!/usr/bin/env python3
"""Test script for MCP tools functionality."""

import asyncio
from unittest.mock import Mock, patch

from awslabs.aws_health_mcp_server.server import (
    get_affected_entities,
    get_completed_events,
    get_scheduled_changes,
    get_service_events,
    get_service_health,
)


async def test_tools_with_mock_data():
    """Test MCP tools with mocked AWS responses."""
    print("🧪 Testing MCP Tools with Mock Data")
    print("=" * 50)

    # Mock health client
    mock_client = Mock()

    # Test 1: get_service_health with no events
    print("\n1. Testing get_service_health() with no events:")
    mock_client.describe_events.return_value = {"events": []}

    with patch("awslabs.aws_health_mcp_server.server.health_client.client", mock_client):
        result = await get_service_health()
        print(f"   Result: {result[:100]}...")
        assert "No active AWS health events found" in result
        print("   ✅ PASSED")

    # Test 2: get_service_health with mock events
    print("\n2. Testing get_service_health() with mock events:")
    mock_events = [
        {
            "arn": "arn:aws:health:us-east-1::event/EC2/AWS_EC2_INSTANCE_REBOOT_MAINTENANCE_SCHEDULED/123",
            "service": "EC2",
            "eventTypeCode": "AWS_EC2_INSTANCE_REBOOT_MAINTENANCE_SCHEDULED",
            "statusCode": "open",
            "region": "us-east-1",
            "startTime": None,
            "endTime": None,
        }
    ]

    mock_client.describe_events.return_value = {"events": mock_events}
    mock_client.describe_event_details.return_value = {
        "successfulSet": [
            {"eventDescription": {"latestDescription": "Mock maintenance event for testing"}}
        ]
    }

    with patch("awslabs.aws_health_mcp_server.server.health_client.client", mock_client):
        result = await get_service_health()
        print(f"   Result contains EC2: {'EC2' in result}")
        print(f"   Result contains maintenance: {'maintenance' in result.lower()}")
        assert "EC2" in result
        print("   ✅ PASSED")

    # Test 3: get_service_events with valid service
    print("\n3. Testing get_service_events('EC2'):")

    with patch("awslabs.aws_health_mcp_server.server.health_client") as mock_health_client:
        mock_health_client.check_health_api_access.return_value = (True, None)
        mock_health_client.client.describe_events.return_value = {"events": mock_events}
        mock_health_client.client.describe_event_details.return_value = {
            "successfulSet": [
                {"eventDescription": {"latestDescription": "Mock EC2 event for testing"}}
            ]
        }

        result = await get_service_events("EC2")
        print(f"   Result contains EC2: {'EC2' in result}")
        assert "EC2" in result
        print("   ✅ PASSED")

    # Test 4: get_service_events with invalid service
    print("\n4. Testing get_service_events('INVALID_SERVICE'):")

    with patch("awslabs.aws_health_mcp_server.server.health_client") as mock_health_client:
        mock_health_client.check_health_api_access.return_value = (True, None)

        result = await get_service_events("INVALID_SERVICE")
        print(f"   Result contains 'Invalid service': {'Invalid service' in result}")
        assert "Invalid service" in result
        print("   ✅ PASSED")

    # Test 5: get_affected_entities
    print("\n5. Testing get_affected_entities():")

    mock_entities = [
        {"entityValue": "i-1234567890abcdef0", "statusCode": "IMPAIRED", "lastUpdatedTime": None}
    ]

    with patch("awslabs.aws_health_mcp_server.server.health_client.client", mock_client):
        mock_client.describe_events.return_value = {"events": mock_events}
        mock_client.describe_affected_entities.return_value = {"entities": mock_entities}

        result = await get_affected_entities()
        print(f"   Result contains instance ID: {'i-1234567890abcdef0' in result}")
        assert "i-1234567890abcdef0" in result
        print("   ✅ PASSED")

    print("\n" + "=" * 50)
    print("🎉 All MCP tool tests passed!")


async def test_error_handling():
    """Test error handling in MCP tools."""
    print("\n🧪 Testing Error Handling")
    print("=" * 50)

    # Test with AWS API error
    print("\n1. Testing AWS API error handling:")

    with patch("awslabs.aws_health_mcp_server.server.health_client.client") as mock_client:
        mock_client.describe_events.side_effect = Exception("Mock AWS API Error")

        result = await get_service_health()
        print(f"   Error handled: {'Error fetching AWS health events' in result}")
        assert "Error fetching AWS health events" in result
        print("   ✅ PASSED")

    print("\n" + "=" * 50)
    print("🎉 Error handling tests passed!")


if __name__ == "__main__":
    asyncio.run(test_tools_with_mock_data())
    asyncio.run(test_error_handling())
