"""Supervisor node — normalizes user query, then classifies intent for routing.

Two-step process:
1. **Normalize** — Fix typos, grammar, and ambiguity so downstream agents
   (especially Genie Text-to-SQL) receive clean, well-formed English.
2. **Classify** — Route the cleaned query to SQL / SEARCH / EXTRACT / ANOMALY / GEO.

Uses Databricks Model Serving LLM for both steps.
"""

import mlflow

from src.state import AgentState
from src.tools.model_serving_tool import query_llm

# ── Step 1: Query normalization ──────────────────────────────────────────
NORMALIZE_PROMPT = """You are a query normalizer for a Ghana healthcare facilities database.

Your ONLY job is to rewrite the user's question into clear, grammatically correct English
while preserving the original intent. Fix typos, abbreviations, and broken grammar.

DOMAIN CONTEXT — common terms the user may misspell:
  hospital, clinic, pharmacy, dentist, doctor, cardiology, ophthalmology,
  gynecology, pediatrics, neurology, radiology, orthopedics, oncology,
  dermatology, urology, anesthesia, pathology, surgery, equipment,
  procedure, specialties, facility, region, district, Ghana, Accra,
  Kumasi, Tamale, Korle Bu, Ashanti, Volta, Northern, Greater Accra

RULES:
- Output ONLY the rewritten question. Nothing else.
- If the query is already correct, return it unchanged.
- Do NOT answer the question. Just rewrite it.
- Keep it concise — one clear sentence.

Examples:
  "how much hopital in ghana" → "How many hospitals are in Ghana?"
  "wat servis korle bu hav" → "What services does Korle Bu Teaching Hospital offer?"
  "cardilogy desert where" → "Where are the cardiology deserts in Ghana?"
  "faciliteis with surgery but no equpment" → "Which facilities claim surgery but lack equipment?"
"""

# ── Step 2: Intent classification ────────────────────────────────────────
ROUTER_PROMPT = """You classify healthcare facility questions into EXACTLY ONE category.

CATEGORY DEFINITIONS (choose the BEST fit):

SQL — Use when the question asks for **counts, rankings, comparisons, distributions, lists, or correlations** across the entire dataset.
Examples:
- "How many hospitals have cardiology?" → SQL
- "Which region has the most hospitals?" → SQL
- "Which procedures depend on very few facilities?" → SQL
- "Correlations between facility characteristics?" → SQL
- "Oversupply vs scarcity by complexity?" → SQL
- "Where is the workforce for ophthalmology practicing?" → SQL

SEARCH — Use when the question asks about a **specific facility by name**, or asks what services/capabilities exist in a **specific area**.
Examples:
- "What services does Korle Bu Teaching Hospital offer?" → SEARCH
- "Are there clinics in Accra that do eye care?" → SEARCH
- "What equipment does Tamale Teaching Hospital have?" → SEARCH

EXTRACT — Use when the question asks to **parse or extract structured facts** from a facility's free-form text (procedure, equipment, capability fields).
Examples:
- "What procedures does Tamale Teaching Hospital perform?" → EXTRACT
- "Parse capabilities for facilities in Ashanti" → EXTRACT

ANOMALY — Use ONLY when the question explicitly asks about **data inconsistencies, mismatches, contradictions, unrealistic claims, or quality problems** in the data.
Examples:
- "Facilities claiming unrealistic procedures for their size?" → ANOMALY
- "High procedure breadth with minimal equipment?" → ANOMALY
- "Things that shouldn't move together?" → ANOMALY

GEO — Use when the question involves **distances, locations, geographic coverage, cold spots, medical deserts, or service gaps by region**.
Examples:
- "Hospitals within 50km of Tamale?" → GEO
- "Largest geographic cold spots for cardiology?" → GEO
- "Gaps where no organizations work despite evident need?" → GEO

Respond with ONLY the category name (SQL, SEARCH, EXTRACT, ANOMALY, or GEO). No explanation."""

VALID_INTENTS = {"SQL", "SEARCH", "EXTRACT", "ANOMALY", "GEO"}


@mlflow.trace(name="supervisor_node", span_type="AGENT")
def supervisor_node(state: AgentState) -> dict:
    """Normalize the user query (fix typos/grammar), then classify intent.

    Returns the cleaned query and intent label for conditional routing.
    Defaults to SQL (Genie) for unrecognized intents.
    """
    raw_query = state["query"]

    # Step 1: Normalize — fix typos & grammar
    cleaned = query_llm(NORMALIZE_PROMPT, raw_query, max_tokens=150).strip()
    # Fallback: if normalization returns empty or something weird, keep original
    if not cleaned or len(cleaned) > len(raw_query) * 5:
        cleaned = raw_query

    # Step 2: Classify intent on the cleaned query
    intent = query_llm(ROUTER_PROMPT, cleaned, max_tokens=10).strip().upper()
    intent = intent.split()[0] if intent else "SQL"
    if intent not in VALID_INTENTS:
        intent = "SQL"

    return {"query": cleaned, "intent": intent}
