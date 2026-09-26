"""
ClinicalTrials.gov Adapter
Retrieves active and completed clinical studies from ClinicalTrials.gov API v2.
https://clinicaltrials.gov/data-api/api
"""
import uuid
import urllib.parse
from typing import List, Dict, Any
from datetime import datetime, timezone

import httpx

from app.utils.logger import logger
from app.utils.cache import cache


class ClinicalTrialsAdapter:
    """
    ClinicalTrials.gov API v2 Adapter.
    Queries for clinical studies relevant to the query.
    Uses v1 LocalCache with 72-hour TTL and SHA-256 keyed entries.
    """

    API_URL = "https://clinicaltrials.gov/api/v2/studies"
    MAX_RESULTS = 3
    TIMEOUT_SEC = 6.0

    async def fetch(self, query: str) -> List[Dict[str, Any]]:
        """
        Fetch clinical trial evidence items for the given query.

        Args:
            query: Full clinical query string.

        Returns:
            List of v1-format evidence dicts, or [] on failure/empty response.
        """
        clean_query = query.strip()
        if not clean_query:
            return []

        cache_key = {"source": "clinicaltrials", "query": clean_query.lower()}
        cached = cache.get("online_sources", cache_key)
        if cached is not None:
            return cached

        results: List[Dict[str, Any]] = []

        try:
            encoded_query = urllib.parse.quote_plus(clean_query)
            url = f"{self.API_URL}?query.term={encoded_query}&pageSize={self.MAX_RESULTS}"

            async with httpx.AsyncClient(timeout=self.TIMEOUT_SEC) as client:
                resp = await client.get(
                    url,
                    headers={
                        "Accept": "application/json",
                        "User-Agent": "Veritas-Evidence-Intelligence/1.0",
                    },
                )
                if resp.status_code != 200:
                    logger.warning(
                        f"[ClinicalTrialsAdapter] API returned HTTP {resp.status_code}"
                    )
                    cache.set("online_sources", cache_key, results)
                    return results

                data = resp.json()
                studies = data.get("studies", [])

                if not studies:
                    logger.info("[ClinicalTrialsAdapter] No studies returned for query.")
                    cache.set("online_sources", cache_key, results)
                    return results

                for study in studies[: self.MAX_RESULTS]:
                    protocol = study.get("protocolSection", {})

                    id_mod = protocol.get("identificationModule", {})
                    nct_id = id_mod.get("nctId", "NCT00000000")
                    brief_title = id_mod.get("briefTitle", "Clinical Trial Study")

                    status_mod = protocol.get("statusModule", {})
                    overall_status = status_mod.get("overallStatus", "UNKNOWN")
                    start_date = status_mod.get("startDateStruct", {}).get("date", "")
                    completion_date = status_mod.get(
                        "primaryCompletionDateStruct", {}
                    ).get("date", "")

                    desc_mod = protocol.get("descriptionModule", {})
                    summary = desc_mod.get("briefSummary", "").strip()

                    cond_mod = protocol.get("conditionsModule", {})
                    conditions = ", ".join(cond_mod.get("conditions", []))

                    # Build evidence text capped at 1200 chars
                    text = (
                        f"Study: {brief_title}\n"
                        f"NCT ID: {nct_id}\n"
                        f"Status: {overall_status}\n"
                        f"Conditions: {conditions}\n"
                        f"Summary: {summary}"
                    )[:1200]

                    study_url = f"https://clinicaltrials.gov/study/{nct_id}"
                    pub_date = completion_date or start_date or ""

                    results.append({
                        "evidence_id": str(uuid.uuid4()),
                        "source_name": "ClinicalTrials.gov",
                        "source_type": "clinical_trial",
                        "authority_tier": 2,
                        "title": f"{brief_title} ({nct_id})",
                        "url": study_url,
                        "publication_date": pub_date,
                        "retrieved_at": datetime.now(timezone.utc).isoformat(),
                        "text": text,
                        "relevance_score": 0.88,
                        "authority_score": 0.88,
                        "recency_score": 0.82,
                        "methodology_score": 0.90,
                        "traceability_score": 1.0,
                        "supports_claim": True,
                        "quality_label": "HIGH",
                    })

        except Exception as e:
            logger.error(f"[ClinicalTrialsAdapter] Network error: {e}")
            # Return empty — do NOT fabricate fallback content
            return []

        cache.set("online_sources", cache_key, results)
        return results
