"""RAG agent: semantic search over `searchable_text` via Vector Search."""

import mlflow

from src.state import AgentState
from src.tools.vector_search_tool import query_vector_search


@mlflow.trace(name="rag_agent_node", span_type="AGENT")
def rag_agent_node(state: AgentState) -> dict:
    results = query_vector_search(state["query"], num_results=10)
    return {
        "search_result": results,
        "citations": [{"source": "vector_search", "hits": len(results)}],
    }
