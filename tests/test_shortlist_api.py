from unittest.mock import patch

from fastapi.testclient import TestClient

from backend_api.main import app


def test_shortlist_contracts():
    client = TestClient(app)
    payload = {"session_id": "mission-1", "facility_id": "facility-1", "facility_name": "District Hospital", "user_notes": "Call before transfer", "system_trust_score": 0.78, "system_verdict": "VERIFIED", "evidence": [{"source": "vector_search", "evidence_snippet": "ICU listed"}]}
    with patch("backend_api.services.shortlist_service.save", return_value={"success": True}):
        response = client.post("/shortlist/save", json=payload)
        assert response.status_code == 200 and response.json()["success"] is True
    with patch("backend_api.services.shortlist_service.list_for_session", return_value=[]):
        response = client.get("/shortlist/mission-1")
        assert response.status_code == 200 and response.json()["items"] == []
    with patch("backend_api.services.shortlist_service.update", return_value={"success": True}):
        response = client.put("/shortlist/update_note", json={"session_id": "mission-1", "facility_id": "facility-1", "user_notes": "Planner verified by phone", "trust_override": 0.9, "override_reason": "Direct confirmation"})
        assert response.status_code == 200


def test_shortlist_reports_missing_sql_config():
    client = TestClient(app)
    with patch("backend_api.services.shortlist_service.list_for_session", side_effect=RuntimeError("DATABRICKS_SQL_HTTP_PATH missing")):
        response = client.get("/shortlist/mission-2")
        assert response.status_code == 503 and "HTTP_PATH" in response.json()["detail"]
