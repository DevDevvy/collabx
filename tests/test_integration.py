"""Integration tests for CollabX server."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from collabx_server.main import create_app
from collabx_server.settings import Settings


@pytest.fixture
def test_app():
    """Create test FastAPI app."""
    import os
    os.environ["COLLABX_TOKEN"] = "test_token_12345678"
    os.environ["COLLABX_DB_PATH"] = ":memory:"
    return create_app()


@pytest.fixture
def client(test_app):
    """Create test client."""
    return TestClient(test_app)


def test_healthz(client):
    """Test health check endpoint."""
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert "version" in data
    assert "uptime_seconds" in data


def test_collect_get(client):
    """Test GET callback collection."""
    response = client.get("/test_token_12345678/c?test=value&foo=bar")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert "id" in data


def test_collect_post_json(client):
    """Test POST callback with JSON body."""
    response = client.post(
        "/test_token_12345678/c",
        json={"message": "test", "data": {"nested": "value"}},
        headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert "id" in data


def test_collect_with_extra_path(client):
    """Test collection with extra path segments."""
    response = client.get("/test_token_12345678/c/extra/path/segments?param=value")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True


def test_get_logs(client):
    """Test logs endpoint."""
    # First, collect some events
    client.get("/test_token_12345678/c?event=1")
    client.post("/test_token_12345678/c", json={"event": 2})
    
    # Get logs
    response = client.get("/test_token_12345678/logs")
    assert response.status_code == 200
    data = response.json()
    assert "events" in data
    assert "next_after_id" in data
    assert "count" in data
    assert data["count"] > 0


def test_get_logs_with_filters(client):
    """Test logs endpoint with filters."""
    # Collect events with different methods
    client.get("/test_token_12345678/c/get-endpoint")
    client.post("/test_token_12345678/c/post-endpoint")
    
    # Filter by method
    response = client.get("/test_token_12345678/logs?method=GET")
    assert response.status_code == 200
    data = response.json()
    for event in data["events"]:
        assert event["method"] == "GET"
    
    # Filter by path
    response = client.get("/test_token_12345678/logs?path_contains=post")
    assert response.status_code == 200
    data = response.json()
    for event in data["events"]:
        assert "post" in event["path"]


def test_statistics(client):
    """Test statistics endpoint."""
    # Collect some events
    client.get("/test_token_12345678/c")
    client.post("/test_token_12345678/c")
    
    response = client.get("/test_token_12345678/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_events" in data
    assert "by_method" in data
    assert "unique_ips" in data
    assert data["total_events"] > 0


def test_export_json(client):
    """Test JSON export."""
    # Collect some events
    client.get("/test_token_12345678/c")
    
    response = client.get("/test_token_12345678/export?format=json")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert "collabx_export_" in response.headers["content-disposition"]


def test_export_csv(client):
    """Test CSV export."""
    # Collect some events
    client.get("/test_token_12345678/c")
    
    response = client.get("/test_token_12345678/export?format=csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    content = response.text
    assert "id,received_at,method" in content  # CSV header


def test_export_ndjson(client):
    """Test NDJSON export."""
    # Collect some events
    client.get("/test_token_12345678/c")
    
    response = client.get("/test_token_12345678/export?format=ndjson")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")


def test_invalid_token(client):
    """Test that invalid token returns 404."""
    response = client.get("/invalid_token_xyz/c")
    assert response.status_code == 404
    
    response = client.get("/invalid_token_xyz/logs")
    assert response.status_code == 404


def test_cleanup_endpoint(client):
    """Test cleanup endpoint."""
    # Collect some events
    client.get("/test_token_12345678/c")
    
    # Cleanup old events (with small days value for testing)
    response = client.delete("/test_token_12345678/cleanup?days=365")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert "deleted_count" in data


def test_pagination(client):
    """Test pagination of logs."""
    # Collect multiple events
    for i in range(10):
        client.get(f"/test_token_12345678/c?event={i}")
    
    # Get first page
    response = client.get("/test_token_12345678/logs?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert len(data["events"]) <= 5
    
    # Get next page
    next_id = data["next_after_id"]
    response = client.get(f"/test_token_12345678/logs?after_id={next_id}&limit=5")
    assert response.status_code == 200
    data2 = response.json()
    assert len(data2["events"]) <= 5
