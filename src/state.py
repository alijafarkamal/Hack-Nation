"""LangGraph state schema — shared state passed between all agent nodes.

Ref: https://langchain-ai.github.io/langgraph/concepts/low_level/#state
"""

from typing import Literal, TypedDict


class AgentState(TypedDict):
    """Shared state passed between all LangGraph nodes."""

    query: str
    """Original user question."""

    intent: Literal["SQL", "SEARCH", "EXTRACT", "ANOMALY", "GEO"]
    """Classified by the supervisor node."""

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

    citations: list
    """Audit trail — each agent appends its source info for MLflow tracing."""
