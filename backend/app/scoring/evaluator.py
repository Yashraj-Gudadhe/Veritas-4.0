from typing import Dict, Any, List
from app.config import settings
from app.schemas.evidence import SourceScoreBreakdown

class VeritasScorer:
    """
    VERITAS Evidence Quality Heuristic Evaluator
    Transparently calculates multi-dimensional evidence quality scores across 5 clinical dimensions:
    Authority (30%), Relevance (25%), Recency (15%), Methodology (15%), Traceability (15%).
    """

    AUTHORITY_TIER_SCORES = {
        1: 0.98,  # WHO, MedlinePlus/NLM, FDA, ICMR, CDC
        2: 0.90,  # PubMed Peer-reviewed, Lancet, NEJM
        3: 0.78,  # Academic medical centers, University clinics
        4: 0.45,  # General commercial web / Blogs
        5: 0.15   # Unverifiable / Unknown forum
    }

    @classmethod
    def evaluate_evidence_item(cls, item: Dict[str, Any]) -> Dict[str, Any]:
        # 1. Authority Score
        tier = item.get("authority_tier", 3)
        base_auth = cls.AUTHORITY_TIER_SCORES.get(tier, 0.50)
        auth_score = item.get("authority_score") or base_auth

        # 2. Relevance Score
        rel_score = float(item.get("relevance_score", 0.75))
        
        source_name = item.get("source_name", "").lower()
        source_type = item.get("source_type", "").lower()
        if "medlineplus" in source_name or source_type == "medlineplus":
            content_to_check = (item.get("title", "") + " " + item.get("text", "")).lower()
            boost_terms = ["kidney", "diabetes", "renal", "glucose", "hba1c", "potassium", "electrolyte", "ckd", "nephro"]
            if any(term in content_to_check for term in boost_terms):
                rel_score += 0.15
                
        rel_score = min(1.0, max(0.0, rel_score))

        # 3. Recency Score
        pub_date = str(item.get("publication_date", ""))
        rec_score = item.get("recency_score")
        if rec_score is None:
            if any(year in pub_date for year in ["2026", "2025", "2024", "2023"]):
                rec_score = 0.95
            elif any(year in pub_date for year in ["2022", "2021", "2020"]):
                rec_score = 0.85
            elif any(year in pub_date for year in ["2019", "2018", "2017"]):
                rec_score = 0.65
            else:
                rec_score = 0.45

        # 4. Methodology Score
        source_type = item.get("source_type", "general")
        meth_score = item.get("methodology_score")
        if meth_score is None:
            if "guideline" in source_type or "reference" in source_type:
                meth_score = 0.95
            elif "peer_reviewed" in source_type:
                meth_score = 0.88
            elif "regulatory" in source_type:
                meth_score = 0.92
            else:
                meth_score = 0.40

        # 5. Traceability Score
        url = item.get("url", "")
        trac_score = item.get("traceability_score")
        if trac_score is None:
            if url and ("gov" in url or "who.int" in url or "nih.gov" in url or "ncbi" in url or "fda.gov" in url or "icmr" in url):
                trac_score = 1.0
            elif url and url.startswith("http"):
                trac_score = 0.85
            else:
                trac_score = 0.25

        # Composite Formula
        raw_composite = (
            settings.WEIGHT_AUTHORITY * auth_score +
            settings.WEIGHT_RELEVANCE * rel_score +
            settings.WEIGHT_RECENCY * rec_score +
            settings.WEIGHT_METHODOLOGY * meth_score +
            settings.WEIGHT_TRACEABILITY * trac_score
        )
        composite_veritas_score = round(raw_composite * 100.0, 1)

        # Quality Label
        if composite_veritas_score >= settings.DECISION_THRESHOLD_HIGH:
            quality_label = "HIGH"
        elif composite_veritas_score >= settings.DECISION_THRESHOLD_MODERATE:
            quality_label = "MODERATE"
        elif composite_veritas_score >= settings.DECISION_THRESHOLD_LOW:
            quality_label = "LOW"
        else:
            quality_label = "QUESTIONABLE"

        # Update item
        item["authority_score"] = round(auth_score, 2)
        item["relevance_score"] = round(rel_score, 2)
        item["recency_score"] = round(rec_score, 2)
        item["methodology_score"] = round(meth_score, 2)
        item["traceability_score"] = round(trac_score, 2)
        item["evidence_score"] = composite_veritas_score
        item["quality_label"] = quality_label

        return item

    @classmethod
    def calculate_overall_breakdown(cls, evidence_items: List[Dict[str, Any]]) -> SourceScoreBreakdown:
        if not evidence_items:
            return SourceScoreBreakdown(
                authority_pct=0.0,
                relevance_pct=0.0,
                recency_pct=0.0,
                methodology_pct=0.0,
                traceability_pct=0.0,
                composite_veritas_score=0.0,
                quality_tier="QUESTIONABLE"
            )

        avg_auth = sum(e.get("authority_score", 0.5) for e in evidence_items) / len(evidence_items)
        avg_rel = sum(e.get("relevance_score", 0.5) for e in evidence_items) / len(evidence_items)
        avg_rec = sum(e.get("recency_score", 0.5) for e in evidence_items) / len(evidence_items)
        avg_meth = sum(e.get("methodology_score", 0.5) for e in evidence_items) / len(evidence_items)
        avg_trac = sum(e.get("traceability_score", 0.5) for e in evidence_items) / len(evidence_items)

        composite = (
            settings.WEIGHT_AUTHORITY * avg_auth +
            settings.WEIGHT_RELEVANCE * avg_rel +
            settings.WEIGHT_RECENCY * avg_rec +
            settings.WEIGHT_METHODOLOGY * avg_meth +
            settings.WEIGHT_TRACEABILITY * avg_trac
        ) * 100.0

        composite = round(composite, 1)

        if composite >= settings.DECISION_THRESHOLD_HIGH:
            tier = "HIGH"
        elif composite >= settings.DECISION_THRESHOLD_MODERATE:
            tier = "MODERATE"
        elif composite >= settings.DECISION_THRESHOLD_LOW:
            tier = "LOW"
        else:
            tier = "QUESTIONABLE"

        return SourceScoreBreakdown(
            authority_pct=round(avg_auth * 100, 1),
            relevance_pct=round(avg_rel * 100, 1),
            recency_pct=round(avg_rec * 100, 1),
            methodology_pct=round(avg_meth * 100, 1),
            traceability_pct=round(avg_trac * 100, 1),
            composite_veritas_score=composite,
            quality_tier=tier
        )
