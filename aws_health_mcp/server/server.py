"""Main MCP server implementation for AWS Health API."""

from typing import Any

from botocore.exceptions import ClientError
from mcp.server.fastmcp import FastMCP

from .client import health_client
from .consts import VALID_AWS_SERVICES
from .formatters import format_timestamp, get_event_description, validate_service_name
from .org_tools import (
    get_org_account_events,
    get_org_affected_entities,
    get_org_scheduled_changes,
    get_org_service_events,
    get_org_service_health,
)

# Initialize FastMCP server
mcp = FastMCP("aws-health")


@mcp.tool()
async def get_service_health() -> str:
    """Get current AWS service health events.

    This tool provides a comprehensive overview of active AWS service health events.
    It will show:
    - Current service status
    - Active incidents
    - Service disruptions
    - Ongoing issues

    Example prompts:
    - "Show me all current AWS service health issues"
    - "What's the current status of AWS services?"
    - "Are there any active AWS service disruptions?"
    - "List all ongoing AWS incidents"
    - "Get a health status report for all AWS services"

    Returns:
        A formatted string containing active AWS health events.
    """
    try:
        # Get current health events with pagination
        events = []
        paginator = health_client.client.get_paginator("describe_events")

        # Include both open and upcoming events
        for page in paginator.paginate(filter={"eventStatusCodes": ["open", "upcoming"]}):
            if "events" in page:
                events.extend(page["events"])

        if not events:
            return "No active AWS health events found."

        # Format the events
        formatted_events = []
        for event in events:
            start_time = event.get("startTime", None)
            end_time = event.get("endTime", None)
            event_details = f"""{'='*50}
📅 Event Details {'='*35}
Service:     {event.get('service', 'Unknown')}
Type:        {event.get('eventTypeCode', 'Unknown')}
Status:      {event.get('statusCode', 'Unknown').upper()}
Region:      {event.get('region', 'global')}
Start Time:  {format_timestamp(start_time) if start_time else 'Not specified'}
End Time:    {format_timestamp(end_time) if end_time else 'Not specified'}

📝 Description:
{get_event_description(event, health_client.client)}
{'='*50}"""
            formatted_events.append(event_details)

        return "\n\n".join(formatted_events)

    except Exception as e:
        return f"Error fetching AWS health events: {str(e)}"


@mcp.tool()
async def get_affected_entities() -> str:
    """Get affected entities for all open AWS health events.

    This tool provides detailed information about resources affected by active health events.
    It shows:
    - Affected resources grouped by event
    - Current status of each resource
    - Last update timestamps
    - Impact details

    Example prompts:
    - "What resources are affected by current AWS issues?"
    - "Show me all impacted AWS entities"
    - "List affected resources for active events"
    - "Get details of impacted AWS resources"
    - "Which AWS resources are experiencing problems?"

    Returns:
        A formatted string containing affected entities grouped by event.
    """
    try:
        # First get all open events with pagination
        events = []
        paginator = health_client.client.get_paginator("describe_events")

        for page in paginator.paginate(filter={"eventStatusCodes": ["open"]}):
            if "events" in page:
                events.extend(page["events"])

        if not events:
            return "No open health events found."

        # Get affected entities for each event
        all_event_details = []
        for event in events:
            event_arn = event["arn"]
            event_service = event.get("service", "Unknown Service")
            event_type = event.get("eventTypeCode", "Unknown Type")
            start_time = event.get("startTime", None)
            end_time = event.get("endTime", None)

            # Get affected entities for this event with pagination
            entities = []
            entities_paginator = health_client.client.get_paginator("describe_affected_entities")

            for entities_page in entities_paginator.paginate(filter={"eventArns": [event_arn]}):
                if "entities" in entities_page:
                    entities.extend(entities_page["entities"])

            if entities:
                # Count entities by status
                status_count = {}
                for entity in entities:
                    status = entity.get("statusCode", "Unknown")
                    status_count[status] = status_count.get(status, 0) + 1

                # Format event and its affected entities
                event_details = f"""{'='*50}
🚨 Event Information {'='*31}
Service:     {event_service}
Type:        {event_type}
Status:      {event.get('statusCode', 'Unknown').upper()}
Region:      {event.get('region', 'global')}
Start Time:  {format_timestamp(start_time) if start_time else 'Not specified'}
End Time:    {format_timestamp(end_time) if end_time else 'Not specified'}

📝 Description:
{get_event_description(event, health_client.client)}

📊 Status Summary:
{chr(10).join(f'- {status}: {count} entities' for status, count in status_count.items())}

🎯 Affected Entities:"""

                # Group entities by status
                entities_by_status = {}
                for entity in entities:
                    status = entity.get("statusCode", "Unknown")
                    if status not in entities_by_status:
                        entities_by_status[status] = []
                    entities_by_status[status].append(entity)

                # Add entities grouped by status
                for status, status_entities in entities_by_status.items():
                    event_details += f"\n\n{status.upper()} ({len(status_entities)}):"
                    for entity in status_entities:
                        entity_details = entity.get("entityValue", "Unknown")
                        last_updated = entity.get("lastUpdatedTime")
                        if last_updated:
                            entity_details += f" (Last updated: {format_timestamp(last_updated)})"
                        event_details += f"\n- {entity_details}"

                event_details += f"\n{'='*50}"
                all_event_details.append(event_details)

        if not all_event_details:
            return "No affected entities found for any open events."

        return "\n\n".join(all_event_details)

    except Exception as e:
        return f"Error fetching affected entities: {str(e)}"


