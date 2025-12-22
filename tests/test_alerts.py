"""Tests for alert detection."""

from datetime import datetime
import pytest

from savas_kb.models import Chunk, SourceType, SignalType
from savas_kb.alerts.detector import AlertDetector


class TestAlertDetectorKeywords:
    """Test keyword-based alert detection (no LLM)."""

    @pytest.fixture
    def detector(self):
        """Create detector without LLM."""
        return AlertDetector(use_llm=False)

    def make_chunk(self, content: str) -> Chunk:
        """Helper to create a test chunk."""
        return Chunk(
            id="test",
            content=content,
            source_type=SourceType.FATHOM,
            source_id="meeting_123",
            timestamp=datetime.now(),
        )

    def test_detect_budget_risk(self, detector):
        """Test detection of budget concerns."""
        chunk = self.make_chunk(
            "The client mentioned they have budget concerns about the project scope."
        )
        alerts = detector.detect_signals(chunk)

        signal_types = [a.signal_type for a in alerts]
        assert SignalType.RISK_BUDGET in signal_types

    def test_detect_schedule_risk(self, detector):
        """Test detection of schedule risks."""
        chunk = self.make_chunk(
            "We're behind schedule and might miss the deadline next week."
        )
        alerts = detector.detect_signals(chunk)

        signal_types = [a.signal_type for a in alerts]
        assert SignalType.RISK_SCHEDULE in signal_types

    def test_detect_scope_creep(self, detector):
        """Test detection of scope creep."""
        chunk = self.make_chunk(
            "They keep adding additional requirements that are out of scope."
        )
        alerts = detector.detect_signals(chunk)

        signal_types = [a.signal_type for a in alerts]
        assert SignalType.RISK_SCOPE in signal_types

    def test_detect_additional_work_opportunity(self, detector):
        """Test detection of additional work opportunities."""
        chunk = self.make_chunk(
            "The client asked about a follow-up project for next quarter."
        )
        alerts = detector.detect_signals(chunk)

        signal_types = [a.signal_type for a in alerts]
        assert SignalType.OPPORTUNITY_ADDITIONAL_WORK in signal_types

    def test_detect_referral_opportunity(self, detector):
        """Test detection of referral opportunities."""
        chunk = self.make_chunk(
            "They said they would recommend your team to their partners and refer you to others."
        )
        alerts = detector.detect_signals(chunk)

        signal_types = [a.signal_type for a in alerts]
        assert SignalType.OPPORTUNITY_REFERRAL in signal_types

    def test_no_signals_in_neutral_content(self, detector):
        """Test that neutral content doesn't trigger alerts."""
        chunk = self.make_chunk(
            "The meeting went well. We discussed the current sprint tasks."
        )
        alerts = detector.detect_signals(chunk)

        assert len(alerts) == 0

    def test_multiple_signals(self, detector):
        """Test detection of multiple signals in one chunk."""
        chunk = self.make_chunk(
            "We're behind schedule and might miss the deadline. The budget concern is real. "
            "But they want to expand company-wide to other teams."
        )
        alerts = detector.detect_signals(chunk)

        signal_types = [a.signal_type for a in alerts]
        # Should detect both risks and opportunity
        assert any("risk" in st.value for st in signal_types)
        assert any("opportunity" in st.value for st in signal_types)

    def test_alert_has_required_fields(self, detector):
        """Test that created alerts have all required fields."""
        chunk = self.make_chunk("The client has budget concerns.")
        alerts = detector.detect_signals(chunk)

        assert len(alerts) > 0
        alert = alerts[0]

        assert alert.id is not None
        assert alert.signal_type is not None
        assert alert.severity in ["high", "medium", "low"]
        assert alert.title is not None
        assert alert.summary is not None
        assert alert.quote is not None
        assert alert.source_chunk == chunk
