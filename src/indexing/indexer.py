# src/indexing/indexer.py
from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List
import json

from indexing.chroma_db import init_chroma
from indexing.chroma_db import add_chunks_batched
from ingestion.metadata import load_metadata  # to fetch title, file_path by md5

def load_chunks_jsonl(jsonl_path: str | Path) -> List[Dict[str, Any]]:
    payload = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            ch = json.loads(line)
            payload.append(ch)
    return payload

def upsert_document_chunks(doc_id: str, jsonl_path: str | Path) -> None:
    """
    Load chunks from JSONL, flatten metadata to Chroma-safe primitives, and upsert.
    """
    # Get human metadata (title, file_path, etc.)
    meta_doc = load_metadata(doc_id)
    title = meta_doc.title if meta_doc else ""
    source_path = meta_doc.file_path if meta_doc else ""
    payload_raw = load_chunks_jsonl(jsonl_path)

    # Prepare Chroma payload
    payload: List[Dict[str, Any]] = []
    for ch in payload_raw:
        meta = {
            "doc_id": ch["doc_id"],                          # md5
            "chunk_id": ch["chunk_id"],
            "title": title,
            "pages_covered": ",".join(map(str, ch["pages_covered"])),
            "source_path": source_path,
            "md5": ch["doc_id"],
            # anchors are non-primitive -> JSON string
            "anchors_json": json.dumps(ch.get("anchors", []), ensure_ascii=False),
        }
        payload.append({
            "chunk_id": ch["chunk_id"],
            "text_clean": ch["text_clean"],
            "metadata": meta,
        })

    # Upsert to Chroma
    client, coll = init_chroma()
    add_chunks_batched(coll, payload)
