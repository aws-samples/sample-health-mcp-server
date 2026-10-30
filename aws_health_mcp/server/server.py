"""Main MCP server implementation for AWS Health API."""

from datetime import datetime, timezone

from botocore.exceptions import ClientError
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations

from .client import health_client, last_updated_by_arn, record_failure
from .formatters import (
    format_entity,
    format_event,
    format_events_batch,
    format_timestamp,
    format_warnings,
    service_candidates,
    validate_service_name,
)

mcp = FastMCP("aws-health")

# Every tool here only ever reads. AWS Health's two mutating operations
# (Enable/DisableHealthServiceAccessForOrganization) are deliberately not
# exposed: org-wide Health access is not configuration an agent should toggle.
_READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=True,
)


async def _resolve_service(service: str) -> tuple[str | None, str]:
    """Resolve a service name against the live AWS Health service list.

    Returns ``(service_code, "")`` on success, or ``(None, error_message)`` with
    a message that suggests a real alternative where one plausibly exists.
    """
    # Scanning every event type to build the full list can take several seconds
    # on a cold start. Common names are confirmed with a single cheap probe first;
    # the full list is only needed for names that don't resolve that way (typos,
    # unusual spellings) so a suggestion can be offered.
    if health_client.cached_services() is None:
        confirmed = await health_client.confirm_service(service_candidates(service))
        if confirmed:
            return confirmed, ""

    known = await health_client.get_known_services()
    is_valid, resolved = validate_service_name(service, known)
    if is_valid:
        return resolved, ""

    if resolved:
        return None, f"Unknown AWS service: {service}. Did you mean '{resolved}'?"
    hint = (
        " Use list_event_types to see the services AWS Health covers."
        if known
        else " Could not reach AWS Health to list valid services."
    )
    return None, f"Unknown AWS service: {service}.{hint}"


def _apply_filters(filter_params: dict, regions: list[str] | None = None) -> dict:
    """Add optional region scoping to a Health API event filter.

    Only ``regions`` is applied here. EventFilter also accepts ``tags`` and
    ``entityValues``, but neither behaves as a caller would expect on
    DescribeEvents: ``tags`` is ignored outright, and ``entityValues`` also
    matches events that have no entities, so a resource ID that exists nowhere
    still returns events. Resource scoping is done in find_events_for_resources,
    which filters through DescribeAffectedEntities where the match is exact.
    """
    if regions:
        filter_params["regions"] = regions
    return filter_params


@mcp.tool(annotations=_READ_ONLY)
async def get_service_health(regions: list[str] | None = None) -> str:
    """Get current AWS service health events.

    Returns active and upcoming AWS health events with descriptions and timelines.
    Consider summarize_health_events first: this returns full descriptions and
    can be very large on a busy account.

    Args:
        regions: Optional. Restrict to these AWS regions, e.g. ['us-west-2'].

    Example prompts:
    - "Show me all current AWS service health issues"
    - "What's broken in us-west-2?"
    - "Are there any active AWS service disruptions?"
    """
    try:
        filter_params = _apply_filters({"eventStatusCodes": ["open", "upcoming"]}, regions)
        events = await health_client.paginate("describe_events", filter=filter_params)
        if not events:
            return "No active AWS health events found."
        return await format_events_batch(events, health_client)
    except ToolError:
        raise
    except Exception as e:
        raise ToolError(f"Error fetching AWS health events: {str(e)}") from e


@mcp.tool(annotations=_READ_ONLY)
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
        warnings: list[str] = []
        for event in events:
            event_arn = event["arn"]
            desc = await health_client.get_event_description(
                event_arn, event.get("lastUpdatedTime"), warnings
            )

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
            lines.append("Summary: " + ", ".join(f"{s}: {c}" for s, c in status_count.items()))
            for status, status_entities in entities_by_status.items():
                lines.append(f"\n### {status.upper()} ({len(status_entities)})")
                for entity in status_entities:
                    lines.append(format_entity(entity))

            sections.append("\n".join(lines))

        if not sections:
            return "No affected entities found for any open events." + format_warnings(warnings)
        return "\n\n---\n\n".join(sections) + format_warnings(warnings)

    except ToolError:
        raise
    except Exception as e:
        raise ToolError(f"Error fetching affected entities: {str(e)}") from e