@mcp.tool()
async def get_service_events(service: str) -> str:
    """Get health events for a specific AWS service.

    This tool provides detailed health event information for a particular AWS service.
    It shows:
    - All active and upcoming events
    - Event descriptions and timelines
    - Regional impact
    - Status updates

    Example prompts:
    - "What's happening with EC2 right now?"
    - "Show me all RDS issues"
    - "Get Lambda service health status"
    - "Are there any problems with S3?"
    - "Check DynamoDB service health"

    Args:
        service: The AWS service name (e.g., 'EC2', 'RDS', 'LAMBDA'). Case insensitive.

    Returns:
        A formatted string containing events for the specified service.
    """
    try:
        # First check if we have access to Health API
        has_access, error_message = health_client.check_health_api_access()
        if not has_access:
            return f"Cannot fetch health events: {error_message}"

        # Validate service name
        is_valid, normalized_service = validate_service_name(service)
        if not is_valid:
            suggestion = f"\nDid you mean '{normalized_service}'?" if normalized_service else ""
            valid_examples = ", ".join(VALID_AWS_SERVICES[:5])
            return f"Invalid service name: {service}.{suggestion}\nPlease provide a valid AWS service name (e.g., {valid_examples})."

        try:
            # Get events with pagination
            events = []
            paginator = health_client.client.get_paginator("describe_events")

            for page in paginator.paginate(
                filter={"eventStatusCodes": ["open", "upcoming"], "services": [normalized_service]}
            ):
                if "events" in page:
                    events.extend(page["events"])

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            error_message = e.response["Error"]["Message"]
            return f"AWS Health API error for service {normalized_service}: {error_code} - {error_message}"

        if not events:
            return f"No active health events found for service: {normalized_service}"

        # Format the events
        formatted_events = []
        for event in events:
            start_time = event.get("startTime", None)
            end_time = event.get("endTime", None)
            event_details = f"""{'='*50}
📅 Event Details for {normalized_service} {'='*35}
Event Type:  {event.get('eventTypeCode', 'Unknown')}
Status:      {event.get('statusCode', 'Unknown').upper()}
Region:      {event.get('region', 'global')}
Start Time:  {format_timestamp(start_time) if start_time else 'Not specified'}
End Time:    {format_timestamp(end_time) if end_time else 'Not specified'}
Event ARN:   {event.get('arn', 'Not available')}

📝 Description:
{get_event_description(event, health_client.client)}

🔍 Additional Information:
- Event Category: {event.get('eventTypeCategory', 'Not specified')}
- Event Scope:    {event.get('eventScopeCode', 'Not specified')}
{'='*50}"""
            formatted_events.append(event_details)

        return "\n\n".join(formatted_events)

    except Exception as e:
        return f"Error fetching AWS health events: {str(e)}\nPlease ensure you have proper AWS credentials and Health API access."


