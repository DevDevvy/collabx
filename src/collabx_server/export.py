"""Export functionality for CollabX logs."""
from __future__ import annotations

import csv
import io
import json
from typing import Any


def export_to_json(events: list[dict[str, Any]]) -> str:
    """Export events to JSON format.
    
    Args:
        events: List of event dictionaries
        
    Returns:
        JSON string representation
    """
    return json.dumps(events, indent=2, ensure_ascii=False)


def export_to_csv(events: list[dict[str, Any]]) -> str:
    """Export events to CSV format.
    
    Args:
        events: List of event dictionaries
        
    Returns:
        CSV string representation
    """
    if not events:
        return ""
        
    output = io.StringIO()
    
    # Define CSV columns
    fieldnames = [
        'id', 'received_at', 'method', 'path', 'query',
        'client_ip', 'x_forwarded_for', 'x_real_ip',
        'origin', 'referer', 'user_agent', 'content_type',
        'body_truncated'
    ]
    
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
    writer.writeheader()
    
    for event in events:
        # Flatten the event, excluding complex fields like headers
        row = {k: v for k, v in event.items() if k in fieldnames}
        writer.writerow(row)
    
    return output.getvalue()


def export_to_ndjson(events: list[dict[str, Any]]) -> str:
    """Export events to NDJSON (newline-delimited JSON) format.
    
    Args:
        events: List of event dictionaries
        
    Returns:
        NDJSON string representation
    """
    lines = [json.dumps(event, ensure_ascii=False) for event in events]
    return '\n'.join(lines)
