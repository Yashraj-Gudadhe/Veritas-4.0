"""
NLM Clinical Tables / FHIR Adapter
Retrieves ICD-10-CM diagnosis codes and clinical terminology from NLM Clinical Tables API.
https://clinicaltables.nlm.nih.gov/fhir.html
"""
import uuid
import urllib.parse
from typing import List, Dict, Any
from datetime import datetime, timezone

import httpx

from app.utils.logger import logger
from app.utils.cache import cache


class NLMFHIRAdapter:
    """
    NLM Clinical Tables / FHIR Adapter.
    Queries the NLM ICD-10-CM endpoint for clinical terminology and diagnosis codes.
    Uses v1 LocalCache with 72-hour TTL and SHA-256 keyed entries.
    """

    ICD10_URL = "https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search"
    MAX_RESULTS = 3
    TIMEOUT_SEC = 5.0

    async def fetch(self, query: str) -> List[Dict[str, Any]]:
        """
        Fetch NLM ICD-10-CM evidence items for the given clinical query.

        Args:
            query: Full clinical query string (condition name, diagnosis description, etc.).

        Returns:
            List of v1-format evidence dicts, or [] on failure/empty response.
        """
        clean_query = query.strip()
        if not clean_query:
            return []

        cache_key = {"source": "nlm_fhir", "query": clean_query.lower()}
        cached = cache.get("online_sources", cache_key)
        if cached is not None:
            return cached

        results: List[Dict[str, Any]] = []

        try:
            encoded_query = urllib.parse.quote_plus(clean_query)
            url = f"{self.ICD10_URL}?terms={encoded_query}&maxList={self.MAX_RESULTS}"

            async with httpx.AsyncClient(timeout=self.TIMEOUT_SEC) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    logger.warning(
                        f"[NLMFHIRAdapter] API returned HTTP {resp.status_code}"
                    )
                    cache.set("online_sources", cache_key, results)
                    return results

                data = resp.json()
                # NLM response format: [total_count, [codes], extra_data_dict, [[code, description], ...]]
                if not (isinstance(data, list) and len(data) >= 4 and data[3]):
                    logger.info("[NLMFHIRAdapter] No ICD-10-CM results returned for query.")
                    cache.set("online_sources", cache_key, results)
                    return results

                rows = data[3]
                if not rows:
                    cache.set("online_sources", cache_key, results)
                    return results

                for row in rows[: self.MAX_RESULTS]:
                    if not isinstance(row, list) or len(row) < 2:
                        continue

                    code = str(row[0])
                    desc = str(row[1]) if len(row) > 1 else clean_query

                    text = (
                        f"ICD-10-CM Standard Clinical Classification:\n"
                        f"Code: {code}\n"
                        f"Description: {desc}\n"
                        f"Source: National Library of Medicine (NLM) Clinical Tables"
                    )
                    code_url = (
                        f"https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search"
                        f"?terms={urllib.parse.quote_plus(code)}"
                    )

                    results.append({
                        "evidence_id": str(uuid.uuid4()),
                        "source_name": "NLM Clinical Tables (ICD-10-CM)",
                        "source_type": "official_clinical_terminology",
                        "authority_tier": 1,
                        "title": f"ICD-10-CM: {code} — {desc}",
                        "url": code_url,
                        "publication_date": "2024-10-01",  # ICD-10-CM annual update
                        "retrieved_at": datetime.now(timezone.utc).isoformat(),
                        "text": text,
                        "relevance_score": 0.90,
                        "authority_score": 0.96,
                        "recency_score": 0.88,
                        "methodology_score": 0.92,
                        "traceability_score": 1.0,
                        "supports_claim": True,
                        "quality_label": "HIGH",
                    })

        except Exception as e:
            logger.error(f"[NLMFHIRAdapter] Network error: {e}")
            # Return empty — do NOT fabricate fallback content
            return []

        cache.set("online_sources", cache_key, results)
        return results