@mcp.tool()
async def get_completed_events(service: str = None) -> str:
    """Get completed/closed health events.

    This tool provides historical information about resolved AWS health events.
    It shows:
    - Recently resolved incidents
    - Event resolution details
    - Duration of past events
    - Service recovery information

    Example prompts:
    - "Show me recently resolved AWS issues"
    - "What EC2 problems were fixed?"
    - "List completed health events"
    - "Get history of resolved incidents"
    - "Show me fixed AWS problems"

    Args:
        service: Optional. The AWS service name to filter by (e.g., 'EC2', 'RDS'). Case insensitive.

    Returns:
        A formatted string containing completed events, optionally filtered by service.
    """
    try:
        # First check if we have access to Health API
        has_access, error_message = health_client.check_health_api_access()
        if not has_access:
            return f"Cannot fetch completed events: {error_message}"

        filter_params = {
            "eventStatusCodes": ["closed"]  # 'closed' is the only valid status for completed events
        }

        normalized_service = None
        if service:
            is_valid, normalized_service = validate_service_name(service)
            if not is_valid:
                suggestion = f"\nDid you mean '{normalized_service}'?" if normalized_service else ""
                valid_examples = ", ".join(VALID_AWS_SERVICES[:5])
                return f"Invalid service name: {service}.{suggestion}\nPlease provide a valid AWS service name (e.g., {valid_examples})."

            filter_params["services"] = [normalized_service]

        try:
            # Get events with pagination
            events = []
            paginator = health_client.client.get_paginator("describe_events")

            for page in paginator.paginate(filter=filter_params):
                if "events" in page:
                    events.extend(page["events"])

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            error_message = e.response["Error"]["Message"]
            service_msg = f" for service {normalized_service}" if normalized_service else ""
            return f"AWS Health API error{service_msg}: {error_code} - {error_message}"

        if not events:
            service_msg = f" for service: {normalized_service}" if normalized_service else ""
            return f"No completed health events found{service_msg}."

        # Format the events
        formatted_events = []
        for event in events:
            service_name = event.get("service", "Unknown")
            start_time = event.get("startTime", None)
            end_time = event.get("endTime", None)
            last_updated = event.get("lastUpdatedTime", None)

            event_details = f"""{'='*50}
✅ Completed Event Details {'='*30}
Service:      {service_name}
Event Type:   {event.get('eventTypeCode', 'Unknown')}
Status:       {event.get('statusCode', 'Unknown').upper()}
Region:       {event.get('region', 'global')}
Start Time:   {format_timestamp(start_time) if start_time else 'Not specified'}
End Time:     {format_timestamp(end_time) if end_time else 'Not specified'}
Last Updated: {format_timestamp(last_updated) if last_updated else 'Not specified'}

📝 Description:
{get_event_description(event, health_client.client)}

🔍 Resolution Details:
- Event Category: {event.get('eventTypeCategory', 'Not specified')}
- Event Scope:    {event.get('eventScopeCode', 'Not specified')}
{'='*50}"""
            formatted_events.append(event_details)

        return "\n\n".join(formatted_events)

    except Exception as e:
        service_msg = f" for service {normalized_service}" if normalized_service else ""
        return f"Error fetching completed events{service_msg}: {str(e)}\nPlease ensure you have proper AWS credentials and Health API access."


