"""Organization-level AWS Health API tools."""

from typing import Any, List, Optional

from botocore.exceptions import ClientError

from .client import health_client
from .consts import VALID_AWS_SERVICES
from .formatters import format_timestamp, get_event_description, validate_service_name


async def get_org_service_health() -> str:
    """Get current AWS service health events across your organization.

    This tool provides a comprehensive overview of active AWS service health events
    across all accounts in your AWS Organization.
    It will show:
    - Current service status
    - Active incidents
    - Service disruptions
    - Ongoing issues
    - Affected accounts

    Example prompts:
    - "Show me all current AWS service health issues across my organization"
    - "What's the current status of AWS services in all my accounts?"
    - "Are there any active AWS service disruptions affecting multiple accounts?"
    - "List all ongoing AWS incidents across my organization"
    - "Get a health status report for all AWS services in my organization"

    Returns:
        A formatted string containing active AWS health events across the organization.
    """
    try:
        # First check if we have access to Organizations Health API
        has_access, error_message = health_client.check_org_health_access()
        if not has_access:
            return f"Cannot fetch organization events: {error_message}"

        # Get events with pagination
        events = []
        paginator = health_client.client.get_paginator("describe_events_for_organization")

        for page in paginator.paginate(filter={"eventStatusCodes": ["open", "upcoming"]}):
            if "events" in page:
                events.extend(page["events"])

        if not events:
            return "No active AWS organization health events found."

        # Format the events
        formatted_events = []
        for event in events:
            start_time = event.get("startTime", None)
            end_time = event.get("endTime", None)
            service_name = event.get("service", "Unknown")
            event_type = event.get("eventTypeCode", "Unknown")
            status_val = event.get("statusCode", "Unknown").upper()
            region = event.get("region", "global")

            # Get affected accounts with pagination if available
            try:
                affected_accounts = []
                if hasattr(health_client.client, "get_paginator") and hasattr(
                    health_client.client.get_paginator,
                    "describe_affected_accounts_for_organization",
                ):
                    accounts_paginator = health_client.client.get_paginator(
                        "describe_affected_accounts_for_organization"
                    )
                    for accounts_page in accounts_paginator.paginate(eventArn=event["arn"]):
                        if "affectedAccounts" in accounts_page:
                            affected_accounts.extend(accounts_page["affectedAccounts"])
                else:
                    # Fall back to non-paginated call
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
{chr(10).join(f'- {acc}' for acc in affected_accounts[:20]) if affected_accounts else 'No accounts affected'}
{f'... and {len(affected_accounts) - 20} more accounts' if len(affected_accounts) > 20 else ''}
{'='*50}"""
            formatted_events.append(event_details)

        return "\n\n".join(formatted_events)

    except Exception as e:
        return f"Error fetching organization health events: {str(e)}\nPlease ensure you have proper AWS credentials and Organizations access."


async def get_org_affected_entities(account_id: str = None, event_arn: str = None) -> str:
    """Get affected entities for AWS health events across your organization.

    This tool provides detailed information about resources affected by health events
    across all accounts in your AWS Organization.
    It shows:
    - Affected resources grouped by event and account
    - Current status of each resource
    - Last update timestamps
    - Impact details

    Example prompts:
    - "What resources are affected by current AWS issues across my organization?"
    - "Show me all impacted AWS entities in account 123456789012"
    - "List affected resources for active events in my organization"
    - "Get details of impacted AWS resources across all my accounts"
    - "Which AWS resources are experiencing problems in my organization?"

    Args:
        account_id: Optional. The AWS account ID to filter events for.
        event_arn: Optional. The ARN of a specific event to get details for.

    Returns:
        A formatted string containing affected entities grouped by event and account.
    """
    try:
        # First check if we have access to Organizations Health API
        has_access, error_message = health_client.check_org_health_access()
        if not has_access:
            return f"Cannot fetch organization events: {error_message}"

        # Get events with pagination
        events = []

        if event_arn:
            # If event ARN is provided, only get that specific event
            try:
                event_response = health_client.client.describe_event_details_for_organization(
                    organizationEventDetailFilters=[{"eventArn": event_arn}]
                )
                if "successfulSet" in event_response and event_response["successfulSet"]:
                    events = [event_response["successfulSet"][0]["event"]]
                else:
                    return f"No event found with ARN: {event_arn}"
            except ClientError as e:
                error_code = e.response["Error"]["Code"]
                error_message = e.response["Error"]["Message"]
                return f"AWS Organizations Health API error: {error_code} - {error_message}"
        else:
            # Otherwise get all open events
            paginator = health_client.client.get_paginator("describe_events_for_organization")
            for page in paginator.paginate(filter={"eventStatusCodes": ["open"]}):
                if "events" in page:
                    events.extend(page["events"])

        if not events:
            return "No open health events found in your organization."

        # Get affected entities for each event
        all_event_details = []
        for event in events:
            event_arn = event["arn"]
            event_service = event.get("service", "Unknown Service")
            event_type = event.get("eventTypeCode", "Unknown Type")
            start_time = event.get("startTime", None)
            end_time = event.get("endTime", None)

            # First get affected accounts
            try:
                affected_accounts = []
                accounts_response = (
                    health_client.client.describe_affected_accounts_for_organization(
                        eventArn=event_arn
                    )
                )
                affected_accounts = accounts_response.get("affectedAccounts", [])

                # Filter by account_id if provided
                if account_id:
                    if account_id not in affected_accounts:
                        continue
                    affected_accounts = [account_id]
            except ClientError:
                affected_accounts = []
                continue

            if not affected_accounts:
                continue

            # Format event header
            event_details = f"""{'='*50}
