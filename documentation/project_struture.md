rag_project/
│
├── data/                     # Local PDFs and vector DB files
│   ├── pdfs/                  # Raw PDF documents (user uploaded)
│   ├── indexes/               # Chroma DB and BM25 indexes
│   ├── logs/                  # QA/debug logs (rotated daily)
│   └── sessions/              # Saved chat histories
│
├── src/
│   ├── ingestion/             # PDF parsing & indexing pipeline
│   │   ├── __init__.py
│   │   ├── pdf_parser.py       # pymupdf text extraction
│   │   ├── formula_parser.py   # LaTeX reconstruction
│   │   ├── chunking.py         # Layout-aware chunking logic
│   │   ├── metadata.py         # Metadata extraction (title, sections, pages)
│   │   └── indexing.py         # Embeddings + BM25 + Chroma ingestion
│   │
│   ├── retrieval/              # Search & ranking pipeline
│   │   ├── __init__.py
│   │   ├── hybrid_retrieval.py  # Dense + BM25 retrieval logic
│   │   ├── fusion.py            # RRF fusion of candidates
│   │   ├── reranker.py          # Cross-encoder reranking + MMR
│   │   └── query_expansion.py   # Multi-Query + HyDE (off by default)
│   │
│   ├── generation/             # Answer generation
│   │   ├── __init__.py
│   │   ├── context_packing.py   # Adaptive context window packing
│   │   ├── openai_api.py        # GPT-4.1 API calls
│   │   └── formatting.py        # Citations & abstention policy
│   │
│   ├── ui/                     # Streamlit UI
│   │   ├── __init__.py
│   │   ├── app.py               # Main Streamlit app
│   │   ├── components.py        # File uploader, search debugger, answer view
│   │   └── state.py             # Session storage & chat history
│   │
│   ├── utils/                   # Shared utilities
│   │   ├── __init__.py
│   │   ├── config.py            # Load .env, constants, paths
│   │   ├── logging_utils.py     # Rotating logs, ingestion errors
│   │   ├── evaluation.py        # Groundedness metrics (future)
│   │   └── helpers.py           # Token counting, deduplication
│   │
│   └── main.py                  # Entry point to launch Streamlit UI
│
├── tests/                       # Minimal test scripts for ingestion/retrieval
│   ├── test_ingestion.py
│   ├── test_retrieval.py
│   ├── test_generation.py
│   └── test_ui.py
│
├── .env                         # API keys & local settings (git-ignored)
├── requirements.txt             # Python dependencies
├── README.md                     # Project overview & setup instructions
└── config.yaml                   # Default settings (chunk sizes, top-K, thresholds)