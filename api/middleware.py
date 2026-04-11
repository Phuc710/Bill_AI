"""
API Key authentication + production request/response logging middleware.

Every inbound request is logged with:
  [request_id] METHOD /path | status=200 | 1234ms | ip=1.2.3.4 | user=uid
"""
from __future__ import annotations

import logging
import time
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from core.config import Config

log = logging.getLogger("billai.access")

# Paths that don't require an API key
_OPEN_PATHS = {"/", "/health", "/docs", "/redoc", "/openapi.json", "/favicon.ico"}


class AuthLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = uuid.uuid4().hex[:12]
        client_ip  = (request.client.host if request.client else "unknown")
        start      = time.perf_counter()

        # Attach for use in routes
        request.state.request_id = request_id

        # ── Auth check ────────────────────────────────────────────────────
        path = request.url.path
        if path not in _OPEN_PATHS and not path.startswith("/dashboard") and not path.startswith("/static"):
            api_key = request.headers.get("X-API-Key", "")
            if not api_key or api_key != Config.API_SECRET_KEY:
                masked = (api_key[:6] + "…") if len(api_key) >= 6 else "MISSING"
                log.warning(
                    f"[{request_id}] 401 UNAUTHORIZED | "
                    f"ip={client_ip} path={request.url.path} key={masked}"
                )
                return Response(
                    content='{"error":"Unauthorized","message":"Invalid or missing X-API-Key header"}',
                    status_code=401,
                    media_type="application/json",
                    headers={"X-Request-Id": request_id},
                )

        # ── Process request ───────────────────────────────────────────────
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Pipeline timing hint (injected by route nếu có)
        timing_hint = response.headers.get("X-Pipeline-Timing", "")
        extra = f" | {timing_hint}" if timing_hint else ""

        log.info(
            f"[{request_id}] {request.method} {request.url.path}"
            f" | {response.status_code} | {elapsed_ms:.0f}ms"
            f"{extra} | ip={client_ip}"
        )
        response.headers["X-Request-Id"]    = request_id
        response.headers["X-Response-Time"] = f"{elapsed_ms:.0f}ms"
        return response

