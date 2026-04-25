"""Pydantic models for Triage, Referral, Policy APIs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TriageAnalyzeRequest(BaseModel):
    symptoms_text: str = Field(..., min_length=1, description="Free-text symptoms (non-diagnostic).")
    metadata: dict[str, Any] = Field(default_factory=dict)


class TriageSessionResponse(BaseModel):
    session_id: str
    status: str
    capabilities_needed: list[str] = []
    query_used: str = ""
    safety_disclaimer: str = (
        "This is a capability-matching triage assistant, not a medical diagnosis. "
        "Seek emergency care if you have life-threatening symptoms."
    )
    graph_summary: str | None = None
    correlation_id: str = ""
    citations: list[dict] = []


class TriageMatchRequest(BaseModel):
    session_id: str
    top_k: int = 10
    state_hint: str | None = None


class ReferralPreviewRequest(BaseModel):
    session_id: str
    to_facility: str
    patient_summary: str = ""
    message_body: str = ""
    contact_hint: str = ""


class ReferralSendRequest(BaseModel):
    preview_id: str


class ReferralPreviewResponse(BaseModel):
    preview_id: str
    subject: str
    body: str
    actions: list[dict] = []
    metadata: dict = {}


class ReferralSendResponse(BaseModel):
    success: bool
    audit_id: str
    message: str = ""


class PolicyDesertParams(BaseModel):
    specialty: str
    level: str = "pin"  # pin|state
