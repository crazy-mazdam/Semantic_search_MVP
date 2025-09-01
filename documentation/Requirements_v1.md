# Semantic Search RAG-based LLM — Final Requirements (v1)

## 1. Database Setup
- **Source**: Local folder with PDFs; supports manual **Reindex** button to reprocess changed or new files.
- **Corpus Size**: ~100 documents, up to 300 pages each.
- **Content**: English-language PDFs with formulas, tables, charts (text only for v1).
- **Formulas**: Best-effort LaTeX reconstruction for non-scanned PDFs; scanned PDFs OCR deferred to future versions.
- **Metadata**: Store title, authors, year, section headers, page numbers for retrieval accuracy.
- **Duplicate Detection**: File hash (MD5) + metadata to avoid double indexing of identical content.
- **Corrupt PDFs**: Skipped with error logs available in Ingestion Status.
- **Storage**: SSD; no backups required in v1.

## 2. Vector Database & Embeddings
- **Vector DB**: Start with **Chroma** (local, free). Abstraction layer for future migration to **Qdrant** if needed.
- **Embeddings Model**: **BGE-Large-EN v1.5** (1024-d), GPU-accelerated (NVIDIA 3070, 8GB).
- **Representation**: Single-vector per chunk; optional future upgrade to multi-vector retrieval.
- **Re-ranking**: **bge-reranker-large** (local cross-encoder) for top-K.
- **Quality Focus**: float32 precision; no compression in v1.

## 3. Chunking & Indexing
- **Chunking**: Layout-aware (headings, sections), longer chunks (~900–1200 tokens, 150–200 overlap).
- **Tokenizer**: OpenAI `tiktoken` for chunk sizing and context packing.
- **Metadata**: Store doc_id, section, page_start, page_end, char offsets.
- **Multi-granularity Summaries**: Disabled for v1; planned for future upgrade.

## 4. Retrieval & Ranking
- **Hybrid Retrieval**:  
  - Dense: BGE-Large embeddings.  
  - BM25: lightweight local (e.g., rank_bm25 or Whoosh).  
- **Fusion**: Reciprocal Rank Fusion (RRF).  
- **Re-ranking**: Cross-encoder + **MMR diversity (λ = 0.7)** for final ranking.  
- **Query Expansion**: Multi-Query (MQ) and HyDE off by default; auto-enabled if recall < threshold.  
- **Defaults**: Fixed top-K values, no user tuning in v1.

## 5. Generation & Grounding
- **LLM**: OpenAI **GPT-4.1** via API; credentials stored in `.env`.
- **Context Packing**: Adaptive packing to fit top-ranked chunks within model limits.
- **Context/Answer Length**: Relaxed limits; longer answers allowed (e.g., up to ~12k context, ~2k output tokens).
- **Citations**: Format `[Title (Year), p. 123, "quoted text"]`; store char offsets for precise references.
- **Direct Quotes**: Include when available; prefer “Not found in corpus” over hallucinations.
- **Abstention Policy**: Trigger if <3 candidates score above 0.5 after re-rank or LLM self-confidence < 0.4.

## 6. Few-shot & Chat History
- **Few-shot**: Generic starter set (8 exemplars) included for econ/finance Q&A patterns.
- **Chat Memory**: Conversational retrieval with token-budgeted packing (adjustable).
- **Persistence**: Sessions saved locally (queries, retrieval sets, citations, settings).

## 7. UI (Streamlit)
- **Components**:  
  - File uploader  
  - Ingestion status (parse progress, chunk counts, errors)  
  - Search debugger (retrieved chunks, scores)  
  - Answer view (with citations + text)  
- **Citation UX**: Show cited text & file link only; no clickable deep links in v1.
- **Expert Controls**: Fixed defaults; no advanced tuning in v1.
- **Language**: English-only for v1.
- **File Paths**: Local filesystem paths displayed with "Open folder" option.

## 8. Evaluation & Quality
- **Metrics**: Focus on groundedness/faithfulness; latency/cost tuning deferred.
- **Gold Set**: Skipped for v1; planned for future QA.
- **API Budget**: Default caps — GPT-4.1, relaxed limits for longer contexts; $50/month, $5/session soft caps.

## 9. Ops & Packaging
- **Runtime**: Windows, NVIDIA 3070 (8GB), 16GB RAM (expandable), SSD.
- **Packaging**: Python venv; no Docker in v1.
- **Persistence**: Indexes/logs on SSD; Git for code; backup policy deferred.
- **Logging**: Local logs for QA/debug with daily rotation (14-day retention).

## 10. Additional Implementation Details
- **PDF Extraction Engine**: `pymupdf` for fast, layout-aware text extraction.
- **Directory Monitoring**: Manual “Reindex” button only; no automatic polling in v1.
- **GPU Utilization**: Used for embeddings + reranker; batch size auto-tuned for 8GB VRAM.
- **Citation Snippet Length**: 1–3 quotes, each ≤200 chars.
- **Versioning**: Store embeddings model name/version + corpus hash for reproducibility.
- **Security**: API keys in `.env` only; excluded from logs/configs.

## 11. Roadmap Preferences
- **v1 Minimum**: Ingest → Retrieve (Hybrid + RRF + MMR) → Re-rank → Generate Answer → Streamlit UI with citations.
- **Future Upgrades**: Multi-granularity summaries, OCR for scanned PDFs, abstractive query expansion, expert controls, latency optimization, gold test set, backups.

## 12. Acceptance Test for v1
- 5 sample queries (definition, equation lookup, policy summary, cross-doc compare, fact check) must return:
  - Grounded answers
  - Accurate citations with page + quoted text
  - Abstention if evidence insufficient
