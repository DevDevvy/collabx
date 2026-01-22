from __future__ import annotations

import asyncio
from typing import Any, Dict, Set


class SSEBroadcaster:
    """Tiny in-memory pub/sub for SSE.

    Best-effort: if a subscriber is slow and its queue fills, we drop events for that subscriber.
    """

    def __init__(self, queue_size: int = 200):
        self._subs: Set[asyncio.Queue] = set()
        self._queue_size = queue_size

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=self._queue_size)
        self._subs.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subs.discard(q)

    def publish_nowait(self, event: Dict[str, Any]) -> None:
        for q in list(self._subs):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass

    @property
    def subscriber_count(self) -> int:
        return len(self._subs)
