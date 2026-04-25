"""MLflow ResponsesAgent wrapper for the CareCompass LangGraph."""

from __future__ import annotations

from typing import Generator
from uuid import uuid4

import mlflow
from mlflow.pyfunc import ResponsesAgent
from mlflow.types.responses import (
    ResponsesAgentRequest,
    ResponsesAgentResponse,
    ResponsesAgentStreamEvent,
)


class CareCompassAgent(ResponsesAgent):
    """ResponsesAgent around the CareCompass LangGraph (stateless per request)."""

    def __init__(self) -> None:
        from src.graph import graph

        self.graph = graph

    def predict(self, request: ResponsesAgentRequest) -> ResponsesAgentResponse:
        user_query = self._extract_query(request)
        result = self.graph.invoke({"query": user_query, "citations": []})
        answer = result.get("final_answer", "No answer produced.")
        return ResponsesAgentResponse(
            output=[self.create_text_output_item(text=answer, id=str(uuid4()))]
        )

    def predict_stream(
        self, request: ResponsesAgentRequest
    ) -> Generator[ResponsesAgentStreamEvent, None, None]:
        user_query = self._extract_query(request)
        result = self.graph.invoke({"query": user_query, "citations": []})
        answer = result.get("final_answer", "No answer produced.")
        item_id = str(uuid4())
        words = answer.split(" ")
        for i, word in enumerate(words):
            chunk = word + (" " if i < len(words) - 1 else "")
            yield self.create_text_delta(delta=chunk, item_id=item_id)
        yield ResponsesAgentStreamEvent(
            type="response.output_item.done",
            item=self.create_text_output_item(text=answer, id=item_id),
        )

    @staticmethod
    def _extract_query(request: ResponsesAgentRequest) -> str:
        for msg in reversed(request.input):
            msg_dict = msg.model_dump() if hasattr(msg, "model_dump") else msg
            if msg_dict.get("role") == "user":
                content = msg_dict.get("content", "")
                if isinstance(content, list):
                    parts = [
                        p.get("text", "") if isinstance(p, dict) else str(p)
                        for p in content
                    ]
                    return " ".join(parts).strip()
                return str(content).strip()
        return "Hello"


try:
    mlflow.models.set_retriever_schema(
        name="india_facility_vector_search",
        primary_key="unique_id",
        text_column="searchable_text",
        doc_uri="",
        other_columns=["name", "facilityTypeId", "address_city", "state_normalized", "pin_code"],
    )
except Exception:
    pass
