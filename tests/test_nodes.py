"""Phase 2 tests — Node contract tests (expected state keys).

These verify each agent node returns the expected keys in its output dict.
Requires Databricks services to be running.

Usage: pytest tests/test_nodes.py -v
"""

import pytest


def test_sql_node_returns_expected_keys():
    """SQL Agent must return sql_result and updated citations."""
    from src.nodes.sql_agent import sql_agent_node

    state = {"query": "How many hospitals?", "citations": []}
    result = sql_agent_node(state)
    assert "sql_result" in result
    assert "citations" in result
    assert len(result["citations"]) > 0


def test_rag_node_returns_expected_keys():
    """RAG Agent must return search_result and updated citations."""
    from src.nodes.rag_agent import rag_agent_node

    state = {"query": "cardiology services", "citations": []}
    result = rag_agent_node(state)
    assert "search_result" in result
    assert len(result["search_result"]) > 0


def test_geo_node_returns_expected_keys():
    """Geospatial node must return geo_result and updated citations."""
    from src.nodes.geospatial import geospatial_node

    state = {"query": "Hospitals near Tamale", "citations": []}
    result = geospatial_node(state)
    assert "geo_result" in result
    assert "citations" in result


def test_synthesis_node_returns_final_answer():
    """Synthesis node must return final_answer given mock input."""
    from src.nodes.synthesis import synthesis_node

    state = {
        "query": "test",
        "sql_result": {"sql": "SELECT 1", "results": [["1"]]},
        "search_result": None,
        "extraction_result": None,
        "anomaly_result": None,
        "geo_result": None,
        "citations": [{"source": "test"}],
    }
    result = synthesis_node(state)
    assert "final_answer" in result
    assert len(result["final_answer"]) > 0
