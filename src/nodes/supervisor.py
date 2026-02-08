"""Supervisor node — normalizes user query, then classifies intent for routing.

Three-step process:
1. **Normalize** — Fix typos, grammar, and ambiguity so downstream agents
   (especially Genie Text-to-SQL) receive clean, well-formed English.
2. **Classify** — Route the cleaned query to one or more of:
   SQL / SEARCH / EXTRACT / ANOMALY / GEO.
3. **Fan-out** — Composite queries that span multiple domains are routed to
   2+ agents in parallel (LangGraph fan-out); synthesis merges all results.

Uses Databricks Model Serving LLM for both normalize and classify steps.
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

# ── Step 2: Intent classification (supports 1 or 2 intents) ──────────────
ROUTER_PROMPT = """You classify healthcare facility questions into one or two categories.

CATEGORY DEFINITIONS:

SQL — **counts, rankings, comparisons, distributions, lists, or correlations** across the dataset.
  "How many hospitals have cardiology?" → SQL
  "Which region has the most hospitals?" → SQL

SEARCH — a **specific facility by name** or services in a **specific area**.
  "What services does Korle Bu Teaching Hospital offer?" → SEARCH
  "Clinics in Accra that do eye care?" → SEARCH

EXTRACT — **parse or extract structured facts** from free-form text fields.
  "What procedures does Tamale Teaching Hospital perform?" → EXTRACT
  "Parse capabilities for facilities in Ashanti" → EXTRACT

ANOMALY — **data inconsistencies, mismatches, contradictions, unrealistic claims**.
  "Facilities claiming unrealistic procedures for their size?" → ANOMALY
  "High procedure breadth with minimal equipment?" → ANOMALY

GEO — **distances, locations, geographic coverage, cold spots, medical deserts**.
  "Hospitals within 50km of Tamale?" → GEO
  "Largest geographic cold spots for cardiology?" → GEO

COMPOSITE QUERY RULES:
- If the question clearly spans TWO categories, return BOTH separated by a comma.
  "Hospitals near Tamale with cardiology deserts" → GEO,SQL
  "Facilities claiming surgery but lacking equipment in Northern region" → ANOMALY,GEO
  "How many ophthalmology deserts exist and which facilities are closest?" → GEO,SQL
  "What does Korle Bu offer and how does it compare to other hospitals?" → SEARCH,SQL
- Never return more than 2 categories.
- If in doubt, return just one.

Respond with ONLY the category name(s). No explanation.
Examples of valid responses: SQL | SEARCH | GEO,SQL | ANOMALY,GEO"""

VALID_INTENTS = {"SQL", "SEARCH", "EXTRACT", "ANOMALY", "GEO"}


@mlflow.trace(name="supervisor_node", span_type="AGENT")
def supervisor_node(state: AgentState) -> dict:
    """Normalize the user query (fix typos/grammar), then classify intent(s).

    Returns the cleaned query and a list of intents. Composite queries
    produce 2 intents for LangGraph fan-out; simple queries produce 1.
    Defaults to SQL (Genie) for unrecognized intents.
    """
    raw_query = state["query"]

    # Step 1: Normalize — fix typos & grammar
    cleaned = query_llm(NORMALIZE_PROMPT, raw_query, max_tokens=150).strip()
    # Fallback: if normalization returns empty or something weird, keep original
    if not cleaned or len(cleaned) > len(raw_query) * 5:
        cleaned = raw_query

    # Step 2: Classify intent(s) on the cleaned query
    raw_intent = query_llm(ROUTER_PROMPT, cleaned, max_tokens=20).strip().upper()

    # Parse: "GEO,SQL" → ["GEO", "SQL"] or "SQL" → ["SQL"]
    tokens = [t.strip() for t in raw_intent.replace(" ", "").split(",")]
    intents = [t for t in tokens if t in VALID_INTENTS]

    # Deduplicate while preserving order, cap at 2
    seen = set()
    unique_intents = []
    for i in intents:
        if i not in seen:
            seen.add(i)
            unique_intents.append(i)
    intents = unique_intents[:2]

    # Fallback: default to SQL if nothing valid was parsed
    if not intents:
        intents = ["SQL"]

    return {"query": cleaned, "intents": intents}
