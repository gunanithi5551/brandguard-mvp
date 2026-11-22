"""
BrandGuard AI — Round 3 Production FastAPI Server (CodeZen India 2026)

Serves both the REST API (/api/*), interactive Swagger docs (/docs), and the
self-contained Apple-clean Single Page Application from backend/static/ on /.
Designed for Render free tier (Python 3.12, 512MB RAM, Root Directory: backend).
"""

from __future__ import annotations

import os
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "true")
os.environ.setdefault("CREWAI_TRACING_ENABLED", "false")
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

import base64
import hashlib
import hmac
import io
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# Load .env from backend/.env and repo-root/.env (never hardcode secrets)
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR.parent / ".env")

import ai_engine  # noqa: E402
from database import guideline_db  # noqa: E402
from generate_samples import ensure_sample_assets  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("brandguard.api")

STATIC_DIR = BASE_DIR / "static"
SAMPLE_ASSETS_DIR = BASE_DIR / "sample_assets"

MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MB strict limit
ALLOWED_DOC_EXTENSIONS = {".pdf", ".docx", ".txt"}
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
IMAGE_MIME_MAP = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}

DEMO_USERNAME = os.getenv("DEMO_USERNAME", "test123")
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "test123")
AUTH_SECRET = os.getenv("AUTH_SECRET", "brandguard-round3-hmac-signing-key-2026")
TOKEN_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 days


# ---------------------------------------------------------------------------
# HMAC-Signed Token Utilities (Zero extra dependencies)
# ---------------------------------------------------------------------------
def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(encoded: str) -> bytes:
    padding = "=" * (-len(encoded) % 4)
    return base64.urlsafe_b64decode(encoded + padding)


def create_auth_token(username: str) -> str:
    payload = {
        "sub": username,
        "iat": int(time.time()),
        "exp": int(time.time()) + TOKEN_TTL_SECONDS,
    }
    payload_b64 = _b64url_encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    )
    signature = hmac.new(
        AUTH_SECRET.encode("utf-8"),
        payload_b64.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{payload_b64}.{_b64url_encode(signature)}"


def verify_auth_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        payload_b64, sig_b64 = parts
        expected_sig = hmac.new(
            AUTH_SECRET.encode("utf-8"),
            payload_b64.encode("ascii"),
            hashlib.sha256,
        ).digest()
        provided_sig = _b64url_decode(sig_b64)
        if not hmac.compare_digest(expected_sig, provided_sig):
            return None
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return payload
    except Exception:
        return None


def get_current_user(authorization: Optional[str] = Header(default=None)) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please sign in.",
        )
    token = authorization.split(" ", 1)[1].strip()
    payload = verify_auth_token(token)
    if not payload or not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid token. Please sign in again.",
        )
    return str(payload["sub"])


# ---------------------------------------------------------------------------
# Pydantic Request & Response Models
# ---------------------------------------------------------------------------
class LoginRequest(BaseModel):
    username: str = Field(..., description="Username (demo: test123)")
    password: str = Field(..., description="Password (demo: test123)")


class TextReviewRequest(BaseModel):
    text: str = Field(..., description="Marketing copy to audit")


class GuidelineTextRequest(BaseModel):
    title: str = Field(..., description="Short rule title")
    content: str = Field(..., description="Rule text or brand policy statement")


# ---------------------------------------------------------------------------
# Document Text Extraction Helpers
# ---------------------------------------------------------------------------
def _extract_document_text(filename: str, content_bytes: bytes) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".txt":
        return content_bytes.decode("utf-8", errors="replace").strip()

    if ext == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(content_bytes))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n\n".join(p.strip() for p in pages if p.strip()).strip()

    if ext == ".docx":
        from docx import Document

        doc = Document(io.BytesIO(content_bytes))
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text and p.text.strip()]
        return "\n\n".join(paragraphs).strip()

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Unsupported file format. Please upload a .pdf, .docx, or .txt file.",
    )


# ---------------------------------------------------------------------------
# FastAPI Application Setup
# ---------------------------------------------------------------------------
app = FastAPI(
    title="BrandGuard AI — Round 3 Enterprise Compliance Platform",
    description=(
        "Multi-agent brand governance platform with dynamic RAG rulebook updates "
        "and multimodal Gemini Vision auditing."
    ),
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup_bootstrap() -> None:
    if guideline_db.count() == 0:
        guideline_db.seed_defaults()
    # Ensure sample ad PNGs exist on Render even after ephemeral filesystem resets
    v_file = SAMPLE_ASSETS_DIR / "sample_violation_ad.png"
    c_file = SAMPLE_ASSETS_DIR / "sample_compliant_ad.png"
    if not v_file.exists() or not c_file.exists():
        try:
            ensure_sample_assets(SAMPLE_ASSETS_DIR)
        except Exception as exc:
            logger.warning("Could not generate sample assets on startup: %s", exc)


# ---------------------------------------------------------------------------
# Health & Auth Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/health")
def health_check() -> Dict[str, Any]:
    return {
        "status": "ok",
        "guidelines_count": guideline_db.count(),
        "ai_configured": ai_engine.is_ai_configured(),
    }


@app.post("/api/auth/login")
def login(payload: LoginRequest) -> Dict[str, Any]:
    username = payload.username.strip()
    password = payload.password.strip()
    if username != DEMO_USERNAME or password != DEMO_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password. Use demo credentials: test123 / test123.",
        )
    token = create_auth_token(username)
    return {
        "token": token,
        "token_type": "bearer",
        "username": username,
    }


