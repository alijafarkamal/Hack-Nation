"""LangGraph state graph definition — the multi-agent orchestration layer.

Builds a StateGraph with:
  supervisor → conditional fan-out → 1-2 agent nodes in parallel → synthesis → END

Composite queries (e.g., "hospitals near Tamale with cardiology deserts") are
routed to 2 agents simultaneously via LangGraph fan-out. The synthesis node
merges results from all agents that ran.

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

# Map of intent labels to node names (they're the same here)
INTENT_TO_NODE = {
    "SQL": "SQL",
    "SEARCH": "SEARCH",
    "EXTRACT": "EXTRACT",
    "ANOMALY": "ANOMALY",
    "GEO": "GEO",
}


def route_by_intents(state: AgentState) -> list[str]:
    """Conditional edge — routes to 1 or 2 agents based on supervisor classification.

    Returning a list triggers LangGraph fan-out: all listed nodes execute
    in parallel, then converge at synthesis.

    Ref: https://langchain-ai.github.io/langgraph/concepts/low_level/#conditional-edges
    """
    intents = state["intents"]
    return [INTENT_TO_NODE[i] for i in intents if i in INTENT_TO_NODE]


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

# Edges: supervisor classifies intents → fan-out to 1-2 agents → converge at synthesis
workflow.set_entry_point("supervisor")
workflow.add_conditional_edges(
    "supervisor",
    route_by_intents,
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

    Composite queries fan-out to multiple agents in parallel;
    synthesis merges all results.

    MLflow traces every step for citation auditing.
    Ref: https://docs.databricks.com/en/mlflow/llm-tracing

    Args:
        query: Natural language question about Ghana healthcare facilities.

    Returns:
        Markdown-formatted answer with citations.
    """
    result = graph.invoke({"query": query, "citations": []})
    return result["final_answer"]
