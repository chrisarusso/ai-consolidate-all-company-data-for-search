# Multi-Source Knowledge Base (Savas Unified Search)

**Status:** Planning
**Last Updated:** 2025-12-21

## Overview

Unified search interface across all Savas company data sources. Semantic search + conversational interface + automated triggers.

## AI Readiness Categories Coverage

- ✅ Search & Content Discoverability
- ✅ Data & Engineering
- ✅ Agents, Assistants & Automation
- ✅ Generative AI
- ✅ Personalization
- ✅ Privacy, Security & Compliance
- ✅ Product Strategy
- ⚠️ Training & Empowerment (add query best practices docs)

## Data Sources

### Priority Order
1. **Slack** - 700K+ messages - DONE via Secret Savas
2. **Fathom** - Meeting transcripts - NEXT (critical for alerts use case)
3. Google Drive - Proposals, task orders, contracts
4. Teamwork - Project management, tasks, messages
5. GitHub - Code, issues, PRs, documentation
6. Harvest - Time tracking, project context

### POC Scope
Slack + Fathom = proof of concept. Enough to demonstrate value across all 4 use cases.

## Use Cases

### UC1: Project Knowledge Search
- **Who:** Anyone at Savas (engineers, designers, PMs, sales)
- **Trigger:** Needs context on current/past project
- **Searches for:** Decisions made, approaches taken, technology used, tools, who worked on it
- **Sources:** Slack, Teamwork, Fathom transcripts, Google Drive docs
- **Note:** Serves multiple stakeholders with overlapping questions - POC focuses on good answers to natural questions

### UC2: Automated Risk/Opportunity Alerts
- **Who:** PMs get risk alerts, Sales gets opportunity alerts
- **Trigger:** Automated scan of new communications (transcripts, Teamwork messages)
- **Risk signals:** Client mentions budget concerns, schedule slippage, frustration
- **Opportunity signals:** Client asks about additional work, new capabilities, referrals
- **Output:** Post to Slack channel, tag @chris for MVP testing
- **Future:** Route to appropriate PM/account lead based on project

### UC3: Sales Call Prep
- **Who:** Sales team
- **Trigger:** Manual - run before call or RFP
- **Input:** Whatever prospect has provided (call transcript, email notes, HubSpot form, RFP document)
- **Output:** Most relevant past experience to highlight - similar projects, approaches, outcomes, who to involve
- **Sources:** All - system matches prospect context against our history
- **Note:** Load prospect context → get back our best matching experience

### UC4: Manager 1:1 Prep
- **Who:** Managers
- **Trigger:** Before scheduled 1:1 with direct report
- **Input:** Team member name
- **Output:** Recent project involvement, wins, blockers mentioned in standups/meetings, topics worth discussing
- **Sources:** Fathom transcripts, Teamwork tasks, Slack mentions

### Legacy (from initial planning)
- **Onboarding**: New employees search institutional knowledge
- **RFP responses**: Find relevant past work quickly

## Sample Queries (RIF as test client)

These queries validate UC1 - Project Knowledge Search:

1. "List me all the projects we've done for RIF"
2. "Who was involved in RIF work?"
3. "What were the biggest challenges on RIF projects?"
4. "What technologies did we use for RIF?"
5. "Who were the main stakeholders on the RIF team?"

Expected: System returns relevant Slack messages + Fathom transcript snippets with source links.

## Technical Architecture

### Data Ingestion

#### Slack
| Mode | Method | Notes |
|------|--------|-------|
| Historical | Slack Export + API backfill | Bulk load all channels |
| Ongoing | Slack Events API | Real-time via webhook |
| Ongoing (alt) | Periodic API poll | Simpler, slight delay |

#### Fathom
| Mode | Method | Notes |
|------|--------|-------|
| Historical | API fetch all past transcripts | One-time bulk load |
| Ongoing | Webhook on recording complete | Auto-process new calls |

#### Chunking Strategy
- **Slack**: Group by thread/conversation (not individual messages), include channel context
- **Fathom**: Split by speaker turns or 2-3 minute windows, preserve speaker labels
- **All sources**: Embed metadata in chunk (who, when, project/client if known)

