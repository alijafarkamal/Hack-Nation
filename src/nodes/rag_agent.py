"""RAG agent: semantic search over `searchable_text` via Vector Search."""

import mlflow

from src.state import AgentState
from src.tools.vector_search_tool import get_vector_search_status, query_vector_search


@mlflow.trace(name="rag_agent_node", span_type="AGENT")
def rag_agent_node(state: AgentState) -> dict:
    corr = (state.get("correlation_id") or "") or ""
    results = query_vector_search(state["query"], num_results=10)
    vs = get_vector_search_status()
    cits = [{"source": "vector_search", "hits": len(results), "correlation_id": corr}]
    if not vs.get("ok"):
        cits.append({
            "source": "vector_search",
            "field": "degradation",
            "evidence_snippet": str(vs.get("warning") or vs.get("error") or "vector search unavailable"),
            "confidence": 0.2,
            "correlation_id": corr,
        })
    return {
        "search_result": results,
        "citations": cits,
        "degraded_components": vs.get("degraded_components", []),
        "warnings": [vs.get("warning")] if vs.get("warning") else [],
    }
