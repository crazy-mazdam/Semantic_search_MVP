# scripts/test_answer.py
from __future__ import annotations
from pathlib import Path
import sys
sys.path.append('F:\Semantic_search_MVP\src')
from generation.answerer import answer_with_citations

def main():
    q = "How population structures are shifting over time?"
    if len(sys.argv) > 1:
        q = " ".join(sys.argv[1:])
    print("Q:", q, flush=True)

    ans = answer_with_citations(q, top_k=5, model="gpt-4.1")

    print("\n=== ANSWER ===\n")
    print(ans.answer)

    print("\n=== CITATIONS ===")
    for i, c in enumerate(ans.citations, 1):
        print(f"[{i}] {c.title} — pages {c.pages}")
        print(f"     {c.excerpt}")

if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    main()
