"""Graph compile and structure."""

import os

import pytest

from src.graph import graph

requires_creds = pytest.mark.skipif(
    not (os.getenv("DATABRICKS_HOST") and os.getenv("DATABRICKS_TOKEN")),
    reason="Supervisor needs LLM",
)


def test_graph_compiles():
    assert graph is not None


@requires_creds
def test_supervisor_returns_intents_list():
    from src.nodes.supervisor import supervisor_node

    out = supervisor_node(
        {
            "query": "How many hospitals are in Bihar?",
            "citations": [],
        }  # type: ignore[typeddict-item]
    )
    assert "intents" in out
    assert isinstance(out["intents"], list)
    assert len(out["intents"]) >= 1
    assert all(i in ("SQL", "SEARCH", "EXTRACT", "TRUST", "GEO") for i in out["intents"])


@requires_creds
def test_route_trust_intent_phrase():
    from src.nodes.supervisor import supervisor_node

    out = supervisor_node(
        {
            "query": "Which facilities claim ICU or surgery but have empty equipment fields?",
            "citations": [],
        }  # type: ignore[typeddict-item]
    )
    assert "TRUST" in out["intents"] or "SQL" in out["intents"]
