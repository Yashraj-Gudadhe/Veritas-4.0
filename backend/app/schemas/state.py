from typing import List, Dict, Any, Optional
from typing_extensions import TypedDict
from app.schemas.evidence import (
    Observation, Claim, EvidenceItem, Contradiction, MissingInfoItem, SourceScoreBreakdown, AuditRecord
)

class DecisionState(TypedDict, total=False):
    request_id: str
    document_id: str
    document_name: str
    file_path: Optional[str]
    raw_text: str
    user_query: str
    
    # Ingestion & Normalization
    observations: List[Dict[str, Any]]
    claims: List[Dict[str, Any]]
    normalized_concepts: List[str]
    evidence_requirements: List[str]
    
    # Retrieval
    local_evidence: List[Dict[str, Any]]
    local_sufficient: bool
    sources_to_query: List[str]
    online_evidence: List[Dict[str, Any]]
    merged_evidence: List[Dict[str, Any]]
    
    # Scoring & Relationship Matching
    scored_evidence: List[Dict[str, Any]]
    supporting_evidence: List[Dict[str, Any]]
    conflicting_evidence: List[Dict[str, Any]]
    questionable_evidence: List[Dict[str, Any]]
    contradictions: List[Dict[str, Any]]
    missing_information: List[Dict[str, Any]]
    overall_evidence_score: float
    score_breakdown: Dict[str, Any]
    
    # Decision Gate
    decision_status: str
    human_review_required: bool
    decision_rationale: str
    
    # LLM Reasoning & Citations
    final_explanation: str
    citations: List[Dict[str, Any]]
    llm_provider_used: str
    fallback_used: bool
    
    # Audit & Observability
    audit_log: List[str]
    sources_queried: List[str]
    sources_failed: List[str]
    start_time: float
    audit_record: Dict[str, Any]