@mcp.tool(annotations=_READ_ONLY)
async def get_service_events(service: str, regions: list[str] | None = None) -> str:
    """Get health events for a specific AWS service.

    Args:
        service: The AWS service name (e.g., 'EC2', 'RDS', 'LAMBDA'). Case insensitive.
            Use list_event_types to discover the codes AWS Health uses.
        regions: Optional. Restrict to these AWS regions, e.g. ['us-west-2'].

    Example prompts:
    - "What's happening with EC2 right now?"
    - "Any RDS issues in eu-west-1?"
    - "Are there any problems with S3?"
    """
    try:
        has_access, error_message = await health_client.check_health_api_access()
        if not has_access:
            raise ToolError(f"Cannot fetch health events: {error_message}")

        normalized_service, error = await _resolve_service(service)
        if not normalized_service:
            return error

        filter_params = _apply_filters(
            {"eventStatusCodes": ["open", "upcoming"], "services": [normalized_service]},
            regions,
        )
        events = await health_client.paginate("describe_events", filter=filter_params)
        if not events:
            return f"No active health events found for service: {normalized_service}"
        return await format_events_batch(events, health_client)

    except ToolError:
        raise
    except ClientError as e:
        code = e.response["Error"]["Code"]
        msg = e.response["Error"]["Message"]
        raise ToolError(f"AWS Health API error: {code} - {msg}") from e
    except Exception as e:
        raise ToolError(f"Error fetching AWS health events: {str(e)}") from e


@mcp.tool(annotations=_READ_ONLY)
async def get_completed_events(service: str | None = None, regions: list[str] | None = None) -> str:
    """Get completed/closed health events.

    Args:
        service: Optional. The AWS service name to filter by. Case insensitive.
        regions: Optional. Restrict to these AWS regions, e.g. ['us-west-2'].

    Example prompts:
    - "Show me recently resolved AWS issues"
    - "What EC2 problems were fixed in us-east-1?"
    - "Get history of resolved incidents"
    """
    try:
        has_access, error_message = await health_client.check_health_api_access()
        if not has_access:
            raise ToolError(f"Cannot fetch completed events: {error_message}")

        filter_params: dict = {"eventStatusCodes": ["closed"]}
        normalized_service = None

        if service:
            normalized_service, error = await _resolve_service(service)
            if not normalized_service:
                return error
            filter_params["services"] = [normalized_service]

        _apply_filters(filter_params, regions)
        events = await health_client.paginate("describe_events", filter=filter_params)
        if not events:
            svc = f" for service: {normalized_service}" if normalized_service else ""
            return f"No completed health events found{svc}."
        return await format_events_batch(events, health_client)

    except ToolError:
        raise
    except ClientError as e:
        code = e.response["Error"]["Code"]
        msg = e.response["Error"]["Message"]
        raise ToolError(f"AWS Health API error: {code} - {msg}") from e
    except Exception as e:
        raise ToolError(f"Error fetching completed events: {str(e)}") from e


@mcp.tool(annotations=_READ_ONLY)
async def get_scheduled_changes(regions: list[str] | None = None) -> str:
    """Get all scheduled changes/maintenance events across AWS services.

    Returns upcoming maintenance windows, planned updates, and infrastructure improvements.

    Args:
        regions: Optional. Restrict to these AWS regions, e.g. ['us-west-2'].

    Example prompts:
    - "What maintenance is planned for AWS services?"
    - "Any upcoming maintenance in eu-west-1?"
    - "When is the next AWS maintenance?"
    """
    try:
        filter_params = _apply_filters(
            {
                "eventTypeCategories": ["scheduledChange"],
                "eventStatusCodes": ["open", "upcoming"],
            },
            regions,
        )
        events = await health_client.paginate("describe_events", filter=filter_params)
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

    except ToolError:
        raise
    except Exception as e:
        raise ToolError(f"Error fetching scheduled AWS changes: {str(e)}") from e


