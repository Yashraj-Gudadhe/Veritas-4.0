import os
import json
import uuid
from pathlib import Path
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel

# New: database + auth + routers (do NOT import RAG modules here — they are imported below as before)
from app.database import engine, Base
from app.models import User, Conversation, Message  # noqa: F401 — needed for table creation
from app.routers import auth as auth_router
from app.routers import account as account_router
from app.routers import chats as chats_router

from app.config import settings
from app.utils.logger import logger
from app.graph.workflow import veritas_graph
from app.ingestion.pdf_parser import PDFParser
from app.ingestion.xml_parser import MedlinePlusXMLParser
from app.retrieval.vector_store import vector_store
from app.schemas.evidence import (
    DecisionResponse, SourceScoreBreakdown, Observation, Claim,
    EvidenceItem, Contradiction, MissingInfoItem, AuditRecord,
    EvidenceGraphNode, EvidenceGraphLink
)

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing VERITAS...")
    # Create new DB tables (User, Conversation, Message) — does not affect existing data
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables verified/created.")
    # Index default MedlinePlus XML if vector index is empty
    if not vector_store.chunks:
        xml_path = Path(settings.MEDLINEPLUS_XML_PATH)
        if not xml_path.is_absolute():
            xml_path = settings.BASE_DIR / xml_path
        if xml_path.exists():
            topics = MedlinePlusXMLParser.parse_xml_file(xml_path)
            if topics:
                count = vector_store.index_documents([t.to_dict() for t in topics])
                logger.info(f"Auto-indexed {count} MedlinePlus topics on startup.")
    yield

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Evidence-Aware Decision Intelligence System",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register new API routers (auth, account, chats) — existing endpoints untouched below
app.include_router(auth_router.router)
app.include_router(account_router.router)
app.include_router(chats_router.router)

FRONTEND_DIR = settings.BASE_DIR / "frontend"
UPLOAD_TEMP_DIR = settings.DATA_DIR / "uploads"
UPLOAD_TEMP_DIR.mkdir(parents=True, exist_ok=True)

class AnalyzeRequest(BaseModel):
    user_query: str
    document_text: Optional[str] = ""
    document_id: Optional[str] = None
    document_name: Optional[str] = "document.pdf"
    demo_id: Optional[str] = None

from dotenv import dotenv_values

@app.get("/api/health")
async def health_check():
    env_vals = dotenv_values(settings.BASE_DIR / ".env")
    xai_configured = bool(env_vals.get("XAI_API_KEY") or os.getenv("XAI_API_KEY", "").strip())
    gemini_configured = bool(env_vals.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY", "").strip())
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "indexed_chunks": len(vector_store.chunks),
        "primary_llm": getattr(settings, 'GROK_MODEL', getattr(settings, 'GROQ_MODEL', 'Deterministic Core')) if xai_configured else "Deterministic Core",
        "fallback_llm": settings.GEMINI_MODEL if gemini_configured else "Deterministic Core"
    }

@app.post("/api/index/medlineplus")
async def index_medlineplus(xml_path: Optional[str] = None):
    target_path = Path(xml_path) if xml_path else Path(settings.MEDLINEPLUS_XML_PATH)
    if not target_path.is_absolute():
        target_path = settings.BASE_DIR / target_path
        
    if not target_path.exists():
        raise HTTPException(status_code=404, detail=f"MedlinePlus XML file not found at: {target_path}")

    topics = MedlinePlusXMLParser.parse_xml_file(target_path)
    if not topics:
        raise HTTPException(status_code=400, detail="No topic records could be parsed from XML file.")

    indexed_count = vector_store.index_documents([t.to_dict() for t in topics])
    return {
        "status": "success",
        "file": str(target_path),
        "topics_parsed": len(topics),
        "chunks_indexed": indexed_count
    }

