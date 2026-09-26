"""
NCBI PubMed Adapter
Retrieves peer-reviewed biomedical literature from PubMed via NCBI E-utilities API.
https://www.ncbi.nlm.nih.gov/books/NBK25501/
"""
import uuid
import urllib.parse
from typing import List, Dict, Any
from datetime import datetime, timezone

import httpx

from app.utils.logger import logger
from app.utils.cache import cache


class NCBIAdapter:
    """
    National Center for Biotechnology Information (NCBI) PubMed Adapter.
    Queries NCBI E-utilities (ESearch + ESummary) for peer-reviewed biomedical literature.
    Uses v1 LocalCache with 72-hour TTL and SHA-256 keyed entries.
    """

    ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    MAX_RESULTS = 3
    TIMEOUT_SEC = 6.0

    async def fetch(self, query: str) -> List[Dict[str, Any]]:
        """
        Fetch PubMed evidence items for the given clinical query.

        Args:
            query: Full clinical query string (not just a single keyword).

        Returns:
            List of v1-format evidence dicts, or [] on failure/empty response.
        """
        clean_query = query.strip()
        if not clean_query:
            return []

        cache_key = {"source": "ncbi", "query": clean_query.lower()}
        cached = cache.get("online_sources", cache_key)
        if cached is not None:
            return cached

        results: List[Dict[str, Any]] = []

        try:
            encoded_query = urllib.parse.quote_plus(clean_query)
            search_url = (
                f"{self.ESEARCH_URL}?db=pubmed"
                f"&term={encoded_query}"
                f"&retmode=json"
                f"&retmax={self.MAX_RESULTS}"
                f"&sort=pub_date"
            )

            async with httpx.AsyncClient(timeout=self.TIMEOUT_SEC) as client:
                # Step 1: ESearch — get PubMed IDs
                search_resp = await client.get(search_url)
                if search_resp.status_code != 200:
                    logger.warning(f"[NCBI] ESearch returned HTTP {search_resp.status_code}")
                    cache.set("online_sources", cache_key, results)
                    return results

                search_data = search_resp.json()
                id_list: List[str] = search_data.get("esearchresult", {}).get("idlist", [])

                if not id_list:
                    logger.info("[NCBI] ESearch returned no results for query.")
                    cache.set("online_sources", cache_key, results)
                    return results

                # Step 2: ESummary — get article metadata
                ids_str = ",".join(id_list)
                sum_url = (
                    f"{self.ESUMMARY_URL}?db=pubmed"
                    f"&id={ids_str}"
                    f"&retmode=json"
                )
                sum_resp = await client.get(sum_url)
                if sum_resp.status_code != 200:
                    logger.warning(f"[NCBI] ESummary returned HTTP {sum_resp.status_code}")
                    cache.set("online_sources", cache_key, results)
                    return results

                sum_data = sum_resp.json().get("result", {})

                for pmid in id_list:
                    doc = sum_data.get(pmid, {})
                    if not doc:
                        continue

                    title = doc.get("title", f"PubMed Article PMID:{pmid}")
                    source_journal = doc.get("source", "PubMed Journal")
                    pubdate = doc.get("pubdate", "")
                    authors = [a.get("name", "") for a in doc.get("authors", [])][:3]
                    author_str = ", ".join(filter(None, authors))

                    text = (
                        f"Title: {title}. "
                        f"Journal: {source_journal} ({pubdate}). "
                        f"Authors: {author_str}."
                    )
                    doc_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

                    results.append({
                        "evidence_id": str(uuid.uuid4()),
                        "source_name": "NCBI PubMed",
                        "source_type": "peer_reviewed_literature",
                        "authority_tier": 2,
                        "title": title,
                        "url": doc_url,
                        "publication_date": pubdate,
                        "retrieved_at": datetime.now(timezone.utc).isoformat(),
                        "text": text,
                        "relevance_score": 0.90,
                        "authority_score": 0.90,
                        "recency_score": 0.80,
                        "methodology_score": 0.85,
                        "traceability_score": 1.0,
                        "supports_claim": True,
                        "quality_label": "HIGH",
                    })

        except Exception as e:
            logger.error(f"[NCBIAdapter] Network error: {e}")
            # Return empty — do NOT fabricate fallback content
            return []

        cache.set("online_sources", cache_key, results)
        return results