🚨 Organization Event Information {'='*25}
Service:     {event_service}
Type:        {event_type}
Status:      {event.get('statusCode', 'Unknown').upper()}
Region:      {event.get('region', 'global')}
Start Time:  {format_timestamp(start_time) if start_time else 'Not specified'}
End Time:    {format_timestamp(end_time) if end_time else 'Not specified'}

📝 Description:
{get_event_description(event, health_client.client)}

👥 Affected Accounts: {len(affected_accounts)}
"""

            # Get affected entities for each account
            account_entities = {}
            for acc in affected_accounts:
                try:
                    # Get affected entities with pagination
                    entities = []
                    entities_paginator = health_client.client.get_paginator(
                        "describe_affected_entities_for_organization"
                    )
                    for entities_page in entities_paginator.paginate(
                        organizationEntityFilters=[{"eventArn": event_arn, "awsAccountId": acc}]
                    ):
                        if "entities" in entities_page:
                            entities.extend(entities_page["entities"])

                    if entities:
                        account_entities[acc] = entities
                except ClientError:
                    continue

            # Add entities grouped by account
            for acc, entities in account_entities.items():
                # Count entities by status
                status_count = {}
                for entity in entities:
                    status = entity.get("statusCode", "Unknown")
                    status_count[status] = status_count.get(status, 0) + 1

                event_details += f"\n🔹 Account: {acc}\n"
                event_details += f"📊 Status Summary:\n"
                event_details += "\n".join(
                    f"- {status}: {count} entities" for status, count in status_count.items()
                )

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
                    for entity in status_entities[:20]:  # Limit to 20 entities per status
                        entity_details = entity.get("entityValue", "Unknown")
                        last_updated = entity.get("lastUpdatedTime")
                        if last_updated:
                            entity_details += f" (Last updated: {format_timestamp(last_updated)})"
                        event_details += f"\n- {entity_details}"

                    if len(status_entities) > 20:
                        event_details += f"\n... and {len(status_entities) - 20} more entities"

            event_details += f"\n{'='*50}"
            all_event_details.append(event_details)

        if not all_event_details:
            account_msg = f" for account {account_id}" if account_id else ""
            return f"No affected entities found for any open events{account_msg}."

        return "\n\n".join(all_event_details)

    except Exception as e:
        return f"Error fetching organization affected entities: {str(e)}\nPlease ensure you have proper AWS credentials and Organizations access."


async def get_org_service_events(service: str) -> str:
    """Get health events for a specific AWS service across your organization.

    This tool provides detailed health event information for a particular AWS service
    across all accounts in your AWS Organization.
    It shows:
    - All active and upcoming events
    - Event descriptions and timelines
    - Regional impact
    - Status updates
    - Affected accounts

    Example prompts:
    - "What's happening with EC2 across my organization right now?"
    - "Show me all RDS issues affecting my AWS accounts"
    - "Get Lambda service health status across my organization"
    - "Are there any problems with S3 in any of my accounts?"
    - "Check DynamoDB service health across my organization"

    Args:
        service: The AWS service name (e.g., 'EC2', 'RDS', 'LAMBDA'). Case insensitive.

    Returns:
        A formatted string containing events for the specified service across the organization.
    """
    try:
        # First check if we have access to Organizations Health API
        has_access, error_message = health_client.check_org_health_access()
        if not has_access:
            return f"Cannot fetch organization events: {error_message}"

        # Validate service name
        is_valid, normalized_service = validate_service_name(service)
        if not is_valid:
            suggestion = f"\nDid you mean '{normalized_service}'?" if normalized_service else ""
            valid_examples = ", ".join(VALID_AWS_SERVICES[:5])
            return f"Invalid service name: {service}.{suggestion}\nPlease provide a valid AWS service name (e.g., {valid_examples})."

        try:
            # Get events with pagination
            events = []
            paginator = health_client.client.get_paginator("describe_events_for_organization")

            for page in paginator.paginate(
                filter={"eventStatusCodes": ["open", "upcoming"], "services": [normalized_service]}
            ):
                if "events" in page:
                    events.extend(page["events"])

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            error_message = e.response["Error"]["Message"]
            return f"AWS Organizations Health API error for service {normalized_service}: {error_code} - {error_message}"

        if not events:
            return f"No active health events found for service {normalized_service} across your organization."

        # Format the events
        formatted_events = []
        for event in events:
            start_time = event.get("startTime", None)
            end_time = event.get("endTime", None)

            # Get affected accounts
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
📅 Organization Event Details for {normalized_service} {'='*20}
Event Type:  {event.get('eventTypeCode', 'Unknown')}
Status:      {event.get('statusCode', 'Unknown').upper()}
Region:      {event.get('region', 'global')}
Start Time:  {format_timestamp(start_time) if start_time else 'Not specified'}
End Time:    {format_timestamp(end_time) if end_time else 'Not specified'}
Event ARN:   {event.get('arn', 'Not available')}

📝 Description:
{get_event_description(event, health_client.client)}

👥 Affected Accounts ({len(affected_accounts)}):
{chr(10).join(f'- {acc}' for acc in affected_accounts[:20]) if affected_accounts else 'No accounts affected'}
{f'... and {len(affected_accounts) - 20} more accounts' if len(affected_accounts) > 20 else ''}

🔍 Additional Information:
- Event Category: {event.get('eventTypeCategory', 'Not specified')}
- Event Scope:    {event.get('eventScopeCode', 'Not specified')}
{'='*50}"""
            formatted_events.append(event_details)

        return "\n\n".join(formatted_events)

    except Exception as e:
        return f"Error fetching organization service events: {str(e)}\nPlease ensure you have proper AWS credentials and Organizations access."


