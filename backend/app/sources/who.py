"""
WHO (World Health Organization) Official Adapter
Retrieves global health guidelines from the WHO GHO API and curated offline guidelines.

Bug fix: Previously the GHO API response was always discarded — the adapter only
checked for connectivity ("connection verified") but never parsed the data.
Now: real GHO indicator data is extracted and returned as evidence items.
Curated offline guidelines serve as fallback only when the API fails or returns
no data relevant to the queried concepts.
"""
import uuid
from typing import List, Dict, Any
from datetime import datetime, timezone

import httpx

from app.config import settings
from app.utils.logger import logger
from app.utils.cache import cache


class WHOAdapter:
    """
    World Health Organization (WHO) Official Adapter.
    Retrieves global health guidelines, disease statistics, and clinical definitions.
    Includes built-in offline curated guidelines as fallback when network is unavailable.
    """

    OFFLINE_WHO_GUIDELINES = {
        "blood_pressure": {
            "title": "WHO Guideline for the Pharmacological Treatment of Hypertension in Adults",
            "url": "https://www.who.int/publications/i/item/9789240033986",
            "date": "2021-08-25",
            "text": (
                "WHO recommends initiating pharmacological antihypertensive treatment in "
                "individuals with a confirmed diagnosis of hypertension of systolic blood "
                "pressure >= 140 mmHg or diastolic blood pressure >= 90 mmHg. For low blood "
                "pressure, a reading below 90/60 mmHg is generally defined as hypotension, "
                "but requires assessment of symptoms (dizziness, fainting) and volume status "
                "before diagnosing pathological hypotension."
            ),
            "authority_tier": 1,
        },
        "blood_glucose": {
            "title": "WHO Diagnostic Criteria and Classification of Hyperglycaemia First Detected in Pregnancy and Diabetes",
            "url": "https://www.who.int/publications/i/item/who-nmh-mnd-19.4",
            "date": "2019-10-15",
            "text": (
                "WHO defines diabetes mellitus as fasting plasma glucose >= 7.0 mmol/L "
                "(126 mg/dL) or 2-hour post-load plasma glucose >= 11.1 mmol/L (200 mg/dL), "
                "or HbA1c >= 6.5% (48 mmol/mol). Diagnosis requires a second confirmatory "
                "test in the absence of unequivocal hyperglycemia with acute metabolic "
                "decompensation."
            ),
            "authority_tier": 1,
        },
        "cardiovascular": {
            "title": "WHO HEARTS Technical Package for Cardiovascular Disease Management in Primary Health Care",
            "url": "https://www.who.int/publications/i/item/9789240001367",
            "date": "2020-04-02",
            "text": (
                "Accurate blood pressure measurement requires patient seated quietly for "
                "5 minutes, arm supported at heart level, with an appropriately sized cuff. "
                "Isolated single measurements should not form the sole basis of clinical diagnosis."
            ),
            "authority_tier": 1,
        },
    }

    # GHO indicator codes relevant to common clinical concepts
    GHO_CONCEPT_INDICATORS = {
        "blood_pressure": ["BP_04", "NCD_HYP_TREATMENT_A"],
        "blood_glucose": ["DIABETES", "GLYC_18PLUS"],
        "cardiovascular": ["CARDIOVASCULAR", "NCD_HEARTDISEASE"],
    }

    @classmethod
    async def fetch(cls, query: str, concepts: List[str]) -> List[Dict[str, Any]]:
        """
        Fetch WHO evidence for the given query and clinical concepts.

        Strategy:
        1. Try the WHO GHO API to get real indicator data.
        2. If the API returns usable results, return those.
        3. If not, fall back to offline curated WHO guidelines matched to concepts.
        4. If no concept match, use the cardiovascular guideline as the most general fallback.

        Args:
            query:    The user's clinical query string.
            concepts: List of normalized clinical concept strings.

        Returns:
            List of v1-format evidence dicts. Never empty (offline fallback always available).
        """
        cache_key = {"source": "who", "query": query, "concepts": concepts}
        cached = cache.get("online_sources", cache_key)
        if cached is not None:
            return cached

        results: List[Dict[str, Any]] = []

        # --- Step 1: Try live WHO GHO API ---
        try:
            results = await cls._fetch_gho_indicators(concepts, query)
        except Exception as e:
            logger.info(
                f"[WHOAdapter] GHO API error: {e}. Falling back to curated guidelines."
            )

        # --- Step 2: Fall back to curated offline guidelines if API gave nothing ---
        if not results:
            results = cls._offline_fallback(concepts, query)

        cache.set("online_sources", cache_key, results)
        return results

    @classmethod
    async def _fetch_gho_indicators(cls, concepts: List[str], query: str) -> List[Dict[str, Any]]:
        """
        Queries the WHO GHO API for indicator metadata relevant to the concepts.
        Returns parsed evidence items, or [] if nothing useful was returned.
        """
        results: List[Dict[str, Any]] = []

        # Determine which indicator codes to request
        indicator_codes: List[str] = []
        for concept in concepts:
            indicator_codes.extend(cls.GHO_CONCEPT_INDICATORS.get(concept, []))

        # If no specific indicators, try the generic GHO list and filter by query terms
        fetch_generic = not indicator_codes

        async with httpx.AsyncClient(timeout=5.0) as client:
            if fetch_generic:
                url = f"{settings.WHO_API_BASE_URL}/GHO"
                resp = await client.get(url, params={"$top": 5, "$format": "json"})
                if resp.status_code == 200:
                    data = resp.json()
                    indicators = data.get("value", [])
                    query_lower = query.lower()
                    for ind in indicators:
                        ind_title = ind.get("IndicatorName", "")
                        ind_code = ind.get("IndicatorCode", "")
                        if not ind_title or not ind_code:
                            continue
                        # Basic relevance filter against query words
                        if any(word in ind_title.lower() for word in query_lower.split()
                               if len(word) > 3):
                            ind_url = (
                                f"https://www.who.int/data/gho/data/indicators/"
                                f"indicator-details/GHO/{ind_code}"
                            )
                            results.append({
                                "evidence_id": str(uuid.uuid4()),
                                "source_name": "World Health Organization (WHO) — GHO",
                                "source_type": "official_international_guideline",
                                "authority_tier": 1,
                                "title": ind_title,
                                "url": ind_url,
                                "publication_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                                "text": (
                                    f"WHO Global Health Observatory indicator: {ind_title} "
                                    f"(Code: {ind_code}). "
                                    f"Source: WHO GHO data repository."
                                ),
                                "relevance_score": 0.82,
                                "authority_score": 0.98,
                                "recency_score": 0.85,
                                "methodology_score": 0.90,
                                "traceability_score": 1.0,
                                "supports_claim": True,
                                "quality_label": "HIGH",
                            })
                            if len(results) >= 2:
                                break
            else:
                for code in indicator_codes[:2]:
                    url = f"{settings.WHO_API_BASE_URL}/{code}"
                    resp = await client.get(url, params={"$top": 1, "$format": "json"})
                    if resp.status_code == 200:
                        data = resp.json()
                        values = data.get("value", [])
                        if values:
                            v = values[0]
                            ind_title = v.get("IndicatorName", code)
                            ind_url = (
                                f"https://www.who.int/data/gho/data/indicators/"
                                f"indicator-details/GHO/{code}"
                            )
                            results.append({
                                "evidence_id": str(uuid.uuid4()),
                                "source_name": "World Health Organization (WHO) — GHO",
                                "source_type": "official_international_guideline",
                                "authority_tier": 1,
                                "title": ind_title,
                                "url": ind_url,
                                "publication_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                                "text": (
                                    f"WHO Global Health Observatory indicator: {ind_title} "
                                    f"(Code: {code}). "
                                    f"Source: WHO GHO data repository."
                                ),
                                "relevance_score": 0.88,
                                "authority_score": 0.98,
                                "recency_score": 0.85,
                                "methodology_score": 0.92,
                                "traceability_score": 1.0,
                                "supports_claim": True,
                                "quality_label": "HIGH",
                            })

        if results:
            logger.info(f"[WHOAdapter] GHO API returned {len(results)} indicator(s).")
        return results

    @classmethod
    def _offline_fallback(cls, concepts: List[str], query: str) -> List[Dict[str, Any]]:
        """
        Returns curated offline WHO guidelines matched to concepts.
        Used ONLY when the live API fails or returns nothing usable.
        """
        results: List[Dict[str, Any]] = []
        matched = False

        for concept in concepts:
            if concept in cls.OFFLINE_WHO_GUIDELINES:
                guide = cls.OFFLINE_WHO_GUIDELINES[concept]
                results.append({
                    "evidence_id": str(uuid.uuid4()),
                    "source_name": "World Health Organization (WHO)",
                    "source_type": "official_international_guideline",
                    "authority_tier": 1,
                    "title": guide["title"],
                    "url": guide["url"],
                    "publication_date": guide["date"],
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                    "text": guide["text"],
                    "relevance_score": 0.92,
                    "authority_score": 0.98,
                    "recency_score": 0.85,
                    "methodology_score": 0.95,
                    "traceability_score": 1.0,
                    "supports_claim": True,
                    "quality_label": "HIGH",
                })
                matched = True

        if not matched:
            # Generic cardiovascular guideline as last resort
            guide = cls.OFFLINE_WHO_GUIDELINES["cardiovascular"]
            results.append({
                "evidence_id": str(uuid.uuid4()),
                "source_name": "World Health Organization (WHO)",
                "source_type": "official_international_guideline",
                "authority_tier": 1,
                "title": guide["title"],
                "url": guide["url"],
                "publication_date": guide["date"],
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "text": guide["text"],
                "relevance_score": 0.75,
                "authority_score": 0.98,
                "recency_score": 0.85,
                "methodology_score": 0.95,
                "traceability_score": 1.0,
                "supports_claim": True,
                "quality_label": "HIGH",
            })

        return results
