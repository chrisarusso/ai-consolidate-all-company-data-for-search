"""
Fathom transcript loader.

Handles loading meeting transcripts from Fathom API
and converting them into chunks for the vector store.
"""

import json
import re
import requests
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional
from pydantic import BaseModel, Field

from ..config import FATHOM_DIR, FATHOM_API_KEY
from ..models import Chunk, FathomTranscript, SourceType
from ..storage.chroma_store import generate_chunk_id


class FathomMeeting(BaseModel):
    """A Fathom meeting from the API."""
    recording_id: int
    title: str
    url: str
    share_url: Optional[str] = None
    created_at: datetime
    recording_start_time: Optional[datetime] = None
    recording_end_time: Optional[datetime] = None
    calendar_invitees_domains_type: Optional[str] = None
    recorded_by: Optional[dict] = None
    calendar_invitees: list[dict] = Field(default_factory=list)


class FathomLoader:
    """
    Load and process Fathom meeting transcripts.

    Supports loading from:
    - Fathom API (primary)
    - JSON export files (fallback)
    """

    BASE_URL = "https://api.fathom.ai/external/v1"

    def __init__(
        self,
        api_key: Optional[str] = None,
        data_dir: Optional[Path] = None,
    ):
        """
        Initialize the Fathom loader.

        Args:
            api_key: Fathom API key.
            data_dir: Path to Fathom data directory for caching.
        """
        self.api_key = api_key or FATHOM_API_KEY
        self.data_dir = data_dir or FATHOM_DIR
        self.headers = {"X-Api-Key": self.api_key} if self.api_key else {}

    def _request(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """Make an authenticated request to Fathom API."""
        if not self.api_key:
            raise ValueError("Fathom API key required. Set FATHOM_API_KEY env var.")

        url = f"{self.BASE_URL}/{endpoint}"
        response = requests.get(url, headers=self.headers, params=params or {})
        response.raise_for_status()
        return response.json()

    def _parse_datetime(self, value: Optional[str]) -> Optional[datetime]:
        """Parse ISO datetime string."""
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None

    def list_meetings(
        self,
        limit: int = 100,
        cursor: Optional[str] = None,
    ) -> tuple[list[FathomMeeting], Optional[str]]:
        """
        List meetings from the API.

        Args:
            limit: Maximum meetings to return per page.
            cursor: Pagination cursor for next page.

        Returns:
            Tuple of (meetings list, next cursor or None).
        """
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor

        response = self._request("meetings", params)

        meetings = []
        for item in response.get("items", []):
            meetings.append(FathomMeeting(
                recording_id=item["recording_id"],
                title=item.get("title") or item.get("meeting_title", "Untitled"),
                url=item.get("url", ""),
                share_url=item.get("share_url"),
                created_at=self._parse_datetime(item["created_at"]) or datetime.now(),
                recording_start_time=self._parse_datetime(item.get("recording_start_time")),
                recording_end_time=self._parse_datetime(item.get("recording_end_time")),
                calendar_invitees_domains_type=item.get("calendar_invitees_domains_type"),
                recorded_by=item.get("recorded_by"),
                calendar_invitees=item.get("calendar_invitees", []),
            ))

        return meetings, response.get("next_cursor")

    def list_all_meetings(
        self,
        since: Optional[datetime] = None,
        max_meetings: int = 1000,
    ) -> Iterator[FathomMeeting]:
        """
        List all meetings, paginating through results.

        Args:
            since: Only return meetings after this date.
            max_meetings: Maximum total meetings to return.

        Yields:
            FathomMeeting objects.
        """
        cursor = None
        count = 0

        while count < max_meetings:
            meetings, cursor = self.list_meetings(limit=min(100, max_meetings - count), cursor=cursor)

            for meeting in meetings:
                # Apply time filter
                if since and meeting.created_at < since:
                    continue

                yield meeting
                count += 1
                if count >= max_meetings:
                    break

            if not cursor:
                break

    def get_transcript(self, recording_id: int) -> Optional[str]:
        """
        Get transcript text for a recording.

        Args:
            recording_id: The recording ID.

        Returns:
            Transcript text or None if not available.
        """
        try:
            response = self._request(f"recordings/{recording_id}/transcript")

            # Transcript comes as list of segments with speaker and text
            segments = response.get("transcript", [])
            if not segments:
                return None

            # Format as "Speaker: text" lines
            lines = []
            for seg in segments:
                # Speaker can be a dict with display_name or a string
                speaker_data = seg.get("speaker", {})
                if isinstance(speaker_data, dict):
                    speaker = speaker_data.get("display_name") or speaker_data.get("name", "Unknown")
                else:
                    speaker = speaker_data or "Unknown"

                text = seg.get("text", "")
                if text:
                    lines.append(f"{speaker}: {text}")

            return "\n".join(lines)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise

    def get_summary(self, recording_id: int) -> Optional[dict]:
        """
        Get summary and action items for a recording.

        Args:
            recording_id: The recording ID.

        Returns:
            Dict with summary and action_items, or None.
        """
        try:
            response = self._request(f"recordings/{recording_id}/summary")
            return {
                "summary": response.get("default_summary", {}).get("markdown_formatted"),
                "action_items": response.get("action_items", []),
            }
        except requests.exceptions.HTTPError:
            return None

    def get_full_transcript(self, meeting: FathomMeeting) -> FathomTranscript:
        """
        Get full transcript details for a meeting.

        Args:
            meeting: FathomMeeting object.

        Returns:
            FathomTranscript with all details.
        """
        transcript_text = self.get_transcript(meeting.recording_id) or ""
        summary_data = self.get_summary(meeting.recording_id) or {}

        # Extract participants from calendar invitees
        participants = []
        for invitee in meeting.calendar_invitees:
            name = invitee.get("name") or invitee.get("email", "").split("@")[0]
            if name:
                participants.append(name)

        # Calculate duration
        duration = 0
        if meeting.recording_start_time and meeting.recording_end_time:
            duration = int((meeting.recording_end_time - meeting.recording_start_time).total_seconds())

        return FathomTranscript(
            id=str(meeting.recording_id),
            title=meeting.title,
            date=meeting.created_at,
            duration_seconds=duration,
            participants=participants,
            transcript_text=transcript_text,
            summary=summary_data.get("summary"),
            action_items=[item.get("text", str(item)) for item in summary_data.get("action_items", [])],
            recording_url=meeting.share_url or meeting.url,
        )

    def load_from_json(self, file_path: Path) -> FathomTranscript:
        """
        Load a single transcript from a JSON file (legacy support).

        Expected format:
        {
            "id": "meeting_123",
            "title": "Weekly Standup",
            "date": "2024-01-15T10:00:00Z",
            "duration_seconds": 1800,
            "participants": ["Alice", "Bob"],
            "transcript": "Alice: Hello everyone...",
            "summary": "Team discussed...",
            "action_items": ["Task 1", "Task 2"],
            "recording_url": "https://..."
        }
        """
        with open(file_path) as f:
            data = json.load(f)

        return FathomTranscript(
            id=data["id"],
            title=data["title"],
            date=datetime.fromisoformat(data["date"].replace("Z", "+00:00")),
            duration_seconds=data.get("duration_seconds", 0),
            participants=data.get("participants", []),
            transcript_text=data.get("transcript", ""),
            summary=data.get("summary"),
            action_items=data.get("action_items", []),
            recording_url=data.get("recording_url"),
        )

    def load_all_transcripts(
        self,
        since: Optional[datetime] = None,
        from_api: bool = True,
        max_meetings: int = 1000,
    ) -> Iterator[FathomTranscript]:
        """
        Load all transcripts.

        Args:
            since: Only load transcripts after this date.
            from_api: If True, load from API. If False, load from files.
            max_meetings: Maximum meetings to load from API.

        Yields:
            FathomTranscript objects.
        """
        if from_api and self.api_key:
            print("Loading meetings from Fathom API...")
            meetings = list(self.list_all_meetings(since=since, max_meetings=max_meetings))
            print(f"  Found {len(meetings)} meetings")

            for i, meeting in enumerate(meetings, 1):
                print(f"  Fetching transcript {i}/{len(meetings)}: {meeting.title[:50]}...")
                try:
                    transcript = self.get_full_transcript(meeting)
                    if transcript.transcript_text:  # Only yield if has content
                        yield transcript
                except Exception as e:
                    print(f"    Warning: Failed to get transcript: {e}")
        else:
            # Fall back to file loading
            for json_file in self.data_dir.glob("*.json"):
                try:
                    transcript = self.load_from_json(json_file)
                    if since and transcript.date < since:
                        continue
                    yield transcript
                except (json.JSONDecodeError, KeyError) as e:
                    print(f"Warning: Failed to load {json_file}: {e}")

    def chunk_transcript(
        self,
        transcript: FathomTranscript,
        chunk_by: str = "speaker_turn",
        max_chunk_size: int = 2000,
        overlap_sentences: int = 1,
    ) -> Iterator[Chunk]:
        """
        Split a transcript into chunks for indexing.

        Args:
            transcript: The transcript to chunk.
            chunk_by: Strategy - "speaker_turn" or "time_window".
            max_chunk_size: Maximum characters per chunk.
            overlap_sentences: Number of sentences to overlap between chunks.

        Yields:
            Chunk objects ready for storage.
        """
        if chunk_by == "speaker_turn":
            yield from self._chunk_by_speaker(transcript, max_chunk_size)
        else:
            yield from self._chunk_by_size(transcript, max_chunk_size, overlap_sentences)

    def _chunk_by_speaker(
        self,
        transcript: FathomTranscript,
        max_chunk_size: int,
    ) -> Iterator[Chunk]:
        """
        Chunk transcript by speaker turns.

        Assumes format like:
        "Speaker Name: What they said.\nOther Speaker: Their response."
        """
        text = transcript.transcript_text

        # Split by speaker pattern (Name: )
        speaker_pattern = r"([A-Z][a-zA-Z\s]+):\s"
        parts = re.split(speaker_pattern, text)

        # Reconstruct speaker turns
        current_chunk = f"[Meeting: {transcript.title}]\n"
        current_speakers = set()
        chunk_index = 0

        i = 1  # Skip first empty split
        while i < len(parts) - 1:
            speaker = parts[i].strip()
            content = parts[i + 1].strip() if i + 1 < len(parts) else ""

            turn = f"{speaker}: {content}\n"
            current_speakers.add(speaker)

            # Check if adding this turn would exceed limit
            if len(current_chunk) + len(turn) > max_chunk_size:
                # Emit current chunk
                if current_chunk.strip():
                    chunk_id = generate_chunk_id(
                        "fathom", f"{transcript.id}:{chunk_index}", current_chunk
                    )
                    yield Chunk(
                        id=chunk_id,
                        content=current_chunk.strip(),
                        source_type=SourceType.FATHOM,
                        source_id=transcript.id,
                        source_url=transcript.recording_url,
                        timestamp=transcript.date,
                        participants=list(current_speakers),
                        channel=transcript.title,
                    )
                    chunk_index += 1

                # Start new chunk with context
                current_chunk = f"[Meeting: {transcript.title} (continued)]\n{turn}"
                current_speakers = {speaker}
            else:
                current_chunk += turn

            i += 2

        # Emit final chunk
        if current_chunk.strip() and len(current_chunk) > 50:  # Skip tiny fragments
            chunk_id = generate_chunk_id(
                "fathom", f"{transcript.id}:{chunk_index}", current_chunk
            )
            yield Chunk(
                id=chunk_id,
                content=current_chunk.strip(),
                source_type=SourceType.FATHOM,
                source_id=transcript.id,
                source_url=transcript.recording_url,
                timestamp=transcript.date,
                participants=list(current_speakers),
                channel=transcript.title,
            )

    def _chunk_by_size(
        self,
        transcript: FathomTranscript,
        max_chunk_size: int,
        overlap_sentences: int,
    ) -> Iterator[Chunk]:
        """
        Chunk transcript by size with sentence overlap.

        Simpler approach that just splits by character count with overlap.
        """
        text = transcript.transcript_text
        prefix = f"[Meeting: {transcript.title}]\n"

        # Split into sentences
        sentences = re.split(r"(?<=[.!?])\s+", text)

        current_chunk = prefix
        chunk_index = 0
        sentence_buffer: list[str] = []

        for sentence in sentences:
            sentence_buffer.append(sentence)

            if len(current_chunk) + len(sentence) > max_chunk_size:
                # Emit current chunk
                if current_chunk.strip():
                    chunk_id = generate_chunk_id(
                        "fathom", f"{transcript.id}:{chunk_index}", current_chunk
                    )
                    yield Chunk(
                        id=chunk_id,
                        content=current_chunk.strip(),
                        source_type=SourceType.FATHOM,
                        source_id=transcript.id,
                        source_url=transcript.recording_url,
                        timestamp=transcript.date,
                        participants=transcript.participants,
                        channel=transcript.title,
                    )
                    chunk_index += 1

                # Start new chunk with overlap
                overlap = sentence_buffer[-overlap_sentences:] if overlap_sentences else []
                current_chunk = prefix + " ".join(overlap) + " "
                sentence_buffer = overlap.copy()
            else:
                current_chunk += sentence + " "

        # Emit final chunk
        if current_chunk.strip() and len(current_chunk) > 50:
            chunk_id = generate_chunk_id(
                "fathom", f"{transcript.id}:{chunk_index}", current_chunk
            )
            yield Chunk(
                id=chunk_id,
                content=current_chunk.strip(),
                source_type=SourceType.FATHOM,
                source_id=transcript.id,
                source_url=transcript.recording_url,
                timestamp=transcript.date,
                participants=transcript.participants,
                channel=transcript.title,
            )

    def load_and_chunk(
        self,
        since: Optional[datetime] = None,
        chunk_by: str = "speaker_turn",
        max_meetings: int = 1000,
    ) -> Iterator[Chunk]:
        """
        Convenience method to load all transcripts and convert to chunks.

        Args:
            since: Only load transcripts after this date.
            chunk_by: Chunking strategy.
            max_meetings: Maximum meetings to load.

        Yields:
            Chunk objects ready for storage.
        """
        for transcript in self.load_all_transcripts(since=since, max_meetings=max_meetings):
            yield from self.chunk_transcript(transcript, chunk_by=chunk_by)
