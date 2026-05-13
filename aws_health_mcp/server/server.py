"""Main MCP server implementation for AWS Health API."""

import asyncio

from botocore.exceptions import ClientError
from mcp.server.fastmcp import FastMCP

from .client import health_client
from .consts import VALID_AWS_SERVICES
from .formatters import (
    format_entity,
    format_event,
    format_events_batch,
    format_timestamp,
    validate_service_name,
)

mcp = FastMCP("aws-health")


@mcp.tool()
async def get_service_health() -> str:
    """Get current AWS service health events.

    Returns active and upcoming AWS health events with descriptions and timelines.

    Example prompts:
    - "Show me all current AWS service health issues"
    - "What's the current status of AWS services?"
    - "Are there any active AWS service disruptions?"
    """
    try:
        events = await health_client.paginate(
            "describe_events", filter={"eventStatusCodes": ["open", "upcoming"]}
        )
        if not events:
            return "No active AWS health events found."
        return await format_events_batch(events, health_client)
    except Exception as e:
        return f"Error fetching AWS health events: {str(e)}"


@mcp.tool()
async def get_affected_entities() -> str:
    """Get affected entities for all open AWS health events.

    Shows resources impacted by active health events, grouped by event and status.

    Example prompts:
    - "What resources are affected by current AWS issues?"
    - "Show me all impacted AWS entities"
    - "Which AWS resources are experiencing problems?"
    """
    try:
        events = await health_client.paginate(
            "describe_events", filter={"eventStatusCodes": ["open"]}
        )
        if not events:
            return "No open health events found."

        sections = []
        for event in events:
            event_arn = event["arn"]
            desc = await health_client.get_event_description(event_arn)

            entities = await health_client.paginate(
                "describe_affected_entities", filter={"eventArns": [event_arn]}
            )
            if not entities:
                continue

            status_count: dict[str, int] = {}
            entities_by_status: dict[str, list] = {}
            for entity in entities:
                status = entity.get("statusCode", "Unknown")
                status_count[status] = status_count.get(status, 0) + 1
                entities_by_status.setdefault(status, []).append(entity)

            header = format_event(event, desc)
            lines = [header, "", "**Affected Entities:**", ""]
            lines.append(
                "Summary: "
                + ", ".join(f"{s}: {c}" for s, c in status_count.items())
            )
            for status, status_entities in entities_by_status.items():
                lines.append(f"\n### {status.upper()} ({len(status_entities)})")
                for entity in status_entities:
                    lines.append(format_entity(entity))

            sections.append("\n".join(lines))

        if not sections:
            return "No affected entities found for any open events."
        return "\n\n---\n\n".join(sections)

    except Exception as e:
        return f"Error fetching affected entities: {str(e)}"


@mcp.tool()
async def get_service_events(service: str) -> str:
    """Get health events for a specific AWS service.

    Args:
        service: The AWS service name (e.g., 'EC2', 'RDS', 'LAMBDA'). Case insensitive.

    Example prompts:
    - "What's happening with EC2 right now?"
    - "Show me all RDS issues"
    - "Are there any problems with S3?"
    """
    try:
        has_access, error_message = await health_client.check_health_api_access()
        if not has_access:
            return f"Cannot fetch health events: {error_message}"

        is_valid, normalized_service = validate_service_name(service)
        if not is_valid:
            suggestion = f"\nDid you mean '{normalized_service}'?" if normalized_service else ""
            return f"Invalid service name: {service}.{suggestion}\nValid examples: {', '.join(VALID_AWS_SERVICES[:5])}"

        events = await health_client.paginate(
            "describe_events",
            filter={"eventStatusCodes": ["open", "upcoming"], "services": [normalized_service]},
        )
        if not events:
            return f"No active health events found for service: {normalized_service}"
        return await format_events_batch(events, health_client)

    except ClientError as e:
        code = e.response["Error"]["Code"]
        msg = e.response["Error"]["Message"]
        return f"AWS Health API error: {code} - {msg}"
    except Exception as e:
        return f"Error fetching AWS health events: {str(e)}"


