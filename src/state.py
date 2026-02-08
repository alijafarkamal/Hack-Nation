"""LangGraph state schema — shared state passed between all agent nodes.

Ref: https://langchain-ai.github.io/langgraph/concepts/low_level/#state
"""

import operator
from typing import Annotated, Literal, TypedDict

IntentType = Literal["SQL", "SEARCH", "EXTRACT", "ANOMALY", "GEO"]


class AgentState(TypedDict):
    """Shared state passed between all LangGraph nodes."""

    query: str
    """User question (normalized by supervisor to fix typos/grammar)."""

    intents: list[IntentType]
    """One or more intents classified by the supervisor.

    Composite queries (e.g., "hospitals near Tamale with cardiology deserts")
    fan-out to 2+ agents in parallel; simple queries get a single intent.
    """

    sql_result: dict | None
    """Structured results from Databricks Genie (Text-to-SQL)."""

    search_result: list | None
    """Semantic search results from Databricks Vector Search."""

    extraction_result: dict | None
    """Structured facts extracted from free-form text by the IDP Extraction node."""

    anomaly_result: str | None
    """Anomaly analysis from the Medical Reasoning node via Model Serving."""

    geo_result: dict | None
    """Geospatial results from local Haversine / desert detection."""

    final_answer: str | None
    """User-facing answer produced by the synthesis node."""

    citations: Annotated[list, operator.add]
    """Audit trail — each agent appends its source info for MLflow tracing.

    Uses operator.add reducer so parallel fan-out nodes can each append
    their citations without triggering INVALID_CONCURRENT_GRAPH_UPDATE.
    Ref: https://langchain-ai.github.io/langgraph/concepts/low_level/#reducers
    """
