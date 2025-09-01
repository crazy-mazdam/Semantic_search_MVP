# scripts/ingest_one_pdf.py

# ------------ add src to path
import os
import sys
from pathlib import Path

# Get the project root directory (2 levels up from this file)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = PROJECT_ROOT / 'src'

# Add src directory to Python path
sys.path.append(str(SRC_DIR))

# ------------ end add src to path

from ingestion.pipeline import ingest_one_pdf

def main():
    if len(sys.argv) < 2:
        print("Usage: python -u scripts/ingest_one_pdf.py <path_to_pdf>")
        sys.exit(2)
    pdf_path = Path(sys.argv[1]).resolve()
    if not pdf_path.exists():
        print(f"File not found: {pdf_path}")
        sys.exit(1)

    doc_id = ingest_one_pdf(pdf_path)
    print(f"\n✅ Ingested & indexed md5={doc_id}")

if __name__ == "__main__":
    # add project root to sys.path if needed
    import sys
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    main()