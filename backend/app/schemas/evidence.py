from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field

class Observation(BaseModel):
    id: str = Field(default="", description="Unique observation ID e.g. OBS-001")
    type: str = Field(..., description="Type of observation e.g. blood_pressure, glucose, lab_value, medication, symptom")
    name: str = Field(..., description="Human-readable parameter name")
    value: Union[str, float, int, Dict[str, Any]] = Field(..., description="Observed quantitative or qualitative value")
    unit: Optional[str] = Field(default=None, description="Measurement unit e.g. mmHg, mg/dL")
    reference_range: Optional[str] = Field(default=None, description="Standard lab reference range if stated in doc")
    source: str = Field(..., description="Source document name")
    page: int = Field(default=1, description="Page number of observation")
    section: Optional[str] = Field(default="Findings", description="Document section header")
    confidence: float = Field(default=1.0, description="Extraction confidence score 0.0 - 1.0")

class Claim(BaseModel):
    id: str = Field(default="", description="Unique claim identifier e.g. CLM-001")
    claim: str = Field(..., description="Extracted claim text or statement to audit")
    claim_type: str = Field(default="interpretation", description="'fact' | 'interpretation' | 'diagnosis'")
    support_required: bool = Field(default=True, description="Whether claim requires external clinical verification")
    related_observations: List[str] = Field(default_factory=list, description="IDs of linked observations")
    normalized_concept: Optional[str] = Field(default=None, description="Canonical clinical concept")

class EvidenceItem(BaseModel):
    evidence_id: str = Field(..., description="Standard citation identifier e.g. EV-001")
    source_name: str = Field(..., description="Publisher/Source name e.g. MedlinePlus, WHO, PubMed, FDA, ICMR, CDC")
    source_type: str = Field(..., description="e.g. official_reference, peer_reviewed, regulatory_guideline, institutional")
    authority_tier: int = Field(..., description="Tier 1 (Gov/Global Org), Tier 2 (PubMed/Peer-Reviewed), Tier 3 (Academic), Tier 4 (Web), Tier 5 (Unverifiable)")
    title: str = Field(..., description="Title or topic title")
    url: Optional[str] = Field(default="", description="URL or URI provenance link")
    publication_date: Optional[str] = Field(default="", description="Publication or guideline update date")
    retrieved_at: str = Field(..., description="ISO timestamp of retrieval")
    text: str = Field(..., description="Extracted excerpt or guideline sentence")
    relevance_score: float = Field(default=0.0, description="Calculated relevance (0.0 - 1.0)")
    authority_score: float = Field(default=0.0, description="Calculated authority (0.0 - 1.0)")
    recency_score: float = Field(default=0.0, description="Calculated recency (0.0 - 1.0)")
    methodology_score: float = Field(default=0.0, description="Calculated methodological rigor (0.0 - 1.0)")
    traceability_score: float = Field(default=1.0, description="Calculated traceability / provenance (0.0 - 1.0)")
    evidence_score: float = Field(default=0.0, description="VERITAS Evidence Quality Score (0 - 100)")
    relationship: str = Field(default="SUPPORTING", description="'SUPPORTING' | 'CONFLICTING' | 'QUESTIONABLE' | 'IRRELEVANT'")
    supports_claim: bool = Field(default=True)
    conflicts_with: List[str] = Field(default_factory=list, description="List of evidence IDs this item conflicts with")
    quality_label: str = Field(default="HIGH", description="'HIGH' | 'MODERATE' | 'LOW' | 'QUESTIONABLE'")
    reasoning: Optional[str] = Field(default="", description="Explanation of how this evidence applies to the claim")

class SourceScoreBreakdown(BaseModel):
    authority_pct: float = 0.0
    relevance_pct: float = 0.0
    recency_pct: float = 0.0
    methodology_pct: float = 0.0
    traceability_pct: float = 0.0
    composite_veritas_score: float = 0.0
    quality_tier: str = "HIGH"

class Contradiction(BaseModel):
    id: str = Field(default="", description="Contradiction ID e.g. CON-001")
    source_a_id: str = Field(..., description="Evidence ID of Source A")
    source_a_name: str
    source_a_claim: str
    source_b_id: str = Field(..., description="Evidence ID of Source B")
    source_b_name: str
    source_b_claim: str
    difference_reason: str = Field(..., description="Explanation of why sources differ e.g. population, guideline version, clinical criteria")
    severity: str = Field(default="SIGNIFICANT", description="'CRITICAL' | 'SIGNIFICANT' | 'MINOR'")

class MissingInfoItem(BaseModel):
    id: str = Field(default="", description="Missing item ID")
    item: str = Field(..., description="The clinical parameter or context missing")
    category: str = Field(..., description="'CRITICAL' | 'IMPORTANT' | 'OPTIONAL'")
    clinical_reason: str = Field(..., description="Why this missing information is required before a valid conclusion can be made")

class EvidenceGraphNode(BaseModel):
    id: str
    label: str
    type: str  # 'claim', 'observation', 'source', 'evidence'
    status: Optional[str] = None
    score: Optional[float] = None

class EvidenceGraphLink(BaseModel):
    source: str
    target: str
    relation: str  # 'SUPPORTS', 'CONTRADICTS', 'DERIVED_FROM', 'CONTEXTUALIZES', 'QUESTIONS'

class AuditRecord(BaseModel):
    request_id: str
    document_id: str
    document_name: str
    query: str
    sources_queried: List[str]
    sources_failed: List[str] = []
    sources_retrieved_count: int
    llm_provider_used: str
    fallback_used: bool = False
    decision_status: str
    human_review_required: bool
    overall_score: float
    execution_time_ms: float
    timestamp: str

class DecisionResponse(BaseModel):
    request_id: str
    document_id: str
    document_name: str
    user_query: str
    decision_status: str  # SUPPORTED, CONFLICTING, ADDITIONAL_INFORMATION_REQUIRED, QUESTIONABLE, NO_RELIABLE_CONCLUSION
    human_review_required: bool
    evidence_quality_score: float
    score_breakdown: SourceScoreBreakdown
    observations: List[Observation]
    claims: List[Claim]
    supporting_evidence: List[EvidenceItem]
    conflicting_evidence: List[EvidenceItem]
    contradictions: List[Contradiction]
    questionable_evidence: List[EvidenceItem]
    missing_information: List[MissingInfoItem]
    final_explanation: str
    citations: List[Dict[str, Any]]
    graph_nodes: List[EvidenceGraphNode] = []
    graph_links: List[EvidenceGraphLink] = []
    audit_record: AuditRecord
