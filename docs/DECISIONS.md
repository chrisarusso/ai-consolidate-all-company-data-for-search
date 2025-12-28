# Architecture Decisions

Why specific technical choices were made.

## ChromaDB for Vector Storage

**Decision:** Used ChromaDB as the vector database for the POC.

**Why:**
- **Zero infrastructure** - Runs embedded, storing data in a local directory
- **Python-native** - It's a library, not a service
- **Good enough for POC scale** - Uses HNSW indexing, fast for ~1M chunks
- **Easy to swap** - Wrapped in `ChromaStore` class with simple interface

**Tradeoffs:**
- No built-in hybrid search (BM25 + semantic)
- Single-machine only

## OpenAI Embeddings via API

**Decision:** Used `text-embedding-3-small` via API rather than local embeddings.

**Why:**
- **Quality** - Best for retrieval tasks
- **Simplicity** - No GPU, no model downloads
- **Cost is low** - $0.00002/1K tokens (~$0.70 for 700K messages)

## Thread-Based Chunking for Slack

**Decision:** Group Slack messages by thread into single chunks.

**Why:**
- Single message like "Yes, let's do that" is meaningless without context
- Thread grouping: "Alice: Should we use React? Bob: Yes, let's do that"
- Max 2000 chars per chunk

## LLM for Response Generation (RAG)

**Decision:** Use GPT-4o-mini to synthesize answers with citations.

**Why:**
- Better UX than raw chunks
- Fast, cheap ($0.15/1M input tokens)
- Temperature 0.3 keeps responses factual
- Prompt constrains to cite sources

## Two-Tier Alert Detection

**Decision:** Keyword regex first, then optional LLM classification.

**Why:**
- Keywords are instant and free for obvious signals
- LLM catches nuance ("revisit the timeline" → schedule risk)
- Configurable: `use_llm=False` for speed, `True` for accuracy

## FastAPI for Web API

**Why:**
- Automatic OpenAPI docs at `/docs`
- Pydantic validation built-in
- Async-ready

## Project Structure: `src/` Layout

**Why:**
- Separation of concerns (ingestion/storage/search/alerts/api)
- Testability - isolated modules
- Modern Python convention (PEP 517/518)

## Guiding Principles

1. **Start simple, make it swappable**
2. **Optimize for developer velocity**
3. **Use proven tools** (OpenAI, Pydantic, FastAPI)
4. **Make the happy path obvious**
5. **Leave room to grow**