async def get_org_account_events(account_id: str) -> str:
    """Get health events for a specific AWS account in your organization.

    This tool provides detailed health event information for a particular AWS account
    in your AWS Organization.
    It shows:
    - All active and upcoming events affecting the account
    - Event descriptions and timelines
    - Regional impact
    - Status updates
    - Affected resources

    Example prompts:
    - "What health events are affecting account 123456789012?"
    - "Show me all issues in my account 123456789012"
    - "Get health status for account 123456789012"
    - "Are there any problems with account 123456789012?"
    - "Check health events for account 123456789012"

    Args:
        account_id: The AWS account ID to get events for.

    Returns:
        A formatted string containing events for the specified account.
    """
    try:
        # First check if we have access to Organizations Health API
        has_access, error_message = health_client.check_org_health_access()
        if not has_access:
            return f"Cannot fetch organization events: {error_message}"

        # Validate account_id format
        if not account_id.isdigit() or len(account_id) != 12:
            return f"Invalid account ID format: {account_id}. Please provide a valid 12-digit AWS account ID."

        # Get all events with pagination
        all_events = []
        paginator = health_client.client.get_paginator("describe_events_for_organization")

        for page in paginator.paginate(filter={"eventStatusCodes": ["open", "upcoming"]}):
            if "events" in page:
                all_events.extend(page["events"])

        if not all_events:
            return "No active health events found across your organization."

        # Filter events that affect the specified account
        account_events = []
        for event in all_events:
            try:
                affected_accounts_response = (
                    health_client.client.describe_affected_accounts_for_organization(
                        eventArn=event["arn"]
                    )
                )
                affected_accounts = affected_accounts_response.get("affectedAccounts", [])

                if account_id in affected_accounts:
                    account_events.append((event, affected_accounts))
            except Exception:
                continue

        if not account_events:
            return f"No active health events found for account {account_id}."

        # Format the events
        formatted_events = []
        for event, affected_accounts in account_events:
            start_time = event.get("startTime", None)
            end_time = event.get("endTime", None)
            service_name = event.get("service", "Unknown")

            # Get affected entities for this account and event
            try:
                entities = []
                entities_paginator = health_client.client.get_paginator(
                    "describe_affected_entities_for_organization"
                )
                for entities_page in entities_paginator.paginate(
                    organizationEntityFilters=[
                        {"eventArn": event["arn"], "awsAccountId": account_id}
                    ]
                ):
                    if "entities" in entities_page:
                        entities.extend(entities_page["entities"])
            except Exception:
                entities = []

            event_details = f"""{'='*50}
📅 Event Details for Account {account_id} {'='*25}
Service:     {service_name}
Type:        {event.get('eventTypeCode', 'Unknown')}
Status:      {event.get('statusCode', 'Unknown').upper()}
Region:      {event.get('region', 'global')}
Start Time:  {format_timestamp(start_time) if start_time else 'Not specified'}
End Time:    {format_timestamp(end_time) if end_time else 'Not specified'}

📝 Description:
{get_event_description(event, health_client.client)}

🔢 Account Impact:
- This account is one of {len(affected_accounts)} affected accounts
"""

            # Add affected entities if available
            if entities:
                # Count entities by status
                status_count = {}
                for entity in entities:
                    status = entity.get("statusCode", "Unknown")
                    status_count[status] = status_count.get(status, 0) + 1

                event_details += f"\n📊 Affected Resources Summary:\n"
                event_details += "\n".join(
                    f"- {status}: {count} resources" for status, count in status_count.items()
                )

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
                    for entity in status_entities[:15]:  # Limit to 15 entities per status
                        entity_details = entity.get("entityValue", "Unknown")
                        last_updated = entity.get("lastUpdatedTime")
                        if last_updated:
                            entity_details += f" (Last updated: {format_timestamp(last_updated)})"
                        event_details += f"\n- {entity_details}"

                    if len(status_entities) > 15:
                        event_details += f"\n... and {len(status_entities) - 15} more resources"
            else:
                event_details += "\nNo specific resources identified for this account."

            event_details += f"\n{'='*50}"
            formatted_events.append(event_details)

        return "\n\n".join(formatted_events)

    except Exception as e:
        return f"Error fetching account health events: {str(e)}\nPlease ensure you have proper AWS credentials and Organizations access."


