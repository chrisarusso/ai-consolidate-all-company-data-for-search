# UI Surfaces and Auth (POC)

Goal: deliver usable entry points quickly for POC while enforcing access controls. Start with Slack; add minimal web search page next.

## Surfaces
- **Slack Slash Command** (primary POC)
  - Command: `/savas-search`
  - Arguments: free text query; optional flags `source:`, `project:`, `time:`
  - Response: top 3–5 results with source, snippet, timestamp, and “open source” link.
  - Permissions: limited to allowed Slack workspace; map Slack user → email for ACL.
- **Web Search Page** (minimal)
  - Stack: Next.js static page calling search API.
  - Auth: Slack SSO (OIDC) or Google OAuth; issue short-lived JWT to call API.
  - Features: query box, filters (source, time, project), results list with provenance.
- **Admin/CLI (optional)**
  - Internal CLI for reindex/debug (protected by VPN or IAM).

## Auth & ACL
- Identity: Slack user ID → email; Web uses OAuth email.
- API receives `viewer_id` + `email`; enforces ACL via `acls`/`visibility`.
- Deny by default; if no ACL match, return empty results.
- Audit log: store query metadata (not full text if sensitive) with user identity.

## Slack Bot Implementation Notes
- Endpoint for `slash command -> API -> respond with blocks`.
- Verify Slack signing secret.
- Rate limiting: respect Slack 3s response window; otherwise send delayed response via `response_url`.
- Include “Open in search UI” deep link for full results.

## Web UX Minimal Scope
- One page with search bar, filters, and results list.
- Show source badges (Slack/Fathom), speaker + timestamp for Fathom, channel/thread for Slack.
- Link out to original source when possible.

## Phasing
- POC: ship slash command + API; no web UI required to validate RIF queries.
- Phase 2: add minimal web UI to support richer filtering and browsing history.