@mcp.tool(annotations=_READ_ONLY)
async def get_org_health_events(
    service: str | None = None,
    account_id: str | None = None,
    status: str = "active",
    regions: list[str] | None = None,
) -> str:
    """Get health events across your AWS Organization.

    If no arguments are provided, returns all active org health events.

    Args:
        service: Optional. The AWS service name to filter by. Case insensitive.
        account_id: Optional. The AWS account ID to filter events for.
        status: Optional. 'active' (default) or 'closed'.
        regions: Optional. Restrict to these AWS regions, e.g. ['us-west-2'].

    Example prompts:
    - "Show me org-wide AWS health events"
    - "What issues affect account 123456789012?"
    - "Any org-wide events in ap-southeast-2?"
    """
    try:
        has_access, error_message = await health_client.check_org_health_access()
        if not has_access:
            raise ToolError(f"Cannot fetch organization events: {error_message}")

        if status.lower() == "active":
            status_codes = ["open", "upcoming"]
        elif status.lower() == "closed":
            status_codes = ["closed"]
        else:
            return "Invalid status. Please use 'active' or 'closed'."

        filter_params: dict = {"eventStatusCodes": status_codes}
        normalized_service = None

        if service:
            normalized_service, error = await _resolve_service(service)
            if not normalized_service:
                return error
            filter_params["services"] = [normalized_service]

        if account_id:
            if not account_id.isdigit() or len(account_id) != 12:
                return f"Invalid account ID: {account_id}. Must be a 12-digit number."
            # OrganizationEventFilter supports awsAccountIds, so AWS filters
            # server-side. Previously this fetched every org event and then made
            # one DescribeAffectedAccountsForOrganization call per event.
            filter_params["awsAccountIds"] = [account_id]

        _apply_filters(filter_params, regions)
        events = await health_client.paginate(
            "describe_events_for_organization", filter=filter_params
        )
        if not events:
            if account_id:
                return f"No organization health events found for account {account_id}."
            return "No organization health events found."

        return await format_events_batch(events, health_client, include_accounts=True)

    except ToolError:
        raise
    except ClientError as e:
        code = e.response["Error"]["Code"]
        msg = e.response["Error"]["Message"]
        raise ToolError(f"AWS Organizations Health API error: {code} - {msg}") from e
    except Exception as e:
        raise ToolError(f"Error fetching organization health events: {str(e)}") from e


@mcp.tool(annotations=_READ_ONLY)
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
            raise ToolError(f"Cannot fetch organization events: {error_message}")

        events = await health_client.paginate(
            "describe_events_for_organization",
            filter={"eventStatusCodes": ["open", "upcoming"]},
        )
        if not events:
            return "No active AWS organization health events found."
        return await format_events_batch(events, health_client, include_accounts=True)

    except ToolError:
        raise
    except Exception as e:
        raise ToolError(f"Error fetching organization health events: {str(e)}") from e


@mcp.tool(annotations=_READ_ONLY)
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
            raise ToolError(f"Cannot fetch organization events: {error_message}")

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
                raise ToolError(
                    f"AWS Organizations Health API error: {e.response['Error']['Code']} - {e.response['Error']['Message']}"
                ) from e
        else:
            events = await health_client.paginate(
                "describe_events_for_organization",
                filter={"eventStatusCodes": ["open"]},
            )

        if not events:
            return "No open health events found in your organization."

        sections = []
        warnings: list[str] = []
        for event in events:
            evt_arn = event["arn"]
            desc = await health_client.get_event_description(
                evt_arn, event.get("lastUpdatedTime"), warnings
            )
            affected_accounts = await health_client.get_affected_accounts(evt_arn, warnings)

            if account_id and account_id not in affected_accounts:
                continue

            target_accounts = [account_id] if account_id else affected_accounts
            if not target_accounts:
                continue

            header = format_event(event, desc, affected_accounts)
            entity_lines = [header, "", "**Affected Entities:**"]

            account_entities = await health_client.get_org_entities_batched(
                evt_arn, target_accounts, warnings
            )

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
            return f"No affected entities found{acct_msg}." + format_warnings(warnings)
        return "\n\n---\n\n".join(sections) + format_warnings(warnings)

    except ToolError:
        raise
    except Exception as e:
        raise ToolError(f"Error fetching organization affected entities: {str(e)}") from e


