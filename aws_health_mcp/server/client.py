"""AWS Health API client initialization and access validation."""

import time
import logging
from typing import Tuple, Optional, Any, Dict

import boto3
from botocore.exceptions import ClientError
from botocore.config import Config as BotocoreConfig

from .config import Config


class HealthClient:
    """AWS Health API client wrapper with retry logic and enhanced error handling."""

    def __init__(self):
        """Initialize AWS Health client with production configuration."""
        self.logger = logging.getLogger(__name__)
        
        try:
            # Configure boto3 with retry and timeout settings
            boto_config = BotocoreConfig(
                region_name="us-east-1",  # Health API only available in us-east-1
                retries={
                    'max_attempts': 3,
                    'mode': 'adaptive'
                },
                read_timeout=Config.HEALTH_API_TIMEOUT,
                connect_timeout=10,
                max_pool_connections=50
            )
            
            # Use profile if specified
            session = boto3.Session(profile_name=Config.AWS_PROFILE)
            self.client = session.client("health", config=boto_config)
            
            # Check Health API access on startup
            has_access, error_message = self.check_health_api_access()
            if not has_access:
                self.logger.warning(f"Health API access check failed: {error_message}")
            else:
                self.logger.info("AWS Health API client initialized successfully")
                
        except Exception as e:
            self.logger.error(f"Error initializing AWS Health client: {str(e)}")
            self.client = None

    def _retry_api_call(self, operation: str, **kwargs) -> Tuple[bool, Any, Optional[str]]:
        """Execute API call with retry logic."""
        max_retries = 3
        base_delay = 1
        
        for attempt in range(max_retries):
            try:
                if not self.client:
                    return False, None, "Health client not initialized"
                
                # Get the operation method
                operation_method = getattr(self.client, operation)
                result = operation_method(**kwargs)
                
                self.logger.debug(f"API call {operation} succeeded on attempt {attempt + 1}")
                return True, result, None
                
            except ClientError as e:
                error_code = e.response["Error"]["Code"]
                error_message = e.response["Error"]["Message"]
                
                # Don't retry on certain errors
                if error_code in ["SubscriptionRequiredException", "AccessDeniedException", "UnauthorizedException"]:
                    return False, None, f"{error_code}: {error_message}"
                
                # Retry on throttling and server errors
                if error_code in ["Throttling", "ThrottlingException", "ServiceUnavailable", "InternalError"]:
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        self.logger.warning(f"API call {operation} failed with {error_code}, retrying in {delay}s...")
                        time.sleep(delay)
                        continue
                
                return False, None, f"{error_code}: {error_message}"
                
            except Exception as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    self.logger.warning(f"API call {operation} failed with {str(e)}, retrying in {delay}s...")
                    time.sleep(delay)
                    continue
                
                return False, None, f"Unexpected error: {str(e)}"
        
        return False, None, f"Max retries ({max_retries}) exceeded"

    def check_health_api_access(self) -> Tuple[bool, Optional[str]]:
        """Check if we have access to AWS Health API."""
        success, result, error = self._retry_api_call(
            "describe_events",
            filter={"eventStatusCodes": ["open"]},
            maxResults=10  # Minimum value is 10
        )
        
        if success:
            return True, None
        
        if "SubscriptionRequiredException" in str(error):
            return False, "AWS Health API requires Business or Enterprise Support subscription"
        elif any(code in str(error) for code in ["AccessDeniedException", "UnauthorizedException"]):
            return False, "Insufficient permissions to access AWS Health API"
        else:
            return False, f"AWS Health API error: {error}"

    def check_org_health_access(self) -> Tuple[bool, Optional[str]]:
        """Check if AWS Health organization view is enabled."""
        success, result, error = self._retry_api_call("describe_health_service_status_for_organization")
        
        if not success:
            if "AccessDeniedException" in str(error):
                return False, (
                    "Insufficient permissions. "
                    "You need 'health:DescribeHealthServiceStatusForOrganization' permission. "
                    "Also, ensure you are calling from the organization's management account."
                )
            return False, f"Error checking organization health status: {error}"
        
        status = result.get("healthServiceAccessStatusForOrganization")
        
        if status == "ENABLED":
            return True, None
        elif status == "PENDING":
            return False, (
                "AWS Health organization view is pending activation. "
                "Please wait a few minutes and try again."
            )
        else:  # DISABLED or something else
            return False, (
                "AWS Health organization view is not enabled. "
                "Please enable it by calling EnableHealthServiceAccessForOrganization "
                "from your AWS management account."
            )

    def describe_events(self, **kwargs) -> Tuple[bool, Any, Optional[str]]:
        """Describe health events with retry logic."""
        return self._retry_api_call("describe_events", **kwargs)

    def describe_events_for_organization(self, **kwargs) -> Tuple[bool, Any, Optional[str]]:
        """Describe organization health events with retry logic."""
        return self._retry_api_call("describe_events_for_organization", **kwargs)

    def describe_affected_entities(self, **kwargs) -> Tuple[bool, Any, Optional[str]]:
        """Describe affected entities with retry logic."""
        return self._retry_api_call("describe_affected_entities", **kwargs)

    def describe_affected_entities_for_organization(self, **kwargs) -> Tuple[bool, Any, Optional[str]]:
        """Describe organization affected entities with retry logic."""
        return self._retry_api_call("describe_affected_entities_for_organization", **kwargs)

    def describe_event_details(self, **kwargs) -> Tuple[bool, Any, Optional[str]]:
        """Describe event details with retry logic."""
        return self._retry_api_call("describe_event_details", **kwargs)


# Global health client instance
health_client = HealthClient()
