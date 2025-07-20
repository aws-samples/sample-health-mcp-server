"""AWS Health API client initialization and access validation."""

import boto3
from botocore.exceptions import ClientError


class HealthClient:
    """AWS Health API client wrapper."""

    def __init__(self):
        """Initialize AWS Health client with explicit region."""
        try:
            # AWS Health API is only available in us-east-1
            self.client = boto3.client("health", region_name="us-east-1")
            # Check Health API access on startup
            has_access, error_message = self.check_health_api_access()
            if not has_access:
                print(f"Warning: {error_message}")
        except Exception as e:
            print(f"Error initializing AWS Health client: {str(e)}")
            self.client = None

    def check_health_api_access(self):
        """Check if we have access to AWS Health API."""
        try:
            # Try a simple API call to check access
            self.client.describe_events(filter={"eventStatusCodes": ["open"]})
            return True, None
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            error_message = e.response["Error"]["Message"]

            if error_code == "SubscriptionRequiredException":
                return False, "AWS Health API requires Business or Enterprise Support subscription"
            elif error_code in ("AccessDeniedException", "UnauthorizedException"):
                return False, "Insufficient permissions to access AWS Health API"
            else:
                return False, f"AWS Health API error: {error_message}"
        except Exception as e:
            return False, f"Error connecting to AWS Health API: {str(e)}"

    def check_org_health_access(self):
        """Check if AWS Health organization view is enabled."""
        try:
            response = self.client.describe_health_service_status_for_organization()
            status = response.get("healthServiceAccessStatusForOrganization")

            if status == "ENABLED":
                return True, None
            elif status == "PENDING":
                return (
                    False,
                    "AWS Health organization view is pending activation. Please wait a few minutes and try again.",
                )
            else:  # DISABLED or something else
                return False, (
                    "AWS Health organization view is not enabled. "
                    "Please enable it by calling EnableHealthServiceAccessForOrganization from your AWS management account."
                )
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "AccessDeniedException":
                return False, (
                    "Insufficient permissions. "
                    "You need 'health:DescribeHealthServiceStatusForOrganization' permission. "
                    "Also, ensure you are calling from the organization's management account."
                )
            return False, f"Error checking organization health status: {e}"
        except Exception as e:
            return False, f"An unexpected error occurred: {str(e)}"


# Global health client instance
health_client = HealthClient()
