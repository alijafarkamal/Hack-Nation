"""Persistent shortlist endpoints for the Referral Copilot."""

from fastapi import APIRouter, HTTPException

from backend_api.schemas import ShortlistSaveRequest, ShortlistUpdateRequest
from backend_api.services import shortlist_service

router = APIRouter(prefix="/shortlist", tags=["shortlist"])


def _fail(exc: Exception) -> HTTPException:
    return HTTPException(status_code=503, detail=str(exc)[:500])


@router.post("/save")
def save(body: ShortlistSaveRequest) -> dict:
    try:
        return shortlist_service.save(body)
    except Exception as exc:
        raise _fail(exc) from exc


@router.get("/{session_id}")
def get_shortlist(session_id: str) -> dict:
    try:
        return {"session_id": session_id, "items": shortlist_service.list_for_session(session_id)}
    except Exception as exc:
        raise _fail(exc) from exc


@router.put("/update_note")
def update_note(body: ShortlistUpdateRequest) -> dict:
    try:
        return shortlist_service.update(body)
    except Exception as exc:
        raise _fail(exc) from exc


@router.post("/{session_id}/refresh_watchlist")
def refresh_watchlist(session_id: str) -> dict:
    try:
        return shortlist_service.refresh_watchlist(session_id)
    except Exception as exc:
        raise _fail(exc) from exc


@router.delete("/{session_id}/{facility_id}")
def delete_item(session_id: str, facility_id: str) -> dict:
    try:
        return shortlist_service.remove(session_id, facility_id)
    except Exception as exc:
        raise _fail(exc) from exc
