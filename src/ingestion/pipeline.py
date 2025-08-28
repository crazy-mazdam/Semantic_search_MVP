# src/ingestion/pipeline.py
from __future__ import annotations
from pathlib import Path
from typing import Optional, Iterable, Tuple, Callable

from utils.logging_utils import get_logger
from utils.paths import indexes_dir
from ingestion.metadata import load_metadata
from ingestion.text_cleaning import clean_document_pages
from ingestion.chunking_stream import build_chunks_streaming
from ingestion.pdf_parser import parse_pdf
from indexing.indexer import upsert_document_chunks

log = get_logger("pipeline")

ProgressCB = Optional[Callable[[float, str], None]]  # percent 0..100, message
StatusCB   = Optional[Callable[[str], None]]          # text status lines

def ingest_one_pdf(
    pdf_path: str | Path,
    *,
    reindex: bool = False,
    on_status: StatusCB = None,
    on_chunk_progress: ProgressCB = None,
) -> str:
    """End-to-end ingestion for a single PDF: parse -> clean -> chunk -> index.
    Returns: doc_id (md5)
    """
    def report_status(msg: str):
        if on_status:
            try: on_status(msg)
            except Exception: pass
        log.info(msg)

    pdf_path = str(pdf_path)
    report_status(f"ingest_start | path={pdf_path}")

    # 1) Parse
    parsed = parse_pdf(pdf_path)
    doc_id = parsed.md5
    report_status(f"parsed_pdf | md5={doc_id} pages={len(parsed.pages)}")

    # 2) Metadata (optional)
    meta = load_metadata(doc_id)
    if not meta:
        report_status(f"metadata_missing | md5={doc_id}")

    # 3) Clean
    page_texts = [(p.page_number, p.text) for p in parsed.pages]
    cleaned = clean_document_pages(page_texts)
    cleaned_iter: Iterable[Tuple[int, str]] = ((cp.page_number, cp.cleaned_text) for cp in cleaned.pages)
    report_status("cleaned_pages_ready")

    # 4) Chunk (streaming)
    chunks_dir = indexes_dir() / "chunks"; chunks_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = chunks_dir / f"{doc_id}.jsonl"

    report_status("chunking_started")
    build_chunks_streaming(
        doc_id=doc_id,
        cleaned_pages_iter=cleaned_iter,
        out_path=jsonl_path,
        target_tokens=1000,
        overlap_tokens=180,
        min_block_len_chars=20,
        on_progress=on_chunk_progress,   # <-- drives UI bar
    )
    report_status(f"chunking_done | file={jsonl_path}")

    # 5) Index
    report_status("indexing_started")
    upsert_document_chunks(doc_id, jsonl_path)
    report_status("indexing_done")

    report_status("ingest_done")
    return doc_id
