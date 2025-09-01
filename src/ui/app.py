# src/ui/app.py
from __future__ import annotations
import sys
sys.path.append('F:\Semantic_search_MVP\src')

import os
from pathlib import Path
import streamlit as st
from utils.paths import project_root  # if you have it; else compute below

from ingestion.pipeline import ingest_one_pdf, reindex_all_pdfs
from ingestion.utils import save_and_fingerprint

from indexing.chroma_db import collection_count, corpus_stats
from indexing.chroma_inspect import list_all_docs

from retrieval.dense import retrieve

from generation.answerer import answer_with_citations

from ui.tabs.upload_tab import show_metadata_form

from datetime import datetime, timezone
from metadata.io import load_metadata, save_metadata
from metadata.schema import DocumentMetadata

from dotenv import load_dotenv 

# TO RUN IN TERMINAL: streamlit run src/ui/app.py

# --- App identity ---
APP_NAME = "Semantic Search RAG — MVP"
APP_VERSION = "v1"
APP_ROOT = project_root()  # project root

# Session state keys
PENDING_UPLOAD_IDS = "pending_upload_ids"

# --- Load .env before anything else ---
load_dotenv(APP_ROOT / ".env")  # look for .env in project root

# --- Session state keys (centralized to avoid typos) ---
SS = {
    "env_ok": "env_ok",
    "corpus_stats": "corpus_stats",
    "last_ingested": "last_ingested",     # list[str md5]
    "chat_history": "chat_history",       # list[dict{role,content}]
    "settings": "settings",               # dict for UI settings
    "answer": "answer",                   # latest answer object
    "debug": "debug",                     # dict for debug payloads
}

DEFAULT_SETTINGS = {
    "model": "gpt-4.1",
    "top_k": 5,
    "max_context_chars": 9000,
    "language": "English",
}

def _ensure_session_defaults():
    for k, v in [
        (SS["env_ok"], False),
        (SS["corpus_stats"], {"docs": 0, "chunks": 0}),
        (SS["last_ingested"], []),
        (SS["chat_history"], []),
        (SS["settings"], DEFAULT_SETTINGS.copy()),
        (SS["answer"], None),
        (SS["debug"], {}),
        (PENDING_UPLOAD_IDS, []),  # <-- add this
    ]:
        if k not in st.session_state:
            st.session_state[k] = v

def _env_check() -> tuple[bool, list[str]]:
    problems = []
    if not os.getenv("OPENAI_API_KEY"):
        problems.append("OPENAI_API_KEY is missing (.env not loaded).")
    # Chroma persisted dir (same path used in code)
    chroma_dir = APP_ROOT / "data" / "indexes" / "chroma"
    chroma_dir.mkdir(parents=True, exist_ok=True)
    # Logs
    logs_dir = APP_ROOT / "data" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    ok = len(problems) == 0
    return ok, problems

def _sidebar():
    st.sidebar.title("Settings")
    st.sidebar.caption("These are fixed defaults for V1-050; will be adjustable later.")

    s = st.session_state[SS["settings"]]

    # Always refresh corpus stats on load
    st.session_state[SS["corpus_stats"]] = corpus_stats()

    st.sidebar.selectbox("Model", ["gpt-4.1"], index=0, key="model")
    st.sidebar.slider("Top-K chunks", min_value=3, max_value=12,
                      value=s.get("top_k", 5), step=1, key="top_k")
    st.sidebar.slider("Context budget (chars)", min_value=3000, max_value=15000,
                      value=s.get("max_context_chars", 9000), step=500, key="max_context_chars")

    st.sidebar.caption("Language: English only in v1.")
    st.sidebar.divider()
    st.sidebar.markdown("**Corpus**")

    stats = st.session_state[SS["corpus_stats"]]
    st.sidebar.text(f"Docs:   {stats['docs']}")
    st.sidebar.text(f"Chunks: {stats['chunks']}")
    st.sidebar.divider()
    st.sidebar.markdown("[Open logs folder](file:///" + str((APP_ROOT / 'data' / 'logs').as_posix()) + ")")

