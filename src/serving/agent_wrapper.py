"""Mosaic AI Agent Framework — ResponsesAgent wrapper for the LangGraph graph.

Wraps the multi-agent LangGraph pipeline as an MLflow ResponsesAgent so it
can be:
  1. Logged to MLflow with `mlflow.pyfunc.log_model`
  2. Registered in Unity Catalog
  3. Deployed on Databricks Model Serving

The wrapper converts between the OpenAI Responses schema and our internal
AgentState, supporting both single-turn predict and streaming predict.

Ref: https://docs.databricks.com/aws/en/generative-ai/agent-framework/author-agent
Ref: https://mlflow.org/docs/latest/genai/serving/responses-agent
"""

from typing import Generator
from uuid import uuid4

import mlflow
from mlflow.pyfunc import ResponsesAgent
from mlflow.types.responses import (
    ResponsesAgentRequest,
    ResponsesAgentResponse,
    ResponsesAgentStreamEvent,
)


class GhanaMedicalAgent(ResponsesAgent):
    """ResponsesAgent wrapper around the Ghana Medical Intelligence LangGraph.

    The LangGraph graph is compiled once in __init__ and reused across
    predict() calls.  Each call reconstructs state from the incoming
    request (no cross-request memory — stateless per Databricks serving).
    """

    def __init__(self):
        # Import graph here to keep module-level imports light and avoid
        # circular imports when MLflow loads the model.
        from src.graph import graph

        self.graph = graph

    # ── Non-streaming predict ──────────────────────────────────────────────
    def predict(
        self, request: ResponsesAgentRequest
    ) -> ResponsesAgentResponse:
        """Handle a single inference request.

        Extracts the last user message, runs the LangGraph graph, and
        returns the synthesis answer in ResponsesAgent format.
        """
        user_query = self._extract_query(request)

        # Run the full agent graph
        result = self.graph.invoke({"query": user_query, "citations": []})
        answer = result.get("final_answer", "No answer produced.")

        output_item = self.create_text_output_item(
            text=answer, id=str(uuid4())
        )
        return ResponsesAgentResponse(output=[output_item])

    # ── Streaming predict ──────────────────────────────────────────────────
    def predict_stream(
        self, request: ResponsesAgentRequest
    ) -> Generator[ResponsesAgentStreamEvent, None, None]:
        """Stream the agent response word-by-word.

        The LangGraph graph itself runs synchronously; streaming is applied
        to the final answer to provide incremental UI feedback.
        """
        user_query = self._extract_query(request)

        # Run the full agent graph (synchronous)
        result = self.graph.invoke({"query": user_query, "citations": []})
        answer = result.get("final_answer", "No answer produced.")

        # Stream the answer in word-sized chunks
        item_id = str(uuid4())
        words = answer.split(" ")
        for i, word in enumerate(words):
            chunk = word + (" " if i < len(words) - 1 else "")
            yield self.create_text_delta(delta=chunk, item_id=item_id)

        # Final aggregated event
        yield ResponsesAgentStreamEvent(
            type="response.output_item.done",
            item=self.create_text_output_item(text=answer, id=item_id),
        )

    # ── Helpers ────────────────────────────────────────────────────────────
    @staticmethod
    def _extract_query(request: ResponsesAgentRequest) -> str:
        """Pull the last user message from the Responses-format input."""
        for msg in reversed(request.input):
            msg_dict = msg.model_dump() if hasattr(msg, "model_dump") else msg
            if msg_dict.get("role") == "user":
                content = msg_dict.get("content", "")
                # content can be a string or a list of content parts
                if isinstance(content, list):
                    # Extract text from content parts
                    parts = [
                        p.get("text", "") if isinstance(p, dict) else str(p)
                        for p in content
                    ]
                    return " ".join(parts).strip()
                return str(content).strip()
        return "Hello"


# ── Set retriever schema for Vector Search integration ─────────────────────
# Maps our Vector Search output columns to MLflow's expected fields so that
# Databricks AI Playground can display retrieval source links automatically.
try:
    mlflow.models.set_retriever_schema(
        name="ghana_facility_vector_search",
        primary_key="unique_id",
        text_column="description",
        doc_uri="source_url",
        other_columns=["name", "facilityTypeId", "address_city", "specialties"],
    )
except Exception:
    # set_retriever_schema is deprecated in newer MLflow versions;
    # retriever spans are auto-detected when using VectorSearchRetrieverTool.
    pass
