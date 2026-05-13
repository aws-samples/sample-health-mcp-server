"""Formatting utilities for AWS Health events and data."""

import asyncio
import difflib
from typing import TYPE_CHECKING

from .consts import VALID_AWS_SERVICES

if TYPE_CHECKING:
    from .client import HealthClient


def validate_service_name(service: str) -> tuple[bool, str]:
    """Validate and normalize AWS service name."""
    if not service:
        return False, ""

    normalized = service.replace(" ", "").replace("-", "_").upper()

    if normalized in VALID_AWS_SERVICES:
        return True, normalized

    service_mappings = {
        "ELASTIC_BEANSTALK": "ELASTICBEANSTALK",
        "ELASTIC_LOAD_BALANCING": "ELASTICLOADBALANCING",
        "ELASTIC_LOAD_BALANCER": "ELASTICLOADBALANCING",
        "ELB": "ELASTICLOADBALANCING",
        "ELASTIC_CACHE": "ELASTICCACHE",
        "ELASTIC_SEARCH": "ELASTICSEARCH",
        "DYNAMO": "DYNAMODB",
        "DYNAMO_DB": "DYNAMODB",
    }

    if normalized in service_mappings:
        return True, service_mappings[normalized]

    matches = difflib.get_close_matches(normalized, VALID_AWS_SERVICES, n=1, cutoff=0.6)
    if matches:
        return False, matches[0]

    return False, ""


def format_timestamp(timestamp) -> str:
    """Format a timestamp into a readable string."""
    if not timestamp:
        return "Not specified"
    return timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")


def format_event(event: dict, description: str, affected_accounts: list[str] | None = None) -> str:
    """Format a single health event into markdown."""
    start_time = event.get("startTime")
    end_time = event.get("endTime")
    last_updated = event.get("lastUpdatedTime")
    service = event.get("service", "Unknown")
    status = event.get("statusCode", "unknown").upper()
    region = event.get("region", "global")

    lines = [
        f"## {service} — {event.get('eventTypeCode', 'Unknown')}",
        "",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| Status | {status} |",
        f"| Region | {region} |",
        f"| Start | {format_timestamp(start_time)} |",
        f"| End | {format_timestamp(end_time)} |",
    ]

    if last_updated:
        lines.append(f"| Last Updated | {format_timestamp(last_updated)} |")

    category = event.get("eventTypeCategory")
    if category:
        lines.append(f"| Category | {category} |")

    scope = event.get("eventScopeCode")
    if scope:
        lines.append(f"| Scope | {scope} |")

    lines.append("")
    lines.append(description)

    if affected_accounts is not None:
        lines.append("")
        lines.append(f"**Affected Accounts ({len(affected_accounts)}):**")
        if affected_accounts:
            for acc in affected_accounts[:20]:
                lines.append(f"- {acc}")
            if len(affected_accounts) > 20:
                lines.append(f"- ... and {len(affected_accounts) - 20} more")
        else:
            lines.append("- None")

    return "\n".join(lines)


def format_entity(entity: dict) -> str:
    """Format a single affected entity."""
    value = entity.get("entityValue", "Unknown")
    last_updated = entity.get("lastUpdatedTime")
    suffix = f" (updated: {format_timestamp(last_updated)})" if last_updated else ""
    return f"- {value}{suffix}"


async def format_events_batch(
    events: list[dict], client: "HealthClient", include_accounts: bool = False
) -> str:
    """Format a batch of events, fetching descriptions in batched API calls."""
    if not events:
        return "No events found."

    arns = [e.get("arn", "") for e in events]
    valid_arns = [a for a in arns if a]

    # Single batched call for all descriptions (10 ARNs per API call)
    descriptions = await client.get_event_descriptions_batched(valid_arns)

    # Fetch accounts in parallel if needed
    accounts_map: dict[str, list[str]] = {}
    if include_accounts:
        account_results = await asyncio.gather(
            *[client.get_affected_accounts(arn) for arn in valid_arns]
        )
        accounts_map = dict(zip(valid_arns, account_results))

    formatted = []
    for event in events:
        arn = event.get("arn", "")
        desc = descriptions.get(arn, "No description available")
        accounts = accounts_map.get(arn) if include_accounts else None
        formatted.append(format_event(event, desc, accounts))

    return "\n\n---\n\n".join(formatted)
