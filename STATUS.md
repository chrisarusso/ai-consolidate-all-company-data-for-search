# Knowledge Base - Current Status

**Last Updated:** 2025-12-27

## What's Live
- **Dashboard:** https://internal.savaslabs.com/knowledge-base/
- **Backend:** FastAPI on port 8004, systemd service `knowledge-base`
- **Server:** ubuntu@3.16.155.59 at `/home/ubuntu/knowledge-base`

## Data Summary
| Source | Storage | Records |
|--------|---------|---------|
| Slack | ChromaDB | 34.5K chunks (embedded) |
| Teamwork | SQLite | 294 projects, 4,830 tasks, 614 messages |
| Harvest | SQLite | 164 clients, 663 projects, 216K time entries |
| Fathom | SQLite | 2 transcripts |
| GitHub | SQLite | 451 issues/PRs |
| Drive | SQLite | 2 documents |

## Next Up: Gmail Integration
Via analytics@savaslabs.com mailbox.

**Steps:**
1. Delete `token.json` (needs Gmail scope added)
2. Create `gmail_loader.py` (model on `drive_loader.py`)
3. Add `g_emails` table to SQLite
4. Update ingest script, API stats, dashboard

## After Gmail
1. Chunk/embed all SQLite data → ChromaDB (enables search)
2. Add search UI to dashboard
3. Alerts pipeline (Fathom risk detection)

## Commands
```bash
# Local dev
cd frontend && npm run dev
uv run uvicorn savas_kb.api.app:app --port 8000

# Deploy
git push github master && ./deploy.sh
```
