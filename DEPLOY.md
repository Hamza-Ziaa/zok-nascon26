# Deploying ZOK — Step by Step

This guide walks you through putting ZOK online so anyone can use it.

---

## Part A: Upload Your Code to GitHub

If you haven't already, create a new repository on [github.com](https://github.com/new) (don't add a README — you already have one).

Then run these commands in your terminal:

```bash
cd "c:\Users\Musa Laptop\Desktop\Projects\Nascon26"
git init
git add -A
git commit -m "ZOK v2.0 — Personal Morning Paper (NaSCon 26)"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

> [!TIP]
> Replace `YOUR_USERNAME` and `YOUR_REPO` with your actual GitHub username and repository name.

---

## Part B: Deploy on Render (Free Tier)

### 1. Create a Render Account
Go to [render.com](https://render.com) and sign up (GitHub login is easiest).

### 2. Create a New Web Service
Click **"New +"** → **"Web Service"**.

### 3. Connect Your GitHub Repo
Search for and select the repository you just pushed.

### 4. Render Auto-Detects Settings
Because you have a `render.yaml` file, Render will automatically pick up:
- **Build command:** `pip install -r requirements.txt && playwright install --with-deps chromium`
- **Start command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
- **Python version:** 3.12

### 5. Add Your API Key
Go to the **Environment** tab and add:

| Key              | Value                    |
| :--------------- | :----------------------- |
| `GEMINI_API_KEY` | *your actual Gemini key* |

### 6. Click "Create Web Service"
Render will start building your app. This takes about **3 minutes**.

### 7. You're Live! 🎉
Once the build finishes, your app will be available at:

```
https://zok-morning-paper.onrender.com
```

---

## ⚠️ A Note About the Database

ZOK uses **SQLite** for storing articles, user profiles, and reading history. This works perfectly on Render's free tier, but there's a catch:

> [!WARNING]
> On Render's free tier, the filesystem resets on every deploy. This means your SQLite database (and any saved data) will be wiped each time you push new code.

**For a hackathon demo, this is totally fine.** ZOK re-fetches fresh articles on startup anyway.

If you ever want persistent data for production, you'd switch to **PostgreSQL** (Render offers a free PostgreSQL database too).

---

## Troubleshooting

| Problem | Fix |
| :--- | :--- |
| Build fails on Playwright | Make sure `render.yaml` uses `playwright install --with-deps chromium` (the `--with-deps` flag installs system libraries) |
| App crashes on start | Check that `GEMINI_API_KEY` is set in Render's Environment tab |
| Port errors | Render sets the `$PORT` variable automatically — don't hardcode a port |
| Slow first load | Free tier spins down after 15 min of inactivity. First request takes ~30s to wake up |
