"""
Medical Text Splitter — provenance-preserving chunker for clinical documents.
Ported from Veritas-2.0 app/rag/splitter.py.
Replaces the sliding-window word-count chunker in vector_store.py for new ingestion.

Uses LangChain's RecursiveCharacterTextSplitter with medically-aware separators
and preserves full provenance metadata on every chunk.
"""
import uuid
import datetime
from typing import List, Dict, Any

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


def create_medical_text_splitter(
    chunk_size: int = 600,
    chunk_overlap: int = 100,
) -> RecursiveCharacterTextSplitter:
    """
    Creates a text splitter tuned for clinical notes, reports, and reference text.
    Separator order preserves paragraph > sentence > clause > word boundaries.
    """
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", "; ", ", ", " ", ""],
        keep_separator=True,
    )


def split_documents_with_provenance(
    docs: List[Document],
    chunk_size: int = 600,
    chunk_overlap: int = 100,
) -> List[Document]:
    """
    Splits LangChain Document objects while strictly retaining and enriching
    provenance metadata on every resulting chunk.

    Args:
        docs:         List of LangChain Document objects to split.
        chunk_size:   Target character count per chunk.
        chunk_overlap: Character overlap between consecutive chunks.

    Returns:
        List of chunked Documents with full provenance metadata on each.
    """
    splitter = create_medical_text_splitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    chunked_docs: List[Document] = []

    for doc_idx, doc in enumerate(docs):
        raw_text = doc.page_content.strip()
        if not raw_text:
            continue

        meta = dict(doc.metadata) if doc.metadata else {}
        sub_chunks = splitter.split_text(raw_text)

        for chunk_idx, chunk_text in enumerate(sub_chunks):
            chunk_id = (
                f"{meta.get('source_file', 'doc')}"
                f"_{meta.get('page', 1)}"
                f"_{doc_idx}_{chunk_idx}"
                f"_{uuid.uuid4().hex[:6]}"
            )

            chunk_metadata: Dict[str, Any] = {
                "source_type": meta.get("source_type", "uploaded_document"),
                "source_name": (
                    meta.get("source_name") or meta.get("source_file", "Unknown Source")
                ),
                "source_file": meta.get("source_file", "unknown_file"),
                "page": meta.get("page", 1),
                "chunk_id": chunk_id,
                "conversation_id": meta.get("conversation_id"),
                "speaker": meta.get("speaker"),
                "source_url": meta.get("source_url", ""),
                "title": meta.get("title", meta.get("source_name", "Medical Document")),
                "evidence_category": meta.get("evidence_category", "uploaded_document"),
                "retrieval_timestamp": meta.get(
                    "retrieval_timestamp",
                    datetime.datetime.now(datetime.timezone.utc).isoformat(),
                ),
            }

            chunked_docs.append(
                Document(page_content=chunk_text, metadata=chunk_metadata)
            )

    return chunked_docs


def chunk_plain_text_with_provenance(
    text: str,
    title: str,
    url: str,
    source_name: str,
    authority_tier: int,
    publication_date: str,
    keywords: List[str],
    chunk_id_offset: int = 0,
    chunk_size: int = 600,
    chunk_overlap: int = 100,
) -> List[Dict[str, Any]]:
    """
    Convenience wrapper: splits a plain string (not a LangChain Document) and
    returns v1-compatible chunk dicts (same schema as the old _sliding_window_chunks).

    This is the function called by vector_store.index_documents() to replace
    the old word-count sliding window chunker.
    """
    splitter = create_medical_text_splitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    if not text.strip():
        return []

    sub_chunks = splitter.split_text(text)
    results: List[Dict[str, Any]] = []

    for i, chunk_text in enumerate(sub_chunks):
        results.append({
            "chunk_id": f"CHK-{chunk_id_offset + i + 1:05d}",
            "title": title,
            "text": chunk_text,
            "summary": chunk_text,
            "url": url,
            "source_name": source_name,
            "authority_tier": authority_tier,
            "publication_date": publication_date,
            "keywords": keywords,
        })

    return results
