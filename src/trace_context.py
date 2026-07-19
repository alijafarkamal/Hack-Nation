"""Request-scoped correlation id for cross-cutting tracing (contextvars, thread/async safe)."""

from __future__ import annotations

import contextvars

current_correlation_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "care-india_cid", default=None
)
