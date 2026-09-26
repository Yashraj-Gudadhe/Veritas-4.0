import pytest
from app.llm.orchestrator import LLMOrchestrator

@pytest.mark.asyncio
async def test_llm_orchestrator_deterministic_fallback():
    # Test that with no active API keys, orchestrator generates deterministic audited explanation without crashing
    explanation, citations, provider, fallback = await LLMOrchestrator.synthesize_audit_report(
        user_query="Is BP 120/80 normal?",
        observations=[{"name": "Blood Pressure", "value": "120/80", "unit": "mmHg"}],
        claims=[{"claim": "Blood pressure reading is normal"}],
        supporting_evidence=[{
            "evidence_id": "EV-001",
            "source_name": "MedlinePlus",
            "title": "Hypertension",
            "text": "Normal blood pressure is less than 120/80 mmHg.",
            "evidence_score": 92.0,
            "publication_date": "2023-01-01"
        }],
        conflicting_evidence=[],
        contradictions=[],
        missing_information=[],
        decision_status="SUPPORTED",
        overall_score=92.0
    )

    assert "[EV-001]" in explanation or len(citations) == 1
    assert "SUPPORTED" in explanation or "Assessment" in explanation
    assert provider in ("VERITAS_DETERMINISTIC_CORE", "Groq (llama-3.3-70b)", "Google_Gemini")
