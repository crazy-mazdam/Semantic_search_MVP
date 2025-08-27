# scripts/test_chroma_init.py
from __future__ import annotations
import os, uuid, json
import sys

sys.path.append('F:\Semantic_search_MVP')

from pathlib import Path
from typing import Dict, Any
from src.indexing.chroma_db import init_chroma, add_chunks, query, reset_collection




def _mk_chunk(text: str, doc_id: str, pages: list[int]) -> Dict[str, Any]:
    cid = uuid.uuid4().hex
    return {
        "chunk_id": cid,
        "text_clean": text,
        "metadata": {
            "doc_id": doc_id,
            "pages_covered": ",".join(map(str, pages)),  # <- string now
            "title": "Demo Doc",
            # "anchors": []  # omit in this smoke test
        },
    }

def main():
    print("Init Chroma…", flush=True)
    client, coll = init_chroma()

    # Optional: start from a clean slate for the test
    if os.getenv("RESET_CHROMA", "0") == "1":
        print("Resetting collection…", flush=True)
        reset_collection(client)

    # Create a few demo chunks
    doc_id = "demo-doc"
    chunks = [
        _mk_chunk(
            "Demographic transitions affect savings rates and the current account balance in open economies.",
            doc_id, [1]
        ),
        _mk_chunk(
            "Population aging can reduce labor supply, putting upward pressure on real wages and capital deepening.",
            doc_id, [2]
        ),
        _mk_chunk(
            "Younger economies may benefit from capital inflows to finance investment during their demographic window.",
            doc_id, [3]
        ),
    ]

    print("Upserting demo chunks…", flush=True)
    add_chunks(coll, chunks)

    q = "How does aging influence savings and the current account?"
    print(f"Query: {q}", flush=True)
    res = query(coll, q, top_k=3)

    # Pretty print minimal fields
    for i, (doc, meta, dist) in enumerate(zip(res["documents"][0], res["metadatas"][0], res["distances"][0])):
        print(f"\nResult {i+1}:")
        print(" text:", doc[:160] + ("..." if len(doc) > 160 else ""))
        print(" meta:", json.dumps(meta, ensure_ascii=False))
        print(" dist:", dist)

    print("\nOK ✅ Chroma init + embed + query path works.", flush=True)

if __name__ == "__main__":
    # Ensure project root in sys.path if needed:
    import sys
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    main()
