from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any, Dict, Optional


class EventOut(BaseModel):
    id: int
    received_at: str

    method: str
    path: str
    query: str

    client_ip: str = ""
    x_forwarded_for: str = ""
    x_real_ip: str = ""

    origin: str = ""
    referer: str = ""
    user_agent: str = ""

    headers: Dict[str, str] = Field(default_factory=dict)

    body_text: Optional[str] = None
    body_b64: Optional[str] = None
    body_truncated: bool = False
    content_type: str = ""