@mcp.tool(annotations=_READ_ONLY)
async def get_org_service_events(service: str, regions: list[str] | None = None) -> str:
    """Get health events for a specific AWS service across your organization.

    Args:
        service: The AWS service name (e.g., 'EC2', 'RDS', 'LAMBDA'). Case insensitive.
        regions: Optional. Restrict to these AWS regions, e.g. ['us-west-2'].

    Example prompts:
    - "What's happening with EC2 across my organization?"
    - "Show me all RDS issues affecting my AWS accounts"
    """
    try:
        has_access, error_message = await health_client.check_org_health_access()
        if not has_access:
            raise ToolError(f"Cannot fetch organization events: {error_message}")

        normalized_service, error = await _resolve_service(service)
        if not normalized_service:
            return error

        filter_params = _apply_filters(
            {"eventStatusCodes": ["open", "upcoming"], "services": [normalized_service]},
            regions,
        )
        events = await health_client.paginate(
            "describe_events_for_organization", filter=filter_params
        )
        if not events:
            return f"No active health events for {normalized_service} across your organization."
        return await format_events_batch(events, health_client, include_accounts=True)

    except ToolError:
        raise
    except ClientError as e:
        code = e.response["Error"]["Code"]
        msg = e.response["Error"]["Message"]
        raise ToolError(f"AWS Organizations Health API error: {code} - {msg}") from e
    except Exception as e:
        raise ToolError(f"Error fetching organization service events: {str(e)}") from e


@mcp.tool(annotations=_READ_ONLY)
async def get_org_account_events(account_id: str, regions: list[str] | None = None) -> str:
    """Get health events for a specific AWS account in your organization.

    Args:
        account_id: The 12-digit AWS account ID.
        regions: Optional. Restrict to these AWS regions, e.g. ['us-west-2'].

    Example prompts:
    - "What health events are affecting account 123456789012?"
    - "Show me all issues in my account"
    """
    try:
        has_access, error_message = await health_client.check_org_health_access()
        if not has_access:
            raise ToolError(f"Cannot fetch organization events: {error_message}")

        if not account_id.isdigit() or len(account_id) != 12:
            return f"Invalid account ID: {account_id}. Must be a 12-digit number."

        # awsAccountIds filters server-side; this used to fetch every org event
        # and then call DescribeAffectedAccountsForOrganization once per event.
        filter_params = _apply_filters(
            {"eventStatusCodes": ["open", "upcoming"], "awsAccountIds": [account_id]},
            regions,
        )
        account_events = await health_client.paginate(
            "describe_events_for_organization", filter=filter_params
        )
        if not account_events:
            return f"No active health events found for account {account_id}."

        sections = []
        warnings: list[str] = []
        for event in account_events:
            evt_arn = event["arn"]
            desc = await health_client.get_event_description(
                evt_arn, event.get("lastUpdatedTime"), warnings
            )
            accounts = await health_client.get_affected_accounts(evt_arn, warnings)

            try:
                entities = await health_client.paginate(
                    "describe_affected_entities_for_organization",
                    organizationEntityFilters=[{"eventArn": evt_arn, "awsAccountId": account_id}],
                )
            except Exception as e:
                record_failure(
                    warnings, f"resources unavailable for {evt_arn} in account {account_id}", e
                )
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

        return "\n\n---\n\n".join(sections) + format_warnings(warnings)

    except ToolError:
        raise
    except Exception as e:
        raise ToolError(f"Error fetching account health events: {str(e)}") from e


@mcp.tool(annotations=_READ_ONLY)
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
            raise ToolError(f"Cannot fetch organization events: {error_message}")

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

    except ToolError:
        raise
    except Exception as e:
        raise ToolError(f"Error fetching organization scheduled changes: {str(e)}") from e


@mcp.tool(annotations=_READ_ONLY)
async def get_event_details(event_arns: list[str]) -> str:
    """Get the full detail of specific AWS health events by ARN.

    Use this to drill into events surfaced by the listing tools, instead of
    pulling every description for every event.

    Args:
        event_arns: One or more event ARNs, as returned by the listing tools.

    Example prompts:
    - "Give me the full details of that EC2 retirement event"
    - "What exactly does event arn:aws:health:... say?"
    """
    try:
        if not event_arns:
            return "No event ARNs provided."

        warnings: list[str] = []
        descriptions = await health_client.get_event_descriptions_batched(
            event_arns, None, warnings
        )

        # describe_event_details accepts up to 10 ARNs per call.
        details: dict[str, dict] = {}
        for i in range(0, len(event_arns), 10):
            batch = event_arns[i : i + 10]
            try:
                response = await health_client.call("describe_event_details", eventArns=batch)
            except ClientError as e:
                raise ToolError(
                    f"AWS Health API error: {e.response['Error']['Code']} - {e.response['Error']['Message']}"
                ) from e
            for entry in response.get("successfulSet", []):
                event = entry.get("event", {})
                if event.get("arn"):
                    details[event["arn"]] = event

        sections = []
        for arn in event_arns:
            event = details.get(arn)
            if event is None:
                sections.append(f"## {arn}\n\nNo detail available for this ARN.")
                continue
            body = format_event(event, descriptions.get(arn, "No description available"))
            sections.append(f"{body}\n\n**ARN:** `{arn}`")

        return "\n\n---\n\n".join(sections) + format_warnings(warnings)

    except ToolError:
        raise
    except Exception as e:
        raise ToolError(f"Error fetching event details: {str(e)}") from e


