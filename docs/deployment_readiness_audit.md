# VIDYA-X AI — Step 16 Deployment Readiness & Security Audit

**Date:** 2026-10-13  
**Status:** Audit Completed  
**Role:** Senior DevOps, Security, and Production Engineer  

---

## 1. Executive Summary

VIDYA-X AI has completed development through Step 15 with 100% test passage (64/64 pytest cases and 39/39 standalone unit assertions). This audit evaluates the production deployment readiness across hosting architecture, database requirements, environment configuration, file storage persistence, security posture, and observability.

---

## 2. Current State Assessment

### A. Codebase & Structure
- **Frontend**: Pure HTML5, CSS3, Vanilla JavaScript (zero node_modules/framework bloat). Uses native browser `fetch()`. Responsive shell and pages located under `frontend/` and `frontend/pages/`.
- **Backend**: Python 3.10+ / FastAPI with Uvicorn ASGI server. Modular services under `backend/services/`, database models under `backend/database/models.py`.
- **Database**: PostgreSQL with `pgvector` extension for semantic vector embeddings (`Vector(384)`). SQLite in-memory/file fallback implemented for local unit test execution without Postgres.

### B. Identified Deployment Blockers & Risks
1. **Unrestricted CORS in Production**:
   - `backend/main.py` currently has `allow_origins=["*"]` with `allow_credentials=True`. In production, wildcard origins with credentialed requests pose CSRF and security risks. Needs configurable `FRONTEND_ORIGINS`.
2. **Hardcoded API URL in Client**:
   - `frontend/js/api.js` defaults to `http://localhost:8000/api`. On static production hosts (e.g. Vercel, Netlify, Cloudflare Pages), this causes mixed-content errors or points back to the user's localhost. Needs dynamic host discovery with window override `window.VIDYAX_CONFIG.API_BASE_URL`.
3. **Missing Health & Readiness Separation**:
   - `GET /api/health` exists, but there is no dedicated `/api/health/ready` (which probes database connectivity) or `/api/health/ai` (which reports AI provider readiness without exposing secrets).
4. **Database Migration Strategy**:
   - Schema creation relies on runtime `Base.metadata.create_all(engine)`. While functional for quick hackathon deploys, production Postgres requires an explicit migration/bootstrap script that safely executes `CREATE EXTENSION IF NOT EXISTS vector;` before table creation.
5. **Persistent Storage for Uploaded Binaries**:
   - Files are written to `backend/uploads/` and `backend/visual_assets/`. On serverless platforms (e.g. standard AWS Lambda, Vercel Functions), the local filesystem is ephemeral. A persistent disk volume (Docker volume, Render Persistent Disk, Railway Volume) is required.
6. **Missing File Size & MIME Guards**:
   - `backend/main.py` checks file extensions (`.pdf`, `.ppt`, `.pptx`, `.mp4`), but needs a configurable max upload size limit (`MAX_UPLOAD_SIZE_MB`, default 50MB) to prevent memory exhaustion attacks.
7. **Containerization**:
   - No `Dockerfile` or `docker-compose.yml` existed in the repository.

---

## 3. Recommended Deployment Architecture

### Primary Recommendation: Containerized PaaS / Single-VPS Stack (Render / Railway / Fly.io / VPS)
- **Frontend**: Served either directly via CDN/static hosting (Cloudflare Pages / Netlify / Vercel) or mounted as static assets via FastAPI/Nginx.
- **Backend**: FastAPI running under production ASGI server `uvicorn` inside a lightweight multi-stage Docker container (`python:3.12-slim`).
- **Database**: Managed PostgreSQL 16+ with `pgvector` extension enabled (available natively on Supabase, Neon, Render Postgres, Railway Postgres, AWS RDS).
- **Storage**: Persistent mount on `/app/backend/uploads` and `/app/backend/visual_assets`.
- **AI Providers**: Configurable via server-side environment variables (`GEMINI_API_KEY`, `EMBEDDING_PROVIDER`, `VISION_MODEL`).

### Why this is optimal for Hackathons:
- Minimizes operational overhead: no Kubernetes cluster management needed.
- Solves pgvector requirements cleanly via standard Supabase or Railway managed Postgres.
- Keeps cost at $0 (free-tier on Render/Neon/Supabase) or minimal budget ($5-$7/month).
- Eliminates CORS issues if frontend and backend share an apex domain or reverse proxy.

---

## 4. Security Hardening Checklist

- [x] Secrets isolated to server-side `.env` (never exposed to browser client).
- [x] Sanitized filenames to eliminate path traversal (`sanitize_filename`).
- [x] Server-side masking of visual image filesystem paths in API responses.
- [x] Configurable CORS with explicit allowed origins.
- [x] Max upload payload bounds (`MAX_UPLOAD_SIZE_MB`).
- [x] Multi-tier health endpoints (`/api/health`, `/api/health/ready`, `/api/health/ai`).
- [x] Safe Demo Mode isolation (`course_demo_physics`, `student_demo`) ensuring reset never deletes user data.

---

## 5. Audit Conclusion
VIDYA-X AI is in a state for production packaging. Implementing centralized config, production health probes, containerization files, an automated smoke test, and complete deployment guides will achieve full Step 16 compliance.
