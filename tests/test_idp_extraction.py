"""Phase 2 tests — IDP Extraction (Core Feature #1, 30% of scoring).

Verifies the IDP Extraction node retrieves facilities and extracts
structured facts from free-form text.

Usage: pytest tests/test_idp_extraction.py -v
"""

import pytest


def test_idp_extraction_returns_structured_facts():
    """IDP Extraction must return extraction_result with parsed data.

    This is the CORE of the challenge (IDP Innovation = 30%).
    """
    from src.nodes.idp_extraction import idp_extraction_node

    state = {
        "query": "Extract capabilities for Korle Bu Teaching Hospital",
        "citations": [],
    }
    result = idp_extraction_node(state)
    assert "extraction_result" in result
    assert "extractions" in result["extraction_result"]
    assert len(result["extraction_result"]["extractions"]) > 0


def test_idp_extraction_updates_citations():
    """IDP Extraction must append citation with facilities_processed count."""
    from src.nodes.idp_extraction import idp_extraction_node

    state = {"query": "Parse procedures for clinics in Accra", "citations": []}
    result = idp_extraction_node(state)
    assert "citations" in result
    assert any(c.get("source") == "idp_extraction" for c in result["citations"])
