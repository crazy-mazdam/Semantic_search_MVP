# src/retrieval/dense.py
from __future__ import annotations
from typing import List, Dict, Any
from dataclasses import dataclass

from indexing.chroma_db import init_chroma, query as chroma_query

@dataclass
class RetrievedChunk:
    chunk_id: str
    doc_id: str
    text: str
    distance: float
    metadata: Dict[str, Any]

def retrieve(
    query_text: str,
    top_k: int = 5,
    collection_name: str = "documents",
) -> List[RetrievedChunk]:
    """
    Query Chroma and return normalized results.
    """
    _, coll = init_chroma(collection_name=collection_name)
    res = chroma_query(coll, query_text, top_k)
    docs = res.get("documents", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    dists = res.get("distances", [[]])[0]

    hits: List[RetrievedChunk] = []
    for text, meta, dist in zip(docs, metas, dists):
        hits.append(RetrievedChunk(
            chunk_id=str(meta.get("chunk_id", "")),
            doc_id=str(meta.get("doc_id", "")),
            text=text,
            distance=float(dist),
            metadata=meta,
        ))
    # sort by ascending distance (smaller = closer)
    hits.sort(key=lambda h: h.distance)
    return hits