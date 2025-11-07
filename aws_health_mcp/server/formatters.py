"""Formatting utilities for AWS Health events and data."""

import difflib
from datetime import datetime

from botocore.exceptions import ClientError

from .consts import VALID_AWS_SERVICES


def validate_service_name(service: str) -> tuple[bool, str]:
    """Validate and normalize AWS service name.

    Args:
        service: The service name to validate

    Returns:
        Tuple of (is_valid, normalized_name)
    """
    if not service:
        return False, ""

    # Normalize input: remove spaces, convert to uppercase
    normalized = service.replace(" ", "").replace("-", "_").upper()

    # Direct match
    if normalized in VALID_AWS_SERVICES:
        return True, normalized

    # Check for common variations
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

    # Find closest match for suggestion
    matches = difflib.get_close_matches(normalized, VALID_AWS_SERVICES, n=1, cutoff=0.6)
    if matches:
        return False, matches[0]

    return False, ""


def format_timestamp(timestamp) -> str:
    """Format a timestamp into a readable string."""
    if not timestamp:
        return "Not specified"
    return timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")


def get_event_description(event: dict, health_client) -> str:
    """Extract and format the event description using describe_event_details.

    Args:
        event: The event dictionary containing at least the ARN
        health_client: The AWS Health client instance

    Returns:
        A formatted description string
    """
    try:
        # Get the event ARN
        event_arn = event.get("arn")
        if not event_arn:
            return "Description: Event ARN not available"

        # Call describe_event_details with retry logic
        max_retries = 3
        retry_delay = 1  # seconds
        
        for attempt in range(max_retries):
            try:
                response = health_client.describe_event_details(eventArns=[event_arn])
                break  # Success, exit retry loop
            except ClientError as e:
                error_code = e.response["Error"]["Code"]
                error_message = e.response["Error"]["Message"]
                
                # If this is a throttling error and not the last attempt, retry
                if error_code in ["Throttling", "ThrottlingException", "RequestLimitExceeded"] and attempt < max_retries - 1:
                    import time
                    time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                    continue
                    
                return f"Error getting detailed description: {error_code} - {error_message}"
            except Exception as e:
                if attempt < max_retries - 1:
                    import time
                    time.sleep(retry_delay * (2 ** attempt))
                    continue
                return f"Error retrieving description: {str(e)}"

        # Extract description from response
        if not response or "successfulSet" not in response or not response["successfulSet"]:
            # Fall back to basic description if detailed call fails
            if "eventDescription" not in event:
                return "Description: Not provided by AWS"

            descriptions = event["eventDescription"]
            if not descriptions or not isinstance(descriptions, list):
                return "Description: Invalid description format"

            # Get the English description or the first available one
            for desc in descriptions:
                if desc.get("language", "") == "en-US":
                    return desc.get("latestDescription", "No English description available")

            # If no English description found, use the first one
            if descriptions:
                return descriptions[0].get(
                    "latestDescription", "Description not available in any language"
                )

            return "Description: Not available"

        # Get the successful event detail
        event_detail = response["successfulSet"][0]

        # Extract the detailed description
        event_desc = event_detail.get("eventDescription", {})
        latest_desc = event_desc.get("latestDescription", "")

        # If we got a detailed description, return it
        if latest_desc:
            return latest_desc

        # Fall back to basic description if detailed is empty
        return "Description: No detailed description available"

    except Exception as e:
        return f"Error retrieving description: {str(e)}"
