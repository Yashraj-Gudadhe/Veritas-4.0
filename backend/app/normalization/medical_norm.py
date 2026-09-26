import re
from typing import Dict, Any, List, Optional

class MedicalNormalizer:
    """
    Normalizes medical synonyms, abbreviations, units, and concepts
    into canonical clinical entities while preserving original wording for strict traceability.
    """

    CONCEPT_MAP = {
        "blood_pressure": [
            "bp", "b.p.", "blood pressure", "arterial pressure", "arterial blood pressure",
            "systolic pressure", "diastolic pressure", "hypotension", "hypertension", "htn"
        ],
        "blood_glucose": [
            "fbs", "rbs", "blood sugar", "fasting blood sugar", "random blood sugar",
            "blood glucose", "glycemia", "hyperglycemia", "hypoglycemia", "glucose"
        ],
        "glycated_hemoglobin": [
            "hba1c", "a1c", "glycated hemoglobin", "glycosylated hemoglobin", "hemoglobin a1c"
        ],
        "heart_rate": [
            "hr", "heart rate", "pulse", "pulse rate", "tachycardia", "bradycardia", "cardiac rate"
        ],
        "oxygen_saturation": [
            "spo2", "o2 sat", "oxygen saturation", "pulse oximetry", "hypoxemia", "hypoxia"
        ],
        "hemoglobin": [
            "hb", "hemoglobin", "haemoglobin", "anemia", "hgb"
        ],
        "creatinine": [
            "serum creatinine", "creatinine", "kidney function", "renal function", "egfr", "gfr"
        ],
        "cholesterol": [
            "lipid panel", "cholesterol", "ldl", "hdl", "triglycerides", "total cholesterol", "dyslipidemia", "hyperlipidemia"
        ],
        "body_temperature": [
            "temp", "temperature", "body temperature", "fever", "pyrexia", "hyperthermia", "hypothermia"
        ],
        "hypertension_medication": [
            "lisinopril", "amlodipine", "losartan", "metoprolol", "hydrochlorothiazide", "atenolol", "enalapril"
        ],
        "diabetes_medication": [
            "metformin", "glipizide", "insulin", "empagliflozin", "sitagliptin", "semaglutide"
        ]
    }

    UNIT_MAP = {
        "mm hg": "mmHg",
        "mmhg": "mmHg",
        "mm of hg": "mmHg",
        "mg/dl": "mg/dL",
        "mg / dl": "mg/dL",
        "mg%": "mg/dL",
        "mmol/l": "mmol/L",
        "bpm": "bpm",
        "beats/min": "bpm",
        "beats per min": "bpm",
        "gm/dl": "g/dL",
        "g/dl": "g/dL",
        "percent": "%"
    }

    @classmethod
    def normalize_term(cls, term: str) -> str:
        clean = term.lower().strip()
        for canonical, synonyms in cls.CONCEPT_MAP.items():
            for syn in synonyms:
                # Use word boundary matching to prevent substring false-positives
                # e.g. "bp" must not match inside "bpm"; "hb" must not match inside "hba1c"
                pattern = r'\b' + re.escape(syn) + r'\b'
                if re.search(pattern, clean):
                    return canonical
        return clean.replace(" ", "_")

    @classmethod
    def normalize_unit(cls, unit: Optional[str]) -> Optional[str]:
        if not unit:
            return None
        clean = unit.lower().strip()
        return cls.UNIT_MAP.get(clean, unit)

    @classmethod
    def extract_canonical_concepts(cls, text: str) -> List[str]:
        detected = set()
        clean = text.lower()
        for canonical, synonyms in cls.CONCEPT_MAP.items():
            for syn in synonyms:
                # Use word boundary matching
                pattern = r'\b' + re.escape(syn) + r'\b'
                if re.search(pattern, clean):
                    detected.add(canonical)
                    break
        return list(detected)
