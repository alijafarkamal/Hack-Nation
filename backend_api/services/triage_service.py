"""Symptom → capability language + graph run (non-diagnostic)."""

from __future__ import annotations

import re
import uuid
from typing import Any

from src.graph import run_graph
from src.tools.model_serving_tool import query_llm

_CAP_CACHE: dict[str, Any] = {}

CAPABILITY_PROMPT = """You translate patient language into healthcare facility CAPABILITIES needed in India (CareCompass).

NOT medical diagnosis. Output JSON only:
{"capabilities":["short tokens e.g. emergencyMedicine", "generalSurgery"], "red_flags":["if any ER red-flag keywords"], "graph_query":"one English question to find matching facilities"}

Keep capabilities as short tokens that could appear in facility specialty JSON (camelCase preferred)."""


def _parse_cap_json(raw: str) -> dict[str, Any]:
    s = (raw or "").strip()
    s = s.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    import json

    try:
        o = json.loads(s)
    except (json.JSONDecodeError, TypeError, ValueError):
        return {"capabilities": [], "red_flags": [], "graph_query": ""}
    if not isinstance(o, dict):
        return {"capabilities": [], "red_flags": [], "graph_query": ""}
    return o


def build_triage_query(symptoms_text: str) -> tuple[str, list[str], list[str]]:
    """Return (graph_query, capabilities, red_flags)."""
    cap_raw = query_llm(CAPABILITY_PROMPT, symptoms_text[:8000], max_tokens=400)
    parsed = _parse_cap_json(cap_raw)
    caps = [str(x) for x in (parsed.get("capabilities") or []) if str(x).strip()]
    rf = [str(x) for x in (parsed.get("red_flags") or []) if str(x).strip()]
    gq = (parsed.get("graph_query") or "").strip()
    if not gq:
        cap_s = ", ".join(caps[:6]) if caps else "general"
        gq = (
            f"Which verified facilities can support these care needs (capabilities: {cap_s}) "
            f"based on specialties, equipment, and trust signals? Context: {symptoms_text[:400]}"
        )
    gq = re.sub(r"\bdiagnos", "assessment", gq, flags=re.I)
    return gq, caps, rf


def run_triage_session(symptoms_text: str, correlation_id: str) -> dict[str, Any]:
    sid = str(uuid.uuid4())
    gq, caps, rf = build_triage_query(symptoms_text)
    graph_out = run_graph(gq, correlation_id=correlation_id)
    _CAP_CACHE[sid] = {
        "symptoms": symptoms_text[:5000],
        "query": gq,
        "capabilities": caps,
        "red_flags": rf,
    }
    return {
        "session_id": sid,
        "query_used": gq,
        "capabilities_needed": caps,
        "red_flags": rf,
        "graph": graph_out,
        "degraded_components": graph_out.get("degraded_components", []),
        "warnings": graph_out.get("warnings", []),
    }


def get_session(session_id: str) -> dict[str, Any] | None:
    return _CAP_CACHE.get(session_id)


_SAFETY = (
    "Capability match / triage assistant only — not a medical diagnosis. "
    "In emergencies, seek immediate in-person care."
)


def match_facilities_for_session(
    session_id: str, correlation_id: str, state_hint: str | None, top_k: int
) -> dict[str, Any]:
    s = get_session(session_id)
    if not s:
        return {
            "error": "session not found",
            "status": 404,
            "correlation_id": correlation_id,
            "safety_disclaimer": _SAFETY,
            "citations": [],
        }
    cap = ", ".join(s.get("capabilities") or ["general"])
    st = f" in {state_hint}" if state_hint else " in India"
    q = (
        f"List up to {top_k} high-trust facilities{st} that match these capabilities: {cap}. "
        f"Include facility name, state, pin, and trust note."
    )
    if state_hint:
        q += f" Prioritize {state_hint}."
    g = run_graph(q, correlation_id=correlation_id)
    return {
        **g,
        "safety_disclaimer": _SAFETY,
        "graph_summary": (g.get("final_answer") or "")[:20000] or None,
        "degraded_components": g.get("degraded_components", []),
        "warnings": g.get("warnings", []),
    }
