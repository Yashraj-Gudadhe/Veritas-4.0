from typing import List, Set
from app.schemas.evidence import Observation, Claim
from app.sources.ncbi import NCBIAdapter
from app.sources.clinicaltrials import ClinicalTrialsAdapter
from app.sources.nlm_fhir import NLMFHIRAdapter

class SourceRouter:
    """
    Lightweight intent and domain router.
    Prevents indiscriminate network calls by directing queries ONLY to the authoritative
    sources whose domain covers the specific clinical observations and questions.
    Note: PubMed has been removed. All evidence now comes from curated offline
    adapters (WHO, ICMR, CDC, FDA) and the local MedlinePlus RAG index.
    """

    @classmethod
    def route_sources(
        cls,
        observations: List[Observation],
        claims: List[Claim],
        normalized_concepts: List[str],
        user_query: str = ""
    ) -> List[str]:
        target_sources: Set[str] = set()
        
        # All queries can check local MedlinePlus first
        target_sources.add("medlineplus")

        combined_text = f"{user_query} {' '.join(normalized_concepts)}".lower()

        # 1. Medications / Drugs / Adverse Events / Recalls -> openFDA + WHO
        if any(c in combined_text for c in ["medication", "drug", "dosage", "side_effect", "adverse", "lisinopril", "metformin", "amlodipine", "aspirin", "interaction", "contraindication", "hypertension_medication", "diabetes_medication"]):
            target_sources.add("fda")
            target_sources.add("who")

        # 2. Blood Pressure / Global Health Guidelines / Cardiovascular -> WHO
        if any(c in combined_text for c in ["blood_pressure", "bp", "hypertension", "hypotension", "heart_rate", "cardiovascular", "who", "guideline"]):
            target_sources.add("who")

        # 3. India-specific guidance / ICMR keywords -> ICMR + WHO
        if any(c in combined_text for c in ["india", "icmr", "indian", "tropical", "dengue", "malaria", "ayush", "south asian"]):
            target_sources.add("icmr")
            target_sources.add("who")

        # 4. Epidemiology / Surveillance / Infectious Disease -> CDC + WHO
        if any(c in combined_text for c in ["epidemiology", "prevalence", "outbreak", "infectious", "transmission", "cdc", "cdc_guideline", "vaccine"]):
            target_sources.add("cdc")
            target_sources.add("who")

        # 5. Laboratory biomarkers / HbA1c / Creatinine / eGFR -> WHO + FDA + ICMR
        if any(c in combined_text for c in ["glucose", "glycated_hemoglobin", "hba1c", "creatinine", "hemoglobin", "egfr", "potassium", "sodium", "study", "trial", "research"]):
            target_sources.add("who")
            target_sources.add("fda")
            target_sources.add("icmr")

        # 6. Clinical trials / RCTs / randomized studies -> ClinicalTrials.gov
        if any(k in combined_text for k in ["trial", "clinical study", "randomized", "rct"]):
            target_sources.add("clinicaltrials")

        # 7. Peer-reviewed literature / PubMed / journal research -> NCBI PubMed
        if any(k in combined_text for k in ["pubmed", "journal", "literature", "paper", "research study"]):
            target_sources.add("ncbi")

        # 8. ICD-10 codes / diagnosis codes / clinical terminology -> NLM FHIR
        if any(k in combined_text for k in ["icd", "diagnosis code", "condition code", "icd-10"]):
            target_sources.add("nlm_fhir")

        # Default fallback if nothing specific matched
        if len(target_sources) <= 1:
            target_sources.add("who")
            target_sources.add("fda")

        return list(target_sources)
