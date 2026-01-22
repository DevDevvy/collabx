from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

import aiosqlite


CREATE_SQL = """
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  received_at TEXT NOT NULL,
  method TEXT NOT NULL,
  path TEXT NOT NULL,
  query TEXT NOT NULL,
  client_ip TEXT NOT NULL,
  x_forwarded_for TEXT NOT NULL,
  x_real_ip TEXT NOT NULL,
  origin TEXT NOT NULL,
  referer TEXT NOT NULL,
  user_agent TEXT NOT NULL,
  headers_json TEXT NOT NULL,
  body_text TEXT,
  body_b64 TEXT,
  body_truncated INTEGER NOT NULL,
  content_type TEXT NOT NULL
);
"""


class EventStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.db: Optional[aiosqlite.Connection] = None

    async def connect(self) -> None:
        self.db = await aiosqlite.connect(self.db_path)
        await self.db.execute("PRAGMA journal_mode=WAL;")
        await self.db.execute("PRAGMA synchronous=NORMAL;")
        await self.db.execute(CREATE_SQL)
        await self.db.commit()

    async def close(self) -> None:
        if self.db:
            await self.db.close()
            self.db = None

    async def add_event(
        self,
        *,
        received_at: str,
        method: str,
        path: str,
        query: str,
        client_ip: str,
        x_forwarded_for: str,
        x_real_ip: str,
        origin: str,
        referer: str,
        user_agent: str,
        headers: Dict[str, str],
        body_text: Optional[str],
        body_b64: Optional[str],
        body_truncated: bool,
        content_type: str,
    ) -> int:
        assert self.db is not None, "DB not connected"
        headers_json = json.dumps(headers, ensure_ascii=False)
        cur = await self.db.execute(
            """
            INSERT INTO events (
              received_at, method, path, query,
              client_ip, x_forwarded_for, x_real_ip,
              origin, referer, user_agent,
              headers_json, body_text, body_b64, body_truncated, content_type
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                received_at,
                method,
                path,
                query,
                client_ip,
                x_forwarded_for,
                x_real_ip,
                origin,
                referer,
                user_agent,
                headers_json,
                body_text,
                body_b64,
                1 if body_truncated else 0,
                content_type,
            ),
        )
        await self.db.commit()
        return int(cur.lastrowid)

    async def get_events(self, after_id: int, limit: int) -> Tuple[List[Dict[str, Any]], int]:
        assert self.db is not None, "DB not connected"
        limit = max(1, min(limit, 200))
        after_id = max(0, int(after_id))

        cur = await self.db.execute(
            """
            SELECT
              id, received_at, method, path, query,
              client_ip, x_forwarded_for, x_real_ip,
              origin, referer, user_agent,
              headers_json, body_text, body_b64, body_truncated, content_type
            FROM events
            WHERE id > ?
            ORDER BY id ASC
            LIMIT ?
            """,
            (after_id, limit),
        )
        rows = await cur.fetchall()

        events: List[Dict[str, Any]] = []
        last_id = after_id
        for r in rows:
            (
                eid,
                received_at,
                method,
                path,
                query,
                client_ip,
                x_forwarded_for,
                x_real_ip,
                origin,
                referer,
                user_agent,
                headers_json,
                body_text,
                body_b64,
                body_truncated,
                content_type,
            ) = r
            last_id = int(eid)
            try:
                headers = json.loads(headers_json) if headers_json else {}
            except json.JSONDecodeError:
                headers = {}
            events.append(
                dict(
                    id=int(eid),
                    received_at=received_at,
                    method=method,
                    path=path,
                    query=query,
                    client_ip=client_ip,
                    x_forwarded_for=x_forwarded_for,
                    x_real_ip=x_real_ip,
                    origin=origin,
                    referer=referer,
                    user_agent=user_agent,
                    headers=headers,
                    body_text=body_text,
                    body_b64=body_b64,
                    body_truncated=bool(body_truncated),
                    content_type=content_type,
                )
            )
        return events, last_id
