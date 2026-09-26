from typing import List, Dict, Any
from app.schemas.evidence import Observation, MissingInfoItem

class MissingEvidenceDetector:
    """
    Missing Evidence Engine
    Compares document observations against clinical evidence requirements.
    Explicitly flags missing clinical context that must be collected before forming a definitive conclusion.
    Each parameter type carries its own clinically accurate caveat string — no shared generic text.
    """

    # Parameter-specific confirmatory caveat strings (clinically accurate, not shared across types)
    CAVEATS = {
        "blood_pressure": (
            "Single isolated reading cannot rule out white-coat hypertension, postural variation, "
            "or situational anxiety. Requires serial measurements on ≥2 separate occasions."
        ),
        "glucose": (
            "Single fasting glucose reading requires confirmation. Fasting status (minimum 8 hours) "
            "must be verified. Postprandial state substantially alters diagnostic thresholds."
        ),
        "hba1c": (
            "HbA1c requires confirmation with a repeat test on a separate occasion unless clinical "
            "symptoms of hyperglycemia are unequivocal. Haemoglobinopathies or anaemia may affect accuracy."
        ),
        "egfr": (
            "Single creatinine/eGFR measurement may reflect acute fluctuation. Repeat testing over "
            "≥3 months is required to confirm chronicity and CKD staging per KDIGO guidelines."
        ),
        "creatinine": (
            "Single creatinine/eGFR measurement may reflect acute fluctuation. Repeat testing over "
            "≥3 months is required to confirm chronicity and CKD staging per KDIGO guidelines."
        ),
        "potassium": (
            "Haemolysed samples falsely elevate serum potassium. Repeat sampling in non-haemolysed "
            "specimen is required before clinical action."
        ),
        "medication": (
            "Iatrogenic drug-induced etiology (e.g. antihypertensive overtreatment, diuretics) "
            "must be evaluated."
        ),
        "symptom": (
            "Essential to distinguish benign asymptomatic physiological variance from symptomatic "
            "cerebral or systemic hypoperfusion."
        ),
        "default": (
            "Mandatory clinical parameter required by guideline standards."
        ),
    }

    @classmethod
    def detect_missing(
        cls,
        observations: List[Observation],
        requirements: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        missing_items = []
        item_counter = 1

        # ---- Inventory what is present ----
        has_bp       = any(o.type == "blood_pressure" for o in observations)
        has_repeat_bp = sum(1 for o in observations if o.type == "blood_pressure") >= 2
        has_glucose  = any(o.type == "glucose" for o in observations)
        has_hba1c    = any(o.type == "hba1c" for o in observations)
        has_egfr     = any(o.type == "egfr" for o in observations)
        has_creat    = any(o.type == "creatinine" for o in observations)
        has_potassium = any(o.type == "potassium" for o in observations)
        has_meds     = any(o.type == "medication" for o in observations)
        has_symptoms = any("symptom" in o.type.lower() or "finding" in o.name.lower() for o in observations)

        # ---- Dual-criteria diabetes check — suppresses individual confirmatory flags ----
        def _get_float_val(val):
            try:
                if isinstance(val, dict):
                    return None
                return float(val)
            except (ValueError, TypeError):
                return None

        glucose_vals = [v for o in observations if o.type == "glucose" and (v := _get_float_val(o.value)) is not None]
        hba1c_vals   = [v for o in observations if o.type == "hba1c" and (v := _get_float_val(o.value)) is not None]
        diabetes_dual_confirmed = (
            any(v >= 126 for v in glucose_vals) and
            any(v >= 6.5 for v in hba1c_vals)
        )

        # ---- eGFR values for CKD checks ----
        egfr_vals    = [v for o in observations if o.type == "egfr" and (v := _get_float_val(o.value)) is not None]
        k_vals       = [v for o in observations if o.type == "potassium" and (v := _get_float_val(o.value)) is not None]
        min_egfr     = min(egfr_vals) if egfr_vals else None

        # ---- Process requirements from the requirement engine ----
        for req in requirements:
            req_text = req.get("requirement", "")
            cat = req.get("category", "IMPORTANT")

            is_missing = False
            clinical_reason = ""
            param_type = "default"

            if "repeat" in req_text.lower() and "blood pressure" in req_text.lower() and not has_repeat_bp:
                is_missing = True
                param_type = "blood_pressure"

            elif "repeat" in req_text.lower() and "glucose" in req_text.lower():
                if diabetes_dual_confirmed:
                    continue
                is_missing = True
                param_type = "glucose"

            elif "repeat" in req_text.lower() and ("hba1c" in req_text.lower() or "a1c" in req_text.lower()):
                if diabetes_dual_confirmed:
                    continue
                is_missing = True
                param_type = "hba1c"

            elif "repeat" in req_text.lower() and ("egfr" in req_text.lower() or "creatinine" in req_text.lower()):
                is_missing = True
                param_type = "egfr"

            elif "repeat" in req_text.lower() and not has_repeat_bp:
                # Generic repeat for non-classified repeat requirement (default to BP logic only)
                if has_bp:
                    is_missing = True
                    param_type = "blood_pressure"

            elif "symptom" in req_text.lower() and not has_symptoms:
                is_missing = True
                param_type = "symptom"

            elif "medication" in req_text.lower() and not has_meds:
                is_missing = True
                param_type = "medication"

            elif "fasting status" in req_text.lower() and has_glucose and not diabetes_dual_confirmed:
                is_missing = True
                param_type = "glucose"

            clinical_reason = cls.CAVEATS.get(param_type, cls.CAVEATS["default"])

            if is_missing:
                missing_items.append({
                    "id": f"MIS-{item_counter:03d}",
                    "item": req_text,
                    "category": cat,
                    "clinical_reason": clinical_reason
                })
                item_counter += 1

        # ---- Proactive observation-based missing checks (beyond requirement engine) ----

        # eGFR < 60: require serial eGFR for CKD staging confirmation
        if has_egfr and min_egfr is not None and min_egfr < 60:
            missing_items.append({
                "id": f"MIS-{item_counter:03d}",
                "item": "3-month serial eGFR for CKD staging confirmation (KDIGO)",
                "category": "IMPORTANT",
                "clinical_reason": cls.CAVEATS["egfr"]
            })
            item_counter += 1

        # Potassium > 5.0: require repeat in non-haemolysed sample + ECG
        if has_potassium and any(v > 5.0 for v in k_vals):
            missing_items.append({
                "id": f"MIS-{item_counter:03d}",
                "item": "Repeat potassium in non-haemolysed sample",
                "category": "CRITICAL",
                "clinical_reason": cls.CAVEATS["potassium"]
            })
            item_counter += 1
            missing_items.append({
                "id": f"MIS-{item_counter:03d}",
                "item": "ECG to assess cardiac risk from hyperkalaemia",
                "category": "CRITICAL",
                "clinical_reason": "Hyperkalaemia (K+ > 5.0 mEq/L) carries risk of life-threatening cardiac arrhythmia. ECG is mandatory before any clinical intervention."
            })
            item_counter += 1

        # Creatinine present but no eGFR: require eGFR calculation
        if has_creat and not has_egfr:
            missing_items.append({
                "id": f"MIS-{item_counter:03d}",
                "item": "Calculate eGFR using CKD-EPI equation from serum creatinine",
                "category": "IMPORTANT",
                "clinical_reason": "Serum creatinine alone is an unreliable marker of renal function without eGFR calculation adjusted for age, sex, and ethnicity per KDIGO 2012 guidelines."
            })
            item_counter += 1

        # Medication + eGFR < 30: pharmacist review for renal dose adjustment
        if has_meds and min_egfr is not None and min_egfr < 30:
            missing_items.append({
                "id": f"MIS-{item_counter:03d}",
                "item": "Pharmacist review for renal dose adjustment (eGFR < 30)",
                "category": "CRITICAL",
                "clinical_reason": "Severely reduced eGFR (< 30 mL/min) substantially alters drug clearance. Several commonly prescribed medications are contraindicated or require mandatory dose reduction at this level."
            })
            item_counter += 1

        return missing_items
