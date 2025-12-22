from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl


class Participant(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None


class FathomWebhookPayload(BaseModel):
    event_id: str
    event_type: str
    call_id: str
    workspace_id: str
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    title: Optional[str] = None
    participants: List[Participant] = Field(default_factory=list)
    language: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    recording_url: Optional[str] = None
    # Accept plain strings to allow inline:// dev payloads
    transcript_url: Optional[str] = None
    summary: Optional[str] = None
    confidence: Optional[float] = None


class TranscriptSegment(BaseModel):
    start_ms: int
    end_ms: int
    speaker: Optional[str] = None
    text: str


class Transcript(BaseModel):
    call_id: str
    title: Optional[str] = None
    workspace_id: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    tags: List[str] = Field(default_factory=list)
    participants: List[Participant] = Field(default_factory=list)
    segments: List[TranscriptSegment]


class Document(BaseModel):
    id: str
    source: str
    external_id: str
    title: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    workspace_id: Optional[str] = None
    project: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    participants: List[Participant] = Field(default_factory=list)


class Chunk(BaseModel):
    id: str
    document_id: str
    idx: int
    speaker: Optional[str] = None
    start_ms: Optional[int] = None
    end_ms: Optional[int] = None
    text: str
    token_count: int


class EmbeddingRecord(BaseModel):
    id: str
    chunk_id: str
    model: str
    vector: List[float]


class SearchFilters(BaseModel):
    source: Optional[List[str]] = None
    project: Optional[List[str]] = None
    time_range: Optional[dict] = None
    participants: Optional[List[str]] = None


class SearchRequest(BaseModel):
    query: str
    filters: Optional[SearchFilters] = None
    limit: int = 20
    rerank: bool = False
    viewer_email: Optional[str] = None


class SearchResult(BaseModel):
    id: str
    document_id: str
    source: str
    title: Optional[str] = None
    text: str
    score: float
    rank: int
    provenance: dict


class AlertCandidate(BaseModel):
    call_id: str
    document_id: str
    chunks: List[Chunk]
    title: Optional[str] = None
    project: Optional[str] = None
    workspace_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Alert(BaseModel):
    alert_type: str
    call_id: str
    title: Optional[str]
    project: Optional[str]
    workspace_id: Optional[str]
    chunks: List[dict]
    score: float
    created_at: datetime = Field(default_factory=datetime.utcnow)