@app.get("/api/fixtures")
async def get_fixtures():
    fixtures_file = settings.FIXTURES_DIR / "demo_cases.json"
    if fixtures_file.exists():
        with open(fixtures_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

@app.post("/api/upload")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF documents (.pdf) are supported.")

    file_id = f"DOC-{uuid.uuid4().hex[:8]}"
    save_path = UPLOAD_TEMP_DIR / f"{file_id}_{file.filename}"
    
    try:
        content = await file.read()
        with open(save_path, "wb") as f:
            f.write(content)

        # Parse with PyMuPDF
        result = PDFParser.parse_pdf(save_path, document_id=file_id)
        
        # Privacy: unlink temporary file after parsing
        try:
            save_path.unlink(missing_ok=True)
        except Exception:
            pass

        return {
            "document_id": result.document_id,
            "filename": file.filename,
            "total_pages": result.total_pages,
            "text": result.full_text,
            "extraction_quality": result.extraction_quality,
            "text_density_score": result.text_density_score,
            "ocr_required": result.ocr_required
        }
    except Exception as e:
        logger.error(f"Error handling upload: {str(e)}")
        raise HTTPException(status_code=500, detail=f"PDF Ingestion failed: {str(e)}")

@app.post("/api/analyze", response_model=DecisionResponse)
async def analyze_document(req: AnalyzeRequest):
    req_id = f"REQ-{uuid.uuid4().hex[:8]}"
    
    # Check if demo case was selected
    doc_text = req.document_text or ""
    query = req.user_query
    doc_name = req.document_name or "clinical_document.pdf"
    doc_id = req.document_id or f"DOC-{uuid.uuid4().hex[:6]}"

    # Setup Initial State
    initial_state = {
        "request_id": req_id,
        "document_id": doc_id,
        "document_name": doc_name,
        "raw_text": doc_text,
        "user_query": query,
        "file_path": None,
        "observations": [],
        "claims": [],
        "normalized_concepts": [],
        "evidence_requirements": [],
        "local_evidence": [],
        "online_evidence": [],
        "merged_evidence": [],
        "scored_evidence": [],
        "supporting_evidence": [],
        "conflicting_evidence": [],
        "questionable_evidence": [],
        "contradictions": [],
        "missing_information": [],
        "overall_evidence_score": 0.0,
        "score_breakdown": {},
        "decision_status": "NO_RELIABLE_CONCLUSION",
        "human_review_required": True,
        "final_explanation": "",
        "citations": [],
        "audit_log": []
    }

    # Handle special Demo 4 & Demo 2 custom fixtures directly if specified
    if req.demo_id == "demo-2":
        initial_state["conflicting_evidence"] = [{
            "evidence_id": "EV-ACC-001",
            "source_name": "ACC/AHA 2017 Hypertension Clinical Practice Guideline",
            "source_type": "official_reference",
            "authority_tier": 1,
            "title": "AHA/ACC Blood Pressure Clinical Criteria",
            "url": "https://www.ahajournals.org/doi/10.1161/HYP.0000000000000065",
            "publication_date": "2017-11-13",
            "retrieved_at": "2024-01-01T00:00:00",
            "text": "Defines Stage 1 hypertension as SBP 130-139 or DBP 80-89 mmHg. Recommends prompt lifestyle modification and pharmacotherapy in patients with elevated ASCVD risk.",
            "relevance_score": 0.95,
            "authority_score": 0.98,
            "recency_score": 0.80,
            "methodology_score": 0.95,
            "traceability_score": 1.0,
            "evidence_score": 91.0,
            "relationship": "CONFLICTING",
            "supports_claim": False,
            "difference_reason": "ACC/AHA lowered hypertension threshold to 130/80 mmHg, whereas ESC/ESH maintains 140/90 mmHg cutoff.",
            "quality_label": "HIGH"
        }]
    elif req.demo_id == "demo-4":
        initial_state["questionable_evidence"] = [{
            "evidence_id": "EV-BLOG-001",
            "source_name": "HolisticHealthBuzz (Commercial Blog)",
            "source_type": "unverified_web",
            "authority_tier": 4,
            "title": "Natural Cures for Blood Pressure",
            "url": "https://example-blog.org/celery-juice",
            "publication_date": "2019-03-01",
            "retrieved_at": "2024-01-01T00:00:00",
            "text": "Drinking celery juice eliminates need for prescription antihypertensive medications within 48 hours.",
            "relevance_score": 0.60,
            "authority_score": 0.20,
            "recency_score": 0.40,
            "methodology_score": 0.15,
            "traceability_score": 0.30,
            "evidence_score": 32.0,
            "relationship": "QUESTIONABLE",
            "supports_claim": False,
            "quality_label": "QUESTIONABLE"
        }]

    # Run LangGraph Workflow
    try:
        final_state = await veritas_graph.ainvoke(initial_state)
    except Exception as e:
        logger.error(f"LangGraph execution error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Decision pipeline failed: {str(e)}")

    # Construct Evidence Graph Nodes and Links for UI Visualization
    graph_nodes = []
    graph_links = []
    
    # Claim Node
    graph_nodes.append(EvidenceGraphNode(
        id="CLAIM-ROOT",
        label=query[:50] + ("..." if len(query) > 50 else ""),
        type="claim",
        status=final_state.get("decision_status")
    ))

    for obs in final_state.get("observations", []):
        obs_id = obs.get("id", "OBS")
        graph_nodes.append(EvidenceGraphNode(
            id=obs_id,
            label=f"{obs.get('name')}: {obs.get('value')} {obs.get('unit') or ''}",
            type="observation"
        ))
        graph_links.append(EvidenceGraphLink(
            source=obs_id,
            target="CLAIM-ROOT",
            relation="DERIVED_FROM"
        ))

    for ev in final_state.get("supporting_evidence", []):
        ev_id = ev.get("evidence_id", "EV")
        graph_nodes.append(EvidenceGraphNode(
            id=ev_id,
            label=f"{ev.get('source_name')} ({ev.get('evidence_score', 0):.0f})",
            type="evidence",
            status="SUPPORTING",
            score=ev.get("evidence_score")
        ))
        graph_links.append(EvidenceGraphLink(
            source=ev_id,
            target="CLAIM-ROOT",
            relation="SUPPORTS"
        ))

    for ev in final_state.get("conflicting_evidence", []):
        ev_id = ev.get("evidence_id", "EV")
        graph_nodes.append(EvidenceGraphNode(
            id=ev_id,
            label=f"{ev.get('source_name')} (CONFLICT)",
            type="evidence",
            status="CONFLICTING",
            score=ev.get("evidence_score")
        ))
        graph_links.append(EvidenceGraphLink(
            source=ev_id,
            target="CLAIM-ROOT",
            relation="CONTRADICTS"
        ))

    for ev in final_state.get("questionable_evidence", []):
        ev_id = ev.get("evidence_id", "EV")
        graph_nodes.append(EvidenceGraphNode(
            id=ev_id,
            label=f"{ev.get('source_name')} (QUESTIONABLE)",
            type="evidence",
            status="QUESTIONABLE",
            score=ev.get("evidence_score")
        ))
        graph_links.append(EvidenceGraphLink(
            source=ev_id,
            target="CLAIM-ROOT",
            relation="QUESTIONS"
        ))

    score_dict = final_state.get("score_breakdown", {})
    breakdown_obj = SourceScoreBreakdown(**score_dict) if score_dict else SourceScoreBreakdown()
    audit_dict = final_state.get("audit_record", {})
    audit_obj = AuditRecord(**audit_dict) if audit_dict else AuditRecord(
        request_id=req_id,
        document_id=doc_id,
        document_name=doc_name,
        query=query,
        sources_queried=[],
        sources_retrieved_count=0,
        llm_provider_used="VERITAS_CORE",
        decision_status=final_state.get("decision_status", "SUPPORTED"),
        human_review_required=final_state.get("human_review_required", False),
        overall_score=final_state.get("overall_evidence_score", 0.0),
        execution_time_ms=0.0,
        timestamp=""
    )

    response = DecisionResponse(
        request_id=req_id,
        document_id=doc_id,
        document_name=doc_name,
        user_query=query,
        decision_status=final_state.get("decision_status", "SUPPORTED"),
        human_review_required=final_state.get("human_review_required", False),
        evidence_quality_score=final_state.get("overall_evidence_score", 0.0),
        score_breakdown=breakdown_obj,
        observations=[Observation(**o) for o in final_state.get("observations", [])],
        claims=[Claim(**c) for c in final_state.get("claims", [])],
        supporting_evidence=[EvidenceItem(**e) for e in final_state.get("supporting_evidence", [])],
        conflicting_evidence=[EvidenceItem(**e) for e in final_state.get("conflicting_evidence", [])],
        contradictions=[Contradiction(**c) for c in final_state.get("contradictions", [])],
        questionable_evidence=[EvidenceItem(**e) for e in final_state.get("questionable_evidence", [])],
        missing_information=[MissingInfoItem(**m) for m in final_state.get("missing_information", [])],
        final_explanation=final_state.get("final_explanation", ""),
        citations=final_state.get("citations", []),
        graph_nodes=graph_nodes,
        graph_links=graph_links,
        audit_record=audit_obj
    )

    return response

# Serve Frontend static assets
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/")
    async def serve_index():
        return FileResponse(FRONTEND_DIR / "index.html")
