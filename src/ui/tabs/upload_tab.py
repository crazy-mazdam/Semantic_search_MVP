# src/ui/tabs/upload_tab.py
import sys
sys.path.append('F:\Semantic_search_MVP\src')

import streamlit as st
from metadata.io import list_all_metadata, save_metadata
from metadata.schema import DocumentMetadata

def show_metadata_form():
    """Show a form for any document with status=draft or missing title."""
    metas = list_all_metadata()
    draft_metas = [m for m in metas if m.status == "draft" or not m.title]

    if not draft_metas:
        st.info("All documents have metadata. No action needed.")
        return

    st.subheader("Metadata: Manual Input Needed")
    st.caption("Fill in required metadata for new documents. Title is mandatory.")
    st.write(f"Found {len(draft_metas)} draft metadata files")

    for meta in draft_metas:
        with st.expander(f"Document: {meta.title_guess or meta.source_path}"):
            title = st.text_input("Title", value=meta.title or meta.title_guess or "")
            authors_str = st.text_input("Authors (comma-separated)", value=", ".join(meta.authors or []))
            year = st.number_input("Year", min_value=1000, max_value=3000, value=meta.year or 2025, step=1)
            doc_type = st.selectbox("Document type", ["book", "paper", "article", "report", "other"], index=4)
            tags_str = st.text_input("Tags (comma-separated)", value=", ".join(meta.tags or []))

            if st.button(f"Save metadata for {meta.doc_id}"):
                meta.title = title.strip()
                meta.authors = [a.strip() for a in authors_str.split(",") if a.strip()]
                meta.year = int(year)
                meta.doc_type = doc_type
                meta.tags = [t.strip() for t in tags_str.split(",") if t.strip()]
                meta.status = "ready"  # Mark as ready now
                save_metadata(meta)
                st.success(f"Metadata saved for {meta.title}")
                st.rerun()  # Refresh UI after save
