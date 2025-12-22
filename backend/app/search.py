from typing import List

from .models import SearchRequest, SearchResult
from .repositories import InMemoryRepository
from .settings import settings


def perform_search(repo: InMemoryRepository, request: SearchRequest) -> List[SearchResult]:
    """
    Execute hybrid search with optional rerank flag.
    Rerank is stubbed (returns same order) but flag is kept for contract fidelity.
    """
    results = repo.search(
        request.query,
        request.filters,
        limit=request.limit,
        viewer_email=request.viewer_email,
    )
    if request.rerank and settings.rerank_enabled:
        # Placeholder for LLM/ML reranker; currently no-op.
        return results
    return results

