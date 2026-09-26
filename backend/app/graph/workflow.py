import time
from typing import Dict, Any, List
from datetime import datetime, timezone
from langgraph.graph import StateGraph, START, END

from app.schemas.state import DecisionState
from app.ingestion.pdf_parser import PDFParser
from app.ingestion.claim_extractor import ClaimExtractor
from app.normalization.medical_norm import MedicalNormalizer
from app.evidence.requirement_engine import EvidenceRequirementEngine
from app.retrieval.local_rag import LocalRAGRetriever
from app.sources.router import SourceRouter
from app.sources.who import WHOAdapter
from app.sources.fda import FDAAdapter
from app.sources.icmr import ICMRAdapter
from app.sources.cdc import CDCAdapter
from app.sources.medlineplus import MedlinePlusOnlineAdapter
from app.sources.ncbi import NCBIAdapter
from app.sources.clinicaltrials import ClinicalTrialsAdapter
from app.sources.nlm_fhir import NLMFHIRAdapter
from app.scoring.evaluator import VeritasScorer
from app.evidence.matcher import EvidenceMatcher
from app.evidence.conflict_detector import ConflictDetector
from app.evidence.missing_detector import MissingEvidenceDetector
from app.evidence.decision_gate import VeritasDecisionGate
from app.llm.orchestrator import LLMOrchestrator
from app.utils.logger import logger

# --- Node Implementations ---

async def node_ingest_document(state: DecisionState) -> Dict[str, Any]:
    start_time = time.time()
    file_path = state.get("file_path")
    raw_text = state.get("raw_text", "")
    doc_id = state.get("document_id", f"DOC-{int(start_time) % 1000000:06d}")
    doc_name = state.get("document_name", "medical_report.pdf")

    if file_path:
        try:
            pdf_result = PDFParser.parse_pdf(file_path, document_id=doc_id)
            raw_text = pdf_result.full_text
            doc_id = pdf_result.document_id
            doc_name = pdf_result.filename
        except Exception as e:
            logger.error(f"PDF parsing error: {str(e)}")

    return {
        "document_id": doc_id,
        "document_name": doc_name,
        "raw_text": raw_text,
        "start_time": start_time,
        "audit_log": [f"Document ingested: {doc_name} (Length: {len(raw_text)} chars)"]
    }

async def node_extract_claims(state: DecisionState) -> Dict[str, Any]:
    raw_text = state.get("raw_text", "")
    user_query = state.get("user_query", "")
    doc_name = state.get("document_name", "document.pdf")

    observations, claims = ClaimExtractor.extract_observations_and_claims(
        text=raw_text,
        source_name=doc_name,
        user_query=user_query
    )

    obs_dicts = [o.model_dump() for o in observations]
    claim_dicts = [c.model_dump() for c in claims]

    return {
        "observations": obs_dicts,
        "claims": claim_dicts,
        "audit_log": state.get("audit_log", []) + [f"Extracted {len(observations)} observations and {len(claims)} claims."]
    }

async def node_normalize_concepts(state: DecisionState) -> Dict[str, Any]:
    claims = state.get("claims", [])
    user_query = state.get("user_query", "")
    
    all_text = f"{user_query} " + " ".join([c.get("claim", "") for c in claims])
    concepts = MedicalNormalizer.extract_canonical_concepts(all_text)

    # Normalize observation units
    for obs in state.get("observations", []):
        if obs.get("unit"):
            obs["unit"] = MedicalNormalizer.normalize_unit(obs["unit"])

    return {
        "normalized_concepts": concepts,
        "audit_log": state.get("audit_log", []) + [f"Normalized {len(concepts)} clinical concepts: {concepts}"]
    }

