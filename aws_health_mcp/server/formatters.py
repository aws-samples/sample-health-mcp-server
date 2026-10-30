"""Formatting utilities for AWS Health events and data."""

import asyncio
import difflib
import re
from typing import TYPE_CHECKING, Iterable, Optional

from .client import last_updated_by_arn
from .consts import SERVICE_ALIASES

if TYPE_CHECKING:
    from .client import HealthClient

# A suggestion is only worth showing if it is close enough to be a plausible
# typo. The previous 0.6 produced actively misleading advice -- "CloudTrail"
# was answered with "did you mean CLOUDFORMATION?" (ratio 0.58), a different
# service entirely.
_SUGGESTION_CUTOFF = 0.85


def compress_service_name(service: str) -> str:
    """Reduce a service name to a canonical comparison key.

    Uppercases and strips every non-alphanumeric character, so "Kinesis Video",
    "kinesis-video" and "KINESIS_VIDEO" all collapse to "KINESISVIDEO". This is
    collision-free across the AWS Health service codes.
    """
    return re.sub(r"[^A-Z0-9]", "", service.upper())


def service_candidates(service: str) -> list[str]:
    """Plausible Health service codes for a user-supplied name, most likely first.

    Used to confirm a name with a cheap API probe before falling back to the full
    service list: the alias target, the name with separators as underscores
    ("Kinesis Video" -> KINESIS_VIDEO), and the fully compressed form
    ("API Gateway" -> APIGATEWAY).
    """
    compressed = compress_service_name(service)
    if not compressed:
        return []
    candidates = [
        SERVICE_ALIASES.get(compressed),
        re.sub(r"[^A-Z0-9]+", "_", service.upper()).strip("_"),
        compressed,
    ]
    return list(dict.fromkeys(c for c in candidates if c))


def validate_service_name(
    service: str, known_services: Optional[Iterable[str]] = None
) -> tuple[bool, str]:
    """Resolve a user-supplied service name to a real AWS Health service code.

    Args:
        service: The name as the caller typed it.
        known_services: Authoritative service codes from ``DescribeEventTypes``.
            When omitted (the API was unreachable) the name is normalized but
            *accepted* rather than rejected -- letting AWS answer is better than
            claiming a real service does not exist.

    Returns:
        ``(True, service_code)`` when resolved, otherwise ``(False, suggestion)``
        where ``suggestion`` is a close real service code or ``""`` if there is
        no plausible match.
    """
    if not service or not service.strip():
        return False, ""

    compressed = compress_service_name(service)
    if not compressed:
        return False, ""

    if known_services is None:
        # Offline/degraded mode: normalize what we can, then defer to the API.
        return True, SERVICE_ALIASES.get(compressed, service.strip().upper())

    # Map each real code by its compressed form so spelling and separator
    # differences resolve without needing an alias entry.
    by_compressed = {compress_service_name(code): code for code in known_services}

    aliased = SERVICE_ALIASES.get(compressed)
    if aliased and compress_service_name(aliased) in by_compressed:
        return True, by_compressed[compress_service_name(aliased)]

    if compressed in by_compressed:
        return True, by_compressed[compressed]

    matches = difflib.get_close_matches(
        compressed, list(by_compressed), n=1, cutoff=_SUGGESTION_CUTOFF
    )
    if matches:
        return False, by_compressed[matches[0]]

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


def format_warnings(warnings: list[str]) -> str:
    """Footer for output built from partial data; empty when every lookup succeeded."""
    if not warnings:
        return ""
    unique = list(dict.fromkeys(warnings))
    lines = [
        "",
        "---",
        "**Warning: partial results.** Some lookups failed, so the above may be incomplete:",
    ]
    lines.extend(f"- {w}" for w in unique[:5])
    if len(unique) > 5:
        lines.append(f"- ... and {len(unique) - 5} more")
    return "\n\n" + "\n".join(lines)


async def format_events_batch(
    events: list[dict], client: "HealthClient", include_accounts: bool = False
) -> str:
    """Format a batch of events, fetching descriptions in batched API calls."""
    if not events:
        return "No events found."

    arns = [e.get("arn", "") for e in events]
    valid_arns = [a for a in arns if a]

    # Single batched call for all descriptions (10 ARNs per API call)
    warnings: list[str] = []
    descriptions = await client.get_event_descriptions_batched(
        valid_arns, last_updated_by_arn(events), warnings
    )

    # Fetch accounts in parallel if needed
    accounts_map: dict[str, list[str]] = {}
    if include_accounts:
        account_results = await asyncio.gather(
            *[client.get_affected_accounts(arn, warnings) for arn in valid_arns]
        )
        accounts_map = dict(zip(valid_arns, account_results))

    formatted = []
    for event in events:
        arn = event.get("arn", "")
        desc = descriptions.get(arn, "No description available")
        accounts = accounts_map.get(arn) if include_accounts else None
        formatted.append(format_event(event, desc, accounts))

    return "\n\n---\n\n".join(formatted) + format_warnings(warnings)
