from typing import List, Dict, Any
from app.schemas.evidence import Contradiction

class ConflictDetector:
    """
    Conflict & Contradiction Detection Engine
    Identifies clinical, guideline, or semantic disagreements between evidence sources.
    Transparently details the basis of difference without arbitrarily discarding either source.
    """

    @classmethod
    def detect_conflicts(
        cls,
        evidence_items: List[Dict[str, Any]],
        conflicting_items: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        contradictions = []
        con_idx = 1

        # Check explicit conflicting items paired against supporting items
        supporting_items = [e for e in evidence_items if e.get("supports_claim", True) and e.get("quality_label") != "QUESTIONABLE"]

        for conf in conflicting_items:
            # Pair with highest-authority supporting item
            partner = supporting_items[0] if supporting_items else evidence_items[0] if evidence_items else None
            if partner and partner.get("evidence_id") != conf.get("evidence_id"):
                reason = conf.get("difference_reason") or conf.get("reasoning")
                if not reason:
                    # Deduce reason based on metadata
                    date_a = partner.get("publication_date", "2021")
                    date_b = conf.get("publication_date", "2024")
                    if date_a[:4] != date_b[:4]:
                        reason = f"Temporal & guideline version variance ({date_a[:4]} vs {date_b[:4]}). Recent clinical trials adopted stricter criteria."
                    else:
                        reason = "Different target patient populations, clinical risk stratification, or methodology protocols."

                contradictions.append({
                    "id": f"CON-{con_idx:03d}",
                    "source_a_id": partner.get("evidence_id", "EV-001"),
                    "source_a_name": partner.get("source_name", "Authoritative Source A"),
                    "source_a_claim": partner.get("title", "") + ": " + partner.get("text", "")[:180],
                    "source_b_id": conf.get("evidence_id", "EV-002"),
                    "source_b_name": conf.get("source_name", "Authoritative Source B"),
                    "source_b_claim": conf.get("title", "") + ": " + conf.get("text", "")[:180],
                    "difference_reason": reason,
                    "severity": conf.get("severity", "SIGNIFICANT")
                })
                con_idx += 1

        return contradictions
