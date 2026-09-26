from typing import Dict, Any, List, Tuple
from app.llm.grok_client import GrokClient
from app.llm.gemini_client import GeminiClient
from app.schemas.evidence import Observation, Claim, EvidenceItem
from app.utils.logger import logger

class LLMOrchestrator:
    """
    Two-Layer Reasoning Orchestrator
    Attempts primary Groq reasoning with structured output validation.
    Falls back to Gemini only if Groq is unavailable or fails.
    If no LLM keys are configured, generates a deterministic, transparent evidence audit report.
    """

    @classmethod
    async def synthesize_audit_report(
        cls,
        user_query: str,
        observations: List[Dict[str, Any]],
        claims: List[Dict[str, Any]],
        supporting_evidence: List[Dict[str, Any]],
        conflicting_evidence: List[Dict[str, Any]],
        contradictions: List[Dict[str, Any]],
        missing_information: List[Dict[str, Any]],
        decision_status: str,
        overall_score: float,
        decision_rationale: str = ""
    ) -> Tuple[str, List[Dict[str, Any]], str, bool]:
        """
        Returns:
            (final_explanation, citations, provider_used, fallback_used)
        """
        # Prepare citation registry
        all_ev = supporting_evidence + conflicting_evidence
        citations = []
        for e in all_ev:
            citations.append({
                "citation_id": f"[{e.get('evidence_id', 'EV-001')}]",
                "evidence_id": e.get("evidence_id", ""),
                "source_name": e.get("source_name", ""),
                "title": e.get("title", ""),
                "score": e.get("evidence_score", 0),
                "url": e.get("url", ""),
                "date": e.get("publication_date", "")
            })

        # Compact context construction
        obs_summary = "; ".join([f"{o.get('name')}: {cls._format_value(o.get('value'))} {o.get('unit') or ''}".strip() for o in observations]) or "None extracted"
        claims_summary = "; ".join([c.get("claim", "") for c in claims]) or user_query
        ev_summary = "\n".join([f"[{e.get('evidence_id')}] ({e.get('source_name')}, Score: {e.get('evidence_score')}/100): {e.get('text')[:200]}" for e in all_ev[:5]])
        
        has_missing = len(missing_information) > 0
        has_conflicts = len(contradictions) > 0
        is_supported = decision_status == "SUPPORTED"

        if not has_missing and not has_conflicts and is_supported:
            constraint = """
HARD CONSTRAINT: The evidence pipeline has confirmed:
- missing_information list is EMPTY (no missing parameters detected)
- contradictions list is EMPTY (no conflicts detected)  
- Decision status is SUPPORTED

You MUST NOT write a Limitations section. You MUST NOT mention missing parameters,
incomplete data, or suggest additional tests are needed. The conclusion must state
all values are normal with no caveats. Violating this constraint is a critical error.
"""
        else:
            constraint = ""

        limitations_req = ""
        if missing_information or contradictions or decision_status != "SUPPORTED":
            limitations_req = "\n   ## Limitations"

        missing_guidance_req = ""
        if missing_information or contradictions:
            missing_guidance_req = "\n   - Essential missing context or conflicting guidance"

        prompt = f"""{constraint}
Clinical Audit Context:
- User Query: {user_query}
- Extracted Document Observations: {obs_summary}
- Extracted Claims: {claims_summary}
- Deterministic Decision Status: {decision_status}
- Overall Veritas Quality Score: {overall_score}/100
- Available Authoritative Evidence:
{ev_summary}
- Missing information items: {len(missing_information)} (if 0, write NO Limitations section)
- Contradictions Detected: {len(contradictions)} conflict(s) flagged.

Instructions:
Generate a clear, objective, evidence-audited clinical explanation in JSON format with a single key "explanation".

FORMAT REQUIREMENTS — follow these exactly:
1. Structure the response using markdown with these section headers using ##:
   ## Assessment
   ## Evidence Summary{limitations_req}
   ## Conclusion
2. Use bullet points (- ) for lists of findings, factors, or recommendations.
3. **Bold** key medical terms, clinical values, and important concepts.
4. CRITICAL: NEVER include bracket codes like [EV-001], [EV-002], or any [XX-NNN] patterns in your response.
   Do not use any internal citation identifiers. Source attribution is handled externally.
   If you need to name a source, use its full name: WHO, FDA, CDC, MedlinePlus, PubMed, etc.
5. Clearly state:
   - Directly observed findings vs interpretations
   - What is supported by authoritative references (name the authority by name, not by ID)
   - Why the decision status is '{decision_status}'{missing_guidance_req}

IMPORTANT: Do NOT invent limitations, caveats, or missing data warnings that are not present in the evidence provided to you. If missing_information[] is empty, do not write a Limitations section at all. If all evidence scores are normal and the decision gate is SUPPORTED with no conflicts and no missing info, your conclusion should state clearly that all available data is within normal ranges and no abnormalities are detected. Do not hedge beyond what the evidence actually says.
"""

        provider_used = "DETERMINISTIC_ENGINE"
        fallback_used = False
        parsed_llm = None

        # 1. Try Groq Primary
        grok_resp = await GrokClient.generate_reasoning(prompt)
        if grok_resp and "explanation" in grok_resp:
            parsed_llm = grok_resp["explanation"]
            provider_used = "Groq (llama-3.3-70b)"
        else:
            # 2. Try Gemini Fallback
            gemini_resp = await GeminiClient.generate_reasoning(prompt)
            if gemini_resp and "explanation" in gemini_resp:
                parsed_llm = gemini_resp["explanation"]
                provider_used = "Google_Gemini"
                fallback_used = True

        # 3. Deterministic Fallback if no LLM responded
        if not parsed_llm:
            parsed_llm = cls._generate_deterministic_explanation(
                user_query=user_query,
                observations=observations,
                claims=claims,
                supporting_evidence=supporting_evidence,
                conflicting_evidence=conflicting_evidence,
                contradictions=contradictions,
                missing_information=missing_information,
                decision_status=decision_status,
                overall_score=overall_score,
                decision_rationale=decision_rationale
            )
            provider_used = "VERITAS_DETERMINISTIC_CORE"

        parsed_llm = cls._strip_unwarranted_limitations(
            parsed_llm, missing_information, contradictions, decision_status
        )

        return parsed_llm, citations, provider_used, fallback_used

    @staticmethod
    def _strip_unwarranted_limitations(
        response_text: str,
        missing_information: List[Dict[str, Any]],
        contradictions: List[Dict[str, Any]],
        decision_status: str
    ) -> str:
        has_missing = len(missing_information) > 0
        has_conflicts = len(contradictions) > 0
        is_supported = decision_status == "SUPPORTED"
        
        if not has_missing and not has_conflicts and is_supported:
            import re
            # Remove the entire Limitations section and its content
            # Handles both ## Limitations and **Limitations** markdown styles
            cleaned = re.sub(
                r'\n?(##\s*Limitations\s*\n|^\*\*Limitations\*\*\s*\n|^Limitations\s*\n)(.*?)(?=\n##\s|\n\*\*[A-Z]|\nConclusion|\Z)',
                '\n',
                response_text,
                flags=re.DOTALL | re.MULTILINE | re.IGNORECASE
            )
            # Also strip any trailing caveat sentence in Conclusion mentioning 
            # "additional", "missing", "further", "cannot be rendered", "without further"
            cleaned = re.sub(
                r'\s*(Further clinical details[^.]*\.|Additional clinical[^.]*\.|A definitive diagnosis cannot[^.]*\.|Without further[^.]*\.)',
                '',
                cleaned,
                flags=re.IGNORECASE
            )
            return cleaned.strip()
        
        return response_text

    @staticmethod
    def _format_value(val: Any) -> str:
        if isinstance(val, dict):
            if "formatted" in val:
                return str(val["formatted"])
            if "drug" in val and "dosage" in val:
                return f"{val['drug']} {val['dosage']}"
        return str(val)

    @classmethod
    def _generate_deterministic_explanation(
        cls,
        user_query: str,
        observations: List[Dict[str, Any]],
        claims: List[Dict[str, Any]],
        supporting_evidence: List[Dict[str, Any]],
        conflicting_evidence: List[Dict[str, Any]],
        contradictions: List[Dict[str, Any]],
        missing_information: List[Dict[str, Any]],
        decision_status: str,
        overall_score: float,
        decision_rationale: str = ""
    ) -> str:
        parts = []

        # ## Assessment
        assessment_lines = []
        if observations:
            obs_lines = [f"- **{o.get('name')}**: {cls._format_value(o.get('value'))} {o.get('unit') or ''}".strip() for o in observations]
            assessment_lines.append("**Observed clinical findings:**\n" + "\n".join(obs_lines))

        if decision_status == "SUPPORTED":
            source_names = ", ".join({e.get("source_name", "") for e in supporting_evidence[:3] if e.get("source_name")})
            assessment_lines.append(
                f"The clinical observations are **supported** by authoritative medical guidelines"
                f"{(' (' + source_names + ')') if source_names else ''}."
                f" Composite evidence quality score: **{overall_score:.1f}/100**."
            )
        elif decision_status == "CONFLICTING":
            assessment_lines.append(
                "**Conflicting guidance detected.** Authoritative sources provide differing recommendations or diagnostic criteria."
            )
        elif decision_status == "ADDITIONAL_INFORMATION_REQUIRED":
            assessment_lines.append(
                "**Additional clinical context is required** before a defensible conclusion can be reached."
            )
        elif decision_status == "QUESTIONABLE":
            assessment_lines.append(
                f"**Questionable evidence quality** (Composite Score: {overall_score:.1f}/100). "
                "Information could not be independently corroborated by Tier 1/2 authoritative databases."
            )
        else:
            assessment_lines.append(
                "**Inconclusive.** The available clinical and reference data does not permit a defensible medical conclusion."
            )

        parts.append("## Assessment\n\n" + "\n\n".join(assessment_lines))

        # ## Evidence Summary
        ev_lines = []
        if supporting_evidence:
            ev_lines.append("**Supporting sources:**")
            for e in supporting_evidence[:3]:
                src = e.get("source_name", "Authoritative source")
                ev_lines.append(f"- {src}: {e.get('text', '')[:150]}…" if e.get('text') else f"- {src}")
        if conflicting_evidence:
            ev_lines.append("\n**Conflicting sources:**")
            for e in conflicting_evidence[:2]:
                src = e.get("source_name", "Source")
                ev_lines.append(f"- {src}: {e.get('text', '')[:150]}…" if e.get('text') else f"- {src}")

        if ev_lines:
            parts.append("## Evidence Summary\n\n" + "\n".join(ev_lines))

        # ## Limitations
        limit_lines = []
        if contradictions:
            for c in contradictions:
                a_name = c.get("source_a_name", "Source A")
                b_name = c.get("source_b_name", "Source B")
                limit_lines.append(f"- **{a_name}** vs **{b_name}**: {c.get('difference_reason', '')}")
        if missing_information:
            for m in missing_information[:3]:
                limit_lines.append(f"- **{m.get('category')}**: {m.get('item')} — {m.get('clinical_reason', '')}")

        if "CONTRAINDICATION DETECTED:" in decision_rationale:
            contra_text = decision_rationale.replace("CONTRAINDICATION DETECTED:", "").strip()
            limit_lines.insert(0, f"- **Contraindication**: {contra_text}")

        if limit_lines:
            parts.append("## Limitations\n\n" + "\n".join(limit_lines))

        # ## Conclusion
        conclusion = ""
        if decision_status == "SUPPORTED":
            conclusion = "Evidence from authoritative sources supports the clinical observations. Standard clinical protocols apply."
        elif decision_status != "SUPPORTED":
            conclusion = (
                "**Clinical Decision Notice:** Professional clinical review and in-person medical evaluation are recommended "
                "before acting on these findings."
            )
        parts.append("## Conclusion\n\n" + conclusion)

        return "\n\n".join(parts)

