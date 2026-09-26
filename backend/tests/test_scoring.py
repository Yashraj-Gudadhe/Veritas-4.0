import pytest
from app.scoring.evaluator import VeritasScorer

def test_veritas_scoring_formula():
    item = {
        "evidence_id": "EV-001",
        "authority_tier": 1,
        "authority_score": 1.0,
        "relevance_score": 1.0,
        "recency_score": 1.0,
        "methodology_score": 1.0,
        "traceability_score": 1.0
    }
    scored = VeritasScorer.evaluate_evidence_item(item)
    # Expected: (0.30*1.0 + 0.25*1.0 + 0.15*1.0 + 0.15*1.0 + 0.15*1.0) * 100 = 100.0
    assert scored["evidence_score"] == 100.0
    assert scored["quality_label"] == "HIGH"

def test_veritas_scoring_low_authority():
    item = {
        "evidence_id": "EV-002",
        "authority_tier": 5,
        "authority_score": 0.15,
        "relevance_score": 0.50,
        "recency_score": 0.40,
        "methodology_score": 0.20,
        "traceability_score": 0.10
    }
    scored = VeritasScorer.evaluate_evidence_item(item)
    # 0.30*0.15 + 0.25*0.50 + 0.15*0.40 + 0.15*0.20 + 0.15*0.10 = 0.045 + 0.125 + 0.06 + 0.03 + 0.015 = 0.275 -> 27.5
    assert scored["evidence_score"] < 50.0
    assert scored["quality_label"] == "QUESTIONABLE"

def test_overall_breakdown_aggregation():
    items = [
        {"authority_score": 0.9, "relevance_score": 0.8, "recency_score": 0.9, "methodology_score": 0.9, "traceability_score": 1.0},
        {"authority_score": 0.9, "relevance_score": 0.8, "recency_score": 0.9, "methodology_score": 0.9, "traceability_score": 1.0}
    ]
    breakdown = VeritasScorer.calculate_overall_breakdown(items)
    assert breakdown.composite_veritas_score > 80.0
    assert breakdown.quality_tier in ("HIGH", "MODERATE")
