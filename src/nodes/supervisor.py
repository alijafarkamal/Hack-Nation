"""Supervisor: normalize query, then classify intent(s) for routing."""

import mlflow

from src.state import AgentState
from src.tools.model_serving_tool import query_llm

NORMALIZE_PROMPT = """You are a query normalizer for an Indian healthcare facilities database
(Virtue Foundation — ~10,000 facilities across India).

Your ONLY job is to rewrite the user's question into clear, grammatically correct English
while preserving the original intent. Fix typos, abbreviations, and broken grammar.

DOMAIN CONTEXT — common terms users may misspell:
  hospital, clinic, pharmacy, dentist, doctor, cardiology, ophthalmology, oncology, dialysis,
  emergency, ICU, ventilator, surgery, anesthesiologist, neonatal, appendectomy, rural, PIN code,
  Bihar, Maharashtra, Uttar Pradesh, Delhi, Telangana, Tamil Nadu, Kerala, West Bengal, Gujarat,
  Mumbai, Delhi NCR, Kolkata, Hyderabad, Bengaluru, ASHA, NGO

RULES:
- Output ONLY the rewritten question. Nothing else.
- If the query is already correct, return it unchanged.
- Do NOT answer the question. Just rewrite it.
- Keep it concise — one clear sentence when possible.

Examples:
  "hopital bihar emrgency" → "Which hospitals in Bihar offer emergency care?"
  "pin 803118 desert" → "Which medical specialties are missing around PIN code 803118?"
"""

ROUTER_PROMPT = """You classify Indian healthcare facility questions into one or two categories.

CATEGORY DEFINITIONS:

SQL — counts, rankings, comparisons, distributions, lists, or correlations across the dataset.
  "How many hospitals in Bihar have cardiology?" → SQL
  "Top states by facility count" → SQL

SEARCH — a specific facility by name, or services in a specific place.
  "What does Apollo Hospital in Hyderabad offer?" → SEARCH
  "Clinics in Patna with eye care" → SEARCH

EXTRACT — parse or extract structured facts from free-form text (procedure, equipment, notes).
  "List procedures and equipment for facilities in rural Bihar" → EXTRACT
  "Extract capabilities from the description for AIIMS Delhi" → EXTRACT

TRUST — contradictions, suspicious claims, trust scoring, data quality, verification.
  "Facilities claiming ICU but listing no ventilator" → TRUST
  "Which records look inconsistent between specialties and equipment?" → TRUST

GEO — distances, coverage, medical deserts, PIN-level gaps, maps.
  "Ophthalmology deserts in Maharashtra" → GEO
  "Facilities within 30 km of this PIN" → GEO

COMPOSITE QUERY RULES:
- If the question clearly spans TWO categories, return BOTH separated by a comma.
  "Hospitals in Bihar with emergency surgery and worst trust scores" → SQL,TRUST
  "Cardiology deserts in Uttar Pradesh" → GEO,SQL
- Never return more than 2 categories.
- If in doubt, return just one.

Respond with ONLY the category name(s). No explanation.
Valid examples: SQL | SEARCH | GEO,SQL | TRUST,EXTRACT | GEO,TRUST"""

VALID_INTENTS = {"SQL", "SEARCH", "EXTRACT", "TRUST", "GEO"}


@mlflow.trace(name="supervisor_node", span_type="AGENT")
def supervisor_node(state: AgentState) -> dict:
    """Normalize and classify. Composite queries return up to 2 intents."""
    raw_query = state["query"]

    cleaned = query_llm(NORMALIZE_PROMPT, raw_query, max_tokens=150).strip()
    if not cleaned or len(cleaned) > len(raw_query) * 5:
        cleaned = raw_query

    raw_intent = query_llm(ROUTER_PROMPT, cleaned, max_tokens=24).strip().upper()
    tokens = [t.strip() for t in raw_intent.replace(" ", "").split(",")]
    intents = [t for t in tokens if t in VALID_INTENTS]

    seen: set[str] = set()
    unique: list[str] = []
    for i in intents:
        if i not in seen:
            seen.add(i)
            unique.append(i)
    intents = unique[:2]

    if not intents:
        intents = ["SQL"]

    out: dict = {"query": cleaned, "intents": intents}
    if state.get("correlation_id"):
        out["correlation_id"] = state["correlation_id"]
    return out
