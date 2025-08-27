# scripts/test_retrieval.py
from __future__ import annotations
from pathlib import Path
import sys
sys.path.append('F:\Semantic_search_MVP\src')
from retrieval.dense import retrieve

def main():
    q = "How does population aging affect savings and current accounts?"
    if len(sys.argv) > 1:
        q = " ".join(sys.argv[1:])
    print("Query:", q, flush=True)

    hits = retrieve(q, top_k=5)
    if not hits:
        print("No results. Did you index any chunks yet?")
        return

    for i, h in enumerate(hits, 1):
        pages = h.metadata.get("pages_covered", "")
        title = h.metadata.get("title", "")
        print(f"\n[{i}] dist={h.distance:.3f} pages={pages} title={title}")
        snippet = h.text[:260].replace("\n", " ")
        print("    ", snippet, "..." if len(h.text) > 260 else "")

if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    main()
