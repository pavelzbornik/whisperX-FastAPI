"""Locust load test user for the WhisperX-FastAPI task endpoints."""

from locust import HttpUser, between, task


class TaskAPIUser(HttpUser):
    """Simulates concurrent API users hitting DB-backed endpoints."""

    wait_time = between(0.1, 0.5)

    @task(5)
    def list_tasks(self) -> None:
        """GET /tasks — exercises DB pool on every request."""
        self.client.get("/task/all")

    @task(3)
    def health_ready(self) -> None:
        """GET /health/ready — DB connectivity check."""
        self.client.get("/health/ready")

    @task(2)
    def health(self) -> None:
        """GET /health — lightweight liveness check."""
        self.client.get("/health")
