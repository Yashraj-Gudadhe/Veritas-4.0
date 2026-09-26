import pytest
from app.graph.workflow import veritas_graph
from app.ingestion.xml_parser import MedlinePlusXMLParser
from app.retrieval.vector_store import vector_store
from app.config import settings

@pytest.fixture(autouse=True)
def setup_index():
    xml_path = settings.BASE_DIR / settings.MEDLINEPLUS_XML_PATH
    if xml_path.exists() and not vector_store.chunks:
        topics = MedlinePlusXMLParser.parse_xml_file(xml_path)
        vector_store.index_documents([t.to_dict() for t in topics])

@pytest.mark.asyncio
async def test_demo_1_supported_case():
    state = {
        "raw_text": "PATIENT CLINICAL VITAL SIGNS\nBlood Pressure: 118/76 mmHg\nHeart Rate: 72 bpm",
        "user_query": "Is this blood pressure normal?",
        "document_name": "normal_bp.pdf"
    }
    result = await veritas_graph.ainvoke(state)
    assert len(result["observations"]) >= 1
    assert result["overall_evidence_score"] >= 65.0
    assert result["decision_status"] in ("SUPPORTED", "ADDITIONAL_INFORMATION_REQUIRED")

@pytest.mark.asyncio
async def test_demo_2_conflicting_case():
    state = {
        "raw_text": "CARDIOVASCULAR HEALTH CHECK\nBlood Pressure: 134/84 mmHg",
        "user_query": "Does 134/84 mmHg confirm hypertension across all guidelines?",
        "document_name": "borderline_bp.pdf",
        "conflicting_evidence": [{
            "evidence_id": "EV-ACC-001",
            "source_name": "ACC/AHA",
            "title": "Hypertension Guideline",
            "text": "130/80 is Stage 1 Hypertension.",
            "publication_date": "2017-01-01",
            "relationship": "CONFLICTING",
            "supports_claim": False,
            "difference_reason": "ACC/AHA lowered threshold to 130/80 whereas ESC maintains 140/90."
        }]
    }
    result = await veritas_graph.ainvoke(state)
    assert result["decision_status"] == "CONFLICTING"
    assert result["human_review_required"] is True

@pytest.mark.asyncio
async def test_demo_3_incomplete_case():
    state = {
        "raw_text": "OUTPATIENT TRIAGE NOTE\nBlood Pressure: 85/55 mmHg",
        "user_query": "Does this single reading prove pathological hypotension?",
        "document_name": "isolated_bp.pdf"
    }
    result = await veritas_graph.ainvoke(state)
    # Blood pressure < 90/60 generates critical requirement for repeat seated measurement
    assert len(result["missing_information"]) >= 1
    assert result["decision_status"] == "ADDITIONAL_INFORMATION_REQUIRED"
    assert result["human_review_required"] is True

@pytest.mark.asyncio
async def test_demo_4_questionable_case():
    state = {
        "raw_text": "NEWSLETTER: Celery juice cures hypertension in 48 hours.",
        "user_query": "Is this celery juice therapy verified?",
        "document_name": "blog_post.pdf",
        "questionable_evidence": [{
            "evidence_id": "EV-BLOG-001",
            "source_name": "Unverified Blog",
            "title": "Celery Therapy",
            "text": "Cures blood pressure without medicine.",
            "authority_tier": 5,
            "evidence_score": 25.0,
            "quality_label": "QUESTIONABLE",
            "relationship": "QUESTIONABLE"
        }]
    }
    result = await veritas_graph.ainvoke(state)
    assert result["decision_status"] in ("QUESTIONABLE", "NO_RELIABLE_CONCLUSION", "ADDITIONAL_INFORMATION_REQUIRED")
    assert result["human_review_required"] is True

@pytest.mark.asyncio
async def test_demo_5_no_reliable_conclusion_case():
    state = {
        "raw_text": "Fragmented sample data without values.",
        "user_query": "What diagnosis is confirmed?",
        "document_name": "fragment.pdf"
    }
    result = await veritas_graph.ainvoke(state)
    assert result["human_review_required"] is True
