"""Referral mock routes."""

from __future__ import annotations

from fastapi import APIRouter, Request

from backend_api.schemas import (
    ReferralPreviewRequest,
    ReferralPreviewResponse,
    ReferralSendRequest,
    ReferralSendResponse,
)
from backend_api.services import referral_service

router = APIRouter(prefix="/referral", tags=["referral"])


def _cid(request: Request) -> str:
    return getattr(request.state, "correlation_id", "")


@router.post("/preview", response_model=ReferralPreviewResponse)
def post_preview(request: Request, body: ReferralPreviewRequest) -> dict:
    return referral_service.build_referral_preview(body, _cid(request))


@router.post("/send", response_model=ReferralSendResponse)
def post_send(request: Request, body: ReferralSendRequest) -> dict:
    return referral_service.mock_send(body, _cid(request))