def _header():
    st.markdown(f"### {APP_NAME} — {APP_VERSION}")
    st.caption("Minimal UI skeleton (V1-050).")

def _tab_upload():
    st.subheader("Upload & Ingestion")
    st.caption("Drop one or more PDFs; first save & fill metadata, then ingest ready docs.")

    st.caption(
        "Reindex will **wipe existing Chroma data** and rebuild index from all PDFs in `data/pdfs`. "
        "Old chunks for removed or changed PDFs are deleted, and only current PDFs are indexed fresh."
    )

    # --- Existing metadata editor (shows any draft docs found on disk) ---
    # This will render forms for metadata with status='draft' or missing title.
    # (Keeps your current modularity)
    show_metadata_form()

    # --- Reindex (keep your original behavior) ---
    if st.button("Reindex all PDFs", use_container_width=True):
        status_box = st.empty()
        prog = st.progress(0, text="Starting reindex.")

        def on_status(msg: str): status_box.write(msg)
        def on_progress(pct: float, msg: str): prog.progress(int(pct), text=msg)

        with st.spinner("Reindexing PDFs."):
            stats = reindex_all_pdfs(on_status=on_status, on_progress=on_progress)

        st.session_state[SS["corpus_stats"]] = stats
        st.success(f"Reindex complete: {stats['docs']} docs, {stats['chunks']} chunks")
        prog.empty()

    # --- Upload zone ---
    app_root = APP_ROOT
    pdf_dir = app_root / "data" / "pdfs"
    pdf_dir.mkdir(parents=True, exist_ok=True)

    uploaded = st.file_uploader("Upload PDFs", type=["pdf"], accept_multiple_files=True)

    col_pre, col_ing = st.columns([1, 1])
    with col_pre:
        prep = st.button("Save uploads & open metadata forms", use_container_width=True)
    with col_ing:
        run_ingest = st.button("Ingest Ready (from uploads)", type="primary", use_container_width=True)

    # Step 1: Save uploads + create/load draft metadata (no indexing)
    if prep:
        if not uploaded:
            st.info("Select one or more PDF files to begin.")
            st.stop()

        pending_ids = set(st.session_state.get(PENDING_UPLOAD_IDS, []))
        created = 0
        updated = 0

        for uf in uploaded:
            # Save + fingerprint using your helper (writes file and returns doc_id)
            pdf_path, doc_id, title_guess = save_and_fingerprint(uf, pdf_dir)

            meta = load_metadata(doc_id)
            if not meta:
                # Create draft metadata; user will confirm in the form rendered by show_metadata_form()
                meta = DocumentMetadata(
                    status="draft",
                    doc_id=doc_id,
                    title=None,
                    title_guess=title_guess,
                    authors=[],
                    year=None,
                    doc_type="other",
                    tags=[],
                    ingested_at=datetime.now(timezone.utc),
                    source_path=str(pdf_path),
                )
                save_metadata(meta)
                created += 1
            else:
                # Make sure source_path points to current file location (idempotent)
                if not meta.source_path:
                    meta.source_path = str(pdf_path)
                    save_metadata(meta)
                    updated += 1
            
            pending_ids.add(doc_id)

        st.session_state[PENDING_UPLOAD_IDS] = list(pending_ids)
        st.success(f"Prepared {created} new and {updated} updated metadata file(s). Fill the forms above, then click “Ingest Ready”.")
        st.rerun()

    # Step 2: Ingest only docs from this upload set that are metadata-ready
    if run_ingest:
        pending_ids = list(st.session_state.get(PENDING_UPLOAD_IDS, []))
        if not pending_ids:
            st.warning("Nothing to ingest yet. First click “Save uploads & open metadata forms”, then fill the forms and save.")
            st.stop()

        status_area = st.container()
        prog = st.progress(0, text="Starting ingestion…")

        def on_status(msg: str):
            status_area.write(msg)

        def on_chunk_progress(pct: float, msg: str):
            prog.progress(int(pct), text=msg)

        last_ids = []
        ready_ids, skipped = [], []

        for doc_id in pending_ids:
            meta = load_metadata(doc_id)
            if not meta or meta.status != "ready" or not meta.source_path:
                skipped.append(doc_id)
                continue
            ready_ids.append(doc_id)

        total = len(ready_ids)
        for i, doc_id in enumerate(ready_ids, start=1):
            meta = load_metadata(doc_id)
            pdf_path = Path(meta.source_path)
            prog.progress(int((i - 1) * 100 / max(1, total)), text=f"Ingesting {i}/{total}…")
            st.write(f"**[{i}/{total}]** Ingesting: `{pdf_path.name}`")
            try:
                out_id = ingest_one_pdf(
                    pdf_path,
                    reindex=False,
                    on_status=on_status,
                    on_chunk_progress=on_chunk_progress,
                )
                st.success(f"Done: md5={out_id}")
                last_ids.append(out_id)
            except Exception as e:
                st.error(f"Failed: {e}")

        prog.progress(100, text=f"Completed {len(ready_ids)}/{total}")

        # Refresh stats in sidebar after ingest
        if last_ids:
            st.session_state[SS["corpus_stats"]] = corpus_stats()
            prev = st.session_state.get(SS["last_ingested"], [])
            st.session_state[SS["last_ingested"]] = last_ids + prev

            # Also try to refresh chunks count (kept from your original flow)
            try:
                cnt = collection_count()
                st.session_state[SS["corpus_stats"]]["chunks"] = cnt
            except Exception:
                pass

            st.markdown("**Recently ingested document IDs (md5):**")
            st.code("\n".join(last_ids), language="text")

        if skipped:
            st.info(f"Skipped {len(skipped)} doc(s) with draft/missing metadata. Fill forms above and save, then ingest again.")

        # Clear pending set after a run (only the ones we just processed)
        st.session_state[PENDING_UPLOAD_IDS] = []