@mcp.tool()
async def get_scheduled_changes() -> str:
    """Get all scheduled changes/maintenance events across AWS services.

    This tool provides information about upcoming planned maintenance and changes.
    It shows:
    - Scheduled maintenance windows
    - Planned service updates
    - Infrastructure improvements
    - System upgrades

    Example prompts:
    - "What maintenance is planned for AWS services?"
    - "Show me upcoming AWS changes"
    - "List scheduled maintenance events"
    - "When is the next AWS maintenance?"
    - "Get planned service updates"

    Returns:
        A formatted string containing upcoming scheduled changes and maintenance events.
    """
    try:
        # Get events with pagination
        events = []
        paginator = health_client.client.get_paginator("describe_events")

        for page in paginator.paginate(
            filter={
                "eventTypeCategories": ["scheduledChange"],
                "eventStatusCodes": ["open", "upcoming"],
            }
        ):
            if "events" in page:
                events.extend(page["events"])

        if not events:
            return "No scheduled changes found."

        # Group events by service
        service_events = {}
        for event in events:
            service = event.get("service", "Unknown")
            if service not in service_events:
                service_events[service] = []
            service_events[service].append(event)

        # Format the events grouped by service
        formatted_services = []
        for service, service_events_list in sorted(service_events.items()):
            service_details = f"""{'='*50}
🔄 Scheduled Changes for {service} {'='*25}
Total scheduled events: {len(service_events_list)}

"""
            for event in service_events_list:
                start_time = event.get("startTime", None)
                end_time = event.get("endTime", None)
                last_updated = event.get("lastUpdatedTime", None)

                service_details += f"""📅 Event Details:
Type:         {event.get('eventTypeCode', 'Unknown')}
Status:       {event.get('statusCode', 'Unknown').upper()}
Region:       {event.get('region', 'global')}
Start Time:   {format_timestamp(start_time) if start_time else 'Not specified'}
End Time:     {format_timestamp(end_time) if end_time else 'Not specified'}
Last Updated: {format_timestamp(last_updated) if last_updated else 'Not specified'}

📝 Description:
{get_event_description(event, health_client.client)}

"""
            service_details += f"{'='*50}"
            formatted_services.append(service_details)

        return "\n\n".join(formatted_services)

    except Exception as e:
        return f"Error fetching scheduled AWS changes: {str(e)}"


