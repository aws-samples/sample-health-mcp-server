"""Data models for AWS Health events."""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class HealthEvent:
    """Represents an AWS Health event."""

    arn: str
    service: str
    event_type_code: str
    status_code: str
    region: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    last_updated_time: Optional[datetime] = None
    event_type_category: Optional[str] = None
    event_scope_code: Optional[str] = None
    description: Optional[str] = None


@dataclass
class AffectedEntity:
    """Represents an entity affected by a health event."""

    entity_arn: str
    entity_value: str
    status_code: str
    last_updated_time: Optional[datetime] = None
    entity_url: Optional[str] = None
    entity_metadata: Optional[Dict] = None


@dataclass
class OrganizationEvent:
    """Represents an organization-wide health event."""

    event: HealthEvent
    affected_accounts: List[str]


@dataclass
class EventSummary:
    """Summary of health events by status."""

    total_events: int
    open_events: int
    upcoming_events: int
    closed_events: int
    events_by_service: Dict[str, int]
    events_by_region: Dict[str, int]
