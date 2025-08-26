# src/ingestion/text_cleaning.py
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple, Optional
import re
import unicodedata

from utils.logging_utils import get_logger

log = get_logger("text_cleaning")


# ==============================
# Data structures
# ==============================
@dataclass
class CleanedPage:
    page_number: int                  # 1-based
    raw_text: str                     # original page text (unchanged)
    cleaned_text: str                 # cleaned content used for embeddings/BM25/LLM
    removed_lines: List[str]          # unused in minimal mode (kept for API compatibility)
    kept_line_indices: List[int]      # unused in minimal mode (kept for API compatibility)


@dataclass
class CleanedDocument:
    pages: List[CleanedPage]
    header_candidates: List[str]      # empty in minimal mode
    footer_candidates: List[str]      # empty in minimal mode


# ==============================
# Regex helpers (minimal mode)
# ==============================
_DEHYPHENATE_RE      = re.compile(r"(\w+)-\n(\w+)")
_SINGLE_NL_RE        = re.compile(r"(?<!\n)\n(?!\n)")  # single \n not part of \n\n
_MULTI_BLANKS_RE     = re.compile(r"\n{3,}")           # 3+ blank lines
_MULTI_SPACES_RE     = re.compile(r"[ \t]{2,}")        # 2+ spaces/tabs
_CONTROL_CHARS_RE    = re.compile(r"[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]")


# ==============================
# Public API (minimal cleaning)
# ==============================
def clean_document_pages(
    page_texts: List[Tuple[int, str]],
    pdf_path: Optional[str] = None,   # ignored in the simplified version
) -> CleanedDocument:
    """
    Minimal cleaning for v1 (header/footer detection disabled):
      - Unicode normalize (NFKC) + strip control chars
      - Standardize newlines to '\n'
      - Fix hyphenation across line breaks: 'word-\\nword' -> 'wordword'
      - Convert single newlines to spaces (soft wrap); keep double '\\n\\n' as paragraph breaks
      - Collapse multiple spaces and reduce 3+ blank lines to exactly 2
    Returns a CleanedDocument with per-page cleaned_text for embeddings/BM25/LLM.
    raw_text remains untouched for citation anchoring elsewhere.
    """
    cleaned_pages: List[CleanedPage] = []

    for (pno, raw_page_text) in page_texts:
        # 1) Normalize unicode (NFKC) and remove control characters
        txt = _normalize_unicode(raw_page_text)
        txt = _strip_control_chars(txt)

        # 2) Standardize newlines
        txt = txt.replace("\r\n", "\n").replace("\r", "\n")

        # 3) De-hyphenate across line breaks: 'foo-\\nbar' -> 'foobar'
        txt = _dehyphenate_across_lines(txt)

        # 4) Collapse SINGLE newlines -> space; keep DOUBLE newlines as paragraph breaks
        txt = _collapse_single_newlines(txt)

        # 5) Collapse multiple spaces + reduce 3+ blank lines to exactly 2
        txt = _collapse_whitespace(txt)

        cleaned_pages.append(CleanedPage(
            page_number=pno,
            raw_text=raw_page_text,   # keep original for precise citation offsets
            cleaned_text=txt,
            removed_lines=[],         # not used in minimal mode
            kept_line_indices=[],     # not used in minimal mode
        ))

    log.info(f"cleaned_pages_done | count={len(cleaned_pages)} (minimal mode)")
    return CleanedDocument(
        pages=cleaned_pages,
        header_candidates=[],  # not computed in minimal mode
        footer_candidates=[],
    )


# ==============================
# Internal helpers (minimal mode)
# ==============================
def _normalize_unicode(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "")

def _strip_control_chars(text: str) -> str:
    return _CONTROL_CHARS_RE.sub("", text)

def _dehyphenate_across_lines(text: str) -> str:
    # Apply repeatedly in case there are several occurrences
    prev = None
    while prev != text:
        prev = text
        text = _DEHYPHENATE_RE.sub(r"\1\2", text)
    return text

def _collapse_single_newlines(text: str) -> str:
    # Turn single \n into a space; leave \n\n intact (paragraph separation)
    return _SINGLE_NL_RE.sub(" ", text)

def _collapse_whitespace(text: str) -> str:
    # Reduce 3+ blank lines to exactly 2 (keep paragraph separation)
    text = _MULTI_BLANKS_RE.sub("\n\n", text)
    # Collapse multiple spaces/tabs
    text = _MULTI_SPACES_RE.sub(" ", text)
    # Final trim
    return text.strip()
