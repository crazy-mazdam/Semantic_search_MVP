# src/ingestion/chunking_stream.py
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Iterable, Iterator, Tuple, List, Dict, Any, Optional, Callable
from pathlib import Path
import json, io, hashlib

ProgressCB = Optional[Callable[[float, str], None]]

# --------- data ---------
@dataclass
class Chunk:
    doc_id: str
    chunk_id: str
    chunk_idx: int
    text_clean: str
    token_count: int
    pages_covered: List[int]
    anchors: List[Dict[str, Any]]

# --------- utils ---------
def _token_estimate(s: str) -> int:
    # super fast: ~4 chars/token
    return max(1, len(s) // 4)

def _chunk_id(doc_id: str, idx: int) -> str:
    import hashlib
    return hashlib.md5(f"{doc_id}:{idx}".encode("utf-8")).hexdigest()

def _split_paragraphs(text: str) -> Iterator[str]:
    start = 0
    while True:
        idx = text.find("\n\n", start)
        if idx == -1:
            part = text[start:].strip()
            if part:
                yield part
            break
        part = text[start:idx].strip()
        if part:
            yield part
        start = idx + 2

def _make_anchors(blocks: List[Tuple[int, str]], window_chars: int = 160) -> List[Dict[str, Any]]:
    # blocks: [(page_no, para_text), ...] for the chunk
    by_page: Dict[int, List[str]] = {}
    for pno, para in blocks:
        by_page.setdefault(pno, []).append(para)
    anchors: List[Dict[str, Any]] = []
    for p in sorted(by_page.keys()):
        paras = by_page[p]
        anchors.append({
            "page": p,
            "start_snippet": paras[0][:window_chars],
            "end_snippet": paras[-1][-window_chars:],
        })
    return anchors

# --------- STREAMING CHUNKER ---------
def build_chunks_streaming(
    doc_id: str,
    cleaned_pages_iter: Iterable[Tuple[int, str]],   # iterator or list
    out_path: str | Path,
    target_tokens: int = 1000,
    overlap_tokens: int = 180,
    min_block_len_chars: int = 20,
    on_progress: ProgressCB = None,
    meta_doc: object | None = None,   # <--- NEW
) -> Path:
    """
    Stream pages -> paragraphs -> chunks; write each chunk to JSONL immediately.
    Keeps O(overlap) text in memory, not O(document).
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    def report(p, msg):
        if on_progress:
            try: on_progress(float(p), msg)
            except Exception: pass
        else:
            print(f"{p:5.1f}% {msg}", flush=True)

    # current chunk buffers
    cur_blocks: List[Tuple[int, str]] = []  # [(page_no, para_text)]
    cur_tokens = 0
    chunk_idx = 0

    # open output once
    with out_path.open("w", encoding="utf-8") as f:
        # consume pages one by one (iterator-friendly)
        total_pages = 0
        for total_pages, (pno, text) in enumerate(cleaned_pages_iter, start=1):
            # split into paragraphs lazily
            para_count = 0
            for para in _split_paragraphs(text or ""):
                if len(para) < min_block_len_chars:
                    continue
                para_tokens = _token_estimate(para)

                # if it fits, add
                if cur_tokens + para_tokens <= target_tokens or not cur_blocks:
                    cur_blocks.append((pno, para))
                    cur_tokens += para_tokens
                else:
                    # flush current chunk
                    _flush_chunk(doc_id, chunk_idx, cur_blocks, cur_tokens, f, meta_doc)
                    chunk_idx += 1

                    # build overlap tail
                    cur_blocks, cur_tokens = _retain_overlap(cur_blocks, overlap_tokens)

                    # add the new para now
                    cur_blocks.append((pno, para))
                    cur_tokens += para_tokens

                para_count += 1
                if para_count % 1000 == 0:
                    report(0, f"Page {pno}: processed {para_count} paragraphs")

            # small heartbeat per page
            report(0, f"Processed page {pno}")

        # after all pages, flush remainder
        if cur_blocks:
            _flush_chunk(doc_id, chunk_idx, cur_blocks, cur_tokens, f, meta_doc)
            chunk_idx += 1

    report(100, f"Chunking complete: {chunk_idx} chunks -> {out_path}")
    return out_path

def _retain_overlap(cur_blocks: List[Tuple[int, str]], overlap_tokens: int) -> Tuple[List[Tuple[int, str]], int]:
    kept: List[Tuple[int, str]] = []
    total = 0
    for pno, para in reversed(cur_blocks):
        t = _token_estimate(para)
        if total + t > overlap_tokens and kept:
            break
        kept.append((pno, para))
        total += t
    kept.reverse()
    return kept, total

def _flush_chunk(
    doc_id: str,
    idx: int,
    blocks: List[Tuple[int, str]],
    tok_sum: int,
    fhandle,
    meta_doc: object | None = None
) -> None:
    """
    Write one chunk with doc-level metadata into JSONL.
    """
    # Join text paragraphs
    text = "\n\n".join(para for _, para in blocks)
    pages = sorted({p for p, _ in blocks})
    anchors = _make_anchors(blocks)

    # Base chunk record
    record = {
        "doc_id": doc_id,
        "chunk_id": f"{doc_id}_{idx}",
        "chunk_idx": idx,
        "text_clean": text,
        "token_count": tok_sum,
        "pages_covered": pages,
        "anchors": anchors
    }

    # Attach doc-level metadata if available
    if meta_doc is not None:
        get = lambda name, default=None: getattr(meta_doc, name, default) if hasattr(meta_doc, name) else meta_doc.get(name, default) if isinstance(meta_doc, dict) else default
        record.update({
            "title": get("title"),
            "authors": get("authors", []),
            "year": get("year"),
            "doc_type": get("doc_type"),
            "tags": get("tags", []),
            "source_path": get("source_path")
        })

    # Write JSONL line
    fhandle.write(json.dumps(record, ensure_ascii=False) + "\n")
