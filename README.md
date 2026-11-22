# BrandGuard AI — Round 3 Production Release (CodeZen India 2026)

**BrandGuard AI** is an enterprise brand-governance platform that audits marketing copy and visual ad creatives in real time against a dynamic, live-editable ChromaDB brand rulebook—powered by **FastAPI**, **CrewAI**, and **Google Gemini 2.5 Flash**.

Designed for zero-friction judging and **Render Free Tier (Python 3.12 · 512MB RAM)**: no Node/npm build step required, automatic default policy seeding on startup, and one-click demo samples across every tab.

---

## Key Features

1. **Frictionless Demo Auth (`POST /api/auth/login`, `GET /api/auth/me`)**
   - HMAC-SHA256 signed session token persisted in `localStorage`.
   - Demo credentials: **`test123` / `test123`** plus a **One-Click Demo Sign In** button.
2. **Interactive Text Audit (`POST /api/review`)**
   - Split-screen Apple-clean workspace with **3 one-click sample drafts**.
   - CrewAI + Gemini (`gemini-2.5-flash`) audit with automatic fallback to direct Gemini structured JSON output.
   - Returns compliance score (0–100), status pill (`Approved`, `Flagged`, `Violation`), broken rules, plain-English explanation, and a **1-click Copy Compliant Rewrite** button.
3. **Dynamic Brand Rulebook / Live RAG Updater (`/api/guidelines*`)**
   - Auto-seeds 4 enterprise brand guidelines on startup (resilient to Render ephemeral restarts).
   - Lightweight deterministic embeddings (zero heavy PyTorch/ONNX downloads, ~0MB extra RAM).
   - Add custom rules via text, upload `.pdf`, `.docx`, or `.txt` policy files (up to 5MB), delete rules, or reset to defaults—every change applies immediately on the very next audit.
4. **Multimodal Visual Compliance Audit (`POST /api/review/image`)**
   - Drag-and-drop `PNG`, `JPG`, `JPEG`, or `WEBP` creatives (up to 5MB) with live preview and optional caption.
   - Includes **2 one-click sample ad creatives** (`sample_violation_ad.png` and `sample_compliant_ad.png`) served from `GET /api/samples/images/{filename}`.
   - Audits visual hierarchy, contrast, embedded text, and urgency claims via **Gemini Vision (`gemini-2.5-flash`)** with a 25-second timeout.

---

## Quick Start (Under 3 Minutes)

### 1. Clone & Create a Virtual Environment
```bash
cd backend
python3.12 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Your Gemini API Key
Copy `.env.example` to `.env` (in the repo root or `backend/.env`) and add your key:
```bash
cp ../.env.example .env
# Edit .env and set GEMINI_API_KEY=your_real_key
```

### 3. Run the Automated Test Suite
```bash
pytest -v
```

### 4. Launch the Application
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
- **Web App:** http://localhost:8000/
- **Interactive API Docs (Swagger):** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/api/health

---

## Render Deployment (Free Tier · 512MB RAM)

1. Connect your GitHub repository in Render as a **Web Service**.
2. Set **Root Directory** to `backend`.
3. Set **Build Command** to `pip install -r requirements.txt`.
4. Set **Start Command** to `uvicorn main:app --host 0.0.0.0 --port $PORT`.
5. Add environment variable `GEMINI_API_KEY` in the Render dashboard.

---

## Project Structure

```text
brandguard-mvp/
├── .env.example
├── .gitignore
├── README.md
└── backend/
    ├── main.py                  # FastAPI API, HMAC auth, static SPA serving
    ├── ai_engine.py             # CrewAI + Gemini 2.5 Flash text & Vision engine
    ├── database.py              # ChromaDB store + zero-RAM deterministic embeddings
    ├── generate_samples.py      # Pillow script to regenerate sample ad creatives
    ├── requirements.txt         # Python 3.12 lightweight dependencies
    ├── sample_assets/
    │   ├── sample_violation_ad.png
    │   └── sample_compliant_ad.png
    ├── static/
    │   ├── index.html
    │   ├── styles.css
    │   └── app.js
    └── tests/
        └── test_api.py          # Full offline pytest suite
```
