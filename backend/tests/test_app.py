import hmac
import json
from hashlib import sha256

import anyio
from fastapi.testclient import TestClient

from app import main
from app.alerts import AlertsService
from app.models import AlertCandidate
from app.worker import process_job


def test_health_seeded():
    client = TestClient(main.app)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["documents"] >= 1


def test_fathom_webhook_signature_and_ingest():
    client = TestClient(main.app)
    payload = {
        "event_id": "evt_1",
        "event_type": "call.completed",
        "call_id": "call_123",
        "workspace_id": "ws_1",
        "title": "Test call",
        "transcript_url": "inline://" + json.dumps(
            {
                "call_id": "call_123",
                "segments": [
                    {"start_ms": 0, "end_ms": 1000, "speaker": "client", "text": "budget is tight"},
                    {"start_ms": 1000, "end_ms": 2000, "speaker": "pm", "text": "we can adjust scope"},
                ],
                "tags": ["rif"],
            }
        ),
    }
    body = json.dumps(payload).encode()
    sig = hmac.new(main.settings.fathom_webhook_secret.encode(), body, sha256).hexdigest()
    resp = client.post(
        "/webhooks/fathom/call-completed",
        data=body,
        headers={"X-Fathom-Signature": sig, "Content-Type": "application/json"},
    )
    assert resp.status_code == 200


def test_worker_creates_alerts():
    repo = main.InMemoryRepository()
    alerts = AlertsService()
    job = {
        "event_id": "evt_x",
        "call_id": "call_x",
        "transcript_url": "inline://" + json.dumps(
            {
                "call_id": "call_x",
                "segments": [
                    {"start_ms": 0, "end_ms": 1000, "speaker": "client", "text": "we may go over budget soon"},
                    {"start_ms": 1000, "end_ms": 2000, "speaker": "pm", "text": "phase two opportunity later"},
                ],
                "tags": ["rif"],
            }
        ),
    }

    async def run():
        alerts_out = await process_job(job, repo, alerts)
        return alerts_out

    alerts_out = anyio.run(run)
    assert any(a["alert_type"] == "budget_risk" for a in alerts_out)


def test_search_returns_results():
    # Use seeded data in main.repo
    results = main.perform_search(
        main.repo,
        main.SearchRequest(query="budget", limit=5),
    )
    assert len(results) >= 1

