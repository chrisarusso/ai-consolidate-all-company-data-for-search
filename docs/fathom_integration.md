# Fathom Integration Assumptions and Interface

This document captures the assumed shape of the Fathom webhook/API for meeting transcripts and how we will consume it. If Fathom API details differ, adjust field mappings and verification logic accordingly.

## Webhook Delivery
- **Endpoint**: `POST /webhooks/fathom/call-completed`
- **Auth**: HMAC signature header (e.g., `X-Fathom-Signature`) using a shared secret. Reject if missing/invalid. Include replay protection with timestamp tolerance.
- **Event trigger**: Fires when a call recording/transcript is finalized (post-processing complete).
- **Retry**: Assume exponential backoff. Endpoint must be idempotent. Deduplicate via `event_id`.

## Payload (expected fields)
- `event_id` (string, unique)
- `event_type` (e.g., `call.completed`)
- `call_id` (string)
- `workspace_id` (string)
- `started_at`, `ended_at` (ISO8601 UTC)
- `title` (string)
- `participants` (array of `{ name, email, role? }`)
- `primary_speaker` (optional string)
- `language` (string, e.g., `en`)
- `tags` (array of strings; may include client/project hints)
- `recording_url` (optional; signed)
- `transcript_url` (string; signed or requires API token)
- `summary` (optional short text)
- `confidence` (optional number)

## Transcript Fetch
- **Auth**: Token-based (bearer) or signed URL provided in webhook.
- **Format**: Assume JSON with per-utterance granularity:
  - `segments`: `{ start_ms, end_ms, speaker, text }[]`
  - Optional `topics`, `action_items`, `sentiment`, `chapters`.
- **Download**: Fetch once; cache in object storage with `call_id` path.

## Mapping to Internal Model
- **Source**: `fathom`
- **Document**: One per `call_id`.
  - `external_id = call_id`
  - `title`, `started_at`, `ended_at`, `workspace_id`, `tags`
  - `participants` → for ACL and enrichment
  - `project` inferred via tags/heuristics or manual mapping table
- **Chunks**: From `segments` grouped by time window or speaker turns.
  - Store `speaker`, `start_ms`, `end_ms`, `text`, `token_count`
- **Embeddings**: Generate from chunk text after cleaning/PII scrubbing.
- **Raw artifact**: Store full transcript JSON in object storage, referenced by `document`.

## Idempotency and Error Handling
- Deduplicate on `event_id` and `call_id`.
- If transcript fetch fails, enqueue retry with backoff; park in a dead-letter queue after N attempts.
- Log parse errors with payload snapshot (with PII guardrails).

## Security & Privacy
- Verify signatures and timestamps.
- Do not log raw transcript text; log hashes and lengths.
- PII scrubbing option before embedding (emails, phone numbers, names if required).
- Access control tags: participants’ emails map to user/org; workspace_id to tenant.

