from __future__ import annotations
import os

CONTACT_EMAIL: str = os.environ.get("CITEAGLE_CONTACT_EMAIL", "citeagle-bot@example.com")
BLUESKY_HANDLE: str = os.environ.get("BLUESKY_HANDLE", "")
BLUESKY_APP_PASSWORD: str = os.environ.get("BLUESKY_APP_PASSWORD", "")
ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")
SEMANTIC_SCHOLAR_API_KEY: str = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "")

USER_AGENT = f"citeagle/0.1.0 (mailto:{CONTACT_EMAIL})"

# Similarity thresholds
TITLE_SIM_VERIFIED = 0.90
TITLE_SIM_NEEDS_REVIEW_UPPER = 0.90
TITLE_SIM_NEEDS_REVIEW_LOWER = 0.50
TITLE_SIM_MISMATCH = 0.50

TITLE_SIM_NO_DOI_VERIFIED = 0.85
TITLE_SIM_NO_DOI_NEEDS_REVIEW = 0.75

# Retry config
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 1.0  # seconds

CACHE_PATH = ".citeagle_cache.json"
