import os, sqlite3, datetime as dt
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import core

core.init()
core.refresh_bg()   # warms the verified news cache in the background

app = FastAPI(title="Zok · Your Personal Morning Paper")
if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

T = Jinja2Templates(directory="templates")

def me(req: Request):
    return core.user_by_token(req.cookies.get("zt"))

def go(uid: int, url="/paper"):
    r = RedirectResponse(url, 303)
    r.set_cookie("zt", core.new_session(uid), max_age=86400 * 60, httponly=True)
    return r

def pretty(day: str):
    try:
        return dt.date.fromisoformat(day).strftime("%A, %d %B %Y")
    except Exception:
        return day

@app.get("/")
def home(req: Request):
    if me(req): return RedirectResponse("/paper")
    return T.TemplateResponse(req, "landing.html", {"topics": core.TOPICS, "err": ""})

@app.post("/signup")
def signup(req: Request, name: str = Form(...), email: str = Form(...), password: str = Form(...),
           work: str = Form(""), bio: str = Form(""), minutes: int = Form(5),
           topics: list[str] = Form([]), preferred_sources: list[str] = Form([])):
    try:
        uid = core.make_user(
            email.lower().strip(),
            password,
            name.strip(),
            work.strip(),
            topics or ["world", "business", "technology"],
            minutes,
            bio=bio.strip(),
            preferred_sources=preferred_sources
        )
    except sqlite3.IntegrityError:
        return T.TemplateResponse(req, "landing.html", {
            "topics": core.TOPICS,
            "err": "An account with that email already exists. Please log in below."
        })
    return go(uid)

@app.get("/login")
def login_page(req: Request):
    if me(req): return RedirectResponse("/paper")
    return T.TemplateResponse(req, "login.html", {"err": ""})

@app.post("/login")
def login(req: Request, email: str = Form(...), password: str = Form(...)):
    uid = core.check_login(email.lower().strip(), password)
    return go(uid) if uid else T.TemplateResponse(req, "login.html", {"err": "Invalid email or password. Please try again."})

@app.get("/logout")
def logout():
    r = RedirectResponse("/", 303)
    r.delete_cookie("zt")
    return r

def get_ed(u, day=None, fresh=0):
    if day:
        ed = core.load(u["id"], day)
        return (day, ed) if ed else (None, None)
    return core.build(u["id"], bool(fresh))

@app.get("/today")
@app.get("/paper")
@app.get("/paper/{day}")

def paper(req: Request, day: str = None, mins: int = 0, fresh: int = 0):
    u = me(req)
    if not u: return RedirectResponse("/")
    day, ed = get_ed(u, day, fresh)
    if not ed: return RedirectResponse("/paper")
    mins = mins or u["minutes"] or 5
    story_count = core.MINS_TO_STORIES.get(mins, mins if mins > 5 else 8)
    today_str = dt.date.today().isoformat()
    return T.TemplateResponse(req, "paper.html", dict(
        u=u,
        ed=ed,
        day=day,
        date=pretty(day),
        stories=ed["stories"][:story_count],
        mins=mins,
        story_count=story_count,
        more=len(ed["stories"]) > story_count,
        is_today=(day == today_str),
        stats=core.stats(u["id"])
    ))

@app.get("/paper.pdf")
def pdf(req: Request, day: str = None, mins: int = 0):
    u = me(req)
    if not u: return RedirectResponse("/")
    day, ed = get_ed(u, day)
    mins = mins or u["minutes"] or 5
    story_count = core.MINS_TO_STORIES.get(mins, mins if mins > 5 else 8)
    html = T.get_template("pdf.html").render(
        u=u,
        ed=ed,
        date=pretty(day),
        stories=ed["stories"][:story_count],
        mins=mins
    )
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page()
            pg.set_content(html, wait_until="load")
            try: pg.evaluate("document.fonts.ready")
            except Exception: pass
            data = pg.pdf(
                format="A4",
                print_background=True,
                display_header_footer=True,
                header_template="<span></span>",
                footer_template='<div style="width:100%;font-size:8px;color:#8a8473;text-align:center;font-family:Georgia,serif">Zok · Personal Morning Paper · page <span class="pageNumber"></span> of <span class="totalPages"></span></div>',
                margin=dict(top="12mm", bottom="16mm", left="12mm", right="12mm")
            )
            b.close()
        return Response(data, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="zok-{day}.pdf"'})
    except Exception as e:
        print("PDF fallback:", e)
        return HTMLResponse(html + "<script>window.print()</script>")

@app.post("/api/dwell")
async def dwell(req: Request):
    u = me(req)
    d = await req.json()
    if u and d.get("aid") and d.get("seconds", 0) >= 15:
        core.learn(u["id"], d["aid"], "dwell")
        return {"ok": 1, "recorded": True}
    return {"ok": 1, "recorded": False}

@app.post("/api/event")
async def event(req: Request):
    u = me(req)
    d = await req.json()
    if u and d.get("action") in core.DELTA:
        core.learn(u["id"], d.get("aid", ""), d["action"])
    return {"ok": 1}


@app.get("/me")
def profile(req: Request):
    u = me(req)
    if not u: return RedirectResponse("/")
    return T.TemplateResponse(req, "me.html", dict(u=u, s=core.stats(u["id"])))

@app.get("/archive")
def archive(req: Request):
    u = me(req)
    if not u: return RedirectResponse("/")
    rows = []
    for d in core.days(u["id"]):
        ed = core.load(u["id"], d)
        lead_title = ed["stories"][0]["title"] if ed and ed.get("stories") else "Your Personal Paper"
        story_count = len(ed["stories"]) if ed and ed.get("stories") else 0
        rows.append((d, pretty(d), lead_title, story_count))
    return T.TemplateResponse(req, "archive.html", dict(u=u, rows=rows))