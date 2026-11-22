"""
BrandGuard AI — Round 3 Automated API & Compliance Test Suite

Run with:
    cd backend
    pytest -v

All Gemini / CrewAI calls are mocked deterministically so tests run 100% offline.
"""

from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

# Ensure backend/ is on sys.path when invoked from repo root or backend/
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import ai_engine  # noqa: E402
import main  # noqa: E402
from database import guideline_db  # noqa: E402

client = TestClient(main.app)


def _build_minimal_pdf_bytes(text: str) -> bytes:
    """Create a valid single-page PDF containing `text` without external files."""
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode("latin-1")

    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n",
        f"4 0 obj << /Length {len(stream)} >> stream\n".encode("latin-1")
        + stream
        + b"\nendstream endobj\n",
        b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
    ]

    buf = io.BytesIO()
    buf.write(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(buf.tell())
        buf.write(obj)

    xref_pos = buf.tell()
    buf.write(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
    buf.write(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        buf.write(f"{off:010d} 00000 n \n".encode("latin-1"))
    buf.write(
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode(
            "latin-1"
        )
    )
    return buf.getvalue()


def _make_tiny_png_bytes() -> bytes:
    img = Image.new("RGB", (64, 64), (0, 113, 227))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# 1. Health Check & Frontend SPA Hosting
# ---------------------------------------------------------------------------
def test_health_check_and_frontend_serving() -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert isinstance(body["guidelines_count"], int)
    assert body["guidelines_count"] >= 4
    assert isinstance(body["ai_configured"], bool)

    root_resp = client.get("/")
    assert root_resp.status_code == 200
    assert "text/html" in root_resp.headers["content-type"]
    assert "BrandGuard AI" in root_resp.text
    assert "One-Click Demo Sign In" in root_resp.text

    docs_resp = client.get("/docs")
    assert docs_resp.status_code == 200


# ---------------------------------------------------------------------------
# 2. Authentication (Login, Bad Login 401, Token Verification /api/auth/me)
# ---------------------------------------------------------------------------
def test_auth_login_success_and_me() -> None:
    login_resp = client.post(
        "/api/auth/login",
        json={"username": "test123", "password": "test123"},
    )
    assert login_resp.status_code == 200
    data = login_resp.json()
    assert data["username"] == "test123"
    assert data["token_type"] == "bearer"
    assert "." in data["token"]

    me_resp = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {data['token']}"},
    )
    assert me_resp.status_code == 200
    assert me_resp.json() == {"authenticated": True, "username": "test123"}


def test_auth_bad_credentials_and_invalid_token() -> None:
    bad_resp = client.post(
        "/api/auth/login",
        json={"username": "test123", "password": "wrongpassword"},
    )
    assert bad_resp.status_code == 401
    assert "Invalid username or password" in bad_resp.json()["detail"]

    no_token_resp = client.get("/api/auth/me")
    assert no_token_resp.status_code == 401

    tampered_resp = client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer invalid.token.signature"},
    )
    assert tampered_resp.status_code == 401


# ---------------------------------------------------------------------------
# 3. Validation Edge Cases (400 Empty, 400 Bad File Type, 413 >5MB)
# ---------------------------------------------------------------------------
def test_empty_text_rejection() -> None:
    resp = client.post("/api/review", json={"text": "   \n\t  "})
    assert resp.status_code == 400
    assert "Empty" in resp.json()["detail"] or "enter" in resp.json()["detail"].lower()


def test_invalid_file_type_and_oversized_upload_rejection() -> None:
    # Unsupported document extension -> 400
    bad_doc = client.post(
        "/api/guidelines/upload",
        files={"file": ("malware.exe", b"not allowed", "application/octet-stream")},
    )
    assert bad_doc.status_code == 400

    # Oversized document > 5MB -> 413
    oversized_txt = b"A" * (5 * 1024 * 1024 + 128)
    big_doc = client.post(
        "/api/guidelines/upload",
        files={"file": ("huge_policy.txt", oversized_txt, "text/plain")},
    )
    assert big_doc.status_code == 413

    # Unsupported image extension -> 400
    bad_img = client.post(
        "/api/review/image",
        files={"file": ("vector.svg", b"<svg></svg>", "image/svg+xml")},
    )
    assert bad_img.status_code == 400

    # Oversized image > 5MB -> 413
    oversized_png = b"\x89PNG" + (b"\x00" * (5 * 1024 * 1024 + 64))
    big_img = client.post(
        "/api/review/image",
        files={"file": ("massive.png", oversized_png, "image/png")},
    )
    assert big_img.status_code == 413


# ---------------------------------------------------------------------------
# 4. Dynamic Guideline Management (Seed, Add Text, Upload .txt & .pdf, Delete, Reset)
# ---------------------------------------------------------------------------
def test_guideline_lifecycle_txt_pdf_delete_and_reset() -> None:
    # Reset first so we start from a clean 4-rule baseline
    reset_resp = client.post("/api/guidelines/reset")
    assert reset_resp.status_code == 200
    assert reset_resp.json()["count"] == 4

    list_resp = client.get("/api/guidelines")
    assert list_resp.status_code == 200
    assert list_resp.json()["count"] == 4

    # Add custom text rule
    add_resp = client.post(
        "/api/guidelines/text",
        json={
            "title": "No Discount Language",
            "content": 'Never use the words "cheap" or "discount" in enterprise copy.',
        },
    )
    assert add_resp.status_code == 201
    created_id = add_resp.json()["guideline"]["id"]
    assert add_resp.json()["count"] == 5

    # Upload a .txt rulebook
    txt_bytes = (
        b"Never reference competitor brand names directly in paid social campaigns.\n\n"
        b"All product performance figures must cite a dated internal benchmark."
    )
    txt_resp = client.post(
        "/api/guidelines/upload",
        files={"file": ("social_policy.txt", txt_bytes, "text/plain")},
    )
    assert txt_resp.status_code == 201
    assert txt_resp.json()["added_count"] >= 1
    assert txt_resp.json()["count"] >= 6

    # Upload a real .pdf rulebook
    pdf_bytes = _build_minimal_pdf_bytes(
        "Always include an accessibility alt-text review before publishing banners."
    )
    pdf_resp = client.post(
        "/api/guidelines/upload",
        files={"file": ("accessibility_guide.pdf", pdf_bytes, "application/pdf")},
    )
    assert pdf_resp.status_code == 201
    assert pdf_resp.json()["added_count"] >= 1
    pdf_added = pdf_resp.json()["added"][0]
    assert "accessibility" in pdf_added["content"].lower()

    # Verify hybrid retrieval surfaces the newly added rule immediately
    retrieved = guideline_db.query_relevant_guidelines("cheap discount pricing")
    retrieved_ids = {r["id"] for r in retrieved}
    assert created_id in retrieved_ids

    # Delete the custom text rule
    del_resp = client.delete(f"/api/guidelines/{created_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["deleted_id"] == created_id

    # Deleting a non-existent rule returns 404
    del_missing = client.delete("/api/guidelines/does-not-exist-999")
    assert del_missing.status_code == 404

    # Reset back to 4 enterprise defaults
    final_reset = client.post("/api/guidelines/reset")
    assert final_reset.status_code == 200
    assert final_reset.json()["count"] == 4


# ---------------------------------------------------------------------------
# 5. Text Audit & Visual Audit (Mocked Gemini Responses + 503 Missing Key Handling)
# ---------------------------------------------------------------------------
def test_text_audit_crewai_and_fallback_mocked() -> None:
    mock_violation_json = json.dumps(
        {
            "status": "violation",
            "score": 18,
            "broken_rules": [
                "No Financial or ROI Guarantees: Claims 'millionaire overnight'",
                "Client Terminology Standard: Uses 'customers' instead of 'Clients'",
            ],
            "explanation": "The draft promises guaranteed financial returns and uses prohibited terminology.",
            "suggestion": "Our platform supports enterprise clients in improving operational governance.",
        }
    )

    with patch.dict(os.environ, {"GEMINI_API_KEY": "test-mock-key-123"}):
        # Test primary CrewAI path
        with patch.object(ai_engine, "_run_crewai_text_audit", return_value=mock_violation_json):
            resp = client.post(
                "/api/review",
                json={"text": "Guaranteed to make you a millionaire overnight! Buy now customers!!!"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "violation"
            assert data["score"] == 18
            assert len(data["broken_rules"]) == 2
            assert data["guidelines_checked"] >= 4
            assert "clients" in data["suggestion"].lower()

        # Test automatic fallback to direct Gemini JSON when CrewAI throws
        with patch.object(
            ai_engine, "_run_crewai_text_audit", side_effect=RuntimeError("CrewAI parse error")
        ), patch.object(ai_engine, "_call_gemini_text_json", return_value=mock_violation_json):
            fallback_resp = client.post(
                "/api/review",
                json={"text": "Guaranteed to make you a millionaire overnight!"},
            )
            assert fallback_resp.status_code == 200
            assert fallback_resp.json()["status"] == "violation"


def test_image_audit_mocked_and_missing_api_key_503() -> None:
    mock_vision_json = json.dumps(
        {
            "status": "violation",
            "score": 15,
            "broken_rules": [
                "Visual & Urgency Compliance: Displays '100% GUARANTEED 10X ROI OVERNIGHT!!!'",
            ],
            "visual_findings": [
                "Clashing neon magenta and yellow palette creates poor visual hierarchy.",
            ],
            "text_in_image_findings": [
                "Detected headline: '100% GUARANTEED 10X ROI OVERNIGHT!!!'",
            ],
            "explanation": "The banner violates ROI guarantee, tone, and accessible contrast rules.",
            "actionable_fixes": [
                "Replace guaranteed return claims with measurable value statements.",
                "Use neutral light canvas with dark charcoal text for WCAG AA contrast.",
            ],
        }
    )

    png_bytes = _make_tiny_png_bytes()

    # With valid mocked key -> 200 structured JSON
    with patch.dict(os.environ, {"GEMINI_API_KEY": "test-mock-key-123"}):
        with patch.object(ai_engine, "_call_gemini_vision_json", return_value=mock_vision_json):
            resp = client.post(
                "/api/review/image",
                files={"file": ("ad.png", png_bytes, "image/png")},
                data={"caption": "Act now customers!"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "violation"
            assert data["score"] == 15
            assert len(data["visual_findings"]) == 1
            assert len(data["text_in_image_findings"]) == 1
            assert len(data["actionable_fixes"]) == 2

    # With missing GEMINI_API_KEY -> graceful 503 (never 500 traceback)
    with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
        no_key_text = client.post("/api/review", json={"text": "Enterprise governance software."})
        assert no_key_text.status_code == 503
        assert "GEMINI_API_KEY" in no_key_text.json()["detail"]

        no_key_img = client.post(
            "/api/review/image",
            files={"file": ("ad.png", png_bytes, "image/png")},
        )
        assert no_key_img.status_code == 503
        assert "GEMINI_API_KEY" in no_key_img.json()["detail"]


# ---------------------------------------------------------------------------
# 6. Sample Image Serving
# ---------------------------------------------------------------------------
def test_sample_image_serving() -> None:
    v_resp = client.get("/api/samples/images/sample_violation_ad.png")
    assert v_resp.status_code == 200
    assert v_resp.headers["content-type"] == "image/png"
    assert len(v_resp.content) > 1000

    c_resp = client.get("/api/samples/images/sample_compliant_ad.png")
    assert c_resp.status_code == 200
    assert c_resp.headers["content-type"] == "image/png"
    assert len(c_resp.content) > 1000

    # Path traversal / unknown file rejected
    bad_resp = client.get("/api/samples/images/nonexistent.png")
    assert bad_resp.status_code == 404
