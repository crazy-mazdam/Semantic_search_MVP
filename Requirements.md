# Semantic Search RAG-based LLM — Updated Requirements

## 1. Database Setup
- **Source**: Local folder with PDFs; supports incremental re-indexing when files change.
- **Corpus Size**: ~100 documents, up to 300 pages each.
- **Content**: English-language PDFs with formulas, tables, charts (text only for v1).
- **Formulas**: Reconstruct into LaTeX for indexing/searching.
- **Metadata**: Store title, authors, year, section headers, page numbers for retrieval accuracy.
- **Scanned PDFs**: Skipped for v1; OCR planned for future versions.
- **Storage**: SSD; no backups required in v1.

## 2. Vector Database & Embeddings
- **Vector DB**: Start with **Chroma** (local, free). Abstraction layer to allow future migration to **Qdrant** if needed.
- **Embeddings Model**: **BGE-Large-EN v1.5** (1024-d), GPU-accelerated (NVIDIA 3070, 8GB).
- **Representation**: Single-vector per chunk; optional future upgrade to multi-vector retrieval.
- **Re-ranking**: **bge-reranker-large** (local cross-encoder) for top-K.
- **Quality Focus**: float32 precision; no compression for v1.

## 3. Chunking & Indexing
- **Chunking**: Layout-aware (headings, sections), longer chunks (~900–1200 tokens, 150–200 overlap).
- **Metadata**: Store doc_id, section, page_start, page_end, char offsets.
- **Multi-granularity Summaries**: Disabled for v1; planned as future upgrade.

## 4. Retrieval & Ranking
- **Hybrid Retrieval**:  
  - Dense: BGE-Large embeddings.  
  - BM25: keyword retrieval for rare terms, acronyms, formulas.  
- **Fusion**: Reciprocal Rank Fusion (RRF).  
- **Re-ranking**: Cross-encoder + **MMR diversity (λ = 0.7)** for final ranking.  
- **Query Expansion**: Multi-Query (MQ) and HyDE off by default; auto-enabled if recall < threshold.  
- **Defaults**: Fixed top-K values, no user tuning in v1.

## 5. Generation & Grounding
- **LLM**: OpenAI API (e.g., GPT-4o-mini); local RAG, external generation.  
- **Context Packing**: Adaptive packing to fit top-ranked chunks within model limits.  
- **Citations**: Format `[Title (Year), p. 123, "quoted text"]`; store char offsets for precise references.  
- **Direct Quotes**: Include when available; prefer “Not found in corpus” over hallucinations.  
- **Abstention Policy**: Triggered if retrieved evidence insufficient or conflicting.

## 6. Few-shot & Chat History
- **Few-shot**: Generic starter set (8 exemplars) included for econ/finance Q&A patterns.  
- **Chat Memory**: Conversational retrieval with token-budgeted packing (adjustable).  
- **Persistence**: Sessions saved locally (queries, retrieval sets, citations, settings).

## 7. UI (Streamlit)
- **Components**:  
  - File uploader  
  - Ingestion status (parse progress, chunk counts)  
  - Search debugger (retrieved chunks, scores)  
  - Answer view (with citations + text)  
- **Citation UX**: Show cited text & file link; no clickable page highlights in v1.  
- **Expert Controls**: Fixed defaults (no advanced tuning in v1).  
- **Language**: English-only for v1.

## 8. Evaluation & Quality
- **Metrics**: Focus on groundedness/faithfulness; latency/cost tuning deferred.  
- **Gold Set**: Skipped for v1; planned for future QA.  
- **API Budget**: Default caps — GPT-4o-mini, ≤8k input / 1.5k output tokens per call; $50/month, $5/session soft caps.

## 9. Ops & Packaging
- **Runtime**: Windows, NVIDIA 3070 (8GB), 16GB RAM (expandable), SSD.  
- **Packaging**: Python venv; no Docker in v1.  
- **Persistence**: Indexes/logs on SSD; Git for code; backup policy deferred.  
- **Logging**: Local logs for QA/debug (queries, retrieved passages, timings).

## 10. Roadmap Preferences
- **v1 Minimum**: Ingest → Retrieve → Generate Answer → Streamlit UI with citations.  
- **Future Upgrades**: Multi-granularity summaries, OCR for scanned PDFs, abstractive query expansion, expert controls, latency optimization, advanced metrics.
