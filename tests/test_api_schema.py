"""Validate dist/api JSON files against JSON Schema contracts.

Each of the 5 API endpoints must conform to its schema.
Deleting a field or changing a type is a hard fail.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError, validate

API_DIR = Path("dist/api")
SCHEMA_DIR = Path("schemas/api/v2")

ENDPOINTS = {
    "manifest.json": "manifest.schema.json",
    "temperature_latest.json": "temperature_latest.schema.json",
    "indicators_latest.json": "indicators_latest.schema.json",
    "divergence_latest.json": "divergence_latest.schema.json",
}


def _load_schema(name: str) -> dict:
    path = SCHEMA_DIR / name
    assert path.exists(), f"Schema not found: {path}"
    return json.loads(path.read_text())


@pytest.mark.parametrize("endpoint,schema_file", ENDPOINTS.items())
def test_api_schema_valid(endpoint, schema_file):
    """Each API JSON file must validate against its schema."""
    json_path = API_DIR / endpoint
    if not json_path.exists():
        pytest.skip(f"{endpoint} not found in dist/api/")

    schema = _load_schema(schema_file)
    data = json.loads(json_path.read_text())
    validate(data, schema, cls=Draft202012Validator)


def test_temperature_history_schema():
    """temperature_history.json.gz must validate against its schema (decompressed)."""
    import gzip

    gz_path = API_DIR / "temperature_history.json.gz"
    if not gz_path.exists():
        pytest.skip("temperature_history.json.gz not found in dist/api/")

    schema = _load_schema("temperature_history.schema.json")
    with gzip.open(gz_path) as f:
        data = json.loads(f.read())
    validate(data, schema, cls=Draft202012Validator)


def test_schema_deletion_detected():
    """Removing a required field should fail validation."""
    schema = _load_schema("manifest.schema.json")

    manifest_path = API_DIR / "manifest.json"
    if manifest_path.exists():
        data = json.loads(manifest_path.read_text())
    else:
        # Synthetic baseline so the test runs without a built dist/ artifact
        data = {
            "schema_version": "2.0.0",
            "asof": "2026-01-01",
            "endpoints": {"manifest": {"path": "manifest.json", "description": "manifest"}},
        }

    # Valid baseline
    validate(data, schema, cls=Draft202012Validator)

    # Remove a required field — must fail
    corrupted = {k: v for k, v in data.items() if k != "endpoints"}
    with pytest.raises(ValidationError):
        validate(corrupted, schema, cls=Draft202012Validator)
