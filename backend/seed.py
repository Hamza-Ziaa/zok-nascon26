"""
Zok (ذوق) — Database Seeding
Pre-populates 3 realistic personas, seed news articles, TF-IDF embeddings,
and sample morning editions with archive history.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from backend.config import SEED_NEWS_PATH
from backend.database import (
    get_all_articles, get_article_by_id, get_edition_by_id, get_editions_for_user,
    get_user_by_id, init_db, insert_article, insert_edition, insert_interaction,
    insert_recall_result, insert_user, is_db_empty, update_article_embedding,
    update_user_interests,
)
from backend.models import Article, Edition, Interaction, RecallResult, User
from backend.recommender import (
    compute_article_embeddings, fit_vectorizer, generate_embedding,
    recommend_articles, select_devils_advocate,
)

logger = logging.getLogger(__name__)

# ── Seed Personas Definition ──────────────────────────────────────────────────

SEED_PERSONAS = [
    {
        "id": "ayesha",
        "name": "Dr. Ayesha Malik",
        "tagline": "AI Researcher & Neuroscientist at NUST Islamabad",
        "bio": "Deep learning, neuromorphic hardware architectures, open-source AI models, computational neuroscience, and cricket biomechanics.",
        "reading_budget": 10,
    },
    {
        "id": "hamza",
        "name": "Hamza Khan",
        "tagline": "Fintech Startup Founder & Macro Trader, Karachi",
        "bio": "Digital payment rails, Raast cross-border payments, macroeconomics, central bank reserves, venture capital allocations, and deep tech investments.",
        "reading_budget": 10,
    },
    {
        "id": "zara",
        "name": "Zara Ahmed",
        "tagline": "Climate Journalist & Environmental Policy Analyst, Lahore",
        "bio": "Glacial lake flood warnings, Gilgit-Baltistan early telemetry, sodium batteries, renewable energy storage grids, and algorithmic echo chamber ethics.",
        "reading_budget": 10,
    },
]


def seed_articles_from_json() -> list[Article]:
    """Load articles from data/seed_news.json and insert into DB."""
    path = Path(SEED_NEWS_PATH)
    if not path.exists():
        logger.warning("Seed news file not found at %s", SEED_NEWS_PATH)
        return []

    with open(path, "r", encoding="utf-8") as f:
        raw_items = json.load(f)

    articles: list[Article] = []
    for item in raw_items:
        pub_dt = None
        if item.get("published_at"):
            try:
                pub_dt = datetime.fromisoformat(item["published_at"].replace("Z", "+00:00"))
            except Exception:
                pub_dt = datetime.utcnow()

        art = Article(
            id=item["id"],
            title=item["title"],
            summary=item.get("summary", ""),
            content=item.get("content", ""),
            source=item.get("source", ""),
            source_url=item.get("source_url", ""),
            category=item.get("category", "General"),
            tags=item.get("tags", []),
            importance_score=item.get("importance_score", 0.7),
            published_at=pub_dt,
            fetched_at=datetime.utcnow(),
        )
        insert_article(art)
        articles.append(art)

    # Compute TF-IDF embeddings
    compute_article_embeddings(articles)
    for art in articles:
        update_article_embedding(art.id, art.embedding)

    logger.info("Seeded and embedded %d articles", len(articles))
    return articles


def seed_personas() -> list[User]:
    """Insert the 3 primary personas with calibrated interest vectors."""
    users = []
    for p in SEED_PERSONAS:
        # Check if already exists
        existing = get_user_by_id(p["id"])
        if existing:
            users.append(existing)
            continue

        # Generate taste vector from bio
        taste_vec = generate_embedding(f"{p['name']} {p['tagline']} {p['bio']}")

        user = User(
            id=p["id"],
            name=p["name"],
            tagline=p["tagline"],
            interests_vector=taste_vec,
            reading_budget=p["reading_budget"],
            created_at=datetime.utcnow() - timedelta(days=7),
        )
        insert_user(user)
        users.append(user)
        logger.info("Seeded persona: %s", user.name)

    return users


def seed_editions_for_user(user: User, all_articles: list[Article]) -> None:
    """Generate today's edition and a couple of archived past editions for the user."""
    # Check if editions already exist
    existing = get_editions_for_user(user.id)
    if existing:
        return

    # 1. Recommend today's articles
    num_articles = 5 if user.reading_budget == 10 else (3 if user.reading_budget == 5 else 8)
    recommended = recommend_articles(user, all_articles, k=num_articles)
    devils_advocate = select_devils_advocate(user, all_articles)

    art_ids = [a.id for a in recommended]
    if devils_advocate and devils_advocate.id not in art_ids:
        art_ids.append(devils_advocate.id)

    # Person-specific editorial letters & 3 Things
    if user.id == "ayesha":
        three_things = [
            "Pakistan launched a sovereign AI compute grid connecting FAST & NUST for national LLMs.",
            "Event-driven neuromorphic processors cut LLM inference power draw by 80%.",
            "Open-weights coding models achieved a record 94.2% verified test suite pass rate.",
        ]
        editorial = "Good morning, Dr. Ayesha. Today's edition leads with sovereign compute and low-power neuromorphic architecture breakthroughs. Because you read deeply into ML systems yesterday, we expanded our technical hardware analysis. Your evening recall score stands at 92%."
        questions = [
            {
                "question": "Which university consortium is hosting the new National AI Compute Grid?",
                "options": ["FAST-NUCES & NUST", "LUMS & GIKI", "Oxford & MIT", "UET Lahore"],
                "answer": "FAST-NUCES & NUST",
            },
            {
                "question": "By what percentage do new neuromorphic chips reduce model energy draw?",
                "options": ["80%", "50%", "20%", "95%"],
                "answer": "80%",
            },
            {
                "question": "What verified pass rate did open-source coding models achieve?",
                "options": ["94.2%", "72.5%", "88.0%", "99.1%"],
                "answer": "94.2%",
            },
        ]
    elif user.id == "hamza":
        three_things = [
            "State Bank of Pakistan's Raast payment rails achieved instant cross-border settlement.",
            "Global central banks are diversifying reserves into rare earth minerals and energy credits.",
            "Venture capital is decisively retreating from copycat SaaS toward sovereign hardware infrastructure.",
        ]
        editorial = "Good morning, Hamza. Your financial broadsheet is primed. Raast's international interoperability is poised to unlock billions in direct remittance liquidity. We've placed macroeconomic reserve diversification on page two, alongside the structural VC pivot toward deep tech."
        questions = [
            {
                "question": "What is the estimated annual foreign remittance volume Raast could formalize?",
                "options": ["$4 Billion", "$1 Billion", "$500 Million", "$10 Billion"],
                "answer": "$4 Billion",
            },
            {
                "question": "Which payment rail achieved cross-border interoperability in Pakistan?",
                "options": ["Raast", "NayaPay", "Easypaisa", "1Link"],
                "answer": "Raast",
            },
            {
                "question": "Where is global venture capital reallocating away from consumer SaaS?",
                "options": ["Sovereign deep tech & hardware", "Crypto exchanges", "Social media apps", "Food delivery"],
                "answer": "Sovereign deep tech & hardware",
            },
        ]
    else:  # zara
        three_things = [
            "High-altitude satellite flood sensors are now live across Gilgit-Baltistan moraines.",
            "Solid-state sodium batteries have shipped commercially, halving renewable grid storage costs.",
            "Cognitive scientists warn that hyper-personalized feeds eliminate lateral intellectual discovery.",
        ]
        editorial = "Good morning, Zara. Today's environmental dispatch centers on climate resilience in the Karakoram range, accompanied by groundbreaking sodium-ion storage breakthroughs. In our Room to Explore corner, we examine the cognitive perils of echo-chamber algorithms."
        questions = [
            {
                "question": "How much advance evacuation warning do the new Gilgit-Baltistan moraine sensors provide?",
                "options": ["45 Minutes", "5 Minutes", "10 Hours", "2 Days"],
                "answer": "45 Minutes",
            },
            {
                "question": "What cheap, abundant material replaces lithium in the newly shipped grid batteries?",
                "options": ["Rock salt / Sodium", "Lead", "Cobalt", "Graphite"],
                "answer": "Rock salt / Sodium",
            },
            {
                "question": "What do cognitive scientists warn is lost in hyper-personalized feeds?",
                "options": ["Accidental serendipity for lateral thinking", "Reading speed", "Spelling accuracy", "Internet bandwidth"],
                "answer": "Accidental serendipity for lateral thinking",
            },
        ]

    today_edition = Edition(
        id=f"ed-{user.id}-today",
        user_id=user.id,
        articles=art_ids,
        editorial_note=editorial,
        three_things=three_things,
        recall_questions=questions,
        weather="☀️ 24°C, Crisp morning breeze over Islamabad",
        created_at=datetime.utcnow(),
    )
    insert_edition(today_edition)

    # Seed 2 historical editions for archive testing
    past_dates = [
        (datetime.utcnow() - timedelta(days=1), "Yesterday's Morning Edition", 85),
        (datetime.utcnow() - timedelta(days=2), "Midweek Synthesis Broadside", 90),
    ]
    for i, (p_date, p_title, recall_pct) in enumerate(past_dates):
        past_ed = Edition(
            id=f"ed-{user.id}-past-{i+1}",
            user_id=user.id,
            articles=art_ids[:4],
            editorial_note=f"Archived edition from {p_date.strftime('%B %d, %Y')}. Knowledge retention score: {recall_pct}%.",
            three_things=three_things,
            recall_questions=questions,
            weather="⛅ 22°C, Partially cloudy",
            created_at=p_date,
        )
        insert_edition(past_ed)

        # Seed sample interactions & recall results
        for art_id in art_ids[:3]:
            insert_interaction(
                Interaction(
                    user_id=user.id,
                    article_id=art_id,
                    dwell_time=48.5,
                    scroll_depth=0.88,
                    clicked_out=False,
                    saved=True,
                    timestamp=p_date,
                )
            )
        insert_recall_result(
            RecallResult(
                user_id=user.id,
                edition_id=past_ed.id,
                question="Sample recall prompt",
                correct=True,
                timestamp=p_date,
            )
        )


def seed_database() -> None:
    """Master seeding routine: inits tables, loads articles, personas, and editions."""
    init_db()
    articles = seed_articles_from_json()
    if not articles:
        articles = get_all_articles()

    users = seed_personas()
    for user in users:
        seed_editions_for_user(user, articles)

    logger.info("Database seeding complete!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    seed_database()
