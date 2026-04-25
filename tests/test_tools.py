"""Databricks service smoke tests — require credentials."""

import os

import pytest

requires_creds = pytest.mark.skipif(
    not (os.getenv("DATABRICKS_HOST") and os.getenv("DATABRICKS_TOKEN")),
    reason="Set DATABRICKS_HOST and DATABRICKS_TOKEN",
)


@requires_creds
def test_genie_returns_shape():
    from src.tools.genie_tool import query_genie

    result = query_genie("How many rows are in the main facilities table?")
    assert "sql" in result or "text" in result or "data" in result


@requires_creds
def test_vector_search_returns_list():
    from src.tools.vector_search_tool import query_vector_search

    results = query_vector_search("cardiology hospital Bihar", num_results=3)
    assert isinstance(results, list)


@requires_creds
def test_model_serving_returns_text():
    from src.tools.model_serving_tool import query_llm

    answer = query_llm("You are a test.", "Reply with exactly: ok")
    assert len(answer) > 0
