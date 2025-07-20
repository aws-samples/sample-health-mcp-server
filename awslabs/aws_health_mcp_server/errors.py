"""Custom exceptions for AWS Health MCP Server."""


class HealthAPIError(Exception):
    """Base exception for AWS Health API errors."""

    pass


class HealthAPIAccessError(HealthAPIError):
    """Raised when there's no access to AWS Health API."""

    pass


class OrganizationHealthAccessError(HealthAPIError):
    """Raised when there's no access to AWS Health Organization features."""

    pass


class InvalidServiceError(HealthAPIError):
    """Raised when an invalid AWS service name is provided."""

    pass


class EventNotFoundError(HealthAPIError):
    """Raised when a requested health event is not found."""

    pass
