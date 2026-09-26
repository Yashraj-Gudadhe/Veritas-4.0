import pytest
from app.evidence.decision_gate import VeritasDecisionGate

def test_decision_gate_supported():
    status, review, _ = VeritasDecisionGate.evaluate(
        supporting_evidence=[{"evidence_id": "EV-001"}],
        conflicting_evidence=[],
        contradictions=[],
        questionable_evidence=[],
        missing_information=[],
        overall_score=92.0
    )
    assert status == "SUPPORTED"
    assert review is False

def test_decision_gate_conflicting():
    status, review, _ = VeritasDecisionGate.evaluate(
        supporting_evidence=[{"evidence_id": "EV-001"}],
        conflicting_evidence=[{"evidence_id": "EV-002"}],
        contradictions=[{"id": "CON-001"}],
        questionable_evidence=[],
        missing_information=[],
        overall_score=78.0
    )
    assert status == "CONFLICTING"
    assert review is True

def test_decision_gate_additional_info_required():
    status, review, _ = VeritasDecisionGate.evaluate(
        supporting_evidence=[{"evidence_id": "EV-001"}],
        conflicting_evidence=[],
        contradictions=[],
        questionable_evidence=[],
        missing_information=[{"category": "CRITICAL", "item": "Repeat measurement"}],
        overall_score=85.0
    )
    assert status == "ADDITIONAL_INFORMATION_REQUIRED"
    assert review is True

def test_decision_gate_questionable():
    status, review, _ = VeritasDecisionGate.evaluate(
        supporting_evidence=[],
        conflicting_evidence=[],
        contradictions=[],
        questionable_evidence=[{"evidence_id": "EV-004"}],
        missing_information=[],
        overall_score=35.0
    )
    assert status == "QUESTIONABLE"
    assert review is True

def test_decision_gate_no_reliable_conclusion():
    status, review, _ = VeritasDecisionGate.evaluate(
        supporting_evidence=[],
        conflicting_evidence=[],
        contradictions=[],
        questionable_evidence=[],
        missing_information=[],
        overall_score=0.0
    )
    assert status == "NO_RELIABLE_CONCLUSION"
    assert review is True
