"""Audit event definitions for structured audit logging."""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class AuditEventType(str, Enum):
    """Types of audit events."""

    TASK_CREATED = "task.created"
    TASK_COMPLETED = "task.completed"
    TASK_DELETED = "task.deleted"
    FILE_UPLOADED = "file.uploaded"
    FILE_DOWNLOADED = "file.downloaded"
    FILE_DELETED = "file.deleted"
    AUTH_SUCCESS = "auth.success"
    AUTH_FAILURE = "auth.failure"
    CONFIG_CHANGED = "config.changed"
    ERROR_OCCURRED = "error.occurred"


@dataclass
class AuditEvent:
    """Structured audit event for security-relevant operations.

    Attributes:
        event_type: Type of audit event
        resource_type: Type of resource being accessed (e.g., 'task', 'file')
        resource_id: Unique identifier for the resource
        action: Action performed on the resource (e.g., 'create', 'delete')
        user_id: User identifier (defaults to 'anonymous')
        ip_address: Client IP address (defaults to 'unknown')
        request_id: Request correlation ID (defaults to 'unknown')
        timestamp: Event timestamp in UTC
        details: Additional event-specific details
    """

    event_type: AuditEventType
    resource_type: str
    resource_id: str
    action: str
    user_id: str = "anonymous"
    ip_address: str = "unknown"
    request_id: str = "unknown"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert audit event to dictionary for logging.

        Returns:
            Dictionary representation of the audit event
        """
        event_dict = asdict(self)
        event_dict["event_type"] = self.event_type.value
        event_dict["timestamp"] = self.timestamp.isoformat()
        return event_dict