@mcp.tool()
async def get_org_health_events(
    service: str = None, account_id: str = None, status: str = "active"
) -> str:
    """Get health events across your AWS Organization.

    This tool provides a comprehensive view of health events across all accounts in your organization.
    It shows:
    - Multi-account impact
    - Organization-wide issues
    - Account-specific problems
    - Cross-account patterns

    If no arguments are provided, it returns all active org health events (open and upcoming), similar to get_service_health.

    Args:
        service: Optional. The AWS service name to filter by (e.g., 'EC2', 'RDS'). Case insensitive.
        account_id: Optional. The AWS account ID to filter events for.
        status: Optional. The event status to filter by. Can be 'active' (default) or 'closed'.

    Returns:
        A formatted string containing organization-wide health events.
    """
    try:
        # First check if we have access to Organizations Health API
        has_access, error_message = health_client.check_org_health_access()
        if not has_access:
            return f"Cannot fetch organization events: {error_message}"

        # If all arguments are default, just return all active org health events (open and upcoming)
        if service is None and account_id is None and (status is None or status == "active"):
            # Get events with pagination
            events = []
            paginator = health_client.client.get_paginator("describe_events_for_organization")

            for page in paginator.paginate(
                filter={"eventStatusCodes": ["open", "upcoming", "closed"]}
            ):
                if "events" in page:
                    events.extend(page["events"])

            if not events:
                return "No active AWS organization health events found."

            formatted_events = []
            for event in events:
                start_time = event.get("startTime", None)
                end_time = event.get("endTime", None)
                service_name = event.get("service", "Unknown")
                event_type = event.get("eventTypeCode", "Unknown")
                status_val = event.get("statusCode", "Unknown").upper()
                region = event.get("region", "global")
                try:
                    affected_accounts_response = (
                        health_client.client.describe_affected_accounts_for_organization(
                            eventArn=event["arn"]
                        )
                    )
                    affected_accounts = affected_accounts_response.get("affectedAccounts", [])
                except Exception:
                    affected_accounts = []
                event_details = f"""{'='*50}
🏢 Org Event Details {'='*35}
Service:     {service_name}
Type:        {event_type}
Status:      {status_val}
Region:      {region}
Start Time:  {format_timestamp(start_time) if start_time else 'Not specified'}
End Time:    {format_timestamp(end_time) if end_time else 'Not specified'}

📝 Description:
{get_event_description(event, health_client.client)}

👥 Affected Accounts ({len(affected_accounts)}):
{chr(10).join(f'- {acc}' for acc in affected_accounts) if affected_accounts else 'No accounts affected'}
{'='*50}"""
                formatted_events.append(event_details)
            return "\n\n".join(formatted_events)

        # Otherwise, keep the original filtering logic
        if status is None:
            status = "active"
        if status.lower() == "active":
            status_codes = ["open", "upcoming"]
        elif status.lower() == "closed":
            status_codes = ["closed"]
        else:
            return "Invalid status. Please use 'active' or 'closed'."

        filter_params = {"eventStatusCodes": status_codes}
        normalized_service = None
        if service:
            is_valid, normalized_service = validate_service_name(service)
            if not is_valid:
                suggestion = f"\nDid you mean '{normalized_service}'?" if normalized_service else ""
                valid_examples = ", ".join(VALID_AWS_SERVICES[:5])
                return f"Invalid service name: {service}.{suggestion}\nPlease provide a valid AWS service name (e.g., {valid_examples})."
            filter_params["services"] = [normalized_service]

        try:
            # Get events with pagination
            events = []
            paginator = health_client.client.get_paginator("describe_events_for_organization")

            for page in paginator.paginate(filter=filter_params):
                if "events" in page:
                    events.extend(page["events"])

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            error_message = e.response["Error"]["Message"]
            return f"AWS Organizations Health API error: {error_code} - {error_message}"

        if not events:
            service_msg = f" for service: {normalized_service}" if service else ""
            status_msg = f" with status '{status}'"
            return f"No organization health events found{status_msg}{service_msg}."

        formatted_events = []
        for event in events:
            event_arn = event["arn"]
            try:
                affected_accounts_response = (
                    health_client.client.describe_affected_accounts_for_organization(
                        eventArn=event_arn
                    )
                )
                affected_accounts = affected_accounts_response.get("affectedAccounts", [])
            except ClientError:
                affected_accounts = []

            if account_id and account_id not in affected_accounts:
                continue

            service_name = event.get("service", "Unknown")
            start_time = event.get("startTime", None)
            end_time = event.get("endTime", None)
            last_updated = event.get("lastUpdatedTime", None)
            event_details = f"""{'='*50}
🏢 Organization Event Details {'='*27}
Service:      {service_name}
Event Type:   {event.get('eventTypeCode', 'Unknown')}
Status:       {event.get('statusCode', 'Unknown').upper()}
Region:       {event.get('region', 'global')}
Start Time:   {format_timestamp(start_time) if start_time else 'Not specified'}
End Time:     {format_timestamp(end_time) if end_time else 'Not specified'}
Last Updated: {format_timestamp(last_updated) if last_updated else 'Not specified'}

�E Description:
{get_event_description(event, health_client.client)}

👥 Affected Accounts ({len(affected_accounts)}):
{chr(10).join(f"- {acc}" for acc in affected_accounts) if affected_accounts else "No accounts affected"}

🔍 Additional Details:
- Event Category: {event.get('eventTypeCategory', 'Not specified')}
- Event Scope:    {event.get('eventScopeCode', 'Not specified')}
{'='*50}"""
            formatted_events.append(event_details)

        if not formatted_events:
            account_msg = f" for account {account_id}" if account_id else ""
            service_msg = f" and service {normalized_service}" if service else ""
            status_msg = f" with status '{status}'"
            return f"No matching organization health events found{account_msg}{status_msg}{service_msg}."

        return "\n\n".join(formatted_events)

    except Exception as e:
        return f"Error fetching organization health events: {str(e)}\nPlease ensure you have proper AWS credentials and Organizations access."


# Register organization-level tools
mcp.tool()(get_org_service_health)
mcp.tool()(get_org_affected_entities)
mcp.tool()(get_org_service_events)
mcp.tool()(get_org_account_events)
mcp.tool()(get_org_scheduled_changes)


def run_server():
    """Run the MCP server."""
    mcp.run(transport="stdio")
