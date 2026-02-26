"""Tests for security module."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from collabx_server.security import (
    verify_token_or_404,
    best_client_ip,
    clamp_headers,
    apply_redactions,
    decode_body_bytes,
)
from collabx_server.settings import Settings


def test_verify_token_valid():
    """Test token verification with valid token."""
    settings = Settings(token="valid_token_123")
    # Should not raise exception
    verify_token_or_404("valid_token_123", settings)


def test_verify_token_invalid():
    """Test token verification with invalid token."""
    settings = Settings(token="valid_token_123")
    with pytest.raises(HTTPException) as exc_info:
        verify_token_or_404("invalid_token", settings)
    assert exc_info.value.status_code == 404


def test_verify_token_multiple():
    """Test token verification with multiple valid tokens."""
    settings = Settings(token="token1,token2,token3")
    verify_token_or_404("token1", settings)
    verify_token_or_404("token2", settings)
    verify_token_or_404("token3", settings)
    
    with pytest.raises(HTTPException):
        verify_token_or_404("invalid", settings)


def test_clamp_headers():
    """Test header clamping to size limit."""
    headers = {
        "header1": "value1",
        "header2": "value2" * 1000,  # Long value
        "header3": "value3",
    }
    
    # Small limit should truncate
    result = clamp_headers(headers, max_total_bytes=50)
    assert len(result) < len(headers)
    
    # Large limit should keep all
    result = clamp_headers(headers, max_total_bytes=100000)
    assert len(result) == len(headers)


def test_apply_redactions():
    """Test redaction of sensitive patterns."""
    text = "password=secret123&token=abc&api_key=xyz"
    patterns = [r"password=[^&]+", r"token=[^&]+"]
    
    result = apply_redactions(text, patterns)
    assert "secret123" not in result
    assert "abc" not in result
    assert "[REDACTED]" in result
    assert "api_key=xyz" in result  # Not redacted


def test_apply_redactions_empty():
    """Test redaction with empty patterns."""
    text = "password=secret123"
    result = apply_redactions(text, [])
    assert result == text


def test_decode_body_bytes_utf8():
    """Test decoding UTF-8 body."""
    body = b'{"test": "data"}'
    text, b64 = decode_body_bytes(body)
    assert text == '{"test": "data"}'
    assert b64 is None


def test_decode_body_bytes_binary():
    """Test decoding binary body."""
    body = b'\x00\x01\x02\xff'
    text, b64 = decode_body_bytes(body)
    assert text is None
    assert b64 is not None
    assert len(b64) > 0
