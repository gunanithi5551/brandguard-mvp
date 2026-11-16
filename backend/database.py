"""
ChromaDB in-memory vector store initialization and guideline query module for BrandGuard AI.
"""
from typing import List, Dict, Any

BRAND_GUIDELINES_TEXT = (
    "BRAND GUIDELINES: "
    "1. Always use a professional tone. "
    "2. Never guarantee ROI or specific financial outcomes. "
    "3. Refer to users as 'Clients', never 'Customers'."
)

COLLECTION_NAME = "brand_guidelines"


class _InMemoryCollectionFallback:
    """Fallback in-memory collection when chromadb binary is unavailable in restricted containers."""

    def __init__(self, name: str):
        self.name = name
        self._docs: Dict[str, str] = {}
        self._metadatas: Dict[str, Dict[str, Any]] = {}

    def count(self) -> int:
        return len(self._docs)

    def upsert(self, ids: List[str], documents: List[str], metadatas: List[Dict[str, Any]] = None):
        for idx, doc_id in enumerate(ids):
            self._docs[doc_id] = documents[idx]
            if metadatas and idx < len(metadatas):
                self._metadatas[doc_id] = metadatas[idx]

    def add(self, ids: List[str], documents: List[str], metadatas: List[Dict[str, Any]] = None):
        self.upsert(ids=ids, documents=documents, metadatas=metadatas)

    def query(self, query_texts: List[str], n_results: int = 1) -> Dict[str, List[List[str]]]:
        docs = list(self._docs.values())[:n_results]
        ids = list(self._docs.keys())[:n_results]
        return {"ids": [ids], "documents": [docs]}


class _InMemoryClientFallback:
    def __init__(self):
        self._collections: Dict[str, _InMemoryCollectionFallback] = {}

    def get_or_create_collection(self, name: str) -> _InMemoryCollectionFallback:
        if name not in self._collections:
            self._collections[name] = _InMemoryCollectionFallback(name)
        return self._collections[name]


try:
    import chromadb  # type: ignore
    _chroma_client = chromadb.Client()
except Exception:
    _chroma_client = _InMemoryClientFallback()

_collection = _chroma_client.get_or_create_collection(name=COLLECTION_NAME)


def init_brand_guidelines() -> str:
    """Injects the canonical BrandGuard AI guidelines into the in-memory ChromaDB collection on startup."""
    _collection.upsert(
        ids=["guideline_core_v1"],
        documents=[BRAND_GUIDELINES_TEXT],
        metadatas=[{"source": "corporate_governance", "version": "1.0"}],
    )
    return BRAND_GUIDELINES_TEXT


def query_brand_guidelines(query_text: str = "brand compliance rules") -> str:
    """Queries the in-memory ChromaDB collection for relevant brand guidelines."""
    if _collection.count() == 0:
        init_brand_guidelines()
    results = _collection.query(query_texts=[query_text], n_results=1)
    documents = results.get("documents", [[]])
    if documents and documents[0]:
        return documents[0][0]
    return BRAND_GUIDELINES_TEXT


# Initialize immediately on module import as well as FastAPI startup
init_brand_guidelines()