async def get_org_scheduled_changes() -> str:
    """Get all scheduled changes/maintenance events across your AWS Organization.

    This tool provides information about upcoming planned maintenance and changes
    across all accounts in your AWS Organization.
    It shows:
    - Scheduled maintenance windows
    - Planned service updates
    - Infrastructure improvements
    - System upgrades
    - Affected accounts

    Example prompts:
    - "What maintenance is planned for AWS services across my organization?"
    - "Show me upcoming AWS changes affecting my accounts"
    - "List scheduled maintenance events across my organization"
    - "When is the next AWS maintenance affecting my accounts?"
    - "Get planned service updates across my organization"

    Returns:
        A formatted string containing upcoming scheduled changes and maintenance events.
    """
    try:
        # First check if we have access to Organizations Health API
        has_access, error_message = health_client.check_org_health_access()
        if not has_access:
            return f"Cannot fetch organization events: {error_message}"

        # Get events with pagination
        events = []
        paginator = health_client.client.get_paginator("describe_events_for_organization")

        for page in paginator.paginate(
            filter={
                "eventTypeCategories": ["scheduledChange"],
                "eventStatusCodes": ["open", "upcoming"],
            }
        ):
            if "events" in page:
                events.extend(page["events"])

        if not events:
            return "No scheduled changes found across your organization."

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
🔄 Organization Scheduled Changes for {service} {'='*15}
Total scheduled events: {len(service_events_list)}

"""
            for event in service_events_list:
                start_time = event.get("startTime", None)
                end_time = event.get("endTime", None)
                last_updated = event.get("lastUpdatedTime", None)

                # Get affected accounts
                try:
                    affected_accounts_response = (
                        health_client.client.describe_affected_accounts_for_organization(
                            eventArn=event["arn"]
                        )
                    )
                    affected_accounts = affected_accounts_response.get("affectedAccounts", [])
                except Exception:
                    affected_accounts = []

                service_details += f"""📅 Event Details:
Type:         {event.get('eventTypeCode', 'Unknown')}
Status:       {event.get('statusCode', 'Unknown').upper()}
Region:       {event.get('region', 'global')}
Start Time:   {format_timestamp(start_time) if start_time else 'Not specified'}
End Time:     {format_timestamp(end_time) if end_time else 'Not specified'}
Last Updated: {format_timestamp(last_updated) if last_updated else 'Not specified'}

📝 Description:
{get_event_description(event, health_client.client)}

👥 Affected Accounts ({len(affected_accounts)}):
{chr(10).join(f'- {acc}' for acc in affected_accounts[:10]) if affected_accounts else 'No accounts affected'}
{f'... and {len(affected_accounts) - 10} more accounts' if len(affected_accounts) > 10 else ''}

"""
            service_details += f"{'='*50}"
            formatted_services.append(service_details)

        return "\n\n".join(formatted_services)

    except Exception as e:
        return f"Error fetching organization scheduled changes: {str(e)}\nPlease ensure you have proper AWS credentials and Organizations access."
