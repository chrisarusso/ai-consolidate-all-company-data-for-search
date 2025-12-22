import json
import logging
from typing import Any, Dict, List, Optional

import httpx

from .alerts import AlertsService
from .chunker import chunk_segments
from .embedding import embed_text
from .models import AlertCandidate, Document, EmbeddingRecord, Participant, Transcript, TranscriptSegment
from .repositories import InMemoryRepository

logger = logging.getLogger(__name__)


async def fetch_transcript(url: str) -> Dict[str, Any]:
    """
    Download transcript JSON from a signed URL or API endpoint.
    For demo, support inline JSON prefixed with 'inline://' to avoid network.
    """
    if url.startswith("inline://"):
        return json.loads(url.replace("inline://", "", 1))
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()


async def process_job(
    job: Dict[str, Any],
    repo: InMemoryRepository,
    alerts: AlertsService,
    *,
    project_resolver=None,
    acl_resolver=None,
) -> List[Dict[str, Any]]:
    """
    Process a single ingest job: fetch transcript, chunk, embed, persist, emit alerts.
    Returns list of alert dicts emitted for observability.
    """
    transcript_payload = job.get("transcript") or await fetch_transcript(job["transcript_url"])
    transcript = _parse_transcript(job, transcript_payload)
    project = project_resolver(transcript) if project_resolver else None
    allowed_emails = acl_resolver(transcript) if acl_resolver else None

    doc = Document(
        id=f"fathom:{transcript.call_id}",
        source="fathom",
        external_id=transcript.call_id,
        title=transcript.title,
        started_at=transcript.started_at,
        ended_at=transcript.ended_at,
        workspace_id=transcript.workspace_id,
        project=project,
        tags=transcript.tags,
        participants=transcript.participants,
    )
    repo.upsert_document(doc, allowed_emails)

    chunks = chunk_segments(transcript.segments, doc.id)
    repo.upsert_chunks(chunks)

    embeds = [
        EmbeddingRecord(
            id=f"{chunk.id}:emb",
            chunk_id=chunk.id,
            model="stub-embedding",
            vector=embed_text(chunk.text),
        )
        for chunk in chunks
    ]
    repo.upsert_embeddings(embeds)

    candidate = AlertCandidate(
        call_id=transcript.call_id,
        document_id=doc.id,
        title=doc.title,
        project=doc.project,
        workspace_id=doc.workspace_id,
        chunks=chunks,
    )
    alert_objs = alerts.score(candidate)
    alerts_emitted = [a.model_dump() for a in alert_objs]
    if alerts_emitted:
        logger.info("Alerts emitted: %s", alerts_emitted)
    return alerts_emitted


def _parse_transcript(job: Dict[str, Any], payload: Dict[str, Any]) -> Transcript:
    segments_raw = payload.get("segments") or []
    segments = [
        TranscriptSegment(
            start_ms=int(seg.get("start_ms") or 0),
            end_ms=int(seg.get("end_ms") or 0),
            speaker=seg.get("speaker"),
            text=seg.get("text") or "",
        )
        for seg in segments_raw
    ]
    participants = [
        Participant(name=p.get("name"), email=p.get("email"), role=p.get("role"))
        for p in payload.get("participants", [])
    ]
    return Transcript(
        call_id=payload.get("call_id") or job["call_id"],
        title=payload.get("title") or job.get("title"),
        workspace_id=payload.get("workspace_id") or job.get("workspace_id"),
        started_at=payload.get("started_at"),
        ended_at=payload.get("ended_at"),
        tags=payload.get("tags", []) or job.get("tags", []),
        participants=participants,
        segments=segments,
    )