### Storage Options

#### Vector Database Options

| Option | Type | Hosting | Pros | Cons | Cost |
|--------|------|---------|------|------|------|
| **pgvector** | Extension | Self-hosted or managed Postgres | Familiar SQL, single DB, good enough for millions | Manual scaling, requires Postgres expertise | Free (self) or ~$50/mo (managed) |
| **Pinecone** | Managed | Cloud only | Fast, scales automatically, good DX | Vendor lock-in, cloud only | Free tier, then ~$70/mo |
| **Weaviate** | Open source | Self-hosted or cloud | Hybrid search built-in, GraphQL | More complex setup | Free (self) or usage-based |
| **Qdrant** | Open source | Self-hosted or cloud | Rust-based (fast), good filtering | Newer, smaller community | Free (self) or ~$25/mo |
| **Chroma** | Open source | Self-hosted | Simple, Python-native, great for prototypes | Not production-hardened | Free |
| **Milvus** | Open source | Self-hosted or Zilliz cloud | Enterprise-grade, scales massively | Complex to operate | Free (self) or usage-based |
| **LanceDB** | Open source | Embedded (local) | Serverless, runs in-process, simple | Newer, less ecosystem | Free |
| **FAISS** | Library | Embedded | Facebook's battle-tested, very fast | No persistence built-in, just search | Free |
| **Supabase pgvector** | Managed | Cloud | Postgres + pgvector managed, auth built-in | Tied to Supabase ecosystem | Free tier, then ~$25/mo |

#### Embedding Model Options

| Model | Provider | Dimensions | Cost | Notes |
|-------|----------|------------|------|-------|
| text-embedding-ada-002 | OpenAI | 1536 | $0.0001/1K tokens | Proven, good quality |
| text-embedding-3-small | OpenAI | 512-1536 | $0.00002/1K tokens | Newer, 5x cheaper |
| text-embedding-3-large | OpenAI | 3072 | $0.00013/1K tokens | Highest quality |
| voyage-2 | Voyage AI | 1024 | $0.0001/1K tokens | Strong for retrieval |
| bge-large-en | Local (HuggingFace) | 1024 | Free (compute only) | Self-hosted option |
| all-MiniLM-L6-v2 | Local (Sentence Transformers) | 384 | Free (compute only) | Fast, lightweight |
| nomic-embed-text | Local (Ollama) | 768 | Free (compute only) | Good local option |

### Hosting Options

#### Local Development / Self-Hosted

```
┌─────────────────────────────────────────────────────────┐
│  Local Machine / On-Prem Server                         │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │ Ingestion   │  │ Vector DB   │  │ Query Service   │  │
│  │ Scripts     │→ │ (Chroma/    │← │ (FastAPI)       │  │
│  │ (Python)    │  │  LanceDB)   │  │                 │  │
│  └─────────────┘  └─────────────┘  └────────┬────────┘  │
│                                              │          │
│  ┌─────────────┐                   ┌────────▼────────┐  │
│  │ Local LLM   │←──────────────────│ Slack Bot /     │  │
│  │ (Ollama)    │                   │ Web UI          │  │
│  └─────────────┘                   └─────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

**Pros**: No cloud costs, data stays local, good for prototyping
**Cons**: Not accessible to team, manual management, no auto-scaling

#### Cloud Hosted

```
┌─────────────────────────────────────────────────────────────────┐
│  Cloud (AWS/GCP/Fly.io)                                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐     ┌──────────────┐     ┌────────────────┐   │
│  │ Slack Events │     │ Fathom       │     │ Scheduled      │   │
│  │ Webhook      │     │ Webhook      │     │ Ingestion      │   │
│  └──────┬───────┘     └──────┬───────┘     └───────┬────────┘   │
│         │                    │                     │            │
│         ▼                    ▼                     ▼            │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                   Ingestion Queue                        │    │
│  │                   (SQS / Redis / Simple Queue)           │    │
│  └─────────────────────────────┬───────────────────────────┘    │
│                                │                                │
│                                ▼                                │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                   Processing Worker                      │    │
│  │  • Chunk content                                         │    │
│  │  • Generate embeddings (OpenAI API)                      │    │
│  │  • Store in vector DB                                    │    │
│  │  • Run alert classification (UC2)                        │    │
│  └─────────────────────────────┬───────────────────────────┘    │
│                                │                                │
│         ┌──────────────────────┼──────────────────────┐         │
│         ▼                      ▼                      ▼         │
│  ┌─────────────┐       ┌─────────────┐       ┌─────────────┐    │
│  │ Vector DB   │       │ Metadata DB │       │ Slack API   │    │
│  │ (managed)   │       │ (Postgres)  │       │ (alerts)    │    │
│  └─────────────┘       └─────────────┘       └─────────────┘    │
│         ▲                      ▲                                │
│         │                      │                                │
│  ┌──────┴──────────────────────┴──────┐                         │
│  │          Query Service (FastAPI)   │                         │
│  └──────────────────┬─────────────────┘                         │
│                     │                                           │
│         ┌───────────┴───────────┐                               │
│         ▼                       ▼                               │
│  ┌─────────────┐         ┌─────────────┐                        │
│  │ Slack Bot   │         │ Web UI      │                        │
│  └─────────────┘         └─────────────┘                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Pros**: Team accessible, auto-scaling, webhooks work reliably
**Cons**: Ongoing costs, more infrastructure to manage

