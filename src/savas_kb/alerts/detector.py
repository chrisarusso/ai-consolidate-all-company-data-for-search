"""
Alert detection for risks and opportunities.

Analyzes content to detect signals that should trigger alerts.
"""

import re
import uuid
from datetime import datetime
from typing import Optional
from openai import OpenAI

from ..config import OPENAI_API_KEY, LLM_MODEL
from ..models import Alert, Chunk, SignalType


# Keyword patterns for quick detection
RISK_KEYWORDS = {
    SignalType.RISK_BUDGET: [
        r"\bbudget\b.*\b(concern|issue|problem|tight|over|exceed)",
        r"\bcost\b.*\b(concern|issue|overrun|too high)",
        r"\bexpensive\b",
        r"\bcan't afford\b",
        r"\bout of budget\b",
    ],
    SignalType.RISK_SCHEDULE: [
        r"\bdeadline\b.*\b(miss|slip|delay|concern)",
        r"\bbehind schedule\b",
        r"\bdelayed?\b",
        r"\btimeline\b.*\b(concern|issue|slip)",
        r"\bwon't make it\b",
        r"\bpushed back\b",
    ],
    SignalType.RISK_SCOPE: [
        r"\bscope\b.*\b(creep|change|expand|grow)",
        r"\badditional requirements\b",
        r"\bmore than expected\b",
        r"\bkeep adding\b",
        r"\bout of scope\b",
    ],
}

OPPORTUNITY_KEYWORDS = {
    SignalType.OPPORTUNITY_ADDITIONAL_WORK: [
        r"\badditional (work|project|phase)\b",
        r"\bnext phase\b",
        r"\bfollow-?up (project|work)\b",
        r"\bmore work\b",
        r"\bexpand.*scope\b",
        r"\banother project\b",
    ],
    SignalType.OPPORTUNITY_REFERRAL: [
        r"\brecommend\b.*\b(you|your team)\b",
        r"\breferr?(al|ed)\b",
        r"\bknow (someone|people|others)\b",
        r"\bintroduce\b.*\bto\b",
    ],
    SignalType.OPPORTUNITY_EXPANSION: [
        r"\bother (teams?|departments?|areas?)\b",
        r"\bcompany-?wide\b",
        r"\broll out\b.*\b(broader|wider)\b",
        r"\bexpand\b.*\b(to|across)\b",
    ],
}


class AlertDetector:
    """
    Detects risks and opportunities in content.

    Uses a hybrid approach:
    1. Fast keyword matching for common patterns
    2. LLM classification for nuanced detection
    """

    def __init__(self, use_llm: bool = True):
        """
        Initialize the detector.

        Args:
            use_llm: Whether to use LLM for nuanced detection.
        """
        self.use_llm = use_llm
        if use_llm:
            self.openai_client = OpenAI(api_key=OPENAI_API_KEY)

    def detect_signals(self, chunk: Chunk) -> list[Alert]:
        """
        Detect risk and opportunity signals in a chunk.

        Args:
            chunk: The content chunk to analyze.

        Returns:
            List of detected alerts (may be empty).
        """
        alerts = []
        content = chunk.content.lower()

        # Quick keyword detection
        keyword_signals = self._detect_keywords(content)

        # LLM detection for nuanced signals
        llm_signals = []
        if self.use_llm:
            llm_signals = self._detect_with_llm(chunk)

        # Combine and deduplicate
        all_signals = set(keyword_signals + llm_signals)

        # Create alerts for each detected signal
        for signal_type in all_signals:
            alert = self._create_alert(chunk, signal_type)
            if alert:
                alerts.append(alert)

        return alerts

    def _detect_keywords(self, content: str) -> list[SignalType]:
        """Detect signals using keyword patterns."""
        detected = []

        # Check risk patterns
        for signal_type, patterns in RISK_KEYWORDS.items():
            for pattern in patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    detected.append(signal_type)
                    break  # One match per signal type is enough

        # Check opportunity patterns
        for signal_type, patterns in OPPORTUNITY_KEYWORDS.items():
            for pattern in patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    detected.append(signal_type)
                    break

        return detected

    def _detect_with_llm(self, chunk: Chunk) -> list[SignalType]:
        """Use LLM for nuanced signal detection."""
        prompt = f"""Analyze this conversation excerpt for business signals.

CONTENT:
{chunk.content}

---

Identify if any of these signals are present:

RISKS:
- RISK_BUDGET: Client expressing budget concerns
- RISK_SCHEDULE: Concerns about timeline or deadlines
- RISK_SCOPE: Scope creep or changing requirements
- RISK_SENTIMENT: General frustration or dissatisfaction

OPPORTUNITIES:
- OPPORTUNITY_ADDITIONAL_WORK: Client interested in more work
- OPPORTUNITY_REFERRAL: Client offering to refer others
- OPPORTUNITY_EXPANSION: Interest in expanding to other areas

Respond with ONLY the signal codes that apply, comma-separated.
If no signals detected, respond with "NONE".

Example response: RISK_BUDGET, OPPORTUNITY_ADDITIONAL_WORK"""

        try:
            response = self.openai_client.chat.completions.create(
                model=LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=100,
            )

            result = response.choices[0].message.content or ""

            if "NONE" in result.upper():
                return []

            # Parse signal types from response
            detected = []
            for signal_type in SignalType:
                if signal_type.value.upper() in result.upper():
                    detected.append(signal_type)

            return detected

        except Exception as e:
            print(f"LLM detection failed: {e}")
            return []

    def _create_alert(self, chunk: Chunk, signal_type: SignalType) -> Optional[Alert]:
        """Create an alert object from a detected signal."""
        # Determine severity
        if "RISK" in signal_type.value:
            severity = "high" if "BUDGET" in signal_type.value else "medium"
        else:
            severity = "medium"

        # Extract a relevant quote (first 200 chars)
        quote = chunk.content[:200]
        if len(chunk.content) > 200:
            quote += "..."

        # Generate title
        titles = {
            SignalType.RISK_BUDGET: "Budget Concern Detected",
            SignalType.RISK_SCHEDULE: "Schedule Risk Detected",
            SignalType.RISK_SCOPE: "Scope Creep Detected",
            SignalType.RISK_SENTIMENT: "Client Sentiment Concern",
            SignalType.OPPORTUNITY_ADDITIONAL_WORK: "Additional Work Opportunity",
            SignalType.OPPORTUNITY_REFERRAL: "Referral Opportunity",
            SignalType.OPPORTUNITY_EXPANSION: "Expansion Opportunity",
        }

        title = titles.get(signal_type, f"Signal: {signal_type.value}")

        # Generate summary
        summary = self._generate_summary(chunk, signal_type) if self.use_llm else quote

        return Alert(
            id=str(uuid.uuid4())[:8],
            signal_type=signal_type,
            severity=severity,
            title=title,
            summary=summary,
            quote=quote,
            source_chunk=chunk,
        )

    def _generate_summary(self, chunk: Chunk, signal_type: SignalType) -> str:
        """Generate a brief summary of the alert."""
        prompt = f"""Summarize this {signal_type.value} signal in 1-2 sentences.
Be specific about what was said and who said it.

Content: {chunk.content[:500]}"""

        try:
            response = self.openai_client.chat.completions.create(
                model=LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=100,
            )
            return response.choices[0].message.content or chunk.content[:200]
        except Exception:
            return chunk.content[:200]
