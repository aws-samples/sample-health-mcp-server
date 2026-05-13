"""Tests for AWS Health MCP Server."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aws_health_mcp.server.config import Config
from aws_health_mcp.server.consts import VALID_AWS_SERVICES
from aws_health_mcp.server.formatters import (
    format_entity,
    format_event,
    format_timestamp,
    validate_service_name,
)


def test_config_validation():
    assert Config.validate() is True


def test_config_defaults():
    assert Config.LOG_LEVEL == "INFO"
    assert Config.HEALTH_API_TIMEOUT == 30


def test_server_version():
    from aws_health_mcp.server import __version__

    assert __version__ == "2.0.0"


class TestValidateServiceName:
    def test_direct_match(self):
        is_valid, normalized = validate_service_name("EC2")
        assert is_valid is True
        assert normalized == "EC2"

    def test_case_insensitive(self):
        is_valid, normalized = validate_service_name("ec2")
        assert is_valid is True
        assert normalized == "EC2"

    def test_alias_mapping(self):
        is_valid, normalized = validate_service_name("ELB")
        assert is_valid is True
        assert normalized == "ELASTICLOADBALANCING"

    def test_hyphen_handling(self):
        is_valid, normalized = validate_service_name("dynamo-db")
        assert is_valid is True
        assert normalized == "DYNAMODB"

    def test_invalid_with_suggestion(self):
        is_valid, normalized = validate_service_name("LAMBDAA")
        assert is_valid is False
        assert normalized == "LAMBDA"

    def test_invalid_no_suggestion(self):
        is_valid, normalized = validate_service_name("ZZZZNOTASERVICE")
        assert is_valid is False
        assert normalized == ""

    def test_empty_string(self):
        is_valid, normalized = validate_service_name("")
        assert is_valid is False
        assert normalized == ""


class TestFormatTimestamp:
    def test_none(self):
        assert format_timestamp(None) == "Not specified"

    def test_datetime(self):
        dt = datetime(2024, 3, 15, 10, 30, 0, tzinfo=timezone.utc)
        assert format_timestamp(dt) == "2024-03-15 10:30:00 UTC"


class TestFormatEvent:
    def test_basic_event(self):
        event = {
            "service": "EC2",
            "eventTypeCode": "AWS_EC2_INSTANCE_ISSUE",
            "statusCode": "open",
            "region": "us-east-1",
            "startTime": datetime(2024, 1, 1, 0, 0, 0),
        }
        result = format_event(event, "Test description")
        assert "EC2" in result
        assert "AWS_EC2_INSTANCE_ISSUE" in result
        assert "OPEN" in result
        assert "us-east-1" in result
        assert "Test description" in result

    def test_event_with_accounts(self):
        event = {
            "service": "RDS",
            "eventTypeCode": "AWS_RDS_MAINTENANCE",
            "statusCode": "upcoming",
            "region": "eu-west-1",
        }
        accounts = ["111111111111", "222222222222"]
        result = format_event(event, "Maintenance", accounts)
        assert "Affected Accounts (2)" in result
        assert "111111111111" in result
        assert "222222222222" in result

    def test_event_with_many_accounts_truncates(self):
        event = {
            "service": "S3",
            "eventTypeCode": "AWS_S3_ISSUE",
            "statusCode": "open",
            "region": "global",
        }
        accounts = [f"{i:012d}" for i in range(25)]
        result = format_event(event, "desc", accounts)
        assert "... and 5 more" in result


class TestFormatEntity:
    def test_basic_entity(self):
        entity = {"entityValue": "i-1234567890abcdef0", "statusCode": "IMPAIRED"}
        result = format_entity(entity)
        assert "i-1234567890abcdef0" in result

    def test_entity_with_timestamp(self):
        entity = {
            "entityValue": "i-abc",
            "lastUpdatedTime": datetime(2024, 6, 1, 12, 0, 0),
        }
        result = format_entity(entity)
        assert "i-abc" in result
        assert "2024-06-01 12:00:00 UTC" in result


class TestHealthClient:
    @pytest.fixture
    def client(self):
        from aws_health_mcp.server.client import HealthClient

        c = HealthClient()
        c._client = MagicMock()
        return c

    def test_cache_set_and_get(self, client):
        client._cache_set("key1", "value1")
        assert client._cache_get("key1") == "value1"

    def test_cache_miss(self, client):
        assert client._cache_get("nonexistent") is None

    @pytest.mark.asyncio
    async def test_paginate(self, client):
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {"events": [{"arn": "arn:1"}, {"arn": "arn:2"}]},
            {"events": [{"arn": "arn:3"}]},
        ]
        client._client.get_paginator.return_value = mock_paginator

        results = await client.paginate("describe_events", filter={"eventStatusCodes": ["open"]})
        assert len(results) == 3
        assert results[0]["arn"] == "arn:1"

    @pytest.mark.asyncio
    async def test_get_event_description_caches(self, client):
        client._client.describe_event_details.return_value = {
            "successfulSet": [
                {
                    "event": {"arn": "arn:test"},
                    "eventDescription": {"latestDescription": "Test desc"},
                }
            ],
            "failedSet": [],
        }

        result1 = await client.get_event_description("arn:test")
        result2 = await client.get_event_description("arn:test")
        assert result1 == "Test desc"
        assert result2 == "Test desc"
        # Only one API call — second hit is cached
        assert client._client.describe_event_details.call_count == 1

    @pytest.mark.asyncio
    async def test_get_event_descriptions_batched(self, client):
        """Verify 15 ARNs result in 2 API calls (batches of 10)."""
        arns = [f"arn:event:{i}" for i in range(15)]

        def mock_describe(eventArns):
            return {
                "successfulSet": [
                    {
                        "event": {"arn": arn},
                        "eventDescription": {"latestDescription": f"Desc for {arn}"},
                    }
                    for arn in eventArns
                ],
                "failedSet": [],
            }

        client._client.describe_event_details.side_effect = mock_describe

        results = await client.get_event_descriptions_batched(arns)
        assert len(results) == 15
        assert results["arn:event:0"] == "Desc for arn:event:0"
        assert results["arn:event:14"] == "Desc for arn:event:14"
        # 15 ARNs / 10 per batch = 2 API calls
        assert client._client.describe_event_details.call_count == 2

    @pytest.mark.asyncio
    async def test_check_health_api_access_success(self, client):
        client._client.describe_events.return_value = {"events": []}
        ok, msg = await client.check_health_api_access()
        assert ok is True
        assert msg is None

    @pytest.mark.asyncio
    async def test_get_affected_accounts_caches(self, client):
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {"affectedAccounts": ["111111111111"]}
        ]
        client._client.get_paginator.return_value = mock_paginator

        result1 = await client.get_affected_accounts("arn:evt")
        result2 = await client.get_affected_accounts("arn:evt")
        assert result1 == ["111111111111"]
        assert result2 == ["111111111111"]
        # Paginator only called once due to caching
        assert client._client.get_paginator.call_count == 1


class TestServerTools:
    @pytest.fixture(autouse=True)
    def mock_health_client(self):
        with patch("aws_health_mcp.server.server.health_client") as mock:
            self.mock_client = mock
            yield mock

    @pytest.mark.asyncio
    async def test_get_service_health_no_events(self):
        self.mock_client.paginate = AsyncMock(return_value=[])
        from aws_health_mcp.server.server import get_service_health

        result = await get_service_health()
        assert result == "No active AWS health events found."

    @pytest.mark.asyncio
    async def test_get_service_events_invalid_service(self):
        self.mock_client.check_health_api_access = AsyncMock(return_value=(True, None))
        from aws_health_mcp.server.server import get_service_events

        result = await get_service_events("NOTAREALSERVICE")
        assert "Invalid service name" in result

    @pytest.mark.asyncio
    async def test_get_service_events_no_access(self):
        self.mock_client.check_health_api_access = AsyncMock(
            return_value=(False, "No subscription")
        )
        from aws_health_mcp.server.server import get_service_events

        result = await get_service_events("EC2")
        assert "No subscription" in result

    @pytest.mark.asyncio
    async def test_get_org_health_events_no_access(self):
        self.mock_client.check_org_health_access = AsyncMock(
            return_value=(False, "Not enabled")
        )
        from aws_health_mcp.server.server import get_org_health_events

        result = await get_org_health_events()
        assert "Not enabled" in result

    @pytest.mark.asyncio
    async def test_get_org_account_events_invalid_id(self):
        self.mock_client.check_org_health_access = AsyncMock(return_value=(True, None))
        from aws_health_mcp.server.server import get_org_account_events

        result = await get_org_account_events("12345")
        assert "Invalid account ID" in result

    @pytest.mark.asyncio
    async def test_get_org_health_events_invalid_status(self):
        self.mock_client.check_org_health_access = AsyncMock(return_value=(True, None))
        from aws_health_mcp.server.server import get_org_health_events

        result = await get_org_health_events(status="invalid")
        assert "Invalid status" in result
