from pathlib import Path
import hashlib
import shutil

def save_and_fingerprint(uploaded_file, pdf_dir: Path):
    """Save uploaded file to disk, compute MD5, return (pdf_path, doc_id, title_guess)."""
    pdf_path = pdf_dir / uploaded_file.name
    with open(pdf_path, "wb") as out:
        for chunk in uploaded_file.chunks if hasattr(uploaded_file, "chunks") else [uploaded_file.read()]:
            out.write(chunk)

    # Compute MD5
    h = hashlib.md5()
    with open(pdf_path, "rb") as f:
        for buf in iter(lambda: f.read(4096), b""):
            h.update(buf)
    doc_id = h.hexdigest()

    # Title guess from filename (strip extension, dashes → spaces)
    title_guess = pdf_path.stem.replace("_", " ").replace("-", " ").strip()
    return pdf_path, doc_id, title_guess
