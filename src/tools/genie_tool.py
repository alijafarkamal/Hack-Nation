"""Databricks Genie SDK wrapper — Text-to-SQL.

Sends a natural language question to Genie, which generates SQL,
executes it against the Delta table, and returns structured results.

Ref: https://docs.databricks.com/en/genie/
"""

import time

from databricks.sdk.service.dashboards import MessageStatus

from src.config import GENIE_SPACE_ID, db_client


def query_genie(question: str, timeout_seconds: int = 30) -> dict:
    """Send natural language to Genie, get SQL + results + text answer.

    Args:
        question: Natural language query (e.g., "How many hospitals have cardiology?")
        timeout_seconds: Max seconds to wait for Genie to complete.

    Returns:
        dict with keys:
          - 'sql': Generated SQL string (or None)
          - 'description': Genie's description of what it did
          - 'text': Natural language answer from Genie
          - 'data': Query result rows (list of lists)
          - 'columns': Column names for the data
    """
    # Start conversation
    wait = db_client.genie.start_conversation(
        space_id=GENIE_SPACE_ID,
        content=question,
    )
    conv_id = wait.conversation_id
    msg_id = wait.message_id

    # Poll until completed
    for _ in range(timeout_seconds // 2):
        time.sleep(2)
        msg = db_client.genie.get_message(
            space_id=GENIE_SPACE_ID,
            conversation_id=conv_id,
            message_id=msg_id,
        )
        if msg.status == MessageStatus.COMPLETED:
            break
        if msg.status == MessageStatus.FAILED:
            return {"sql": None, "description": "Genie query failed", "text": "Query failed", "data": [], "columns": []}
    else:
        return {"sql": None, "description": "Genie timed out", "text": "Query timed out", "data": [], "columns": []}

    # Extract results from attachments
    result = {"sql": None, "description": None, "text": None, "data": [], "columns": []}

    for att in msg.attachments or []:
        # Extract SQL query
        if att.query:
            result["sql"] = att.query.query
            result["description"] = att.query.description

            # Get the actual query results
            try:
                qr = db_client.genie.get_message_attachment_query_result(
                    space_id=GENIE_SPACE_ID,
                    conversation_id=conv_id,
                    message_id=msg_id,
                    attachment_id=att.attachment_id,
                )
                if qr.statement_response:
                    sr = qr.statement_response
                    if sr.result and sr.result.data_array:
                        result["data"] = sr.result.data_array
                    if sr.manifest and sr.manifest.schema:
                        result["columns"] = [c.name for c in sr.manifest.schema.columns]
            except Exception:
                pass  # Query result fetch failed — still return SQL + text

        # Extract text answer
        if att.text and att.text.content:
            result["text"] = att.text.content

    return result
