"""Phase 2 tests — LangGraph compilation and intent routing.

These verify the graph compiles and the supervisor routes correctly.

Usage: pytest tests/test_graph.py -v
"""

import pytest


def test_graph_compiles():
    """The LangGraph state graph must compile without errors."""
    from src.graph import graph

    assert graph is not None


def test_route_sql_intent():
    """Supervisor routes count queries to SQL agent."""
    from src.nodes.supervisor import supervisor_node

    result = supervisor_node(
        {"query": "How many hospitals have cardiology?", "citations": []}
    )
    assert result["intent"] == "SQL"


def test_route_search_intent():
    """Supervisor routes facility lookup queries to SEARCH agent."""
    from src.nodes.supervisor import supervisor_node

    result = supervisor_node(
        {"query": "What services does Korle Bu offer?", "citations": []}
    )
    assert result["intent"] == "SEARCH"


def test_route_extract_intent():
    """Supervisor routes extraction queries to EXTRACT agent."""
    from src.nodes.supervisor import supervisor_node

    result = supervisor_node(
        {"query": "Extract capabilities for Tamale Teaching Hospital", "citations": []}
    )
    assert result["intent"] == "EXTRACT"


def test_route_anomaly_intent():
    """Supervisor routes anomaly queries to ANOMALY agent."""
    from src.nodes.supervisor import supervisor_node

    result = supervisor_node(
        {
            "query": "Facilities claiming surgery but lacking equipment?",
            "citations": [],
        }
    )
    assert result["intent"] == "ANOMALY"


def test_route_geo_intent():
    """Supervisor routes geospatial queries to GEO agent."""
    from src.nodes.supervisor import supervisor_node

    result = supervisor_node(
        {"query": "Where are ophthalmology deserts in Ghana?", "citations": []}
    )
    assert result["intent"] == "GEO"
