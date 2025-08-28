# src/indexing/chroma_inspect.py
from typing import Dict, Any, List, Optional
from indexing.chroma_db import init_chroma

def list_all_docs(limit_per_doc: int = 3, filter_doc: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return summary info for all documents in Chroma.
       If filter_doc provided, return *all* chunks for that document."""
    _, coll = init_chroma()

    data = coll.get()  # {"ids": [...], "documents": [...], "metadatas": [...]}

    docs_map = {}
    for doc_id, text, meta in zip(data["ids"], data["documents"], data["metadatas"]):
        doc_key = meta.get("doc_id", "unknown")
        if filter_doc and filter_doc not in doc_key:
            continue  # skip non-matching docs if filter is active
        if doc_key not in docs_map:
            docs_map[doc_key] = {
                "doc_id": doc_key,
                "title": meta.get("title", ""),
                "chunks": []
            }
        docs_map[doc_key]["chunks"].append({
            "id": doc_id,
            "pages": meta.get("pages_covered", ""),
            "preview": text[:240].replace("\n", " ") + ("…" if len(text) > 240 else ""),
            "full_text": text
        })

    docs_list = []
    for d in docs_map.values():
        all_chunks = d["chunks"]
        d["chunk_count"] = len(all_chunks)
        if filter_doc:
            # return all chunks if user requested one doc
            d["chunks"] = all_chunks
        else:
            d["chunks"] = all_chunks[:limit_per_doc]
        docs_list.append(d)

    return docs_list

