"""SQL Agent node — sends the user question to Databricks Genie for Text-to-SQL.

Genie generates SQL, executes it against the Delta table in Unity Catalog,
and returns structured results.

Ref: https://docs.databricks.com/en/genie/
"""

from src.state import AgentState
from src.tools.genie_tool import query_genie


def sql_agent_node(state: AgentState) -> dict:
    """SQL Agent — forwards query to Genie, returns structured results + citation."""
    result = query_genie(state["query"])
    return {
        "sql_result": result,
        "citations": state["citations"]
        + [{"source": "genie", "sql": result.get("sql")}],
    }