@mcp.tool()
async def get_completed_events(service: str | None = None) -> str:
    """Get completed/closed health events.

    Args:
        service: Optional. The AWS service name to filter by. Case insensitive.

    Example prompts:
    - "Show me recently resolved AWS issues"
    - "What EC2 problems were fixed?"
    - "Get history of resolved incidents"
    """
    try:
        has_access, error_message = await health_client.check_health_api_access()
        if not has_access:
            return f"Cannot fetch completed events: {error_message}"

        filter_params: dict = {"eventStatusCodes": ["closed"]}
        normalized_service = None

        if service:
            is_valid, normalized_service = validate_service_name(service)
            if not is_valid:
                suggestion = f"\nDid you mean '{normalized_service}'?" if normalized_service else ""
                return f"Invalid service name: {service}.{suggestion}\nValid examples: {', '.join(VALID_AWS_SERVICES[:5])}"
            filter_params["services"] = [normalized_service]

        events = await health_client.paginate("describe_events", filter=filter_params)
        if not events:
            svc = f" for service: {normalized_service}" if normalized_service else ""
            return f"No completed health events found{svc}."
        return await format_events_batch(events, health_client)

    except ClientError as e:
        code = e.response["Error"]["Code"]
        msg = e.response["Error"]["Message"]
        return f"AWS Health API error: {code} - {msg}"
    except Exception as e:
        return f"Error fetching completed events: {str(e)}"


@mcp.tool()
async def get_scheduled_changes() -> str:
    """Get all scheduled changes/maintenance events across AWS services.

    Returns upcoming maintenance windows, planned updates, and infrastructure improvements.

    Example prompts:
    - "What maintenance is planned for AWS services?"
    - "Show me upcoming AWS changes"
    - "When is the next AWS maintenance?"
    """
    try:
        events = await health_client.paginate(
            "describe_events",
            filter={
                "eventTypeCategories": ["scheduledChange"],
                "eventStatusCodes": ["open", "upcoming"],
            },
        )
        if not events:
            return "No scheduled changes found."

        service_groups: dict[str, list] = {}
        for event in events:
            svc = event.get("service", "Unknown")
            service_groups.setdefault(svc, []).append(event)

        sections = []
        for svc, svc_events in sorted(service_groups.items()):
            header = f"# {svc} ({len(svc_events)} scheduled)\n"
            formatted = await format_events_batch(svc_events, health_client)
            sections.append(header + formatted)

        return "\n\n---\n\n".join(sections)

    except Exception as e:
        return f"Error fetching scheduled AWS changes: {str(e)}"


@mcp.tool()
async def get_org_health_events(
    service: str | None = None, account_id: str | None = None, status: str = "active"
) -> str:
    """Get health events across your AWS Organization.

    If no arguments are provided, returns all active org health events.

    Args:
        service: Optional. The AWS service name to filter by. Case insensitive.
        account_id: Optional. The AWS account ID to filter events for.
        status: Optional. 'active' (default) or 'closed'.

    Example prompts:
    - "Show me org-wide AWS health events"
    - "What issues affect account 123456789012?"
    - "Get closed org health events for RDS"
    """
    try:
        has_access, error_message = await health_client.check_org_health_access()
        if not has_access:
            return f"Cannot fetch organization events: {error_message}"

        if status.lower() == "active":
            status_codes = ["open", "upcoming"]
        elif status.lower() == "closed":
            status_codes = ["closed"]
        else:
            return "Invalid status. Please use 'active' or 'closed'."

        filter_params: dict = {"eventStatusCodes": status_codes}
        normalized_service = None

        if service:
            is_valid, normalized_service = validate_service_name(service)
            if not is_valid:
                suggestion = f"\nDid you mean '{normalized_service}'?" if normalized_service else ""
                return f"Invalid service name: {service}.{suggestion}\nValid examples: {', '.join(VALID_AWS_SERVICES[:5])}"
            filter_params["services"] = [normalized_service]

        events = await health_client.paginate(
            "describe_events_for_organization", filter=filter_params
        )
        if not events:
            return "No organization health events found."

        if account_id:
            async def _is_affected(event: dict) -> bool:
                accounts = await health_client.get_affected_accounts(event["arn"])
                return account_id in accounts

            checks = await asyncio.gather(*[_is_affected(e) for e in events])
            events = [e for e, affected in zip(events, checks) if affected]
            if not events:
                return f"No organization health events found for account {account_id}."

        return await format_events_batch(events, health_client, include_accounts=True)

    except ClientError as e:
        code = e.response["Error"]["Code"]
        msg = e.response["Error"]["Message"]
        return f"AWS Organizations Health API error: {code} - {msg}"
    except Exception as e:
        return f"Error fetching organization health events: {str(e)}"


