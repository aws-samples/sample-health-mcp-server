"""Tests for AWS Health MCP Server."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aws_health_mcp.server.config import Config
from aws_health_mcp.server.formatters import (
    compress_service_name,
    format_entity,
    format_event,
    format_timestamp,
    validate_service_name,
)

# A representative slice of real DescribeEventTypes service codes. Tests pass
# this explicitly so they never depend on network access.
KNOWN_SERVICES = [
    "APIGATEWAY",
    "BEDROCK",
    "CLOUDFORMATION",
    "CLOUDTRAIL",
    "COGNITO",
    "DYNAMODB",
    "EC2",
    "ELASTICFILESYSTEM",
    "ELASTICLOADBALANCING",
    "ES",
    "EVENTS",
    "KINESIS_VIDEO",
    "LAMBDA",
    "ORGANIZATIONS",
    "RDS",
    "S3",
    "STATES",
    "STORAGEGATEWAY",
]


def test_config_validation():
    assert Config.validate() is True


def test_config_defaults():
    assert Config.LOG_LEVEL == "INFO"
    assert Config.HEALTH_API_TIMEOUT == 30


def test_server_version():
    from aws_health_mcp.server import __version__

    assert __version__ == "2.0.0"


class TestCompressServiceName:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("EC2", "EC2"),
            ("ec2", "EC2"),
            ("Kinesis Video", "KINESISVIDEO"),
            ("kinesis-video", "KINESISVIDEO"),
            ("KINESIS_VIDEO", "KINESISVIDEO"),
            ("Storage Gateway", "STORAGEGATEWAY"),
        ],
    )
    def test_compression(self, raw, expected):
        assert compress_service_name(raw) == expected


class TestValidateServiceName:
    def test_direct_match(self):
        assert validate_service_name("EC2", KNOWN_SERVICES) == (True, "EC2")

    def test_case_insensitive(self):
        assert validate_service_name("ec2", KNOWN_SERVICES) == (True, "EC2")

    def test_alias_mapping(self):
        assert validate_service_name("ELB", KNOWN_SERVICES) == (
            True,
            "ELASTICLOADBALANCING",
        )

    def test_hyphen_handling(self):
        assert validate_service_name("dynamo-db", KNOWN_SERVICES) == (True, "DYNAMODB")

    @pytest.mark.parametrize(
        "raw,expected",
        [
            # Separator differences resolve without an alias entry
            ("api gateway", "APIGATEWAY"),
            ("Kinesis Video", "KINESIS_VIDEO"),
            ("storage-gateway", "STORAGEGATEWAY"),
            # Semantic aliases: the common name differs from the Health code
            ("Step Functions", "STATES"),
            ("EventBridge", "EVENTS"),
            ("EFS", "ELASTICFILESYSTEM"),
            ("OpenSearch", "ES"),
        ],
    )
    def test_resolves_to_real_service_code(self, raw, expected):
        """Names the old hardcoded list either rejected or silently mismapped."""
        assert validate_service_name(raw, KNOWN_SERVICES) == (True, expected)

    @pytest.mark.parametrize("raw", ["Bedrock", "CloudTrail", "Organizations"])
    def test_services_missing_from_old_hardcoded_list(self, raw):
        """These were unreachable before the list came from the API."""
        is_valid, resolved = validate_service_name(raw, KNOWN_SERVICES)
        assert is_valid is True
        assert resolved == raw.upper()

    def test_invalid_with_suggestion(self):
        assert validate_service_name("LAMBDAA", KNOWN_SERVICES) == (False, "LAMBDA")

    def test_invalid_no_suggestion(self):
        assert validate_service_name("ZZZZNOTASERVICE", KNOWN_SERVICES) == (False, "")

    def test_no_misleading_cross_service_suggestion(self):
        """0.6 cutoff used to answer 'CloudTrial' with a different service."""
        is_valid, resolved = validate_service_name("CLOUDTRIAL", KNOWN_SERVICES)
        assert resolved != "CLOUDFORMATION"

    def test_empty_string(self):
        assert validate_service_name("", KNOWN_SERVICES) == (False, "")

    def test_whitespace_only(self):
        assert validate_service_name("   ", KNOWN_SERVICES) == (False, "")

    def test_offline_mode_accepts_rather_than_rejects(self):
        """With no service list, defer to AWS instead of denying a real service."""
        assert validate_service_name("BEDROCK", None) == (True, "BEDROCK")
        assert validate_service_name("Step Functions", None) == (True, "STATES")


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

        stamp = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        result1 = await client.get_event_description("arn:test", stamp)
        result2 = await client.get_event_description("arn:test", stamp)
        assert result1 == "Test desc"
        assert result2 == "Test desc"
        # Only one API call — second hit is cached
        assert client._client.describe_event_details.call_count == 1

    def _details(self, arn, text, updated):
        return {
            "successfulSet": [
                {
                    "event": {"arn": arn, "lastUpdatedTime": updated},
                    "eventDescription": {"latestDescription": text},
                }
            ],
            "failedSet": [],
        }

    @pytest.mark.asyncio
    async def test_description_refetched_when_event_updated(self, client):
        """An ongoing event rewrites its description; a changed lastUpdatedTime must miss."""
        t1 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 1, 1, 13, 0, tzinfo=timezone.utc)
        client._client.describe_event_details.side_effect = [
            self._details("arn:evt", "Investigating", t1),
            self._details("arn:evt", "Mitigated, recovery in progress", t2),
        ]

        first = await client.get_event_description("arn:evt", t1)
        second = await client.get_event_description("arn:evt", t2)

        assert first == "Investigating"
        assert second == "Mitigated, recovery in progress"
        assert client._client.describe_event_details.call_count == 2

    @pytest.mark.asyncio
    async def test_description_cached_under_fetched_timestamp(self, client):
        """The details response is authoritative: if the event moved on between the
        listing and the fetch, the newer text is filed under the newer timestamp."""
        listed = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        newer = datetime(2026, 1, 1, 12, 5, tzinfo=timezone.utc)
        client._client.describe_event_details.return_value = self._details(
            "arn:evt", "Newer text", newer
        )

        await client.get_event_description("arn:evt", listed)
        # A later listing that has caught up with the newer timestamp reuses it.
        again = await client.get_event_description("arn:evt", newer)

        assert again == "Newer text"
        assert client._client.describe_event_details.call_count == 1

    @pytest.mark.asyncio
    async def test_description_without_timestamp_is_never_served_from_cache(self, client):
        """With no lastUpdatedTime the entry cannot be checked for staleness."""
        t1 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        client._client.describe_event_details.return_value = self._details("arn:evt", "Text", t1)

        await client.get_event_description("arn:evt")
        await client.get_event_description("arn:evt")
        await client.get_event_descriptions_batched(["arn:evt"])

        assert client._client.describe_event_details.call_count == 3

    @pytest.mark.asyncio
    async def test_failed_description_fetch_is_not_cached(self, client):
        """The 'not available' placeholder must not stick for the whole cache TTL."""
        t1 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        client._client.describe_event_details.return_value = {
            "successfulSet": [],
            "failedSet": [{"eventArn": "arn:evt"}],
        }
        client._client.describe_event_details_for_organization.return_value = {
            "successfulSet": [],
            "failedSet": [],
        }
        assert await client.get_event_description("arn:evt", t1) == "Description not available"

        client._client.describe_event_details.return_value = self._details(
            "arn:evt", "Recovered text", t1
        )
        assert await client.get_event_description("arn:evt", t1) == "Recovered text"

    @pytest.mark.asyncio
    async def test_batched_descriptions_only_refetch_changed_events(self, client):
        t1 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 1, 1, 13, 0, tzinfo=timezone.utc)
        texts = {"arn:a": "A v1", "arn:b": "B v1"}

        def describe(eventArns):
            return {
                "successfulSet": [
                    {
                        "event": {"arn": a, "lastUpdatedTime": t1},
                        "eventDescription": {"latestDescription": texts[a]},
                    }
                    for a in eventArns
                ],
                "failedSet": [],
            }

        client._client.describe_event_details.side_effect = describe
        await client.get_event_descriptions_batched(["arn:a", "arn:b"], {"arn:a": t1, "arn:b": t1})

        texts["arn:b"] = "B v2"

        def describe_b(eventArns):
            assert eventArns == ["arn:b"], "unchanged event A must come from cache"
            return {
                "successfulSet": [
                    {
                        "event": {"arn": "arn:b", "lastUpdatedTime": t2},
                        "eventDescription": {"latestDescription": "B v2"},
                    }
                ],
                "failedSet": [],
            }

        client._client.describe_event_details.side_effect = describe_b
        result = await client.get_event_descriptions_batched(
            ["arn:a", "arn:b"], {"arn:a": t1, "arn:b": t2}
        )
        assert result == {"arn:a": "A v1", "arn:b": "B v2"}

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
        mock_paginator.paginate.return_value = [{"affectedAccounts": ["111111111111"]}]
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
        self.mock_client.get_known_services = AsyncMock(return_value=["EC2", "RDS"])
        from aws_health_mcp.server.server import get_service_events

        result = await get_service_events("NOTAREALSERVICE")
        assert "Unknown AWS service" in result

    @pytest.mark.asyncio
    async def test_get_service_events_suggests_real_service(self):
        self.mock_client.check_health_api_access = AsyncMock(return_value=(True, None))
        self.mock_client.get_known_services = AsyncMock(return_value=["EC2", "LAMBDA"])
        from aws_health_mcp.server.server import get_service_events

        result = await get_service_events("LAMBDAA")
        assert "Did you mean 'LAMBDA'?" in result

    @pytest.mark.asyncio
    async def test_get_service_events_accepts_service_absent_from_old_list(self):
        """BEDROCK was rejected outright by the hardcoded list."""
        self.mock_client.check_health_api_access = AsyncMock(return_value=(True, None))
        self.mock_client.get_known_services = AsyncMock(return_value=["BEDROCK", "EC2"])
        self.mock_client.paginate = AsyncMock(return_value=[])
        from aws_health_mcp.server.server import get_service_events

        result = await get_service_events("Bedrock")
        assert "BEDROCK" in result
        assert "Unknown AWS service" not in result

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
        self.mock_client.check_org_health_access = AsyncMock(return_value=(False, "Not enabled"))
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


class TestNewReadOnlyTools:
    @pytest.fixture(autouse=True)
    def mock_health_client(self):
        with patch("aws_health_mcp.server.server.health_client") as mock:
            self.mock_client = mock
            yield mock

    @pytest.mark.asyncio
    async def test_get_event_details_empty_input(self):
        from aws_health_mcp.server.server import get_event_details

        assert "No event ARNs provided" in await get_event_details([])

    @pytest.mark.asyncio
    async def test_get_event_details_formats_event(self):
        self.mock_client.get_event_descriptions_batched = AsyncMock(
            return_value={"arn:evt:1": "Instance is being retired"}
        )
        self.mock_client.call = AsyncMock(
            return_value={
                "successfulSet": [
                    {
                        "event": {
                            "arn": "arn:evt:1",
                            "service": "EC2",
                            "eventTypeCode": "AWS_EC2_INSTANCE_RETIREMENT",
                            "statusCode": "upcoming",
                            "region": "us-east-1",
                        }
                    }
                ],
                "failedSet": [],
            }
        )
        from aws_health_mcp.server.server import get_event_details

        result = await get_event_details(["arn:evt:1"])
        assert "AWS_EC2_INSTANCE_RETIREMENT" in result
        assert "Instance is being retired" in result
        assert "arn:evt:1" in result

    @pytest.mark.asyncio
    async def test_get_event_details_reports_unknown_arn(self):
        self.mock_client.get_event_descriptions_batched = AsyncMock(return_value={})
        self.mock_client.call = AsyncMock(return_value={"successfulSet": [], "failedSet": []})
        from aws_health_mcp.server.server import get_event_details

        result = await get_event_details(["arn:missing"])
        assert "No detail available" in result

    @pytest.mark.asyncio
    async def test_get_event_details_batches_by_ten(self):
        """describe_event_details caps eventArns at 10 per call."""
        arns = [f"arn:evt:{i}" for i in range(25)]
        self.mock_client.get_event_descriptions_batched = AsyncMock(return_value={})
        self.mock_client.call = AsyncMock(return_value={"successfulSet": [], "failedSet": []})
        from aws_health_mcp.server.server import get_event_details

        await get_event_details(arns)
        assert self.mock_client.call.await_count == 3
        for call_args in self.mock_client.call.await_args_list:
            assert len(call_args.kwargs["eventArns"]) <= 10

    @pytest.mark.asyncio
    async def test_summarize_rejects_bad_group_by(self):
        from aws_health_mcp.server.server import summarize_health_events

        assert "Invalid group_by" in await summarize_health_events(group_by="colour")

    @pytest.mark.asyncio
    async def test_summarize_counts_by_service_without_descriptions(self):
        """The summary must not pull descriptions -- that is the token blow-up."""
        self.mock_client.paginate = AsyncMock(
            return_value=[
                {"service": "EC2", "statusCode": "open", "region": "us-east-1"},
                {"service": "EC2", "statusCode": "open", "region": "us-west-2"},
                {"service": "RDS", "statusCode": "upcoming", "region": "us-east-1"},
            ]
        )
        from aws_health_mcp.server.server import summarize_health_events

        result = await summarize_health_events(group_by="service")
        assert "3 health events" in result
        assert "| EC2 | 2 |" in result
        assert "| RDS | 1 |" in result
        self.mock_client.get_event_descriptions_batched.assert_not_called()

    @pytest.mark.asyncio
    async def test_summarize_by_category_uses_server_side_aggregate(self):
        """eventTypeCategory is the only field DescribeEventAggregates supports."""
        self.mock_client.call = AsyncMock(
            return_value={
                "eventAggregates": [
                    {"aggregateValue": "scheduledChange", "count": 44},
                    {"aggregateValue": "issue", "count": 2},
                ]
            }
        )
        from aws_health_mcp.server.server import summarize_health_events

        result = await summarize_health_events(group_by="category")
        assert "46 health events" in result
        assert "| scheduledChange | 44 |" in result
        assert self.mock_client.call.await_args.kwargs["aggregateField"] == "eventTypeCategory"

    @pytest.mark.asyncio
    async def test_summarize_no_events(self):
        self.mock_client.paginate = AsyncMock(return_value=[])
        from aws_health_mcp.server.server import summarize_health_events

        assert "No health events found" in await summarize_health_events(group_by="region")

    @pytest.mark.asyncio
    async def test_count_affected_entities(self):
        self.mock_client.call = AsyncMock(
            return_value={
                "entityAggregates": [
                    {"eventArn": "arn:evt:1", "count": 42, "statuses": {"IMPAIRED": 42}}
                ]
            }
        )
        from aws_health_mcp.server.server import count_affected_entities

        result = await count_affected_entities(["arn:evt:1"])
        assert "42" in result
        assert "IMPAIRED: 42" in result

    @pytest.mark.asyncio
    async def test_count_affected_entities_empty_input(self):
        from aws_health_mcp.server.server import count_affected_entities

        assert "No event ARNs provided" in await count_affected_entities([])

    @pytest.mark.asyncio
    async def test_list_affected_accounts(self):
        self.mock_client.check_org_health_access = AsyncMock(return_value=(True, None))
        self.mock_client.get_affected_accounts = AsyncMock(
            return_value=["111111111111", "222222222222"]
        )
        from aws_health_mcp.server.server import list_affected_accounts

        result = await list_affected_accounts("arn:evt:1")
        assert "2 affected account(s)" in result
        assert "111111111111" in result

    @pytest.mark.asyncio
    async def test_list_affected_accounts_no_org_access(self):
        self.mock_client.check_org_health_access = AsyncMock(return_value=(False, "Not enabled"))
        from aws_health_mcp.server.server import list_affected_accounts

        assert "Not enabled" in await list_affected_accounts("arn:evt:1")

    @pytest.mark.asyncio
    async def test_list_event_types_unfiltered_returns_service_index(self):
        self.mock_client.get_known_services = AsyncMock(return_value=["EC2", "RDS", "STATES"])
        from aws_health_mcp.server.server import list_event_types

        result = await list_event_types()
        assert "3 services" in result
        assert "STATES" in result

    @pytest.mark.asyncio
    async def test_list_event_types_for_service(self):
        self.mock_client.get_known_services = AsyncMock(return_value=["STATES"])
        self.mock_client.paginate = AsyncMock(
            return_value=[
                {"service": "STATES", "code": "AWS_STATES_OPERATIONAL_ISSUE", "category": "issue"}
            ]
        )
        from aws_health_mcp.server.server import list_event_types

        result = await list_event_types(service="Step Functions")
        assert "STATES" in result
        assert "AWS_STATES_OPERATIONAL_ISSUE" in result

    @pytest.mark.asyncio
    async def test_list_event_types_rejects_bad_category(self):
        self.mock_client.get_known_services = AsyncMock(return_value=["EC2"])
        from aws_health_mcp.server.server import list_event_types

        assert "Invalid category" in await list_event_types(category="nonsense")

    @pytest.mark.asyncio
    async def test_check_health_access_all_ok(self):
        self.mock_client.get_caller_identity = AsyncMock(
            return_value={"Account": "123456789012", "Arn": "arn:aws:iam::123456789012:user/dev"}
        )
        self.mock_client.check_health_api_access = AsyncMock(return_value=(True, None))
        self.mock_client.check_org_health_access = AsyncMock(return_value=(True, None))
        self.mock_client.get_known_services = AsyncMock(return_value=["EC2"])
        from aws_health_mcp.server.server import check_health_access

        result = await check_health_access()
        assert "123456789012" in result
        assert "**Health API (account):** ok" in result
        assert "**Health API (organization):** ok" in result

    @pytest.mark.asyncio
    async def test_check_health_access_explains_subscription_requirement(self):
        self.mock_client.get_caller_identity = AsyncMock(return_value=None)
        self.mock_client.check_health_api_access = AsyncMock(
            return_value=(
                False,
                "AWS Health API requires Business or Enterprise Support subscription",
            )
        )
        self.mock_client.check_org_health_access = AsyncMock(return_value=(False, "Not enabled"))
        self.mock_client.get_known_services = AsyncMock(return_value=None)
        from aws_health_mcp.server.server import check_health_access

        result = await check_health_access()
        assert "Credentials:** FAILED" in result
        assert "Business or Enterprise Support plan" in result
        assert "enable-health-service-access-for-organization" in result


class TestScopingFilters:
    @pytest.fixture(autouse=True)
    def mock_health_client(self):
        with patch("aws_health_mcp.server.server.health_client") as mock:
            self.mock_client = mock
            yield mock

    def _sent_filter(self):
        return self.mock_client.paginate.await_args.kwargs["filter"]

    @pytest.mark.asyncio
    async def test_regions_filter_passed_through(self):
        self.mock_client.paginate = AsyncMock(return_value=[])
        from aws_health_mcp.server.server import get_service_health

        await get_service_health(regions=["us-west-2", "eu-west-1"])
        assert self._sent_filter()["regions"] == ["us-west-2", "eu-west-1"]

    @pytest.mark.asyncio
    async def test_event_listing_never_sends_tags_or_entity_values(self):
        """Neither filter works as expected on DescribeEvents.

        A live check showed `tags` is ignored outright (a nonsense tag key still
        returned all 48 events) and `entityValues` also matches events with no
        entities (a bogus resource ID still returned 2). Sending either would
        make the tool confidently wrong, so resource scoping lives in
        find_events_for_resources instead.
        """
        self.mock_client.paginate = AsyncMock(return_value=[])
        from aws_health_mcp.server.server import get_service_health

        await get_service_health(regions=["us-east-1"])
        sent = self._sent_filter()
        assert "tags" not in sent
        assert "entityValues" not in sent

    @pytest.mark.asyncio
    async def test_no_filters_means_no_extra_keys(self):
        self.mock_client.paginate = AsyncMock(return_value=[])
        from aws_health_mcp.server.server import get_service_health

        await get_service_health()
        assert set(self._sent_filter()) == {"eventStatusCodes"}

    @pytest.mark.asyncio
    async def test_scheduled_changes_accepts_filters(self):
        self.mock_client.paginate = AsyncMock(return_value=[])
        from aws_health_mcp.server.server import get_scheduled_changes

        await get_scheduled_changes(regions=["ap-southeast-2"])
        sent = self._sent_filter()
        assert sent["regions"] == ["ap-southeast-2"]
        assert sent["eventTypeCategories"] == ["scheduledChange"]

    @pytest.mark.asyncio
    async def test_org_account_filter_is_server_side(self):
        """awsAccountIds replaces one DescribeAffectedAccounts call per event."""
        self.mock_client.check_org_health_access = AsyncMock(return_value=(True, None))
        self.mock_client.paginate = AsyncMock(return_value=[])
        from aws_health_mcp.server.server import get_org_account_events

        await get_org_account_events("123456789012")
        assert self._sent_filter()["awsAccountIds"] == ["123456789012"]
        self.mock_client.get_affected_accounts.assert_not_called()

    @pytest.mark.asyncio
    async def test_org_health_events_account_filter_is_server_side(self):
        self.mock_client.check_org_health_access = AsyncMock(return_value=(True, None))
        self.mock_client.paginate = AsyncMock(return_value=[])
        from aws_health_mcp.server.server import get_org_health_events

        await get_org_health_events(account_id="123456789012")
        assert self._sent_filter()["awsAccountIds"] == ["123456789012"]
        self.mock_client.get_affected_accounts.assert_not_called()

    @pytest.mark.asyncio
    async def test_org_health_events_rejects_bad_account_id(self):
        self.mock_client.check_org_health_access = AsyncMock(return_value=(True, None))
        from aws_health_mcp.server.server import get_org_health_events

        assert "Invalid account ID" in await get_org_health_events(account_id="123")

    @pytest.mark.asyncio
    async def test_org_tools_never_send_tags(self):
        """OrganizationEventFilter has no tag support at all."""
        self.mock_client.check_org_health_access = AsyncMock(return_value=(True, None))
        self.mock_client.get_known_services = AsyncMock(return_value=["EC2"])
        self.mock_client.paginate = AsyncMock(return_value=[])
        from aws_health_mcp.server.server import get_org_service_events

        await get_org_service_events("EC2", regions=["us-east-1"])
        assert "tags" not in self._sent_filter()


class TestFindEventsForResources:
    @pytest.fixture(autouse=True)
    def mock_health_client(self):
        with patch("aws_health_mcp.server.server.health_client") as mock:
            self.mock_client = mock
            yield mock

    @pytest.mark.asyncio
    async def test_empty_input(self):
        from aws_health_mcp.server.server import find_events_for_resources

        assert "No resource identifiers provided" in await find_events_for_resources([])

    @pytest.mark.asyncio
    async def test_reports_no_match_without_claiming_events_exist(self):
        self.mock_client.paginate = AsyncMock(return_value=[{"arn": "arn:evt:1"}])
        self.mock_client.find_entities_for_values = AsyncMock(return_value={})
        from aws_health_mcp.server.server import find_events_for_resources

        result = await find_events_for_resources(["i-000nonexistent"])
        assert "No health events affect i-000nonexistent" in result
        assert "searched 1 events" in result

    @pytest.mark.asyncio
    async def test_returns_matching_event_and_resource(self):
        self.mock_client.paginate = AsyncMock(
            return_value=[
                {
                    "arn": "arn:evt:1",
                    "service": "ECS",
                    "eventTypeCode": "AWS_ECS_TASK_PATCHING_RETIREMENT",
                    "statusCode": "upcoming",
                    "region": "us-west-2",
                },
                {"arn": "arn:evt:2", "service": "RDS"},
            ]
        )
        self.mock_client.find_entities_for_values = AsyncMock(
            return_value={"arn:evt:1": [{"entityValue": "my-cluster"}]}
        )
        self.mock_client.get_event_descriptions_batched = AsyncMock(
            return_value={"arn:evt:1": "Tasks will be replaced"}
        )
        from aws_health_mcp.server.server import find_events_for_resources

        result = await find_events_for_resources(["my-cluster"])
        assert "**1 event(s)** affect" in result
        assert "AWS_ECS_TASK_PATCHING_RETIREMENT" in result
        assert "my-cluster" in result
        # The non-matching event must not leak into the answer
        assert "RDS" not in result

    @pytest.mark.asyncio
    async def test_no_events_at_all(self):
        self.mock_client.paginate = AsyncMock(return_value=[])
        from aws_health_mcp.server.server import find_events_for_resources

        assert "No health events to search" in await find_events_for_resources(["i-abc"])


class TestFindEntitiesForValues:
    @pytest.fixture
    def client(self):
        from aws_health_mcp.server.client import HealthClient

        c = HealthClient()
        c._client = MagicMock()
        return c

    @pytest.mark.asyncio
    async def test_batches_event_arns_by_ten(self, client):
        """DescribeAffectedEntities rejects more than 10 eventArns per call."""
        arns = [f"arn:evt:{i}" for i in range(25)]
        seen_batches = []

        mock_paginator = MagicMock()

        def paginate(**kwargs):
            seen_batches.append(kwargs["filter"]["eventArns"])
            return [{"entities": []}]

        mock_paginator.paginate.side_effect = paginate
        client._client.get_paginator.return_value = mock_paginator

        await client.find_entities_for_values(arns, ["i-abc"])
        assert len(seen_batches) == 3
        assert all(len(b) <= 10 for b in seen_batches)

    @pytest.mark.asyncio
    async def test_groups_entities_by_event_arn(self, client):
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {
                "entities": [
                    {"eventArn": "arn:evt:1", "entityValue": "i-a"},
                    {"eventArn": "arn:evt:1", "entityValue": "i-b"},
                    {"eventArn": "arn:evt:2", "entityValue": "i-c"},
                ]
            }
        ]
        client._client.get_paginator.return_value = mock_paginator

        result = await client.find_entities_for_values(
            ["arn:evt:1", "arn:evt:2"], ["i-a", "i-b", "i-c"]
        )
        assert len(result["arn:evt:1"]) == 2
        assert len(result["arn:evt:2"]) == 1

    @pytest.mark.asyncio
    async def test_batch_failure_does_not_abort_search(self, client):
        client._client.get_paginator.side_effect = RuntimeError("throttled")

        result = await client.find_entities_for_values(["arn:evt:1"], ["i-a"])
        assert result == {}

    @pytest.mark.asyncio
    async def test_discards_public_event_unknown_placeholder(self, client):
        """PUBLIC events return entityValue 'UNKNOWN' regardless of the filter.

        Trusting the API filter here reported 2 matching events for a resource
        ID that exists nowhere.
        """
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {
                "entities": [
                    {"eventArn": "arn:public:1", "entityValue": "UNKNOWN"},
                    {"eventArn": "arn:evt:1", "entityValue": "i-a"},
                ]
            }
        ]
        client._client.get_paginator.return_value = mock_paginator

        result = await client.find_entities_for_values(["arn:public:1", "arn:evt:1"], ["i-a"])
        assert "arn:public:1" not in result
        assert result["arn:evt:1"][0]["entityValue"] == "i-a"

    @pytest.mark.asyncio
    async def test_match_is_case_insensitive(self, client):
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {"entities": [{"eventArn": "arn:evt:1", "entityValue": "My-Cluster"}]}
        ]
        client._client.get_paginator.return_value = mock_paginator

        result = await client.find_entities_for_values(["arn:evt:1"], ["my-cluster"])
        assert "arn:evt:1" in result


class TestToolAnnotations:
    def test_all_tools_declared_read_only(self):
        """No tool here mutates; clients should be able to see that."""
        from aws_health_mcp.server.server import mcp

        tools = asyncio.run(mcp.list_tools())
        assert len(tools) == 18
        for tool in tools:
            assert tool.annotations is not None, f"{tool.name} has no annotations"
            assert tool.annotations.readOnlyHint is True, f"{tool.name} not read-only"
            assert tool.annotations.destructiveHint is False, f"{tool.name} marked destructive"

    def test_no_mutating_health_operations_exposed(self):
        """Enable/DisableHealthServiceAccessForOrganization must stay unexposed."""
        from aws_health_mcp.server.server import mcp

        names = {tool.name for tool in asyncio.run(mcp.list_tools())}
        assert not any("enable" in n or "disable" in n for n in names)
