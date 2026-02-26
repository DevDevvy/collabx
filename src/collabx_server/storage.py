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
CREATE INDEX IF NOT EXISTS idx_events_id ON events(id);
CREATE INDEX IF NOT EXISTS idx_events_received_at ON events(received_at);
CREATE INDEX IF NOT EXISTS idx_events_method ON events(method);
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

    async def get_events(
        self,
        after_id: int,
        limit: int,
        method: Optional[str] = None,
        path_contains: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Get events with optional filtering.
        
        Args:
            after_id: Return events with ID > this value
            limit: Maximum number of events to return
            method: Optional filter by HTTP method
            path_contains: Optional filter for paths containing this string
            
        Returns:
            Tuple of (events list, last_id)
        """
        assert self.db is not None, "DB not connected"
        limit = max(1, min(limit, 200))
        after_id = max(0, int(after_id))

        # Build query with optional filters
        conditions = ["id > ?"]
        params = [after_id]
        
        if method:
            conditions.append("method = ?")
            params.append(method.upper())
        
        if path_contains:
            conditions.append("path LIKE ?")
            params.append(f"%{path_contains}%")
        
        where_clause = " AND ".join(conditions)
        
        cur = await self.db.execute(
            f"""
            SELECT
              id, received_at, method, path, query,
              client_ip, x_forwarded_for, x_real_ip,
              origin, referer, user_agent,
              headers_json, body_text, body_b64, body_truncated, content_type
            FROM events
            WHERE {where_clause}
            ORDER BY id ASC
            LIMIT ?
            """,
            (*params, limit),
        )
        rows = await cur.fetchall()

        events: List[Dict[str, Any]] = []
        last_id = after_id
        for r in rows:
            (
                eid,
                received_at,
                method_val,
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
                    method=method_val,
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
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get collection statistics.
        
        Returns:
            Dictionary with statistics about collected events
        """
        assert self.db is not None, "DB not connected"
        
        # Total count
        cur = await self.db.execute("SELECT COUNT(*) FROM events")
        row = await cur.fetchone()
        total_count = row[0] if row else 0
        
        # Count by method
        cur = await self.db.execute(
            "SELECT method, COUNT(*) as count FROM events GROUP BY method ORDER BY count DESC"
        )
        rows = await cur.fetchall()
        by_method = {method: count for method, count in rows}
        
        # Recent events (last 24 hours)
        cur = await self.db.execute(
            "SELECT COUNT(*) FROM events WHERE received_at > datetime('now', '-1 day')"
        )
        row = await cur.fetchone()
        last_24h = row[0] if row else 0
        
        # First and last event timestamps
        cur = await self.db.execute(
            "SELECT MIN(received_at), MAX(received_at) FROM events"
        )
        row = await cur.fetchone()
        first_event = row[0] if row and row[0] else None
        last_event = row[1] if row and row[1] else None
        
        # Unique IPs
        cur = await self.db.execute(
            "SELECT COUNT(DISTINCT client_ip) FROM events WHERE client_ip != ''"
        )
        row = await cur.fetchone()
        unique_ips = row[0] if row else 0
        
        return {
            "total_events": total_count,
            "events_last_24h": last_24h,
            "unique_ips": unique_ips,
            "by_method": by_method,
            "first_event": first_event,
            "last_event": last_event,
        }
    
    async def cleanup_old_events(self, days: int) -> int:
        """Delete events older than the specified number of days.
        
        Args:
            days: Delete events older than this many days
            
        Returns:
            Number of deleted events
        """
        assert self.db is not None, "DB not connected"
        
        cur = await self.db.execute(
            "DELETE FROM events WHERE received_at < datetime('now', ? || ' days')",
            (f"-{days}",)
        )
        await self.db.commit()
        
        return cur.rowcount if cur.rowcount else 0
