# src/ingestion/pipeline.py
from __future__ import annotations

import sys
sys.path.append('F:\Semantic_search_MVP\src')

from pathlib import Path
from typing import Optional, Iterable, Tuple, Callable

from utils.logging_utils import get_logger
from utils.paths import indexes_dir, pdfs_dir

from ingestion.text_cleaning import clean_document_pages
from ingestion.chunking_stream import build_chunks_streaming
from ingestion.pdf_parser import parse_pdf
from indexing.indexer import upsert_document_chunks
from indexing.chroma_db import corpus_stats, clear_all, init_chroma

from metadata.io import load_metadata, save_metadata, exists_metadata
from metadata.schema import DocumentMetadata
from datetime import datetime, timezone


log = get_logger("pipeline")

ProgressCB = Optional[Callable[[float, str], None]]  # percent 0..100, message
StatusCB   = Optional[Callable[[str], None]]          # text status lines


def ensure_metadata_for_pdf(pdf_path: Path, doc_id: str):
    """Create draft metadata JSON if not exists."""
    if exists_metadata(doc_id):
        return  # already there → skip

    meta = DocumentMetadata(
        status="draft",
        doc_id=doc_id,
        title=None,
        title_guess=pdf_path.stem,  # nice prefill for UI
        authors=[],
        year=None,
        doc_type="other",
        tags=[],
        ingested_at=datetime.now(timezone.utc),
        source_path=str(pdf_path)
    )
    save_metadata(meta)

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

    # 2) Metadata handling
    meta = load_metadata(doc_id)

    if not meta:
        raise RuntimeError(f"No metadata found for {doc_id}")

    # Metadata exists but not ready → stop ingestion
    if meta.status != "ready":
        log.info(f"Skipping {doc_id}: metadata not ready")
        return doc_id

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
        meta_doc=meta,               # <-- for titles in chunks
    )
    report_status(f"chunking_done | file={jsonl_path}")

    # 5) Index
    report_status("indexing_started")
    upsert_document_chunks(doc_id, jsonl_path)
    report_status("indexing_done")

    report_status("ingest_done")
    return doc_id


def reindex_all_pdfs(
    on_status: StatusCB = None,
    on_progress: ProgressCB = None,
    force: bool = True
) -> dict:
    """
    Reindex all PDFs from data/pdfs folder in a robust, isolated way.
    Returns final corpus stats {docs, chunks}.
    """

    def report(msg: str):
        if on_status:
            try:
                on_status(msg)
            except Exception:
                pass
        log.info(msg)

    pdf_dir = Path(pdfs_dir())
    pdfs = sorted(pdf_dir.glob("*.pdf"))
    if not pdfs:
        report("No PDFs found in data/pdfs")
        return {"docs": 0, "chunks": 0}

    # Step 1: Clear collection if requested
    if force:
        report("Clearing existing Chroma collection...")
        clear_all()

    # Step 2: Ensure collection exists before starting
    _, coll = init_chroma()

    # Prepare chunks dir
    chunks_dir = indexes_dir() / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)

    total = len(pdfs)
    successes, failures = 0, 0

    report(f"Starting reindex for {total} PDFs...")

    # Step 3: Process each PDF independently
    for i, pdf_path in enumerate(pdfs, start=1):
        report(f"[{i}/{total}] Processing {pdf_path.name}")

        try:
            parsed = parse_pdf(pdf_path)
            doc_id = parsed.md5

            # Load and validate metadata
            meta = load_metadata(doc_id)
            if not meta or meta.status != "ready":
                report(f"Skipping {doc_id}: metadata missing or not ready")
                failures += 1
                continue

            # Clean text
            page_texts = [(p.page_number, p.text) for p in parsed.pages]
            cleaned = clean_document_pages(page_texts)
            cleaned_iter = ((cp.page_number, cp.cleaned_text) for cp in cleaned.pages)

            # Chunk to JSONL
            jsonl_path = chunks_dir / f"{doc_id}.jsonl"
            build_chunks_streaming(
                doc_id=doc_id,
                cleaned_pages_iter=cleaned_iter,
                out_path=jsonl_path,
                target_tokens=1000,
                overlap_tokens=180,
                min_block_len_chars=20,
                on_progress=on_progress,
                meta_doc=meta,
            )

            # Index into Chroma
            upsert_document_chunks(doc_id, jsonl_path)

            successes += 1
            report(f"[{i}/{total}] Done: {pdf_path.name}")

        except Exception as e:
            failures += 1
            report(f"[{i}/{total}] Failed: {pdf_path.name} | Error: {e}")

    # Step 4: Final corpus stats
    stats = corpus_stats()
    report(
        f"Reindex complete. "
        f"Successes: {successes}, Failures: {failures}, "
        f"Docs: {stats['docs']}, Chunks: {stats['chunks']}"
    )
    return stats
