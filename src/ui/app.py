# src/ui/app.py
from __future__ import annotations
import os
from pathlib import Path
import streamlit as st
from dotenv import load_dotenv  

# --- App identity ---
APP_NAME = "Semantic Search RAG — MVP"
APP_VERSION = "v1"

# --- Load .env before anything else ---
APP_ROOT = Path(__file__).resolve().parents[2]  # project root
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
    st.sidebar.caption("These are fixed defaults for V1-050; we’ll wire them in V1-051/053.")
    s = st.session_state[SS["settings"]]

    s["model"] = st.sidebar.selectbox("Model", ["gpt-4.1"], index=0, help="Configured in .env; using GPT-4.1 for MVP.")
    s["top_k"] = st.sidebar.slider("Top-K chunks", min_value=3, max_value=12, value=s.get("top_k", 5), step=1)
    s["max_context_chars"] = st.sidebar.slider("Context budget (chars)", min_value=3000, max_value=15000, value=s.get("max_context_chars", 9000), step=500)
    st.sidebar.caption("Language: English only in v1.")
    st.sidebar.divider()
    st.sidebar.markdown("**Corpus**")
    stats = st.session_state[SS["corpus_stats"]]
    st.sidebar.text(f"Docs:   {stats.get('docs', 0)}")
    st.sidebar.text(f"Chunks: {stats.get('chunks', 0)}")
    st.sidebar.divider()
    st.sidebar.markdown("[Open logs folder](file:///" + str((APP_ROOT / "data" / "logs").as_posix()) + ")")

def _header():
    st.markdown(f"### {APP_NAME} — {APP_VERSION}")
    st.caption("Minimal UI skeleton (V1-050). Upload & Ask flows will be wired in V1-051 and V1-053.")

def _tab_upload():
    st.subheader("Upload & Ingestion (placeholder)")
    st.info("This tab will host file upload, ingestion progress, and indexing status in **V1-051**.")
    # Placeholders we’ll wire next:
    st.file_uploader("Upload PDFs", type=["pdf"], accept_multiple_files=True, disabled=True)
    st.progress(0, text="Waiting to start…")
    st.caption("Status stream will appear here during ingestion (parse → clean → chunk → index).")
    # Last ingested list (from state)
    last = st.session_state[SS["last_ingested"]]
    if last:
        st.write("Recently ingested document IDs:")
        st.code("\n".join(last), language="text")

def _tab_ask():
    st.subheader("Ask (placeholder)")
    st.info("This tab will provide query input, retrieval debug, and grounded answers in **V1-053**.")
    st.text_input("Your question", placeholder="e.g., How does population aging affect savings?", disabled=True)
    st.button("Search", disabled=True)
    # Placeholder for answer & citations
    st.markdown("##### Answer")
    st.write("—")
    st.markdown("##### Citations")
    st.write("—")

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

    tabs = st.tabs(["Upload", "Ask", "Debug"])
    with tabs[0]:
        _tab_upload()
    with tabs[1]:
        _tab_ask()
    with tabs[2]:
        st.subheader("Debug")
        st.json(st.session_state[SS["debug"]])

    _footer()

if __name__ == "__main__":
    main()
