import re
from typing import List, Dict, Any, Tuple, Optional
from app.schemas.evidence import Observation, Claim
from app.utils.logger import logger

class ClaimExtractor:
    """
    Extracts structured clinical observations and claims from document text,
    strictly distinguishing observed objective measurements from interpretations and diagnoses.
    """

    @staticmethod
    def extract_observations_and_claims(
        text: str,
        source_name: str = "document.pdf",
        page: int = 1,
        user_query: Optional[str] = None
    ) -> Tuple[List[Observation], List[Claim]]:
        observations: List[Observation] = []
        claims: List[Claim] = []
        obs_counter = 1
        claim_counter = 1

        # 1. Blood Pressure Pattern (e.g. 120/80, 85/55 mmHg, BP: 140/90)
        bp_matches = re.finditer(
            r'(?i)\b(?:BP|blood\s*pressure|B\.P\.)?\s*[:\-=]?\s*(\d{2,3})\s*[/\\\/]\s*(\d{2,3})\s*(mmHg)?\b',
            text
        )
        for match in bp_matches:
            sys_val = int(match.group(1))
            dia_val = int(match.group(2))
            if 40 <= sys_val <= 300 and 20 <= dia_val <= 200:
                obs_id = f"OBS-{obs_counter:03d}"
                obs_counter += 1
                obs = Observation(
                    id=obs_id,
                    type="blood_pressure",
                    name="Blood Pressure",
                    value={"systolic": sys_val, "diastolic": dia_val, "formatted": f"{sys_val}/{dia_val}"},
                    unit="mmHg",
                    reference_range="90/60 - 120/80 mmHg",
                    source=source_name,
                    page=page,
                    section="Vital Signs"
                )
                observations.append(obs)
                
                # Derive initial claim from observation for evidence requirement analysis
                clm_id = f"CLM-{claim_counter:03d}"
                claim_counter += 1
                
                # Determine factual observation state
                if sys_val < 90 or dia_val < 60:
                    claim_text = f"The recorded blood pressure reading ({sys_val}/{dia_val} mmHg) is lower than the standard reference range."
                    claim_type = "interpretation"
                elif sys_val >= 140 or dia_val >= 90:
                    claim_text = f"The recorded blood pressure reading ({sys_val}/{dia_val} mmHg) meets hypertension diagnostic criteria."
                    claim_type = "interpretation"
                else:
                    claim_text = f"The recorded blood pressure reading ({sys_val}/{dia_val} mmHg) is within standard adult limits."
                    claim_type = "fact"

                claims.append(Claim(
                    id=clm_id,
                    claim=claim_text,
                    claim_type=claim_type,
                    support_required=True,
                    related_observations=[obs_id],
                    normalized_concept="blood_pressure"
                ))

        # 2. Blood Glucose / Fasting / Postprandial / HbA1c
        glucose_matches = re.finditer(
            r'(?i)\b(?:fasting\s*blood\s*sugar|FBS|blood\s*glucose|random\s*blood\s*sugar|RBS|glucose)\s*[:\-=]?\s*(\d{2,3}(?:\.\d+)?)\s*(mg/dL|mmol/L)?\b',
            text
        )
        for match in glucose_matches:
            g_val = float(match.group(1))
            unit = match.group(2) or "mg/dL"
            obs_id = f"OBS-{obs_counter:03d}"
            obs_counter += 1
            obs = Observation(
                id=obs_id,
                type="glucose",
                name="Blood Glucose",
                value=g_val,
                unit=unit,
                reference_range="70-99 mg/dL (fasting)",
                source=source_name,
                page=page,
                section="Laboratory Findings"
            )
            observations.append(obs)
            
            clm_id = f"CLM-{claim_counter:03d}"
            claim_counter += 1
            if g_val > 126:
                claim_text = f"Fasting blood glucose of {g_val} {unit} exceeds normal baseline and indicates hyperglycemia."
                claim_type = "interpretation"
            elif g_val < 70:
                claim_text = f"Blood glucose of {g_val} {unit} is below normal baseline, indicating hypoglycemia."
                claim_type = "interpretation"
            else:
                claim_text = f"Blood glucose of {g_val} {unit} is within normal reference limits."
                claim_type = "fact"

            claims.append(Claim(
                id=clm_id,
                claim=claim_text,
                claim_type=claim_type,
                support_required=True,
                related_observations=[obs_id],
                normalized_concept="blood_glucose"
            ))

        # 3. HbA1c Pattern
        hba1c_matches = re.finditer(r'(?i)\b(?:HbA1c|glycated\s*hemoglobin|A1C)\s*[:\-=]?\s*(\d{1,2}(?:\.\d+)?)\s*(%|percent)?\b', text)
        for match in hba1c_matches:
            val = float(match.group(1))
            obs_id = f"OBS-{obs_counter:03d}"
            obs_counter += 1
            observations.append(Observation(
                id=obs_id,
                type="hba1c",
                name="HbA1c",
                value=val,
                unit="%",
                reference_range="< 5.7%",
                source=source_name,
                page=page,
                section="Laboratory Findings"
            ))
            clm_id = f"CLM-{claim_counter:03d}"
            claim_counter += 1
            claims.append(Claim(
                id=clm_id,
                claim=f"Glycated hemoglobin (HbA1c) level is {val}%.",
                claim_type="interpretation" if val >= 5.7 else "fact",
                support_required=True,
                related_observations=[obs_id],
                normalized_concept="glycated_hemoglobin"
            ))

        # 4. Heart Rate / Pulse
        hr_matches = re.finditer(r'(?i)\b(?:heart\s*rate|pulse|pulse\s*rate|HR)\s*[:\-=]?\s*(\d{2,3})\s*(bpm|beats/min)?\b', text)
        for match in hr_matches:
            hr_val = int(match.group(1))
            if 30 <= hr_val <= 250:
                obs_id = f"OBS-{obs_counter:03d}"
                obs_counter += 1
                observations.append(Observation(
                    id=obs_id,
                    type="heart_rate",
                    name="Heart Rate",
                    value=hr_val,
                    unit="bpm",
                    reference_range="60-100 bpm",
                    source=source_name,
                    page=page,
                    section="Vital Signs"
                ))

        # 5. SpO2 / Oxygen Saturation
        spo2_matches = re.finditer(r'(?i)\b(?:SpO2|oxygen\s*saturation|O2\s*sat)\s*[:\-=]?\s*(\d{2,3})\s*(%|percent)?\b', text)
        for match in spo2_matches:
            spo2_val = int(match.group(1))
            if 50 <= spo2_val <= 100:
                obs_id = f"OBS-{obs_counter:03d}"
                obs_counter += 1
                observations.append(Observation(
                    id=obs_id,
                    type="oxygen_saturation",
                    name="Oxygen Saturation (SpO2)",
                    value=spo2_val,
                    unit="%",
                    reference_range="95-100%",
                    source=source_name,
                    page=page,
                    section="Vital Signs"
                ))

        # 6. Hemoglobin
        hb_matches = re.finditer(r'(?i)\b(?:hemoglobin|haemoglobin|Hb)\s*[:\-=]?\s*(\d{1,2}(?:\.\d+)?)\s*(g/dL|g/L)?\b', text)
        for match in hb_matches:
            hb_val = float(match.group(1))
            if 3.0 <= hb_val <= 25.0:
                obs_id = f"OBS-{obs_counter:03d}"
                obs_counter += 1
                observations.append(Observation(
                    id=obs_id,
                    type="hemoglobin",
                    name="Hemoglobin",
                    value=hb_val,
                    unit="g/dL",
                    reference_range="12.0-17.5 g/dL",
                    source=source_name,
                    page=page,
                    section="Laboratory Findings"
                ))

        # 7. Serum Creatinine / Kidney Function
        creat_matches = re.finditer(r'(?i)\b(?:serum\s*creatinine|creatinine)\s*[:\-=]?\s*(\d{1,2}(?:\.\d+)?)\s*(mg/dL|umol/L)?\b', text)
        for match in creat_matches:
            creat_val = float(match.group(1))
            obs_id = f"OBS-{obs_counter:03d}"
            obs_counter += 1
            observations.append(Observation(
                id=obs_id,
                type="creatinine",
                name="Serum Creatinine",
                value=creat_val,
                unit="mg/dL",
                reference_range="0.6-1.2 mg/dL",
                source=source_name,
                page=page,
                section="Laboratory Findings"
            ))

        # 8. eGFR (estimated Glomerular Filtration Rate)
        egfr_matches = re.finditer(
            r'(?i)\b(?:eGFR|estimated\s*GFR|GFR)\s*[:\-=]?\s*(\d{1,3}(?:\.\d+)?)\s*(mL/min(?:/1\.73\s*m[\u00b2²]?)?)?\b',
            text
        )
        for match in egfr_matches:
            egfr_val = float(match.group(1))
            if 1.0 <= egfr_val <= 200.0:
                obs_id = f"OBS-{obs_counter:03d}"
                obs_counter += 1
                obs = Observation(
                    id=obs_id,
                    type="egfr",
                    name="eGFR",
                    value=egfr_val,
                    unit="mL/min/1.73m²",
                    reference_range="60-120 mL/min/1.73m²",
                    source=source_name,
                    page=page,
                    section="Laboratory Findings"
                )
                observations.append(obs)

                clm_id = f"CLM-{claim_counter:03d}"
                claim_counter += 1
                if egfr_val < 15:
                    ckd_stage = "Stage 5 CKD (Kidney Failure)"
                elif egfr_val < 30:
                    ckd_stage = "Stage 4 CKD (Severely Reduced)"
                elif egfr_val < 45:
                    ckd_stage = "Stage 3b CKD (Moderately-Severely Reduced)"
                elif egfr_val < 60:
                    ckd_stage = "Stage 3a CKD (Mildly-Moderately Reduced)"
                elif egfr_val < 90:
                    ckd_stage = "Stage 2 CKD (Mildly Reduced)"
                else:
                    ckd_stage = "Stage 1 / Normal"

                if egfr_val < 60:
                    claim_text = f"Reduced eGFR — CKD suspected ({ckd_stage}). eGFR of {egfr_val} mL/min/1.73m² is below the 60 mL/min threshold."
                    claim_type = "interpretation"
                else:
                    claim_text = f"eGFR of {egfr_val} mL/min/1.73m² is within or above normal limits ({ckd_stage})."
                    claim_type = "fact"

                claims.append(Claim(
                    id=clm_id,
                    claim=claim_text,
                    claim_type=claim_type,
                    support_required=True,
                    related_observations=[obs_id],
                    normalized_concept="egfr"
                ))

        # 9. Serum Potassium (K+)
        k_matches = re.finditer(
            r'(?i)\b(?:potassium|K\+|serum\s*K)\s*[:\-=]?\s*(\d{1,2}(?:\.\d+)?)\s*(mEq/L|mmol/L)?\b',
            text
        )
        for match in k_matches:
            k_val = float(match.group(1))
            if 2.0 <= k_val <= 8.0:
                obs_id = f"OBS-{obs_counter:03d}"
                obs_counter += 1
                obs = Observation(
                    id=obs_id,
                    type="potassium",
                    name="Serum Potassium (K+)",
                    value=k_val,
                    unit="mEq/L",
                    reference_range="3.5-5.0 mEq/L",
                    source=source_name,
                    page=page,
                    section="Laboratory Findings"
                )
                observations.append(obs)

                clm_id = f"CLM-{claim_counter:03d}"
                claim_counter += 1
                if k_val > 5.0:
                    claim_text = f"Hyperkalemia: Serum potassium of {k_val} mEq/L exceeds the upper reference limit of 5.0 mEq/L."
                    claim_type = "interpretation"
                elif k_val < 3.5:
                    claim_text = f"Hypokalemia: Serum potassium of {k_val} mEq/L is below the lower reference limit of 3.5 mEq/L."
                    claim_type = "interpretation"
                else:
                    claim_text = f"Serum potassium of {k_val} mEq/L is within the normal reference range (3.5-5.0 mEq/L)."
                    claim_type = "fact"

                claims.append(Claim(
                    id=clm_id,
                    claim=claim_text,
                    claim_type=claim_type,
                    support_required=True,
                    related_observations=[obs_id],
                    normalized_concept="potassium"
                ))

        # 10. Serum Sodium (Na+)
        na_matches = re.finditer(
            r'(?i)\b(?:sodium|Na\+|serum\s*Na)\s*[:\-=]?\s*(\d{2,3}(?:\.\d+)?)\s*(mEq/L|mmol/L)?\b',
            text
        )
        for match in na_matches:
            na_val = float(match.group(1))
            if 110.0 <= na_val <= 170.0:
                obs_id = f"OBS-{obs_counter:03d}"
                obs_counter += 1
                obs = Observation(
                    id=obs_id,
                    type="sodium",
                    name="Serum Sodium (Na+)",
                    value=na_val,
                    unit="mEq/L",
                    reference_range="135-145 mEq/L",
                    source=source_name,
                    page=page,
                    section="Laboratory Findings"
                )
                observations.append(obs)

        # 11. Medications Extraction (e.g. Lisinopril 10mg, Metformin 500mg, Amlodipine 5mg, Atorvastatin 20mg, Aspirin 75mg)
        med_matches = re.finditer(
            r'(?i)\b(Lisinopril|Metformin|Amlodipine|Atorvastatin|Aspirin|Levothyroxine|Losartan|Omeprazole|Metoprolol|Hydrochlorothiazide|Azithromycin|Amoxicillin|Paracetamol|Ibuprofen|Ciprofloxacin|Pantoprazole)\s*(?:(\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml))|\b)',
            text
        )
        for match in med_matches:
            drug_name = match.group(1).title()
            dosage = match.group(2) or "Standard dose"
            obs_id = f"OBS-{obs_counter:03d}"
            obs_counter += 1
            observations.append(Observation(
                id=obs_id,
                type="medication",
                name=f"Medication: {drug_name}",
                value={"drug": drug_name, "dosage": dosage},
                unit=None,
                source=source_name,
                page=page,
                section="Prescription / Medications"
            ))

        # 9. User Query / Requested Assessment Claim
        if user_query:
            clm_id = f"CLM-{claim_counter:03d}"
            claim_counter += 1
            claims.insert(0, Claim(
                id=clm_id,
                claim=f"Assessment Request: {user_query}",
                claim_type="interpretation",
                support_required=True,
                related_observations=[o.id for o in observations],
                normalized_concept="clinical_assessment"
            ))

        # If no specific quantitative items were found, extract general clinical sentences
        if not claims and text:
            sentences = [s.strip() for s in re.split(r'[.\n]+', text) if len(s.strip()) > 20]
            for sent in sentences[:3]:
                clm_id = f"CLM-{claim_counter:03d}"
                claim_counter += 1
                claims.append(Claim(
                    id=clm_id,
                    claim=sent,
                    claim_type="interpretation",
                    support_required=True,
                    related_observations=[]
                ))

        return observations, claims
