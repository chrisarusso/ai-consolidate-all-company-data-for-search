"""
Configuration for Savas Knowledge Base.

Loads settings from environment variables with sensible defaults.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if present
load_dotenv()

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
CHROMA_DIR = DATA_DIR / "chroma"
SLACK_DIR = DATA_DIR / "slack"
FATHOM_DIR = DATA_DIR / "fathom"
GITHUB_DIR = DATA_DIR / "github"
DRIVE_DIR = DATA_DIR / "drive"
TEAMWORK_DIR = DATA_DIR / "teamwork"
HARVEST_DIR = DATA_DIR / "harvest"

# Ensure directories exist
for dir_path in [DATA_DIR, CHROMA_DIR, SLACK_DIR, FATHOM_DIR, GITHUB_DIR, DRIVE_DIR, TEAMWORK_DIR, HARVEST_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")
FATHOM_API_KEY = os.getenv("FATHOM_API_KEY")

# Teamwork API
TEAMWORK_API_KEY = os.getenv("TEAMWORK_API_KEY")
TEAMWORK_SITE = os.getenv("TEAMWORK_SITE", "savaslabs.teamwork.com")

# Harvest API
HARVEST_ACCESS_TOKEN = os.getenv("HARVEST_ACCESS_TOKEN")
HARVEST_ACCOUNT_ID = os.getenv("HARVEST_ACCOUNT_ID")

# Google OAuth paths
GOOGLE_CREDENTIALS_FILE = PROJECT_ROOT / "credentials.json"
GOOGLE_TOKEN_FILE = PROJECT_ROOT / "token.json"

# Embedding settings
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))

# Search settings
SEARCH_TOP_K = int(os.getenv("SEARCH_TOP_K", "20"))
RERANK_TOP_K = int(os.getenv("RERANK_TOP_K", "5"))

# LLM settings for response generation
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

# Chroma settings
CHROMA_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "savas_knowledge")

# Alert settings
ALERT_SLACK_CHANNEL = os.getenv("ALERT_SLACK_CHANNEL", "#alerts")
ALERT_TAG_USER = os.getenv("ALERT_TAG_USER", "@chris")
