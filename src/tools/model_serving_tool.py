"""Databricks Model Serving SDK wrapper — LLM inference.

Calls a foundation model hosted on Databricks Model Serving for
intent classification, extraction, reasoning, and synthesis.

Ref: https://docs.databricks.com/en/machine-learning/model-serving
"""

from databricks.sdk.service.serving import ChatMessage, ChatMessageRole

from src.config import LLM_ENDPOINT, db_client


def query_llm(
    system_prompt: str,
    user_message: str,
    max_tokens: int = 2048,
    temperature: float = 0.1,
) -> str:
    """Call foundation model via Databricks Model Serving.

    Args:
        system_prompt: System-level instructions for the LLM.
        user_message: User-facing content to process.
        max_tokens: Maximum response length.
        temperature: Sampling temperature (lower = more deterministic).

    Returns:
        The LLM's text response.
    """
    response = db_client.serving_endpoints.query(
        name=LLM_ENDPOINT,
        messages=[
            ChatMessage(role=ChatMessageRole.SYSTEM, content=system_prompt),
            ChatMessage(role=ChatMessageRole.USER, content=user_message),
        ],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return response.choices[0].message.content
