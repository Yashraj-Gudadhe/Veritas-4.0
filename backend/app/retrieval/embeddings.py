"""
Resilient Google Embeddings — optional upgrade over sentence-transformers.
Ported from Veritas-2.0 app/rag/embeddings.py.

Used by vector_store.py conditionally:
  - If GOOGLE_API_KEY is set AND langchain_google_genai is importable → ResilientGoogleEmbeddings
  - Otherwise → existing sentence-transformers (all-MiniLM-L6-v2) is used as default

IMPORTANT: Switching to Google embeddings requires a full index rebuild because the
embedding dimension changes from 384 (sentence-transformers) to 3072 (Gemini).
vector_store.py only switches if no existing index is loaded.
"""
from typing import List

from langchain_core.embeddings import Embeddings


class ResilientGoogleEmbeddings(Embeddings):
    """
    Wrapper around GoogleGenerativeAIEmbeddings with automatic fallback to
    sentence-transformers (all-MiniLM-L6-v2) if the remote API errors out.

    Fallback model is the same one v1 uses by default, so results remain
    consistent with any already-indexed FAISS data.
    """

    def __init__(
        self,
        model_name: str = "models/gemini-embedding-001",
        api_key: str | None = None,
    ):
        self.primary = None
        self._fallback_model = None  # lazy-loaded sentence-transformers

        if api_key:
            try:
                from langchain_google_genai import GoogleGenerativeAIEmbeddings

                self.primary = GoogleGenerativeAIEmbeddings(
                    model=model_name,
                    google_api_key=api_key,
                )
            except Exception as e:
                print(f"[Embeddings Init Notice]: Could not initialise Google embeddings: {e}")

    def _get_fallback(self):
        """Lazy-load sentence-transformers fallback model."""
        if self._fallback_model is None:
            from sentence_transformers import SentenceTransformer

            self._fallback_model = SentenceTransformer("all-MiniLM-L6-v2")
        return self._fallback_model

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if self.primary:
            try:
                return self.primary.embed_documents(texts)
            except Exception as e:
                print(
                    f"[Embeddings Warning] Remote API failed ({e}), "
                    "falling back to sentence-transformers."
                )
        model = self._get_fallback()
        return model.encode(texts, show_progress_bar=False, convert_to_numpy=True).tolist()

    def embed_query(self, text: str) -> List[float]:
        if self.primary:
            try:
                return self.primary.embed_query(text)
            except Exception as e:
                print(
                    f"[Embeddings Warning] Remote API query failed ({e}), "
                    "falling back to sentence-transformers."
                )
        model = self._get_fallback()
        return model.encode([text], show_progress_bar=False, convert_to_numpy=True)[0].tolist()
