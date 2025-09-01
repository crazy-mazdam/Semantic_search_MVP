# src/indexing/indexer.py
from __future__ import annotations

import sys
sys.path.append('F:\Semantic_search_MVP\src')


from pathlib import Path
from typing import Dict, Any, List
import json

from indexing.chroma_db import init_chroma
from indexing.chroma_db import add_chunks_batched
from metadata.io import load_metadata
from metadata.schema import DocumentMetadata

def load_chunks_jsonl(jsonl_path: str | Path) -> List[Dict[str, Any]]:
    payload = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            ch = json.loads(line)
            payload.append(ch)
    return payload

def upsert_document_chunks(doc_id: str, jsonl_path: str | Path) -> None:
    meta_doc = load_metadata(doc_id)
    title = meta_doc.title if meta_doc else ""
    source_path = meta_doc.source_path if meta_doc else ""
    authors = (meta_doc.authors or []) if meta_doc else []
    year = meta_doc.year if meta_doc else None
    doc_type = meta_doc.doc_type if meta_doc else None
    tags = (meta_doc.tags or []) if meta_doc else []

    payload_raw = load_chunks_jsonl(jsonl_path)

    payload: List[Dict[str, Any]] = []
    for ch in payload_raw:
        meta = {
            "doc_id": ch["doc_id"],
            "chunk_id": ch["chunk_id"],
            "chunk_idx": ch.get("chunk_idx", 0),                         # int
            "title": title or "",                                        # str
            "authors": json.dumps(authors, ensure_ascii=False),          # JSON string (Chroma-safe)
            "year": year,                                                # int | None
            "doc_type": doc_type or "",                                  # str
            "tags": json.dumps(tags, ensure_ascii=False),                # JSON string
            "pages_covered": ",".join(map(str, ch["pages_covered"])),    # comma string
            "source_path": source_path or "",
            "md5": ch["doc_id"],
            "anchors_json": json.dumps(ch.get("anchors", []), ensure_ascii=False),
        }
        payload.append({
            "chunk_id": ch["chunk_id"],
            "text_clean": ch["text_clean"],
            "metadata": meta,
        })

    client, coll = init_chroma()
    add_chunks_batched(coll, payload)
