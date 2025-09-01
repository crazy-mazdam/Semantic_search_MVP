# scripts/metadata_audit.py

import sys
sys.path.append('F:\Semantic_search_MVP\src')

import json
from pathlib import Path
from typing import List
from metadata.io import list_all_metadata, exists_metadata
from metadata.schema import DocumentMetadata
from utils.paths import pdfs_dir, metadata_dir


def audit_metadata():
    pdf_dir = pdfs_dir()
    meta_dir = metadata_dir()

    pdf_files = {pdf.stem: pdf for pdf in pdf_dir.glob("*.pdf")}
    meta_files = {m.stem: m for m in meta_dir.glob("*.json")}

    missing_meta = []    # PDFs with no metadata JSON
    orphan_meta = []     # Metadata JSONs with no PDF
    invalid_meta = []    # Metadata JSONs failing schema
    draft_docs = []      # Metadata with status="draft"

    # 1. PDFs → metadata
    for pdf_stem, pdf_path in pdf_files.items():
        # Hash is doc_id, not filename stem → must parse metadata instead of comparing stems
        # We'll check existence by doc_id after loading metadata
        pass

    # Load metadata JSONs → validate
    all_metadata = []
    for meta_path in meta_dir.glob("*.json"):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            meta = DocumentMetadata(**data)
            all_metadata.append(meta)
            if meta.status == "draft":
                draft_docs.append(meta)
        except Exception as e:
            invalid_meta.append((meta_path, str(e)))

    # Check missing metadata: PDFs with no doc_id JSON file
    for pdf in pdf_files.values():
        # We'll match by MD5 → re-hash here
        import hashlib
        h = hashlib.md5()
        with open(pdf, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                h.update(chunk)
        doc_id = h.hexdigest()
        if not exists_metadata(doc_id):
            missing_meta.append((pdf, doc_id))

    # Check orphan metadata: JSON files with no matching PDF
    doc_ids_with_pdf = {md.doc_id for md in all_metadata if Path(md.source_path).exists()}
    for meta in all_metadata:
        if not Path(meta.source_path).exists():
            orphan_meta.append((meta.doc_id, meta.source_path))

    # Summary
    print("=== Metadata Audit ===")
    print(f"PDFs total:       {len(pdf_files)}")
    print(f"Metadata total:   {len(meta_files)}")
    print(f"Valid metadata:   {len(all_metadata)}")
    print(f"Invalid metadata: {len(invalid_meta)}")
    print(f"Draft metadata:   {len(draft_docs)}")
    print(f"Missing metadata: {len(missing_meta)}")
    print(f"Orphan metadata:  {len(orphan_meta)}")
    print("======================")

    if invalid_meta:
        print("\nInvalid metadata files:")
        for path, err in invalid_meta:
            print(f" - {path.name}: {err}")

    if missing_meta:
        print("\nPDFs missing metadata:")
        for pdf, doc_id in missing_meta:
            print(f" - {pdf.name} (doc_id={doc_id})")

    if orphan_meta:
        print("\nMetadata with missing PDFs:")
        for doc_id, spath in orphan_meta:
            print(f" - {doc_id}: {spath}")

    if draft_docs:
        print("\nDraft metadata (need manual title):")
        for d in draft_docs:
            print(f" - {d.doc_id}: {d.title_guess or d.source_path}")

    print("======================")


if __name__ == "__main__":
    audit_metadata()
