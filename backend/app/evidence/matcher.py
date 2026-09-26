from typing import List, Dict, Any, Tuple
from app.schemas.evidence import Claim, EvidenceItem
from app.scoring.evaluator import VeritasScorer

class EvidenceMatcher:
    """
    Matches extracted claims to candidate evidence items.
    Classifies relationship into SUPPORTING, CONFLICTING, QUESTIONABLE, or IRRELEVANT.
    """

    @classmethod
    def match_and_classify(
        cls,
        claims: List[Claim],
        evidence_items: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        supporting = []
        conflicting = []
        questionable = []

        for item in evidence_items:
            rel_type = item.get("relationship", "SUPPORTING")
            
            # Score first
            scored_item = VeritasScorer.evaluate_evidence_item(item)
            score = scored_item.get("evidence_score", 0)
            
            # Explicit conflicting item
            if rel_type == "CONFLICTING" or not item.get("supports_claim", True):
                scored_item["relationship"] = "CONFLICTING"
                scored_item["supports_claim"] = False
                conflicting.append(scored_item)
            # Questionable check
            elif score < 50.0 or scored_item.get("authority_tier", 5) >= 4 or scored_item.get("quality_label") == "QUESTIONABLE":
                scored_item["relationship"] = "QUESTIONABLE"
                scored_item["supports_claim"] = False
                questionable.append(scored_item)
            else:
                scored_item["relationship"] = "SUPPORTING"
                scored_item["supports_claim"] = True
                supporting.append(scored_item)

        return supporting, conflicting, questionable
