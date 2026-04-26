"""IDP extraction: structured facts from messy facility notes (challenge IDP 30%)."""

import json
import re

import mlflow

from src.state import AgentState
from src.tools.model_serving_tool import query_llm
from src.tools.vector_search_tool import get_vector_search_status, query_vector_search

IDP_EXTRACTION_PROMPT = """You are a medical facility information extractor for Indian facilities.

Given one facility's fields (name, description, JSON arrays: specialties, procedure, equipment, capability),
return STRUCTURED JSON with these keys (use null where unknown):

{
  "facility_name": "string",
  "parsed_procedures": ["string", ...],
  "parsed_equipment": ["string", ...],
  "parsed_capabilities": ["string", ...],
  "inferred_specialties_camelCase": ["cardiology", "emergencyMedicine", ...],
  "part_time_or_locum_mentioned": true | false,
  "open_24_7_claimed": true | false,
  "per_field_confidence": {
     "procedures": 0.0-1.0,
     "equipment": 0.0-1.0,
     "capabilities": 0.0-1.0
  },
  "confidence_flags": ["short specific notes on gaps or contradictions", ...]
}

RULES:
- Extract ONLY from the provided data. No external medical knowledge.
- Empty JSON arrays in source mean "no evidence" — say so; do not invent items.
- Map specialties to camelCase where possible (e.g. medicalOncology, generalSurgery).
- If procedure claims exist but equipment is empty, lower confidence and flag.
- Return ONLY valid JSON, no markdown fences."""


def _try_parse_idp(s: str) -> dict | None:
    t = (s or "").strip()
    t = t.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    m = re.search(r"\{[\s\S]*\}\s*$", t)
    if m:
        t = m.group(0)
    try:
        o = json.loads(t)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    return o if isinstance(o, dict) else None


@mlflow.trace(name="idp_extraction_node", span_type="AGENT")
def idp_extraction_node(state: AgentState) -> dict:
    corr = (state.get("correlation_id") or "") or ""
    raw_facilities = query_vector_search(state["query"], num_results=5)
    vs = get_vector_search_status()
    extractions: list[str] = []
    parsed_rows: list[dict] = []
    for facility in raw_facilities:
        raw = query_llm(
            IDP_EXTRACTION_PROMPT, json.dumps(facility, default=str), max_tokens=1024
        )
        extractions.append(raw)
        pr = _try_parse_idp(raw)
        if pr:
            pr["_facility_source_name"] = facility.get("name", "") if isinstance(facility, dict) else ""
            parsed_rows.append(pr)
    out = {
        "extraction_result": {
            "query": state["query"],
            "extractions": extractions,
            "structured_parsed": parsed_rows,
        },
        "citations": [
            {
                "source": "idp_extraction",
                "field": "idp",
                "evidence_snippet": f"processed {len(raw_facilities)} facilities",
                "confidence": 0.65,
                "correlation_id": corr,
            }
        ],
    }
    if not vs.get("ok"):
        out["degraded_components"] = vs.get("degraded_components", [])
        out["warnings"] = [vs.get("warning")] if vs.get("warning") else []
        out["citations"].append({
            "source": "vector_search",
            "field": "degradation",
            "evidence_snippet": str(vs.get("warning") or vs.get("error") or "vector search unavailable"),
            "confidence": 0.2,
            "correlation_id": corr,
        })
    return out
