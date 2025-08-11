"""Tests for the task router module."""

import asyncio
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.routers.task import delete_task, get_all_tasks_status, get_transcription_status
from app.schemas import Metadata, Response, Result, ResultTasks, TaskSimple, TaskStatus

client = TestClient(app)


class TestGetAllTasksStatus:
    """Test cases for get_all_tasks_status endpoint."""

    @patch("app.routers.task.get_all_tasks_status_from_db")
    @pytest.mark.asyncio
    async def test_get_all_tasks_status_success(self, mock_get_all_tasks):
        """Test successful retrieval of all tasks status."""
        # Create proper TaskSimple objects
        task1 = TaskSimple(
            identifier="task-1",
            status=TaskStatus.completed.value,
            task_type="transcription", 
            language="en",
            file_name="test.mp3",
            error=None,
            url=None,
            duration=10.5
        )
        task2 = TaskSimple(
            identifier="task-2", 
            status=TaskStatus.processing.value,
            task_type="diarization",
            language="en",
            file_name="test2.wav", 
            error=None,
            url=None,
            duration=None
        )
        
        mock_tasks = ResultTasks(tasks=[task1, task2])
        mock_get_all_tasks.return_value = mock_tasks
        
        mock_session = Mock()
        
        result = await get_all_tasks_status(mock_session)
        
        assert result == mock_tasks
        assert len(result.tasks) == 2
        assert result.tasks[0].identifier == "task-1"
        assert result.tasks[1].identifier == "task-2"
        mock_get_all_tasks.assert_called_once_with(mock_session)

    @patch("app.routers.task.get_all_tasks_status_from_db")
    @pytest.mark.asyncio
    async def test_get_all_tasks_status_empty(self, mock_get_all_tasks):
        """Test retrieval when no tasks exist."""
        mock_get_all_tasks.return_value = ResultTasks(tasks=[])
        
        mock_session = Mock()
        result = await get_all_tasks_status(mock_session)
        
        assert result.tasks == []
        mock_get_all_tasks.assert_called_once_with(mock_session)


class TestGetTranscriptionStatus:
    """Test cases for get_transcription_status endpoint."""

    @patch("app.routers.task.get_task_status_from_db")
    @pytest.mark.asyncio
    async def test_get_transcription_status_found(self, mock_get_task_status):
        """Test successful retrieval of a specific task status."""
        # Create proper Result object
        metadata = Metadata(
            task_type="transcription",
            task_params={"model": "tiny"},
            language="en",
            file_name="test.mp3",
            url=None,
            duration=15.0
        )
        
        mock_result = Result(
            status=TaskStatus.completed.value,
            result={"text": "test transcription"},
            metadata=metadata,
            error=None
        )
        mock_get_task_status.return_value = mock_result
        
        mock_session = Mock()
        identifier = "task-123"
        
        result = await get_transcription_status(identifier, mock_session)
        
        assert result == mock_result
        assert result.status == TaskStatus.completed.value
        mock_get_task_status.assert_called_once_with(identifier, mock_session)

    @patch("app.routers.task.get_task_status_from_db")
    @pytest.mark.asyncio
    async def test_get_transcription_status_not_found(self, mock_get_task_status):
        """Test retrieval of non-existent task."""
        mock_get_task_status.return_value = None
        
        mock_session = Mock()
        identifier = "non-existent-task"
        
        with pytest.raises(HTTPException) as exc_info:
            await get_transcription_status(identifier, mock_session)
        
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Identifier not found"
        mock_get_task_status.assert_called_once_with(identifier, mock_session)

    @patch("app.routers.task.get_task_status_from_db")
    @pytest.mark.asyncio
    async def test_get_transcription_status_processing(self, mock_get_task_status):
        """Test retrieval of processing task."""
        metadata = Metadata(
            task_type="transcription",
            task_params=None,
            language="en",
            file_name="processing.mp3",
            url=None,
            duration=None
        )
        
        mock_result = Result(
            status=TaskStatus.processing.value,
            result=None,
            metadata=metadata,
            error=None
        )
        mock_get_task_status.return_value = mock_result
        
        mock_session = Mock()
        identifier = "task-processing"
        
        result = await get_transcription_status(identifier, mock_session)
        
        assert result.status == TaskStatus.processing.value
        assert result.result is None

    def test_get_transcription_status_endpoint_not_found(self):
        """Test the endpoint directly via HTTP for not found case."""
        with patch("app.routers.task.get_task_status_from_db") as mock_get_task_status:
            mock_get_task_status.return_value = None
            
            response = client.get("/task/non-existent")
            
            assert response.status_code == 404
            data = response.json()
            assert data["detail"] == "Identifier not found"


class TestDeleteTask:
    """Test cases for delete_task endpoint."""

    @patch("app.routers.task.delete_task_from_db")
    @pytest.mark.asyncio
    async def test_delete_task_success(self, mock_delete_task):
        """Test successful task deletion."""
        mock_delete_task.return_value = True
        
        mock_session = Mock()
        identifier = "task-to-delete"
        
        result = await delete_task(identifier, mock_session)
        
        assert isinstance(result, Response)
        assert result.identifier == identifier
        assert result.message == "Task deleted"
        mock_delete_task.assert_called_once_with(identifier, mock_session)

    @patch("app.routers.task.delete_task_from_db")
    @pytest.mark.asyncio
    async def test_delete_task_not_found(self, mock_delete_task):
        """Test deletion of non-existent task."""
        mock_delete_task.return_value = False
        
        mock_session = Mock()
        identifier = "non-existent-task"
        
        with pytest.raises(HTTPException) as exc_info:
            await delete_task(identifier, mock_session)
        
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Task not found"
        mock_delete_task.assert_called_once_with(identifier, mock_session)

    def test_delete_task_endpoint_success(self):
        """Test the delete endpoint directly via HTTP for successful case."""
        with patch("app.routers.task.delete_task_from_db") as mock_delete_task:
            mock_delete_task.return_value = True
            
            response = client.delete("/task/test-task/delete")
            
            assert response.status_code == 200
            data = response.json()
            assert data["identifier"] == "test-task"
            assert data["message"] == "Task deleted"

    def test_delete_task_endpoint_not_found(self):
        """Test the delete endpoint directly via HTTP for not found case."""
        with patch("app.routers.task.delete_task_from_db") as mock_delete_task:
            mock_delete_task.return_value = False
            
            response = client.delete("/task/non-existent/delete")
            
            assert response.status_code == 404
            data = response.json()
            assert data["detail"] == "Task not found"


class TestTaskRouterIntegration:
    """Integration tests for the task router."""

    def test_router_endpoints_exist(self):
        """Test that all expected endpoints are available."""
        # Test that endpoints return expected status codes (not 404)
        with patch("app.routers.task.get_all_tasks_status_from_db") as mock_get_all:
            mock_get_all.return_value = ResultTasks(tasks=[])
            response = client.get("/task/all")
            assert response.status_code == 200

    def test_router_tags(self):
        """Test that endpoints have correct tags for documentation."""
        # This is more of a documentation test - verifying the API structure
        # The tags should be present in the OpenAPI schema
        openapi_schema = app.openapi()
        
        # Find task-related endpoints
        task_endpoints = []
        for path, methods in openapi_schema["paths"].items():
            if "/task/" in path:
                for method, details in methods.items():
                    if "tags" in details:
                        task_endpoints.extend(details["tags"])
        
        # Verify that "Tasks Management" tag is used
        assert "Tasks Management" in task_endpoints