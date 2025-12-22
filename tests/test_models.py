"""Tests for data models."""

from datetime import datetime
import pytest

from savas_kb.models import (
    Chunk,
    SourceType,
    SignalType,
    Alert,
    SearchResult,
    SearchResponse,
    SlackMessage,
    FathomTranscript,
)


class TestChunk:
    """Tests for the Chunk model."""

    def test_create_minimal_chunk(self):
        """Test creating a chunk with minimal required fields."""
        chunk = Chunk(
            id="test123",
            content="This is test content",
            source_type=SourceType.SLACK,
            source_id="msg_123",
            timestamp=datetime.now(),
        )
        assert chunk.id == "test123"
        assert chunk.content == "This is test content"
        assert chunk.source_type == SourceType.SLACK

    def test_create_full_chunk(self):
        """Test creating a chunk with all fields."""
        chunk = Chunk(
            id="test456",
            content="Full content here",
            source_type=SourceType.FATHOM,
            source_id="meeting_456",
            source_url="https://fathom.video/123",
            timestamp=datetime(2024, 1, 15, 10, 0),
            author="Alice",
            participants=["Alice", "Bob", "Charlie"],
            project="RIF",
            client="Reading Is Fundamental",
            channel="Weekly Standup",
            thread_id="thread_1",
            parent_id="parent_1",
        )
        assert chunk.author == "Alice"
        assert len(chunk.participants) == 3
        assert chunk.project == "RIF"


class TestSourceType:
    """Tests for SourceType enum."""

    def test_all_source_types(self):
        """Verify all expected source types exist."""
        assert SourceType.SLACK.value == "slack"
        assert SourceType.FATHOM.value == "fathom"
        assert SourceType.DRIVE.value == "drive"
        assert SourceType.TEAMWORK.value == "teamwork"
        assert SourceType.GITHUB.value == "github"
        assert SourceType.HARVEST.value == "harvest"


class TestSignalType:
    """Tests for SignalType enum."""

    def test_risk_signals(self):
        """Verify risk signal types."""
        assert "risk" in SignalType.RISK_BUDGET.value
        assert "risk" in SignalType.RISK_SCHEDULE.value
        assert "risk" in SignalType.RISK_SCOPE.value

    def test_opportunity_signals(self):
        """Verify opportunity signal types."""
        assert "opportunity" in SignalType.OPPORTUNITY_ADDITIONAL_WORK.value
        assert "opportunity" in SignalType.OPPORTUNITY_REFERRAL.value


class TestSlackMessage:
    """Tests for SlackMessage model."""

    def test_create_message(self):
        """Test creating a Slack message."""
        msg = SlackMessage(
            ts="1234567890.123456",
            user="U12345",
            text="Hello world",
            channel="C12345",
            channel_name="general",
        )
        assert msg.ts == "1234567890.123456"
        assert msg.text == "Hello world"
        assert msg.reply_count == 0  # Default


class TestFathomTranscript:
    """Tests for FathomTranscript model."""

    def test_create_transcript(self):
        """Test creating a Fathom transcript."""
        transcript = FathomTranscript(
            id="meeting_123",
            title="Weekly Standup",
            date=datetime(2024, 1, 15, 10, 0),
            duration_seconds=1800,
            participants=["Alice", "Bob"],
            transcript_text="Alice: Hello\nBob: Hi there",
        )
        assert transcript.id == "meeting_123"
        assert transcript.duration_seconds == 1800
        assert len(transcript.participants) == 2


class TestSearchResult:
    """Tests for SearchResult model."""

    def test_create_result(self):
        """Test creating a search result."""
        chunk = Chunk(
            id="test",
            content="Test content",
            source_type=SourceType.SLACK,
            source_id="123",
            timestamp=datetime.now(),
        )
        result = SearchResult(chunk=chunk, score=0.95)
        assert result.score == 0.95
        assert result.chunk.id == "test"


class TestSearchResponse:
    """Tests for SearchResponse model."""

    def test_create_response(self):
        """Test creating a search response."""
        response = SearchResponse(
            query="test query",
            answer="This is the answer",
            sources_used=3,
        )
        assert response.query == "test query"
        assert response.answer == "This is the answer"
        assert response.sources_used == 3
