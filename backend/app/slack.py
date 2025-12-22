from typing import List

from .models import SearchResult


def format_results_blocks(results: List[SearchResult]) -> dict:
    """
    Format search results as Slack blocks for a slash command response.
    """
    blocks = []
    if not results:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "No results found."}})
        return {"blocks": blocks}

    for res in results[:5]:
        text = f"*{res.title or res.source}* (score {res.score:.2f})\n{res.text[:280]}..."
        if res.provenance.get("start_ms") is not None:
            ts_seconds = int(res.provenance["start_ms"] / 1000)
            text += f"\n`t={ts_seconds}s`"
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": text}})
        blocks.append({"type": "divider"})
    return {"blocks": blocks}

