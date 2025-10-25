"""Audit logger for security-relevant events."""

import logging
from typing import Any, Optional

from app.core.logging.audit_events import AuditEvent, AuditEventType

# Get the audit logger
audit_logger = logging.getLogger("audit")


class AuditLogger:
    """Structured audit logging for security-relevant events.

    This logger provides a high-level API for logging audit events with
    consistent structure and metadata. All audit events are logged at
    INFO level and should never be filtered out.

    Audit logs include:
    - Event type and action
    - Resource type and ID
    - User ID and IP address
    - Request correlation ID
    - Timestamp (ISO 8601 format)
    - Additional event-specific details
    """

    @staticmethod
    def log_event(
        event_type: AuditEventType,
        resource_type: str,
        resource_id: str,
        action: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        request_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """Log an audit event with structured data.

        Args:
            event_type: Type of audit event
            resource_type: Type of resource (e.g., 'task', 'file')
            resource_id: Unique identifier for the resource
            action: Action performed (e.g., 'create', 'delete')
            user_id: User identifier (optional, defaults to 'anonymous')
            ip_address: Client IP address (optional, defaults to 'unknown')
            request_id: Request correlation ID (optional, defaults to 'unknown')
            details: Additional event-specific details (optional)
        """
        event = AuditEvent(
            event_type=event_type,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            user_id=user_id or "anonymous",
            ip_address=ip_address or "unknown",
            request_id=request_id or "unknown",
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
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> None:
        """Log task creation event.

        Args:
            task_id: Unique task identifier
            task_type: Type of task (e.g., 'transcription', 'diarization')
            user_id: User identifier (optional)
            ip_address: Client IP address (optional)
            request_id: Request correlation ID (optional)
        """
        AuditLogger.log_event(
            event_type=AuditEventType.TASK_CREATED,
            resource_type="task",
            resource_id=task_id,
            action="create",
            user_id=user_id,
            ip_address=ip_address,
            request_id=request_id,
            details={"task_type": task_type},
        )

    @staticmethod
    def log_task_completed(
        task_id: str,
        duration: float,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> None:
        """Log task completion event.

        Args:
            task_id: Unique task identifier
            duration: Task duration in seconds
            user_id: User identifier (optional)
            ip_address: Client IP address (optional)
            request_id: Request correlation ID (optional)
        """
        AuditLogger.log_event(
            event_type=AuditEventType.TASK_COMPLETED,
            resource_type="task",
            resource_id=task_id,
            action="complete",
            user_id=user_id,
            ip_address=ip_address,
            request_id=request_id,
            details={"duration_seconds": duration},
        )

    @staticmethod
    def log_task_deleted(
        task_id: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        request_id: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> None:
        """Log task deletion event.

        Args:
            task_id: Unique task identifier
            user_id: User identifier (optional)
            ip_address: Client IP address (optional)
            request_id: Request correlation ID (optional)
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
            user_id=user_id,
            ip_address=ip_address,
            request_id=request_id,
            details=details,
        )

    @staticmethod
    def log_file_uploaded(
        file_name: str,
        file_size: int,
        content_type: Optional[str] = None,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> None:
        """Log file upload event.

        Args:
            file_name: Name of uploaded file
            file_size: Size in bytes
            content_type: MIME type (optional)
            user_id: User identifier (optional)
            ip_address: Client IP address (optional)
            request_id: Request correlation ID (optional)
        """
        details: dict[str, Any] = {"file_size_bytes": file_size}
        if content_type:
            details["content_type"] = content_type

        AuditLogger.log_event(
            event_type=AuditEventType.FILE_UPLOADED,
            resource_type="file",
            resource_id=file_name,
            action="upload",
            user_id=user_id,
            ip_address=ip_address,
            request_id=request_id,
            details=details,
        )

    @staticmethod
    def log_file_downloaded(
        file_name: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> None:
        """Log file download event.

        Args:
            file_name: Name of downloaded file
            user_id: User identifier (optional)
            ip_address: Client IP address (optional)
            request_id: Request correlation ID (optional)
        """
        AuditLogger.log_event(
            event_type=AuditEventType.FILE_DOWNLOADED,
            resource_type="file",
            resource_id=file_name,
            action="download",
            user_id=user_id,
            ip_address=ip_address,
            request_id=request_id,
        )

    @staticmethod
    def log_file_deleted(
        file_name: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> None:
        """Log file deletion event.

        Args:
            file_name: Name of deleted file
            user_id: User identifier (optional)
            ip_address: Client IP address (optional)
            request_id: Request correlation ID (optional)
        """
        AuditLogger.log_event(
            event_type=AuditEventType.FILE_DELETED,
            resource_type="file",
            resource_id=file_name,
            action="delete",
            user_id=user_id,
            ip_address=ip_address,
            request_id=request_id,
        )