@mcp.tool(annotations=_READ_ONLY)
async def summarize_health_events(group_by: str = "service", include_closed: bool = False) -> str:
    """Count active AWS health events without returning their descriptions.

    A cheap overview for "is anything wrong?" questions. Listing tools return
    full descriptions and can run to tens of thousands of tokens; this returns
    counts only.

    Args:
        group_by: One of 'service', 'status', 'category' or 'region'.
        include_closed: Include resolved events as well as open/upcoming ones.

    Example prompts:
    - "How many AWS health events are open, by service?"
    - "Give me a summary of current AWS issues"
    - "Which regions have active events?"
    """
    try:
        valid_groups = ("service", "status", "category", "region")
        key = group_by.lower().strip()
        if key not in valid_groups:
            return f"Invalid group_by: {group_by}. Use one of: {', '.join(valid_groups)}."

        status_codes = ["open", "upcoming"]
        if include_closed:
            status_codes.append("closed")

        # eventTypeCategory is the only field DescribeEventAggregates supports,
        # so it is the one grouping AWS can count server-side.
        if key == "category":
            response = await health_client.call(
                "describe_event_aggregates",
                aggregateField="eventTypeCategory",
                filter={"eventStatusCodes": status_codes},
            )
            counts = {
                a.get("aggregateValue", "unknown"): a.get("count", 0)
                for a in response.get("eventAggregates", [])
            }
        else:
            events = await health_client.paginate(
                "describe_events", filter={"eventStatusCodes": status_codes}
            )
            field = {"service": "service", "status": "statusCode", "region": "region"}[key]
            counts = {}
            for event in events:
                value = event.get(field) or "unknown"
                counts[value] = counts.get(value, 0) + 1

        if not counts:
            return "No health events found."

        total = sum(counts.values())
        scope = "open, upcoming and closed" if include_closed else "open and upcoming"
        lines = [
            f"**{total} health events** ({scope}), by {key}:",
            "",
            f"| {key.capitalize()} | Events |",
            "|---|---|",
        ]
        for value, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
            lines.append(f"| {value} | {count} |")
        lines.append("")
        lines.append("Use get_event_details or the listing tools to drill into any of these.")
        return "\n".join(lines)

    except ToolError:
        raise
    except ClientError as e:
        raise ToolError(
            f"AWS Health API error: {e.response['Error']['Code']} - {e.response['Error']['Message']}"
        ) from e
    except Exception as e:
        raise ToolError(f"Error summarizing health events: {str(e)}") from e


@mcp.tool(annotations=_READ_ONLY)
async def count_affected_entities(event_arns: list[str]) -> str:
    """Count the resources affected by events, without listing them.

    Use this before the entity-listing tools when an event could touch
    thousands of resources.

    Args:
        event_arns: One or more event ARNs.

    Example prompts:
    - "How many instances does this retirement event affect?"
    - "What's the blast radius of these events?"
    """
    try:
        if not event_arns:
            return "No event ARNs provided."

        response = await health_client.call("describe_entity_aggregates", eventArns=event_arns)
        aggregates = response.get("entityAggregates", [])
        if not aggregates:
            return "No affected entities found for the given events."

        lines = ["| Event ARN | Affected entities | By status |", "|---|---|---|"]
        for aggregate in aggregates:
            statuses = aggregate.get("statuses") or {}
            breakdown = ", ".join(f"{k}: {v}" for k, v in statuses.items()) or "-"
            lines.append(
                f"| `{aggregate.get('eventArn', 'unknown')}` "
                f"| {aggregate.get('count', 0)} | {breakdown} |"
            )
        return "\n".join(lines)

    except ToolError:
        raise
    except ClientError as e:
        raise ToolError(
            f"AWS Health API error: {e.response['Error']['Code']} - {e.response['Error']['Message']}"
        ) from e
    except Exception as e:
        raise ToolError(f"Error counting affected entities: {str(e)}") from e


