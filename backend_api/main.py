"""
care-india FastAPI: triage, referral (Twilio or mock), policy, Tavily enrichment.
Run: `uvicorn backend_api.main:app --reload` from repo root.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow `python main.py` when the current directory is `backend_api`.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend_api.integrations import integration_status
from backend_api.middleware.correlation import CorrelationIdMiddleware
from backend_api.schemas import (
    TriageAnalyzeRequest,
    TriageMatchRequest,
    TriageSessionResponse,
)
from backend_api.routes import enrichment, referral, shortlist
from backend_api.services import policy_service, readiness_service, triage_service

app = FastAPI(
    title="care-india API",
    version="0.1.0",
    description="Capability-matching triage, trust-backed policy, referral SMS (optional Twilio), Tavily enrichment.",
)
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(referral.router)
app.include_router(enrichment.router)
app.include_router(shortlist.router)


def _cid(request: Request) -> str:
    return getattr(request.state, "correlation_id", "")


@app.get("/healthz")
def healthz() -> dict:
    return {
        "ok": True,
        "service": "care-india",
        "integrations": integration_status(),
    }




@app.get("/readiness")
def readiness() -> dict:
    return readiness_service.readiness_report()

@app.post("/triage/analyze", response_model=TriageSessionResponse)
def triage_analyze(request: Request, body: TriageAnalyzeRequest) -> TriageSessionResponse:
    cor = _cid(request)
    out = triage_service.run_triage_session(body.symptoms_text, cor)
    g = out.get("graph") or {}
    return TriageSessionResponse(
        session_id=out["session_id"],
        status="analyzed",
        capabilities_needed=list(out.get("capabilities_needed") or []),
        red_flags=list(out.get("red_flags") or []),
        query_used=str(out.get("query_used") or ""),
        graph_summary=(g.get("final_answer") or "")[:20000] or None,
        correlation_id=str(g.get("correlation_id", cor) or cor),
        citations=(g.get("citations") or []),
        degraded_components=list(g.get("degraded_components") or []),
        warnings=list(g.get("warnings") or []),
    )


@app.get("/triage/{session_id}", response_model=TriageSessionResponse)
def triage_get(request: Request, session_id: str) -> TriageSessionResponse:
    s = triage_service.get_session(session_id)
    if not s:
        raise HTTPException(404, "Session not found")
    cor = _cid(request)
    return TriageSessionResponse(
        session_id=session_id,
        status="ok",
        capabilities_needed=s.get("capabilities", []),
        red_flags=s.get("red_flags", []),
        query_used=s.get("query", ""),
        graph_summary=None,
        correlation_id=cor,
        citations=[],
        degraded_components=[],
        warnings=[],
    )


@app.post("/triage/match_facilities")
def triage_match(request: Request, body: TriageMatchRequest) -> dict:
    cor = _cid(request)
    return triage_service.match_facilities_for_session(
        body.session_id, cor, body.state_hint, body.top_k
    )


@app.get("/policy/deserts")
def policy_deserts(
    request: Request,
    specialty: str = "emergency",
    level: str = "pin",
) -> dict:
    return policy_service.get_desert_report(specialty, level, _cid(request))


@app.get("/policy/pin-risk/{pin_code}")
def policy_pin_risk(request: Request, pin_code: str) -> dict:
    r = policy_service.get_pin_risk(pin_code, _cid(request))
    if r.get("error"):
        raise HTTPException(400, str(r.get("error")))
    return r


_react_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _react_dist.exists():
    app.mount("/", StaticFiles(directory=_react_dist, html=True), name="react")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="debug")
