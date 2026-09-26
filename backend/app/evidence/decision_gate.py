from typing import List, Dict, Any, Tuple, Optional

class VeritasDecisionGate:
    """
    Deterministic Decision Gate
    Evaluates evidence quality, contradiction severity, and missing context completeness
    to output an audited clinical decision state.

    Pre-gate contraindication checks run before the standard 5-state logic:
      - Metformin + eGFR < 30  → CRITICAL flag + CONFLICTING decision
      - Dual-criteria diabetes (HbA1c ≥ 6.5% AND glucose ≥ 126) → confirmed, suppress repeat requests
      - eGFR < 60              → chronic staging requirement added (non-blocking)
    """

    @classmethod
    def evaluate(
        cls,
        supporting_evidence: List[Dict[str, Any]],
        conflicting_evidence: List[Dict[str, Any]],
        contradictions: List[Dict[str, Any]],
        questionable_evidence: List[Dict[str, Any]],
        missing_information: List[Dict[str, Any]],
        overall_score: float,
        observations: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[str, bool, str]:
        """
        Returns:
            (decision_status, human_review_required, rationale)
        """
        observations = observations or []

        # ================================================================
        # PRE-GATE: Extract observation values for contraindication checks
        # ================================================================
        egfr_vals   = [o.get("value") for o in observations if o.get("type") == "egfr"
                       and isinstance(o.get("value"), (int, float))]
        glucose_vals = [o.get("value") for o in observations if o.get("type") == "glucose"
                        and isinstance(o.get("value"), (int, float))]
        hba1c_vals  = [o.get("value") for o in observations if o.get("type") == "hba1c"
                       and isinstance(o.get("value"), (int, float))]
        med_obs     = [o for o in observations if o.get("type") == "medication"]

        min_egfr = min(egfr_vals) if egfr_vals else None

        # Dual-criteria diabetes confirmation (WHO 2019)
        diabetes_dual_confirmed = (
            any(v >= 126 for v in glucose_vals) and
            any(v >= 6.5 for v in hba1c_vals)
        )

        # ── PRE-GATE CHECK 1: Medication contraindication at eGFR < 30 ──
        contraindication_flags = []
        force_conflicting = False

        if med_obs and min_egfr is not None and min_egfr < 30:
            for med in med_obs:
                drug_value = med.get("value", {})
                drug_name = (
                    drug_value.get("drug", "") if isinstance(drug_value, dict) else str(drug_value)
                ).lower()

                if "metformin" in drug_name:
                    contraindication_flags.append(
                        "CRITICAL — Metformin contraindicated: eGFR < 30 mL/min. "
                        "Discontinue immediately per FDA/NICE guidelines. Risk of life-threatening lactic acidosis."
                    )
                    force_conflicting = True

        # ── PRE-GATE CHECK 2: Dual-criteria diabetes → confirmed, no repeat HbA1c needed ──
        # (missing_information is already filtered in missing_detector.py via diabetes_dual_confirmed flag;
        #  we surface the confirmation here for the rationale)
        diabetes_note = ""
        if diabetes_dual_confirmed:
            diabetes_note = (
                " Diabetes confirmed by dual criteria (HbA1c ≥ 6.5% AND fasting glucose ≥ 126 mg/dL) "
                "per WHO 2019 guidelines — no additional confirmatory test required."
            )

        # ── PRE-GATE CHECK 3: eGFR < 60 → non-blocking note ──
        ckd_note = ""
        if min_egfr is not None and min_egfr < 60:
            ckd_note = (
                f" eGFR {min_egfr} mL/min/1.73m² indicates CKD. "
                "Serial eGFR over ≥3 months required to confirm chronicity per KDIGO 2012."
            )

        # If contraindications detected, return CONFLICTING immediately
        if force_conflicting:
            rationale = (
                f"CONTRAINDICATION DETECTED: {'; '.join(contraindication_flags)}"
                f"{ckd_note}{diabetes_note}"
            )
            return ("CONFLICTING", True, rationale)

        # ================================================================
        # STANDARD 5-STATE LOGIC
        # ================================================================

        # Critical missing items check
        critical_missing = [m for m in missing_information if m.get("category") == "CRITICAL"]

        # 1. Check if no evidence found at all
        if not supporting_evidence and not conflicting_evidence and not questionable_evidence:
            return (
                "NO_RELIABLE_CONCLUSION",
                True,
                "No authoritative or peer-reviewed evidence matching the query could be retrieved."
            )

        # 2. Check for Conflicting Evidence
        if len(conflicting_evidence) > 0 or len(contradictions) > 0:
            return (
                "CONFLICTING",
                True,
                f"Detected {len(contradictions) or len(conflicting_evidence)} authoritative evidence source(s) "
                f"with divergent clinical recommendations or conflicting diagnostic thresholds."
                f"{diabetes_note}{ckd_note}"
            )

        # 3. Check for Questionable / Unverifiable Evidence
        if (not supporting_evidence and len(questionable_evidence) > 0) or (overall_score < 50.0 and len(supporting_evidence) <= 1):
            return (
                "QUESTIONABLE",
                True,
                f"Available evidence originates from low-authority, outdated, or unverified sources (Score: {overall_score:.1f}/100)."
            )

        # 4. Check for Incomplete / Additional Information Required
        if len(critical_missing) > 0:
            missing_names = ", ".join(m.get("item", "")[:40] for m in critical_missing[:2])
            return (
                "ADDITIONAL_INFORMATION_REQUIRED",
                True,
                f"Key clinical context ({missing_names}) is missing. "
                f"An isolated reading or partial finding is insufficient for diagnostic confirmation."
                f"{diabetes_note}"
            )

        # 5. Supported Evidence
        if len(supporting_evidence) >= 1 and overall_score >= 65.0:
            return (
                "SUPPORTED",
                False,
                f"Conclusion is supported by {len(supporting_evidence)} authoritative evidence source(s) "
                f"with an evidence quality score of {overall_score:.1f}/100."
                f"{diabetes_note}{ckd_note}"
            )

        # Default fallback
        return (
            "NO_RELIABLE_CONCLUSION",
            True,
            "The available evidence is insufficient to justify a definitive clinical conclusion without professional consultation."
        )
