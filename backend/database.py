"""
Zok (ذوق) — SQLite Database Layer
Provides schema creation, connection management, and CRUD helpers.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Generator, Optional

from backend.config import DB_PATH
from backend.models import (
    Article, ArticleCreate, Edition, EditionCreate,
    Interaction, RecallResult, User, UserCreate,
)


# ── Schema ────────────────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    tagline     TEXT DEFAULT '',
    interests_vector TEXT DEFAULT '[]',
    reading_budget   INTEGER DEFAULT 10,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS articles (
    id              TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    summary         TEXT DEFAULT '',
    content         TEXT DEFAULT '',
    source          TEXT DEFAULT '',
    source_url      TEXT DEFAULT '',
    category        TEXT DEFAULT '',
    tags            TEXT DEFAULT '[]',
    importance_score REAL DEFAULT 0.5,
    published_at    TIMESTAMP,
    fetched_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    cluster_id      TEXT DEFAULT '',
    embedding       TEXT DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS editions (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    articles        TEXT DEFAULT '[]',
    editorial_note  TEXT DEFAULT '',
    three_things    TEXT DEFAULT '[]',
    recall_questions TEXT DEFAULT '[]',
    weather         TEXT DEFAULT '',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS interactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     TEXT NOT NULL,
    article_id  TEXT NOT NULL,
    dwell_time  REAL DEFAULT 0.0,
    scroll_depth REAL DEFAULT 0.0,
    clicked_out BOOLEAN DEFAULT 0,
    saved       BOOLEAN DEFAULT 0,
    timestamp   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id)    REFERENCES users(id),
    FOREIGN KEY (article_id) REFERENCES articles(id)
);

CREATE TABLE IF NOT EXISTS recall_results (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     TEXT NOT NULL,
    edition_id  TEXT NOT NULL,
    question    TEXT NOT NULL,
    correct     BOOLEAN DEFAULT 0,
    timestamp   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id)    REFERENCES users(id),
    FOREIGN KEY (edition_id) REFERENCES editions(id)
);

CREATE INDEX IF NOT EXISTS idx_articles_source_url ON articles(source_url);
CREATE INDEX IF NOT EXISTS idx_editions_user      ON editions(user_id);
CREATE INDEX IF NOT EXISTS idx_interactions_user   ON interactions(user_id);
"""


# ── Init & Connection ─────────────────────────────────────────────────────────

def init_db() -> None:
    """Create all tables if they don't already exist."""
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(_SCHEMA)
    conn.commit()
    conn.close()


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Context manager that yields a SQLite connection with Row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ts(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def _parse_ts(val: Any) -> Optional[datetime]:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    try:
        return datetime.fromisoformat(str(val))
    except (ValueError, TypeError):
        return None


def _json_dumps(obj: Any) -> str:
    return json.dumps(obj, default=str)


def _json_loads(val: Any, default: Any = None) -> Any:
    if val is None:
        return default if default is not None else []
    if isinstance(val, (list, dict)):
        return val
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return default if default is not None else []


# ── User CRUD ─────────────────────────────────────────────────────────────────

def create_user(user: User) -> User:
    with get_db() as db:
        db.execute(
            "INSERT OR REPLACE INTO users (id, name, tagline, interests_vector, reading_budget, created_at) VALUES (?,?,?,?,?,?)",
            (user.id, user.name, user.tagline, _json_dumps(user.interests_vector),
             user.reading_budget, _ts(user.created_at)),
        )
    return user


def get_user(user_id: str) -> Optional[User]:
    with get_db() as db:
        row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        return None
    return User(
        id=row["id"],
        name=row["name"],
        tagline=row["tagline"] or "",
        interests_vector=_json_loads(row["interests_vector"], []),
        reading_budget=row["reading_budget"] or 10,
        created_at=_parse_ts(row["created_at"]) or datetime.utcnow(),
    )


def get_all_users() -> list[User]:
    with get_db() as db:
        rows = db.execute("SELECT * FROM users").fetchall()
    return [
        User(
            id=r["id"], name=r["name"], tagline=r["tagline"] or "",
            interests_vector=_json_loads(r["interests_vector"], []),
            reading_budget=r["reading_budget"] or 10,
            created_at=_parse_ts(r["created_at"]) or datetime.utcnow(),
        )
        for r in rows
    ]


def update_user_vector(user_id: str, vector: list[float]) -> None:
    with get_db() as db:
        db.execute(
            "UPDATE users SET interests_vector = ? WHERE id = ?",
            (_json_dumps(vector), user_id),
        )


# ── Article CRUD ──────────────────────────────────────────────────────────────

def insert_article(article: Article) -> Article:
    with get_db() as db:
        db.execute(
            """INSERT OR IGNORE INTO articles
               (id, title, summary, content, source, source_url, category, tags,
                importance_score, published_at, fetched_at, cluster_id, embedding)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (article.id, article.title, article.summary, article.content,
             article.source, article.source_url, article.category,
             _json_dumps(article.tags), article.importance_score,
             _ts(article.published_at), _ts(article.fetched_at),
             article.cluster_id, _json_dumps(article.embedding)),
        )
    return article


def update_article(article: Article) -> None:
    with get_db() as db:
        db.execute(
            """UPDATE articles SET summary=?, tags=?, importance_score=?, embedding=?, cluster_id=?
               WHERE id=?""",
            (article.summary, _json_dumps(article.tags), article.importance_score,
             _json_dumps(article.embedding), article.cluster_id, article.id),
        )


def get_article(article_id: str) -> Optional[Article]:
    with get_db() as db:
        row = db.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
    if not row:
        return None
    return _row_to_article(row)


def get_all_articles() -> list[Article]:
    with get_db() as db:
        rows = db.execute("SELECT * FROM articles ORDER BY published_at DESC").fetchall()
    return [_row_to_article(r) for r in rows]


def article_exists_by_url(url: str) -> bool:
    with get_db() as db:
        row = db.execute("SELECT 1 FROM articles WHERE source_url = ?", (url,)).fetchone()
    return row is not None


def _row_to_article(row: sqlite3.Row) -> Article:
    return Article(
        id=row["id"],
        title=row["title"],
        summary=row["summary"] or "",
        content=row["content"] or "",
        source=row["source"] or "",
        source_url=row["source_url"] or "",
        category=row["category"] or "",
        tags=_json_loads(row["tags"], []),
        importance_score=row["importance_score"] or 0.5,
        published_at=_parse_ts(row["published_at"]),
        fetched_at=_parse_ts(row["fetched_at"]) or datetime.utcnow(),
        cluster_id=row["cluster_id"] or "",
        embedding=_json_loads(row["embedding"], []),
    )


# ── Edition CRUD ──────────────────────────────────────────────────────────────

def insert_edition(edition: Edition) -> Edition:
    with get_db() as db:
        db.execute(
            """INSERT OR REPLACE INTO editions
               (id, user_id, articles, editorial_note, three_things, recall_questions, weather, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (edition.id, edition.user_id, _json_dumps(edition.articles),
             edition.editorial_note, _json_dumps(edition.three_things),
             _json_dumps(edition.recall_questions), edition.weather,
             _ts(edition.created_at)),
        )
    return edition


def get_editions_for_user(user_id: str) -> list[Edition]:
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM editions WHERE user_id = ? ORDER BY created_at DESC", (user_id,)
        ).fetchall()
    return [_row_to_edition(r) for r in rows]


def get_edition(edition_id: str) -> Optional[Edition]:
    with get_db() as db:
        row = db.execute("SELECT * FROM editions WHERE id = ?", (edition_id,)).fetchone()
    if not row:
        return None
    return _row_to_edition(row)


def get_latest_edition(user_id: str) -> Optional[Edition]:
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM editions WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
            (user_id,),
        ).fetchone()
    if not row:
        return None
    return _row_to_edition(row)


