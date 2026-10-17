"""
Zok (ذوق) — Gemini API Enrichment
Uses Google Gemini Flash to generate summaries, tags, editorial notes, and recall questions.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from backend.config import GEMINI_API_KEY
from backend.models import Article, User

logger = logging.getLogger(__name__)

# ── Gemini Client ─────────────────────────────────────────────────────────────

_client = None
_enrichment_cache: dict[str, dict] = {}  # article_id → enrichment dict


def _get_client():
    global _client
    if _client is None:
        if not GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY not set — enrichment will use fallbacks")
            return None
        from google import genai
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def _call_gemini(prompt: str, retries: int = 1) -> str:
    """Call Gemini Flash and return the text response. Retries once on failure."""
    client = _get_client()
    if client is None:
        return ""
    for attempt in range(retries + 1):
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
            )
            return response.text or ""
        except Exception as e:
            logger.warning("Gemini call failed (attempt %d): %s", attempt + 1, e)
            if attempt >= retries:
                return ""
    return ""


def _extract_json(text: str) -> Any:
    """Try to parse JSON from Gemini response, handling markdown code blocks."""
    if not text:
        return None
    # Strip markdown code fences
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        text = match.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find any JSON object/array in the text
        for pattern in [r"\{[\s\S]*\}", r"\[[\s\S]*\]"]:
            m = re.search(pattern, text)
            if m:
                try:
                    return json.loads(m.group(0))
                except json.JSONDecodeError:
                    continue
    return None


# ── Article Enrichment ────────────────────────────────────────────────────────

def enrich_article(article: Article) -> Article:
    """
    Enrich an article with Gemini-generated summary, importance, tags, and 'why it matters'.
    Results are cached by article ID to avoid duplicate API calls.
    """
    # Check cache
    if article.id in _enrichment_cache:
        cached = _enrichment_cache[article.id]
        article.summary = cached.get("summary", article.summary)
        article.importance_score = cached.get("importance_score", article.importance_score)
        article.tags = cached.get("tags", article.tags)
        return article

    prompt = f"""Analyze this news article and return ONLY a JSON object with these exact keys:
{{
  "summary": "A crisp 2-line summary of the article (max 200 chars)",
  "importance_score": 0.75,
  "tags": ["tag1", "tag2", "tag3"],
  "why_it_matters": "One sentence on why a curious reader should care"
}}

ARTICLE TITLE: {article.title}
ARTICLE CONTENT: {article.content[:2000]}
SOURCE: {article.source}

Return ONLY the JSON, nothing else."""

    raw = _call_gemini(prompt)
    data = _extract_json(raw)

    if data and isinstance(data, dict):
        article.summary = data.get("summary", article.summary) or article.summary
        article.importance_score = float(data.get("importance_score", article.importance_score) or 0.5)
        article.tags = data.get("tags", article.tags) or article.tags
        # Store the why_it_matters in content if not already rich
        why = data.get("why_it_matters", "")
        if why and "\n\nWhy it matters:" not in article.content:
            article.content = article.content + f"\n\nWhy it matters: {why}"
    else:
        # Fallback defaults
        if not article.tags:
            article.tags = [article.category] if article.category else ["General"]
        logger.info("Using fallback enrichment for article: %s", article.title[:50])

    # Cache result
    _enrichment_cache[article.id] = {
        "summary": article.summary,
        "importance_score": article.importance_score,
        "tags": article.tags,
    }

    return article


# ── Editorial Note ────────────────────────────────────────────────────────────

def generate_editorial_note(user: User, articles: list[Article]) -> str:
    """Generate a personalized editor's letter for the user's morning edition."""
    titles = "\n".join(f"- {a.title} ({a.category})" for a in articles[:8])

    prompt = f"""You are the editor of "Zok (ذوق)", a personalized morning newspaper.
Write a warm, engaging editor's note (3-4 sentences) for this reader:

READER: {user.name}
TAGLINE: {user.tagline}
TODAY'S ARTICLES:
{titles}

The note should:
- Greet the reader by first name
- Reference 1-2 specific stories from today's edition
- Feel personal, witty, and warm — like a note from a friend who knows what you like
- End with something encouraging for the day ahead

