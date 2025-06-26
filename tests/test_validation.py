"""Tests for enhanced file validation and error handling."""

import io
import pytest
from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient

from app.files import validate_extension, validate_file_size, validate_upload_file, validate_file_content
from app.main import app


client = TestClient(app)


class TestFileValidation:
    """Test cases for file validation functions."""

    def test_validate_extension_valid(self):
        """Test extension validation with valid extensions."""
        # Should not raise any exception
        validate_extension("test.mp3", {".mp3", ".wav"})
        validate_extension("test.WAV", {".mp3", ".wav"})  # Case insensitive
        
    def test_validate_extension_invalid(self):
        """Test extension validation with invalid extensions."""
        with pytest.raises(HTTPException) as exc_info:
            validate_extension("test.txt", {".mp3", ".wav"})
        assert exc_info.value.status_code == 400
        assert "Invalid file extension" in exc_info.value.detail
        
    def test_validate_extension_empty_filename(self):
        """Test extension validation with empty filename."""
        with pytest.raises(HTTPException) as exc_info:
            validate_extension("", {".mp3", ".wav"})
        assert exc_info.value.status_code == 400
        assert "Filename cannot be empty" in exc_info.value.detail
        
    def test_validate_file_size_valid(self):
        """Test file size validation with valid size."""
        # Should not raise any exception
        validate_file_size(1024 * 1024)  # 1MB
        validate_file_size(100 * 1024 * 1024)  # 100MB
        
    def test_validate_file_size_invalid(self):
        """Test file size validation with oversized file."""
        with pytest.raises(HTTPException) as exc_info:
            validate_file_size(600 * 1024 * 1024)  # 600MB > 500MB default limit
        assert exc_info.value.status_code == 413
        assert "exceeds maximum allowed size" in exc_info.value.detail
        
    def test_validate_file_content_empty(self):
        """Test file content validation with empty content."""
        with pytest.raises(HTTPException) as exc_info:
            validate_file_content(b"", "test.mp3")
        assert exc_info.value.status_code == 400
        assert "File content cannot be empty" in exc_info.value.detail
        
    def test_validate_file_content_valid_mp3(self):
        """Test file content validation with MP3 magic number."""
        mp3_content = b"ID3" + b"\x00" * 100  # MP3 with ID3 header
        # Should not raise exception but may log warning
        validate_file_content(mp3_content, "test.mp3")
        
    def test_validate_upload_file_valid(self):
        """Test upload file validation with valid file."""
        content = b"ID3" + b"\x00" * 1000  # Small MP3-like content
        file_obj = io.BytesIO(content)
        upload_file = UploadFile(filename="test.mp3", file=file_obj)
        
        # Should not raise exception
        validate_upload_file(upload_file)
        
    def test_validate_upload_file_no_filename(self):
        """Test upload file validation without filename."""
        content = b"test content"
        file_obj = io.BytesIO(content)
        upload_file = UploadFile(filename=None, file=file_obj)
        
        with pytest.raises(HTTPException) as exc_info:
            validate_upload_file(upload_file)
        assert exc_info.value.status_code == 400
        assert "Filename is required" in exc_info.value.detail


class TestMiddleware:
    """Test cases for middleware functionality."""
    
    def test_correlation_id_header(self):
        """Test that correlation ID is added to response headers."""
        response = client.get("/health")
        assert response.status_code == 200
        assert "X-Correlation-ID" in response.headers
        assert "X-Response-Time" in response.headers
        
    def test_custom_correlation_id(self):
        """Test that custom correlation ID from request is preserved."""
        custom_id = "custom-test-id-123"
        response = client.get("/health", headers={"X-Correlation-ID": custom_id})
        assert response.status_code == 200
        assert response.headers["X-Correlation-ID"] == custom_id


class TestEnhancedHealthChecks:
    """Test cases for enhanced health check endpoints."""
    
    def test_health_check_enhanced(self):
        """Test enhanced health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "ok"
        assert "correlation_id" in data
        assert "timestamp" in data
        assert data["message"] == "Service is running"
        
    def test_liveness_check_enhanced(self):
        """Test enhanced liveness check endpoint."""
        response = client.get("/health/live")
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "ok"
        assert "correlation_id" in data
        assert "timestamp" in data
        assert "uptime_seconds" in data
        assert data["message"] == "Application is live"
        
    def test_readiness_check_comprehensive(self):
        """Test comprehensive readiness check endpoint."""
        response = client.get("/health/ready")
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "ok"
        assert "correlation_id" in data
        assert "timestamp" in data
        assert "components" in data
        assert "system_metrics" in data
        assert "gpu_info" in data
        
        # Check components structure
        components = data["components"]
        assert "database" in components
        assert "system_resources" in components
        
        # Check system metrics structure
        system_metrics = data["system_metrics"]
        if "error" not in system_metrics:
            assert "cpu_percent" in system_metrics
            assert "cpu_count" in system_metrics
            assert "memory" in system_metrics
            assert "disk" in system_metrics
            
        # Check GPU info structure
        gpu_info = data["gpu_info"]
        assert "available" in gpu_info
        if gpu_info["available"]:
            assert "devices" in gpu_info
        else:
            assert "reason" in gpu_info


class TestErrorHandling:
    """Test cases for error handling improvements."""
    
    def test_large_file_rejection(self):
        """Test that large files are rejected by middleware."""
        # Create a mock large file content header
        large_content = "a" * (600 * 1024 * 1024)  # 600MB string
        
        # This test simulates the content-length header check
        # In a real scenario, the middleware would catch this before processing
        with pytest.raises(Exception):
            # We can't easily test the middleware directly, but we can test
            # the validation function
            from app.files import validate_file_size
            validate_file_size(600 * 1024 * 1024)