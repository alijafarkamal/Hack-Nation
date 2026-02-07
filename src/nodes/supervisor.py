"""Supervisor node — classifies user intent and drives conditional routing.

Uses Databricks Model Serving LLM to classify each query into one of:
SQL, SEARCH, EXTRACT, ANOMALY, GEO.
"""

from src.state import AgentState
from src.tools.model_serving_tool import query_llm

ROUTER_PROMPT = """Classify this healthcare data question into ONE category:
- SQL: counts, aggregations, rankings, comparisons (e.g. "How many hospitals have cardiology?")
- SEARCH: specific facility services, capabilities, equipment (e.g. "What does Korle Bu offer?")
- EXTRACT: extract structured facts from unstructured text for a facility (e.g. "What procedures does Tamale Teaching Hospital perform?" or "Parse capabilities for facilities in Ashanti")
- ANOMALY: data inconsistencies, mismatches (e.g. "Facilities claiming surgery but lacking equipment?")
- GEO: distances, locations, medical deserts, coverage gaps (e.g. "Hospitals within 50km of Tamale?" or "Where are ophthalmology deserts?")
Respond with ONLY the category name."""

VALID_INTENTS = {"SQL", "SEARCH", "EXTRACT", "ANOMALY", "GEO"}


def supervisor_node(state: AgentState) -> dict:
    """Classify user intent using Databricks Model Serving LLM.

    Returns the intent label which drives conditional routing in the graph.
    Defaults to SQL (Genie) for unrecognized intents.
    """
    intent = query_llm(ROUTER_PROMPT, state["query"]).strip().upper()
    if intent not in VALID_INTENTS:
        intent = "SQL"
    return {"intent": intent}
