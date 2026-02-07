"""Phase 1 tests — Databricks SDK wrapper smoke tests.

These verify each Databricks service responds to a simple request.
Run after Phase 1 (Foundation) when Genie Space, Vector Search index,
and Model Serving are configured.

Usage: pytest tests/test_tools.py -v
"""

import pytest


def test_genie_returns_response():
    """Smoke test: Genie responds to a simple count query."""
    from src.tools.genie_tool import query_genie

    result = query_genie("How many rows are in the table?")
    assert "results" in result or "sql" in result


def test_vector_search_returns_results():
    """Smoke test: Vector Search returns non-empty for a known term."""
    from src.tools.vector_search_tool import query_vector_search

    results = query_vector_search("cardiology")
    assert len(results) > 0


def test_model_serving_returns_text():
    """Smoke test: Model Serving LLM returns a non-empty string."""
    from src.tools.model_serving_tool import query_llm

    answer = query_llm("You are a test.", "Say hello.")
    assert len(answer) > 0
