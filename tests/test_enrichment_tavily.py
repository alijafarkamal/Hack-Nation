"""Tavily enrichment: parse + no-key behavior."""

from __future__ import annotations

import sys
import unittest.mock as mock

sys.path.insert(0, ".")

from backend_api.services import enrichment_service as es


def test_enrich_without_tavily_key():
    with mock.patch("backend_api.services.enrichment_service.tavily_effective", return_value=False):
        out = es.enrich_facility("Apollo Patna", "Patna", "Bihar", "cid")
        assert out["success"] is False
        assert "TAVILY" in (out.get("error") or "")


def test_enrich_parses_tavily_results():
    sample = {
        "results": [
            {
                "title": "City Hospital +91-9876-123456",
                "content": "24/7 emergency contact",
                "url": "https://hospital.com",
            }
        ]
    }
    with mock.patch("backend_api.services.enrichment_service.tavily_effective", return_value=True), mock.patch(
        "backend_api.services.enrichment_service.tavily_search", return_value=sample
    ):
        out = es.enrich_facility("City Hospital", "Patna", "Bihar", "cid")
        assert out["success"] is True
        assert out["enrichment"].get("website_estimated")
        assert out["citations"]
        assert any(c.get("source") == "tavily" for c in out["citations"] if isinstance(c, dict))


def test_tavily_search_failure_returns_graceful():
    with mock.patch("backend_api.services.enrichment_service.tavily_effective", return_value=True), mock.patch(
        "backend_api.services.enrichment_service.tavily_search", return_value=None
    ):
        out = es.enrich_facility("X", "", "", "cid")
        assert out["success"] is False
