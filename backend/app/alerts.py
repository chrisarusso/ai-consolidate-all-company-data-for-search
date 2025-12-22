from typing import List

from .models import Alert, AlertCandidate


class AlertsService:
    """
    Simple keyword-based alert scoring.
    """

    def __init__(self):
        self.rules = {
            "budget_risk": [
                "budget",
                "over budget",
                "too expensive",
                "cost overrun",
                "scope creep",
                "out of scope",
                "change order",
                "cannot afford",
            ],
            "schedule_risk": [
                "slipping",
                "behind schedule",
                "delay",
                "deadline",
                "blocked",
                "pushed back",
                "need more time",
                "not ready",
            ],
            "satisfaction_risk": [
                "frustrated",
                "unhappy",
                "concerned",
                "not working",
                "quality issue",
                "rework",
            ],
            "opportunity": [
                "can you also",
                "additional work",
                "phase two",
                "expansion",
                "maintenance",
                "support retainer",
                "new project",
                "integration",
                "referral",
            ],
        }

    def score(self, candidate: AlertCandidate) -> List[Alert]:
        alerts: List[Alert] = []
        for alert_type, keywords in self.rules.items():
            best_chunk = None
            best_score = 0.0
            for chunk in candidate.chunks:
                text = chunk.text.lower()
                score = sum(text.count(k) for k in keywords)
                if score > best_score:
                    best_score = float(score)
                    best_chunk = chunk
            if best_score > 0 and best_chunk:
                alerts.append(
                    Alert(
                        alert_type=alert_type,
                        call_id=candidate.call_id,
                        title=candidate.title,
                        project=candidate.project,
                        workspace_id=candidate.workspace_id,
                        chunks=[
                            {
                                "text": best_chunk.text,
                                "speaker": best_chunk.speaker,
                                "start_ms": best_chunk.start_ms,
                            }
                        ],
                        score=best_score,
                    )
                )
        return alerts