#### Hybrid (Recommended for POC)

- **Local**: Development, testing, data exploration
- **Cloud**: Production deployment for team access
- **Same codebase**: Docker-based, runs anywhere

### Search & Retrieval Pipeline

```
User Query
    │
    ▼
┌─────────────────────────┐
│ 1. Query Preprocessing  │  • Clean/normalize text
│                         │  • Extract entities (names, projects)
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ 2. Embed Query          │  • Same model as ingestion
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ 3. Hybrid Search        │  • Semantic: vector similarity (top 50)
│                         │  • Keyword: BM25/full-text (top 50)
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ 4. Merge & Rerank       │  • Reciprocal Rank Fusion
│                         │  • Optional: LLM reranker (Cohere, GPT)
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ 5. Generate Response    │  • LLM synthesizes answer from chunks
│                         │  • Cites sources with links
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ 6. Return to User       │  • Answer + source snippets + links
└─────────────────────────┘
```

### Alerts Pipeline (UC2)

```
New Fathom Transcript (webhook)
    │
    ▼
┌─────────────────────────────────────────┐
│ 1. Extract & Prepare                    │
│    • Parse transcript text              │
│    • Extract metadata (attendees, date) │
│    • Identify client/project if known   │
└───────────────────┬─────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│ 2. Signal Detection                     │
│    • Keyword scan (budget, timeline,    │
│      scope, additional work, referral)  │
│    • LLM classification for nuance      │
│    • Sentiment analysis on flagged      │
└───────────────────┬─────────────────────┘
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
   No signals              Signal detected
        │                       │
        ▼                       ▼
┌───────────────┐    ┌─────────────────────────────┐
│ Store only    │    │ 3. Post Alert to Slack      │
│ (for search)  │    │    • Channel: #alerts       │
└───────────────┘    │    • Tag: @chris            │
                     │    • Include:               │
                     │      - Signal type          │
                     │      - Relevant quote       │
                     │      - Meeting link         │
                     │      - Attendees            │
                     └─────────────────────────────┘
```

### Query Interfaces

#### Slack Bot
- Slash command: `/savas-search <query>`
- Or mention: `@SavasKB what technologies did we use for RIF?`
- Returns: Answer + top 3 source snippets with links
- Threads for follow-up questions

#### Web UI (Simple)
- Single search box
- Results show: synthesized answer + source cards
- Each source card: snippet, source type icon, timestamp, link
- Filter by: source type, date range, project/client
- For UC3: paste/upload prospect context, get matching experience

### Access Control
- Role-based results (sales sees client data, engineers see technical)
- Respect source permissions (private Slack channels stay private)
- Audit logging for sensitive queries

## Architecture Decision Rationale

This section explains why specific technical choices were made for the POC implementation.

### Project Structure: `src/` Layout with Separate Modules

