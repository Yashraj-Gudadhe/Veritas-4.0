import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np
from sentence_transformers import SentenceTransformer
import faiss
from app.config import settings
from app.utils.logger import logger
from app.retrieval.splitter import chunk_plain_text_with_provenance


class LocalVectorStore:
    """
    High-performance local vector store using semantic embeddings (all-MiniLM-L6-v2)
    and FAISS IndexFlatIP for cosine-similarity search.
    Operates 100% locally after first model download (~80MB), with FAISS index
    persisted to disk for instant subsequent startups.
    """

    _model: Optional[SentenceTransformer] = None
    EMBEDDING_DIM = 384
    # Words per chunk / overlap for legacy sliding-window chunker (kept for reference)
    CHUNK_SIZE_WORDS = 150
    CHUNK_OVERLAP_WORDS = 30

    @classmethod
    def get_model(cls) -> SentenceTransformer:
        if cls._model is None:
            cls._model = SentenceTransformer("all-MiniLM-L6-v2")
        return cls._model

    @staticmethod
    def _select_embedding_model(index_already_loaded: bool):
        """
        Returns the embedding callable to use for new index builds.

        Policy:
        - If GOOGLE_API_KEY is set in env AND langchain_google_genai is importable
          AND no existing index was loaded (to avoid dimension mismatch) →
          return ResilientGoogleEmbeddings (may use Gemini embedding-001, dim=3072).
        - Otherwise → use existing sentence-transformers (all-MiniLM-L6-v2, dim=384).
        """
        google_api_key = os.getenv("GOOGLE_API_KEY", "")
        if google_api_key and not index_already_loaded:
            try:
                from langchain_google_genai import GoogleGenerativeAIEmbeddings  # noqa: F401
                from app.retrieval.embeddings import ResilientGoogleEmbeddings
                logger.info("[VectorStore] Using ResilientGoogleEmbeddings (Gemini) for new index.")
                return ResilientGoogleEmbeddings(
                    model_name="models/gemini-embedding-001",
                    api_key=google_api_key,
                )
            except Exception as e:
                logger.info(f"[VectorStore] Google embeddings unavailable ({e}); using sentence-transformers.")
        return None  # signals caller to use get_model() (sentence-transformers)

    def __init__(self, persist_path: Optional[Path] = None):
        self.persist_dir = persist_path or Path(settings.CHROMA_PERSIST_DIRECTORY)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.persist_dir / "veritas_local_index.json"
        self.faiss_file = self.persist_dir / "veritas_faiss.index"

        self.faiss_index: Optional[faiss.Index] = None
        self.chunks: List[Dict[str, Any]] = []
        self._load_if_exists()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _sliding_window_chunks(
        self,
        text: str,
        title: str,
        url: str,
        source: str,
        auth_tier: int,
        pub_date: str,
        keywords: List[str],
        chunk_id_offset: int,
    ) -> List[Dict[str, Any]]:
        """
        Split *text* into overlapping word-window chunks.
        If the text is short enough (<=200 words) a single chunk is returned.
        """
        words = text.split()
        if len(words) <= 200:
            return [
                {
                    "chunk_id": f"CHK-{chunk_id_offset + 1:05d}",
                    "title": title,
                    "text": text,
                    "summary": text,
                    "url": url,
                    "source_name": source,
                    "authority_tier": auth_tier,
                    "publication_date": pub_date,
                    "keywords": keywords,
                }
            ]

        results: List[Dict[str, Any]] = []
        step = self.CHUNK_SIZE_WORDS - self.CHUNK_OVERLAP_WORDS
        for start in range(0, len(words), step):
            end = min(start + self.CHUNK_SIZE_WORDS, len(words))
            chunk_text = " ".join(words[start:end])
            results.append(
                {
                    "chunk_id": f"CHK-{chunk_id_offset + len(results) + 1:05d}",
                    "title": title,
                    "text": chunk_text,
                    "summary": chunk_text,
                    "url": url,
                    "source_name": source,
                    "authority_tier": auth_tier,
                    "publication_date": pub_date,
                    "keywords": keywords,
                }
            )
            if end == len(words):
                break
        return results

    def _build_faiss_index(self, texts: List[str], google_emb=None) -> faiss.Index:
        if google_emb is not None:
            # Google embeddings: dimension may differ from EMBEDDING_DIM
            raw = google_emb.embed_documents(texts)
            embeddings = np.array(raw, dtype=np.float32)
            dim = embeddings.shape[1]
        else:
            model = self.get_model()
            embeddings = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
            embeddings = embeddings.astype(np.float32)
            dim = self.EMBEDDING_DIM
        faiss.normalize_L2(embeddings)
        index = faiss.IndexFlatIP(dim)
        index.add(embeddings)
        return index

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def _load_if_exists(self) -> None:
        # Warm up the model so the first-run download happens at startup
        # Unless GOOGLE_API_KEY is set (which means we use lightweight API embeddings)
        try:
            if not os.getenv("GOOGLE_API_KEY"):
                self.get_model()
                logger.info("Semantic embedding model loaded: all-MiniLM-L6-v2")
            else:
                logger.info("GOOGLE_API_KEY found. Skipping local PyTorch model load to save memory.")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            return  # Fall back to empty index — online adapters will handle evidence

        if not self.index_file.exists():
            return

        try:
            with open(self.index_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.chunks = data.get("chunks", [])
            if not self.chunks:
                return

            if self.faiss_file.exists():
                self.faiss_index = faiss.read_index(str(self.faiss_file))
                logger.info(
                    f"Loaded existing FAISS index ({self.faiss_index.ntotal} vectors) "
                    f"and {len(self.chunks)} chunks from {self.persist_dir}"
                )
            else:
                # FAISS file missing — re-encode from stored chunks
                logger.info("FAISS index missing; re-encoding chunks from stored JSON...")
                texts = [c["text"] for c in self.chunks]
                self.faiss_index = self._build_faiss_index(texts)
                faiss.write_index(self.faiss_index, str(self.faiss_file))
                logger.info(f"Re-built and persisted FAISS index ({self.faiss_index.ntotal} vectors)")

        except Exception as e:
            logger.error(f"Error loading vector index: {str(e)}")

    def index_documents(self, documents: List[Dict[str, Any]]) -> int:
        """
        Ingest a list of documents/topics, apply provenance-aware chunking
        (via splitter.py's RecursiveCharacterTextSplitter), build a FAISS index,
        and persist both to disk.

        Each doc should have: title, summary/text, url, source, authority_tier,
        date_created, keywords, sections (optional).
        """
        # Decide embedding model: Google if available and no existing index loaded
        google_emb = self._select_embedding_model(
            index_already_loaded=(self.faiss_index is not None)
        )

        new_chunks: List[Dict[str, Any]] = []

        for doc in documents:
            title = doc.get("title", "")
            summary = doc.get("summary", "") or doc.get("text", "")
            url = doc.get("url", "")
            source = doc.get("source", "MedlinePlus")
            auth_tier = doc.get("authority_tier", 1)
            pub_date = doc.get("date_created", "2024-01-01")
            keywords = doc.get("keywords", [])

            full_text = f"{title}. {summary}"
            new_chunks.extend(
                chunk_plain_text_with_provenance(
                    full_text, title, url, source, auth_tier, pub_date, keywords,
                    chunk_id_offset=len(new_chunks),
                )
            )

            # Also chunk per-section content if available
            for sec in doc.get("sections", []):
                sec_title = sec.get("title", "")
                sec_text = sec.get("text", "")
                if sec_text:
                    combined = f"{title}: {sec_title}. {sec_text}"
                    new_chunks.extend(
                        chunk_plain_text_with_provenance(
                            combined,
                            f"{title} - {sec_title}",
                            url, source, auth_tier, pub_date, keywords,
                            chunk_id_offset=len(new_chunks),
                        )
                    )

        if not new_chunks:
            return 0

        self.chunks = new_chunks
        texts = [c["text"] for c in self.chunks]
        self.faiss_index = self._build_faiss_index(texts, google_emb=google_emb)

        # Persist chunks JSON
        try:
            with open(self.index_file, "w", encoding="utf-8") as f:
                json.dump({"chunks": self.chunks}, f, ensure_ascii=False, indent=2)
            logger.info(f"Persisted {len(self.chunks)} chunks to {self.index_file}")
        except Exception as e:
            logger.error(f"Error persisting chunk index: {str(e)}")

        # Persist FAISS index
        try:
            faiss.write_index(self.faiss_index, str(self.faiss_file))
            logger.info(f"Persisted FAISS index ({self.faiss_index.ntotal} vectors) to {self.faiss_file}")
        except Exception as e:
            logger.error(f"Error persisting FAISS index: {str(e)}")

        return len(self.chunks)

    def search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.15,
        obs_types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Semantic search over indexed chunks.

        Steps:
        1. Encode & normalise query embedding.
        2. FAISS inner-product search (= cosine similarity on normalised vectors).
        3. Domain-aware score boosting based on obs_types.
        4. Deduplicate by parent title (keep highest-scoring chunk per title).
        5. Filter by min_score and cap at top_k.

        Returns same dict format as the old TF-IDF implementation.
        """
        if not self.chunks or self.faiss_index is None:
            return []

        obs_types = obs_types or []

        try:
            if os.getenv("GOOGLE_API_KEY"):
                from app.retrieval.embeddings import ResilientGoogleEmbeddings
                google_emb = ResilientGoogleEmbeddings(
                    model_name="models/gemini-embedding-001",
                    api_key=os.getenv("GOOGLE_API_KEY")
                )
                raw_emb = google_emb.embed_query(query)
                query_vec = np.array(raw_emb, dtype=np.float32).reshape(1, -1)
            else:
                model = self.get_model()
                query_vec = model.encode([query], convert_to_numpy=True).astype(np.float32)

            faiss.normalize_L2(query_vec)

            # Retrieve more candidates than top_k to allow for post-filtering
            k = min(top_k * 4, self.faiss_index.ntotal)
            distances, indices = self.faiss_index.search(query_vec, k)
            distances = distances[0]
            indices = indices[0]

            # --- Domain-aware reranking ---
            boost_kidney = any(t in obs_types for t in ("egfr", "creatinine"))
            boost_diabetes = any(t in obs_types for t in ("glucose", "hba1c"))

            scored: List[Dict[str, Any]] = []
            for dist, idx in zip(distances, indices):
                if idx < 0:
                    continue
                score = float(dist)
                chunk = dict(self.chunks[idx])
                title_lower = chunk.get("title", "").lower()

                if boost_kidney and any(kw in title_lower for kw in ("kidney", "renal")):
                    score = min(score * 1.2, 1.0)
                if boost_diabetes and "diabetes" in title_lower:
                    score = min(score * 1.2, 1.0)

                chunk["relevance_score"] = round(score, 4)
                scored.append(chunk)

            # --- Deduplication by parent title (keep top score per title) ---
            seen_titles: Dict[str, float] = {}
            deduped: List[Dict[str, Any]] = []
            for chunk in scored:
                t = chunk.get("title", "")
                if t not in seen_titles or chunk["relevance_score"] > seen_titles[t]:
                    seen_titles[t] = chunk["relevance_score"]
                    deduped = [c for c in deduped if c.get("title") != t]
                    deduped.append(chunk)

            # Sort descending, apply min_score, cap at top_k
            deduped.sort(key=lambda c: c["relevance_score"], reverse=True)
            results = [c for c in deduped if c["relevance_score"] >= min_score][:top_k]
            return results

        except Exception as e:
            logger.error(f"Search error in vector store: {str(e)}")
            return []


# Singleton instance
vector_store = LocalVectorStore()
