"""
BrandGuard AI — Dynamic Brand Guideline Store (ChromaDB + Lightweight Deterministic Embeddings)

Designed specifically for Render's 512MB RAM free tier:
- Uses a zero-dependency deterministic hashed n-gram embedding function so ChromaDB
  never downloads or loads heavy PyTorch/ONNX models into memory.
- Combines vector cosine similarity with keyword token matching for high-precision
  hybrid retrieval.
- Automatically seeds 4 default enterprise brand guidelines on startup whenever
  the collection is empty (resilient to ephemeral filesystem wipes).
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import chromadb
    from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

    CHROMADB_AVAILABLE = True
except ImportError:
    chromadb = None  # type: ignore[assignment]
    Documents = List[str]  # type: ignore[misc, assignment]
    Embeddings = List[List[float]]  # type: ignore[misc, assignment]
    EmbeddingFunction = object  # type: ignore[misc, assignment]
    CHROMADB_AVAILABLE = False


EMBEDDING_DIM = 128
TOKEN_RE = re.compile(r"[a-z0-9]+")

DEFAULT_GUIDELINES: List[Dict[str, str]] = [
    {
        "id": "default-rule-1",
        "title": "Formal Enterprise Tone",
        "content": (
            "Always maintain a formal, professional enterprise tone; avoid "
            'exclamation marks and slang ("crazy", "insane", "awesome").'
        ),
        "source": "default_policy",
    },
    {
        "id": "default-rule-2",
        "title": "No Financial or ROI Guarantees",
        "content": "Never guarantee ROI, profits, or specific financial outcomes.",
        "source": "default_policy",
    },
    {
        "id": "default-rule-3",
        "title": "Client Terminology Standard",
        "content": (
            'Always refer to buyers as "Clients", never "Customers" or "Guys".'
        ),
        "source": "default_policy",
    },
    {
        "id": "default-rule-4",
        "title": "Visual & Urgency Compliance",
        "content": (
            "Visual and written ads must avoid misleading urgency claims "
            '(e.g., "100% Guaranteed", "Risk-Free Overnight") and maintain '
            "clean, accessible contrast."
        ),
        "source": "default_policy",
    },
]


def _tokenize(text: str) -> List[str]:
    return TOKEN_RE.findall(text.lower())


def _embed_text(text: str, dim: int = EMBEDDING_DIM) -> List[float]:
    """Pure-Python deterministic feature-hashing embedding (zero ML RAM overhead)."""
    vec = [0.0] * dim
    tokens = _tokenize(text)
    if not tokens:
        return vec

    features: List[str] = list(tokens)
    for i in range(len(tokens) - 1):
        features.append(f"{tokens[i]}_{tokens[i + 1]}")
    for token in tokens:
        if len(token) >= 4:
            for i in range(len(token) - 2):
                features.append(f"c:{token[i:i + 3]}")

    for feat in features:
        digest = hashlib.blake2b(feat.encode("utf-8"), digest_size=8).digest()
        idx = int.from_bytes(digest[:4], "little") % dim
        sign = 1.0 if (digest[4] & 1) == 0 else -1.0
        vec[idx] += sign

    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0.0:
        vec = [v / norm for v in vec]
    return vec


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


class LightweightDeterministicEmbeddingFunction(EmbeddingFunction):  # type: ignore[misc]
    """ChromaDB-compatible embedding function with ~0MB memory footprint."""

    def __call__(self, input: Documents) -> Embeddings:  # noqa: A002
        return [_embed_text(doc) for doc in input]


def chunk_text(text: str, max_chars: int = 650, overlap: int = 80) -> List[str]:
    """Split uploaded document text into clean, self-contained guideline chunks."""
    cleaned = re.sub(r"\r\n?", "\n", text).strip()
    if not cleaned:
        return []

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", cleaned) if p.strip()]
    chunks: List[str] = []
    current = ""

    for para in paragraphs:
        # Collapse internal single newlines inside a paragraph
        para_norm = re.sub(r"\s+", " ", para).strip()
        if not para_norm:
            continue

        if len(para_norm) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            # Split long paragraph by sentences or sliding window
            sentences = re.split(r"(?<=[.!?])\s+", para_norm)
            buf = ""
            for sent in sentences:
                if len(sent) > max_chars:
                    if buf:
                        chunks.append(buf)
                        buf = ""
                    step = max(1, max_chars - overlap)
                    for start in range(0, len(sent), step):
                        piece = sent[start : start + max_chars].strip()
                        if piece:
                            chunks.append(piece)
                elif len(buf) + len(sent) + 1 <= max_chars:
                    buf = f"{buf} {sent}".strip()
                else:
                    if buf:
                        chunks.append(buf)
                    buf = sent
            if buf:
                chunks.append(buf)
        elif len(current) + len(para_norm) + 1 <= max_chars:
            current = f"{current} {para_norm}".strip()
        else:
            if current:
                chunks.append(current)
            current = para_norm

    if current:
        chunks.append(current)

    return chunks


class GuidelineDatabase:
    """
    Manages brand guidelines in ChromaDB with automatic fallback to a local
    JSON-persisted vector store if chromadb is not installed in an offline
    test environment.
    """

    def __init__(
        self,
        persist_dir: Optional[str] = None,
        collection_name: str = "brand_guidelines",
        auto_seed: bool = True,
    ) -> None:
        base_dir = Path(__file__).resolve().parent
        default_dir = os.getenv("CHROMA_PERSIST_DIR", str(base_dir / "chroma_db"))
        self.persist_dir = Path(persist_dir or default_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.collection_name = collection_name
        self._lock = threading.RLock()

        self._use_chroma = CHROMADB_AVAILABLE and os.getenv(
            "BRANDGUARD_FORCE_LOCAL_STORE", ""
        ).lower() not in {"1", "true", "yes"}
        self._client = None
        self._collection = None
        self._fallback_file = self.persist_dir / f"{collection_name}.json"
        self._fallback_records: Dict[str, Dict[str, Any]] = {}

        self._init_backend()
        if auto_seed and self.count() == 0:
            self.seed_defaults()

    def _init_backend(self) -> None:
        if self._use_chroma and chromadb is not None:
            self._embedding_fn = LightweightDeterministicEmbeddingFunction()
            self._client = chromadb.PersistentClient(path=str(self.persist_dir))
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                embedding_function=self._embedding_fn,
                metadata={"hnsw:space": "cosine"},
            )
        else:
            self._use_chroma = False
            self._load_fallback()

    def _load_fallback(self) -> None:
        if self._fallback_file.exists():
            try:
                data = json.loads(self._fallback_file.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self._fallback_records = data
                    return
            except Exception:
                pass
        self._fallback_records = {}

    def _save_fallback(self) -> None:
        self._fallback_file.write_text(
            json.dumps(self._fallback_records, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def count(self) -> int:
        with self._lock:
            if self._use_chroma and self._collection is not None:
                return int(self._collection.count())
            return len(self._fallback_records)

    def seed_defaults(self) -> List[Dict[str, Any]]:
        """Seed the 4 default enterprise brand guidelines."""
        seeded: List[Dict[str, Any]] = []
        with self._lock:
            for item in DEFAULT_GUIDELINES:
                record = self.add_guideline(
                    title=item["title"],
                    content=item["content"],
                    source=item["source"],
                    rule_id=item["id"],
                )
                seeded.append(record)
        return seeded

    def add_guideline(
        self,
        title: str,
        content: str,
        source: str = "manual",
        rule_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        clean_title = title.strip()
        clean_content = content.strip()
        if not clean_title or not clean_content:
            raise ValueError("Guideline title and content must be non-empty.")

        gid = rule_id or f"rule-{uuid.uuid4().hex[:10]}"
        created_at = self._now_iso()
        doc_text = f"{clean_title}: {clean_content}"
        meta = {
            "title": clean_title,
            "source": source.strip() or "manual",
            "created_at": created_at,
        }

        with self._lock:
            if self._use_chroma and self._collection is not None:
                self._collection.upsert(
                    ids=[gid],
                    documents=[clean_content],
                    metadatas=[meta],
                )
            else:
                self._fallback_records[gid] = {
                    "id": gid,
                    "title": clean_title,
                    "content": clean_content,
                    "source": meta["source"],
                    "created_at": created_at,
                    "embedding": _embed_text(doc_text),
                }
                self._save_fallback()

        return {
            "id": gid,
            "title": clean_title,
            "content": clean_content,
            "source": meta["source"],
            "created_at": created_at,
        }

    def add_document_chunks(
        self,
        filename: str,
        raw_text: str,
    ) -> List[Dict[str, Any]]:
        """Chunk an uploaded document and upsert each chunk as a brand guideline."""
        chunks = chunk_text(raw_text)
        if not chunks:
            raise ValueError("No readable text could be extracted from the uploaded file.")

        stem = Path(filename).stem.replace("_", " ").replace("-", " ").strip() or "Uploaded Policy"
        added: List[Dict[str, Any]] = []
        total = len(chunks)
        for idx, chunk in enumerate(chunks, start=1):
            title = f"{stem}" if total == 1 else f"{stem} (Part {idx}/{total})"
            record = self.add_guideline(
                title=title,
                content=chunk,
                source=f"upload:{filename}",
            )
            added.append(record)
        return added

    def list_guidelines(self) -> List[Dict[str, Any]]:
        with self._lock:
            items: List[Dict[str, Any]] = []
            if self._use_chroma and self._collection is not None:
                res = self._collection.get(include=["documents", "metadatas"])
                ids = res.get("ids") or []
                docs = res.get("documents") or []
                metas = res.get("metadatas") or []
                for gid, doc, meta in zip(ids, docs, metas):
                    meta = meta or {}
                    items.append(
                        {
                            "id": gid,
                            "title": str(meta.get("title", "Brand Guideline")),
                            "content": str(doc or ""),
                            "source": str(meta.get("source", "manual")),
                            "created_at": str(meta.get("created_at", "")),
                        }
                    )
            else:
                for rec in self._fallback_records.values():
                    items.append(
                        {
                            "id": rec["id"],
                            "title": rec["title"],
                            "content": rec["content"],
                            "source": rec["source"],
                            "created_at": rec["created_at"],
                        }
                    )

            items.sort(key=lambda r: (r["created_at"], r["id"]))
            return items

    def delete_guideline(self, rule_id: str) -> bool:
        with self._lock:
            if self._use_chroma and self._collection is not None:
                existing = self._collection.get(ids=[rule_id])
                if not existing.get("ids"):
                    return False
                self._collection.delete(ids=[rule_id])
                return True

            if rule_id not in self._fallback_records:
                return False
            del self._fallback_records[rule_id]
            self._save_fallback()
            return True

    def reset_to_defaults(self) -> List[Dict[str, Any]]:
        """Clear all guidelines and re-seed the 4 enterprise defaults."""
        with self._lock:
            if self._use_chroma and self._client is not None:
                try:
                    self._client.delete_collection(name=self.collection_name)
                except Exception:
                    pass
                self._collection = self._client.get_or_create_collection(
                    name=self.collection_name,
                    embedding_function=self._embedding_fn,
                    metadata={"hnsw:space": "cosine"},
                )
            else:
                self._fallback_records = {}
                self._save_fallback()
            return self.seed_defaults()

    def query_relevant_guidelines(
        self,
        query_text: str,
        top_k: int = 12,
    ) -> List[Dict[str, Any]]:
        """
        Hybrid keyword + deterministic vector retrieval.
        If the active rulebook has <= top_k rules, returns ALL active rules ranked
        by relevance so newly added custom rules are guaranteed to be evaluated.
        """
        all_rules = self.list_guidelines()
        if not all_rules:
            return []

        q_vec = _embed_text(query_text)
        q_tokens = set(_tokenize(query_text))

        scored: List[tuple[float, Dict[str, Any]]] = []
        for rule in all_rules:
            combined = f"{rule['title']} {rule['content']}"
            r_vec = _embed_text(combined)
            vec_score = _cosine_similarity(q_vec, r_vec)
            r_tokens = set(_tokenize(combined))
            overlap = len(q_tokens & r_tokens) / max(1, len(q_tokens))
            hybrid_score = (0.65 * vec_score) + (0.35 * overlap)
            scored.append((hybrid_score, rule))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [rule for _, rule in scored[: max(top_k, min(len(all_rules), 25))]]


# Singleton instance used by FastAPI
guideline_db = GuidelineDatabase()
