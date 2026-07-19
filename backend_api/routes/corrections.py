"""Routes for the Data Readiness Desk."""

from fastapi import APIRouter, HTTPException

from backend_api.schemas import CorrectionSubmitRequest, CorrectionResponse
from backend_api.services import corrections_service

router = APIRouter(prefix="/corrections", tags=["corrections"])

def _fail(exc: Exception) -> HTTPException:
    return HTTPException(status_code=503, detail=str(exc)[:500])

@router.post("/submit", response_model=CorrectionResponse)
def submit_correction(body: CorrectionSubmitRequest) -> dict:
    """Submit a manual correction for a facility's data."""
    try:
        return corrections_service.submit_correction(body)
    except Exception as exc:
        raise _fail(exc) from exc