def _tab_ask():
    st.subheader("Ask")
    st.caption("Ask runs a semantic search on your indexed PDFs, retrieves the most relevant chunks from ChromaDB, "
               "and sends them to GPT-4.1 via OpenAI API to generate an answer with citations from the source documents.")
    
    if collection_count() == 0:
        st.info("Index is empty. Upload PDFs first on the **Upload** tab.")
        return

    # ---- session state keys for Ask tab ----
    if "ask_last_q" not in st.session_state: st.session_state["ask_last_q"] = ""
    if "ask_last_ans" not in st.session_state: st.session_state["ask_last_ans"] = None
    if "ask_last_hits" not in st.session_state: st.session_state["ask_last_hits"] = []
    if "ask_show_chunks" not in st.session_state: st.session_state["ask_show_chunks"] = False

    # ---- form: prevents reruns until "Search" is clicked ----
    with st.form("ask_form", clear_on_submit=False):
        question = st.text_area(
            "Your question",
            value=st.session_state["ask_last_q"],
            placeholder="e.g., How does population aging affect savings and current accounts?",
            height=140,
        )
        submitted = st.form_submit_button("Search", use_container_width=True)

    # Run retrieval + LLM only when submitted
    if submitted and question.strip():
        st.session_state["ask_last_q"] = question
        with st.spinner("Retrieving and generating..."):
            top_k = st.session_state[SS["settings"]]["top_k"]
            # Retrieve for debug view and to keep consistent with answer context
            hits = retrieve(question, top_k=top_k)
            ans = answer_with_citations(question, top_k=top_k, model=st.session_state[SS["settings"]]["model"])
        # persist results so future reruns (e.g., toggling UI) don’t lose them
        st.session_state["ask_last_hits"] = hits
        st.session_state["ask_last_ans"] = ans
        st.session_state["ask_show_chunks"] = False  # reset view on new search

    ans = st.session_state["ask_last_ans"]
    hits = st.session_state["ask_last_hits"]

    st.markdown("---")
    st.markdown("### Answer")
    if ans is None:
        st.info("Enter a question and click **Search**.")
    else:
        if ans.answer.strip() == "Not found in corpus.":
            st.warning("Not found in corpus.")
        else:
            st.write(ans.answer)

        st.markdown("### Citations")
        if ans.citations:
            for i, c in enumerate(ans.citations, 1):
                st.markdown(f"**[{i}] {c.title} — pages {c.pages}**")
                st.caption(c.excerpt)
        else:
            st.info("No citations returned.")

    # Toggle button instead of checkbox (persists answer, no extra compute)
    if hits:
        st.markdown("---")
        colA, colB = st.columns([1, 5])
        if colA.button(
            "Show retrieved chunks" if not st.session_state["ask_show_chunks"] else "Hide retrieved chunks",
            use_container_width=True
        ):
            st.session_state["ask_show_chunks"] = not st.session_state["ask_show_chunks"]

        if st.session_state["ask_show_chunks"]:
            expand_all = colB.checkbox("Expand all", value=False)
            st.markdown("### Retrieved Chunks (Debug)")
            for i, h in enumerate(hits, 1):
                title = h.metadata.get("title", "") or h.metadata.get("doc_id", "")
                pages = h.metadata.get("pages_covered", "")
                st.markdown(f"**[{i}] {title} — pages {pages}**")
                preview = h.text[:240].replace("\n", " ")
                st.text(preview + ("…" if len(h.text) > 240 else ""))
                with st.expander("Show full text", expanded=expand_all):
                    st.text(h.text)
                st.caption(f"distance = {h.distance:.3f}")
                st.divider()

