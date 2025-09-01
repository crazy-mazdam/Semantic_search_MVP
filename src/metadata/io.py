# src/metadata/io.py
from __future__ import annotations
import sys
sys.path.append('F:\\Semantic_search_MVP\\src')


from typing import List, Optional
from metadata.schema import DocumentMetadata

import json
from utils.paths import metadata_dir


def save_metadata(meta: DocumentMetadata) -> None:
    """Save metadata to JSON file, overwriting if exists."""
    path = metadata_dir() / f"{meta.doc_id}.json"
    with open(path, "w", encoding="utf-8") as f:
        f.write(meta.model_dump_json(indent=2))  # handles datetime automatically
    print(f"[metadata] Saved: {path}")


def load_metadata(doc_id: str) -> Optional[DocumentMetadata]:
    """Load metadata JSON for given doc_id. Returns None if missing."""
    path = metadata_dir() / f"{doc_id}.json"
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return DocumentMetadata(**data)


def exists_metadata(doc_id: str) -> bool:
    """Check if metadata JSON exists for given doc_id."""
    return (metadata_dir() / f"{doc_id}.json").exists()


def list_all_metadata() -> List[DocumentMetadata]:
    """Load metadata for all documents in metadata dir."""
    metas: List[DocumentMetadata] = []
    for json_file in metadata_dir().glob("*.json"):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            metas.append(DocumentMetadata(**data))
        except Exception as e:
            print(f"[metadata] Skipped {json_file}: {e}")
    return metas


def delete_metadata(doc_id: str) -> bool:
    """Delete metadata file if exists. Returns True if deleted."""
    path = metadata_dir() / f"{doc_id}.json"
    if path.exists():
        path.unlink()
        print(f"[metadata] Deleted: {path}")
        return True
    return False
