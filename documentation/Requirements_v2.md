# Semantic Search RAG-based LLM — Planned Features for v2

## 1. Database & Ingestion Upgrades
- **Scanned PDFs Support**:  
  - Integrate OCR (e.g., Tesseract or PaddleOCR) for scanned documents.  
  - Enable hybrid text + image parsing for embedded charts/captions.  

- **Incremental Re-ingestion**:  
  - Detect file changes automatically with periodic directory polling (configurable).  
  - Update affected chunks without full reindexing.  

- **Advanced Metadata Extraction**:  
  - Extract full bibliographic metadata (title, authors, year, abstract).  
  - Auto-detect section/chapter boundaries for multi-granularity indexing.  

- **Duplicate Handling**:  
  - Content-based similarity to detect near-duplicate documents, not only exact file hash matches.  

---

## 2. Vector DB & Embeddings Enhancements
- **Switch to Qdrant** (or equivalent) with:  
  - Payload filtering for metadata fields (year, author, section).  
  - Disk-based indexing for larger corpora.  
  - Snapshot backups & easy migrations.

- **Multi-vector Representations**:  
  - Support for late-interaction models (e.g., BGE-M3, ColBERT) for higher recall in complex queries.  

- **Embedding Quality**:  
  - Experiment with OpenAI `text-embedding-3-large` or Cohere embeddings for long-text retrieval quality.  
  - Option to switch between local and API-based embeddings in settings.

---

## 3. Chunking & Indexing Improvements
- **Multi-granularity Index**:  
  - Store section-level summaries alongside passages for two-stage retrieval (summary → passages).  
  - Automatic abstractive summaries generated via LLM for broad questions.  

- **Dynamic Chunk Sizing**:  
  - Adaptive chunk length based on document structure (shorter for equations, longer for narrative text).  

- **Layout Preservation**:  
  - Preserve table boundaries and figure captions for better reference context.  

---

## 4. Retrieval & Ranking Upgrades
- **Query Expansion**:  
  - Enable Multi-Query and HyDE by default with configurable triggers.  
  - Add term expansion using domain-specific glossaries for acronyms and formulas.  

- **Advanced Fusion**:  
  - Context-aware weighting between BM25 and dense retrievers based on query type.  

- **Reranking Enhancements**:  
  - Multi-stage reranking (cross-encoder → LLM-based validation).  
  - Confidence calibration scores exposed to the UI.

- **Diversity Controls**:  
  - User-adjustable MMR λ parameter for diversity vs relevance trade-offs.

---

## 5. Generation & Grounding Enhancements
- **Answer Structuring**:  
  - Configurable output formats (bullets, structured tables, JSON exports).  
  - Inline citations with clickable references to exact PDF page highlights.  

- **Abstention Logic**:  
  - Confidence-based thresholds adjustable in UI.  
  - Return alternative suggestions when confidence low (e.g., “Try related terms”).  

- **Multiple LLM Options**:  
  - Switch between GPT-4.1, Claude, or local open-source LLMs with unified interface.  

- **Summarization Mode**:  
  - Allow user to request corpus-wide or document-level summaries with citations.

---

## 6. Few-shot & Conversational Memory
- **User-Defined Exemplars**:  
  - UI for uploading domain-specific Q/A pairs to fine-tune few-shot prompts.  

- **Long-Term Memory**:  
  - Persist conversational embeddings across sessions for personalized retrieval.  

- **Thread Search**:  
  - Searchable past conversations to retrieve relevant discussion history.

---

## 7. UI (Streamlit) Enhancements
- **Interactive PDF Viewer**:  
  - Highlight exact citation spans in embedded PDF viewer.  
  - Scroll directly to cited page/section on click.  

- **Advanced Controls**:  
  - Top-K sliders, reranker toggles, query expansion settings, latency vs cost modes.  

- **Multi-language Support**:  
  - English/UKR toggle for interface and prompts.  

- **Analytics Panel**:  
  - Query latency, token usage, API cost breakdown, retrieval precision metrics.

---

## 8. Evaluation & Quality Framework
- **Gold Test Set**:  
  - Curate Q/A pairs with known ground truth citations for regression testing.  

- **Metrics Dashboard**:  
  - Faithfulness, citation accuracy, retrieval precision@K, latency distribution.  

- **A/B Testing**:  
  - Compare hybrid retrieval configs, rerankers, and query expansion strategies.

---

## 9. Ops & Packaging Upgrades
- **Docker Support**:  
  - Optional containerized deployment for easy environment setup.  

- **Configurable Storage**:  
  - UI settings for index/cache/log directories, backup paths.  

- **Automated Backups**:  
  - Scheduled snapshots for vector DB and metadata.  

- **Monitoring Hooks**:  
  - Local Prometheus/Grafana endpoints for latency and error metrics.

---

## 10. Roadmap Candidates Beyond v2
- **Active Learning Loop**:  
  - User feedback on answer quality to fine-tune retrieval/reranking.  

- **Domain Adaptation**:  
  - Fine-tuning embeddings on economics/finance corpus for better relevance.  

- **RAG + Agents**:  
  - Task planning agents for multi-hop reasoning across documents.  

- **Multi-Modal Inputs**:  
  - Extract text from images/diagrams for richer answers.

---

## 11. Minimal Acceptance Criteria for v2
- OCR-enabled ingestion for scanned PDFs.  
- Multi-granularity retrieval with section summaries.  
- Clickable citations highlighting exact spans in PDFs.  
- Configurable query expansion & reranking parameters.  
- Basic analytics dashboard for latency/cost/precision.  
- Gold test set with automated evaluation pipeline.
