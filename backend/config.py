"""
Zok (ذوق) — Configuration
Loads environment variables and defines paths and RSS feed sources.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# ── API Keys ──────────────────────────────────────────────────────────────────
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

# ── Paths ─────────────────────────────────────────────────────────────────────
# Use /tmp on Vercel (read-only filesystem), local otherwise
if os.environ.get("VERCEL"):
    DB_PATH = "/tmp/zok.db"
else:
    DB_PATH = str(BASE_DIR / "zok.db")

TEMPLATES_DIR = str(BASE_DIR / "templates")
STATIC_DIR = str(BASE_DIR / "public")
DATA_DIR = str(BASE_DIR / "data")
SEED_NEWS_PATH = str(BASE_DIR / "data" / "seed_news.json")

# ── RSS Feed Sources ──────────────────────────────────────────────────────────
RSS_FEEDS: list[dict[str, str]] = [
    {
        "url": "https://feeds.bbci.co.uk/news/world/rss.xml",
        "source": "BBC World",
        "category": "World",
    },
    {
        "url": "https://feeds.bbci.co.uk/news/technology/rss.xml",
        "source": "BBC Tech",
        "category": "Technology",
    },
    {
        "url": "https://www.reutersagency.com/feed/?taxonomy=best-sectors&post_type=best",
        "source": "Reuters",
        "category": "World",
    },
    {
        "url": "https://www.dawn.com/feeds/home",
        "source": "Dawn News",
        "category": "Pakistan",
    },
    {
        "url": "https://techcrunch.com/feed/",
        "source": "TechCrunch",
        "category": "Technology",
    },
    {
        "url": "https://hnrss.org/frontpage",
        "source": "Hacker News",
        "category": "Technology",
    },
]

# ── Source Trust Scores (used by recommender) ─────────────────────────────────
SOURCE_TRUST: dict[str, float] = {
    "BBC World": 0.95,
    "BBC Tech": 0.93,
    "Reuters": 0.97,
    "Dawn News": 0.85,
    "TechCrunch": 0.82,
    "Hacker News": 0.75,
}

# ── Defaults ──────────────────────────────────────────────────────────────────
DEFAULT_READING_BUDGET = 10  # minutes
ARTICLES_PER_BUDGET = {5: 3, 10: 5, 20: 10}
