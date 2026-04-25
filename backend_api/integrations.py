"""
Optional external integrations: Twilio SMS, Tavily web search (enrichment).

Environment contract (all optional; backend stays functional without any):
- TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER
  - Use the Twilio Console **Live credentials** (Account SID + Auth Token), not the API Key (SK…),
    for the `twilio` Python SDK and SMS.
- TAVILY_API_KEY
  - When set, /enrichment/* uses Tavily Search. Missing key → 503 on single-facility route.

Load order: `src.config` / dotenv is imported before API routes, so .env is applied.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TwilioConfig:
    account_sid: str
    auth_token: str
    from_number: str  # E.164, e.g. +15551234567

    @property
    def is_complete(self) -> bool:
        return bool(
            self.account_sid.strip()
            and self.auth_token.strip()
            and self.from_number.strip()
        )


def get_twilio_config() -> TwilioConfig | None:
    sid = (os.getenv("TWILIO_ACCOUNT_SID") or "").strip()
    token = (os.getenv("TWILIO_AUTH_TOKEN") or "").strip()
    from_n = (os.getenv("TWILIO_FROM_NUMBER") or "").strip()
    if not (sid and token and from_n):
        return None
    return TwilioConfig(account_sid=sid, auth_token=token, from_number=from_n)


def twilio_effective() -> bool:
    return get_twilio_config() is not None


def get_tavily_api_key() -> str:
    return (os.getenv("TAVILY_API_KEY") or "").strip()


def tavily_effective() -> bool:
    return bool(get_tavily_api_key())


# Legacy: Serper no longer used by enrichment; keep helper for one-off tools
def get_serper_api_key() -> str:
    return (os.getenv("SERPER_API_KEY") or "").strip()


def serper_effective() -> bool:
    return bool(get_serper_api_key())


def integration_status() -> dict[str, Any]:
    """For /healthz or debugging — no secret values."""
    t = get_twilio_config()
    return {
        "twilio": {"configured": t is not None, "from_set": bool(t and t.from_number)},
        "tavily": {"configured": tavily_effective()},
    }
