from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Dict, Optional, Any

from fastapi import FastAPI, Request, Response, Query
from fastapi.responses import JSONResponse, StreamingResponse

from .settings import Settings
from .storage import EventStore
from .sse import SSEBroadcaster
from .security import (
    verify_token_or_404,
    best_client_ip,
    clamp_headers,
    apply_redactions,
    decode_body_bytes,
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_app() -> FastAPI:
    settings = Settings()  # reads env
    store = EventStore(settings.db_path)
    broadcaster = SSEBroadcaster(queue_size=200)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await store.connect()
        app.state.settings = settings
        app.state.store = store
        app.state.broadcaster = broadcaster
        yield
        await store.close()

    app = FastAPI(title="collabx collector", lifespan=lifespan)

    @app.get("/healthz")
    async def healthz():
        return {"ok": True, "service": settings.service_name, "subscribers": broadcaster.subscriber_count}

    async def _handle_collect(request: Request, token: str, extra_path: str = "") -> Response:
        verify_token_or_404(token, settings)

        path = f"/{token}/c"
        if extra_path:
            path += f"/{extra_path}"

        query_raw = request.url.query or ""
        query = apply_redactions(query_raw, settings.redact_pattern_list())

        client_ip, xff, xri = best_client_ip(request)

        allow = settings.header_allowlist_set()
        headers: Dict[str, str] = {}
        for k, v in request.headers.items():
            kl = k.lower()
            if kl in allow:
                headers[kl] = v
        headers = clamp_headers(headers, settings.max_header_bytes)

        origin = request.headers.get("origin", "")
        referer = request.headers.get("referer", "")
        user_agent = request.headers.get("user-agent", "")
        content_type = request.headers.get("content-type", "")

        body_text: Optional[str] = None
        body_b64: Optional[str] = None
        body_truncated = False

        if request.method in ("POST", "PUT", "PATCH") and settings.store_raw_body:
            body = await request.body()
            if body and len(body) > settings.max_body_bytes:
                body = body[: settings.max_body_bytes]
                body_truncated = True

            bt, bb = decode_body_bytes(body)
            if bt is not None:
                bt = apply_redactions(bt, settings.redact_pattern_list())
            body_text, body_b64 = bt, bb

        received_at = utc_now_iso()
        event_id = await store.add_event(
            received_at=received_at,
            method=request.method,
            path=path,
            query=query,
            client_ip=client_ip,
            x_forwarded_for=xff,
            x_real_ip=xri,
            origin=origin,
            referer=referer,
            user_agent=user_agent,
            headers=headers,
            body_text=body_text,
            body_b64=body_b64,
            body_truncated=body_truncated,
            content_type=content_type,
        )

        event: Dict[str, Any] = {
            "id": event_id,
            "received_at": received_at,
            "method": request.method,
            "path": path,
            "query": query,
            "client_ip": client_ip,
            "x_forwarded_for": xff,
            "x_real_ip": xri,
            "origin": origin,
            "referer": referer,
            "user_agent": user_agent,
            "headers": headers,
            "body_text": body_text,
            "body_b64": body_b64,
            "body_truncated": body_truncated,
            "content_type": content_type,
        }

        # JSON line to stdout (useful on cloud providers)
        print(
            json.dumps(
                {
                    "id": event_id,
                    "received_at": received_at,
                    "method": request.method,
                    "path": path,
                    "query": query,
                    "client_ip": client_ip,
                    "origin": origin,
                    "referer": referer,
                    "user_agent": user_agent,
                    "body_truncated": body_truncated,
                    "content_type": content_type,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )

        broadcaster.publish_nowait(event)
        return JSONResponse({"ok": True, "id": event_id})

    @app.get("/{token}/c")
    async def collect_get(request: Request, token: str):
        return await _handle_collect(request, token)

    @app.post("/{token}/c")
    async def collect_post(request: Request, token: str):
        return await _handle_collect(request, token)

    @app.get("/{token}/c/{extra_path:path}")
    async def collect_get_path(request: Request, token: str, extra_path: str):
        return await _handle_collect(request, token, extra_path=extra_path)

    @app.post("/{token}/c/{extra_path:path}")
    async def collect_post_path(request: Request, token: str, extra_path: str):
        return await _handle_collect(request, token, extra_path=extra_path)

    @app.get("/{token}/logs")
    async def get_logs(
        token: str,
        after_id: int = Query(default=0, ge=0),
        limit: int = Query(default=50, ge=1, le=200),
    ):
        verify_token_or_404(token, settings)
        events, last_id = await store.get_events(after_id=after_id, limit=limit)
        return {"events": events, "next_after_id": last_id}

    @app.get("/{token}/events")
    async def sse_events(token: str):
        """Opt-in real-time stream (SSE)."""
        verify_token_or_404(token, settings)
        q = broadcaster.subscribe()

        async def gen():
            yield ":ok\n\n"
            try:
                while True:
                    try:
                        evt = await asyncio.wait_for(q.get(), timeout=15.0)
                        yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"
                    except asyncio.TimeoutError:
                        yield ":keepalive\n\n"
            finally:
                broadcaster.unsubscribe(q)

        headers = {
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
        return StreamingResponse(gen(), media_type="text/event-stream", headers=headers)

    return app


app = create_app()
