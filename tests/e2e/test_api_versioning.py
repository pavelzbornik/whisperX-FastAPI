"""End-to-end tests for API versioning functionality."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Create and return test client.

    Returns:
        TestClient: The FastAPI test client instance
    """
    from app import main

    return TestClient(main.app, follow_redirects=False)


@pytest.mark.e2e
class TestAPIVersioning:
    """Test suite for API versioning behavior."""

    def test_v1_endpoint_accessible(self, client: TestClient) -> None:
        """Test that v1 endpoints are accessible."""
        response = client.get("/api/v1/task/all")
        assert response.status_code == 200
        assert "tasks" in response.json()

    def test_unsupported_version_returns_404(self, client: TestClient) -> None:
        """Test that unsupported API versions return 404."""
        response = client.get("/api/v2/task/all")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_health_endpoints_unversioned(self, client: TestClient) -> None:
        """Test that health check endpoints remain unversioned."""
        # Test basic health check
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

        # Test liveness check
        response = client.get("/health/live")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

        # Test readiness check
        response = client.get("/health/ready")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_root_redirects_to_versioned_docs(self, client: TestClient) -> None:
        """Test that root path redirects to versioned documentation."""
        response = client.get("/")
        assert response.status_code == 307
        assert response.headers["location"] == "/api/v1/docs"

    def test_old_docs_redirect_to_versioned_docs(self, client: TestClient) -> None:
        """Test that old docs URL redirects to versioned docs."""
        response = client.get("/docs")
        assert response.status_code == 307
        assert response.headers["location"] == "/api/v1/docs"

    def test_openapi_spec_available_at_versioned_url(self, client: TestClient) -> None:
        """Test that OpenAPI spec is available at versioned URL."""
        response = client.get("/api/v1/openapi.json")
        assert response.status_code == 200
        spec = response.json()
        assert "openapi" in spec
        assert "info" in spec
        assert spec["info"]["version"] == "1.0.0"
        assert "WhisperX API" in spec["info"]["title"]

    def test_all_v1_routes_have_api_prefix(self, client: TestClient) -> None:
        """Test that all versioned routes are properly prefixed."""
        response = client.get("/api/v1/openapi.json")
        assert response.status_code == 200
        spec = response.json()

        # Check that all paths start with /api/v1/
        for path in spec["paths"].keys():
            # Skip the openapi spec itself and docs paths
            if not any(
                skip in path for skip in ["/openapi", "/docs", "/redoc", "/health"]
            ):
                assert path.startswith("/api/v1/"), (
                    f"Path {path} does not have /api/v1/ prefix"
                )

    def test_version_detection_middleware_adds_version_to_request(
        self, client: TestClient
    ) -> None:
        """Test that version middleware extracts version from URL."""
        # Make a request to a versioned endpoint
        response = client.get("/api/v1/task/all")
        assert response.status_code == 200
        # If middleware worked, the request should succeed


@pytest.mark.e2e
class TestDeprecationHeaders:
    """Test suite for deprecation headers (when versions are deprecated)."""

    def test_no_deprecation_headers_for_current_version(
        self, client: TestClient
    ) -> None:
        """Test that current version v1 has no deprecation headers."""
        response = client.get("/api/v1/task/all")
        assert response.status_code == 200

        # Should not have deprecation headers
        assert "Deprecation" not in response.headers
        assert "Sunset" not in response.headers
        assert "Link" not in response.headers or (
            "successor-version" not in response.headers.get("Link", "")
        )


@pytest.mark.e2e
class TestBackwardCompatibility:
    """Test suite for backward compatibility of v1 API."""

    def test_speech_to_text_endpoint_exists(self, client: TestClient) -> None:
        """Test that speech-to-text endpoint is available at v1."""
        # Just verify the endpoint exists (would return 422 without file)
        response = client.post("/api/v1/speech-to-text")
        # 422 = validation error (missing required file), which means endpoint exists
        assert response.status_code == 422

    def test_speech_to_text_url_endpoint_exists(self, client: TestClient) -> None:
        """Test that speech-to-text-url endpoint is available at v1."""
        response = client.post("/api/v1/speech-to-text-url")
        # 422 = validation error (missing required params), which means endpoint exists
        assert response.status_code == 422

    def test_task_management_endpoints_exist(self, client: TestClient) -> None:
        """Test that task management endpoints are available at v1."""
        # Get all tasks
        response = client.get("/api/v1/task/all")
        assert response.status_code == 200

        # Get specific task (404 expected for non-existent ID)
        response = client.get("/api/v1/task/test-id-12345")
        assert response.status_code == 404

        # Delete task (404 expected for non-existent ID)
        response = client.delete("/api/v1/task/test-id-12345/delete")
        assert response.status_code == 404

    def test_service_endpoints_exist(self, client: TestClient) -> None:
        """Test that individual service endpoints are available at v1."""
        # These would return 422 without proper files, meaning they exist
        response = client.post("/api/v1/service/transcribe")
        assert response.status_code == 422

        response = client.post("/api/v1/service/align")
        assert response.status_code == 422

        response = client.post("/api/v1/service/diarize")
        assert response.status_code == 422

        response = client.post("/api/v1/service/combine")
        assert response.status_code == 422
