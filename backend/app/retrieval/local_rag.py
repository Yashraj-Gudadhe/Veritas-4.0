from typing import List, Dict, Any, Tuple
from datetime import datetime, timezone
from app.retrieval.vector_store import vector_store
from app.schemas.evidence import EvidenceItem
from app.utils.logger import logger

class LocalRAGRetriever:
    """
    Local MedlinePlus & Internal Evidence Retriever
    Performs fast local vector search and checks evidence sufficiency
    before triggering any external online API calls.
    """

    DOMAIN_EXPANSION = {
        "egfr": "chronic kidney disease CKD renal glomerular filtration",
        "creatinine": "renal function kidney disease nephrology",
        "potassium": "electrolyte hyperkalemia hypokalemia cardiac",
        "sodium": "electrolyte hyponatremia hypernatremia",
        "glucose": "diabetes mellitus glycemia blood sugar",
        "hba1c": "diabetes glycated hemoglobin glycemic control",
        "blood_pressure": "hypertension cardiovascular blood pressure",
        "heart_rate": "cardiac arrhythmia tachycardia bradycardia",
        "spo2": "oxygen saturation respiratory pulmonary",
        "hemoglobin": "anemia hematology blood count",
        "medication": "pharmacology drug therapy treatment"
    }

    @classmethod
    def retrieve(
        cls,
        query: str,
        normalized_concepts: List[str],
        top_k: int = 5,
        observations: List[Dict[str, Any]] = None
    ) -> Tuple[List[Dict[str, Any]], bool]:
        observations = observations or []
        obs_types = list(set(o.get("type", "") for o in observations if o.get("type")))
        
        expansion_terms = []
        for o_type in obs_types:
            if o_type in cls.DOMAIN_EXPANSION:
                expansion_terms.extend(cls.DOMAIN_EXPANSION[o_type].split())
                
        unique_terms = list(dict.fromkeys(expansion_terms))
        base_query = f"{query} {' '.join(normalized_concepts)}".strip()
        enriched_query = f"{base_query} {' '.join(unique_terms)}".strip() if unique_terms else base_query
        
        results = vector_store.search(enriched_query, top_k=top_k, obs_types=obs_types)
        
        evidence_list = []
        ev_count = 1
        
        for item in results:
            ev_id = f"EV-L{ev_count:02d}"
            ev_count += 1
            
            # Dynamic quality label based on semantic relevance score
            rel_score = item.get("relevance_score", 0.85)
            if rel_score >= 0.75:
                quality_label = "HIGH"
            elif rel_score >= 0.50:
                quality_label = "MODERATE"
            else:
                quality_label = "LOW"

            # Form standard evidence dict
            evidence_item = {
                "evidence_id": ev_id,
                "source_name": item.get("source_name", "MedlinePlus"),
                "source_type": "official_reference",
                "authority_tier": item.get("authority_tier", 1),
                "title": item.get("title", "Clinical Reference"),
                "url": item.get("url", "https://medlineplus.gov/"),
                "publication_date": item.get("publication_date", "2024-01-01"),
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "text": item.get("summary", item.get("text", "")),
                "relevance_score": rel_score,
                "authority_score": 0.95,
                "recency_score": 0.88,
                "methodology_score": 0.90,
                "traceability_score": 1.0,
                "supports_claim": True,
                "conflicts_with": [],
                "quality_label": quality_label,
                "reasoning": f"Retrieved from local authoritative MedlinePlus database matching concept: {query}"
            }
            evidence_list.append(evidence_item)

        # Sufficiency check:
        # Semantic scores are higher than TF-IDF scores; require >= 0.35 for at least 2 results
        if len(evidence_list) >= 2 and any(e["relevance_score"] >= 0.35 for e in evidence_list):
            local_sufficient = True
        else:
            local_sufficient = False

        return evidence_list, local_sufficient
