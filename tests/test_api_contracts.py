"""API route contracts (no Databricks; mock heavy graph)."""

from __future__ import annotations

import sys
import unittest.mock as mock

from fastapi.testclient import TestClient

# Ensure project root
sys.path.insert(0, ".")


def _client():
    from backend_api.main import app

    return TestClient(app)


@mock.patch("backend_api.main.triage_service.run_triage_session")
def test_triage_analyze(mock_run):
    from backend_api.main import app

    mock_run.return_value = {
        "session_id": "s1",
        "query_used": "q",
        "capabilities_needed": ["emergencyMedicine"],
        "red_flags": [],
        "graph": {
            "final_answer": "a",
            "citations": [],
            "correlation_id": "cid",
        },
    }
    c = TestClient(app)
    r = c.post(
        "/triage/analyze",
        json={"symptoms_text": "chest pain in rural Bihar", "metadata": {}},
    )
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["session_id"] == "s1"
    assert "safety" in (j.get("safety_disclaimer") or "").lower() or "capability" in (j.get("safety_disclaimer") or "").lower() or "disclaimer" in j


def test_healthz():
    r = _client().get("/healthz")
    assert r.status_code == 200
    j = r.json()
    assert j["ok"] is True
    assert "integrations" in j
    assert "twilio" in j.get("integrations", {})


def test_referral_preview_send():
    c = _client()
    p = c.post(
        "/referral/preview",
        json={
            "session_id": "s1",
            "to_facility": "Rural CHC A",
            "patient_summary": "needs surgery consult",
        },
    )
    assert p.status_code == 200, p.text
    pid = p.json()["preview_id"]
    s = c.post("/referral/send", json={"preview_id": pid})
    assert s.status_code == 200, s.text
    sj = s.json()
    assert sj["success"] is True
    assert sj["audit_id"]
    assert sj.get("mode") in ("mock", "twilio", "mock_fallback")


@mock.patch("backend_api.services.policy_service._run_facility_sql")
def test_policy_endpoints(mock_sql):
    from backend_api.main import app

    mock_sql.return_value = [
        {
            "name": "A",
            "state_normalized": "Bihar",
            "pin_code": "800001",
            "specialties": "[]",
            "trust_score": 0.7,
            "trust_flag": "high",
            "procedure": "[]",
            "equipment": "[]",
            "capability": "[]",
        },
    ]
    c = TestClient(app)
    r = c.get("/policy/deserts", params={"specialty": "emergency", "level": "state"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert "desert_states" in d
    assert "citations" in d
    p = c.get("/policy/pin-risk/800001")
    assert p.status_code == 200, p.text
    assert p.json()["pin_code"] == "800001"


@mock.patch("backend_api.services.enrichment_service.tavily_effective", return_value=False)
def test_enrichment_503_without_tavily(_mock_tavily):
    from backend_api.main import app

    c = TestClient(app)
    r = c.post(
        "/enrichment/facility",
        json={"facility_name": "Test", "district": "", "state": ""},
    )
    assert r.status_code == 503


def test_geospatial_desert_pins_unit():
    from src.nodes.geospatial import find_desert_pins, find_desert_states

    fac = [
        {
            "state_normalized": "Bihar",
            "pin_code": "800001",
            "specialties": '["ophthalmology"]',
        },
        {
            "state_normalized": "Bihar",
            "pin_code": "800002",
            "specialties": '["emergency"]',
        },
    ]
    assert "800001" in find_desert_pins(fac, "emergency")
    # Bihar has 800002 with emergency → state is not a desert for this token
    assert "Bihar" not in find_desert_states(fac, "emergency")