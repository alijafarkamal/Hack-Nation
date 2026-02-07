"""Databricks Model Serving SDK wrapper — LLM inference.

Calls a foundation model (Llama 3.3 70B) hosted on Databricks
Model Serving for intent classification, extraction, reasoning, and synthesis.

Ref: https://docs.databricks.com/en/machine-learning/model-serving
"""

from src.config import db_client


def query_llm(system_prompt: str, user_message: str) -> str:
    """Call foundation model via Databricks Model Serving.

    Args:
        system_prompt: System-level instructions for the LLM.
        user_message: User-facing content to process.

    Returns:
        The LLM's text response.
    """
    response = db_client.serving_endpoints.query(
        name="databricks-meta-llama-3-3-70b-instruct",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )
    return response.choices[0].message.content