async def node_generate_requirements(state: DecisionState) -> Dict[str, Any]:
    obs = [ClaimExtractor.Observation(**o) if hasattr(ClaimExtractor, 'Observation') else o for o in state.get("observations", [])]
    from app.schemas.evidence import Observation, Claim
    obs_objs = [Observation(**o) for o in state.get("observations", [])]
    claim_objs = [Claim(**c) for c in state.get("claims", [])]

    reqs = EvidenceRequirementEngine.generate_requirements(
        observations=obs_objs,
        claims=claim_objs,
        user_query=state.get("user_query", "")
    )

    return {
        "evidence_requirements": reqs,
        "audit_log": state.get("audit_log", []) + [f"Generated {len(reqs)} clinical evidence requirements."]
    }

async def node_retrieve_local(state: DecisionState) -> Dict[str, Any]:
    query = state.get("user_query", "") or (state.get("claims", [{}])[0].get("claim", "") if state.get("claims") else "")
    concepts = state.get("normalized_concepts", [])

    local_evidence, sufficient = LocalRAGRetriever.retrieve(
        query=query,
        normalized_concepts=concepts,
        top_k=15,
        observations=state.get("observations", [])
    )

    return {
        "local_evidence": local_evidence,
        "local_sufficient": sufficient,
        "audit_log": state.get("audit_log", []) + [f"Local RAG retrieved {len(local_evidence)} items (Sufficient: {sufficient})."]
    }

async def node_conditional_online(state: DecisionState) -> Dict[str, Any]:
    local_sufficient = state.get("local_sufficient", False)
    sources_queried = ["medlineplus_local"]
    sources_failed = []
    online_evidence = []

    # If local is not fully sufficient or specific sources are needed, route
    from app.schemas.evidence import Observation, Claim
    obs_objs = [Observation(**o) for o in state.get("observations", [])]
    claim_objs = [Claim(**c) for c in state.get("claims", [])]
    concepts = state.get("normalized_concepts", [])
    user_query = state.get("user_query", "")

    target_sources = SourceRouter.route_sources(
        observations=obs_objs,
        claims=claim_objs,
        normalized_concepts=concepts,
        user_query=user_query
    )

    query = user_query or (concepts[0] if concepts else "clinical guidance")

    # If no concepts or observations and no medical terms detected, do not fetch unrelated guidelines
    if not concepts and not state.get("observations"):
        pre_seeded = state.get("conflicting_evidence", []) + state.get("questionable_evidence", [])
        return {
            "sources_to_query": [],
            "sources_queried": ["medlineplus_local"],
            "sources_failed": [],
            "online_evidence": [],
            "merged_evidence": pre_seeded,
            "audit_log": state.get("audit_log", []) + ["No canonical clinical concepts detected for online retrieval."]
        }

    # If already seeded with explicit questionable evidence (e.g. Demo 4 blog fixture), do not override with standard guidelines
    if state.get("questionable_evidence") and not state.get("observations"):
        pre_seeded = state.get("questionable_evidence", [])
        return {
            "sources_to_query": [],
            "sources_queried": ["synthetic_fixture"],
            "sources_failed": [],
            "online_evidence": [],
            "merged_evidence": pre_seeded,
            "audit_log": state.get("audit_log", []) + ["Unverified claim evaluated against unverified source fixture."]
        }

    for src in target_sources:
        try:
            if src == "who":
                sources_queried.append("who")
                who_ev = await WHOAdapter.fetch(query, concepts)
                online_evidence.extend(who_ev)
            elif src == "fda":
                sources_queried.append("fda")
                # Extract the first medication observation's drug name as the FDA search term.
                # This ensures the FDA evidence returned is specific to the patient's actual medication.
                med_obs = [
                    o for o in state.get("observations", [])
                    if o.get("type") == "medication"
                ]
                if med_obs:
                    first_med = med_obs[0]
                    med_value = first_med.get("value", {})
                    target_drug = (
                        med_value.get("drug", "").lower()
                        if isinstance(med_value, dict)
                        else str(med_value).lower()
                    ) or None
                else:
                    target_drug = None

                if target_drug:
                    fda_ev = await FDAAdapter.fetch(target_drug)
                    online_evidence.extend(fda_ev)
                else:
                    logger.info("No medication observation found — skipping FDA lookup.")
            elif src == "icmr":
                sources_queried.append("icmr")
                icmr_ev = await ICMRAdapter.fetch(query, concepts)
                online_evidence.extend(icmr_ev)
            elif src == "cdc":
                sources_queried.append("cdc")
                cdc_ev = await CDCAdapter.fetch(query, concepts)
                online_evidence.extend(cdc_ev)
            elif src == "medlineplus":
                sources_queried.append("medlineplus_online")
                mp_ev = await MedlinePlusOnlineAdapter.fetch(query)
                online_evidence.extend(mp_ev)
            elif src == "ncbi":
                sources_queried.append("ncbi")
                adapter_results = await NCBIAdapter().fetch(state["user_query"])
                online_evidence.extend(adapter_results)
            elif src == "clinicaltrials":
                sources_queried.append("clinicaltrials")
                adapter_results = await ClinicalTrialsAdapter().fetch(state["user_query"])
                online_evidence.extend(adapter_results)
            elif src == "nlm_fhir":
                sources_queried.append("nlm_fhir")
                adapter_results = await NLMFHIRAdapter().fetch(state["user_query"])
                online_evidence.extend(adapter_results)
        except Exception as e:
            sources_failed.append(src)
            logger.warning(f"Source adapter failed for {src}: {str(e)}")

    pre_seeded = state.get("conflicting_evidence", []) + state.get("questionable_evidence", [])
    merged = state.get("local_evidence", []) + online_evidence + pre_seeded
    return {
        "sources_to_query": target_sources,
        "sources_queried": sources_queried,
        "sources_failed": sources_failed,
        "online_evidence": online_evidence,
        "merged_evidence": merged,
        "audit_log": state.get("audit_log", []) + [f"Merged total of {len(merged)} candidate evidence items from sources: {sources_queried}"]
    }

