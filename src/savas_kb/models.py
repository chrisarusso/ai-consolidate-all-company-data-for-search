"""
Data models for Savas Knowledge Base.

Defines the core data structures used throughout the system.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class SourceType(str, Enum):
    """Types of data sources."""
    SLACK = "slack"
    FATHOM = "fathom"
    DRIVE = "drive"
    TEAMWORK = "teamwork"
    GITHUB = "github"
    HARVEST = "harvest"


class SignalType(str, Enum):
    """Types of detected signals for alerts."""
    RISK_BUDGET = "risk_budget"
    RISK_SCHEDULE = "risk_schedule"
    RISK_SCOPE = "risk_scope"
    RISK_SENTIMENT = "risk_sentiment"
    OPPORTUNITY_ADDITIONAL_WORK = "opportunity_additional_work"
    OPPORTUNITY_REFERRAL = "opportunity_referral"
    OPPORTUNITY_EXPANSION = "opportunity_expansion"


class Chunk(BaseModel):
    """
    A chunk of content from a data source.

    Represents a searchable unit of text with metadata for context.
    """
    id: str = Field(..., description="Unique identifier for the chunk")
    content: str = Field(..., description="The text content of the chunk")
    source_type: SourceType = Field(..., description="Type of data source")
    source_id: str = Field(..., description="ID in the source system (channel_id, meeting_id, etc.)")
    source_url: Optional[str] = Field(None, description="Link back to the original content")

    # Metadata for filtering and context
    timestamp: datetime = Field(..., description="When the content was created")
    author: Optional[str] = Field(None, description="Who created the content")
    participants: list[str] = Field(default_factory=list, description="People involved")
    project: Optional[str] = Field(None, description="Associated project name")
    client: Optional[str] = Field(None, description="Associated client name")
    channel: Optional[str] = Field(None, description="Slack channel or meeting title")

    # For threading/context
    thread_id: Optional[str] = Field(None, description="Thread or conversation ID")
    parent_id: Optional[str] = Field(None, description="Parent message/chunk ID")


class SearchResult(BaseModel):
    """A single search result with relevance score."""
    chunk: Chunk
    score: float = Field(..., description="Relevance score (0-1)")
    highlights: list[str] = Field(default_factory=list, description="Relevant snippets")


class SearchResponse(BaseModel):
    """Response from a search query."""
    query: str
    answer: str = Field(..., description="Synthesized answer from the LLM")
    results: list[SearchResult] = Field(default_factory=list, description="Source chunks")
    sources_used: int = Field(0, description="Number of sources used in answer")


class Alert(BaseModel):
    """An alert generated from content analysis."""
    id: str
    signal_type: SignalType
    severity: str = Field(..., description="high, medium, or low")
    title: str
    summary: str
    quote: str = Field(..., description="Relevant quote from the content")
    source_chunk: Chunk
    detected_at: datetime = Field(default_factory=datetime.now)
    posted_to_slack: bool = False
    slack_message_ts: Optional[str] = None


class SlackMessage(BaseModel):
    """A Slack message from export or API."""
    ts: str
    user: str
    text: str
    channel: str
    channel_name: Optional[str] = None
    thread_ts: Optional[str] = None
    reply_count: int = 0
    reactions: list[dict] = Field(default_factory=list)


class FathomTranscript(BaseModel):
    """A Fathom meeting transcript."""
    id: str
    title: str
    date: datetime
    duration_seconds: int
    participants: list[str]
    transcript_text: str
    summary: Optional[str] = None
    action_items: list[str] = Field(default_factory=list)
    recording_url: Optional[str] = None
