"""
FastAPI Backend Entrypoint for BrandGuard AI Governance Portal.
"""
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

try:
    from backend.database import init_brand_guidelines, query_brand_guidelines
    from backend.ai_engine import run_brand_check, BrandReviewSchema
except ImportError:
    from database import init_brand_guidelines, query_brand_guidelines
    from ai_engine import run_brand_check, BrandReviewSchema


class ReviewRequest(BaseModel):
    content: str = Field(..., min_length=1, description="Draft marketing or corporate text to audit")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_brand_guidelines()
    yield


app = FastAPI(
    title="BrandGuard AI - Governance API",
    description="Multi-Agent Brand Compliance & Auto-Correction Engine powered by FastAPI, CrewAI, and ChromaDB",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check():
    guidelines = query_brand_guidelines()
    return {"status": "ok", "service": "BrandGuard AI Backend", "guidelines_loaded": bool(guidelines)}


@app.post("/api/review", response_model=BrandReviewSchema)
async def review_content(payload: ReviewRequest):
    if not payload.content or not payload.content.strip():
        raise HTTPException(status_code=400, detail="Content field cannot be empty.")
    raw_json_str = run_brand_check(payload.content)
    if isinstance(raw_json_str, str):
        return json.loads(raw_json_str)
    return raw_json_str
