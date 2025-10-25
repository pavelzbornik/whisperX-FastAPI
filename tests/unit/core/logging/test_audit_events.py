"""Tests for audit event definitions."""

from datetime import datetime, timezone


from app.core.logging.audit_events import AuditEvent, AuditEventType


class TestAuditEventType:
    """Test audit event type enum."""

    def test_event_type_values(self) -> None:
        """Test that all event types have correct string values."""
        assert AuditEventType.TASK_CREATED.value == "task.created"
        assert AuditEventType.TASK_COMPLETED.value == "task.completed"
        assert AuditEventType.TASK_DELETED.value == "task.deleted"
        assert AuditEventType.FILE_UPLOADED.value == "file.uploaded"
        assert AuditEventType.FILE_DOWNLOADED.value == "file.downloaded"
        assert AuditEventType.FILE_DELETED.value == "file.deleted"
        assert AuditEventType.AUTH_SUCCESS.value == "auth.success"
        assert AuditEventType.AUTH_FAILURE.value == "auth.failure"
        assert AuditEventType.CONFIG_CHANGED.value == "config.changed"
        assert AuditEventType.ERROR_OCCURRED.value == "error.occurred"


class TestAuditEvent:
    """Test audit event dataclass."""

    def test_audit_event_creation(self) -> None:
        """Test creating an audit event with required fields."""
        event = AuditEvent(
            event_type=AuditEventType.TASK_CREATED,
            resource_type="task",
            resource_id="task-123",
            action="create",
        )

        assert event.event_type == AuditEventType.TASK_CREATED
        assert event.resource_type == "task"
        assert event.resource_id == "task-123"
        assert event.action == "create"
        assert event.user_id == "anonymous"
        assert event.ip_address == "unknown"
        assert event.request_id == "unknown"
        assert isinstance(event.timestamp, datetime)
        assert event.details == {}

    def test_audit_event_with_optional_fields(self) -> None:
        """Test creating an audit event with all fields."""
        timestamp = datetime.now(timezone.utc)
        event = AuditEvent(
            event_type=AuditEventType.FILE_UPLOADED,
            resource_type="file",
            resource_id="audio.mp3",
            action="upload",
            user_id="user-456",
            ip_address="192.168.1.1",
            request_id="req-789",
            timestamp=timestamp,
            details={"file_size_bytes": 1024, "content_type": "audio/mpeg"},
        )

        assert event.user_id == "user-456"
        assert event.ip_address == "192.168.1.1"
        assert event.request_id == "req-789"
        assert event.timestamp == timestamp
        assert event.details["file_size_bytes"] == 1024
        assert event.details["content_type"] == "audio/mpeg"

    def test_audit_event_to_dict(self) -> None:
        """Test converting audit event to dictionary."""
        event = AuditEvent(
            event_type=AuditEventType.TASK_COMPLETED,
            resource_type="task",
            resource_id="task-999",
            action="complete",
            user_id="user-123",
            details={"duration_seconds": 45.5},
        )

        event_dict = event.to_dict()

        assert event_dict["event_type"] == "task.completed"
        assert event_dict["resource_type"] == "task"
        assert event_dict["resource_id"] == "task-999"
        assert event_dict["action"] == "complete"
        assert event_dict["user_id"] == "user-123"
        assert event_dict["ip_address"] == "unknown"
        assert event_dict["request_id"] == "unknown"
        assert "timestamp" in event_dict
        assert isinstance(event_dict["timestamp"], str)  # ISO format
        assert event_dict["details"]["duration_seconds"] == 45.5

    def test_audit_event_timestamp_format(self) -> None:
        """Test that timestamp is properly formatted as ISO 8601."""
        event = AuditEvent(
            event_type=AuditEventType.TASK_DELETED,
            resource_type="task",
            resource_id="task-111",
            action="delete",
        )

        event_dict = event.to_dict()
        timestamp_str = event_dict["timestamp"]

        # Verify it's a valid ISO 8601 format
        parsed_timestamp = datetime.fromisoformat(timestamp_str)
        assert isinstance(parsed_timestamp, datetime)

    def test_audit_event_defaults(self) -> None:
        """Test default values for optional fields."""
        event = AuditEvent(
            event_type=AuditEventType.CONFIG_CHANGED,
            resource_type="config",
            resource_id="app-settings",
            action="update",
        )

        # Verify defaults
        assert event.user_id == "anonymous"
        assert event.ip_address == "unknown"
        assert event.request_id == "unknown"
        assert event.details == {}
        assert event.timestamp.tzinfo == timezone.utc
