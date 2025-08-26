# src/ingestion/metadata.py
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, List
from datetime import datetime
import json
import re
from pathlib import Path

import fitz  # PyMuPDF

from utils.paths import metadata_dir
from utils.logging_utils import get_logger

log = get_logger("metadata")

INDEX_FILE = metadata_dir() / "_index.json"
DOI_RE = re.compile(r"^10\.\d{4,9}/[-._;()/:A-Z0-9]+$", re.I)

DOC_TYPES = ("book", "chapter", "paper", "report", "dataset", "other")

@dataclass
class DocumentMetadata:
    # User-provided (required)
    title: str
    authors: str
    year: int
    doi: Optional[str]
    doc_type: str
    language: str = "en"

    # User-provided (optional)
    publisher: str = ""
    isbn: str = ""
    url: str = ""
    short_title: str = ""
    edition: str = ""
    volume: str = ""
    issue: str = ""
    pages_total: Optional[int] = None
    tags: Optional[List[str]] = None
    summary: str = ""
    institution: str = ""
    license: str = ""
    notes: str = ""

    # Auto-filled (no manual input)
    doc_id: Optional[str] = None            # md5
    file_name: Optional[str] = None
    file_path: Optional[str] = None
    ingested_at: Optional[str] = None       # ISO datetime
    embeddings_model: Optional[str] = None
    embeddings_version: Optional[str] = None
    corpus_hash: Optional[str] = None


# ------------------------ public API ------------------------

def load_metadata(md5: str) -> Optional[DocumentMetadata]:
    """Return existing metadata for this md5, or None."""
    p = _meta_path(md5)
    if not p.exists():
        return None
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
        return _coerce_docmeta(obj)
    except Exception as e:
        log.error(f"Failed to load metadata for {md5}: {e}")
        return None


def save_metadata(md5: str, file_path: str, file_name: str, meta: DocumentMetadata) -> None:
    """Validate and persist per-doc JSON + update the global index."""
    # validate required fields
    _validate_docmeta(meta)

    # set auto fields
    meta.doc_id = md5
    meta.file_path = str(Path(file_path).resolve())
    meta.file_name = file_name
    meta.ingested_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    # write {md5}.json
    out = _meta_path(md5)
    out.write_text(json.dumps(asdict(meta), ensure_ascii=False, indent=2), encoding="utf-8")

    # update _index.json
    idx = _load_index()
    idx[md5] = {"file_name": file_name, "title": meta.title}
    _save_index(idx)

    log.info(f"metadata_saved | md5={md5} title={meta.title!r} year={meta.year} type={meta.doc_type}")


def ensure_minimal_defaults(file_path: str, info_dict: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Lightweight prefill helper for the UI:
    - Title from filename
    - Authors/Year from PDF info dict if available
    """
    file_path = str(file_path)
    file_name = Path(file_path).name
    title_guess = _nicify_filename(file_name)

    authors_guess = ""
    year_guess: Optional[int] = None
    if info_dict:
        if info_dict.get("author"):
            authors_guess = str(info_dict["author"]).strip()
        # Try to parse creationDate 'D:YYYYMMDD...' or similar
        cd = info_dict.get("creationDate") or info_dict.get("CreationDate")
        y = _parse_year_from_creation_date(cd) if cd else None
        if y:
            year_guess = y

    return {
        "title": title_guess,
        "authors": authors_guess,
        "year": year_guess,
        "doi": "",
        "doc_type": "book",
        "language": "en",
    }


def read_pdf_info_dict(pdf_path: str) -> Dict[str, Any]:
    """Expose PyMuPDF info dict so the UI can prefill from it if desired."""
    try:
        doc = fitz.open(pdf_path)
        info = doc.metadata or {}
        doc.close()
        return info
    except Exception as e:
        log.warning(f"Cannot read PDF metadata from {pdf_path}: {e}")
        return {}


# ------------------------ helpers ------------------------

def _meta_path(md5: str) -> Path:
    return metadata_dir() / f"{md5}.json"

def _load_index() -> Dict[str, Any]:
    if INDEX_FILE.exists():
        try:
            return json.loads(INDEX_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def _save_index(idx: Dict[str, Any]) -> None:
    INDEX_FILE.write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")

def _coerce_docmeta(obj: Dict[str, Any]) -> DocumentMetadata:
    # tolerant load; default optional lists/ints
    tags = obj.get("tags")
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    return DocumentMetadata(
        title=obj.get("title", ""),
        authors=obj.get("authors", ""),
        year=int(obj.get("year")) if obj.get("year") not in (None, "") else 0,
        doi=obj.get("doi") or None,
        doc_type=obj.get("doc_type", "other"),
        language=obj.get("language", "en"),
        publisher=obj.get("publisher", ""),
        isbn=obj.get("isbn", ""),
        url=obj.get("url", ""),
        short_title=obj.get("short_title", ""),
        edition=obj.get("edition", ""),
        volume=obj.get("volume", ""),
        issue=obj.get("issue", ""),
        pages_total=obj.get("pages_total"),
        tags=tags,
        summary=obj.get("summary", ""),
        institution=obj.get("institution", ""),
        license=obj.get("license", ""),
        notes=obj.get("notes", ""),
        doc_id=obj.get("doc_id"),
        file_name=obj.get("file_name"),
        file_path=obj.get("file_path"),
        ingested_at=obj.get("ingested_at"),
        embeddings_model=obj.get("embeddings_model"),
        embeddings_version=obj.get("embeddings_version"),
        corpus_hash=obj.get("corpus_hash"),
    )

def _validate_docmeta(meta: DocumentMetadata) -> None:
    if not meta.title or len(meta.title.strip()) < 3:
        raise ValueError("title must be at least 3 characters")
    if not meta.authors or len(meta.authors.strip()) < 2:
        raise ValueError("authors must be provided")
    if not isinstance(meta.year, int) or not (1800 <= meta.year <= 2100):
        raise ValueError("year must be an integer between 1800 and 2100")
    if meta.doi:
        if not DOI_RE.match(meta.doi.strip()):
            raise ValueError("doi must match 10.xxxx/... pattern")
    if meta.doc_type not in DOC_TYPES:
        raise ValueError(f"doc_type must be one of {DOC_TYPES}")
    if meta.pages_total is not None and (not isinstance(meta.pages_total, int) or meta.pages_total <= 0):
        raise ValueError("pages_total must be a positive integer if provided")
    if meta.tags is not None and not isinstance(meta.tags, list):
        raise ValueError("tags must be a list of strings")

def _nicify_filename(file_name: str) -> str:
    name = Path(file_name).stem
    name = name.replace("_", " ").replace("-", " ")
    name = re.sub(r"\s+", " ", name).strip()
    # Title case lightly (keep ALL CAPS acronyms)
    return " ".join([w if w.isupper() else w.capitalize() for w in name.split(" ")])

def _parse_year_from_creation_date(cd: str) -> Optional[int]:
    # Handles "D:YYYYMMDD..." or plain years in the string
    if not cd:
        return None
    m = re.search(r"(19|20)\d{2}", cd)
    if not m:
        return None
    y = int(m.group(0))
    return y if 1800 <= y <= 2100 else None
