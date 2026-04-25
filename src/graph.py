"""LangGraph: supervisor → fan-out → synthesis → END."""

import mlflow
import uuid
from langgraph.graph import END, StateGraph

from src.nodes.geospatial import geospatial_node
from src.nodes.idp_extraction import idp_extraction_node
from src.nodes.rag_agent import rag_agent_node
from src.nodes.sql_agent import sql_agent_node
from src.nodes.supervisor import supervisor_node
from src.nodes.synthesis import synthesis_node
from src.nodes.trust_scorer import trust_scorer_node
from src.state import AgentState
from src import trace_context

INTENT_TO_NODE = {
    "SQL": "SQL",
    "SEARCH": "SEARCH",
    "EXTRACT": "EXTRACT",
    "TRUST": "TRUST",
    "GEO": "GEO",
}


def route_by_intents(state: AgentState) -> list[str]:
    intents = state["intents"]
    return [INTENT_TO_NODE[i] for i in intents if i in INTENT_TO_NODE]


workflow = StateGraph(AgentState)
workflow.add_node("supervisor", supervisor_node)
workflow.add_node("SQL", sql_agent_node)
workflow.add_node("SEARCH", rag_agent_node)
workflow.add_node("EXTRACT", idp_extraction_node)
workflow.add_node("TRUST", trust_scorer_node)
workflow.add_node("GEO", geospatial_node)
workflow.add_node("synthesis", synthesis_node)

workflow.set_entry_point("supervisor")
workflow.add_conditional_edges(
    "supervisor",
    route_by_intents,
    {
        "SQL": "SQL",
        "SEARCH": "SEARCH",
        "EXTRACT": "EXTRACT",
        "TRUST": "TRUST",
        "GEO": "GEO",
    },
)
workflow.add_edge("SQL", "synthesis")
workflow.add_edge("SEARCH", "synthesis")
workflow.add_edge("EXTRACT", "synthesis")
workflow.add_edge("TRUST", "synthesis")
workflow.add_edge("GEO", "synthesis")
workflow.add_edge("synthesis", END)

graph = workflow.compile()


def run_graph(
    query: str,
    correlation_id: str | None = None,
    initial_citations: list | None = None,
) -> dict:
    """
    Run the full graph; return final AgentState as a dict.
    `correlation_id` is propagated in state, citations, and MLflow tags (via context var).
    """
    cid = (correlation_id or "").strip() or str(uuid.uuid4())
    token = trace_context.current_correlation_id.set(cid)
    try:
        out = graph.invoke(
            {
                "query": query,
                "citations": initial_citations or [],
                "correlation_id": cid,
            }
        )
        return {**out, "correlation_id": cid}
    finally:
        trace_context.current_correlation_id.reset(token)


@mlflow.trace
def run_agent(query: str) -> str:
    """Run the full CareCompass graph; return Markdown answer."""
    r = run_graph(query).get("final_answer") or "No answer produced."
    return (r.strip() or "No answer produced.")
