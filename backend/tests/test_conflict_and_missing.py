import pytest
from app.schemas.evidence import Observation
from app.evidence.conflict_detector import ConflictDetector
from app.evidence.missing_detector import MissingEvidenceDetector
from app.evidence.requirement_engine import EvidenceRequirementEngine

def test_conflict_detection():
    supporting = [{
        "evidence_id": "EV-001",
        "source_name": "ACC/AHA",
        "title": "Hypertension Guideline",
        "text": "Defines hypertension at 130/80 mmHg threshold.",
        "publication_date": "2017-01-01",
        "supports_claim": True
    }]
    conflicting = [{
        "evidence_id": "EV-002",
        "source_name": "ESC/ESH",
        "title": "European Guidelines",
        "text": "Maintains 140/90 mmHg cutoff for hypertension diagnosis.",
        "publication_date": "2023-01-01",
        "difference_reason": "Divergent diagnostic threshold across geographic jurisdictions.",
        "supports_claim": False
    }]
    contradictions = ConflictDetector.detect_conflicts(supporting, conflicting)
    assert len(contradictions) == 1
    assert contradictions[0]["source_a_id"] == "EV-001"
    assert contradictions[0]["source_b_id"] == "EV-002"
    assert "Divergent" in contradictions[0]["difference_reason"]

def test_missing_evidence_detection():
    obs = [Observation(
        id="OBS-001",
        type="blood_pressure",
        name="Blood Pressure",
        value={"systolic": 85, "diastolic": 55},
        unit="mmHg",
        source="doc.pdf",
        page=1
    )]
    reqs = EvidenceRequirementEngine.generate_requirements(obs, [])
    assert len(reqs) >= 3

    missing = MissingEvidenceDetector.detect_missing(obs, reqs)
    assert len(missing) >= 1
    crit = [m for m in missing if m["category"] == "CRITICAL"]
    assert len(crit) >= 1
