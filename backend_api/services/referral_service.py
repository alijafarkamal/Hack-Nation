"""One-touch referral: real Twilio SMS when configured; else auditable mock."""

from __future__ import annotations

import logging
import re
import time
import uuid
from typing import Any

from backend_api.integrations import get_twilio_config, twilio_effective
from backend_api.schemas import ReferralPreviewRequest, ReferralSendRequest

logger = logging.getLogger(__name__)

_AUDIT: list[dict] = []
_PREV: dict[str, dict] = {}


def _e164_sanitize(phone: str) -> str:
    s = re.sub(r"[\s\-]", "", (phone or "").strip())
    if not s:
        return ""
    if s.startswith("+"):
        return "+" + re.sub(r"\D", "", s[1:])
    if s.startswith("0") and len(s) == 11 and s[0] == "0":
        return "+91" + s[1:]
    digits = re.sub(r"\D", "", s)
    if len(digits) == 10:
        return "+91" + digits
    if len(digits) == 12 and digits.startswith("91"):
        return "+" + digits
    if s.startswith("+"):
        return s
    return "+" + digits if digits else ""


def build_referral_preview(
    body: ReferralPreviewRequest, correlation_id: str
) -> dict[str, Any]:
    preview_id = str(uuid.uuid4())
    subj = f"Referral: {body.to_facility[:80]}"
    text = (body.message_body or "").strip() or (
        f"care-india referral preview for facility {body.to_facility}. "
        f"Summary: {body.patient_summary or 'N/A'}"
    )
    to_phone = _e164_sanitize((body.to_phone or "").strip())
    actions: list[dict] = [
        {"label": "Copy message", "action": "copy", "payload": text[:2000]},
    ]
    ch = (body.contact_hint or "").strip()
    if ch:
        tel_href = ch if ch.lower().startswith("tel:") else f"tel:{ch.lstrip(' +')}"
        actions.append({"label": "Call (tel:)", "action": "tel", "href": tel_href})
    if to_phone:
        actions.append(
            {
                "label": "Send SMS (Twilio if configured)",
                "action": "send_sms",
                "href": f"/referral/send",
            }
        )
    card = {
        "preview_id": preview_id,
        "subject": subj,
        "body": text,
        "actions": actions,
        "metadata": {
            "to_facility": body.to_facility,
            "session_id": body.session_id,
            "correlation_id": correlation_id,
            "contact_hint": body.contact_hint,
            "to_phone": to_phone,
            "twilio_configured": twilio_effective(),
        },
    }
    _PREV[preview_id] = {
        **{k: v for k, v in card.items() if k != "actions"},
        "created": time.time(),
        "to_phone": to_phone,
        "body": text,
        "raw_message": text,
    }
    return card


def _twilio_send_sms(
    to_e164: str, body_text: str, correlation_id: str
) -> tuple[str | None, str | None]:
    """Return (message_sid, error)."""
    cfg = get_twilio_config()
    if not cfg or not to_e164:
        return None, "twilio_not_configured"
    try:
        from twilio.rest import Client

        client = Client(cfg.account_sid, cfg.auth_token)
        msg = client.messages.create(
            to=to_e164,
            from_=cfg.from_number,
            body=body_text[:1600],
        )
        return (msg.sid if msg else None, None)
    except Exception as e:  # noqa: BLE001
        err = str(e)[:500]
        logger.warning("Twilio send failed: %s", err)
        return None, err


def send_referral(
    body: ReferralSendRequest, correlation_id: str
) -> dict[str, Any]:
    p = _PREV.get(body.preview_id)
    audit_id = str(uuid.uuid4())
    to_raw = (getattr(body, "to_phone", None) or (p or {}).get("to_phone") or "").strip()
    to_e164 = _e164_sanitize(to_raw) if to_raw else ((p or {}).get("to_phone") or "")
    if isinstance(to_e164, str) and to_e164 and not to_e164.startswith("+"):
        to_e164 = _e164_sanitize(to_e164)

    body_text = (p or {}).get("raw_message") or (p or {}).get("body") or "care-india referral"

    if not p:
        _AUDIT.append(
            {
                "audit_id": audit_id,
                "preview_id": body.preview_id,
                "correlation_id": correlation_id,
                "ok": False,
                "mode": "mock",
                "ts": time.time(),
            }
        )
        return {
            "success": False,
            "audit_id": audit_id,
            "message": "Unknown preview",
            "mode": "mock",
            "twilio_message_sid": None,
            "provider_error": None,
        }

    use_twilio = twilio_effective() and bool(to_e164) and to_e164.startswith("+")
    if use_twilio:
        sid, err = _twilio_send_sms(str(to_e164), str(body_text), correlation_id)
        if sid:
            _AUDIT.append(
                {
                    "audit_id": audit_id,
                    "preview_id": body.preview_id,
                    "correlation_id": correlation_id,
                    "ok": True,
                    "mode": "twilio",
                    "twilio_message_sid": sid,
                    "to": to_e164,
                    "ts": time.time(),
                }
            )
            return {
                "success": True,
                "audit_id": audit_id,
                "message": f"SMS sent via Twilio (sid {sid})",
                "mode": "twilio",
                "twilio_message_sid": sid,
                "provider_error": None,
            }
        # Fallback to mock after provider failure
        _AUDIT.append(
            {
                "audit_id": audit_id,
                "preview_id": body.preview_id,
                "correlation_id": correlation_id,
                "ok": True,
                "mode": "mock_fallback",
                "provider_error": err,
                "ts": time.time(),
            }
        )
        return {
            "success": True,
            "audit_id": audit_id,
            "message": f"Mock send (Twilio unavailable: {err or 'error'})",
            "mode": "mock_fallback",
            "twilio_message_sid": None,
            "provider_error": err,
        }

    # Mock path: no number or no Twilio
    _AUDIT.append(
        {
            "audit_id": audit_id,
            "preview_id": body.preview_id,
            "correlation_id": correlation_id,
            "ok": True,
            "mode": "mock",
            "ts": time.time(),
            "note": "Set TWILIO_* and pass to_phone to send real SMS" if not twilio_effective() else "Provide E.164 to_phone for SMS",
        }
    )
    return {
        "success": True,
        "audit_id": audit_id,
        "message": "Mock send accepted (no external SMS) — set TWILIO_* and to_phone for real SMS",
        "mode": "mock",
        "twilio_message_sid": None,
        "provider_error": None,
    }


# Backwards-compatible name
def mock_send(body: ReferralSendRequest, correlation_id: str) -> dict[str, Any]:
    return send_referral(body, correlation_id)
