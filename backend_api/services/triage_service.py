"""Symptom → capability language + graph run (non-diagnostic)."""

from __future__ import annotations

import re
import uuid
from typing import Any

from src.graph import run_graph
from src.tools.model_serving_tool import query_llm

_CAP_CACHE: dict[str, Any] = {}

CAPABILITY_PROMPT = """You translate patient language into healthcare facility CAPABILITIES needed in India (care-india).

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

def _run_llm_judge(user_request: str, ai_answer: str) -> dict[str, Any]:
    prompt = """You are an AI Output Judge verifying a healthcare facility recommendation.
Review the AI's answer against the user's request.
Output ONLY JSON in this format:
{"trust_score": <int 0-100>, "judge_note": "<short explanation of whether the AI hallucinated or if the data is reliable>"}"""
    user_msg = f"User Request: {user_request}\nAI Answer: {ai_answer[:2000]}"
    try:
        raw = query_llm(prompt, user_msg, max_tokens=150)
        import json
        s = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        o = json.loads(s)
        return {"trust_score": o.get("trust_score", 50), "judge_note": o.get("judge_note", "Validation parsed with warnings.")}
    except Exception as e:
        return {"trust_score": 0, "judge_note": f"Judge unavailable ({e})"}


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
    
    desert_analysis = None
    if state_hint:
        try:
            from src.config import db_client, CATALOG, SCHEMA, TABLE_FACILITIES
            from databricks.sdk.service.sql import Disposition
            warehouses = list(db_client.warehouses.list())
            if warehouses:
                wh = warehouses[0].id
                stmt = f"SELECT count(*) FROM {CATALOG}.{SCHEMA}.{TABLE_FACILITIES} WHERE lower(state) LIKE lower('%{state_hint}%')"
                resp = db_client.statement_execution.execute_statement(
                    warehouse_id=wh, statement=stmt, wait_timeout="20s", disposition=Disposition.INLINE
                )
                if resp.result and resp.result.data_array:
                    total_facilities = int(resp.result.data_array[0][0])
                    if total_facilities > 0:
                        desert_analysis = f"DATA DESERT WARNING: We found {total_facilities} facilities in {state_hint}, but their data is too sparse to verify they have: {cap}."
                    else:
                        desert_analysis = f"MEDICAL DESERT WARNING: There are 0 registered facilities in {state_hint}."
        except Exception as e:
            desert_analysis = f"Desert analysis unavailable ({e})"

    llm_judge = None
    final_ans = g.get("final_answer")
    if final_ans:
        llm_judge = _run_llm_judge(q, final_ans)

    return {
        **g,
        "llm_judge": llm_judge,
        "desert_analysis": desert_analysis,
        "safety_disclaimer": _SAFETY,
        "graph_summary": (g.get("final_answer") or "")[:20000] or None,
        "degraded_components": g.get("degraded_components", []),
        "warnings": g.get("warnings", []),
    }
