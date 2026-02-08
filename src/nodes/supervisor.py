"""Supervisor node — classifies user intent and drives conditional routing.

Uses Databricks Model Serving LLM to classify each query into one of:
SQL, SEARCH, EXTRACT, ANOMALY, GEO.
"""

from src.state import AgentState
from src.tools.model_serving_tool import query_llm

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


def supervisor_node(state: AgentState) -> dict:
    """Classify user intent using Databricks Model Serving LLM.

    Returns the intent label which drives conditional routing in the graph.
    Defaults to SQL (Genie) for unrecognized intents.
    """
    intent = query_llm(ROUTER_PROMPT, state["query"], max_tokens=10).strip().upper()
    # Clean up: take only the first word in case the LLM adds extra
    intent = intent.split()[0] if intent else "SQL"
    if intent not in VALID_INTENTS:
        intent = "SQL"
    return {"intent": intent}