def _row_to_edition(row: sqlite3.Row) -> Edition:
    return Edition(
        id=row["id"],
        user_id=row["user_id"],
        articles=_json_loads(row["articles"], []),
        editorial_note=row["editorial_note"] or "",
        three_things=_json_loads(row["three_things"], []),
        recall_questions=_json_loads(row["recall_questions"], []),
        weather=row["weather"] or "",
        created_at=_parse_ts(row["created_at"]) or datetime.utcnow(),
    )


# ── Interaction CRUD ──────────────────────────────────────────────────────────

def insert_interaction(interaction: Interaction) -> None:
    with get_db() as db:
        db.execute(
            """INSERT INTO interactions
               (user_id, article_id, dwell_time, scroll_depth, clicked_out, saved, timestamp)
               VALUES (?,?,?,?,?,?,?)""",
            (interaction.user_id, interaction.article_id, interaction.dwell_time,
             interaction.scroll_depth, int(interaction.clicked_out),
             int(interaction.saved), _ts(interaction.timestamp)),
        )


def get_interactions_for_user(user_id: str) -> list[Interaction]:
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM interactions WHERE user_id = ? ORDER BY timestamp DESC", (user_id,)
        ).fetchall()
    return [
        Interaction(
            user_id=r["user_id"], article_id=r["article_id"],
            dwell_time=r["dwell_time"] or 0.0, scroll_depth=r["scroll_depth"] or 0.0,
            clicked_out=bool(r["clicked_out"]), saved=bool(r["saved"]),
            timestamp=_parse_ts(r["timestamp"]) or datetime.utcnow(),
        )
        for r in rows
    ]


# ── Recall CRUD ───────────────────────────────────────────────────────────────

def insert_recall_result(result: RecallResult) -> None:
    with get_db() as db:
        db.execute(
            """INSERT INTO recall_results (user_id, edition_id, question, correct, timestamp)
               VALUES (?,?,?,?,?)""",
            (result.user_id, result.edition_id, result.question,
             int(result.correct), _ts(result.timestamp)),
        )


def get_recall_results_for_user(user_id: str) -> list[RecallResult]:
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM recall_results WHERE user_id = ? ORDER BY timestamp DESC", (user_id,)
        ).fetchall()
    return [
        RecallResult(
            user_id=r["user_id"], edition_id=r["edition_id"],
            question=r["question"], correct=bool(r["correct"]),
            timestamp=_parse_ts(r["timestamp"]) or datetime.utcnow(),
        )
        for r in rows
    ]


def is_db_empty() -> bool:
    """Return True if the users table has no rows."""
    with get_db() as db:
        row = db.execute("SELECT COUNT(*) as cnt FROM users").fetchone()
    return row["cnt"] == 0


def update_user_budget(user_id: str, budget: int) -> None:
    with get_db() as db:
        db.execute("UPDATE users SET reading_budget = ? WHERE id = ?", (budget, user_id))


def update_article_embedding(article_id: str, embedding: list[float]) -> None:
    with get_db() as db:
        db.execute(
            "UPDATE articles SET embedding = ? WHERE id = ?",
            (_json_dumps(embedding), article_id),
        )


# ── Aliases ───────────────────────────────────────────────────────────────────
insert_user = create_user
get_user_by_id = get_user
get_article_by_id = get_article
get_edition_by_id = get_edition
get_latest_edition_for_user = get_latest_edition
update_user_interests = update_user_vector

