from __future__ import annotations

import math
from collections import defaultdict
from typing import Dict, List, Optional, Sequence

from .embedding import embed_text
from .models import Chunk, Document, EmbeddingRecord, SearchFilters, SearchResult


class InMemoryRepository:
    """
    In-memory stand-in for Postgres + pgvector.
    Stores documents, chunks, and embeddings; supports basic hybrid search.
    """

    def __init__(self):
        self.documents: Dict[str, Document] = {}
        self.chunks: Dict[str, Chunk] = {}
        self.embeddings: Dict[str, EmbeddingRecord] = {}
        self.chunks_by_doc: Dict[str, List[str]] = defaultdict(list)
        self.acls: Dict[str, List[str]] = {}  # document_id -> list of allowed emails (placeholder)

    def upsert_document(self, doc: Document, allowed_emails: Optional[List[str]] = None) -> None:
        self.documents[doc.id] = doc
        if allowed_emails is not None:
            self.acls[doc.id] = allowed_emails

    def upsert_chunks(self, chunks: Sequence[Chunk]) -> None:
        for chunk in chunks:
            self.chunks[chunk.id] = chunk
            if chunk.document_id not in self.chunks_by_doc:
                self.chunks_by_doc[chunk.document_id] = []
            if chunk.id not in self.chunks_by_doc[chunk.document_id]:
                self.chunks_by_doc[chunk.document_id].append(chunk.id)

    def upsert_embeddings(self, embeds: Sequence[EmbeddingRecord]) -> None:
        for emb in embeds:
            self.embeddings[emb.id] = emb

    def search(
        self,
        query: str,
        filters: Optional[SearchFilters],
        limit: int,
        viewer_email: Optional[str] = None,
    ) -> List[SearchResult]:
        lexical_scores = self._lexical_scores(query, filters, viewer_email)
        vector_scores = self._vector_scores(query, filters, viewer_email)

        combined: Dict[str, float] = defaultdict(float)
        for chunk_id, score in lexical_scores.items():
            combined[chunk_id] += score
        for chunk_id, score in vector_scores.items():
            combined[chunk_id] += score

        ranked = sorted(combined.items(), key=lambda kv: kv[1], reverse=True)[:limit]
        results: List[SearchResult] = []
        for rank, (chunk_id, score) in enumerate(ranked, start=1):
            chunk = self.chunks[chunk_id]
            doc = self.documents[chunk.document_id]
            results.append(
                SearchResult(
                    id=chunk.id,
                    document_id=doc.id,
                    source=doc.source,
                    title=doc.title,
                    text=chunk.text,
                    score=score,
                    rank=rank,
                    provenance={
                        "start_ms": chunk.start_ms,
                        "end_ms": chunk.end_ms,
                        "speaker": chunk.speaker,
                        "workspace_id": doc.workspace_id,
                        "project": doc.project,
                    },
                )
            )
        return results

    def _lexical_scores(
        self, query: str, filters: Optional[SearchFilters], viewer_email: Optional[str]
    ) -> Dict[str, float]:
        tokens = [t.lower() for t in query.split() if t.strip()]
        scores: Dict[str, float] = {}
        for chunk in self._iter_chunks(filters, viewer_email):
            text_l = chunk.text.lower()
            score = sum(text_l.count(tok) for tok in tokens)
            if score:
                scores[chunk.id] = float(score)
        return scores

    def _vector_scores(
        self, query: str, filters: Optional[SearchFilters], viewer_email: Optional[str]
    ) -> Dict[str, float]:
        query_vec = embed_text(query)
        scores: Dict[str, float] = {}
        for chunk in self._iter_chunks(filters, viewer_email):
            emb = self.embeddings.get(f"{chunk.id}:emb")
            if not emb:
                continue
            score = dot(query_vec, emb.vector)
            if score > 0:
                scores[chunk.id] = float(score)
        return scores

    def _iter_chunks(
        self, filters: Optional[SearchFilters], viewer_email: Optional[str]
    ) -> List[Chunk]:
        results: List[Chunk] = []
        for chunk_id, chunk in self.chunks.items():
            doc = self.documents.get(chunk.document_id)
            if not doc:
                continue
            if viewer_email and not self._is_allowed(doc.id, viewer_email):
                continue
            if filters:
                if filters.source and doc.source not in filters.source:
                    continue
                if filters.project and doc.project not in filters.project:
                    continue
            results.append(chunk)
        return results

    def _is_allowed(self, document_id: str, email: str) -> bool:
        allowed = self.acls.get(document_id)
        if allowed is None:
            return True  # default allow if not configured
        return email.lower() in {a.lower() for a in allowed}


def dot(a: List[float], b: List[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def l2(vec: List[float]) -> float:
    return math.sqrt(sum(v * v for v in vec)) or 1.0

