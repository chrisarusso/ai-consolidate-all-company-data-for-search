"""
Slack data loader.

Handles loading messages from Slack exports (JSON files) and converting
them into chunks for the vector store.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

from ..config import SLACK_DIR
from ..models import Chunk, SlackMessage, SourceType
from ..storage.chroma_store import generate_chunk_id


class SlackLoader:
    """
    Load and process Slack messages from export files.

    Slack exports are organized as:
    - channels.json: List of channels with metadata
    - users.json: List of users with metadata
    - <channel_name>/YYYY-MM-DD.json: Messages for each day
    """

    def __init__(self, export_dir: Optional[Path] = None):
        """
        Initialize the Slack loader.

        Args:
            export_dir: Path to Slack export directory. Defaults to config.
        """
        self.export_dir = export_dir or SLACK_DIR
        self.channels: dict[str, dict] = {}
        self.users: dict[str, dict] = {}
        self._load_metadata()

    def _load_metadata(self) -> None:
        """Load channel and user metadata from export."""
        channels_file = self.export_dir / "channels.json"
        if channels_file.exists():
            with open(channels_file) as f:
                channels_list = json.load(f)
                self.channels = {c["id"]: c for c in channels_list}

        users_file = self.export_dir / "users.json"
        if users_file.exists():
            with open(users_file) as f:
                users_list = json.load(f)
                self.users = {u["id"]: u for u in users_list}

    def get_user_name(self, user_id: str) -> str:
        """Get display name for a user ID."""
        if user_id in self.users:
            user = self.users[user_id]
            return user.get("real_name") or user.get("name") or user_id
        return user_id

    def get_channel_name(self, channel_id: str) -> str:
        """Get name for a channel ID."""
        if channel_id in self.channels:
            return self.channels[channel_id].get("name", channel_id)
        return channel_id

    def load_messages(
        self,
        channel_filter: Optional[list[str]] = None,
        since: Optional[datetime] = None,
    ) -> Iterator[SlackMessage]:
        """
        Load messages from all channels in the export.

        Args:
            channel_filter: Only load from these channels (by name).
            since: Only load messages after this timestamp.

        Yields:
            SlackMessage objects.
        """
        # Find all channel directories
        for channel_dir in self.export_dir.iterdir():
            if not channel_dir.is_dir():
                continue

            channel_name = channel_dir.name

            # Apply channel filter
            if channel_filter and channel_name not in channel_filter:
                continue

            # Find channel ID from metadata
            channel_id = None
            for cid, cdata in self.channels.items():
                if cdata.get("name") == channel_name:
                    channel_id = cid
                    break
            channel_id = channel_id or channel_name

            # Load all JSON files in the channel directory
            for json_file in sorted(channel_dir.glob("*.json")):
                with open(json_file) as f:
                    messages = json.load(f)

                for msg in messages:
                    # Skip non-message types (joins, leaves, etc.)
                    if msg.get("subtype") in ["channel_join", "channel_leave", "bot_message"]:
                        continue

                    # Skip empty messages
                    if not msg.get("text"):
                        continue

                    # Parse timestamp
                    ts = msg.get("ts", "0")
                    try:
                        msg_time = datetime.fromtimestamp(float(ts))
                    except (ValueError, TypeError):
                        continue

                    # Apply time filter
                    if since and msg_time < since:
                        continue

                    yield SlackMessage(
                        ts=ts,
                        user=msg.get("user", "unknown"),
                        text=msg.get("text", ""),
                        channel=channel_id,
                        channel_name=channel_name,
                        thread_ts=msg.get("thread_ts"),
                        reply_count=msg.get("reply_count", 0),
                        reactions=msg.get("reactions", []),
                    )

    def messages_to_chunks(
        self,
        messages: Iterator[SlackMessage],
        group_by_thread: bool = True,
        max_chunk_size: int = 2000,
    ) -> Iterator[Chunk]:
        """
        Convert Slack messages to chunks for indexing.

        Args:
            messages: Iterator of SlackMessage objects.
            group_by_thread: Group thread replies into single chunks.
            max_chunk_size: Maximum characters per chunk.

        Yields:
            Chunk objects ready for storage.
        """
        # Group messages by thread if requested
        threads: dict[str, list[SlackMessage]] = {}
        standalone: list[SlackMessage] = []

        for msg in messages:
            if group_by_thread and msg.thread_ts:
                thread_key = f"{msg.channel}:{msg.thread_ts}"
                if thread_key not in threads:
                    threads[thread_key] = []
                threads[thread_key].append(msg)
            else:
                standalone.append(msg)

        # Process standalone messages
        for msg in standalone:
            user_name = self.get_user_name(msg.user)
            channel_name = msg.channel_name or self.get_channel_name(msg.channel)

            content = f"[#{channel_name}] {user_name}: {msg.text}"

            # Truncate if too long
            if len(content) > max_chunk_size:
                content = content[:max_chunk_size] + "..."

            chunk_id = generate_chunk_id("slack", msg.ts, content)

            yield Chunk(
                id=chunk_id,
                content=content,
                source_type=SourceType.SLACK,
                source_id=msg.ts,
                timestamp=datetime.fromtimestamp(float(msg.ts)),
                author=user_name,
                channel=channel_name,
                thread_id=msg.thread_ts,
            )

        # Process threads as combined chunks
        for thread_key, thread_msgs in threads.items():
            # Sort by timestamp
            thread_msgs.sort(key=lambda m: float(m.ts))

            # Build combined content
            parts = []
            participants = set()
            channel_name = None

            for msg in thread_msgs:
                user_name = self.get_user_name(msg.user)
                participants.add(user_name)
                if not channel_name:
                    channel_name = msg.channel_name or self.get_channel_name(msg.channel)
                parts.append(f"{user_name}: {msg.text}")

            content = f"[#{channel_name} thread]\n" + "\n".join(parts)

            # Truncate if too long
            if len(content) > max_chunk_size:
                content = content[:max_chunk_size] + "..."

            first_msg = thread_msgs[0]
            chunk_id = generate_chunk_id("slack", thread_key, content)

            yield Chunk(
                id=chunk_id,
                content=content,
                source_type=SourceType.SLACK,
                source_id=first_msg.thread_ts or first_msg.ts,
                timestamp=datetime.fromtimestamp(float(first_msg.ts)),
                author=self.get_user_name(first_msg.user),
                participants=list(participants),
                channel=channel_name,
                thread_id=first_msg.thread_ts,
            )

    def load_and_chunk(
        self,
        channel_filter: Optional[list[str]] = None,
        since: Optional[datetime] = None,
    ) -> Iterator[Chunk]:
        """
        Convenience method to load messages and convert to chunks.

        Args:
            channel_filter: Only load from these channels.
            since: Only load messages after this timestamp.

        Yields:
            Chunk objects ready for storage.
        """
        messages = self.load_messages(channel_filter=channel_filter, since=since)
        return self.messages_to_chunks(messages)
