# scripts/backfill_metadata.py
import sys
sys.path.append('F:\Semantic_search_MVP\src')

# scripts/backfill_metadata.py
import hashlib
import re
from pathlib import Path
from datetime import datetime, timezone
from metadata.schema import DocumentMetadata
from metadata.io import save_metadata, exists_metadata
from utils.paths import pdfs_dir

def compute_md5(file_path: Path) -> str:
    h = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            h.update(chunk)
    return h.hexdigest()

def guess_title_from_filename(stem: str) -> str:
    """
    Make a human-ish guess from filename stem:
    - replace separators with spaces
    - collapse multiple spaces
    - remove trailing year-ish tokens (e.g., 2015, 2025-06)
    """
    s = stem.replace("_", " ").replace("-", " ")
    s = re.sub(r"\s+", " ", s).strip()
    # drop trailing year tokens (e.g., '... 2015', '... 2025 06')
    s = re.sub(r"(?:\s+\d{4}(?:\s*\d{1,2})?)$", "", s).strip()
    return s

def backfill_placeholders():
    folder = pdfs_dir()
    folder.mkdir(parents=True, exist_ok=True)
    pdf_files = sorted(folder.glob("*.pdf"))
    if not pdf_files:
        print("[backfill] No PDFs found.")
        return

    created = skipped = 0
    for pdf in pdf_files:
        doc_id = compute_md5(pdf)
        if exists_metadata(doc_id):
            print(f"[backfill] Skipped (exists): {pdf.name}")
            skipped += 1
            continue

        title_guess = guess_title_from_filename(pdf.stem)

        meta = DocumentMetadata(
            status="draft",                   # <-- important: draft until user confirms
            doc_id=doc_id,
            title=None,                      # <-- no hard title; user will input later
            title_guess=title_guess,         # <-- shown as a suggestion in the form
            authors=[],
            year=None,
            doc_type="other",
            tags=[],
            ingested_at=datetime.now(timezone.utc),
            source_path=str(pdf)
        )
        save_metadata(meta)
        print(f"[backfill] Created placeholder for: {pdf.name} (doc_id={doc_id})")
        created += 1

    print(f"[backfill] Done. Created: {created}, Skipped: {skipped}, Total PDFs: {len(pdf_files)}")

if __name__ == "__main__":
    backfill_placeholders()
