# Technical Architecture

## Data Ingestion

### Slack
| Mode | Method | Notes |
|------|--------|-------|
| Historical | Slack Export + API backfill | Bulk load all channels |
| Ongoing | Slack Events API | Real-time via webhook |
| Ongoing (alt) | Periodic API poll | Simpler, slight delay |

### Fathom
| Mode | Method | Notes |
|------|--------|-------|
| Historical | API fetch all past transcripts | One-time bulk load |
| Ongoing | Webhook on recording complete | Auto-process new calls |

### Chunking Strategy
- **Slack**: Group by thread/conversation (not individual messages), include channel context
- **Fathom**: Split by speaker turns or 2-3 minute windows, preserve speaker labels
- **All sources**: Embed metadata in chunk (who, when, project/client if known)

## Storage Options

### Vector Database Options

| Option | Type | Hosting | Pros | Cons | Cost |
|--------|------|---------|------|------|------|
| **pgvector** | Extension | Self-hosted or managed Postgres | Familiar SQL, single DB, good enough for millions | Manual scaling, requires Postgres expertise | Free (self) or ~$50/mo (managed) |
| **Pinecone** | Managed | Cloud only | Fast, scales automatically, good DX | Vendor lock-in, cloud only | Free tier, then ~$70/mo |
| **Chroma** | Open source | Self-hosted | Simple, Python-native, great for prototypes | Not production-hardened | Free |
| **Supabase pgvector** | Managed | Cloud | Postgres + pgvector managed, auth built-in | Tied to Supabase ecosystem | Free tier, then ~$25/mo |

### Embedding Model Options

| Model | Provider | Dimensions | Cost | Notes |
|-------|----------|------------|------|-------|
| text-embedding-3-small | OpenAI | 512-1536 | $0.00002/1K tokens | Current choice - cheap, good quality |
| text-embedding-3-large | OpenAI | 3072 | $0.00013/1K tokens | Highest quality |
| bge-large-en | Local | 1024 | Free (compute only) | Self-hosted option |

## Search & Retrieval Pipeline

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
│                         │  • Optional: LLM reranker
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

## Alerts Pipeline

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
│    • Keyword scan (budget, timeline)    │
│    • LLM classification for nuance      │
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
                     └─────────────────────────────┘
```

## Query Interfaces

### Slack Bot
- Slash command: `/savas-search <query>`
- Or mention: `@SavasKB what technologies did we use for RIF?`
- Returns: Answer + top 3 source snippets with links

### Web UI
- Single search box
- Results show: synthesized answer + source cards
- Filter by: source type, date range, project/client
