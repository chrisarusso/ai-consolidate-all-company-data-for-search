import json
import logging
from datetime import datetime
from typing import Any, Dict

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBearer

from .alerts import AlertsService
from .models import Chunk, Document, FathomWebhookPayload, SearchRequest
from .queue import InMemoryQueue
from .repositories import InMemoryRepository, EmbeddingRecord
from .search import perform_search
from .security import verify_hmac_signature, verify_slack_signature
from .settings import settings
from .slack import format_results_blocks
from .worker import process_job
from .embedding import embed_text

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(title=settings.app_name)
auth_scheme = HTTPBearer(auto_error=False)

# Single-process demo components
queue = InMemoryQueue(settings.queue_name)
repo = InMemoryRepository()
alerts = AlertsService()


def seed_demo_data() -> None:
    if repo.documents:
        return
    doc = Document(
        id="slack:rif:1",
        source="slack",
        external_id="slack:rif:1",
        title="RIF kickoff",
        project="rif",
        workspace_id="savas",
        tags=["rif"],
        participants=[],
        started_at=datetime.utcnow(),
        ended_at=datetime.utcnow(),
    )
    chunk = Chunk(
        id="slack:rif:1:0",
        document_id=doc.id,
        idx=0,
        speaker="eng",
        start_ms=0,
        end_ms=0,
        text="Discussed RIF project scope and timelines; potential budget risk flagged.",
        token_count=14,
    )
    repo.upsert_document(doc, allowed_emails=None)
    repo.upsert_chunks([chunk])
    repo.upsert_embeddings(
        [
            EmbeddingRecord(
                id=f"{chunk.id}:emb",
                chunk_id=chunk.id,
                model="stub-embedding",
                vector=embed_text(chunk.text),
            )
        ]
    )


seed_demo_data()


def project_resolver(transcript) -> str | None:
    tags = [t.lower() for t in (transcript.tags or [])]
    if "rif" in tags:
        return "rif"
    return None


def acl_resolver(transcript) -> list[str] | None:
    emails = [p.email for p in transcript.participants if p.email]
    return emails or None


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "queue_depth": len(queue), "documents": len(repo.documents)}


@app.post("/webhooks/fathom/call-completed")
async def fathom_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict:
    raw_body = await request.body()
    signature = request.headers.get("X-Fathom-Signature") or ""
    if not verify_hmac_signature(raw_body, signature, settings.fathom_webhook_secret):
        raise HTTPException(status_code=401, detail="invalid signature")

    payload_dict = json.loads(raw_body.decode())
    payload = FathomWebhookPayload.model_validate(payload_dict)
    job = {
        "event_id": payload.event_id,
        "call_id": payload.call_id,
        "transcript_url": str(payload.transcript_url) if payload.transcript_url else "",
        "title": payload.title,
        "workspace_id": payload.workspace_id,
        "tags": payload.tags,
    }
    queue.enqueue(job)
    background_tasks.add_task(run_ingest_job, job)
    return {"queued": True}


async def run_ingest_job(job: Dict[str, Any]) -> None:
    try:
        await process_job(
            job,
            repo,
            alerts,
            project_resolver=project_resolver,
            acl_resolver=acl_resolver,
        )
    except Exception as exc:  # pragma: no cover - logged for visibility
        logger.exception("Failed to process job %s: %s", job, exc)


@app.post("/search")
async def search(request: SearchRequest) -> dict:
    results = perform_search(repo, request)
    return {"results": [r.model_dump() for r in results], "latency_ms": 0, "used_rerank": request.rerank}


@app.post("/slack/command")
async def slack_command(request: Request) -> JSONResponse:
    raw_body = await request.body()
    timestamp = request.headers.get("X-Slack-Request-Timestamp")
    signature = request.headers.get("X-Slack-Signature") or ""
    if not verify_slack_signature(timestamp, signature, raw_body, settings.slack_signing_secret):
        raise HTTPException(status_code=401, detail="invalid slack signature")
    form = await request.form()
    text = form.get("text", "")
    user_email = form.get("user_email") or form.get("user_name")
    search_req = SearchRequest(query=text, viewer_email=user_email, rerank=False)
    results = perform_search(repo, search_req)
    return JSONResponse(format_results_blocks(results))


@app.get("/ui", response_class=HTMLResponse)
async def ui() -> HTMLResponse:
    html = """
    <html>
        <body>
            <h2>Savas Unified Search (POC)</h2>
            <form id="f">
                <input type="text" name="query" placeholder="Search..." size="60" />
                <button type="submit">Search</button>
            </form>
            <pre id="out"></pre>
            <script>
                const form = document.getElementById('f');
                const out = document.getElementById('out');
                form.addEventListener('submit', async (e) => {
                    e.preventDefault();
                    const q = form.query.value;
                    const resp = await fetch('/search', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({query: q, limit: 5})
                    });
                    const data = await resp.json();
                    out.textContent = JSON.stringify(data, null, 2);
                });
            </script>
        </body>
    </html>
    """
    return HTMLResponse(content=html)

