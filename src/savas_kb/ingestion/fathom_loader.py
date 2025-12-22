"""
Fathom transcript loader.

Handles loading meeting transcripts from Fathom exports or API
and converting them into chunks for the vector store.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

from ..config import FATHOM_DIR
from ..models import Chunk, FathomTranscript, SourceType
from ..storage.chroma_store import generate_chunk_id


class FathomLoader:
    """
    Load and process Fathom meeting transcripts.

    Supports loading from:
    - JSON export files
    - Fathom API (to be implemented)
    """

    def __init__(self, data_dir: Optional[Path] = None):
        """
        Initialize the Fathom loader.

        Args:
            data_dir: Path to Fathom data directory. Defaults to config.
        """
        self.data_dir = data_dir or FATHOM_DIR

    def load_from_json(self, file_path: Path) -> FathomTranscript:
        """
        Load a single transcript from a JSON file.

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
    ) -> Iterator[FathomTranscript]:
        """
        Load all transcripts from the data directory.

        Args:
            since: Only load transcripts after this date.

        Yields:
            FathomTranscript objects.
        """
        for json_file in self.data_dir.glob("*.json"):
            try:
                transcript = self.load_from_json(json_file)

                # Apply time filter
                if since and transcript.date < since:
                    continue

                yield transcript
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Warning: Failed to load {json_file}: {e}")
                continue

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
    ) -> Iterator[Chunk]:
        """
        Convenience method to load all transcripts and convert to chunks.

        Args:
            since: Only load transcripts after this date.
            chunk_by: Chunking strategy.

        Yields:
            Chunk objects ready for storage.
        """
        for transcript in self.load_all_transcripts(since=since):
            yield from self.chunk_transcript(transcript, chunk_by=chunk_by)
