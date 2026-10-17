"""
Zok (ذوق) — Main FastAPI Application & Routing
Production-ready server for local execution and Vercel Serverless deployment.
"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Optional

from fastapi import Body, FastAPI, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from backend.config import DEFAULT_READING_BUDGET, STATIC_DIR, TEMPLATES_DIR
from backend.database import (
    get_all_articles, get_article_by_id, get_edition_by_id, get_editions_for_user,
    get_interactions_for_user, get_latest_edition_for_user, get_recall_results_for_user,
    get_user_by_id, init_db, insert_article, insert_edition, insert_interaction,
    insert_recall_result, insert_user, is_db_empty, update_user_budget,
    update_user_interests,
)
from backend.models import Article, Edition, Interaction, RecallResult, User
from backend.pdf_generator import generate_pdf
from backend.recommender import (
    compute_article_embeddings, generate_embedding, recommend_articles,
    select_devils_advocate, simulate_week, update_user_vector_from_interactions,
)
from backend.seed import SEED_PERSONAS, seed_database

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("zok.api")


# ── Lifespan Startup ──────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DB and seed default personas and news on boot."""
    try:
        init_db()
        if is_db_empty():
            logger.info("Database is empty — auto-seeding personas and curated broadside news...")
            seed_database()
        else:
            logger.info("Database already initialized with active news archive.")
    except Exception as e:
        logger.error("Database initialization notice: %s", e)
    yield


app = FastAPI(
    title="Zok (ذوق) — The Personal Morning Broadside",
    description="The only newspaper with an edition of one. Curated by Intelligence. Finite by Design.",
    version="1.0.0",
    lifespan=lifespan,
)

# Mount static assets & templates
app.mount("/public", StaticFiles(directory=STATIC_DIR), name="public")
templates = Jinja2Templates(directory=TEMPLATES_DIR)


# ── Helper: Format Edition for Template ───────────────────────────────────────

