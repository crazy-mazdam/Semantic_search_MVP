# src/ingestion/pipeline.py
from __future__ import annotations
from pathlib import Path
from typing import Optional, Iterable, Tuple

from utils.logging_utils import get_logger
from utils.paths import indexes_dir
from ingestion.metadata import load_metadata
from ingestion.text_cleaning import clean_document_pages
from ingestion.chunking_stream import build_chunks_streaming
# NOTE: adjust import below to your actual PDF parser location/name
from ingestion.pdf_parser import parse_pdf  # parse_pdf(pdf_path) -> object with .md5 and .pages
from indexing.indexer import upsert_document_chunks

log = get_logger("pipeline")

def ingest_one_pdf(pdf_path: str | Path, *, reindex: bool = False) -> str:
    """
    End-to-end ingestion for a single PDF:
      parse -> clean -> chunk (stream) -> index (Chroma)
    Returns: doc_id (md5)
    """
    pdf_path = str(pdf_path)
    log.info(f"ingest_start | path={pdf_path}")

    # 1) Parse PDF (expects: parsed.md5, parsed.pages with .page_number & .text)
    parsed = parse_pdf(pdf_path)
    doc_id = parsed.md5
    log.info(f"parsed_pdf | md5={doc_id} pages={len(parsed.pages)}")

    # 2) (Optional) metadata existence check (manual entry done in V1-011)
    meta = load_metadata(doc_id)
    if not meta:
        log.warning(f"No metadata found for md5={doc_id}. You can add it later via the UI.")

    # 3) Clean pages (minimal cleaner)
    page_texts = [(p.page_number, p.text) for p in parsed.pages]
    cleaned = clean_document_pages(page_texts)
    cleaned_iter: Iterable[Tuple[int, str]] = ((cp.page_number, cp.cleaned_text) for cp in cleaned.pages)
    log.info("cleaned_pages_ready")

    # 4) Stream chunking -> JSONL on disk
    chunks_dir = indexes_dir() / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = chunks_dir / f"{doc_id}.jsonl"

    build_chunks_streaming(
        doc_id=doc_id,
        cleaned_pages_iter=cleaned_iter,
        out_path=jsonl_path,
        target_tokens=1000,
        overlap_tokens=180,
        min_block_len_chars=20,
        on_progress=lambda p, m: log.info(f"{p:.1f}% {m}")  # simple logging callback
    )
    log.info(f"chunks_written | path={jsonl_path}")

    # 5) Upsert chunks into Chroma
    upsert_document_chunks(doc_id, jsonl_path)
    log.info(f"indexed_in_chroma | md5={doc_id}")

    log.info("ingest_done")
    return doc_id
