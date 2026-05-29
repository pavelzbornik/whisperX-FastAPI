"""Unit tests for the OpenAPI documentation generation helpers."""

import json
from pathlib import Path

import pytest
import yaml
from fastapi import FastAPI

from app.docs import save_openapi_json


@pytest.mark.unit
def test_save_openapi_json_writes_consistent_json_and_yaml(tmp_path: Path) -> None:
    """Both spec files are written and decode to the same structure."""
    app = FastAPI(title="Test API")

    @app.get("/ping")
    def _ping() -> dict[str, str]:
        return {"status": "ok"}

    save_openapi_json(app, path=str(tmp_path))

    json_file = tmp_path / "openapi.json"
    yaml_file = tmp_path / "openapi.yaml"
    assert json_file.exists()
    assert yaml_file.exists()

    json_data = json.loads(json_file.read_text())
    yaml_data = yaml.safe_load(yaml_file.read_text())
    assert json_data == yaml_data
    assert "/ping" in json_data["paths"]


@pytest.mark.unit
def test_save_openapi_json_uses_indented_block_sequences(tmp_path: Path) -> None:
    """Block sequences are indented under their parent key (custom dumper)."""
    app = FastAPI(
        title="Test API",
        servers=[{"url": "https://a.example"}, {"url": "https://b.example"}],
    )

    @app.get("/ping")
    def _ping() -> dict[str, str]:
        return {"status": "ok"}

    save_openapi_json(app, path=str(tmp_path))
    content = (tmp_path / "openapi.yaml").read_text()

    # Indented style: "servers:\n  - url: ..." rather than the default indentless
    # "servers:\n- url: ...".
    assert "\n  - url:" in content
