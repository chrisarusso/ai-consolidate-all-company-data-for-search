# Search API and Retrieval Stack

Goal: unified search across Slack + Fathom (POC), extensible to Drive/Teamwork. Hybrid retrieval with BM25 + vector + RRF, optional rerank.

## Stack
- API service: FastAPI or Express/Node.
- Retrieval: Postgres+pgvector for vectors; BM25 via SQL `tsvector` or external (OpenSearch) if needed.
- Embeddings: `text-embedding-3-small` by default; configurable per source/model.
- Rerank: optional OpenAI or Cohere on top-50.

## Endpoints (REST)
- `POST /search`
  - body: `{ "query": "...", "filters": { "source": ["slack","fathom"], "project": ["rif"], "time_range": { "from": "...", "to": "..." }, "participants": ["alice@savas.com"] }, "limit": 20, "rerank": true }`
  - response: results with source snippets, scores, and provenance.
- `GET /health`
- `GET /metrics` (if exposing Prometheus)
- Admin (optional, protected):
  - `POST /reindex` for a document
  - `GET /documents/:id`

## Response Shape
```json
{
  "results": [
    {
      "id": "chunk_id",
      "document_id": "doc_id",
      "source": "fathom",
      "title": "RIF weekly sync",
      "text": "client raised concern about budget...",
      "score": 0.71,
      "rank": 1,
      "provenance": {
        "start_ms": 120000,
        "end_ms": 150000,
        "speaker": "PM",
        "url": "https://fathom.link/call#t=120",
        "workspace_id": "ws_1",
        "project": "rif"
      }
    }
  ],
  "used_rerank": true,
  "latency_ms": 180
}
```

## Query Flow
1) Normalize query; build lexical query (tsvector/BM25) and embedding vector.
2) Retrieve top-K lexical (e.g., 100) and top-K vector (e.g., 100).
3) Combine via RRF; truncate to 50; optional rerank to N (20) with LLM reranker.
4) Apply ACL filters in SQL and at merge step.
5) Return scored results with source links and timing.

## Filters and ACL
- Filters: source, project, workspace, time_range, participants, tags.
- ACL: join against `acls` and `documents.visibility`; deny by default.
- Support `viewer_id` in request header/body to filter principals.

## Performance Targets
- P50 < 400ms, P95 < 1.2s for K=100/100 and rerank on 20.
- Cold start minimized via warm pool or provisioned concurrency (if serverless).

## Pagination
- Use `limit` + `cursor` (opaque) for deep paging; default `limit=20`, max 50.

## Telemetry
- Log query, filters, counts, latency, rerank flag, and trace id (no raw query text in logs if sensitive).
- Expose Prometheus metrics: `search_latency_ms`, `bm25_hits`, `vector_hits`, `rerank_usage`.

## Error Handling
- 400 on invalid filters; 401/403 on auth; 429 on rate limit; 500 on internal error.
- Gracefully degrade: if reranker fails, return combined results; if vector search unavailable, fall back to BM25.

