# src/ingestion/pdf_parser.py
from __future__ import annotations
import hashlib
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Any, Optional

import fitz  # PyMuPDF

from utils.logging_utils import get_logger

log = get_logger(__name__)


@dataclass
class Span:
    text: str
    bbox: List[float]         # [x0, y0, x1, y1]
    start: int                # char start offset in page_text
    end: int                  # char end offset (exclusive)


@dataclass
class PageParse:
    page_number: int          # 1-based
    text: str                 # full page text
    spans: List[Span]         # span-level details


@dataclass
class ParsedDocument:
    file_path: str
    file_name: str
    file_size: int
    md5: str
    pages: List[PageParse]


class PdfParseError(Exception):
    """Raised when a PDF cannot be opened or parsed."""
    pass


def _md5_file(path: Path, chunk_size: int = 1 << 20) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_pdf(pdf_path: str | Path) -> ParsedDocument:
    """
    Parse a PDF with PyMuPDF, returning per-page full text plus span-level text with bboxes and
    character offsets (for precise citation mapping).
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    try:
        doc = fitz.open(pdf_path.as_posix())
    except Exception as e:
        log.error(f"Failed to open PDF: {pdf_path} | error={e}")
        raise PdfParseError(f"Cannot open PDF: {pdf_path}") from e

    pages: List[PageParse] = []
    try:
        for i, page in enumerate(doc):  # 0-based in fitz
            page_no = i + 1
            # Use 'dict' to get blocks/lines/spans with geometry
            # Structure: { "blocks": [ { "lines": [ { "spans": [ { "text", "size", "flags", "font", "bbox" } ] } ] } ] }
            pdict: Dict[str, Any] = page.get_text("dict")  # layout-aware
            page_text_parts: List[str] = []
            spans: List[Span] = []
            cursor = 0

            for block in pdict.get("blocks", []):
                for line in block.get("lines", []):
                    for sp in line.get("spans", []):
                        text: str = sp.get("text", "") or ""
                        bbox = sp.get("bbox", [0, 0, 0, 0])

                        # Normalize newlines: PyMuPDF spans rarely include '\n'; we insert spaces/newlines
                        # Heuristic: append text; add a space between spans in same line
                        if page_text_parts and not page_text_parts[-1].endswith((" ", "\n")):
                            # add a space before next span to avoid gluing tokens
                            page_text_parts.append(" ")
                            cursor += 1

                        start = cursor
                        page_text_parts.append(text)
                        cursor += len(text)
                        end = cursor

                        spans.append(Span(text=text, bbox=[float(x) for x in bbox], start=start, end=end))

                    # End of a line: add newline
                    page_text_parts.append("\n")
                    cursor += 1

            page_text = "".join(page_text_parts).rstrip("\n")

            # NOTE: If page has no text (e.g., image-only), page_text may be empty.
            pages.append(PageParse(page_number=page_no, text=page_text, spans=spans))

    except Exception as e:
        log.exception(f"Parsing failed at page index {i} for {pdf_path}: {e}")
        raise PdfParseError(f"Parsing failed for {pdf_path} at page {i+1}") from e
    finally:
        doc.close()

    parsed = ParsedDocument(
        file_path=str(pdf_path.resolve()),
        file_name=pdf_path.name,
        file_size=pdf_path.stat().st_size,
        md5=_md5_file(pdf_path),
        pages=pages,
    )
    log.info(
        f"Parsed PDF: name={parsed.file_name} pages={len(parsed.pages)} size={parsed.file_size} md5={parsed.md5}"
    )
    return parsed


# Convenience: JSON-like dict for logging/serialization (avoids dataclasses-json dependency)
def parsed_document_to_dict(pd: ParsedDocument) -> Dict[str, Any]:
    return {
        "file_path": pd.file_path,
        "file_name": pd.file_name,
        "file_size": pd.file_size,
        "md5": pd.md5,
        "pages": [
            {
                "page_number": p.page_number,
                "text_len": len(p.text),
                "spans": [
                    {"text": s.text, "bbox": s.bbox, "start": s.start, "end": s.end}
                    for s in p.spans
                ],
            }
            for p in pd.pages
        ],
    }


if __name__ == "__main__":
    # Manual smoke test:
    # python -m src.ingestion.pdf_parser "data/pdfs/sample.pdf"
    import sys, json
    if len(sys.argv) < 2:
        print("Usage: python -m src.ingestion.pdf_parser <pdf_path>")
        sys.exit(1)
    pdf = sys.argv[1]
    parsed = parse_pdf(pdf)
    # Print a compact summary
    summary = parsed_document_to_dict(parsed)
    print(json.dumps(summary, ensure_ascii=False)[:2000])  # truncate for console
