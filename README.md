# BrandGuard AI — Enterprise Brand Governance Platform

[![Live Demo](https://img.shields.io/badge/Live%20Demo-Render-2563EB?style=for-the-badge)](https://brandguard-mvp.onrender.com)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-1.x%20RAG-F97316?style=for-the-badge)](https://www.trychroma.com/)
[![Gemini](https://img.shields.io/badge/Google%20Gemini-Multi--Modal-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev/)

**BrandGuard AI** is a multi-agent and multimodal enterprise brand-compliance platform. It audits marketing copy and visual ad creatives in real time against a live, editable ChromaDB vector rulebook—returning quantitative compliance scores, exact rule violations, OCR/visual accessibility findings, and instant policy-compliant rewrites.

- **Live Production App:** [https://brandguard-mvp.onrender.com](https://brandguard-mvp.onrender.com)
- **Source Repository:** [https://github.com/gunanithi5551/brandguard-mvp](https://github.com/gunanithi5551/brandguard-mvp)
- **Zero-Walkthrough Access:** Click **One-Click Demo Sign In** on the login screen (session persists across page refreshes).

> **Note on Cloud Cold Starts:** The live demo runs on Render's free tier. If the instance has been idle, the first request may take 30–50 seconds to wake the container before audits run normally.

---

## Key Features

### 1. Text Compliance Audit & Instant Rewrite
- Evaluates draft marketing copy against all active brand guidelines stored in ChromaDB using a **CrewAI Compliance Agent** powered by Gemini (`gemini-3.5-flash-lite`) with an automatic direct `google-genai` structured JSON fallback.
- Outputs a `0–100` compliance score, status (`Approved`, `Flagged`, `Violation`), specific rule citations, plain-English explanation, and a **one-click copyable Compliant Rewrite**.
- Includes built-in one-click sample drafts (**ROI Guarantee Violation**, **Casual Tone Violation**, **Compliant Enterprise Copy**) for immediate evaluation.

### 2. Multi-Modal Visual Compliance Audit
- Inspects uploaded marketing creatives (`PNG`, `JPG`, `WEBP`, up to `5 MB`) plus optional ad captions via direct **Google Gemini Vision** (`google-genai`).
- Evaluates embedded typography/OCR text, WCAG AA contrast and legibility, visual clutter, terminology rules, and misleading urgency or financial claims.
- Returns structured `visual_findings`, `text_in_image_findings`, `broken_rules`, and `actionable_fixes`, complete with one-click sample creatives (**Violation Banner** and **Compliant Creative**).

### 3. Dynamic Brand Rulebook (Live ChromaDB RAG)
- Add custom brand rules directly from the dashboard (`Rule Title` + `Policy Statement`), delete individual rules, or click **Reset to Defaults** to restore the 4 core enterprise guidelines.
- Supports **Policy Document Ingestion** (`.PDF`, `.DOCX`, `.TXT` up to `5 MB`) that extracts text, chunks cleanly, and indexes rules directly into ChromaDB.
- Changes take effect **immediately** on the very next Text or Visual audit with zero server restarts.

### 4. Production Resilience & Quota Protection
- **Multi-Project API Key Pool (`GEMINI_API_KEYS`):** Rotates across multiple Google Cloud project keys automatically to prevent Free Tier daily request exhaustion.
- **Multi-Model Fallback Chain:** Automatically rotates across `gemini-3.5-flash-lite`, `gemini-3.1-flash-lite`, `gemini-3.5-flash`, and `gemini-3.6-flash` on `503 UNAVAILABLE`, `504`, or network timeouts.
- **Instant `429` Blacklisting:** Skips daily-exhausted `(key, model)` pairs for 1 hour on first detection instead of burning timeout budget.
- **Strict Timeout & Retry Isolation:** Uses `attempts=1` fast-fail HTTP client configuration with a 60-second overall vision timeout so requests never hang indefinitely.

---

## Round 2 → Round 3 Improvements Delivered

| Round 2 Commitment | Round 3 Delivery Status | Summary |
| :--- | :--- | :--- |
| **1. Interactive Web Frontend Dashboard** | **Delivered** | Full 3-tab responsive UI (**Text Audit**, **Visual Audit**, **Brand Rulebook**), one-click demo auth with persistent sessions, sample presets, live active-rule indicator, and copyable rewrites. |
| **2. Dynamic Guideline Management System (RAG Updater)** | **Delivered** | Upgraded to ChromaDB 1.x with live rule CRUD, `.PDF`/`.DOCX`/`.TXT` policy document ingestion, instant enforcement without restarts, and one-click Reset to Defaults. |
| **3. Multi-Modal Visual Compliance Auditing** | **Delivered (Images) / Scoped (PDF Creatives)** | Live Gemini Vision auditing for `PNG`, `JPG`, and `WEBP` creatives with OCR text detection and WCAG contrast checks. Multi-page PDF *visual brochure rasterization* was intentionally deferred to Roadmap Phase 1 to protect Render free-tier memory stability (while `.PDF` *policy rulebook text ingestion* is live today). |

---

## Technical Architecture

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                     Browser Frontend (backend/static/)                  │
│   Text Audit Tab   │   Visual Audit Tab   │   Brand Rulebook Tab        │
│   One-Click Auth   │   Sample Presets     │   Live Policy CRUD / Upload │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │ REST JSON / Multipart Form-Data
┌─────────────────────────────────▼───────────────────────────────────────┐
│                   FastAPI + Uvicorn Backend (backend/)                  │
│  main.py  ──► Auth Middleware & API Routes (/api/review, /review/image, │
│               /api/guidelines, /api/health, /api/auth/*)                │
│  database.py ──► ChromaDB 1.x Persistent Vector Store (backend/chroma_db)│
│  ai_engine.py ──► Multi-Agent & Multimodal Orchestration                │
│      ├── Text Primary: CrewAI Agent + LiteLLM (gemini-3.5-flash-lite)   │
│      ├── Text Fallback: Direct google-genai Structured JSON             │
│      ├── Visual Audit: Direct google-genai Multimodal Vision (60s cap)  │
│      └── Resilience Layer: Multi-Key Pool + 4-Model Fallback + 429 Skip │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │ HTTPS (v1 / v1beta)
┌─────────────────────────────────▼───────────────────────────────────────┐
│                         Google Gemini API                               │
│  gemini-3.5-flash-lite ──► 3.1-flash-lite ──► 3.5-flash ──► 3.6-flash   │
└─────────────────────────────────────────────────────────────────────────┘
```

### Repository Layout

```text
brandguard-mvp/
├── .env.example              # Environment variable template (safe placeholders)
├── .gitignore                # Excludes .env, venv/, chroma_db/, caches
├── README.md                 # Project documentation & setup guide
└── backend/
    ├── main.py               # FastAPI app, routes, auth, static asset serving
    ├── ai_engine.py          # CrewAI + google-genai vision + fallback/key rotation
    ├── database.py           # ChromaDB 1.x RAG rulebook CRUD & document ingestion
    ├── generate_samples.py   # Script to generate built-in sample ad creatives
    ├── requirements.txt      # Pinned/resolved Python dependencies
    ├── sample_assets/        # Built-in Violation & Compliant sample banners
    ├── static/               # Frontend UI (index.html, app.js, styles.css)
    └── tests/                # Automated pytest test suite (9 tests)
```

---

## Quickstart — Clone & Run Locally

### Prerequisites
- Python **3.11+** (tested on Python 3.12)
- A Google Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey)

### 1. Clone the Repository
```bash
git clone https://github.com/gunanithi5551/brandguard-mvp.git
cd brandguard-mvp
```

### 2. Create a Virtual Environment & Install Dependencies

**Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
```

**macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` into `backend/.env` and add your Gemini API key:

**Windows (PowerShell):**
```powershell
Copy-Item .env.example backend\.env
```

**macOS / Linux:**
```bash
cp .env.example backend/.env
```

Edit `backend/.env`:
```env
GEMINI_API_KEY=your_primary_gemini_api_key
# Optional: Comma-separated keys from separate Google Cloud projects for automatic quota rotation
GEMINI_API_KEYS=your_primary_key,your_backup_project_key
GEMINI_MODEL=gemini-3.5-flash-lite

DEMO_USERNAME=test123
DEMO_PASSWORD=test123
AUTH_SECRET=replace-with-a-long-random-secret
```

### 4. Run Automated Tests
```bash
pytest backend/tests -v
```
Expected result: **`9 passed`**.

### 5. Launch the Server
```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000
```
Open **[http://127.0.0.1:8000](http://127.0.0.1:8000)** in your browser and click **One-Click Demo Sign In**.

---

## Deploying on Render

1. Connect the GitHub repository to a Render **Web Service**.
2. Configure build & start commands:
   - **Root Directory:** `backend`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
3. Set Environment Variables in the Render dashboard:
   - `GEMINI_API_KEY` — Primary Gemini API key
   - `GEMINI_API_KEYS` — *(Recommended)* Comma-separated multi-project Gemini keys for high availability
   - `GEMINI_MODEL` — `gemini-3.5-flash-lite`
   - `AUTH_SECRET` — Random production signing secret

---

## API Overview

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Service health & AI configuration status |
| `POST` | `/api/auth/login` | Authenticate demo session (HTTP-only cookie) |
| `GET` | `/api/auth/me` | Verify active authenticated session |
| `GET` | `/api/guidelines` | List all active ChromaDB brand rules |
| `POST` | `/api/guidelines` | Add a new custom rule to ChromaDB |
| `POST` | `/api/guidelines/upload` | Ingest `.PDF`, `.DOCX`, or `.TXT` policy document |
| `DELETE` | `/api/guidelines/{id}` | Remove a single rule from ChromaDB |
| `POST` | `/api/guidelines/reset` | Reset rulebook to the 4 default enterprise policies |
| `POST` | `/api/review` | Run CrewAI + Gemini text compliance audit & rewrite |
| `POST` | `/api/review/image` | Run Gemini Vision audit on uploaded ad creative + caption |

---

## Testing & Verification Summary

- **Automated Backend Suite (`pytest backend/tests -v`):** 9/9 tests passing covering API health, authentication persistence, rulebook CRUD & reset, payload validation, and structured audit normalization.
- **Dynamic RAG End-to-End Test:** Added custom rule *"No Discount or Free Trial Language"* → verified badge updated to `5 Active Rules` → audited otherwise-compliant copy containing *"free trial"* and *"discount"* → immediately scored `0/100`, flagged the new rule, and rewrote to *"guided evaluation"* and *"value-tiered pricing"*.
- **Multimodal Visual Audit Verification:** Audited both built-in presets (`Compliant Creative` → `100/100 Approved`; `Violation Banner` → `10/100 Violation` with all 4 rules detected) and custom uploaded ad creatives under 5 MB.
- **Resilience Testing:** Verified automatic failover across models and API keys during live Google Gemini `503 UNAVAILABLE` spikes and `429 RESOURCE_EXHAUSTED` quota limits.

---

## License

Built for Hackathon Round 3 Evaluation. All sample assets and default enterprise guidelines are provided for demonstration purposes.