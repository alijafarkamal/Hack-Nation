"""Synthesis: structured JSON first, then render Markdown (stable for APIs + UIs)."""

import json
import re

import mlflow

from src.citations import normalize_citation
from src.state import AgentState
from src.tools.model_serving_tool import query_llm

SYNTHESIS_JSON_PROMPT = """You are a medical data synthesis expert for Indian healthcare facilities (CareCompass).

You MUST return ONLY a single valid JSON object (no markdown, no backticks) with this exact shape:
{
  "answer_markdown": "string — short heading + key bullets, facility-named when data exists",
  "evidence_table": [
     {
        "facility": "name",
        "state": "or empty",
        "pin_or_city": "or empty",
        "facilityTypeId": "or empty",
        "notes": "concrete, row-specific; quote shortest supporting phrase when possible"
     }
  ],
  "citations": [
     {
        "source": "sql|search|idp|trust|geo|synthesis",
        "facility": "if applicable",
        "field": "e.g. specialties|procedure|trust|geo",
        "evidence_snippet": "short",
        "confidence": 0.0-1.0
     }
  ],
  "data_quality_notes": "string",
  "confidence_0_1": 0.0-1.0,
  "confidence_notes": ["string", "optional statistical / completeness notes"]
}

RULES:
1. Use ONLY the agent result context — no invented facilities.
2. Prefer `state_normalized` and `pin_code` for geography; never invent geographies.
3. Citation schema must match: source, facility, field, evidence_snippet, confidence.
4. `answer_markdown` can use ### headings but must stay concise.
"""


def _parse_synthesis_json(raw: str) -> dict | None:
    s = (raw or "").strip()
    s = s.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    m = re.search(r"\{[\s\S]*\}\s*$", s)
    if m:
        s = m.group(0)
    try:
        obj = json.loads(s)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    return obj if isinstance(obj, dict) else None


_SYNTH_FALLBACK = """You are a medical data synthesis expert for Indian healthcare facilities (CareCompass).

If structured JSON is unavailable, produce Markdown with:
### Answer, ### Supporting Evidence (table with Facility|State|PIN|Type|Notes), ### Data Quality Notes.
Never invent facilities; use only the provided context.
"""


def _format_result_context(state: AgentState) -> str:
    parts: list[str] = []

    if state.get("sql_result"):
        sr = state["sql_result"]
        section = "**SQL/Genie Result:**\n"
        if sr.get("text"):
            section += f"Answer: {sr['text']}\n"
        if sr.get("sql"):
            section += f"SQL: {sr['sql']}\n"
        if sr.get("data"):
            cols = sr.get("columns", [])
            section += f"Columns: {cols}\n"
            for row in sr["data"][:50]:
                section += f"  {row}\n"
            if len(sr["data"]) > 50:
                section += f"  ... ({len(sr['data'])} total rows)\n"
        if sr.get("detail_data"):
            dcols = sr.get("detail_columns", [])
            section += "\n**Individual facility rows:**\n"
            section += f"Columns: {dcols}\n"
            for row in sr["detail_data"][:30]:
                section += f"  {row}\n"
        parts.append(section)

    if state.get("search_result"):
        section = "**Vector Search Results:**\n"
        for i, r in enumerate(state["search_result"][:10]):
            if isinstance(r, dict):
                section += (
                    f"{i+1}. {r.get('name', '?')} | {r.get('state_normalized', '?')} | "
                    f"pin {r.get('pin_code', '?')} | {r.get('facilityTypeId', '?')}\n"
                    f"   trust: {r.get('trust_flag', '?')} ({r.get('trust_score', '?')})\n"
                    f"   description: {str(r.get('description', ''))[:200]}\n"
                    f"   specialties: {str(r.get('specialties', ''))[:200]}\n"
                )
            else:
                section += f"{i+1}. {r}\n"
        parts.append(section)

    if state.get("extraction_result"):
        er = state["extraction_result"]
        section = "**IDP Extraction:**\n"
        for i, ex in enumerate(er.get("extractions", [])[:5]):
            section += f"{i+1}. {ex[:800]}\n"
        parts.append(section)

    if state.get("trust_result"):
        section = f"**Trust Scorer / Validator:**\n{state['trust_result'][:4000]}\n"
        parts.append(section)

    if state.get("geo_result"):
        gr = state["geo_result"]
        section = "**Geospatial:**\n"
        section += f"Message: {gr.get('message', 'N/A')}\n"
        if gr.get("desert_states"):
            section += f"Desert states (specialty signal): {gr['desert_states']}\n"
        if gr.get("desert_pins"):
            section += f"Desert PINs (no specialty match in data, sample of first 20): {gr['desert_pins'][:20]}\n"
        if gr.get("desert_pin_ratio_interval"):
            iv = gr["desert_pin_ratio_interval"]
            section += f"Desert-PIN share interval (95%): point={iv.get('point')}, low={iv.get('low_95')}, high={iv.get('high_95')}\n"
        if gr.get("facilities"):
            for f in gr["facilities"][:10]:
                section += f"  - {f.get('name')} ({f.get('distance_km')} km)\n"
        if gr.get("facilities_in_pin"):
            section += f"PIN facilities count: {len(gr['facilities_in_pin'])}\n"
        parts.append(section)

    return "\n---\n".join(parts) if parts else "No results from agents."