**Decision:** Organized code into `src/savas_kb/` with subpackages for ingestion, storage, search, alerts, and api.

**Why:**
- **Separation of concerns** - Each module has a single responsibility. Ingestion knows how to load data, storage knows how to persist it, search knows how to query it. When you want to change how Slack data is loaded, you only touch `ingestion/slack_loader.py`.
- **Testability** - Isolated modules are easier to unit test. The alert detector can be tested without needing a real database or API keys.
- **Swappability** - The `storage/` module abstracts ChromaDB behind a `ChromaStore` class. If Pinecone becomes preferable later, create `pinecone_store.py` implementing the same interface, and nothing else changes.
- **`src/` layout** - This is the modern Python convention (PEP 517/518). It prevents accidental imports from the project root and makes the package installable.

### ChromaDB for Vector Storage

**Decision:** Used ChromaDB as the vector database for the POC.

**Why:**
- **Zero infrastructure** - ChromaDB runs embedded, storing data in a local directory. No Docker, no server process, no cloud account needed. Start building immediately.
- **Python-native** - It's a Python library, not a service. Fewer moving parts = fewer things to debug.
- **Good enough for POC scale** - For hundreds of thousands of chunks (which is what you'd have with 700K Slack messages grouped into threads), ChromaDB performs fine. It uses HNSW indexing which is fast for approximate nearest neighbor search.
- **Easy to swap later** - Wrapped in `ChromaStore` class with simple interface: `add_chunks()`, `search()`, `get_chunk()`. When you outgrow it, implement the same methods for Pinecone/Weaviate/pgvector.

**Tradeoffs accepted:**
- No built-in hybrid search (BM25 + semantic). Would need another library if keyword matching becomes important.
- Single-machine only. For team access, need to run the API on a server or switch to cloud-hosted solution.

### OpenAI Embeddings via API (Not Local)

**Decision:** Used OpenAI's `text-embedding-3-small` model via API rather than local embeddings.

**Why:**
- **Quality** - OpenAI's embeddings are among the best for retrieval tasks. Local models like `all-MiniLM-L6-v2` are good but not as accurate for nuanced semantic search.
- **Simplicity** - No GPU required, no model downloading, no managing inference. Just an API call.
- **Cost is low** - `text-embedding-3-small` costs $0.00002 per 1K tokens. For 700K Slack messages averaging 50 tokens each, that's 35M tokens = ~$0.70 total. Negligible.
- **Existing infrastructure** - OpenAI keys already in use for other Savas projects.

**Tradeoffs accepted:**
- Requires internet connection and API key
- Slight latency on each embedding call (mitigated by batching)
- Vendor dependency

**Why not local embeddings?**
- Setup friction (downloading models, managing CUDA/MPS)
- Lower quality for the use case (finding "decisions made" or "approaches taken" requires nuanced understanding)
- Cost minimization isn't the goal - getting value quickly is

### Chunking Strategy: Thread-Based for Slack, Speaker-Turn for Fathom

**Decision:** Group Slack messages by thread into single chunks. Split Fathom transcripts by speaker turns.

**Why this matters:**
- **Context preservation** - A single Slack message like "Yes, let's do that" is meaningless without the thread context. By grouping threads, the chunk becomes "Alice: Should we use React? Bob: Yes, let's do that" - now searchable and meaningful.
- **Retrieval quality** - If someone searches "What did we decide about React?", the chunk with the full thread discussion will rank higher than isolated messages.

**For Slack specifically:**
- Threads are natural conversation units
- Including channel name in the chunk (`[#engineering] Alice: ...`) adds context for filtering and understanding
- Max chunk size of 2000 chars prevents any single chunk from dominating

**For Fathom specifically:**
- Speaker turns preserve who said what - critical for alerts ("Client mentioned budget concerns")
- Meeting title is prepended to each chunk for context
- Overlap between chunks (optional) ensures context isn't lost at boundaries

**Tradeoffs:**
- Very long threads become truncated (2000 char limit)
- Some standalone messages get indexed individually (might lack context)

### Hybrid Search (Planned but Not Fully Implemented)

**What's in the architecture:** Semantic search + keyword matching with Reciprocal Rank Fusion.

**What's built:** Semantic search only (ChromaDB vector similarity).

**Why the gap:**
- **POC pragmatism** - Pure semantic search works well enough to validate the concept. Adding BM25 requires another library (like `rank_bm25`) and a merge step.
- **Easy to add later** - The `SearchEngine` class has a clear place to add keyword search. The architecture supports it.

**When hybrid becomes important:**
- Searching for exact project codes like "RIF-2024-01"
- Finding messages containing specific technical terms
- Queries where exact keyword match is more important than semantic meaning

### LLM for Response Generation (RAG Pattern)

**Decision:** Use GPT-4o-mini to synthesize answers from retrieved chunks, with source citations.

**Why:**
- **User experience** - Instead of returning raw chunks and making users read through them, the LLM synthesizes a coherent answer. "Here's what I found about RIF technologies: React, Drupal, and PostgreSQL were used [Source 1, 2]"
- **GPT-4o-mini specifically** - Fast, cheap ($0.15/1M input tokens), and capable enough for summarization. Full GPT-4 would be overkill and slow.
- **Temperature 0.3** - Low temperature keeps responses factual and grounded in the sources. Higher temperature would add creativity we don't want.
- **Source citations** - The prompt explicitly asks the LLM to cite sources. This builds trust and lets users verify.

**Prompt constraints:**
```
"Answer the question using ONLY the provided context"
"Cite your sources by referring to [Source N]"
"If the context doesn't contain enough information, say so honestly"
```

This constrains the LLM to be a faithful summarizer, not a creative writer.

### Alert Detection: Keyword Patterns + LLM Classification

**Decision:** Two-tier detection - fast keyword regex first, then optional LLM classification.

**Why two tiers:**
- **Keywords are fast and cheap** - Regex matching is instant and free. For obvious signals like "budget concern" or "behind schedule", no LLM needed.
- **LLM catches nuance** - "We might need to revisit the timeline" doesn't match "behind schedule" but an LLM understands it's a schedule risk.
- **Configurable** - `use_llm=False` for speed, `use_llm=True` for accuracy. Tune based on false positive/negative rates.

**Keyword pattern design:**
```python
r"\bbudget\b.*\b(concern|issue|problem|tight|over|exceed)"
```

These are regex patterns, not simple string matches. `\b` ensures word boundaries (so "budget" doesn't match "budgetary" accidentally). The `.*` allows words between.

**Tradeoffs:**
- Keyword patterns need tuning based on real data (some will be too aggressive, some will miss signals)
- LLM classification adds latency and cost (but only runs on flagged content)

### Slack Notifier with Rich Formatting

**Decision:** Post alerts as Slack Block Kit messages with headers, sections, and context.

**Why:**
- **Scannability** - Color-coded (red for risk, green for opportunity), emoji indicators, clear sections
- **Actionability** - Includes the relevant quote, meeting link, and attendees so you can act without digging
- **Tagging** - Tags @chris (configurable) so alerts don't get lost

**Dry-run mode:** If `SLACK_BOT_TOKEN` isn't set, it prints to console instead of posting. This enables development and testing without spamming Slack.

### CLI with Subcommands

**Decision:** Built a CLI using argparse with subcommands (`ingest`, `search`, `sales-prep`, `1on1`, `alerts`, `stats`, `clear`).

**Why:**
- **Developer-friendly** - While building and testing, you don't want to spin up a web server. CLI lets you quickly ingest data, run queries, check stats.
- **Scriptable** - Can be called from cron jobs, CI/CD, or other scripts
- **Self-documenting** - `savas-kb --help` shows all commands; each command has its own help

**Why argparse over Click/Typer:** Zero dependencies - argparse is stdlib. Good enough for this use case.

### FastAPI for the Web API

**Decision:** Used FastAPI with Pydantic models for request/response validation.

**Why FastAPI:**
- **Automatic OpenAPI docs** - Visit `/docs` and you get interactive API documentation for free
- **Pydantic integration** - Request bodies are validated automatically. If someone sends `{"query": 123}` instead of a string, they get a clear error.
- **Async-ready** - Although sync code is used for simplicity, FastAPI supports async handlers when needed
- **Fast** - It's in the name, and it matters for a search API

**CORS configuration:** `allow_origins=["http://localhost:3000", "http://localhost:5173"]` allows React frontend (Vite on 5173, or CRA on 3000) to call the API during development.

### Pydantic Models for All Data

**Decision:** Every data structure is a Pydantic BaseModel.

**Why:**
- **Validation** - When loading Slack exports, if a message is missing `ts`, Pydantic catches it immediately with a clear error
- **Serialization** - Converting to/from JSON, dict, API responses is automatic
- **Type hints** - IDE autocomplete works, and bugs are caught at write-time not runtime
- **Documentation** - Each field has a description, which shows up in API docs

### Configuration via Environment Variables

**Decision:** All configuration comes from `.env` file or environment variables, with sensible defaults.

**Why:**
- **12-factor app principle** - Config should be separate from code
- **Easy deployment switching** - Same code runs locally and in production; only the env vars change
- **Secret management** - API keys never go in code
- **Defaults where sensible** - `EMBEDDING_MODEL=text-embedding-3-small` is a reasonable default; only override if there's a reason

### Tests That Don't Require API Keys

**Decision:** Unit tests for models and keyword-based alert detection; no tests requiring OpenAI/Slack.

**Why:**
- **CI-friendly** - Tests can run in any environment without secrets
- **Fast** - No network calls = tests run in under a second
- **Focused** - Testing the logic, not the external services

**Not tested yet:** Integration tests with real embeddings, end-to-end tests with actual search. These would need fixtures or mocking, to be added as the codebase matures.

### Guiding Principles Summary

1. **Start simple, make it swappable** - ChromaDB is easy to start with; the abstraction layer lets you swap it later.
2. **Optimize for developer velocity** - CLI, local storage, no infrastructure = fast iteration.
3. **Use proven tools** - OpenAI embeddings, Pydantic, FastAPI are all battle-tested. No experimental libraries.
4. **Make the happy path obvious** - Copy `.env.example`, add key, ingest, search. Minimal steps to value.
5. **Leave room to grow** - The architecture supports adding more data sources, better search, more alert types without rewrites.

## MVP Scope

**POC: Slack + Fathom**
- Integrate Fathom transcripts into existing Secret Savas infrastructure. They must be automatically processed after a call ends for all accounts.
- Unified search across both sources
- Test with RIF sample queries
- Validate UC1 (knowledge search) works end-to-end

**Phase 1: Add Alerts**
- Implement UC2 risk/opportunity detection on new Fathom transcripts
- Post to Slack channel, tag @chris
- Define signal patterns (budget, schedule, opportunity keywords)

**Phase 2: Add Google Drive + Teamwork**
- Expand to proposals, contracts, PM data
- Role-based access control

**Phase 3: Polish**
- Web interface for search
- Conversational interface
- Add remaining sources (GitHub, Harvest)

## Success Metrics

- Time to find information: Reduce from 15min → 2min
- RFP response quality: Include 3+ relevant case studies consistently
- Knowledge retention: Reduce "I didn't know we did that" moments
- Onboarding time: Reduce from 4 weeks → 2 weeks

## Open Questions

- [x] What queries would sales team actually use? → Load prospect context, get matching experience (UC3)
- [ ] How to handle conflicting information across sources?
- [ ] What's the right UI/UX for busy team members?
- [ ] How does Fathom webhook/API work for auto-processing?
- [ ] What metadata does Fathom provide (attendees, meeting title, client tags)?

## Related Work

- Secret Savas: Proven RAG architecture, cost model
- Google Drive T&C organizer: Drive API integration
- RIF semantic search: Large-scale vectorization (21K resources)

## Next Steps

- [ ] Research Fathom API/webhook capabilities
- [ ] Set up local dev environment (Chroma or LanceDB for quick start)
- [ ] Ingest sample Slack export + sample Fathom transcripts
- [ ] Build basic search query → answer pipeline
- [ ] Test with RIF sample queries
- [ ] Add Slack bot integration
- [ ] Deploy to cloud for team access
