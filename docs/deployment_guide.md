# VIDYA-X AI — Complete Production Deployment Guide (Step 16)

**Project:** VIDYA-X AI — Your Course-Aware, Adaptive & Multimodal AI Tutor  
**Tagline:** "Learn from your material. Get cited answers. Practice intelligently. Improve continuously."

---

## 1. Architecture Overview

VIDYA-X AI follows a clean, resilient decoupled architecture:

```
[Student Browser]
       │
       ▼ (HTTPS)
┌─────────────────────────────────────────────────────────┐
│               Frontend Presentation Layer               │
│  HTML5 + CSS3 + Vanilla JavaScript (Static Web Host)    │
│  (Vercel / Cloudflare Pages / Render / Netlify)         │
└──────────────────────────┬──────────────────────────────┘
                           │ API Requests (CORS Guarded)
                           ▼
┌─────────────────────────────────────────────────────────┐
│                 Backend Service Layer                   │
│   FastAPI + Uvicorn ASGI Server (Container / PaaS)      │
│   (Render Web Service / Railway / Fly.io / VPS)         │
│                                                         │
│  ├── Multimodal Extractors (PyMuPDF, PPTX, FFmpeg)      │
│  ├── Knowledge Structuring & pgvector Cosine Retrieval │
│  ├── Grounded AI Tutor & Citation Assembly              │
│  ├── Adaptive Question Scoring & BKT Mastery Engine     │
│  └── Flashcards, Study Planner & Visual Studio          │
└──────────────┬────────────────────────────┬─────────────┘
               │                            │
               ▼                            ▼
┌───────────────────────────┐  ┌──────────────────────────┐
│   PostgreSQL + pgvector   │  │    Persistent Disk       │
│  (Supabase / Neon / RDS)  │  │ (Docker Volume / Mount)  │
│  • Course Knowledge Graph │  │ • /backend/uploads       │
│  • 384d Semantic Vectors  │  │ • /backend/visual_assets │
│  • BKT Student Mastery    │  │ • /backend/extracted     │
│  • Misconception Records  │  └──────────────────────────┘
└───────────────────────────┘
```

---

## 2. Recommended Hosting Options

| Hosting Provider | Frontend | Backend | Database | Estimated Cost | Setup Effort | Hackathon Rating |
|---|---|---|---|---|---|---|
| **Option A (Recommended): Render + Neon** | Render Static Site | Render Web Service (Docker) | Neon Serverless Postgres (`pgvector`) | **$0 (Free Tier)** | 10 mins | ⭐⭐⭐⭐⭐ **Best Choice** |
| **Option B: Railway Full Stack** | Railway Static/Nginx | Railway Python Service | Railway PostgreSQL (`pgvector`) | ~$5 credit | 5 mins | ⭐⭐⭐⭐⭐ **Fastest** |
| **Option C: Single VPS (Docker Compose)** | Nginx Container | FastAPI Container | `pgvector/pgvector:pg16` | $4–$6 / month | 15 mins | ⭐⭐⭐⭐ **Most Control** |

---

## 3. Environment Variables Reference

| Variable Name | Required | Default (Dev) | Description |
|---|---|---|---|
| `APP_ENV` | Yes | `development` | Set to `production` in live deployments. |
| `DATABASE_URL` | Yes | `sqlite:///./vidya_x.db` | PostgreSQL connection string with `postgresql+psycopg://` scheme. |
| `FRONTEND_ORIGINS` | Yes | `*` | Comma-separated list of allowed frontend origins (e.g. `https://vidya-x.vercel.app`). |
| `MAX_UPLOAD_SIZE_MB` | No | `50` | Maximum allowed upload size in megabytes. |
| `EMBEDDING_PROVIDER` | No | `local` | `local` (deterministic fast n-gram vectors), `sentence-transformers`, `openai`, or `gemini`. |
| `GEMINI_API_KEY` | Optional | `None` | Google Gemini API key for live multimodal vision analysis & AI tutor generation. |
| `VISION_MODEL` | No | `gemini-1.5-flash` | Gemini model name for visual diagram understanding. |
| `DEMO_MODE_ENABLED`| No | `true` | Allows the 1-click Classical Mechanics presentation mode. |

---

## 4. Step-by-Step Deployment Instructions (Option A: Render + Neon)

