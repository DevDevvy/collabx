"""Tests for export functionality."""
from __future__ import annotations

import json
import csv
import io

from collabx_server.export import export_to_json, export_to_csv, export_to_ndjson


def test_export_to_json():
    """Test JSON export."""
    events = [
        {"id": 1, "method": "GET", "path": "/test"},
        {"id": 2, "method": "POST", "path": "/data"},
    ]
    
    result = export_to_json(events)
    parsed = json.loads(result)
    
    assert len(parsed) == 2
    assert parsed[0]["id"] == 1
    assert parsed[1]["method"] == "POST"


def test_export_to_csv():
    """Test CSV export."""
    events = [
        {
            "id": 1,
            "received_at": "2024-01-01T00:00:00Z",
            "method": "GET",
            "path": "/test",
            "query": "a=1",
            "client_ip": "127.0.0.1",
            "x_forwarded_for": "",
            "x_real_ip": "",
            "origin": "",
            "referer": "",
            "user_agent": "test",
            "content_type": "",
            "body_truncated": False,
        }
    ]
    
    result = export_to_csv(events)
    
    # Parse CSV
    reader = csv.DictReader(io.StringIO(result))
    rows = list(reader)
    
    assert len(rows) == 1
    assert rows[0]["id"] == "1"
    assert rows[0]["method"] == "GET"
    assert rows[0]["path"] == "/test"


def test_export_to_csv_empty():
    """Test CSV export with empty events."""
    result = export_to_csv([])
    assert result == ""


def test_export_to_ndjson():
    """Test NDJSON export."""
    events = [
        {"id": 1, "method": "GET"},
        {"id": 2, "method": "POST"},
    ]
    
    result = export_to_ndjson(events)
    lines = result.split('\n')
    
    assert len(lines) == 2
    assert json.loads(lines[0])["id"] == 1
    assert json.loads(lines[1])["id"] == 2
