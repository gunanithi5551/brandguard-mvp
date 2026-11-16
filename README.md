# BrandGuard AI — Governance Portal (Codezen India 2026 Round 2 MVP)

**BrandGuard AI** is a full-stack, multi-agent brand governance platform built with **FastAPI**, **CrewAI**, **ChromaDB**, and **React (Vite + Tailwind CSS)**. It audits marketing and corporate drafts against canonical brand guidelines in real time, flags rule violations with transparent explanations, and generates compliant rewrites that preserve the author's original intent.

## Repository Structure

```text
brandguard-mvp/
├── backend/
│   ├── ai_engine.py       # CrewAI 'Compliance Auditor' & 'Correction Editor' + deterministic fallback
│   ├── database.py        # In-memory ChromaDB collection pre-loaded with official Brand Guidelines
│   ├── main.py            # FastAPI server with wide-open CORS and POST /api/review endpoint
│   ├── requirements.txt   # Backend Python dependencies
│   └── test_runner.py     # End-to-end automated integration test script
├── frontend/
│   ├── src/
│   │   ├── App.jsx        # Enterprise BrandGuard AI Governance Portal UI
│   │   ├── index.css      # Tailwind CSS directives
│   │   └── main.jsx       # React DOM entrypoint
│   ├── index.html
│   ├── package.json
│   ├── postcss.config.js
│   ├── tailwind.config.js
│   └── vite.config.js
├── .gitignore
├── README.md
├── start_all.bat          # One-click Windows launcher for Backend + Frontend
└── start_all.sh           # One-command Linux/macOS launcher for Backend + Frontend
```

## Injected Brand Guidelines (ChromaDB)

On startup, `backend/database.py` initializes an in-memory ChromaDB collection and injects:
> `BRAND GUIDELINES: 1. Always use a professional tone. 2. Never guarantee ROI or specific financial outcomes. 3. Refer to users as 'Clients', never 'Customers'.`

## Quick Start Instructions

### Option A: One-Command Launch
- **Windows:**
  ```cmd
  start_all.bat
  ```
- **Linux / macOS:**
  ```bash
  ./start_all.sh
  ```

### Option B: Manual Server Startup

#### 1. Start the Backend (`http://localhost:8000`)
```bash
cd backend
python -m venv venv
# Windows: venv\Scripts\activate | Linux/macOS: source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
*(Optional)* Set `OPENAI_API_KEY` or `GEMINI_API_KEY` in `backend/.env` for live LLM execution. When no key is configured, `ai_engine.py` automatically uses its built-in deterministic guideline auditor so local testing and CI never fail.

#### 2. Start the Frontend (`http://localhost:5173`)
```bash
cd frontend
npm install
npm run dev
```

#### 3. Run the End-to-End Test Runner
With the FastAPI server running on port `8000`:
```bash
python backend/test_runner.py
```