Return ONLY the editor's note text, no JSON."""

    result = _call_gemini(prompt)
    if result and len(result) > 20:
        # Clean up any quotes
        return result.strip().strip('"').strip("'")

    # Fallback
    first_name = user.name.split()[0] if user.name else "Reader"
    return (
        f"Good morning, {first_name}! ☀️ Your personalized edition is ready. "
        f"We've curated {len(articles)} stories across {len(set(a.category for a in articles))} topics "
        f"that match your interests. Happy reading!"
    )


# ── Three Things ──────────────────────────────────────────────────────────────

def generate_three_things(articles: list[Article]) -> list[str]:
    """Generate 'Three Things To Know Today' from the top articles."""
    titles_and_summaries = "\n".join(
        f"- {a.title}: {a.summary[:150]}" for a in articles[:8]
    )

    prompt = f"""Based on these news articles, write "Three Things To Know Today" — 
three concise, punchy bullet points (1 sentence each) that capture the most important news.

ARTICLES:
{titles_and_summaries}

Return ONLY a JSON array of 3 strings, like:
["First thing...", "Second thing...", "Third thing..."]"""

    raw = _call_gemini(prompt)
    data = _extract_json(raw)

    if data and isinstance(data, list) and len(data) >= 3:
        return [str(item) for item in data[:3]]

    # Fallback: use first 3 article summaries
    fallback = []
    for a in articles[:3]:
        summary = a.summary if a.summary else a.title
        if len(summary) > 120:
            summary = summary[:117] + "..."
        fallback.append(summary)
    while len(fallback) < 3:
        fallback.append("Stay curious — more news is brewing.")
    return fallback


# ── Recall Questions ──────────────────────────────────────────────────────────

def generate_recall_questions(articles: list[Article]) -> list[dict]:
    """Generate 3 multiple-choice recall questions from the edition's articles."""
    content_snippets = "\n\n".join(
        f"ARTICLE: {a.title}\nSUMMARY: {a.summary}" for a in articles[:6]
    )

    prompt = f"""Based on these news articles, create 3 multiple-choice recall quiz questions.
Each question should test whether the reader remembers key facts from the articles.

ARTICLES:
{content_snippets}

Return ONLY a JSON array of 3 objects, each with:
{{
  "question": "What happened with...?",
  "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
  "correct": 0,
  "article_title": "Related Article Title"
}}

Where "correct" is the 0-based index of the right answer."""

    raw = _call_gemini(prompt)
    data = _extract_json(raw)

    if data and isinstance(data, list) and len(data) >= 1:
        questions = []
        for item in data[:3]:
            if isinstance(item, dict) and "question" in item:
                q = {
                    "question": str(item.get("question", "")),
                    "options": item.get("options", ["A", "B", "C", "D"]),
                    "correct": int(item.get("correct", 0)),
                    "article_title": str(item.get("article_title", "")),
                }
                questions.append(q)
        if questions:
            return questions

    # Fallback questions
    fallback = []
    for i, a in enumerate(articles[:3]):
        fallback.append({
            "question": f"Which source reported: '{a.title[:80]}'?",
            "options": [f"A) {a.source}", "B) Al Jazeera", "C) CNN", "D) The Guardian"],
            "correct": 0,
            "article_title": a.title,
        })
    return fallback if fallback else [{
        "question": "What is Zok?",
        "options": ["A) A newspaper app", "B) A game", "C) A recipe app", "D) A map"],
        "correct": 0,
        "article_title": "General",
    }]


# ── Onboarding Parser ────────────────────────────────────────────────────────

def parse_onboarding(text: str) -> list[str]:
    """Extract interest keywords from a user's self-description."""
    if not text or len(text.strip()) < 3:
        return ["technology", "world news", "science"]

    prompt = f"""A new user described themselves as: "{text}"

Extract 5-8 interest/topic keywords that we should use to personalize their news feed.
Return ONLY a JSON array of strings, like: ["artificial intelligence", "startups", "cricket"]"""

    raw = _call_gemini(prompt)
    data = _extract_json(raw)

    if data and isinstance(data, list) and len(data) >= 2:
        return [str(item).lower() for item in data[:8]]

    # Fallback: basic keyword extraction
    keywords = []
    topic_words = {
        "tech", "technology", "ai", "science", "startup", "finance", "climate",
        "sports", "cricket", "politics", "health", "education", "business",
        "programming", "data", "machine learning", "pakistan", "economy",
    }
    words = text.lower().split()
    for w in words:
        clean = re.sub(r"[^a-z]", "", w)
        if clean in topic_words:
            keywords.append(clean)
    if not keywords:
        keywords = ["technology", "world news", "science"]
    return keywords