_AGENT_LABELS = {
    "sql_result": "SQL/Genie",
    "search_result": "Vector Search",
    "extraction_result": "IDP Extraction",
    "trust_result": "Trust Scorer",
    "geo_result": "Geospatial",
}


def _active_agents(state: AgentState) -> list[str]:
    return [label for key, label in _AGENT_LABELS.items() if state.get(key)]


def _json_to_markdown(obj: dict) -> str:
    am = (obj.get("answer_markdown") or "").strip()
    ev = obj.get("evidence_table") or []
    dqn = (obj.get("data_quality_notes") or "").strip()
    conf = float(obj.get("confidence_0_1", 0.65) or 0.0)
    parts = [am] if am else []
    if ev:
        parts.append("\n### Supporting Evidence\n")
        parts.append("| Facility | State | PIN or City | Type | Notes |\n|---|---|---|---|---|\n")
        for row in ev[:30]:
            if not isinstance(row, dict):
                continue
            parts.append(
                f"| {row.get('facility','')[:80]} | {row.get('state','')} | {row.get('pin_or_city','')} | "
                f"{row.get('facilityTypeId','')} | {str(row.get('notes',''))[:200]} |\n"
            )
    if dqn:
        parts.append(f"\n### Data Quality Notes\n{dqn}\n")
    parts.append(f"\n_Synthesis confidence (self-reported): {conf:.2f}_\n")
    return "\n".join(parts) if parts else (am or "No answer produced.")


@mlflow.trace(name="synthesis_node", span_type="CHAIN")
def synthesis_node(state: AgentState) -> dict:
    context = _format_result_context(state)
    user_query = state["query"]
    agents_used = _active_agents(state)
    corr = (state.get("correlation_id") or "") or ""
    prompt_input = f"User question: {user_query}\n\nAgent results:\n{context}"
    raw = query_llm(SYNTHESIS_JSON_PROMPT, prompt_input, max_tokens=2048)
    parsed = _parse_synthesis_json(raw)
    if not parsed:
        answer = query_llm(_SYNTH_FALLBACK, prompt_input, max_tokens=2048)
        merged = f"{answer}\n\n**Sources merged:** {', '.join(agents_used)}."
        return {
            "final_answer": merged,
            "synthesis_artifacts": {
                "parse_error": True,
                "raw_llm": raw[:8000],
                "agents_merged": agents_used,
            },
            "citations": [
                {
                    "source": "synthesis",
                    "field": "fallback",
                    "evidence_snippet": merged[:500],
                    "confidence": 0.45,
                    "correlation_id": corr,
                }
            ],
        }
    am = _json_to_markdown(parsed) + f"\n\n**Sources merged:** {', '.join(agents_used)}."
    cits: list[dict] = []
    for c in (parsed.get("citations") or [])[:50]:
        if not isinstance(c, dict):
            continue
        try:
            conf = float(c.get("confidence", 0.6) or 0.0)
        except (TypeError, ValueError):
            conf = 0.6
        cits.append(
            normalize_citation(
                source=str(c.get("source", "synthesis")),
                facility=str(c.get("facility", "")),
                field=str(c.get("field", "")),
                evidence_snippet=str(c.get("evidence_snippet", ""))[:2000],
                confidence=conf,
                row_id="",
                correlation_id=corr,
            )
        )
    cits.append(
        {
            "source": "synthesis",
            "field": "structured",
            "evidence_snippet": (parsed.get("answer_markdown") or "")[:500],
            "confidence": float(parsed.get("confidence_0_1", 0.6) or 0.0),
            "correlation_id": corr,
        }
    )
    syn_art = {**parsed, "agents_merged": agents_used, "correlation_id": corr}
    return {
        "final_answer": am,
        "synthesis_artifacts": syn_art,
        "degraded_components": degraded,
        "warnings": warnings,
        "citations": cits,
    }
