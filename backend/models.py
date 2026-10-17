"""
Zok (ذوق) — Pydantic Models
Data transfer objects matching the database schema.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
import uuid


def _uid() -> str:
    return uuid.uuid4().hex[:12]


# ── User ──────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    name: str
    tagline: str = ""
    interests_vector: list[float] = Field(default_factory=list)
    reading_budget: int = 10


class User(BaseModel):
    id: str = Field(default_factory=_uid)
    name: str
    tagline: str = ""
    interests_vector: list[float] = Field(default_factory=list)
    reading_budget: int = 10
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Article ───────────────────────────────────────────────────────────────────

class ArticleCreate(BaseModel):
    title: str
    summary: str = ""
    content: str = ""
    source: str = ""
    source_url: str = ""
    category: str = ""
    tags: list[str] = Field(default_factory=list)
    importance_score: float = 0.5
    published_at: Optional[datetime] = None


class Article(BaseModel):
    id: str = Field(default_factory=_uid)
    title: str
    summary: str = ""
    content: str = ""
    source: str = ""
    source_url: str = ""
    category: str = ""
    tags: list[str] = Field(default_factory=list)
    importance_score: float = 0.5
    published_at: Optional[datetime] = None
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    cluster_id: str = ""
    embedding: list[float] = Field(default_factory=list)


# ── Edition ───────────────────────────────────────────────────────────────────

class EditionCreate(BaseModel):
    user_id: str
    articles: list[str] = Field(default_factory=list)
    editorial_note: str = ""
    three_things: list[str] = Field(default_factory=list)
    recall_questions: list[dict] = Field(default_factory=list)
    weather: str = "☀️ 32°C, Clear skies over Islamabad"


class Edition(BaseModel):
    id: str = Field(default_factory=_uid)
    user_id: str
    articles: list[str] = Field(default_factory=list)
    editorial_note: str = ""
    three_things: list[str] = Field(default_factory=list)
    recall_questions: list[dict] = Field(default_factory=list)
    weather: str = "☀️ 32°C, Clear skies over Islamabad"
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Interaction ───────────────────────────────────────────────────────────────

class Interaction(BaseModel):
    user_id: str
    article_id: str
    dwell_time: float = 0.0
    scroll_depth: float = 0.0
    clicked_out: bool = False
    saved: bool = False
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ── Recall ────────────────────────────────────────────────────────────────────

class RecallResult(BaseModel):
    user_id: str
    edition_id: str
    question: str
    correct: bool
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ── Onboarding ────────────────────────────────────────────────────────────────

class OnboardingInput(BaseModel):
    name: str
    tagline: str = ""
    description: str = ""
    reading_budget: int = 10


# ── Persona Switch ────────────────────────────────────────────────────────────

class PersonaSwitch(BaseModel):
    persona_id: str
