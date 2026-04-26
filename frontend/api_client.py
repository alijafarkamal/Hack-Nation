"""HTTP client for CareCompass FastAPI (browser-safe: no Databricks secrets)."""

from __future__ import annotations

import os
import uuid
from typing import Any

import requests

_LAST_REQUEST_ID: str | None = None


def _base_url() -> str:
    return (os.environ.get("CARECOMPASS_API_URL") or "http://127.0.0.1:8000").rstrip("/")


def get_api_base() -> str:
    return _base_url()


def _new_request_id() -> str:
    return str(uuid.uuid4())


class ApiError(Exception):
    """HTTP or logical API failure."""

    def __init__(
        self,
        message: str,
        *,
        status: int = 0,
        detail: str | None = None,
        correlation_id: str | None = None,
        raw: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.detail = detail
        self.correlation_id = correlation_id
        self.raw = raw


def _req_headers(request_id: str | None) -> dict[str, str]:
    rid = request_id or _new_request_id()
    return {"Accept": "application/json", "X-Request-Id": rid}


def _after_request_id(resp: requests.Response) -> None:
    global _LAST_REQUEST_ID
    rid = resp.headers.get("X-Request-Id")
    if rid:
        _LAST_REQUEST_ID = rid


def get_last_request_id() -> str | None:
    return _LAST_REQUEST_ID


def request_json(
    method: str,
    path: str,
    *,
    json_body: Any | None = None,
    request_id: str | None = None,
    timeout: float = 300.0,
) -> dict[str, Any]:
    global _LAST_REQUEST_ID
    url = f"{_base_url()}{path if path.startswith('/') else '/' + path}"
    headers = _req_headers(request_id)
    if json_body is not None:
        headers["Content-Type"] = "application/json"

    rid = headers["X-Request-Id"]
    _LAST_REQUEST_ID = rid

    try:
        if method.upper() == "GET":
            resp = requests.get(url, headers=headers, timeout=timeout)
        elif method.upper() == "POST":
            resp = requests.post(url, headers=headers, json=json_body, timeout=timeout)
        else:
            raise ValueError(f"Unsupported method: {method}")
    except requests.RequestException as e:
        raise ApiError(f"Network error: {e}", status=0, detail=str(e)) from e

    _after_request_id(resp)

    try:
        data: Any = resp.json() if resp.content else {}
    except ValueError:
        data = {"_raw_text": resp.text}

    if not resp.ok:
        detail = None
        if isinstance(data, dict) and "detail" in data:
            detail = str(data["detail"])
        raise ApiError(
            detail or f"Request failed ({resp.status_code})",
            status=resp.status_code, detail=detail, raw=data,
        )

    if isinstance(data, dict) and "error" in data and "status" in data and isinstance(
        data.get("status"), (int, float)
    ):
        st_code = int(data["status"])
        msg = str(data.get("error") or "Request failed")
        err = ApiError(msg, status=st_code, detail=msg, raw=data)
        if "correlation_id" in data:
            err.correlation_id = str(data["correlation_id"])
        raise err

    if not isinstance(data, dict):
        return {"_non_object": data}
    return data


def get_json(path: str, request_id: str | None = None) -> dict[str, Any]:
    return request_json("GET", path, request_id=request_id)


def post_json(path: str, body: dict[str, Any], request_id: str | None = None) -> dict[str, Any]:
    return request_json("POST", path, json_body=body, request_id=request_id)


# ── Triage ───────────────────────────────────────────────────────────────────

def triage_analyze(symptoms_text: str, request_id: str | None = None) -> dict[str, Any]:
    return post_json("/triage/analyze", {"symptoms_text": symptoms_text, "metadata": {}}, request_id=request_id)


def triage_match_facilities(
    session_id: str, top_k: int = 10, state_hint: str | None = None, request_id: str | None = None,
) -> dict[str, Any]:
    return post_json(
        "/triage/match_facilities",
        {"session_id": session_id, "top_k": int(top_k), "state_hint": state_hint or None},
        request_id=request_id,
    )


# ── Policy ───────────────────────────────────────────────────────────────────

def get_policy_deserts(specialty: str, level: str, request_id: str | None = None) -> dict[str, Any]:
    from urllib.parse import urlencode
    q = urlencode({"specialty": (specialty or "emergency").strip(), "level": level})
    return get_json(f"/policy/deserts?{q}", request_id=request_id)


def get_pin_risk(pin_code: str, request_id: str | None = None) -> dict[str, Any]:
    from urllib.parse import quote
    seg = quote(str(pin_code).strip(), safe="")
    return get_json(f"/policy/pin-risk/{seg}", request_id=request_id)


# ── System ───────────────────────────────────────────────────────────────────

def healthz(request_id: str | None = None) -> dict[str, Any]:
    return get_json("/healthz", request_id=request_id)


def readiness(request_id: str | None = None) -> dict[str, Any]:
    return get_json("/readiness", request_id=request_id)


# ── Referral ─────────────────────────────────────────────────────────────────

def referral_preview(
    *, session_id: str, to_facility: str, patient_summary: str = "",
    message_body: str = "", contact_hint: str = "", to_phone: str = "",
    request_id: str | None = None,
) -> dict[str, Any]:
    return post_json("/referral/preview", {
        "session_id": session_id, "to_facility": to_facility,
        "patient_summary": patient_summary, "message_body": message_body,
        "contact_hint": contact_hint, "to_phone": to_phone,
    }, request_id=request_id)


def referral_send(preview_id: str, to_phone: str = "", request_id: str | None = None) -> dict[str, Any]:
    return post_json("/referral/send", {"preview_id": preview_id, "to_phone": to_phone}, request_id=request_id)


# ── Enrichment (optional) ───────────────────────────────────────────────────

def enrichment_facility(
    facility_name: str, district: str = "", state: str = "", request_id: str | None = None,
) -> dict[str, Any]:
    return post_json("/enrichment/facility", {
        "facility_name": facility_name, "district": district, "state": state,
    }, request_id=request_id)
