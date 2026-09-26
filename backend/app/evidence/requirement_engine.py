from typing import List, Dict, Any, Optional
from app.schemas.evidence import Observation, Claim

class EvidenceRequirementEngine:
    """
    Evidence Requirement Engine
    Determines what clinical evidence and contextual parameters are strictly mandatory
    before a medical conclusion or diagnostic claim can be justified.
    """

    REQUIREMENT_RULES = {
        "blood_pressure": {
            "low": [
                {"requirement": "Standard clinical definition & reference range for hypotension vs physiological baseline", "category": "CRITICAL"},
                {"requirement": "Repeat blood pressure reading taken after 5 minutes seated rest", "category": "CRITICAL"},
                {"requirement": "Presence or absence of hypoperfusion symptoms (dizziness, fainting, orthostatic lightheadedness)", "category": "CRITICAL"},
                {"requirement": "Current medication list (antihypertensives, beta-blockers, diuretics)", "category": "IMPORTANT"},
                {"requirement": "Hydration status and recent fluid intake history", "category": "IMPORTANT"},
                {"requirement": "Baseline historical blood pressure readings", "category": "OPTIONAL"}
            ],
            "high": [
                {"requirement": "Standard clinical diagnostic criteria for Stage 1 / Stage 2 Hypertension", "category": "CRITICAL"},
                {"requirement": "Serial repeat blood pressure measurements on at least 2 separate occasions", "category": "CRITICAL"},
                {"requirement": "White-coat hypertension screening or ambulatory BP monitoring", "category": "IMPORTANT"},
                {"requirement": "Evaluation of cardiovascular risk factors and current pharmacotherapy", "category": "IMPORTANT"},
                {"requirement": "Target organ damage screening (ECG, renal panel, urine protein)", "category": "OPTIONAL"}
            ]
        },
        "blood_glucose": {
            "high": [
                {"requirement": "Fasting status confirmation (minimum 8 hours fast)", "category": "CRITICAL"},
                {"requirement": "Confirmatory repeat laboratory fasting plasma glucose or standardized HbA1c test", "category": "CRITICAL"},
                {"requirement": "Classic symptoms of hyperglycemia (polyuria, polydipsia, unexplained weight loss)", "category": "IMPORTANT"},
                {"requirement": "Medication history (steroids, diabetogenic agents, insulin)", "category": "IMPORTANT"}
            ],
            "low": [
                {"requirement": "Whipple's triad assessment (symptoms, low plasma glucose, symptom resolution with glucose)", "category": "CRITICAL"},
                {"requirement": "Timing relative to meals and physical activity", "category": "CRITICAL"},
                {"requirement": "Current antidiabetic medications (sulfonylureas, insulin dosages)", "category": "CRITICAL"}
            ]
        },
        "glycated_hemoglobin": {
            "general": [
                {"requirement": "Diagnostic threshold criteria (ADA / WHO guidelines for prediabetes & diabetes)", "category": "CRITICAL"},
                {"requirement": "Exclusion of hemoglobinopathies or hemolytic anemia that alter red cell turnover", "category": "IMPORTANT"},
                {"requirement": "Correlation with recent self-monitoring blood glucose logs", "category": "IMPORTANT"}
            ]
        },
        "medication": {
            "general": [
                {"requirement": "Indication verification matching approved clinical guidelines", "category": "CRITICAL"},
                {"requirement": "Dosage appropriateness for renal/hepatic function and age", "category": "CRITICAL"},
                {"requirement": "Drug-drug interaction and contraindication screening", "category": "IMPORTANT"},
                {"requirement": "Documented adverse effect monitoring parameters", "category": "IMPORTANT"}
            ]
        },
        "general_clinical": [
            {"requirement": "Authoritative peer-reviewed or guideline-backed evidence source", "category": "CRITICAL"},
            {"requirement": "Patient clinical context and symptom presentation", "category": "IMPORTANT"},
            {"requirement": "Laboratory quality assurance and reference interval calibration", "category": "OPTIONAL"}
        ]
    }

    @classmethod
    def generate_requirements(
        cls,
        observations: List[Observation],
        claims: List[Claim],
        user_query: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        requirements = []
        seen = set()

        for obs in observations:
            if obs.type == "blood_pressure" and isinstance(obs.value, dict):
                sys_val = obs.value.get("systolic", 120)
                dia_val = obs.value.get("diastolic", 80)
                if sys_val < 90 or dia_val < 60:
                    for req in cls.REQUIREMENT_RULES["blood_pressure"]["low"]:
                        if req["requirement"] not in seen:
                            seen.add(req["requirement"])
                            requirements.append(req)
                elif sys_val >= 130 or dia_val >= 85:
                    for req in cls.REQUIREMENT_RULES["blood_pressure"]["high"]:
                        if req["requirement"] not in seen:
                            seen.add(req["requirement"])
                            requirements.append(req)

            elif obs.type == "glucose":
                val = float(obs.value) if isinstance(obs.value, (int, float)) else 100
                if val > 125:
                    for req in cls.REQUIREMENT_RULES["blood_glucose"]["high"]:
                        if req["requirement"] not in seen:
                            seen.add(req["requirement"])
                            requirements.append(req)
                elif val < 70:
                    for req in cls.REQUIREMENT_RULES["blood_glucose"]["low"]:
                        if req["requirement"] not in seen:
                            seen.add(req["requirement"])
                            requirements.append(req)

            elif obs.type == "hba1c":
                for req in cls.REQUIREMENT_RULES["glycated_hemoglobin"]["general"]:
                    if req["requirement"] not in seen:
                        seen.add(req["requirement"])
                        requirements.append(req)

            elif obs.type == "medication":
                for req in cls.REQUIREMENT_RULES["medication"]["general"]:
                    if req["requirement"] not in seen:
                        seen.add(req["requirement"])
                        requirements.append(req)

        # If general question or no specific requirements generated yet, add standard clinical requirements
        if not requirements:
            for req in cls.REQUIREMENT_RULES["general_clinical"]:
                requirements.append(req)

        return requirements
