"""AWS Health API client with lazy initialization."""

import time
import logging
from typing import Tuple, Optional, Any

import boto3
from botocore.exceptions import ClientError
from botocore.config import Config as BotocoreConfig

from .config import Config

logger = logging.getLogger(__name__)


class HealthClient:
    """AWS Health API client wrapper with lazy init and retry logic."""

    def __init__(self):
        self._client = None

    @property
    def client(self):
        """Lazily create the boto3 Health client on first use."""
        if self._client is None:
            boto_config = BotocoreConfig(
                region_name="us-east-1",  # Health API is us-east-1 only
                retries={"max_attempts": 3, "mode": "adaptive"},
                read_timeout=Config.HEALTH_API_TIMEOUT,
                connect_timeout=10,
            )
            session = boto3.Session(profile_name=Config.AWS_PROFILE)
            self._client = session.client("health", config=boto_config)
            logger.info("AWS Health API client initialized")
        return self._client

    def check_health_api_access(self) -> Tuple[bool, Optional[str]]:
        """Check if we have access to AWS Health API."""
        try:
            self.client.describe_events(filter={"eventStatusCodes": ["open"]}, maxResults=10)
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

    def check_org_health_access(self) -> Tuple[bool, Optional[str]]:
        """Check if AWS Health organization view is enabled."""
        try:
            result = self.client.describe_health_service_status_for_organization()
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


# Global singleton — boto3 client is NOT created until first tool call
health_client = HealthClient()
