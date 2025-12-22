import os
from pydantic import BaseModel


class Settings(BaseModel):
    """
    Centralized configuration with sensible dev defaults.
    In production, override via environment variables.
    """

    app_name: str = "Savas Unified Search POC"
    fathom_webhook_secret: str = os.getenv("FATHOM_WEBHOOK_SECRET", "dev-fathom-secret")
    slack_signing_secret: str = os.getenv("SLACK_SIGNING_SECRET", "dev-slack-secret")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "dev-openai")
    queue_name: str = os.getenv("QUEUE_NAME", "fathom-ingest")
    signature_tolerance_seconds: int = int(os.getenv("SIGNATURE_TOLERANCE_SECONDS", "300"))
    rerank_enabled: bool = os.getenv("RERANK_ENABLED", "false").lower() == "true"

    @classmethod
    def load(cls) -> "Settings":
        return cls()


settings = Settings.load()

