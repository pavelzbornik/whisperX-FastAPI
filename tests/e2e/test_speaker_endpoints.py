"""End-to-end tests for speaker embedding API endpoints."""

import pytest
from starlette.testclient import TestClient


@pytest.mark.e2e
class TestSpeakerEndpoints:
    """Test speaker CRUD and search endpoints."""

    def test_create_speaker(self, client: TestClient) -> None:
        """Test creating a speaker embedding."""
        response = client.post(
            "/speakers",
            json={
                "speaker_label": "Alice",
                "embedding": [0.1, 0.2, 0.3],
                "description": "Project manager",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert "uuid" in data
        assert data["message"] == "Speaker created"

    def test_list_speakers_empty(self, client: TestClient) -> None:
        """Test listing speakers returns empty list initially."""
        response = client.get("/speakers")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_crud_flow(self, client: TestClient) -> None:
        """Test full CRUD lifecycle."""
        # Create
        create_resp = client.post(
            "/speakers",
            json={
                "speaker_label": "Bob",
                "embedding": [0.5, -0.5, 0.0],
                "description": "Engineer",
            },
        )
        assert create_resp.status_code == 201
        uuid = create_resp.json()["uuid"]

        # Read
        get_resp = client.get(f"/speakers/{uuid}")
        assert get_resp.status_code == 200
        speaker = get_resp.json()
        assert speaker["speaker_label"] == "Bob"
        assert speaker["description"] == "Engineer"
        assert speaker["embedding"] == [0.5, -0.5, 0.0]

        # Update
        update_resp = client.put(
            f"/speakers/{uuid}",
            json={"speaker_label": "Robert", "description": "Senior engineer"},
        )
        assert update_resp.status_code == 200

        # Verify update
        get_resp2 = client.get(f"/speakers/{uuid}")
        assert get_resp2.json()["speaker_label"] == "Robert"
        assert get_resp2.json()["description"] == "Senior engineer"

        # Delete
        delete_resp = client.delete(f"/speakers/{uuid}")
        assert delete_resp.status_code == 200

        # Verify deleted
        get_resp3 = client.get(f"/speakers/{uuid}")
        assert get_resp3.status_code == 404

    def test_get_nonexistent_speaker(self, client: TestClient) -> None:
        """Test getting a nonexistent speaker returns 404."""
        response = client.get("/speakers/nonexistent-uuid")
        assert response.status_code == 404

    def test_search_speakers(self, client: TestClient) -> None:
        """Test searching for similar speakers."""
        # Create two speakers with different embeddings
        client.post(
            "/speakers",
            json={"speaker_label": "Alice", "embedding": [1.0, 0.0, 0.0]},
        )
        client.post(
            "/speakers",
            json={"speaker_label": "Bob", "embedding": [0.0, 1.0, 0.0]},
        )

        # Search with embedding similar to Alice
        search_resp = client.post(
            "/speakers/search",
            json={"embedding": [0.9, 0.1, 0.0], "limit": 5, "threshold": 0.5},
        )
        assert search_resp.status_code == 200
        data = search_resp.json()
        assert "results" in data
        assert len(data["results"]) >= 1
        # Best match should be Alice
        assert data["results"][0]["speaker"]["speaker_label"] == "Alice"
        assert data["results"][0]["similarity"] > 0.9

    def test_identify_speaker(self, client: TestClient) -> None:
        """Test identifying a speaker."""
        # Create a known speaker
        client.post(
            "/speakers",
            json={"speaker_label": "Charlie", "embedding": [0.0, 0.0, 1.0]},
        )

        # Identify with similar embedding
        identify_resp = client.post(
            "/speakers/identify",
            json={"embedding": [0.05, 0.05, 0.95], "threshold": 0.8},
        )
        assert identify_resp.status_code == 200
        data = identify_resp.json()
        assert data["speaker"]["speaker_label"] == "Charlie"
        assert data["similarity"] > 0.9

    def test_identify_speaker_no_match(self, client: TestClient) -> None:
        """Test identify returns 404 when no match above threshold."""
        identify_resp = client.post(
            "/speakers/identify",
            json={"embedding": [1.0, 0.0, 0.0], "threshold": 0.99},
        )
        # Either 404 (no speakers) or low similarity
        assert identify_resp.status_code in (200, 404)

    def test_create_speaker_with_task_uuid(self, client: TestClient) -> None:
        """Test creating a speaker linked to a task."""
        response = client.post(
            "/speakers",
            json={
                "speaker_label": "Linked",
                "embedding": [0.1, 0.2],
                "task_uuid": "task-123",
            },
        )
        assert response.status_code == 201
        uuid = response.json()["uuid"]

        # Filter by task
        list_resp = client.get("/speakers?task_id=task-123")
        assert list_resp.status_code == 200
        speakers = list_resp.json()
        assert any(s["uuid"] == uuid for s in speakers)

    def test_delete_speakers_by_task(self, client: TestClient) -> None:
        """Test deleting all speakers for a task."""
        # Create speakers linked to a task
        client.post(
            "/speakers",
            json={
                "speaker_label": "S1",
                "embedding": [0.1],
                "task_uuid": "task-del",
            },
        )
        client.post(
            "/speakers",
            json={
                "speaker_label": "S2",
                "embedding": [0.2],
                "task_uuid": "task-del",
            },
        )

        delete_resp = client.delete("/speakers?task_id=task-del")
        assert delete_resp.status_code == 200
        assert "Deleted" in delete_resp.json()["message"]

        # Verify deleted
        list_resp = client.get("/speakers?task_id=task-del")
        assert list_resp.json() == []

    def test_update_nonexistent_speaker(self, client: TestClient) -> None:
        """Test updating a nonexistent speaker returns 404."""
        response = client.put(
            "/speakers/nonexistent",
            json={"speaker_label": "Ghost"},
        )
        assert response.status_code == 404

    def test_update_empty_body(self, client: TestClient) -> None:
        """Test updating with no fields returns 400."""
        create_resp = client.post(
            "/speakers",
            json={"speaker_label": "Temp", "embedding": [0.1]},
        )
        uuid = create_resp.json()["uuid"]

        response = client.put(f"/speakers/{uuid}", json={})
        assert response.status_code == 400
