"""
Slack notification for alerts.

Posts detected alerts to a Slack channel.
"""

from typing import Optional
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from ..config import SLACK_BOT_TOKEN, ALERT_SLACK_CHANNEL, ALERT_TAG_USER
from ..models import Alert


class SlackNotifier:
    """
    Posts alerts to Slack.

    Formats alerts as rich messages with context and links.
    """

    def __init__(
        self,
        channel: Optional[str] = None,
        tag_user: Optional[str] = None,
    ):
        """
        Initialize the notifier.

        Args:
            channel: Slack channel to post to.
            tag_user: User to tag in alerts.
        """
        self.channel = channel or ALERT_SLACK_CHANNEL
        self.tag_user = tag_user or ALERT_TAG_USER
        self.client = WebClient(token=SLACK_BOT_TOKEN) if SLACK_BOT_TOKEN else None

    def post_alert(self, alert: Alert) -> Optional[str]:
        """
        Post an alert to Slack.

        Args:
            alert: The alert to post.

        Returns:
            Message timestamp if successful, None otherwise.
        """
        if not self.client:
            print(f"[DRY RUN] Would post alert: {alert.title}")
            print(f"  Signal: {alert.signal_type.value}")
            print(f"  Summary: {alert.summary}")
            return None

        # Determine emoji based on signal type
        if "RISK" in alert.signal_type.value:
            emoji = ":warning:"
            color = "#FF6B6B"  # Red
        else:
            emoji = ":star:"
            color = "#4CAF50"  # Green

        # Build message blocks
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} {alert.title}",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Signal Type:* `{alert.signal_type.value}`\n*Severity:* {alert.severity.upper()}",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Summary:*\n{alert.summary}",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Quote:*\n>{alert.quote}",
                },
            },
        ]

        # Add source context
        chunk = alert.source_chunk
        source_text = f"*Source:* {chunk.source_type.value}"
        if chunk.channel:
            source_text += f" | {chunk.channel}"
        if chunk.timestamp:
            source_text += f" | {chunk.timestamp.strftime('%Y-%m-%d %H:%M')}"
        if chunk.source_url:
            source_text += f"\n<{chunk.source_url}|View original>"

        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": source_text,
                }
            ],
        })

        # Add tag
        if self.tag_user:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"cc: {self.tag_user}",
                },
            })

        try:
            response = self.client.chat_postMessage(
                channel=self.channel,
                blocks=blocks,
                text=f"{alert.title}: {alert.summary}",  # Fallback text
            )
            return response["ts"]

        except SlackApiError as e:
            print(f"Failed to post alert to Slack: {e}")
            return None

    def post_alerts(self, alerts: list[Alert]) -> list[str]:
        """
        Post multiple alerts to Slack.

        Args:
            alerts: List of alerts to post.

        Returns:
            List of message timestamps for successful posts.
        """
        timestamps = []
        for alert in alerts:
            ts = self.post_alert(alert)
            if ts:
                timestamps.append(ts)
                alert.posted_to_slack = True
                alert.slack_message_ts = ts
        return timestamps
