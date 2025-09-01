# src/ingestion/pipeline.py
from __future__ import annotations
from pathlib import Path
from typing import Optional, Iterable, Tuple, Callable

from utils.logging_utils import get_logger
from utils.paths import indexes_dir, pdfs_dir
from ingestion.metadata import load_metadata
from ingestion.text_cleaning import clean_document_pages
from ingestion.chunking_stream import build_chunks_streaming
from ingestion.pdf_parser import parse_pdf
from indexing.indexer import upsert_document_chunks
from indexing.chroma_db import corpus_stats, clear_all


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


def reindex_all_pdfs(
    on_status: StatusCB = None,
    on_progress: ProgressCB = None,
    force: bool = True
) -> dict:
    """Reindex all PDFs from data/pdfs. Returns summary stats."""

    if force:
        report_status("Force reindex: clearing existing Chroma data...")
        clear_all()

    def report_status(msg: str):
        if on_status:
            try: on_status(msg)
            except Exception: pass

    pdfs = sorted(Path(pdfs_dir()).glob("*.pdf"))
    if not pdfs:
        report_status("No PDFs found in data/pdfs")
        return {"docs": 0, "chunks": 0}

    total_docs = 0
    for i, pdf_path in enumerate(pdfs, start=1):
        report_status(f"[{i}/{len(pdfs)}] Reindexing {pdf_path.name}")
        try:
            # Same pipeline as ingest_one_pdf
            parsed = parse_pdf(pdf_path)
            doc_id = parsed.md5

            # Clean pages
            page_texts = [(p.page_number, p.text) for p in parsed.pages]
            cleaned = clean_document_pages(page_texts)
            cleaned_iter = ((cp.page_number, cp.cleaned_text) for cp in cleaned.pages)

            # Chunk
            out_path = Path("data/indexes/chunks") / f"{doc_id}.jsonl"
            build_chunks_streaming(
                doc_id=doc_id,
                cleaned_pages_iter=cleaned_iter,
                out_path=out_path,
                target_tokens=1000,
                overlap_tokens=180,
                min_block_len_chars=20,
                on_progress=on_progress
            )

            # Index
            upsert_document_chunks(doc_id, out_path)
            total_docs += 1

        except Exception as e:
            report_status(f"Error: {e}")

    stats = corpus_stats()
    report_status(f"Reindex complete. Docs: {stats['docs']}  Chunks: {stats['chunks']}")
    return stats