from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import os
import chromadb
from chromadb.config import Settings
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from dotenv import load_dotenv
import json

# Load env early
load_dotenv()

from utils.paths import indexes_dir

COLLECTION_NAME = "documents"

# --- Singleton client instance ---
_CLIENT: Optional[chromadb.api.client.Client] = None


# ----------------- Helpers -----------------
def _persist_dir() -> Path:
    d = indexes_dir() / "chroma"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _get_client() -> chromadb.api.client.Client:
    """
    Return a singleton PersistentClient bound to a stable path.
    Prevents multiple UUID folders when Streamlit reloads or clear_all is called.
    """
    global _CLIENT
    if _CLIENT is not None:
        return _CLIENT

    persist_dir = _persist_dir()

    # Default client without tenant/database to avoid errors on folder deletion
    try:
        _CLIENT = chromadb.PersistentClient(
            path=str(persist_dir),
            settings=Settings(anonymized_telemetry=False)
        )
    except AttributeError:
        # Fallback for very old versions of chromadb
        _CLIENT = chromadb.Client(Settings(
            persist_directory=str(persist_dir),
            anonymized_telemetry=False,
        ))

    return _CLIENT


# ----------------- Main API -----------------
def init_chroma(collection_name: str = COLLECTION_NAME):
    """
    Return (client, collection). If missing, create with embedding_function.
    Avoids embedding conflicts by attaching the embedder only when creating.
    """
    client = _get_client()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not found in environment or .env")

    embed_fn = OpenAIEmbeddingFunction(
        api_key=api_key,
        model_name=os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small"),
    )

    existing = {c.name for c in client.list_collections()}
    if collection_name in existing:
        collection = client.get_collection(name=collection_name)
    else:
        collection = client.create_collection(
            name=collection_name,
            embedding_function=embed_fn
        )

    return client, collection


def clear_all() -> bool:
    """
    Delete the Chroma collection if it exists.
    Collection will be re-created on next init_chroma() call.
    """
    client = _get_client()
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    return True


def query(collection, query_text: str, top_k: int = 5) -> Dict[str, Any]:
    return collection.query(query_texts=[query_text], n_results=top_k)


# ----------------- Chunk helpers -----------------
PRIMITIVES = (str, int, float, bool, type(None))


def _sanitize_meta(d: dict) -> dict:
    out = {}
    for k, v in (d or {}).items():
        if isinstance(v, PRIMITIVES):
            out[k] = v
        elif isinstance(v, (list, tuple)):
            try:
                if all(isinstance(x, PRIMITIVES) for x in v):
                    out[k] = ",".join(map(str, v))
                else:
                    out[k] = json.dumps(v, ensure_ascii=False)
            except Exception:
                out[k] = str(v)
        elif isinstance(v, dict):
            out[k] = json.dumps(v, ensure_ascii=False)
        else:
            out[k] = str(v)
    return out


def _approx_tokens(s: str) -> int:
    return max(1, len(s) // 4)


def add_chunks_batched(
    collection,
    chunks: List[Dict[str, Any]],
    max_text_tokens_per_call: int = 280_000,
    max_items_per_call: int = 256,
) -> None:
    """Upsert chunks in batches without exceeding token or count limits."""
    i = 0
    n = len(chunks)
    while i < n:
        batch_ids, batch_docs, batch_metas = [], [], []
        token_sum = 0
        count = 0
        while i < n and count < max_items_per_call:
            ch = chunks[i]
            doc = ch["text_clean"]
            t = _approx_tokens(doc)
            if token_sum + t > max_text_tokens_per_call and count > 0:
                break
            batch_ids.append(ch["chunk_id"])
            batch_docs.append(doc)
            batch_metas.append(_sanitize_meta(ch.get("metadata", {})))
            token_sum += t
            count += 1
            i += 1

        collection.add(ids=batch_ids, documents=batch_docs, metadatas=batch_metas)


# ----------------- Stats -----------------
def collection_count(collection=None) -> int:
    if collection is None:
        _, collection = init_chroma()
    try:
        return collection.count()
    except Exception:
        return 0


def corpus_stats() -> dict:
    """Return {docs, chunks} or empty if no collection yet."""
    try:
        _, coll = init_chroma()
        data = coll.get()
        chunks = len(data["ids"])
        docs = len(set(meta.get("doc_id", "unknown") for meta in data["metadatas"]))
        return {"docs": docs, "chunks": chunks}
    except Exception:
        return {"docs": 0, "chunks": 0}