@mcp.tool(annotations=_READ_ONLY)
async def list_affected_accounts(event_arn: str) -> str:
    """List the organization accounts affected by a single health event.

    Args:
        event_arn: The ARN of an organization health event.

    Example prompts:
    - "Which accounts does this event affect?"
    - "How wide is the blast radius of this event across my organization?"
    """
    try:
        has_access, error_message = await health_client.check_org_health_access()
        if not has_access:
            raise ToolError(f"Cannot fetch affected accounts: {error_message}")

        accounts = await health_client.get_affected_accounts(event_arn)
        if not accounts:
            return f"No affected accounts found for {event_arn}."

        lines = [f"**{len(accounts)} affected account(s)** for `{event_arn}`:", ""]
        lines.extend(f"- {account}" for account in accounts)
        return "\n".join(lines)

    except ToolError:
        raise
    except ClientError as e:
        raise ToolError(
            f"AWS Organizations Health API error: {e.response['Error']['Code']} - {e.response['Error']['Message']}"
        ) from e
    except Exception as e:
        raise ToolError(f"Error fetching affected accounts: {str(e)}") from e


@mcp.tool(annotations=_READ_ONLY)
async def list_event_types(service: str | None = None, category: str | None = None) -> str:
    """List the event types AWS Health can report, optionally for one service.

    Also the way to discover valid service names: the service codes AWS Health
    uses do not always match the marketing name (Step Functions is 'STATES',
    EventBridge is 'EVENTS').

    Args:
        service: Optional. Restrict to one AWS service. Case insensitive.
        category: Optional. One of 'issue', 'accountNotification',
            'scheduledChange', 'investigation'.

    Example prompts:
    - "What service names does AWS Health use?"
    - "What kinds of EC2 events can AWS Health report?"
    """
    try:
        filter_params: dict = {}

        if service:
            normalized_service, error = await _resolve_service(service)
            if not normalized_service:
                return error
            filter_params["services"] = [normalized_service]

        if category:
            valid_categories = (
                "issue",
                "accountNotification",
                "scheduledChange",
                "investigation",
            )
            match = next((c for c in valid_categories if c.lower() == category.lower()), None)
            if match is None:
                return f"Invalid category: {category}. Use one of: {', '.join(valid_categories)}."
            filter_params["eventTypeCategories"] = [match]

        if not filter_params:
            # Unfiltered, this is ~5000 event types. Return the service index,
            # which is what "what can I ask about?" actually means.
            services = await health_client.get_known_services()
            if not services:
                return "Could not reach AWS Health to list services."
            lines = [
                f"AWS Health covers **{len(services)} services**. "
                "Pass `service` to see the event types for one of them.",
                "",
            ]
            lines.extend(f"- {code}" for code in services)
            return "\n".join(lines)

        event_types = await health_client.paginate("describe_event_types", filter=filter_params)
        if not event_types:
            return "No matching event types found."

        by_service: dict[str, list[dict]] = {}
        for event_type in event_types:
            by_service.setdefault(event_type.get("service", "unknown"), []).append(event_type)

        sections = []
        for svc, types in sorted(by_service.items()):
            lines = [f"## {svc} ({len(types)} event types)", "", "| Code | Category |", "|---|---|"]
            for event_type in sorted(types, key=lambda t: t.get("code", "")):
                lines.append(
                    f"| {event_type.get('code', 'unknown')} "
                    f"| {event_type.get('category', '-')} |"
                )
            sections.append("\n".join(lines))
        return "\n\n".join(sections)

    except ToolError:
        raise
    except ClientError as e:
        raise ToolError(
            f"AWS Health API error: {e.response['Error']['Code']} - {e.response['Error']['Message']}"
        ) from e
    except Exception as e:
        raise ToolError(f"Error listing event types: {str(e)}") from e


