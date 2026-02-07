"""LangGraph state graph definition — the multi-agent orchestration layer.

Builds a StateGraph with:
  supervisor → conditional routing → agent nodes → synthesis → END

Each agent node calls a Databricks service via the SDK wrappers in src/tools/.
MLflow traces every run for citation auditing.

Ref: https://langchain-ai.github.io/langgraph/
"""

import mlflow
from langgraph.graph import END, StateGraph

from src.nodes.geospatial import geospatial_node
from src.nodes.idp_extraction import idp_extraction_node
from src.nodes.medical_reasoning import medical_reasoning_node
from src.nodes.rag_agent import rag_agent_node
from src.nodes.sql_agent import sql_agent_node
from src.nodes.supervisor import supervisor_node
from src.nodes.synthesis import synthesis_node
from src.state import AgentState


def route_by_intent(state: AgentState) -> str:
    """Conditional edge — routes to the right agent based on supervisor classification.

    Ref: https://langchain-ai.github.io/langgraph/concepts/low_level/#conditional-edges
    """
    return state["intent"]


# ---------------------------------------------------------------------------
# Build the graph
# ---------------------------------------------------------------------------
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("supervisor", supervisor_node)
workflow.add_node("SQL", sql_agent_node)
workflow.add_node("SEARCH", rag_agent_node)
workflow.add_node("EXTRACT", idp_extraction_node)
workflow.add_node("ANOMALY", medical_reasoning_node)
workflow.add_node("GEO", geospatial_node)
workflow.add_node("synthesis", synthesis_node)

# Edges: supervisor classifies intent → route to correct agent → merge in synthesis
workflow.set_entry_point("supervisor")
workflow.add_conditional_edges(
    "supervisor",
    route_by_intent,
    {
        "SQL": "SQL",
        "SEARCH": "SEARCH",
        "EXTRACT": "EXTRACT",
        "ANOMALY": "ANOMALY",
        "GEO": "GEO",
    },
)
workflow.add_edge("SQL", "synthesis")
workflow.add_edge("SEARCH", "synthesis")
workflow.add_edge("EXTRACT", "synthesis")
workflow.add_edge("ANOMALY", "synthesis")
workflow.add_edge("GEO", "synthesis")
workflow.add_edge("synthesis", END)

# Compile
graph = workflow.compile()


@mlflow.trace
def run_agent(query: str) -> str:
    """Run the full agent graph end-to-end.

    MLflow traces every step for citation auditing.
    Ref: https://docs.databricks.com/en/mlflow/llm-tracing

    Args:
        query: Natural language question about Ghana healthcare facilities.

    Returns:
        Markdown-formatted answer with citations.
    """
    result = graph.invoke({"query": query, "citations": []})
    return result["final_answer"]