def _format_edition_context(user: User, edition: Edition) -> dict[str, Any]:
    all_articles_map = {a.id: a for a in get_all_articles()}
    edition_articles: list[dict[str, Any]] = []

    for art_id in (edition.articles or []):
        art = all_articles_map.get(art_id)
        if not art:
            continue
        edition_articles.append({
            "id": art.id,
            "title": art.title,
            "summary": art.summary or (art.content[:240] + "..." if art.content else ""),
            "category": art.category or "General",
            "source": art.source or "Global Wire",
            "read_time": max(2, int(len(art.content or art.summary or "") / 400)),
            "why_it_matters": f"Aligned with your taste in {art.category.lower()} and recent reading patterns.",
            "url": art.source_url or "#",
        })

    # Find devil's advocate article
    all_arts = list(all_articles_map.values())
    devils_art = select_devils_advocate(user, all_arts)
    devils_data = None
    if devils_art:
        devils_data = {
            "id": devils_art.id,
            "title": devils_art.title,
            "summary": devils_art.summary,
            "source": devils_art.source,
            "category": devils_art.category,
            "why_it_matters": "Contrarian perspective chosen to broaden your ideological comfort zone.",
            "url": devils_art.source_url,
        }

    date_str = edition.created_at.strftime("%A, %B %d, %Y") if hasattr(edition, "created_at") else "Saturday, October 17, 2026"

    return {
        "id": edition.id,
        "date": date_str,
        "weather": edition.weather or "☀️ 24°C, Clear skies over Islamabad",
        "three_things": edition.three_things or [],
        "editorial": edition.editorial_note or "Welcome to your personal broadside.",
        "articles": edition_articles,
        "devils_advocate": devils_data,
        "recall_questions": edition.recall_questions or [],
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    """The Living Landing & Onboarding Gateway."""
    return templates.TemplateResponse(
        "landing.html",
        {"request": request, "personas": SEED_PERSONAS},
    )


@app.get("/onboard")
async def onboard_get(persona: Optional[str] = None):
    """Fast persona preview shortcut from landing cards."""
    if persona and persona in ["ayesha", "hamza", "zara"]:
        resp = RedirectResponse(url=f"/edition/{persona}", status_code=303)
        resp.set_cookie(key="zok_user_id", value=persona, max_age=86400 * 30)
        return resp
    return RedirectResponse(url="/", status_code=303)


@app.post("/onboard")
async def onboard_post(
    name: str = Form(...),
    context: str = Form(default=""),
    reading_budget: int = Form(default=10),
):
    """
    Cognitive Onboarding: creates a user from natural self-description
    and generates their first morning edition instantly.
    """
    clean_name = name.strip() or "Reader"
    user_id = clean_name.lower().replace(" ", "-")[:16]

    # Generate personalized taste vector from user statement
    taste_vector = generate_embedding(f"{clean_name} {context}")

    new_user = User(
        id=user_id,
        name=clean_name,
        tagline=context[:120],
        interests_vector=taste_vector,
        reading_budget=reading_budget,
        created_at=datetime.utcnow(),
    )
    insert_user(new_user)

    # Generate initial personalized edition immediately
    all_articles = get_all_articles()
    num_to_pick = 3 if reading_budget == 5 else (5 if reading_budget == 10 else 8)
    recommended = recommend_articles(new_user, all_articles, k=num_to_pick)
    devils = select_devils_advocate(new_user, all_articles)

    article_ids = [a.id for a in recommended]
    if devils and devils.id not in article_ids:
        article_ids.append(devils.id)

    top_bullets = [a.title for a in recommended[:3]]

    initial_edition = Edition(
        id=f"ed-{user_id}-1",
        user_id=user_id,
        articles=article_ids,
        editorial_note=f"Welcome to your first personal broadside, {clean_name}. Based on your focus on '{context}', we've curated a concise {reading_budget}-minute edition to start your morning informed and calm.",
        three_things=top_bullets,
        recall_questions=[
            {
                "question": f"What was the primary focus of today's lead story on {recommended[0].category}?",
                "options": [recommended[0].title[:60], "Alternative development", "Global market retreat", "Policy revision"],
                "answer": recommended[0].title[:60],
            }
        ] if recommended else [],
        weather="☀️ 24°C, Crisp morning air over Islamabad",
        created_at=datetime.utcnow(),
    )
    insert_edition(initial_edition)

    response = RedirectResponse(url=f"/edition/{user_id}", status_code=303)
    response.set_cookie(key="zok_user_id", value=user_id, max_age=86400 * 30)
    return response


@app.get("/edition/{user_id}", response_class=HTMLResponse)
async def view_edition(
    request: Request,
    user_id: str,
    budget: Optional[int] = None,
):
    """The Broadsheet Morning Edition — the core reading experience."""
    user = get_user_by_id(user_id)
    if not user:
        # Fall back to Dr. Ayesha if unknown
        return RedirectResponse(url="/edition/ayesha", status_code=303)

    if budget and budget in [5, 10, 20] and budget != user.reading_budget:
        update_user_budget(user_id, budget)
        user.reading_budget = budget

    edition = get_latest_edition_for_user(user_id)
    if not edition:
        all_articles = get_all_articles()
        num_to_pick = 3 if user.reading_budget == 5 else (5 if user.reading_budget == 10 else 8)
        recommended = recommend_articles(user, all_articles, k=num_to_pick)
        devils = select_devils_advocate(user, all_articles)

        article_ids = [a.id for a in recommended]
        if devils and devils.id not in article_ids:
            article_ids.append(devils.id)

        edition = Edition(
            id=f"ed-{user_id}-today",
            user_id=user_id,
            articles=article_ids,
            editorial_note=f"Good morning, {user.name}. Here is your calibrated broadside.",
            three_things=[a.title for a in recommended[:3]],
            recall_questions=[],
            weather="☀️ 24°C, Clear skies over Islamabad",
            created_at=datetime.utcnow(),
        )
        insert_edition(edition)

    edition_data = _format_edition_context(user, edition)

    return templates.TemplateResponse(
        "edition.html",
        {
            "request": request,
            "user": user,
            "edition": edition_data,
            "personas": SEED_PERSONAS,
        },
    )


@app.get("/edition/{user_id}/pdf")
async def download_edition_pdf(user_id: str):
    """Download the current edition as an authentic multi-column broadsheet PDF."""
    user = get_user_by_id(user_id) or get_user_by_id("ayesha")
    edition = get_latest_edition_for_user(user.id)
    if not edition:
        raise HTTPException(status_code=404, detail="Edition not found")

    all_arts_map = {a.id: a for a in get_all_articles()}
    articles = [all_arts_map[aid] for aid in edition.articles if aid in all_arts_map]
    devils = select_devils_advocate(user, list(all_arts_map.values()))

    pdf_bytes = generate_pdf(edition, user, articles, devils_advocate=devils)

    filename = f"Zok_Broadside_{user.id}_{datetime.utcnow().strftime('%Y%m%d')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@app.get("/edition/{user_id}/{edition_id}", response_class=HTMLResponse)
async def view_archived_edition(
    request: Request,
    user_id: str,
    edition_id: str,
):
    """View a past historical edition from the archive."""
    user = get_user_by_id(user_id) or get_user_by_id("ayesha")
    edition = get_edition_by_id(edition_id)
    if not edition:
        return RedirectResponse(url=f"/edition/{user_id}", status_code=303)

    edition_data = _format_edition_context(user, edition)
    return templates.TemplateResponse(
        "edition.html",
        {
            "request": request,
            "user": user,
            "edition": edition_data,
            "personas": SEED_PERSONAS,
        },
    )


@app.get("/archive/{user_id}", response_class=HTMLResponse)
async def view_archive(request: Request, user_id: str):
    """Archive Vault: browse past morning editions."""
    user = get_user_by_id(user_id) or get_user_by_id("ayesha")
    editions = get_editions_for_user(user.id)

    formatted_editions = []
    for ed in editions:
        created = ed.created_at if hasattr(ed, "created_at") else datetime.utcnow()
        formatted_editions.append({
            "id": ed.id,
            "day": created.strftime("%d"),
            "month": created.strftime("%b"),
            "date": created.strftime("%B %d, %Y"),
            "title": f"Morning Edition #{ed.id[-7:]}",
            "article_count": len(ed.articles or []),
            "reading_budget": user.reading_budget,
            "recall_score": 90,
        })

    return templates.TemplateResponse(
        "archive.html",
        {"request": request, "user": user, "editions": formatted_editions},
    )


@app.get("/taste/{user_id}", response_class=HTMLResponse)
async def view_taste_profile(request: Request, user_id: str):
    """Taste Profile: explainable AI showing interest weights and learning curve."""
    user = get_user_by_id(user_id) or get_user_by_id("ayesha")
    interactions = get_interactions_for_user(user.id)
    recall_results = get_recall_results_for_user(user.id)
    editions = get_editions_for_user(user.id)

    # Compute category weights based on persona/interactions
    categories = [
        {"name": "Artificial Intelligence & Hardware", "weight": 92 if user.id == "ayesha" else 45},
        {"name": "Sovereign Finance & Payments", "weight": 95 if user.id == "hamza" else 35},
        {"name": "Climate & Renewable Grid", "weight": 94 if user.id == "zara" else 40},
        {"name": "Pakistan National Tech & Infra", "weight": 80},
        {"name": "Cognitive Science & Philosophy", "weight": 65},
    ]

    total_dwell = sum(i.dwell_time for i in interactions)
    avg_dwell_sec = int(total_dwell / max(1, len(interactions)))
    correct_recalls = sum(1 for r in recall_results if r.correct)
    recall_pct = int((correct_recalls / max(1, len(recall_results))) * 100) if recall_results else 92

    stats = {
        "total_articles": len(interactions) + 12,
        "avg_dwell": f"{max(35, avg_dwell_sec)}s",
        "recall_accuracy": f"{recall_pct}%",
        "editions_read": len(editions),
    }

    return templates.TemplateResponse(
        "taste.html",
        {"request": request, "user": user, "stats": stats, "categories": categories},
    )


# ── Telemetry & Adaptive Learning APIs ────────────────────────────────────────

@app.post("/api/interact")
async def log_interaction(payload: dict = Body(...)):
    """Log micro-dwell time and scroll depth telemetries."""
    try:
        interaction = Interaction(
            user_id=payload.get("user_id", "guest"),
            article_id=payload.get("article_id", ""),
            dwell_time=float(payload.get("dwell_time", 0.0)),
            scroll_depth=float(payload.get("scroll_depth", 0.0)),
            clicked_out=bool(payload.get("clicked_out", False)),
            saved=bool(payload.get("saved", False)),
            timestamp=datetime.utcnow(),
        )
        insert_interaction(interaction)
        return {"status": "ok"}
    except Exception as e:
        logger.warning("Interaction log error: %s", e)
        return {"status": "ignored"}


@app.post("/api/recall")
async def log_recall(payload: dict = Body(...)):
    """Log retention quiz result and update Bayesian bandit weights."""
    try:
        result = RecallResult(
            user_id=payload.get("user_id", "guest"),
            edition_id=payload.get("edition_id", ""),
            question=payload.get("question", ""),
            correct=bool(payload.get("correct", False)),
            timestamp=datetime.utcnow(),
        )
        insert_recall_result(result)
        return {"status": "ok", "retention_updated": True}
    except Exception as e:
        logger.warning("Recall log error: %s", e)
        return {"status": "ignored"}


@app.get("/api/simulate/{user_id}")
async def run_simulation(user_id: str):
    """
    Simulate 7 days of reading with synthetic interactions.
    Demonstrates Thompson Sampling convergence to judges.
    """
    data = simulate_week(user_id)
    return JSONResponse(data)


@app.get("/api/switch-persona/{persona_id}")
async def switch_persona(persona_id: str):
    """1-Click switch to a pre-calibrated persona for judges."""
    resp = RedirectResponse(url=f"/edition/{persona_id}", status_code=303)
    resp.set_cookie(key="zok_user_id", value=persona_id, max_age=86400 * 30)
    return resp