@mcp.tool()
async def get_org_service_health() -> str:
    """Get current AWS service health events across your organization.

    Provides a comprehensive overview of active health events across all accounts
    in your AWS Organization.

    Example prompts:
    - "Show me all current AWS service health issues across my organization"
    - "Are there any active AWS service disruptions affecting multiple accounts?"
    """
    try:
        has_access, error_message = await health_client.check_org_health_access()
        if not has_access:
            return f"Cannot fetch organization events: {error_message}"

        events = await health_client.paginate(
            "describe_events_for_organization",
            filter={"eventStatusCodes": ["open", "upcoming"]},
        )
        if not events:
            return "No active AWS organization health events found."
        return await format_events_batch(events, health_client, include_accounts=True)

    except Exception as e:
        return f"Error fetching organization health events: {str(e)}"


@mcp.tool()
async def get_org_affected_entities(
    account_id: str | None = None, event_arn: str | None = None
) -> str:
    """Get affected entities for AWS health events across your organization.

    Args:
        account_id: Optional. The AWS account ID to filter events for.
        event_arn: Optional. The ARN of a specific event to get details for.

    Example prompts:
    - "What resources are affected by current AWS issues across my organization?"
    - "Show me impacted entities in account 123456789012"
    """
    try:
        has_access, error_message = await health_client.check_org_health_access()
        if not has_access:
            return f"Cannot fetch organization events: {error_message}"

        if event_arn:
            try:
                response = await health_client.call(
                    "describe_event_details_for_organization",
                    organizationEventDetailFilters=[{"eventArn": event_arn}],
                )
                if "successfulSet" in response and response["successfulSet"]:
                    events = [response["successfulSet"][0]["event"]]
                else:
                    return f"No event found with ARN: {event_arn}"
            except ClientError as e:
                return f"AWS Organizations Health API error: {e.response['Error']['Code']} - {e.response['Error']['Message']}"
        else:
            events = await health_client.paginate(
                "describe_events_for_organization",
                filter={"eventStatusCodes": ["open"]},
            )

        if not events:
            return "No open health events found in your organization."

        sections = []
        for event in events:
            evt_arn = event["arn"]
            desc = await health_client.get_event_description(evt_arn)
            affected_accounts = await health_client.get_affected_accounts(evt_arn)

            if account_id and account_id not in affected_accounts:
                continue

            target_accounts = [account_id] if account_id else affected_accounts
            if not target_accounts:
                continue

            header = format_event(event, desc, affected_accounts)
            entity_lines = [header, "", "**Affected Entities:**"]

            account_entities = await health_client.get_org_entities_batched(evt_arn, target_accounts)

            for acc, entities in account_entities.items():
                if not entities:
                    continue

                entity_lines.append(f"\n### Account: {acc}")
                entities_by_status: dict[str, list] = {}
                for entity in entities:
                    s = entity.get("statusCode", "Unknown")
                    entities_by_status.setdefault(s, []).append(entity)

                for s, s_entities in entities_by_status.items():
                    entity_lines.append(f"\n**{s.upper()} ({len(s_entities)}):**")
                    for entity in s_entities[:20]:
                        entity_lines.append(format_entity(entity))
                    if len(s_entities) > 20:
                        entity_lines.append(f"- ... and {len(s_entities) - 20} more")

            sections.append("\n".join(entity_lines))

        if not sections:
            acct_msg = f" for account {account_id}" if account_id else ""
            return f"No affected entities found{acct_msg}."
        return "\n\n---\n\n".join(sections)

    except Exception as e:
        return f"Error fetching organization affected entities: {str(e)}"


@mcp.tool()
async def get_org_service_events(service: str) -> str:
    """Get health events for a specific AWS service across your organization.

    Args:
        service: The AWS service name (e.g., 'EC2', 'RDS', 'LAMBDA'). Case insensitive.

    Example prompts:
    - "What's happening with EC2 across my organization?"
    - "Show me all RDS issues affecting my AWS accounts"
    """
    try:
        has_access, error_message = await health_client.check_org_health_access()
        if not has_access:
            return f"Cannot fetch organization events: {error_message}"

        is_valid, normalized_service = validate_service_name(service)
        if not is_valid:
            suggestion = f"\nDid you mean '{normalized_service}'?" if normalized_service else ""
            return f"Invalid service name: {service}.{suggestion}\nValid examples: {', '.join(VALID_AWS_SERVICES[:5])}"

        events = await health_client.paginate(
            "describe_events_for_organization",
            filter={"eventStatusCodes": ["open", "upcoming"], "services": [normalized_service]},
        )
        if not events:
            return f"No active health events for {normalized_service} across your organization."
        return await format_events_batch(events, health_client, include_accounts=True)

    except ClientError as e:
        code = e.response["Error"]["Code"]
        msg = e.response["Error"]["Message"]
        return f"AWS Organizations Health API error: {code} - {msg}"
    except Exception as e:
        return f"Error fetching organization service events: {str(e)}"


