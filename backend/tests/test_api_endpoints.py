import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "VERITAS" in data["app"]

def test_fixtures_endpoint():
    response = client.get("/api/fixtures")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 5
    assert data[0]["id"] == "demo-1"

def test_analyze_endpoint():
    payload = {
        "user_query": "Is a blood pressure reading of 120/80 mmHg normal?",
        "document_text": "CLINICAL REPORT\nBlood Pressure: 120/80 mmHg\nPulse: 70 bpm",
        "demo_id": "demo-1"
    }
    response = client.post("/api/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "decision_status" in data
    assert "evidence_quality_score" in data
    assert len(data["observations"]) >= 1
    assert "final_explanation" in data
    assert "audit_record" in data
    assert len(data["graph_nodes"]) >= 1
