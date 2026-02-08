"""SQL Agent node — sends the user question to Databricks Genie for Text-to-SQL.

Genie generates SQL, executes it against the Delta table in Unity Catalog,
and returns structured results + natural language answer.

When Genie returns only an aggregate (COUNT / SUM), the agent fires a
follow-up query to retrieve the individual facility names so the
synthesis node can cite real evidence.

Ref: https://docs.databricks.com/en/genie/
"""

import logging
import mlflow

from src.state import AgentState
from src.tools.genie_tool import query_genie

log = logging.getLogger(__name__)


def _is_aggregate_only(result: dict) -> bool:
    """Return True if Genie returned only a count/aggregate, not facility rows."""
    data = result.get("data", [])
    cols = [c.lower() for c in result.get("columns", [])]
    # Aggregate if: single row with a single numeric column, or columns are count-like
    if len(data) <= 1 and len(cols) <= 2:
        count_keywords = {"count", "cnt", "total", "sum", "avg", "min", "max"}
        if any(kw in c for c in cols for kw in count_keywords):
            return True
        # Single numeric value
        if len(data) == 1 and len(data[0]) == 1:
            try:
                int(data[0][0])
                return True
            except (ValueError, TypeError):
                pass
    return False


@mlflow.trace(name="sql_agent_node", span_type="AGENT")
def sql_agent_node(state: AgentState) -> dict:
    """SQL Agent — forwards query to Genie, returns structured results + citation.

    If Genie returns only an aggregate count, fires a follow-up to list
    the actual facility names, regions, and types.
    """
    result = query_genie(state["query"])

    # If we only got a count, ask Genie to list the actual facilities
    if _is_aggregate_only(result):
        log.info("Aggregate-only result detected — fetching facility details")
        detail_query = f"List the names, regions, and types of the facilities for: {state['query']}"
        detail_result = query_genie(detail_query)
        if detail_result.get("data"):
            result["detail_data"] = detail_result["data"]
            result["detail_columns"] = detail_result.get("columns", [])

    return {
        "sql_result": result,
        "citations": [{"source": "genie", "sql": result.get("sql"), "description": result.get("description")}],
    }
