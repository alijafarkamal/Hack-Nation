"""Correlation id middleware: X-Request-Id or generate UUID; expose on request state."""

from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

CORR_HEADER = "X-Request-Id"
STATE_KEY = "correlation_id"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        raw = (request.headers.get(CORR_HEADER) or "").strip() or str(uuid.uuid4())
        cid = raw[:200]
        setattr(request.state, STATE_KEY, cid)
        response = await call_next(request)
        response.headers[CORR_HEADER] = getattr(request.state, STATE_KEY, cid)
        return response