async def node_score_and_match(state: DecisionState) -> Dict[str, Any]:
    from app.schemas.evidence import Claim
    claim_objs = [Claim(**c) for c in state.get("claims", [])]
    merged_ev = state.get("merged_evidence", [])

    supporting, conflicting, questionable = EvidenceMatcher.match_and_classify(
        claims=claim_objs,
        evidence_items=merged_ev
    )

    all_scored = supporting + conflicting + questionable
    breakdown = VeritasScorer.calculate_overall_breakdown(all_scored)

    return {
        "supporting_evidence": supporting,
        "conflicting_evidence": conflicting,
        "questionable_evidence": questionable,
        "overall_evidence_score": breakdown.composite_veritas_score,
        "score_breakdown": breakdown.model_dump(),
        "audit_log": state.get("audit_log", []) + [f"Scored {len(all_scored)} items. Overall VERITAS Score: {breakdown.composite_veritas_score}/100"]
    }

async def node_detect_conflicts_and_missing(state: DecisionState) -> Dict[str, Any]:
    from app.schemas.evidence import Observation
    obs_objs = [Observation(**o) for o in state.get("observations", [])]
    requirements = state.get("evidence_requirements", [])
    supporting = state.get("supporting_evidence", [])
    conflicting = state.get("conflicting_evidence", [])

    contradictions = ConflictDetector.detect_conflicts(
        evidence_items=supporting,
        conflicting_items=conflicting
    )

    missing = MissingEvidenceDetector.detect_missing(
        observations=obs_objs,
        requirements=requirements
    )

    return {
        "contradictions": contradictions,
        "missing_information": missing,
        "audit_log": state.get("audit_log", []) + [f"Detected {len(contradictions)} contradictions and {len(missing)} missing clinical context items."]
    }

