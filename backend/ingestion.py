"""
Zok (ذوق) — RSS Feed Ingestion
Fetches, parses, and deduplicates news articles from configured RSS feeds.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime
from typing import Optional

import feedparser
from bs4 import BeautifulSoup

from backend.config import RSS_FEEDS
from backend.database import article_exists_by_url
from backend.models import ArticleCreate

logger = logging.getLogger(__name__)


def _clean_html(raw: str) -> str:
    """Strip HTML tags and collapse whitespace."""
    if not raw:
        return ""
    text = BeautifulSoup(raw, "html.parser").get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _parse_date(entry: dict) -> Optional[datetime]:
    """Try to extract a datetime from a feedparser entry."""
    for key in ("published_parsed", "updated_parsed"):
        tp = entry.get(key)
        if tp:
            try:
                from time import mktime
                return datetime.fromtimestamp(mktime(tp))
            except Exception:
                pass
    # fallback: try string parsing
    for key in ("published", "updated"):
        val = entry.get(key)
        if val:
            try:
                return datetime.fromisoformat(val)
            except (ValueError, TypeError):
                pass
    return datetime.utcnow()


def _extract_content(entry: dict) -> str:
    """Pull the best available content body from a feed entry."""
    # content field (Atom feeds)
    if "content" in entry and entry["content"]:
        return _clean_html(entry["content"][0].get("value", ""))
    # summary_detail
    if "summary_detail" in entry:
        return _clean_html(entry["summary_detail"].get("value", ""))
    # summary
    if "summary" in entry:
        return _clean_html(entry["summary"])
    # description
    if "description" in entry:
        return _clean_html(entry["description"])
    return ""


def _extract_summary(entry: dict) -> str:
    """Get a short summary from the entry."""
    raw = entry.get("summary", "") or entry.get("description", "")
    text = _clean_html(raw)
    # Limit to ~300 chars for a crisp summary
    if len(text) > 300:
        text = text[:297] + "..."
    return text


def fetch_feeds() -> list[ArticleCreate]:
    """
    Fetch all configured RSS feeds, parse entries, skip duplicates.
    Returns a list of ArticleCreate objects ready for DB insertion.
    """
    articles: list[ArticleCreate] = []

    for feed_cfg in RSS_FEEDS:
        url = feed_cfg["url"]
        source = feed_cfg["source"]
        category = feed_cfg["category"]

        try:
            logger.info("Fetching feed: %s", source)
            feed = feedparser.parse(url)

            if feed.bozo and not feed.entries:
                logger.warning("Feed parse error for %s: %s", source, feed.bozo_exception)
                continue

            for entry in feed.entries[:15]:  # cap per feed
                link = entry.get("link", "")
                if not link:
                    continue

                # Deduplicate against DB
                if article_exists_by_url(link):
                    continue

                title = _clean_html(entry.get("title", "Untitled"))
                summary = _extract_summary(entry)
                content = _extract_content(entry)
                pub_date = _parse_date(entry)

                articles.append(
                    ArticleCreate(
                        title=title,
                        summary=summary,
                        content=content if content else summary,
                        source=source,
                        source_url=link,
                        category=category,
                        tags=[],
                        importance_score=0.5,
                        published_at=pub_date,
                    )
                )

        except Exception as e:
            logger.error("Failed to fetch feed %s: %s", source, e, exc_info=True)
            continue

    logger.info("Ingested %d new articles from RSS feeds", len(articles))
    return articles
