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
