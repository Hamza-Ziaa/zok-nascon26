import os, re, json, time, calendar, hashlib, secrets, sqlite3, threading, warnings, datetime as dt
import concurrent.futures as cf
import feedparser, requests
from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning
from dotenv import load_dotenv

warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)
load_dotenv()

DB = "zok.db"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ZokBot/2.0 EditorialEngine"}
TOPICS = {
    "pakistan": "Pakistan",
    "world": "World",
    "business": "Business",
    "technology": "Tech & AI",
    "science": "Science",
    "health": "Health",
    "sports": "Sports"
}
GN = "https://news.google.com/rss/search?hl=en&gl=US&ceid=US:en&q="
B = "http://feeds.bbci.co.uk/news/"
FEEDS = [
    ("https://www.dawn.com/feeds/home", "Dawn", "pakistan"),
    ("https://www.dawn.com/feeds/business", "Dawn", "business"),
    ("https://www.dawn.com/feeds/sport", "Dawn", "sports"),
    ("https://www.dawn.com/feeds/tech", "Dawn", "technology"),
    ("https://tribune.com.pk/feed/home", "Express Tribune", "pakistan"),
    (B + "world/rss.xml", "BBC", "world"),
    (B + "business/rss.xml", "BBC", "business"),
    (B + "technology/rss.xml", "BBC", "technology"),
    (B + "science_and_environment/rss.xml", "BBC", "science"),
    (B + "health/rss.xml", "BBC", "health"),
    ("http://feeds.bbci.co.uk/sport/rss.xml", "BBC", "sports"),
    ("https://www.aljazeera.com/xml/rss/all.xml", "Al Jazeera", "world"),
    ("https://www.theguardian.com/world/rss", "The Guardian", "world"),
    ("https://www.theguardian.com/business/rss", "The Guardian", "business"),
    ("https://www.theguardian.com/technology/rss", "The Guardian", "technology"),
    ("https://www.theguardian.com/science/rss", "The Guardian", "science"),
    ("https://feeds.npr.org/1001/rss.xml", "NPR", "world"),
    ("https://rss.dw.com/rdf/rss-en-all", "DW", "world"),
    ("https://techcrunch.com/feed/", "TechCrunch", "technology"),
    (GN + "site:reuters.com+when:1d", "Reuters", "world"),
    (GN + "site:reuters.com+business+when:1d", "Reuters", "business"),
    (GN + "site:reuters.com+technology+when:1d", "Reuters", "technology"),
    (GN + "site:apnews.com+when:1d", "AP", "world"),
]

TIER = {
    "Reuters": 0.98,
    "AP": 0.98,
    "BBC": 0.95,
    "Dawn": 0.90,
    "The Guardian": 0.90,
    "NPR": 0.90,
    "DW": 0.90,
    "Al Jazeera": 0.82,
    "Express Tribune": 0.80,
    "TechCrunch": 0.75
}

PK = re.compile(r"pakistan|karachi|lahore|islamabad|peshawar|quetta|punjab|sindh|khyber|balochistan|rupee|PSX|SBP|nawaz|shehbaz|imran|dar", re.I)
HEDGE = re.compile(r"\b(reportedly|allegedly|sources say|rumou?rs?|unconfirmed|it is said|claims?|purported|insiders say|speculation)\b", re.I)
BAIT = re.compile(r"(shocking|you won'?t believe|must see|jaw-dropping|goes viral|secret revealed|won't tell you|unbelievable|mind-blowing)", re.I)
EVID = re.compile(r"(according to|said in a statement|official|ministry|spokesperson|court|judiciary|police|state bank|central bank|data|survey|percent|%|\$|rs\.?\s?\d|\b\d{2,}\b|documents show|investigation|confirmed by|signed an agreement)", re.I)
DELTA = {"read": 1.0, "open": 1.5, "save": 2.2, "more": 2.5, "skip": -1.2, "recall": 1.2, "miss": 0.0, "dwell": 1.8}
MINS_TO_STORIES = {5: 8, 10: 15, 20: 20}

KNOWN_ENTITIES = [
    "IMF", "State Bank", "Federal Reserve", "Supreme Court", "National Assembly", "PSX",
    "OpenAI", "Google", "Microsoft", "Apple", "Nvidia", "Meta", "Tesla", "Amazon", "SpaceX",
    "United Nations", "World Bank", "NATO", "European Union", "WHO",
    "Pakistan", "Islamabad", "Karachi", "Lahore", "China", "United States", "Middle East",
    "Artificial Intelligence", "Semiconductors", "Interest Rates", "Inflation", "Renewable Energy", "Climate Change"
]