@mcp.tool(annotations=_READ_ONLY)
async def find_events_for_resources(entity_values: list[str], include_closed: bool = False) -> str:
    """Find which health events affect specific resources of yours.

    Answers "is my instance / cluster / database affected by anything?".

    Matching goes through DescribeAffectedEntities, where entity values match
    exactly. The equivalent filter on DescribeEvents cannot be used for this:
    it also returns events that have no entities at all, so a resource ID that
    exists nowhere still comes back with matches.

    Args:
        entity_values: Resource identifiers, e.g. ['i-1234567890abcdef0'].
        include_closed: Also search resolved events, not just open/upcoming.

    Example prompts:
    - "Is i-1234567890abcdef0 affected by any AWS issue?"
    - "Do any current events touch my cluster my-prod-cluster?"
    """
    try:
        if not entity_values:
            return "No resource identifiers provided."

        status_codes = ["open", "upcoming"]
        if include_closed:
            status_codes.append("closed")

        events = await health_client.paginate(
            "describe_events", filter={"eventStatusCodes": status_codes}
        )
        if not events:
            return "No health events to search."

        events_by_arn = {e["arn"]: e for e in events if e.get("arn")}
        warnings: list[str] = []
        matches = await health_client.find_entities_for_values(
            list(events_by_arn), entity_values, warnings
        )
        if not matches:
            searched = ", ".join(entity_values)
            if warnings:
                # Events that could not be checked make "nothing found" a guess.
                raise ToolError(
                    f"Could not finish searching for {searched}; no match was found in the "
                    f"events that were checked.{format_warnings(warnings)}"
                )
            return f"No health events affect {searched} " f"(searched {len(events_by_arn)} events)."

        descriptions = await health_client.get_event_descriptions_batched(
            list(matches), last_updated_by_arn(events), warnings
        )

        sections = []
        for arn, entities in matches.items():
            event = events_by_arn.get(arn, {"arn": arn})
            body = format_event(event, descriptions.get(arn, "No description available"))
            lines = [body, "", "**Your matching resources:**"]
            lines.extend(format_entity(entity) for entity in entities)
            lines.append(f"\n**ARN:** `{arn}`")
            sections.append("\n".join(lines))

        header = (
            f"**{len(matches)} event(s)** affect the {len(entity_values)} "
            f"resource(s) you asked about.\n"
        )
        return header + "\n\n---\n\n".join(sections) + format_warnings(warnings)

    except ToolError:
        raise
    except ClientError as e:
        raise ToolError(
            f"AWS Health API error: {e.response['Error']['Code']} - {e.response['Error']['Message']}"
        ) from e
    except Exception as e:
        raise ToolError(f"Error searching events for resources: {str(e)}") from e


@mcp.tool(annotations=_READ_ONLY)
async def check_health_access() -> str:
    """Diagnose whether this server can actually reach the AWS Health API.

    Reports the calling identity, whether the account's support plan allows
    Health API access, and whether organization view is enabled. Run this first
    when other tools return access errors.

    Example prompts:
    - "Why can't you see my AWS health events?"
    - "Is AWS Health set up correctly?"
    - "Do I have organization-wide health access?"
    """
    lines = ["# AWS Health access check", ""]

    identity = await health_client.get_caller_identity()
    if identity:
        lines.append(f"- **Credentials:** ok — account `{identity.get('Account', 'unknown')}`")
        lines.append(f"- **Identity:** `{identity.get('Arn', 'unknown')}`")
    else:
        lines.append("- **Credentials:** FAILED — no usable AWS credentials.")
        lines.append("  Configure `aws configure`, or set `AWS_PROFILE` for this server.")

    has_access, error_message = await health_client.check_health_api_access()
    if has_access:
        lines.append("- **Health API (account):** ok")
    else:
        lines.append(f"- **Health API (account):** FAILED — {error_message}")
        if error_message and "Business or Enterprise" in error_message:
            lines.append(
                "  The Health API requires a Business or Enterprise Support plan. "
                "Account-level tools will not work without one."
            )
        else:
            lines.append("  The calling principal needs `health:Describe*` permissions.")

    org_access, org_error = await health_client.check_org_health_access()
    if org_access:
        lines.append("- **Health API (organization):** ok")
    else:
        lines.append(f"- **Health API (organization):** unavailable — {org_error}")
        lines.append(
            "  Org-level tools need this enabled from the management account: "
            "`aws health enable-health-service-access-for-organization`"
        )

    services = await health_client.get_known_services()
    lines.append(
        f"- **Service catalog:** {len(services)} services loaded"
        if services
        else "- **Service catalog:** unavailable — service names cannot be validated"
    )

    lines.append("")
    lines.append(f"Checked at {format_timestamp(datetime.now(timezone.utc))}.")
    return "\n".join(lines)


def run_server():
    """Run the MCP server."""
    mcp.run(transport="stdio")