### Step 4.1: Provision PostgreSQL with pgvector on Neon (Free)
1. Go to [Neon.tech](https://neon.tech) and create a free project named `vidya-x`.
2. In the Neon SQL Console, run:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
3. Copy your connection string:
   `postgresql://username:password@ep-sample-12345.us-east-2.aws.neon.tech/neondb?sslmode=require`
4. Convert protocol prefix for psycopg3:
   `postgresql+psycopg://username:password@ep-sample-12345.us-east-2.aws.neon.tech/neondb?sslmode=require`

### Step 4.2: Deploy Backend Web Service on Render
1. Go to [Render.com](https://render.com) → **New Web Service** → Connect your GitHub repository.
2. Select **Docker** environment (Render will automatically detect the root [`Dockerfile`](file:///c:/Users/hp/Downloads/vidya%20-%20x/Dockerfile)).
3. Under **Environment Variables**, add:
   - `DATABASE_URL`: *(Your psycopg Neon URL from Step 4.1)*
   - `APP_ENV`: `production`
   - `FRONTEND_ORIGINS`: `https://your-frontend-domain.onrender.com`
   - `EMBEDDING_PROVIDER`: `local`
   - `DEMO_MODE_ENABLED`: `true`
   - *(Optional)* `GEMINI_API_KEY`: *(Your key)*
4. Under **Disks**, add a Persistent Disk:
   - Name: `vidya_storage`
   - Mount Path: `/app/backend/uploads`
   - Size: `1 GB`
5. Click **Create Web Service**.
6. Once deployed, run the schema initialization command in Render Shell:
   ```bash
   python scripts/init_db.py
   ```
7. Verify health: visit `https://your-backend.onrender.com/health/ready`.

### Step 4.3: Deploy Frontend on Render / Vercel / Netlify
1. In `frontend/config.js`, set `API_BASE_URL` to your live backend:
   ```javascript
   window.VIDYAX_CONFIG = {
     API_BASE_URL: "https://your-backend.onrender.com/api",
     APP_ENV: "production",
   };
   ```
2. Create a new **Static Site** on Render/Vercel:
   - Root directory: `frontend`
   - Build command: *(leave empty)*
   - Publish directory: `frontend`
3. Deploy and open the live URL!

---

## 5. Alternative: 1-Command Local or VPS Deployment (Docker Compose)

On any Linux VPS (Ubuntu, Debian) or local machine with Docker installed:

```bash
# 1. Clone repository
git clone <repo_url> "vidya-x"
cd "vidya-x"

# 2. Launch complete stack (Postgres + pgvector, Backend, Frontend Nginx)
docker compose up -d --build

# 3. Initialize database tables & extension
docker exec -it vidyax_backend python /app/scripts/init_db.py

# 4. Open in browser:
# Frontend: http://localhost:3000
# Backend API & Docs: http://localhost:8000/docs
```

---

## 6. Running Smoke Tests Against Deployed Instance

Run the non-destructive deployment smoke test suite against your live URL:

```bash
python scripts/smoke_test.py https://your-backend.onrender.com
```

Expected output:
```text
=================================================================
  VIDYA-X AI — Production Smoke Tests
  Target: https://your-backend.onrender.com
=================================================================
  [PASS]  1. Liveness Probe (/health) — version=1.0.0
  [PASS]  2. Readiness Probe (/health/ready) — db=connected
  [PASS]  3. AI Provider Diagnostic (/health/ai) — llm_ready=True
  [PASS]  4. Dashboard Summary API — chunks=4
  [PASS]  5. Grounded AI Tutor Response with Citations — citations=1
  [PASS]  6. Safe Abstention on Out-of-Domain Query — abstained correctly
  [PASS]  7. Visual Assets Course API & Path Masking — assets_found=0
-----------------------------------------------------------------
  Summary: 7/7 smoke tests passed
=================================================================
```

---

## 7. Rollback & Troubleshooting

- **Database Connection Failure (503 Unhealthy)**: Check that `sslmode=require` is present if connecting to cloud providers (Neon/Supabase) and that IP allowlists permit connections.
- **CORS Blocked**: Confirm `FRONTEND_ORIGINS` exactly matches the browser URL scheme and domain (including `https://` and without trailing slash).
- **Video Extraction Timeout**: Ensure `ffmpeg` is available on system PATH (already bundled in the Dockerfile). For large lecture videos (>200MB), upload short clips during live hackathon demos.
- **Rollback**: To rollback code on Render/Railway, navigate to **Deploys** and click **Rollback to this deploy** on any previous successful build.
