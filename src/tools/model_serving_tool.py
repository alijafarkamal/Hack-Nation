"""LLM inference — Databricks Model Serving with OpenRouter fallback."""

import logging

import mlflow
import requests
from databricks.sdk.service.serving import ChatMessage, ChatMessageRole

from src.config import LLM_ENDPOINT, OPENROUTER_API_KEY, db_client
from src import trace_context

logger = logging.getLogger(__name__)

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_OPENROUTER_MODEL = "minimax/minimax-m2.1"


def _call_openrouter(
    system_prompt: str,
    user_message: str,
    max_tokens: int = 2048,
    temperature: float = 0.1,
) -> str:
    if not OPENROUTER_API_KEY:
        raise RuntimeError(
            "Databricks LLM failed and no OPENROUTER_API_KEY configured."
        )
    resp = requests.post(
        _OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": _OPENROUTER_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


@mlflow.trace(name="query_llm", span_type="LLM")
def query_llm(
    system_prompt: str,
    user_message: str,
    max_tokens: int = 2048,
    temperature: float = 0.1,
) -> str:
    cid = trace_context.current_correlation_id.get()
    if cid:
        try:
            mlflow.set_tag("care-india.correlation_id", str(cid)[:200])
        except Exception:  # noqa: BLE001
            pass
    try:
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
    except Exception as e:
        logger.warning("Databricks Model Serving failed: %s — OpenRouter fallback", e)
    try:
        return _call_openrouter(system_prompt, user_message, max_tokens, temperature)
    except Exception as e2:
        logger.error("All LLM backends failed: %s", e2)
        return (
            "[LLM unavailable] Set DATABRICKS_TOKEN and valid LLM_ENDPOINT, "
            "or OPENROUTER_API_KEY for fallback."
        )