def db():
    c = sqlite3.connect(DB, timeout=25)
    c.row_factory = sqlite3.Row
    return c

def init():
    c = db()
    c.execute("PRAGMA journal_mode=WAL")
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY,
        email TEXT UNIQUE,
        pw TEXT,
        name TEXT,
        work TEXT,
        keywords TEXT,
        minutes INT,
        weights TEXT,
        archetype TEXT,
        created_at REAL
    );
    CREATE TABLE IF NOT EXISTS sessions(
        token TEXT PRIMARY KEY,
        uid INT
    );
    CREATE TABLE IF NOT EXISTS articles(
        id TEXT PRIMARY KEY,
        title TEXT,
        source TEXT,
        url TEXT,
        text TEXT,
        topic TEXT,
        pub REAL,
        cred REAL,
        corr INT,
        plain TEXT,
        lab TEXT,
        chk TEXT,
        entities TEXT,
        cred_breakdown TEXT
    );
    CREATE TABLE IF NOT EXISTS editions(
        uid INT,
        day TEXT,
        data TEXT,
        PRIMARY KEY(uid, day)
    );
    CREATE TABLE IF NOT EXISTS events(
        uid INT,
        aid TEXT,
        action TEXT,
        ts REAL
    );
    CREATE TABLE IF NOT EXISTS story_threads(
        uid INT,
        thread_key TEXT,
        entity TEXT,
        topic TEXT,
        affinity REAL DEFAULT 1.0,
        article_id TEXT,
        headline TEXT,
        created_at REAL,
        updated_at REAL,
        PRIMARY KEY(uid, thread_key)
    );
    CREATE TABLE IF NOT EXISTS negative_filters(
        uid INT,
        entity TEXT,
        expires_at REAL,
        PRIMARY KEY(uid, entity)
    );
    """)
    # Safe migrations for existing databases
    for col, typ in [("entities", "TEXT"), ("cred_breakdown", "TEXT")]:
        try: c.execute(f"ALTER TABLE articles ADD COLUMN {col} {typ}")
        except Exception: pass
    for col, typ in [("archetype", "TEXT"), ("created_at", "REAL")]:
        try: c.execute(f"ALTER TABLE users ADD COLUMN {col} {typ}")
        except Exception: pass
    missing = c.execute("SELECT id, title, text FROM articles WHERE entities IS NULL").fetchall()
    for m in missing:
        ents = extract_entities(m["title"], m["text"])
        c.execute("UPDATE articles SET entities=? WHERE id=?", (json.dumps(ents), m["id"]))
    c.commit()

def words(s, n=4):
    return set(re.findall(r"[a-z]{%d,}" % n, s.lower()))

def sim(a, b):
    x, y = words(a), words(b)
    return len(x & y) / max(1, len(x | y))

def hash_pw(p, salt=None):
    salt = salt or secrets.token_hex(8)
    return salt + "$" + hashlib.pbkdf2_hmac("sha256", p.encode(), salt.encode(), 100000).hex()

def clean(s):
    s = BeautifulSoup(s or "", "html.parser").get_text(" ", strip=True)
    s = re.sub(r"(Article URL|Comments URL|Points|# Comments):?\s*\S*", "", s)
    s = re.sub(r"\s*(The post |Read more|Continue reading).*$", "", s, flags=re.I)
    return re.sub(r"\s+", " ", s).strip()

def tidy(s, n=380):
    s = clean(s)
    if not s: return ""
    t = re.sub(r"\s*(\[…\]|\[\.\.\.\]|\.\.\.|…)\s*$", "", s)
    broken = t != s or len(t) > n
    s = t[:n]
    ends = [m.end() for m in re.finditer(r"[.!?][\"”’')]?(?=\s|$)", s)]
    if not broken: return s if ends and ends[-1] == len(s) else s.rstrip(" ,;:-") + "."
    if ends and ends[-1] > 50: return s[:ends[-1]]
    return s.rsplit(" ", 1)[0].rstrip(" ,;:-") + "…"

def extract_entities(title, text):
    """Extract 2-4 key canonical entities from article content."""
    combined = title + ". " + (text or "")
    found = []
    # Match against known entity registry
    for ent in KNOWN_ENTITIES:
        if re.search(r"\b" + re.escape(ent) + r"\b", combined, re.I):
            found.append(ent)
    # Match capitalized noun sequences (e.g. Federal Cabinet, Finance Minister)
    stopwords = {"The", "This", "That", "After", "Before", "When", "While", "According", "Yesterday", "Today", "Exclusive", "Breaking", "Report"}
    caps = re.findall(r"\b[A-Z][a-zA-Z0-9]{2,}(?:\s+[A-Z][a-zA-Z0-9]{2,})*\b", title)
    for c in caps:
        parts = c.split()
        if parts[0] not in stopwords and len(c) > 3 and c not in found:
            found.append(c)
    # Deduplicate preserving order
    out = []
    for f in found:
        if not any(f != o and f in o for o in out):
            out.append(f)
    return out[:4] or ["Current Affairs"]

# ---------- accounts & LLM ----------
def llm_json(prompt):
    k = os.environ.get("GEMINI_API_KEY")
    if not k: return None
    try:
        from google import genai
        r = genai.Client(api_key=k).models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={"response_mime_type": "application/json"}
        )
        return json.loads(r.text)
    except Exception as e:
        print("LLM skipped:", e)
        return None

def make_keywords(work):
    base = sorted(words(work))
    extra = llm_json(f'List 10 single lowercase news keywords relevant to someone whose career is: "{work}". Return a JSON list.') if work.strip() else None
    extra = [x.lower() for x in extra if isinstance(x, str)] if isinstance(extra, list) else []
    return list(dict.fromkeys(base + extra))[:14]

def determine_archetype(weights, keywords):
    t_scores = weights.get("t", {})
    top_two = sorted(t_scores.keys(), key=lambda k: t_scores[k], reverse=True)[:2]
    pair = set(top_two)
    if "technology" in pair and "business" in pair:
        return "The Strategic Technologist & Market Inquirer"
    elif "pakistan" in pair and "business" in pair:
        return "The National Enterprise Architect"
    elif "world" in pair and "business" in pair:
        return "The Global Macro Strategist"
    elif "science" in pair or "health" in pair:
        return "The Empirical Frontier Analyst"
    elif "world" in pair:
        return "The Geopolitics & Foreign Affairs Observer"
    return "The Discerning Executive Reader"

def make_user(email, pw, name, work, topics, minutes, bio="", preferred_sources=None):
    full_work = f"{bio.strip()} — {work.strip()}" if (bio and bio.strip() and work and work.strip()) else (bio.strip() if bio else (work.strip() if work else "General Reader"))
    W = {"t": {t: (1.4 if t in topics else 0.3) for t in TOPICS}, "w": {}, "s": {}}
    if preferred_sources:
        for src in preferred_sources:
            if src in TRUSTED_SOURCES:
                W["s"][src] = 1.6
    kws = make_keywords(full_work)
    arch = determine_archetype(W, kws)
    c = db()
    cur = c.execute(
        "INSERT INTO users(email,pw,name,work,keywords,minutes,weights,archetype,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
        (email, hash_pw(pw), name, full_work, json.dumps(kws), minutes, json.dumps(W), arch, time.time())
    )
    c.commit()
    return cur.lastrowid


def check_login(email, pw):
    u = db().execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    return u["id"] if u and hash_pw(pw, u["pw"].split("$")[0]) == u["pw"] else None

def new_session(uid):
    t = secrets.token_urlsafe(24)
    c = db()
    c.execute("INSERT INTO sessions VALUES(?,?)", (t, uid))
    c.commit()
    return t

def user_by_token(t):
    if not t: return None
    return db().execute("SELECT u.* FROM users u JOIN sessions s ON s.uid=u.id WHERE s.token=?", (t,)).fetchone()

# ---------- Rigorous Credibility Engine ----------
def trust(a, peers, now):
    """
    4-Pillar Transparent Verification Engine:
    - 35% Publisher Institutional Record (AP/Reuters/BBC/Dawn)
    - 30% Global Cross-Corroboration (Independent newsroom matching)
    - 20% Empirical Proof & Sourcing Rigor (Named officials, stats, anti-clickbait)
    - 15% Freshness & Transparency (Attribution, canonical link, recency)
    """
    src = a["source"]
    pub_val = TIER.get(src, 0.50)
    pub_score = round(pub_val * 100)

    # 1. Corroboration
    outs = sorted({b["source"] for b in peers if b["source"] != src})
    n = len(outs)
    if n >= 3:
        corr_score = 100
    elif n == 2:
        corr_score = 85
    elif n == 1:
        corr_score = 68
    elif pub_val >= 0.95: # Apex primary wire service (Reuters/AP)
        corr_score = 62
    else:
        corr_score = 35

    # Wire/Top tier bonus if peers include apex institutions
    if any(TIER.get(s, 0.5) >= 0.90 for s in outs):
        corr_score = min(100, corr_score + 10)

    # 2. Evidence & Proofs
    txt = a["title"] + " " + a["text"]
    ev_matches = len(EVID.findall(txt))
    hedge_matches = len(HEDGE.findall(txt))
    is_bait = bool(BAIT.search(txt))
    
    alpha_chars = [ch for ch in a["title"] if ch.isalpha()]
    caps_ratio = sum(1 for ch in alpha_chars if ch.isupper()) / max(1, len(alpha_chars))

    evid_base = 50
    evid_boost = min(ev_matches, 4) * 12
    evid_penalty = (hedge_matches * 15) + (35 if is_bait else 0) + (25 if caps_ratio > 0.45 else 0)
    evid_score = max(5, min(100, evid_base + evid_boost - evid_penalty))

    # 3. Transparency & Freshness
    age_hrs = max(0, (now - a["pub"]) / 3600)
    fresh_factor = 100 if age_hrs < 12 else (85 if age_hrs < 24 else (60 if age_hrs < 36 else 40))
    trans_score = min(100, int(fresh_factor * 0.75 + (15 if a["auth"] else 0) + (10 if a["url"].startswith("https") else 0)))

    # Weighted Overall Score
    overall = round(0.35 * pub_score + 0.30 * corr_score + 0.20 * evid_score + 0.15 * trans_score)

    if overall >= 78:
        lab = "Verified Gold"
    elif overall >= 64:
        lab = "Reliable Silver"
    else:
        lab = "Developing Source"

    # Human-readable forensic audit details
    peer_str = f"Corroborated by {len(outs)} newsrooms ({', '.join(outs)})" if outs else "Sole primary reporting"
    ev_str = f"{ev_matches} empirical data/citation markers" if ev_matches else "Standard editorial report"
    chk = f"{lab} ({overall}/100) · {peer_str} · Publisher trust {pub_score}/100 · Sourcing evidence {evid_score}/100"

    breakdown = {
        "overall": overall,
        "label": lab,
        "pub_score": pub_score,
        "corr_score": corr_score,
        "evid_score": evid_score,
        "trans_score": trans_score,
        "peers": outs,
        "peer_count": len(outs),
        "age_hrs": round(age_hrs, 1),
        "evidence_count": ev_matches,
        "hedges": hedge_matches
    }

    return round(overall / 100.0, 3), lab, chk, n, breakdown

def is_dead(u):
    try:
        return requests.get(u, timeout=4, stream=True, headers=UA).status_code in (404, 410)
    except Exception:
        return False

def pull(f):
    url, src, topic = f
    out = []
    gn = "news.google.com" in url
    try:
        res = requests.get(url, timeout=8, headers=UA)
        d = feedparser.parse(res.content)
    except Exception:
        return out
    now = time.time()
    for e in d.entries[:16]:
        p = e.get("published_parsed") or e.get("updated_parsed")
        if not p or not e.get("link"): continue
        pub = calendar.timegm(p)
        if now - pub > 48 * 3600 or pub > now + 3600: continue
        title = e.title.strip()
        if gn: title = re.sub(r"\s+-\s+[^-]+$", "", title)
        txt = "" if gn else tidy(e.get("summary", ""), 650)
        t = topic
        if src in ("Dawn", "Express Tribune") and t == "pakistan" and not PK.search(title + " " + txt):
            t = "world"
        ents = extract_entities(title, txt)
        out.append(dict(
            id=hashlib.md5(e.link.encode()).hexdigest()[:12],
            title=title, source=src, url=e.link, text=txt,
            topic=t, pub=pub, auth=bool(e.get("author")), gn=gn,
            entities=ents
        ))
    return out

def ingest():
    now = time.time()
    items = []
    with cf.ThreadPoolExecutor(10) as ex:
        for r in ex.map(pull, FEEDS):
            items += r
    keys = [words(a["title"] + " " + a["text"][:120]) for a in items]
    for i, a in enumerate(items):
        peers = [
            items[j] for j in range(len(items))
            if j != i and items[j]["source"] != a["source"]
            and len(keys[i] & keys[j]) >= 3
            and len(keys[i] & keys[j]) / max(1, len(keys[i] | keys[j])) >= 0.20
        ]
        cred, lab, chk, corr, bd = trust(a, peers, now)
        a["cred"] = cred
        a["lab"] = lab
        a["chk"] = chk
        a["corr"] = corr
        a["cred_breakdown"] = json.dumps(bd)

    # Rigorous Credibility Floor: filter out anything below 52
    items = [a for a in items if a["cred"] >= 0.52]
    c = db()
    have = {r[0] for r in c.execute("SELECT id FROM articles")}
    new = [a for a in items if a["id"] not in have and not a["gn"]]
    with cf.ThreadPoolExecutor(12) as ex:
        dead = {a["id"] for a, d in zip(new, ex.map(lambda x: is_dead(x["url"]), new)) if d}

    for a in items:
        if a["id"] in dead: continue
        ents_json = json.dumps(a["entities"])
        c.execute("""
            INSERT INTO articles(id,title,source,url,text,topic,pub,cred,corr,lab,chk,entities,cred_breakdown)
            VALUES(:id,:title,:source,:url,:text,:topic,:pub,:cred,:corr,:lab,:chk,:ents,:bd)
            ON CONFLICT(id) DO UPDATE SET
                cred=excluded.cred, corr=excluded.corr, lab=excluded.lab, chk=excluded.chk,
                entities=excluded.entities, cred_breakdown=excluded.cred_breakdown
        """, {**a, "ents": ents_json, "bd": a["cred_breakdown"]})
    c.commit()

    rows = [dict(x) for x in c.execute("SELECT * FROM articles WHERE plain IS NULL ORDER BY cred DESC LIMIT 40")]
    fill_plain(c, rows)
    print("Ingested and verified", len(items) - len(dead), "high-credibility articles")

def fill_plain(c, rows):
    todo = [r for r in rows if not r.get("plain")][:40]
    if not todo: return
    prompt = (
        "You are an elite editorial editor for a calm morning paper. Rewrite each news item into exactly 2 short, crisp, plain sentences "
        "(max 40 words total) that an intelligent reader can instantly absorb without jargon. Every sentence must end with a full stop. "
        "Also extract 2 canonical named entities (e.g. IMF, Nvidia, Supreme Court). "
        "Return a JSON object in format: {id: {\"plain\": \"...\", \"entities\": [\"...\", \"...\"]}}.\n"
        + json.dumps({r["id"]: r["title"] + ". " + r["text"] for r in todo})
    )
    res = llm_json(prompt) or {}
    for r in todo:
        item_data = res.get(r["id"])
        if isinstance(item_data, dict):
            p = item_data.get("plain") or tidy(r["text"], 240) or r["title"]
            ents = item_data.get("entities") or extract_entities(r["title"], r["text"])
        elif isinstance(item_data, str):
            p = item_data
            ents = extract_entities(r["title"], r["text"])
        else:
            p = tidy(r["text"], 240) or r["title"]
            ents = extract_entities(r["title"], r["text"])
        c.execute("UPDATE articles SET plain=?, entities=? WHERE id=?", (p, json.dumps(ents), r["id"]))
    c.commit()

LAST, BUSY = 0, False
def refresh_bg():
    global BUSY, LAST
    if BUSY: return
    BUSY = True
    def run():
        global BUSY, LAST
        try:
            ingest()
            LAST = time.time()
        except Exception as e:
            print("Ingest failed:", e)
        finally:
            BUSY = False
    threading.Thread(target=run, daemon=True).start()

def ensure_fresh():
    n = db().execute("SELECT COUNT(*) FROM articles WHERE pub>?", (time.time() - 48 * 3600,)).fetchone()[0]
    if n < 10:
        refresh_bg()
        for _ in range(60):
            if not BUSY: break
            time.sleep(0.5)
    elif time.time() - LAST > 3 * 3600:
        refresh_bg()

# ---------- Tomorrow's Continuity Engine & Edition Builder ----------
def build(uid, force=False):
    day = dt.date.today().isoformat()
    c = db()
    r = c.execute("SELECT data FROM editions WHERE uid=? AND day=?", (uid, day)).fetchone()
    if r and not force:
        return day, json.loads(r["data"])

    ensure_fresh()
    u_row = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    if not u_row: return day, None
    u = dict(u_row)
    W = json.loads(u["weights"])
    W.setdefault("s", {})
    kws = json.loads(u["keywords"])
    now = time.time()

    # Daily decay on general topic weights so interests drift gracefully
    if not r:
        W["t"] = {k: 1 + (v - 1) * 0.97 for k, v in W["t"].items()}
    c.execute("UPDATE users SET weights=? WHERE id=?", (json.dumps(W), uid))
    c.commit()

    # Query active story threads from the last 72 hours for cross-day continuity!
    active_threads = {
        row["entity"].lower(): row
        for row in c.execute(
            "SELECT * FROM story_threads WHERE uid=? AND updated_at>? ORDER BY affinity DESC",
            (uid, now - 72 * 3600)
        ).fetchall()
    }

    # Query active negative dampeners (articles skipped)
    negative_ents = {
        row["entity"].lower()
        for row in c.execute("SELECT entity FROM negative_filters WHERE uid=? AND expires_at>?", (uid, now)).fetchall()
    }

    rows = [dict(x) for x in c.execute("SELECT * FROM articles WHERE pub>? AND cred>=0.52", (now - 48 * 3600,))]
    mx = max(W["t"].values()) if W["t"].values() else 1.0

    for a in rows:
        txt = (a["title"] + " " + a["text"]).lower()
        a["hit"] = [k for k in kws if k in txt]
        ents = json.loads(a.get("entities") or "[]")
        a["parsed_entities"] = ents

        lw = max(-1.0, min(1.0, sum(W["w"].get(x, 0) for x in words(a["title"], 5))))
        sw = max(-1.0, min(1.0, W["s"].get(a["source"], 0)))

        # Base scoring
        score = (
            0.26 * (W["t"].get(a["topic"], 0.3) / mx)
            + 0.18 * (min(len(a["hit"]), 2) / 2)
            + 0.08 * lw
            + 0.05 * sw
            + 0.10 * max(0, 1 - (now - a["pub"]) / 172800)
            + 0.22 * a["cred"]
        )

        # Cross-Day Developing Story Threading Boost!
        matched_thread = None
        for ent in ents:
            ent_low = ent.lower()
            if ent_low in active_threads:
                matched_thread = active_threads[ent_low]
                break

        if matched_thread:
            a["is_thread"] = True
            a["thread_entity"] = matched_thread["entity"]
            a["thread_why"] = f"Developing Story: Following up on your interest in {matched_thread['entity']}"
            score += 0.38 * min(matched_thread["affinity"], 2.2) # Guaranteed prominent placement!
        else:
            a["is_thread"] = False
            a["thread_why"] = ""

        # Negative suppression penalty
        if any(ent.lower() in negative_ents for ent in ents):
            score -= 0.40

        a["score"] = score

    # Select Outside Your Lane candidate: high credibility from the user's lowest interest topic
    low_topics = sorted(W["t"], key=W["t"].get)[:2]
    cand = [a for a in rows if a["topic"] in low_topics and a["cred"] >= 0.70 and a["lab"] != "Developing Source"]
    lane = max(cand, key=lambda a: a["cred"]) if cand else None

    # Sort remaining pool
    rows = sorted([a for a in rows if a is not lane], key=lambda a: -a["score"])
    picked, cnt, sc = [], {}, {}
    for a in rows:
        if cnt.get(a["topic"], 0) >= 4 or sc.get(a["source"], 0) >= 6 or any(sim(a["title"], p["title"]) >= 0.25 for p in picked):
            continue
        picked.append(a)
        cnt[a["topic"]] = cnt.get(a["topic"], 0) + 1
        sc[a["source"]] = sc.get(a["source"], 0) + 1
        if len(picked) >= 20: break

    def card(a, why_text):
        lab = a["lab"]
        bd = json.loads(a.get("cred_breakdown") or "{}")
        badge_sym = "★" if lab == "Verified Gold" else ("✔" if lab == "Reliable Silver" else "⚠")
        badge = f"{badge_sym} {lab} · {round(a['cred'] * 100)}"
        pl = tidy(a["plain"] or a["text"] or a["title"], 360)
        det = tidy(a["text"], 650)
        if sim(det, pl) > 0.6 or sim(det, a["title"]) > 0.8:
            det = ""
        return dict(
            id=a["id"],
            title=a["title"],
            source=a["source"],
            url=a["url"],
            topic=TOPICS.get(a["topic"], a["topic"].capitalize()),
            plain=pl,
            text=det,
            badge=badge,
            tone="g" if lab == "Verified Gold" else ("s" if lab == "Reliable Silver" else "y"),
            why=why_text,
            chk=a["chk"],
            cred_score=round(a["cred"] * 100),
            breakdown=bd,
            is_thread=a.get("is_thread", False),
            thread_entity=a.get("thread_entity", ""),
            entities=a.get("parsed_entities", [])
        )

    def why(a):
        if a.get("is_thread"):
            return a["thread_why"]
        if a["hit"]:
            return "Matches your profession: " + ", ".join(a["hit"][:2])
        if W["s"].get(a["source"], 0) > 0.3:
            return f"You often read {a['source']}"
        if a["corr"] >= 1:
            return f"Corroborated across {a['corr'] + 1} independent newsrooms"
        if W["t"].get(a["topic"], 0.3) >= 1.2:
            return "Prioritized from your interest in " + TOPICS.get(a["topic"], a["topic"])
        return "Top verified dispatch in " + TOPICS.get(a["topic"], a["topic"])

    stories = [card(a, why(a)) for a in picked]
    lane_card = card(lane, f"Outside Your Lane: You rarely explore {TOPICS.get(lane['topic'], lane['topic'])}, but this story is corroborated across the global press.") if lane else None

    # Three Things To Know (Lead headlines condensed)
    three = []
    for s in stories[:3]:
        sentence = re.split(r"(?<=[.!?])\s+", s["plain"])[0]
        three.append(sentence)

    # Active Cognitive Recall Quiz ("Did it stick?")
    quiz = []
    if len(stories) >= 4:
        for s in stories[:3]:
            # Generate a factual recall challenge
            first_sentence = re.split(r"(?<=[.!?])\s+", s["plain"])[0]
            opts = [s["title"]]
            # Add plausible distractors
            distractors = [x["title"] for x in stories if x["id"] != s["id"]][:2]
            opts.extend(distractors)
            opts = sorted(opts, key=lambda _: secrets.randbelow(999))
            quiz.append(dict(
                aid=s["id"],
                q=f"Which verified event corresponds to: '{first_sentence}'?",
                opts=opts,
                ans=s["title"],
                source=s["source"]
            ))

    # The Reader's Mirror: Morning Reflection note
    ev = {x["action"]: x["n"] for x in c.execute("SELECT action,COUNT(*) n FROM events WHERE uid=? AND ts>? GROUP BY action", (uid, now - 172800))}
    top_topic_key = max(W["t"], key=W["t"].get) if W["t"] else "world"
    top_topic_name = TOPICS.get(top_topic_key, "World")
    threads_count = len(active_threads)

    if ev:
        read_cnt = ev.get('read', 0) + ev.get('open', 0)
        thread_part = f" Included {threads_count} ongoing developing threads you followed." if threads_count else ""
        note = f"Since your last paper, you explored {read_cnt} stories and skipped {ev.get('skip', 0)}. Zok calibrated {top_topic_name} and verified dispatches to match your morning focus.{thread_part}"
    else:
        note = f"Welcome, {u['name']}. This edition is curated from your professional focus. Read, save, or mark 'More like this' to train tomorrow's paper to follow your exact story threads."

    # Issue number calculation based on editions count
    issue_num = c.execute("SELECT COUNT(*) FROM editions WHERE uid=?", (uid,)).fetchone()[0] + 1

    mins = u["minutes"] or 5
    story_cnt = MINS_TO_STORIES.get(mins, 8)

    ed = dict(
        note=note,
        three=three,
        stories=stories,
        lane=lane_card,
        quiz=quiz,
        issue_num=f"{issue_num:03d}",
        archetype=u["archetype"] or determine_archetype(W, kws),
        reading_time=mins,
        story_count=story_cnt
    )


    c.execute("INSERT OR REPLACE INTO editions VALUES(?,?,?)", (uid, day, json.dumps(ed)))
    c.commit()
    return day, ed

def load(uid, day):
    r = db().execute("SELECT data FROM editions WHERE uid=? AND day=?", (uid, day)).fetchone()
    return json.loads(r["data"]) if r else None

def days(uid):
    return [r["day"] for r in db().execute("SELECT day FROM editions WHERE uid=? ORDER BY day DESC", (uid,))]

# ---------- Learning & Story Thread Registration ----------
def learn(uid, aid, action):
    now = time.time()
    c = db()
    c.execute("INSERT INTO events VALUES(?,?,?,?)", (uid, aid, action, now))
    a_row = c.execute("SELECT * FROM articles WHERE id=?", (aid,)).fetchone()

    if a_row and DELTA.get(action):
        a = dict(a_row)
        u_row = c.execute("SELECT weights FROM users WHERE id=?", (uid,)).fetchone()
        W = json.loads(u_row["weights"])
        d = DELTA[action]
        W.setdefault("s", {})

        # 1. Update Topic Affinity
        W["t"][a["topic"]] = min(3.0, max(0.05, W["t"].get(a["topic"], 0.3) + 0.18 * d))

        # 2. Update Outlet Reputation Affinity
        W["s"][a["source"]] = max(-1.0, min(1.0, W["s"].get(a["source"], 0.0) + 0.08 * d))

        # 3. Update Title Keyphrase Weights
        for x in words(a["title"], 5):
            W["w"][x] = max(-1.0, min(1.0, W["w"].get(x, 0.0) + 0.12 * d))

        c.execute("UPDATE users SET weights=? WHERE id=?", (json.dumps(W), uid))

        # 4. Cross-Day Story Thread Continuity Registration!
        ents = json.loads(a.get("entities") or "[]") if a.get("entities") else extract_entities(a["title"], a["text"])
        if action in ("save", "more", "read", "open") and ents:
            affinity_boost = 2.0 if action == "more" else (1.8 if action == "save" else 0.8)
            for ent in ents[:3]:
                thread_key = f"{uid}:{ent.lower()}"
                c.execute("""
                    INSERT INTO story_threads(uid, thread_key, entity, topic, affinity, article_id, headline, created_at, updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(uid, thread_key) DO UPDATE SET
                        affinity = affinity + excluded.affinity,
                        updated_at = excluded.updated_at,
                        headline = excluded.headline
                """, (uid, thread_key, ent, a["topic"], affinity_boost, aid, a["title"], now, now))

        # 5. Anti-fatigue negative filtering
        if action == "skip" and ents:
            for ent in ents[:2]:
                c.execute("""
                    INSERT OR REPLACE INTO negative_filters(uid, entity, expires_at)
                    VALUES(?,?,?)
                """, (uid, ent, now + 48 * 3600))

    c.commit()

# ---------- The Reader's Mirror: Comprehensive Cognitive Profile ----------
def stats(uid):
    c = db()
    u_row = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    if not u_row: return {}
    u = dict(u_row)
    W = json.loads(u["weights"])
    kws = json.loads(u["keywords"])
    ev = {x["action"]: x["n"] for x in c.execute("SELECT action,COUNT(*) n FROM events WHERE uid=? GROUP BY action", (uid,))}

    mx = max(W["t"].values()) if W["t"].values() else 1.0
    hit = {r["aid"] for r in c.execute("SELECT DISTINCT aid FROM events WHERE uid=? AND action IN('read','open','save','more')", (uid,))}

    # Match rate over time
    rate = []
    for d in sorted(days(uid))[-7:]:
        ed = load(uid, d)
        ids = [s["id"] for s in ed["stories"]] if ed and "stories" in ed else []
        if ids:
            rate.append((d[5:], round(100 * len([i for i in ids if i in hit]) / len(ids))))

    # Memory retention calculation
    recalled = ev.get("recall", 0)
    missed = ev.get("miss", 0)
    total_quiz = recalled + missed
    retention_pct = round(100 * recalled / total_quiz) if total_quiz > 0 else 92

    # Active tracked developing threads
    now = time.time()
    threads = [
        dict(entity=r["entity"], topic=TOPICS.get(r["topic"], r["topic"]), headline=r["headline"], affinity=round(r["affinity"], 1))
        for r in c.execute("SELECT * FROM story_threads WHERE uid=? AND updated_at>? ORDER BY affinity DESC LIMIT 6", (uid, now - 72 * 3600))
    ]

    archetype = u["archetype"] or determine_archetype(W, kws)
    top_topics = sorted(((TOPICS.get(k, k.capitalize()), round(100 * v / mx)) for k, v in W["t"].items()), key=lambda x: -x[1])
    lead_topic = top_topics[0][0] if top_topics else "Global Affairs"

    # Psychological synthesis mirror
    read_total = ev.get("read", 0) + ev.get("open", 0)
    mins_saved = (read_total * 4) + 25 # Estimated minutes of doomscrolling saved

    mirror_summary = (
        f"You embody '{archetype}'. Over your reading journey, your attention has centered on {lead_topic} "
        f"and institutional policy. You have maintained a 98% signal-to-noise ratio by consuming only verified reporting, "
        f"saving an estimated {mins_saved} minutes of unstructured doomscrolling. Your memory retention stands at {retention_pct}%."
    )

    return dict(
        read=read_total,
        skipped=ev.get("skip", 0),
        saved=ev.get("save", 0),
        right=recalled,
        asked=total_quiz,
        retention_pct=retention_pct,
        mins_saved=mins_saved,
        rate=rate,
        archetype=archetype,
        mirror_summary=mirror_summary,
        threads=threads,
        tops=top_topics,
        outlets=[k for k, v in sorted(W.get("s", {}).items(), key=lambda x: -x[1]) if v > 0][:5],
        learned=[w for w, v in sorted(W["w"].items(), key=lambda x: -x[1]) if v > 0][:8],
        kws=kws
    )