"""LangGraph state schema — shared state passed between all agent nodes."""

import operator
from typing import Annotated, Literal, NotRequired, TypedDict

IntentType = Literal["SQL", "SEARCH", "EXTRACT", "TRUST", "GEO"]


class AgentState(TypedDict):
    """Shared state passed between all LangGraph nodes."""

    query: str
    """User question (normalized by supervisor)."""

    intents: list[IntentType]
    """One or more intents; composite queries fan out to 2 agents in parallel."""

    sql_result: dict | None
    """Structured results from Databricks Genie (Text-to-SQL)."""

    search_result: list | None
    """Semantic search results from Mosaic AI Vector Search."""

    extraction_result: dict | None
    """Structured facts from IDP extraction over free-form facility text."""

    trust_result: str | None
    """Trust / validation analysis (Validator Agent / Trust Scorer)."""

    geo_result: dict | None
    """Geospatial results (Haversine, PIN / state desert detection)."""

    final_answer: str | None
    """User-facing answer from synthesis."""

    citations: Annotated[list, operator.add]
    """Audit trail for MLflow tracing — parallel nodes append via operator.add."""

    # Machine-readable trust pipeline (two-pass + deterministic rules)
    trust_artifacts: NotRequired[dict | None]
    """Extractor + validator + disagreement + deterministic flags (JSON-serializable)."""

    # Structured synthesis (JSON) before rendered Markdown
    synthesis_artifacts: NotRequired[dict | None]
    """Parseable answer object + normalized citations for APIs."""

    correlation_id: NotRequired[str | None]
    """Request/session id for trace continuity (APIs set on invoke)."""
