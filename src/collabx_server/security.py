from __future__ import annotations

import base64
import re
from typing import Dict, Tuple, Optional, List

from fastapi import HTTPException, Request
from .settings import Settings


def verify_token_or_404(token_in_path: str, settings: Settings) -> None:
    # Use 404 to reduce noise and avoid giving hints.
    if token_in_path not in set(settings.tokens()):
        raise HTTPException(status_code=404, detail="Not found")


def best_client_ip(request: Request) -> Tuple[str, str, str]:
    # Common proxy headers; store chain for forensics
    xff = request.headers.get("x-forwarded-for", "")
    xri = request.headers.get("x-real-ip", "")
    cf = request.headers.get("cf-connecting-ip", "")
    tci = request.headers.get("true-client-ip", "")

    # Prefer the left-most public-ish IP in XFF when present
    chosen = ""
    if xff:
        # XFF can be "client, proxy1, proxy2"
        chosen = xff.split(",")[0].strip()
    elif cf:
        chosen = cf.strip()
    elif tci:
        chosen = tci.strip()
    elif xri:
        chosen = xri.strip()
    elif request.client and request.client.host:
        chosen = request.client.host

    return chosen or "", xff, xri


def clamp_headers(headers: Dict[str, str], max_total_bytes: int) -> Dict[str, str]:
    # Rough safeguard: truncate if total bytes exceed max_total_bytes
    out: Dict[str, str] = {}
    total = 0
    for k, v in headers.items():
        kv = f"{k}:{v}"
        total += len(kv.encode("utf-8", errors="ignore"))
        if total > max_total_bytes:
            break
        out[k] = v
    return out


def apply_redactions(text: str, patterns: List[str]) -> str:
    if not patterns or not text:
        return text
    redacted = text
    for pat in patterns:
        try:
            redacted = re.sub(pat, "[REDACTED]", redacted, flags=re.IGNORECASE)
        except re.error:
            # Ignore invalid regex rather than breaking the collector
            continue
    return redacted


def decode_body_bytes(body: bytes) -> Tuple[Optional[str], Optional[str]]:
    if body is None:
        return None, None
    try:
        return body.decode("utf-8"), None
    except UnicodeDecodeError:
        return None, base64.b64encode(body).decode("ascii")
