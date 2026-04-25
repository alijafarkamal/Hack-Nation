"""Tavily-powered facility enrichment API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from backend_api.schemas import EnrichmentBatchRequest, EnrichmentFacilityRequest
from backend_api.services import enrichment_service

router = APIRouter(prefix="/enrichment", tags=["enrichment"])


def _cid(request: Request) -> str:
    return getattr(request.state, "correlation_id", "")


@router.post("/facility")
def enrich_one(request: Request, body: EnrichmentFacilityRequest) -> dict:
    cor = _cid(request)
    out = enrichment_service.enrich_facility(
        body.facility_name.strip(),
        (body.district or "").strip(),
        (body.state or "").strip(),
        correlation_id=cor,
    )
    if not out.get("success") and out.get("error", "").startswith("TAVILY_API_KEY"):
        raise HTTPException(
            status_code=503,
            detail=out.get("error", "Tavily not configured"),
        )
    return out


@router.post("/batch")
def enrich_batch(request: Request, body: EnrichmentBatchRequest) -> dict:
    cor = _cid(request)
    items = body.items[:20] if isinstance(body.items, list) else []
    if not items:
        raise HTTPException(400, "items required (max 20)")
    return {
        "results": enrichment_service.enrich_batch(items, correlation_id=cor),
        "correlation_id": cor,
    }
