# Risk/Opportunity Alerts (Fathom)

Goal: detect risk/opportunity signals on new Fathom transcripts and post to Slack for MVP testing (@chris). Start with rules/keywords; evolve to classifier later.

## Trigger
- Event: new Fathom call ingested; worker emits alert event per chunk or per call.
- Scope: only new data; dedupe per `call_id` + rule type within 24h.

## Rules (initial keyword/phrase lists)
- **Budget risk**: `budget`, `over budget`, `too expensive`, `cost overrun`, `scope creep`, `out of scope`, `change order`, `cannot afford`
- **Schedule risk**: `slipping`, `behind schedule`, `delay`, `deadline`, `blocked`, `pushed back`, `need more time`, `not ready`
- **Satisfaction risk**: `frustrated`, `unhappy`, `concerned`, `not working`, `quality issue`, `rework`
- **Opportunity**: `can you also`, `additional work`, `phase two`, `expansion`, `maintenance`, `support retainer`, `new project`, `integration`, `referral`

Tunable with stemming/lemmatization; can add simple sentiment threshold.

## Scoring
- Count keyword hits per chunk; boost by speaker role (e.g., client > internal).
- Aggregate per call: `score = max(chunk_score)`; threshold per rule type.
- Keep top N chunks for context in Slack alert.

## Alert Payload
```json
{
  "alert_type": "budget_risk",
  "call_id": "call_abc",
  "title": "RIF weekly sync",
  "score": 0.82,
  "project": "rif",
  "workspace_id": "ws_1",
  "chunks": [
    {
      "text": "client mentioned budget is tight and scope creep risk",
      "speaker": "Client PM",
      "start_ms": 120000,
      "url": "https://fathom.link/call#t=120"
    }
  ],
  "created_at": "2025-12-21T00:00:00Z"
}
```

## Slack Delivery
- Use bot token; post to channel (e.g., `#alerts-risk-oppty`) and tag `@chris`.
- Message template includes:
  - Alert type + score badge
  - Call title, time, participants (client vs internal)
  - Top 1–2 snippets with timestamps/links
  - CTA: “Mark as reviewed” link (future)

## Processing Path
1) Ingest worker emits alert candidate events into `alerts` queue after embedding/chunking.
2) Alert worker evaluates rules, scores, dedupes, stores to `alerts` table, and posts to Slack.
3) Record delivery status and errors; retries with backoff on Slack failures.

## Data Model Additions
- `alerts(id, call_id, chunk_id, alert_type, score, status, created_at, delivered_at, delivery_error)`
- Index on `(call_id, alert_type, created_at)` for dedupe.

## Future Improvements
- Replace keyword rules with lightweight classifier (few-shot or fine-tuned) leveraging embeddings.
- Personalize routing by project/owner; tag correct PM/AE instead of `@chris`.
- Add web dashboard for alert triage and feedback to improve model.

