"""Databricks Genie SDK wrapper — Text-to-SQL."""

import time

import mlflow
from databricks.sdk.service.dashboards import MessageStatus

from src.config import GENIE_SPACE_ID, db_client


@mlflow.trace(name="query_genie", span_type="TOOL")
def query_genie(question: str, timeout_seconds: int = 60) -> dict:
    """Send natural language to Genie; return SQL, results, and text answer."""
    if not GENIE_SPACE_ID:
        return {
            "sql": None,
            "description": "GENIE_SPACE_ID not set",
            "text": "Configure GENIE_SPACE_ID in .env",
            "data": [],
            "columns": [],
        }

    wait = db_client.genie.start_conversation(
        space_id=GENIE_SPACE_ID,
        content=question,
    )
    conv_id = wait.conversation_id
    msg_id = wait.message_id

    for _ in range(max(1, timeout_seconds // 2)):
        time.sleep(2)
        msg = db_client.genie.get_message(
            space_id=GENIE_SPACE_ID,
            conversation_id=conv_id,
            message_id=msg_id,
        )
        if msg.status == MessageStatus.COMPLETED:
            break
        if msg.status == MessageStatus.FAILED:
            return {
                "sql": None,
                "description": "Genie query failed",
                "text": "Query failed",
                "data": [],
                "columns": [],
            }
    else:
        return {
            "sql": None,
            "description": "Genie timed out",
            "text": "Query timed out",
            "data": [],
            "columns": [],
        }

    result: dict = {
        "sql": None,
        "description": None,
        "text": None,
        "data": [],
        "columns": [],
    }

    for att in msg.attachments or []:
        if att.query:
            result["sql"] = att.query.query
            result["description"] = att.query.description
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
                pass
        if att.text and att.text.content:
            result["text"] = att.text.content

    return result
