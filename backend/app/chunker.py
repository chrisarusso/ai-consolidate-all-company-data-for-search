from typing import Iterable, List

from .models import Chunk, TranscriptSegment


def chunk_segments(
    segments: Iterable[TranscriptSegment],
    document_id: str,
    target_chars: int = 500,
    overlap_chars: int = 50,
) -> List[Chunk]:
    """
    Group transcript segments into approximate windows for embedding.
    Uses a rolling buffer by characters, not tokens, for simplicity.
    """
    chunks: List[Chunk] = []
    buffer: List[TranscriptSegment] = []
    buffer_len = 0
    idx = 0

    for seg in segments:
        if not seg.text.strip():
            continue
        seg_len = len(seg.text)
        if buffer_len + seg_len > target_chars and buffer:
            chunks.append(_flush(buffer, document_id, idx))
            idx += 1
            # start new buffer; optionally overlap last segment text
            if overlap_chars and buffer:
                tail = buffer[-1]
                overlap_text = tail.text[-overlap_chars:]
                buffer = [
                    TranscriptSegment(
                        start_ms=tail.start_ms,
                        end_ms=tail.end_ms,
                        speaker=tail.speaker,
                        text=overlap_text,
                    )
                ]
                buffer_len = len(overlap_text)
            else:
                buffer = []
                buffer_len = 0
        buffer.append(seg)
        buffer_len += seg_len

    if buffer:
        chunks.append(_flush(buffer, document_id, idx))
    return chunks


def _flush(buffer: List[TranscriptSegment], document_id: str, idx: int) -> Chunk:
    start_ms = buffer[0].start_ms if buffer else None
    end_ms = buffer[-1].end_ms if buffer else None
    speaker = buffer[0].speaker
    text = " ".join(seg.text.strip() for seg in buffer)
    return Chunk(
        id=f"{document_id}:{idx}",
        document_id=document_id,
        idx=idx,
        speaker=speaker,
        start_ms=start_ms,
        end_ms=end_ms,
        text=text,
        token_count=max(len(text.split()), 1),
    )

