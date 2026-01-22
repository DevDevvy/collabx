from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="COLLABX_", extra="ignore")

    # Comma-separated list supported (token rotation)
    token: str = Field(..., description="Required. Token(s) used in URL path. Comma-separated allowed.")
    db_path: str = Field(default="collabx.sqlite3", description="SQLite DB file path.")
    max_body_bytes: int = Field(default=256 * 1024, description="Max request body bytes to store.")
    max_header_bytes: int = Field(default=8 * 1024, description="Max total header bytes to store (approx).")
    header_allowlist: str = Field(
        default="origin,referer,user-agent,x-forwarded-for,x-real-ip,cf-connecting-ip,true-client-ip",
        description="Comma-separated headers to store (lowercase). Avoid auth/cookie.",
    )
    store_raw_body: bool = Field(default=True, description="Store request body (size-limited).")
    redact_patterns: str = Field(
        default="",
        description="Optional comma-separated regex patterns applied to query/body for redaction.",
    )
    service_name: str = Field(default="collabx", description="Display name.")

    def tokens(self) -> List[str]:
        return [t.strip() for t in self.token.split(",") if t.strip()]

    def header_allowlist_set(self) -> set[str]:
        return {h.strip().lower() for h in self.header_allowlist.split(",") if h.strip()}

    def redact_pattern_list(self) -> List[str]:
        return [p.strip() for p in self.redact_patterns.split(",") if p.strip()]
