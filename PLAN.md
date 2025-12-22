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
- **Incremental updates**: Process only new data since last run
- **Batching**: Cost optimization (90% savings proven in Secret Savas)
- **Pre-filtering**: Remove noise before embedding

### Storage
- PostgreSQL + pgvector (proven stack from Secret Savas)
- Embeddings: OpenAI ada-002 ($0.58 for 700K messages)
- Metadata enrichment: timestamps, source, author, access level

### Search & Retrieval
- Hybrid approach: Semantic search + keyword matching
- Reciprocal Rank Fusion for combining results
- Evidence linking: Always show source material

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

- [ ] Define 10 realistic search queries from sales team
- [ ] Design information architecture for multi-source results
- [ ] Prototype Google Drive integration
- [ ] Create demo data set for testing

## Rationale and Implementation Notes

Chosen stack and packaging
- Backend uses FastAPI + Pydantic to get typed request/response models, async handlers, and a mature test client. This mirrors existing Savas FastAPI use (see CLAUDE.md), keeps the mental model consistent, and speeds iteration for RAG-style backends.
- Dependencies are intentionally minimal in `pyproject.toml` (FastAPI, httpx, pydantic, uvicorn, pytest, anyio, python-multipart) to respect the “prefer minimal libraries” guidance. Editable install and a local virtualenv avoid macOS system Python constraints (PEP 668) while keeping the feedback loop fast.

Data/storage abstractions (why stubs now, swap later)
- In-memory repo and queue mirror the shapes we need for Postgres+pgvector and SQS/PubSub but avoid infra during early validation. They expose the same CRUD and search boundaries so swapping to real storage does not change the API layer.
- Stub embeddings are deterministic hash-based vectors: zero cost, deterministic tests, and no network calls. The interface is intentionally thin so we can drop in OpenAI embeddings later without touching callers.
- A single seeded Slack document/chunk is loaded at startup to make the POC return something immediately without external data. This is deliberate scaffolding, not production data.

Ingestion design
- Webhook-first ingestion for Fathom matches the requirement that transcripts must be processed automatically when a call completes. FastAPI’s `/webhooks/fathom/call-completed` validates a signature/bearer token (depending on how Fathom delivers auth) and immediately enqueues work to decouple ingestion latency.
- BackgroundTasks stand in for a real queue + worker (e.g., SQS + Fargate). The worker path (fetch, chunk, embed, persist, alert) is isolated so we can plug a real queue with minimal change.
- Chunking (`chunker.py`) groups by character budget while retaining speaker and timing. This preserves evidence for search snippets and supplies context for alerts (e.g., who said it, when).
- Inline `transcript_url` (`inline://...`) keeps local/offline testing simple while using the same code path that will handle signed URLs from Fathom.

Search and retrieval
- The target retrieval approach is hybrid (BM25 + vector + RRF) with an optional rerank layer; the current implementation is simplified but keeps the API contract (`/search`, filters, rerank flag) intact. That contract stability lets us upgrade the internals (pgvector + Postgres tsvector or OpenSearch) without breaking clients.
- ACL enforcement is threaded through the repository interface (viewer email, allowed principals per document) so access control will survive the swap to real storage.

Alerts
- Phase 1 uses explicit keyword rules (budget, schedule, satisfaction, opportunity) per `docs/alerts_rules.md`. This is intentional: cheap, deterministic, and inspectable, giving us fast signal with no model training. The scoring API returns structured alert objects so a later classifier can replace the rules without changing consumers.

Surfaces and auth
- Slack slash command is the primary UX in POC because it meets users where they work and requires no new UI. Signature verification follows Slack’s v0 spec. The handler passes viewer identity (email/user) to search to support ACLs.
- Minimal web UI (`/ui`) exists for manual demos and debugging without Slack setup. It is intentionally bare to minimize surface area until we add OAuth/SSO and richer filtering.

Testing and determinism
- Pytest suite covers health, webhook signature + ingest, alert generation, and search. Inline transcripts keep tests self-contained and deterministic (no network calls, no flaky embeddings).
- Deterministic stub embeddings ensure stable scores in tests and demos; once real embeddings are enabled, we can pin fixtures or snapshot responses to keep tests reliable.

Documentation footprint
- Dedicated docs (`docs/fathom_integration.md`, `ingestion_pipeline.md`, `search_api.md`, `alerts_rules.md`, `ui_surfaces.md`) keep rationale close to code and align with CLAUDE.md’s preference for consolidated, longer docs rather than scattered notes.