@mcp.tool()
async def get_org_account_events(account_id: str) -> str:
    """Get health events for a specific AWS account in your organization.

    Args:
        account_id: The 12-digit AWS account ID.

    Example prompts:
    - "What health events are affecting account 123456789012?"
    - "Show me all issues in my account"
    """
    try:
        has_access, error_message = await health_client.check_org_health_access()
        if not has_access:
            return f"Cannot fetch organization events: {error_message}"

        if not account_id.isdigit() or len(account_id) != 12:
            return f"Invalid account ID: {account_id}. Must be a 12-digit number."

        events = await health_client.paginate(
            "describe_events_for_organization",
            filter={"eventStatusCodes": ["open", "upcoming"]},
        )
        if not events:
            return "No active health events found across your organization."

        async def _is_affected(event: dict) -> bool:
            accounts = await health_client.get_affected_accounts(event["arn"])
            return account_id in accounts

        checks = await asyncio.gather(*[_is_affected(e) for e in events])
        account_events = [e for e, affected in zip(events, checks) if affected]

        if not account_events:
            return f"No active health events found for account {account_id}."

        sections = []
        for event in account_events:
            evt_arn = event["arn"]
            desc = await health_client.get_event_description(evt_arn)
            accounts = await health_client.get_affected_accounts(evt_arn)

            try:
                entities = await health_client.paginate(
                    "describe_affected_entities_for_organization",
                    organizationEntityFilters=[{"eventArn": evt_arn, "awsAccountId": account_id}],
                )
            except Exception:
                entities = []

            header = format_event(event, desc)
            lines = [header]
            lines.append(f"\nThis account is one of {len(accounts)} affected accounts.")

            if entities:
                entities_by_status: dict[str, list] = {}
                for entity in entities:
                    s = entity.get("statusCode", "Unknown")
                    entities_by_status.setdefault(s, []).append(entity)

                lines.append("\n**Affected Resources:**")
                for s, s_entities in entities_by_status.items():
                    lines.append(f"\n### {s.upper()} ({len(s_entities)})")
                    for entity in s_entities[:15]:
                        lines.append(format_entity(entity))
                    if len(s_entities) > 15:
                        lines.append(f"- ... and {len(s_entities) - 15} more")
            else:
                lines.append("\nNo specific resources identified for this account.")

            sections.append("\n".join(lines))

        return "\n\n---\n\n".join(sections)

    except Exception as e:
        return f"Error fetching account health events: {str(e)}"


@mcp.tool()
async def get_org_scheduled_changes() -> str:
    """Get scheduled changes/maintenance events across your AWS Organization.

    Returns upcoming maintenance affecting accounts in your organization.

    Example prompts:
    - "What maintenance is planned across my organization?"
    - "Show me upcoming AWS changes affecting my accounts"
    """
    try:
        has_access, error_message = await health_client.check_org_health_access()
        if not has_access:
            return f"Cannot fetch organization events: {error_message}"

        events = await health_client.paginate(
            "describe_events_for_organization",
            filter={
                "eventTypeCategories": ["scheduledChange"],
                "eventStatusCodes": ["open", "upcoming"],
            },
        )
        if not events:
            return "No scheduled changes found across your organization."

        service_groups: dict[str, list] = {}
        for event in events:
            svc = event.get("service", "Unknown")
            service_groups.setdefault(svc, []).append(event)

        sections = []
        for svc, svc_events in sorted(service_groups.items()):
            header = f"# {svc} ({len(svc_events)} scheduled)\n"
            formatted = await format_events_batch(svc_events, health_client, include_accounts=True)
            sections.append(header + formatted)

        return "\n\n---\n\n".join(sections)

    except Exception as e:
        return f"Error fetching organization scheduled changes: {str(e)}"


def run_server():
    """Run the MCP server."""
    mcp.run(transport="stdio")
