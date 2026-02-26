from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Dict, Optional, Any

from fastapi import FastAPI, Request, Response, Query
from fastapi.responses import JSONResponse, StreamingResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware

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
from .middleware import RateLimitMiddleware
from .export import export_to_json, export_to_csv, export_to_ndjson
from .logging_config import get_logger, log_event

logger = get_logger(__name__)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_app() -> FastAPI:
    settings = Settings()  # reads env
    store = EventStore(settings.db_path)
    broadcaster = SSEBroadcaster(queue_size=200)
    start_time = time.time()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("Starting CollabX server", extra={"db_path": settings.db_path})
        await store.connect()
        app.state.settings = settings
        app.state.store = store
        app.state.broadcaster = broadcaster
        app.state.start_time = start_time
        yield
        logger.info("Shutting down CollabX server")
        await store.close()

    app = FastAPI(
        title="CollabX Collector",
        description="Ephemeral HTTP callback collector for security testing and webhooks",
        version="0.4.0",
        lifespan=lifespan
    )
    
    # Add CORS middleware
    if settings.enable_cors:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins_list(),
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    # Add rate limiting middleware
    if settings.enable_rate_limit:
        app.add_middleware(RateLimitMiddleware, requests_per_minute=settings.rate_limit_per_minute)

    @app.get("/healthz", tags=["Health"])
    async def healthz(request: Request):
        """Health check endpoint with service status."""
        uptime = time.time() - request.app.state.start_time
        return {
            "ok": True,
            "service": settings.service_name,
            "version": "0.4.0",
            "uptime_seconds": int(uptime),
            "subscribers": broadcaster.subscriber_count,
        }

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

        # Structured logging
        log_event(logger, event)
        
        # Also print JSON line to stdout (useful on cloud providers)
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

    @app.get("/{token}/c", tags=["Collector"])
    async def collect_get(request: Request, token: str):
        """Collect GET request callback."""
        return await _handle_collect(request, token)

    @app.post("/{token}/c", tags=["Collector"])
    async def collect_post(request: Request, token: str):
        """Collect POST request callback."""
        return await _handle_collect(request, token)

    @app.get("/{token}/c/{extra_path:path}", tags=["Collector"])
    async def collect_get_path(request: Request, token: str, extra_path: str):
        """Collect GET request callback with extra path."""
        return await _handle_collect(request, token, extra_path=extra_path)

    @app.post("/{token}/c/{extra_path:path}", tags=["Collector"])
    async def collect_post_path(request: Request, token: str, extra_path: str):
        """Collect POST request callback with extra path."""
        return await _handle_collect(request, token, extra_path=extra_path)

    @app.get("/{token}/logs", tags=["Logs"])
    async def get_logs(
        token: str,
        after_id: int = Query(default=0, ge=0, description="Start cursor (event ID)"),
        limit: int = Query(default=50, ge=1, le=200, description="Max events to return"),
        method: Optional[str] = Query(default=None, description="Filter by HTTP method (GET, POST, etc.)"),
        path_contains: Optional[str] = Query(default=None, description="Filter paths containing this string"),
    ):
        """Get collected events with optional filtering."""
        verify_token_or_404(token, settings)
        events, last_id = await store.get_events(
            after_id=after_id,
            limit=limit,
            method=method,
            path_contains=path_contains
        )
        return {"events": events, "next_after_id": last_id, "count": len(events)}

    @app.get("/{token}/events", tags=["Logs"])
    async def sse_events(token: str):
        """Opt-in real-time stream (SSE)."""
        verify_token_or_404(token, settings)
        logger.debug(f"SSE client connected for token: {token[:8]}...")
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
                logger.debug(f"SSE client disconnected for token: {token[:8]}...")

        headers = {
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
        return StreamingResponse(gen(), media_type="text/event-stream", headers=headers)
    
    @app.get("/{token}/stats", tags=["Statistics"])
    async def get_statistics(token: str):
        """Get collection statistics."""
        verify_token_or_404(token, settings)
        stats = await store.get_statistics()
        return stats
    
    @app.get("/{token}/export", tags=["Export"])
    async def export_logs(
        token: str,
        format: str = Query(default="json", regex="^(json|csv|ndjson)$", description="Export format"),
        after_id: int = Query(default=0, ge=0, description="Start cursor (event ID)"),
        limit: int = Query(default=1000, ge=1, le=10000, description="Max events to export"),
    ):
        """Export collected events in various formats."""
        verify_token_or_404(token, settings)
        events, _ = await store.get_events(after_id=after_id, limit=limit)
        
        if format == "csv":
            content = export_to_csv(events)
            media_type = "text/csv"
            filename = f"collabx_export_{int(time.time())}.csv"
        elif format == "ndjson":
            content = export_to_ndjson(events)
            media_type = "application/x-ndjson"
            filename = f"collabx_export_{int(time.time())}.ndjson"
        else:  # json
            content = export_to_json(events)
            media_type = "application/json"
            filename = f"collabx_export_{int(time.time())}.json"
        
        return PlainTextResponse(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    
    @app.delete("/{token}/cleanup", tags=["Management"])
    async def cleanup_old_events(
        token: str,
        days: int = Query(default=7, ge=1, le=365, description="Delete events older than N days"),
    ):
        """Delete old events to manage storage."""
        verify_token_or_404(token, settings)
        deleted_count = await store.cleanup_old_events(days=days)
        logger.info(f"Cleaned up {deleted_count} events older than {days} days")
        return {"ok": True, "deleted_count": deleted_count, "days": days}

    return app


app = create_app()
