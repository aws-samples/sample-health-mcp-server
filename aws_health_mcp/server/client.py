"""AWS Health API client with lazy initialization and async support."""

import asyncio
import logging
import os
import time as _time
from typing import Optional

import boto3
from botocore.config import Config as BotocoreConfig
from botocore.exceptions import ClientError

from .config import Config

logger = logging.getLogger(__name__)

MAX_CONCURRENCY = int(os.getenv("HEALTH_API_MAX_CONCURRENCY", "5"))


class HealthClient:
    """AWS Health API client wrapper with lazy init, caching, and async support."""

    def __init__(self):
        self._client = None
        self._cache: dict[str, tuple[float, object]] = {}
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

    @property
    def client(self):
        """Lazily create the boto3 Health client on first use."""
        if self._client is None:
            boto_config = BotocoreConfig(
                region_name="us-east-1",
                retries={"max_attempts": 3, "mode": "adaptive"},
                read_timeout=Config.HEALTH_API_TIMEOUT,
                connect_timeout=10,
            )
            session = boto3.Session(profile_name=Config.AWS_PROFILE)
            self._client = session.client("health", config=boto_config)
            logger.info("AWS Health API client initialized")
        return self._client

    def _cache_get(self, key: str):
        if not Config.ENABLE_CACHE:
            return None
        entry = self._cache.get(key)
        if entry is None:
            return None
        ts, value = entry
        if _time.time() - ts > Config.CACHE_TTL:
            del self._cache[key]
            return None
        return value

    def _cache_set(self, key: str, value) -> None:
        if Config.ENABLE_CACHE:
            self._cache[key] = (_time.time(), value)

    async def paginate(self, operation: str, **kwargs) -> list:
        """Paginate a Health API operation off the event loop, with concurrency control."""
        async with self._semaphore:
            def _sync():
                results = []
                paginator = self.client.get_paginator(operation)
                key = _response_key(operation)
                for page in paginator.paginate(**kwargs):
                    if key in page:
                        results.extend(page[key])
                return results
            return await asyncio.to_thread(_sync)

    async def call(self, operation: str, **kwargs) -> dict:
        """Call a Health API operation off the event loop, with concurrency control."""
        async with self._semaphore:
            def _sync():
                method = getattr(self.client, operation)
                return method(**kwargs)
            return await asyncio.to_thread(_sync)

    async def get_event_description(self, event_arn: str) -> str:
        """Get a single event description. Prefer get_event_descriptions_batched for multiple."""
        cache_key = f"desc:{event_arn}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        results = await self.get_event_descriptions_batched([event_arn])
        return results.get(event_arn, "Description not available")

    async def get_event_descriptions_batched(self, event_arns: list[str]) -> dict[str, str]:
        """Fetch descriptions for multiple events in batched API calls.

        describe_event_details accepts up to 10 ARNs per call.
        Falls back to the org API for any ARNs that fail.
        Results are cached individually.
        """
        BATCH_SIZE = 10
        result: dict[str, str] = {}
        uncached_arns: list[str] = []

        for arn in event_arns:
            cached = self._cache_get(f"desc:{arn}")
            if cached is not None:
                result[arn] = cached
            else:
                uncached_arns.append(arn)

        if not uncached_arns:
            return result

        batches = [
            uncached_arns[i : i + BATCH_SIZE]
            for i in range(0, len(uncached_arns), BATCH_SIZE)
        ]

        failed_arns: list[str] = []

        async def _fetch_batch(batch: list[str]) -> dict[str, str]:
            batch_result: dict[str, str] = {}
            try:
                response = await self.call("describe_event_details", eventArns=batch)
                for detail in response.get("successfulSet", []):
                    arn = detail.get("event", {}).get("arn", "")
                    desc = detail.get("eventDescription", {}).get("latestDescription", "")
                    if arn and desc:
                        batch_result[arn] = desc
                for failure in response.get("failedSet", []):
                    failed_arn = failure.get("eventArn", "")
                    if failed_arn:
                        failed_arns.append(failed_arn)
            except Exception:
                failed_arns.extend(batch)
            return batch_result

        batch_results = await asyncio.gather(*[_fetch_batch(b) for b in batches])
        for br in batch_results:
            result.update(br)

        # Retry failures via org API (also batches of 10)
        remaining = [arn for arn in failed_arns if arn not in result]
        if remaining:
            org_batches = [
                remaining[i : i + BATCH_SIZE]
                for i in range(0, len(remaining), BATCH_SIZE)
            ]

            async def _fetch_org_batch(batch: list[str]) -> dict[str, str]:
                batch_result: dict[str, str] = {}
                try:
                    response = await self.call(
                        "describe_event_details_for_organization",
                        organizationEventDetailFilters=[{"eventArn": arn} for arn in batch],
                    )
                    for detail in response.get("successfulSet", []):
                        arn = detail.get("event", {}).get("arn", "")
                        desc = detail.get("eventDescription", {}).get("latestDescription", "")
                        if arn and desc:
                            batch_result[arn] = desc
                except Exception:
                    pass
                return batch_result

            org_results = await asyncio.gather(*[_fetch_org_batch(b) for b in org_batches])
            for br in org_results:
                result.update(br)

        # Fill missing with default and cache everything
        for arn in uncached_arns:
            desc = result.get(arn, "Description not available")
            result[arn] = desc
            self._cache_set(f"desc:{arn}", desc)

        return result

    async def check_health_api_access(self) -> tuple[bool, Optional[str]]:
        """Check if we have access to AWS Health API."""
        try:
            await self.call("describe_events", filter={"eventStatusCodes": ["open"]}, maxResults=10)
            return True, None
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code == "SubscriptionRequiredException":
                return False, "AWS Health API requires Business or Enterprise Support subscription"
            if code in ("AccessDeniedException", "UnauthorizedException"):
                return False, "Insufficient permissions to access AWS Health API"
            return False, f"{code}: {e.response['Error']['Message']}"
        except Exception as e:
            return False, str(e)

    async def check_org_health_access(self) -> tuple[bool, Optional[str]]:
        """Check if AWS Health organization view is enabled."""
        try:
            result = await self.call("describe_health_service_status_for_organization")
            status = result.get("healthServiceAccessStatusForOrganization")
            if status == "ENABLED":
                return True, None
            if status == "PENDING":
                return False, "AWS Health organization view is pending activation."
            return False, (
                "AWS Health organization view is not enabled. "
                "Enable it via EnableHealthServiceAccessForOrganization from your management account."
            )
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code == "AccessDeniedException":
                return (
                    False,
                    "Insufficient permissions — ensure you're calling from the management account.",
                )
            return False, f"{code}: {e.response['Error']['Message']}"
        except Exception as e:
            return False, str(e)

    async def get_affected_accounts(self, event_arn: str) -> list[str]:
        """Get affected accounts for an org event, with caching and pagination."""
        cache_key = f"accounts:{event_arn}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        try:
            accounts = await self.paginate(
                "describe_affected_accounts_for_organization", eventArn=event_arn
            )
        except Exception:
            accounts = []

        self._cache_set(cache_key, accounts)
        return accounts

    async def get_org_entities_batched(
        self, event_arn: str, account_ids: list[str]
    ) -> dict[str, list]:
        """Fetch affected entities for multiple accounts efficiently.

        Batches account IDs into groups of 10 (API limit for organizationEntityFilters)
        and fetches them concurrently with semaphore protection.

        Returns a dict mapping account_id -> list of entities.
        """
        BATCH_SIZE = 10
        batches = [
            account_ids[i : i + BATCH_SIZE]
            for i in range(0, len(account_ids), BATCH_SIZE)
        ]

        async def _fetch_batch(batch: list[str]) -> list:
            try:
                return await self.paginate(
                    "describe_affected_entities_for_organization",
                    organizationEntityFilters=[
                        {"eventArn": event_arn, "awsAccountId": acc} for acc in batch
                    ],
                )
            except Exception:
                return []

        batch_results = await asyncio.gather(*[_fetch_batch(b) for b in batches])

        result: dict[str, list] = {}
        for entities in batch_results:
            for entity in entities:
                acc = entity.get("awsAccountId", "")
                if acc:
                    result.setdefault(acc, []).append(entity)
        return result


def _response_key(operation: str) -> str:
    """Map paginator operation to its response list key."""
    mapping = {
        "describe_events": "events",
        "describe_affected_entities": "entities",
        "describe_events_for_organization": "events",
        "describe_affected_entities_for_organization": "entities",
        "describe_affected_accounts_for_organization": "affectedAccounts",
    }
    return mapping.get(operation, "events")


health_client = HealthClient()
