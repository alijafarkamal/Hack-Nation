"""RAG Agent node — performs semantic search over facility free-form text.

Uses Databricks Mosaic AI Vector Search to find facilities matching
the user's query by semantic similarity over procedure/equipment/capability columns.

Ref: https://docs.databricks.com/en/generative-ai/vector-search
"""

import mlflow

from src.state import AgentState
from src.tools.vector_search_tool import query_vector_search


@mlflow.trace(name="rag_agent_node", span_type="AGENT")
def rag_agent_node(state: AgentState) -> dict:
    """RAG Agent — semantic search, returns top-k matching facilities + citation."""
    results = query_vector_search(state["query"])
    return {
        "search_result": results,
        "citations": [{"source": "vector_search", "hits": len(results)}],
    }