async def node_decision_gate(state: DecisionState) -> Dict[str, Any]:
    status, human_req, rationale = VeritasDecisionGate.evaluate(
        supporting_evidence=state.get("supporting_evidence", []),
        conflicting_evidence=state.get("conflicting_evidence", []),
        contradictions=state.get("contradictions", []),
        questionable_evidence=state.get("questionable_evidence", []),
        missing_information=state.get("missing_information", []),
        overall_score=state.get("overall_evidence_score", 0.0),
        observations=state.get("observations", []),
    )

    return {
        "decision_status": status,
        "human_review_required": human_req,
        "decision_rationale": rationale,
        "audit_log": state.get("audit_log", []) + [f"VERITAS DECISION GATE: Status = {status}, HumanReviewRequired = {human_req}"]
    }

async def node_generate_explanation(state: DecisionState) -> Dict[str, Any]:
    explanation, citations, provider, fallback = await LLMOrchestrator.synthesize_audit_report(
        user_query=state.get("user_query", ""),
        observations=state.get("observations", []),
        claims=state.get("claims", []),
        supporting_evidence=state.get("supporting_evidence", []),
        conflicting_evidence=state.get("conflicting_evidence", []),
        contradictions=state.get("contradictions", []),
        missing_information=state.get("missing_information", []),
        decision_status=state.get("decision_status", "SUPPORTED"),
        overall_score=state.get("overall_evidence_score", 0.0),
        decision_rationale=state.get("decision_rationale", "")
    )

    exec_time = round((time.time() - state.get("start_time", time.time())) * 1000, 1)

    audit_rec = {
        "request_id": state.get("request_id", f"REQ-{int(time.time()):06d}"),
        "document_id": state.get("document_id", "DOC-001"),
        "document_name": state.get("document_name", "document.pdf"),
        "query": state.get("user_query", ""),
        "sources_queried": state.get("sources_queried", []),
        "sources_failed": state.get("sources_failed", []),
        "sources_retrieved_count": len(state.get("merged_evidence", [])),
        "llm_provider_used": provider,
        "fallback_used": fallback,
        "decision_status": state.get("decision_status", "SUPPORTED"),
        "human_review_required": state.get("human_review_required", False),
        "overall_score": state.get("overall_evidence_score", 0.0),
        "execution_time_ms": exec_time,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    return {
        "final_explanation": explanation,
        "citations": citations,
        "llm_provider_used": provider,
        "fallback_used": fallback,
        "audit_record": audit_rec,
        "audit_log": state.get("audit_log", []) + [f"Completed in {exec_time}ms using {provider}."]
    }

# --- Graph Assembly ---

def build_veritas_graph():
    builder = StateGraph(DecisionState)

    builder.add_node("ingest_document", node_ingest_document)
    builder.add_node("extract_claims", node_extract_claims)
    builder.add_node("normalize_concepts", node_normalize_concepts)
    builder.add_node("generate_requirements", node_generate_requirements)
    builder.add_node("retrieve_local", node_retrieve_local)
    builder.add_node("conditional_online", node_conditional_online)
    builder.add_node("score_and_match", node_score_and_match)
    builder.add_node("detect_conflicts_and_missing", node_detect_conflicts_and_missing)
    builder.add_node("decision_gate", node_decision_gate)
    builder.add_node("generate_explanation", node_generate_explanation)

    # Wire Edges
    builder.add_edge(START, "ingest_document")
    builder.add_edge("ingest_document", "extract_claims")
    builder.add_edge("extract_claims", "normalize_concepts")
    builder.add_edge("normalize_concepts", "generate_requirements")
    builder.add_edge("generate_requirements", "retrieve_local")
    builder.add_edge("retrieve_local", "conditional_online")
    builder.add_edge("conditional_online", "score_and_match")
    builder.add_edge("score_and_match", "detect_conflicts_and_missing")
    builder.add_edge("detect_conflicts_and_missing", "decision_gate")
    builder.add_edge("decision_gate", "generate_explanation")
    builder.add_edge("generate_explanation", END)

    return builder.compile()

veritas_graph = build_veritas_graph()
