# Multi-Source Knowledge Base (Savas Unified Search)

Unified search interface across all Savas company data sources.

**For current status and next steps, see [STATUS.md](STATUS.md)**

---

## Use Cases

### UC1: Project Knowledge Search
- **Who:** Anyone at Savas
- **Searches for:** Decisions made, approaches taken, technology used, who worked on it
- **Sources:** Slack, Teamwork, Fathom transcripts, Google Drive docs

### UC2: Automated Risk/Opportunity Alerts
- **Who:** PMs get risk alerts, Sales gets opportunity alerts
- **Trigger:** Automated scan of new Fathom transcripts
- **Risk signals:** Budget concerns, schedule slippage, frustration
- **Opportunity signals:** Additional work requests, referrals
- **Output:** Post to Slack, tag @chris

### UC3: Sales Call Prep
- **Who:** Sales team
- **Input:** Prospect context (transcript, email, RFP)
- **Output:** Most relevant past experience to highlight

### UC4: Manager 1:1 Prep
- **Who:** Managers
- **Input:** Team member name
- **Output:** Recent project involvement, wins, blockers, discussion topics

---

## Data Sources

| Source | Loader | Volume |
|--------|--------|--------|
| Slack | `SlackLoader` (export files) | ~1.29M messages |
| Fathom | `FathomLoader` (API) | 1,400+ meetings |
| GitHub | `GitHubLoader` (gh CLI) | All savaslabs repos |
| Google Drive | `DriveLoader` (OAuth) | Docs, Slides, Sheets |
| Teamwork | `TeamworkLoader` (API) | 43 projects + tasks |
| Harvest | `HarvestLoader` (API) | 663 projects, 216K time entries |
| Gmail | `GmailLoader` (OAuth) | TBD - analytics@savaslabs.com |

---

## MVP Scope

**Phase 1 (Current):** Dashboard + Raw Data
- SQLite storage for all sources
- Dashboard showing data counts
- Deployed to internal.savaslabs.com/knowledge-base/

**Phase 2:** Search
- Chunk and embed all sources into ChromaDB
- Add search UI to dashboard
- Validate with RIF sample queries

**Phase 3:** Alerts
- Risk/opportunity detection on Fathom transcripts
- Post to Slack when signals found

---

## Success Metrics

- Time to find information: 15min → 2min
- RFP response quality: Include 3+ relevant case studies
- Onboarding time: 4 weeks → 2 weeks

---

## Related Docs

- [STATUS.md](STATUS.md) - Current state, next steps
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - Technical architecture, pipelines
- [docs/DECISIONS.md](docs/DECISIONS.md) - Why we made specific choices
