# src/ui/app.py
from __future__ import annotations
import sys
sys.path.append('F:\Semantic_search_MVP\src')

import os
from pathlib import Path
import streamlit as st
from utils.paths import project_root  # if you have it; else compute below

from ingestion.pipeline import ingest_one_pdf, reindex_all_pdfs

from indexing.chroma_db import collection_count, corpus_stats
from indexing.chroma_inspect import list_all_docs

from retrieval.dense import retrieve

from generation.answerer import answer_with_citations

from dotenv import load_dotenv 

# TO RUN IN TERMINAL: streamlit run src/ui/app.py

# --- App identity ---
APP_NAME = "Semantic Search RAG — MVP"
APP_VERSION = "v1"
APP_ROOT = project_root()  # project root

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
    st.caption("Drop one or more PDFs; we’ll parse → clean → chunk → index locally. Embeddings via OpenAI API.")

    st.caption("Reindex will **wipe existing Chroma data** and rebuild index from all PDFs in `data/pdfs`. "
           "Old chunks for removed or changed PDFs are deleted, and only current PDFs are indexed fresh.")


    # Reindex button at top
    if st.button("Reindex all PDFs", use_container_width=True):
        status_box = st.empty()
        prog = st.progress(0, text="Starting reindex...")

        def on_status(msg: str): status_box.write(msg)
        def on_progress(pct: float, msg: str): prog.progress(int(pct), text=msg)

        with st.spinner("Reindexing PDFs..."):
            stats = reindex_all_pdfs(on_status=on_status, on_progress=on_progress)

        # Refresh stats in sidebar after reindex
        st.session_state[SS["corpus_stats"]] = stats
        st.success(f"Reindex complete: {stats['docs']} docs, {stats['chunks']} chunks")
        prog.empty()


    # Where to save uploads
    app_root = APP_ROOT
    pdf_dir = app_root / "data" / "pdfs"
    pdf_dir.mkdir(parents=True, exist_ok=True)

    uploaded = st.file_uploader("Upload PDFs", type=["pdf"], accept_multiple_files=True)
    if not uploaded:
        st.info("Select one or more PDF files to begin.")
        return

    run = st.button("Start ingestion", type="primary", use_container_width=True)
    if not run:
        return

    # UI elements
    status_area = st.container()
    prog = st.progress(0, text="Waiting…")

    # Helpers to receive pipeline progress
    def on_status(msg: str):
        status_area.write(msg)

    def on_chunk_progress(pct: float, msg: str):
        prog.progress(int(pct), text=msg)

    last_ids = []        

    for i, uf in enumerate(uploaded, start=1):
        prog.progress(0, text=f"Saving file {i}/{len(uploaded)}…")
        # Persist uploaded file to disk
        out_path = pdf_dir / uf.name
        with open(out_path, "wb") as f:
            f.write(uf.getbuffer())

        st.write(f"**[{i}/{len(uploaded)}]** Ingesting: `{uf.name}`")
        try:
            doc_id = ingest_one_pdf(
                out_path,
                reindex=False,
                on_status=on_status,
                on_chunk_progress=on_chunk_progress,
            )
            st.success(f"Done: md5={doc_id}")
            last_ids.append(doc_id)
        except Exception as e:
            st.error(f"Failed: {e}")

        prog.progress(100, text=f"Completed {i}/{len(uploaded)}")

    # Update session state
    if last_ids:
        st.session_state[SS["corpus_stats"]] = corpus_stats()
        prev = st.session_state.get(SS["last_ingested"], [])
        st.session_state[SS["last_ingested"]] = last_ids + prev

    # Update sidebar stats (chunks only for now)
    try:
        cnt = collection_count()
        st.session_state[SS["corpus_stats"]]["chunks"] = cnt
    except Exception:
        pass

    st.divider()
    if last_ids:
        st.markdown("**Recently ingested document IDs (md5):**")
        st.code("\n".join(last_ids), language="text")



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
    st.subheader("Chroma Inspector")
    st.caption("View stored chunks with metadata. Filter by doc_id or expand chunks for full text.")

    # Input for filtering
    filter_doc = st.text_input("Filter by doc_id (leave empty for all docs):", "")

    try:
        docs = list_all_docs(limit_per_doc=3, filter_doc=filter_doc.strip() or None)
    except Exception as e:
        st.error(f"Failed to read Chroma: {e}")
        return

    if not docs:
        st.info("No documents found." if filter_doc else "No documents indexed yet.")
        return

    for d in docs:
        exp_label = f"{d['title'] or d['doc_id']} — {d['chunk_count']} chunks"
        with st.expander(exp_label, expanded=bool(filter_doc)):  # auto-expand if filtering
            st.code(f"doc_id: {d['doc_id']}")
            for i, ch in enumerate(d["chunks"], start=1):
                st.markdown(f"**Chunk {i} — Pages {ch['pages']}**")
                st.text(ch["preview"])  # always show preview
                with st.expander("Show full text"):
                    st.text(ch["full_text"])  # expandable full text
                st.divider()

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
