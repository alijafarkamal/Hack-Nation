"""Mock one-touch referral pipeline with audit log."""

from __future__ import annotations

import time
import uuid
from typing import Any

from backend_api.schemas import ReferralPreviewRequest, ReferralSendRequest

_AUDIT: list[dict] = []
_PREV: dict[str, dict] = {}


def build_referral_preview(
    body: ReferralPreviewRequest, correlation_id: str
) -> dict[str, Any]:
    preview_id = str(uuid.uuid4())
    subj = f"Referral: {body.to_facility[:80]}"
    text = (body.message_body or "").strip() or (
        f"CareCompass referral preview for facility {body.to_facility}. "
        f"Summary: {body.patient_summary or 'N/A'}"
    )
    card = {
        "preview_id": preview_id,
        "subject": subj,
        "body": text,
        "actions": [
            {"label": "Copy message", "action": "copy", "payload": text[:2000]},
            {"label": "Mark sent (mock)", "action": "mock_send", "href": f"/referral/send?preview_id={preview_id}"},
        ],
        "metadata": {
            "to_facility": body.to_facility,
            "session_id": body.session_id,
            "correlation_id": correlation_id,
            "contact_hint": body.contact_hint,
        },
    }
    _PREV[preview_id] = {**card, "created": time.time()}
    return card


def mock_send(
    body: ReferralSendRequest, correlation_id: str
) -> dict[str, Any]:
    p = _PREV.get(body.preview_id)
    audit_id = str(uuid.uuid4())
    _AUDIT.append(
        {
            "audit_id": audit_id,
            "preview_id": body.preview_id,
            "correlation_id": correlation_id,
            "ok": bool(p),
            "ts": time.time(),
        }
    )
    return {
        "success": bool(p),
        "audit_id": audit_id,
        "message": "Mock send accepted (no external SMS/email)." if p else "Unknown preview",
    }
