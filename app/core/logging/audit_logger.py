"""Audit logger for security-relevant events."""

import logging
from typing import Any

from app.core.logging.audit_events import AuditEvent, AuditEventType
from app.core.logging.context import get_request_context

# Get the audit logger
audit_logger = logging.getLogger("audit")


class AuditLogger:
    """Structured audit logging for security-relevant events.

    Request-scoped fields (``user_id``, ``ip_address``, ``request_id``)
    are read automatically from the request context set by middleware.
    Explicit overrides are accepted but should rarely be needed.
    """

    @staticmethod
    def log_event(
        event_type: AuditEventType,
        resource_type: str,
        resource_id: str,
        action: str,
        user_id: str | None = None,
        ip_address: str | None = None,
        request_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Log an audit event with structured data.

        Context fields fall back to the request context when not
        provided explicitly.

        Args:
            event_type: Type of audit event
            resource_type: Type of resource (e.g., 'task', 'file')
            resource_id: Unique identifier for the resource
            action: Action performed (e.g., 'create', 'delete')
            user_id: User identifier (optional, from context or 'anonymous')
            ip_address: Client IP address (optional, from context or 'unknown')
            request_id: Request correlation ID (optional, from context or 'unknown')
            details: Additional event-specific details (optional)
        """
        ctx = get_request_context()

        event = AuditEvent(
            event_type=event_type,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            user_id=user_id or ctx.get("user_id") or "anonymous",
            ip_address=ip_address or ctx.get("ip_address") or "unknown",
            request_id=request_id or ctx.get("request_id") or "unknown",
            details=details or {},
        )

        # Log as structured data using extra parameter
        audit_logger.info(
            "Audit: %s on %s/%s",
            event.action,
            event.resource_type,
            event.resource_id,
            extra=event.to_dict(),
        )

    @staticmethod
    def log_task_created(
        task_id: str,
        task_type: str,
    ) -> None:
        """Log task creation event.

        Args:
            task_id: Unique task identifier
            task_type: Type of task (e.g., 'transcription', 'diarization')
        """
        AuditLogger.log_event(
            event_type=AuditEventType.TASK_CREATED,
            resource_type="task",
            resource_id=task_id,
            action="create",
            details={"task_type": task_type},
        )

    @staticmethod
    def log_task_completed(
        task_id: str,
        duration: float,
    ) -> None:
        """Log task completion event.

        Args:
            task_id: Unique task identifier
            duration: Task duration in seconds
        """
        AuditLogger.log_event(
            event_type=AuditEventType.TASK_COMPLETED,
            resource_type="task",
            resource_id=task_id,
            action="complete",
            details={"duration_seconds": duration},
        )

    @staticmethod
    def log_task_deleted(
        task_id: str,
        reason: str | None = None,
    ) -> None:
        """Log task deletion event.

        Args:
            task_id: Unique task identifier
            reason: Deletion reason (optional)
        """
        details: dict[str, Any] = {}
        if reason:
            details["reason"] = reason

        AuditLogger.log_event(
            event_type=AuditEventType.TASK_DELETED,
            resource_type="task",
            resource_id=task_id,
            action="delete",
            details=details,
        )

    @staticmethod
    def log_file_uploaded(
        file_name: str,
        file_size: int,
        content_type: str | None = None,
    ) -> None:
        """Log file upload event.

        Args:
            file_name: Name of uploaded file
            file_size: Size in bytes
            content_type: MIME type (optional)
        """
        details: dict[str, Any] = {"file_size_bytes": file_size}
        if content_type:
            details["content_type"] = content_type

        AuditLogger.log_event(
            event_type=AuditEventType.FILE_UPLOADED,
            resource_type="file",
            resource_id=file_name,
            action="upload",
            details=details,
        )

    @staticmethod
    def log_file_downloaded(
        file_name: str,
    ) -> None:
        """Log file download event.

        Args:
            file_name: Name of downloaded file
        """
        AuditLogger.log_event(
            event_type=AuditEventType.FILE_DOWNLOADED,
            resource_type="file",
            resource_id=file_name,
            action="download",
        )

    @staticmethod
    def log_file_deleted(
        file_name: str,
    ) -> None:
        """Log file deletion event.

        Args:
            file_name: Name of deleted file
        """
        AuditLogger.log_event(
            event_type=AuditEventType.FILE_DELETED,
            resource_type="file",
            resource_id=file_name,
            action="delete",
        )