def _tab_chroma():
    st.subheader("Chroma DB Inspector")

    # Option to filter for a single document
    filter_doc = st.text_input("Filter by doc_id (optional)")

    # Fetch docs with metadata
    docs = list_all_docs(limit_per_doc=3, filter_doc=filter_doc if filter_doc else None)

    if not docs:
        st.info("No documents found in Chroma DB.")
        return

    for doc in docs:
        with st.expander(f"Document: {doc['title']} (Chunks: {doc['chunk_count']})", expanded=False):
            # Document-level metadata
            st.markdown(f"**Doc ID:** {doc['doc_id']}")
            st.markdown(f"**Title:** {doc.get('title', '')}")
            st.markdown(f"**Authors:** {', '.join(doc.get('authors', [])) if doc.get('authors') else 'N/A'}")
            st.markdown(f"**Year:** {doc.get('year', 'N/A')}")
            st.markdown(f"**Type:** {doc.get('doc_type', 'N/A')}")
            st.markdown(f"**Tags:** {', '.join(doc.get('tags', [])) if doc.get('tags') else 'N/A'}")
            st.markdown(f"**Source Path:** {doc.get('source_path', 'N/A')}")

            st.markdown("---")
            st.markdown("### Chunks Preview")

            # Chunk-level metadata & preview
            for ch in doc["chunks"]:
                with st.expander(f"Chunk {ch['id']} (Pages: {ch['pages']})"):
                    st.markdown(f"**Preview:** {ch['preview']}")
                    st.markdown("**Full Text:**")
                    st.text(ch['full_text'])

                    # Show full per-chunk metadata
                    st.markdown("**Chunk Metadata:**")
                    for k, v in ch.get("chunk_meta", {}).items():
                        st.markdown(f"- **{k}:** {v}")

def _footer():
    st.divider()
    st.caption("© 2025 — RAG MVP. This is an internal prototype UI for testing end-to-end flow.")

def main():
    st.set_page_config(page_title="Semantic Search RAG — MVP", layout="wide", page_icon="🔎")
    _ensure_session_defaults()
    ok, problems = _env_check()
    st.session_state[SS["env_ok"]] = ok

    _header()
    _sidebar()

    if not ok:
        st.error("Environment check failed:")
        for p in problems:
            st.write(f"- {p}")
        st.stop()

    tabs = st.tabs(["Ask", "Upload", "Chroma Inspector"])  # , "Debug"

    with tabs[0]:
        _tab_ask()

    with tabs[1]:
        _tab_upload()

    with tabs[2]:
        _tab_chroma()

    # with tabs[3]:
    #     st.subheader("Debug")
    #     st.json(st.session_state[SS["debug"]])

    _footer()

if __name__ == "__main__":
    main()