@app.get("/api/auth/me")
def auth_me(username: str = Depends(get_current_user)) -> Dict[str, Any]:
    return {"authenticated": True, "username": username}


# ---------------------------------------------------------------------------
# Dynamic Guideline Management / RAG Updater Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/guidelines")
def list_guidelines() -> Dict[str, Any]:
    rules = guideline_db.list_guidelines()
    return {"guidelines": rules, "count": len(rules)}


@app.post("/api/guidelines/text", status_code=status.HTTP_201_CREATED)
def add_guideline_text(payload: GuidelineTextRequest) -> Dict[str, Any]:
    title = payload.title.strip()
    content = payload.content.strip()
    if not title or not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Both guideline title and rule content are required.",
        )
    created = guideline_db.add_guideline(title=title, content=content, source="manual")
    return {
        "guideline": created,
        "count": guideline_db.count(),
    }


@app.post("/api/guidelines/upload", status_code=status.HTTP_201_CREATED)
async def upload_guideline_file(file: UploadFile = File(...)) -> Dict[str, Any]:
    filename = (file.filename or "").strip()
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_DOC_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Only .pdf, .docx, and .txt files are allowed.",
        )

    raw_bytes = await file.read()
    if len(raw_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )
    if len(raw_bytes) > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds the 5MB maximum size limit.",
        )

    try:
        extracted_text = _extract_document_text(filename, raw_bytes)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read {ext} document: {exc}",
        ) from exc

    if not extracted_text or not extracted_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No readable text was found inside the uploaded document.",
        )

    added_rules = guideline_db.add_document_chunks(filename=filename, raw_text=extracted_text)
    return {
        "added": added_rules,
        "added_count": len(added_rules),
        "count": guideline_db.count(),
    }


@app.delete("/api/guidelines/{rule_id}")
def delete_guideline(rule_id: str) -> Dict[str, Any]:
    deleted = guideline_db.delete_guideline(rule_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Guideline '{rule_id}' was not found.",
        )
    return {
        "deleted_id": rule_id,
        "count": guideline_db.count(),
    }


@app.post("/api/guidelines/reset")
def reset_guidelines() -> Dict[str, Any]:
    rules = guideline_db.reset_to_defaults()
    return {
        "status": "reset",
        "guidelines": rules,
        "count": len(rules),
    }


# ---------------------------------------------------------------------------
# Text Compliance Audit Endpoint
# ---------------------------------------------------------------------------
@app.post("/api/review")
def review_text(payload: TextReviewRequest) -> Dict[str, Any]:
    copy_text = (payload.text or "").strip()
    if not copy_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please enter marketing copy to audit. Empty or whitespace-only text is not allowed.",
        )

    active_rules = guideline_db.query_relevant_guidelines(copy_text)
    try:
        result = ai_engine.review_text_compliance(copy_text, active_rules)
        return result
    except ai_engine.AIConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Unhandled error in /api/review")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Compliance engine error: {exc}",
        ) from exc


# ---------------------------------------------------------------------------
# Multimodal Visual Compliance Audit & Sample Assets Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/samples/images/{filename}")
def get_sample_image(filename: str) -> FileResponse:
    # Prevent path traversal strictly
    safe_name = Path(filename).name
    if safe_name != filename or safe_name not in {
        "sample_violation_ad.png",
        "sample_compliant_ad.png",
    }:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sample image not found.",
        )

    file_path = SAMPLE_ASSETS_DIR / safe_name
    if not file_path.exists():
        ensure_sample_assets(SAMPLE_ASSETS_DIR)
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sample image asset is unavailable.",
        )
    return FileResponse(file_path, media_type="image/png", filename=safe_name)


@app.post("/api/review/image")
async def review_image(
    file: UploadFile = File(...),
    caption: Optional[str] = Form(default=""),
) -> Dict[str, Any]:
    filename = (file.filename or "").strip()
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported image format. Please upload PNG, JPG, JPEG, or WEBP.",
        )

    image_bytes = await file.read()
    if len(image_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded image file is empty.",
        )
    if len(image_bytes) > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Image exceeds the 5MB maximum size limit.",
        )

    mime_type = IMAGE_MIME_MAP.get(ext, file.content_type or "image/png")
    query_hint = (caption or "").strip() or "visual ad contrast urgency claims typography brand tone"
    active_rules = guideline_db.query_relevant_guidelines(query_hint)

    try:
        result = ai_engine.review_image_compliance(
            image_bytes=image_bytes,
            mime_type=mime_type,
            guidelines=active_rules,
            caption=caption,
        )
        return result
    except ai_engine.AIConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except ai_engine.AITimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Unhandled error in /api/review/image")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Visual compliance engine error: {exc}",
        ) from exc


# ---------------------------------------------------------------------------
# Static SPA Hosting on / (keeps /docs, /redoc, /openapi.json, /api/* intact)
# ---------------------------------------------------------------------------
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
def serve_spa() -> FileResponse:
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        return JSONResponse(  # type: ignore[return-value]
            status_code=404,
            content={"detail": "Frontend static/index.html not found."},
        )
    return FileResponse(index_path, media_type="text/html")
