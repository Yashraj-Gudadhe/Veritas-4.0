"""
CDC (Centers for Disease Control and Prevention) Adapter
Provides population-level epidemiology, surveillance metrics, and disease prevention guidance.

Bug fix: Previously no live API was ever called — a hardcoded record was always
returned unconditionally, regardless of query. Now: attempts the CDC Open Data
API (data.cdc.gov) for live indicators. Curated offline records are returned ONLY
when the live API is unavailable or returns no usable results.
"""
import uuid
from typing import List, Dict, Any
from datetime import datetime, timezone

import httpx

from app.utils.logger import logger
from app.utils.cache import cache


class CDCAdapter:
    """
    Centers for Disease Control and Prevention (CDC) Adapter.
    Provides population-level epidemiology, surveillance metrics, and disease prevention guidance.
    """

    # CDC Open Data API — queries PHDI dataset catalog
    CDC_OPEN_DATA_URL = "https://data.cdc.gov/api/views/metadata/v1"
    TIMEOUT_SEC = 5.0

    # Curated offline CDC records — fallback only
    CDC_RECORDS = {
        "blood_pressure": {
            "title": "CDC High Blood Pressure & Hypotension Surveillance",
            "url": "https://www.cdc.gov/bloodpressure/facts.htm",
            "date": "2023-07-06",
            "text": (
                "Nearly half of adults in the United States have hypertension. "
                "Normal blood pressure is defined as less than 120/80 mmHg. "
                "Hypotension (low blood pressure) is typically defined as a reading "
                "lower than 90/60 mmHg; however, what is low for one person may be "
                "normal for another in the absence of clinical symptoms."
            ),
            "authority_tier": 1,
        },
        "general": {
            "title": "CDC Public Health Guidelines and Surveillance",
            "url": "https://www.cdc.gov/",
            "date": "2023-01-01",
            "text": (
                "The CDC provides authoritative clinical and public health guidance "
                "for disease surveillance, prevention, and control across the United States."
            ),
            "authority_tier": 1,
        },
    }

    @classmethod
    async def fetch(cls, query: str, concepts: List[str]) -> List[Dict[str, Any]]:
        """
        Fetch CDC evidence for the given query and clinical concepts.

        Strategy:
        1. Try the CDC Open Data API (data.cdc.gov) for live surveillance data.
        2. If nothing relevant comes back, fall back to curated offline CDC records
           only for concepts that match (blood_pressure); skip 'general' record
           unless nothing else matches.

        Args:
            query:    The user's clinical query string.
            concepts: List of normalized clinical concept strings.

        Returns:
            List of v1-format evidence dicts, or [] if no API result and no concept match.
        """
        cache_key = {"source": "cdc", "query": query, "concepts": concepts}
        cached = cache.get("online_sources", cache_key)
        if cached is not None:
            return cached

        results: List[Dict[str, Any]] = []

        # --- Step 1: Try live CDC Open Data API ---
        try:
            results = await cls._fetch_live(query)
        except Exception as e:
            logger.info(f"[CDCAdapter] Live API unavailable: {e}. Using curated records.")

        # --- Step 2: Fall back to curated records if API returned nothing ---
        if not results:
            results = cls._offline_fallback(concepts, query)

        cache.set("online_sources", cache_key, results)
        return results

    @classmethod
    async def _fetch_live(cls, query: str) -> List[Dict[str, Any]]:
        """
        Queries CDC Open Data catalog for datasets relevant to the query.
        Returns parsed evidence items, or [] if nothing useful found.
        """
        results: List[Dict[str, Any]] = []
        query_lower = query.lower()

        async with httpx.AsyncClient(timeout=cls.TIMEOUT_SEC) as client:
            # Use the SODA search endpoint to find relevant datasets
            search_url = "https://data.cdc.gov/api/views"
            params = {
                "$limit": 3,
                "$q": query,
                "$$app_token": "",  # public access, no token needed for basic queries
            }
            resp = await client.get(search_url, params=params)

            if resp.status_code != 200:
                logger.warning(f"[CDCAdapter] Open Data API returned HTTP {resp.status_code}")
                return results

            datasets = resp.json()
            if not isinstance(datasets, list):
                return results

            for ds in datasets[:3]:
                name = ds.get("name", "")
                desc = ds.get("description", "")
                permalink = ds.get("permalink") or (
                    f"https://data.cdc.gov/d/{ds.get('id', '')}"
                )

                if not name:
                    continue

                # Light relevance filter
                combined = (name + " " + desc).lower()
                if not any(
                    word in combined
                    for word in query_lower.split()
                    if len(word) > 3
                ):
                    continue

                text = f"CDC Open Data: {name}. {desc}"[:1000]

                results.append({
                    "evidence_id": str(uuid.uuid4()),
                    "source_name": "Centers for Disease Control and Prevention (CDC)",
                    "source_type": "official_public_health_reference",
                    "authority_tier": 1,
                    "title": name,
                    "url": permalink,
                    "publication_date": ds.get("publicationDate", ""),
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                    "text": text,
                    "relevance_score": 0.84,
                    "authority_score": 0.98,
                    "recency_score": 0.90,
                    "methodology_score": 0.92,
                    "traceability_score": 1.0,
                    "supports_claim": True,
                    "quality_label": "HIGH",
                })

        if results:
            logger.info(f"[CDCAdapter] Live API returned {len(results)} dataset(s).")
        return results

    @classmethod
    def _offline_fallback(cls, concepts: List[str], query: str) -> List[Dict[str, Any]]:
        """
        Returns curated CDC records matched to concepts.
        The 'general' record is only returned if no concept-specific match exists
        AND the query is epidemiological in nature.
        Does NOT auto-append unconditionally (previous bug).
        """
        results: List[Dict[str, Any]] = []
        matched = False

        if any("blood_pressure" in c for c in concepts):
            record = cls.CDC_RECORDS["blood_pressure"]
            results.append({
                "evidence_id": str(uuid.uuid4()),
                "source_name": "Centers for Disease Control and Prevention (CDC)",
                "source_type": "official_public_health_reference",
                "authority_tier": 1,
                "title": record["title"],
                "url": record["url"],
                "publication_date": record["date"],
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "text": record["text"],
                "relevance_score": 0.87,
                "authority_score": 0.98,
                "recency_score": 0.92,
                "methodology_score": 0.95,
                "traceability_score": 1.0,
                "supports_claim": True,
                "quality_label": "HIGH",
            })
            matched = True

        # Only append the generic CDC record if there is a real epidemiology need
        if not matched:
            epi_terms = {
                "epidemiology", "prevalence", "outbreak", "infectious",
                "transmission", "vaccine", "surveillance",
            }
            query_words = set(query.lower().split())
            concept_words = set(" ".join(concepts).lower().split())
            if epi_terms & (query_words | concept_words):
                record = cls.CDC_RECORDS["general"]
                results.append({
                    "evidence_id": str(uuid.uuid4()),
                    "source_name": "Centers for Disease Control and Prevention (CDC)",
                    "source_type": "official_public_health_reference",
                    "authority_tier": 1,
                    "title": record["title"],
                    "url": record["url"],
                    "publication_date": record["date"],
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                    "text": record["text"],
                    "relevance_score": 0.75,
                    "authority_score": 0.98,
                    "recency_score": 0.90,
                    "methodology_score": 0.92,
                    "traceability_score": 1.0,
                    "supports_claim": True,
                    "quality_label": "HIGH",
                })

        return results
