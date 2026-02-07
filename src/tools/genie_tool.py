"""Databricks Genie SDK wrapper — Text-to-SQL.

Sends a natural language question to Genie, which generates SQL,
executes it against the Delta table, and returns structured results.

Ref: https://docs.databricks.com/en/genie/
"""

from src.config import db_client, GENIE_SPACE_ID


def query_genie(question: str) -> dict:
    """Send natural language to Genie, get SQL + results back.

    Args:
        question: Natural language query (e.g., "How many hospitals have cardiology?")

    Returns:
        dict with keys 'sql' (generated SQL) and 'results' (query output)
    """
    response = db_client.genie.start_conversation(
        space_id=GENIE_SPACE_ID,
        content=question,
    )
    return {"sql": response.sql, "results": response.attachments}
