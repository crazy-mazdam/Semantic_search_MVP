# src/indexing/chroma_inspect.py
from typing import Dict, Any, List, Optional
from indexing.chroma_db import init_chroma

def list_all_docs(limit_per_doc: int = 3, filter_doc: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return summary info for all documents in Chroma.
       If filter_doc provided, return *all* chunks for that document,
       including full metadata for doc and chunks."""

    _, coll = init_chroma()
    data = coll.get()  # {"ids": [...], "documents": [...], "metadatas": [...]}

    docs_map = {}
    for chunk_id, text, meta in zip(data["ids"], data["documents"], data["metadatas"]):
        doc_key = meta.get("doc_id", "unknown")
        if filter_doc and filter_doc not in doc_key:
            continue

        if doc_key not in docs_map:
            # Top-level doc metadata
            docs_map[doc_key] = {
                "doc_id": doc_key,
                "title": meta.get("title", ""),
                "authors": meta.get("authors", ""),
                "year": meta.get("year", ""),
                "doc_type": meta.get("doc_type", ""),
                "tags": meta.get("tags", ""),
                "source_path": meta.get("source_path", ""),
                "chunks": []
            }

        # Add chunk info with metadata
        docs_map[doc_key]["chunks"].append({
            "id": chunk_id,
            "pages": meta.get("pages_covered", ""),
            "preview": text[:240].replace("\n", " ") + ("…" if len(text) > 240 else ""),
            "full_text": text,
            "chunk_meta": meta  # full per-chunk metadata
        })

    # Convert to list
    docs_list = []
    for d in docs_map.values():
        all_chunks = d["chunks"]
        d["chunk_count"] = len(all_chunks)
        if filter_doc:
            d["chunks"] = all_chunks
        else:
            d["chunks"] = all_chunks[:limit_per_doc]
        docs_list.append(d)

    return docs_list


