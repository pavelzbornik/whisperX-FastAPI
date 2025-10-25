"""Tests for audit logger."""

from unittest.mock import patch


from app.core.logging.audit_events import AuditEventType
from app.core.logging.audit_logger import AuditLogger


class TestAuditLogger:
    """Test audit logger functionality."""

    def test_log_event(self) -> None:
        """Test logging a generic audit event."""
        with patch("app.core.logging.audit_logger.audit_logger") as mock_logger:
            AuditLogger.log_event(
                event_type=AuditEventType.TASK_CREATED,
                resource_type="task",
                resource_id="task-123",
                action="create",
                user_id="user-456",
                ip_address="192.168.1.1",
                request_id="req-789",
                details={"task_type": "transcription"},
            )

            # Verify logger was called
            mock_logger.info.assert_called_once()
            # Check the log message format string and arguments
            call_args = mock_logger.info.call_args
            # Format string is call_args[0][0], arguments are call_args[0][1:]
            assert call_args[0][1] == "create"  # action
            assert call_args[0][2] == "task"  # resource_type
            assert call_args[0][3] == "task-123"  # resource_id
            # Check extra data
            extra = call_args[1]["extra"]
            assert extra["event_type"] == "task.created"
            assert extra["user_id"] == "user-456"
            assert extra["ip_address"] == "192.168.1.1"

    def test_log_event_with_defaults(self) -> None:
        """Test logging an event with default values."""
        with patch("app.core.logging.audit_logger.audit_logger") as mock_logger:
            AuditLogger.log_event(
                event_type=AuditEventType.FILE_UPLOADED,
                resource_type="file",
                resource_id="audio.mp3",
                action="upload",
            )

            # Verify defaults were applied
            call_args = mock_logger.info.call_args
            extra = call_args[1]["extra"]
            assert extra["user_id"] == "anonymous"
            assert extra["ip_address"] == "unknown"
            assert extra["request_id"] == "unknown"
            assert extra["details"] == {}

    def test_log_task_created(self) -> None:
        """Test logging task creation."""
        with patch("app.core.logging.audit_logger.audit_logger") as mock_logger:
            AuditLogger.log_task_created(
                task_id="task-999",
                task_type="transcription",
                user_id="user-123",
                ip_address="10.0.0.1",
                request_id="req-abc",
            )

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            extra = call_args[1]["extra"]
            assert extra["event_type"] == "task.created"
            assert extra["resource_type"] == "task"
            assert extra["resource_id"] == "task-999"
            assert extra["action"] == "create"
            assert extra["details"]["task_type"] == "transcription"

    def test_log_task_completed(self) -> None:
        """Test logging task completion."""
        with patch("app.core.logging.audit_logger.audit_logger") as mock_logger:
            AuditLogger.log_task_completed(
                task_id="task-888",
                duration=45.5,
                user_id="user-456",
            )

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            extra = call_args[1]["extra"]
            assert extra["event_type"] == "task.completed"
            assert extra["details"]["duration_seconds"] == 45.5

    def test_log_task_deleted(self) -> None:
        """Test logging task deletion."""
        with patch("app.core.logging.audit_logger.audit_logger") as mock_logger:
            AuditLogger.log_task_deleted(
                task_id="task-777",
                user_id="user-789",
                reason="User requested deletion",
            )

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            extra = call_args[1]["extra"]
            assert extra["event_type"] == "task.deleted"
            assert extra["details"]["reason"] == "User requested deletion"

    def test_log_task_deleted_without_reason(self) -> None:
        """Test logging task deletion without reason."""
        with patch("app.core.logging.audit_logger.audit_logger") as mock_logger:
            AuditLogger.log_task_deleted(task_id="task-666")

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            extra = call_args[1]["extra"]
            assert extra["event_type"] == "task.deleted"
            assert "reason" not in extra["details"]

    def test_log_file_uploaded(self) -> None:
        """Test logging file upload."""
        with patch("app.core.logging.audit_logger.audit_logger") as mock_logger:
            AuditLogger.log_file_uploaded(
                file_name="audio.mp3",
                file_size=1024000,
                content_type="audio/mpeg",
                user_id="user-123",
                ip_address="172.16.0.1",
            )

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            extra = call_args[1]["extra"]
            assert extra["event_type"] == "file.uploaded"
            assert extra["resource_id"] == "audio.mp3"
            assert extra["details"]["file_size_bytes"] == 1024000
            assert extra["details"]["content_type"] == "audio/mpeg"

    def test_log_file_uploaded_without_content_type(self) -> None:
        """Test logging file upload without content type."""
        with patch("app.core.logging.audit_logger.audit_logger") as mock_logger:
            AuditLogger.log_file_uploaded(
                file_name="audio.mp3",
                file_size=1024000,
            )

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            extra = call_args[1]["extra"]
            assert "content_type" not in extra["details"]

    def test_log_file_downloaded(self) -> None:
        """Test logging file download."""
        with patch("app.core.logging.audit_logger.audit_logger") as mock_logger:
            AuditLogger.log_file_downloaded(
                file_name="result.json",
                user_id="user-789",
                ip_address="192.168.1.100",
            )

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            extra = call_args[1]["extra"]
            assert extra["event_type"] == "file.downloaded"
            assert extra["action"] == "download"

    def test_log_file_deleted(self) -> None:
        """Test logging file deletion."""
        with patch("app.core.logging.audit_logger.audit_logger") as mock_logger:
            AuditLogger.log_file_deleted(
                file_name="old_file.wav",
                user_id="user-999",
            )

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            extra = call_args[1]["extra"]
            assert extra["event_type"] == "file.deleted"
            assert extra["action"] == "delete"

    def test_audit_events_always_at_info_level(self) -> None:
        """Test that all audit events are logged at INFO level."""
        with patch("app.core.logging.audit_logger.audit_logger") as mock_logger:
            # Test all audit methods
            AuditLogger.log_task_created("task-1", "type1")
            AuditLogger.log_task_completed("task-2", 10.0)
            AuditLogger.log_task_deleted("task-3")
            AuditLogger.log_file_uploaded("file1.mp3", 1024)
            AuditLogger.log_file_downloaded("file2.mp3")
            AuditLogger.log_file_deleted("file3.mp3")

            # All should call info() method
            assert mock_logger.info.call_count == 6
            # None should call other levels
            assert mock_logger.debug.call_count == 0
            assert mock_logger.warning.call_count == 0
            assert mock_logger.error.call_count == 0
