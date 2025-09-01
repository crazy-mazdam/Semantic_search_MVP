# src/indexing/chroma_db.py
from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any, Tuple
import os
import chromadb
from chromadb.config import Settings
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from dotenv import load_dotenv   # <-- add this


# Load .env so OPENAI_API_KEY becomes visible to os.getenv
load_dotenv()

# NEW: use project-rooted path
from utils.paths import indexes_dir

COLLECTION_NAME = "documents"

def _persist_dir() -> Path:
    # always the same path regardless of CWD
    d = indexes_dir() / "chroma"
    d.mkdir(parents=True, exist_ok=True)
    return d

def init_chroma(collection_name: str = COLLECTION_NAME):
    load_dotenv()
    persist_dir = _persist_dir()

    # Prefer PersistentClient to avoid surprises
    try:
        client = chromadb.PersistentClient(path=str(persist_dir))
    except AttributeError:
        # fallback for older chromadb
        client = chromadb.Client(Settings(
            persist_directory=str(persist_dir),
            anonymized_telemetry=False,
        ))

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not found in environment or .env")

    embed_fn = OpenAIEmbeddingFunction(
        api_key=api_key,
        model_name=os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small"),
    )

    collection = client.get_or_create_collection(
        name=collection_name,
        embedding_function=embed_fn,
    )
    return client, collection


def query(collection, query_text: str, top_k: int = 5) -> Dict[str, Any]:
    """Query the collection by text."""
    return collection.query(query_texts=[query_text], n_results=top_k)

def reset_collection(client, collection_name: str = COLLECTION_NAME) -> None:
    """Danger: deletes and recreates the collection (for clean tests)."""
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass
    client.create_collection(collection_name)

import json

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
    # Fast ~4 chars per token
    return max(1, len(s) // 4)

def add_chunks_batched(
    collection,
    chunks: List[Dict[str, Any]],
    max_text_tokens_per_call: int = 280_000,   # below 300k hard limit
    max_items_per_call: int = 256,             # also cap by count
) -> None:
    """Upsert chunks in safe batches so embedding requests never exceed limits."""
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

def collection_count(collection=None) -> int:
    """Return number of records (chunks) in the default collection."""
    if collection is None:
        _, collection = init_chroma()
    try:
        return collection.count()
    except Exception:
        return 0
    
def corpus_stats() -> dict:
    """Return {docs: int, chunks: int} from Chroma collection."""
    _, coll = init_chroma()
    try:
        data = coll.get()
        chunks = len(data["ids"])
        docs = len(set(meta.get("doc_id", "unknown") for meta in data["metadatas"]))
        return {"docs": docs, "chunks": chunks}
    except Exception:
        return {"docs": 0, "chunks": 0}
    
def clear_all():
    """Delete and recreate the Chroma collection to avoid stale data or conflicts."""
    from chromadb import PersistentClient

    persist_dir = _persist_dir()
    client = PersistentClient(path=str(persist_dir))

    # Try to delete old collection completely
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass  # It's fine if it doesn't exist

    # Recreate with embedder
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not found in environment or .env")

    embed_fn = OpenAIEmbeddingFunction(
        api_key=api_key,
        model_name=os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small"),
    )

    client.create_collection(
        name=COLLECTION_NAME,
        embedding_function=embed_fn
    )
    return True