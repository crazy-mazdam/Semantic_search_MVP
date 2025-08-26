# RAG v1 — Step-by-Step Implementation Plan (Jira-style)

## EPIC 0 — Project Bootstrap & Foundations
**Goal:** Create a clean, configurable skeleton with logging and paths.

- **V1-001: Repo scaffold & paths** - **(DONE - ✅)**
  - *Desc:* Create `rag_project/` structure; add `data/{pdfs,indexes,logs,sessions}`, `src/` subpackages, `tests/`, `config.yaml`, `.env.example`.
  - *Deps:* —
  - *DoD:* Tree matches spec; `README.md` minimal; `.gitignore` excludes `.env`, `data/indexes`, logs.

- **V1-002: Config loader** - **(DONE - ✅)**
  - *Desc:* Centralize settings (paths, chunk sizes, K values, thresholds, model names) in `utils/config.py` reading `config.yaml` + env overrides.
  - *Deps:* V1-001
  - *DoD:* Single import provides typed config across modules.

- **V1-003: Logging & rotation** - **(DONE - ✅)**
  - *Desc:* JSON logger in `utils/logging_utils.py` with daily rotation (14-day retention) to `data/logs/`.
  - *Deps:* V1-001
  - *DoD:* Logs include correlation IDs, timings; verified file rotation.

---

## EPIC 1 — Ingestion Pipeline
**Goal:** Parse PDFs, reconstruct formulas (best-effort), chunk with layout, enrich metadata, and prepare for indexing.

- **V1-010: PDF text extraction**
  - *Desc:* Implement `pymupdf` extraction in `ingestion/pdf_parser.py`; capture page text + bbox spans.
  - *Deps:* 0
  - *DoD:* Unit test parses sample PDFs; corrupt files are detected.

- **V1-011: Metadata extraction**
  - *Desc:* In `ingestion/metadata.py`, extract title/author/year (when available), section/heading hints.
  - *Deps:* V1-010
  - *DoD:* Metadata attached to doc object; defaults when fields missing.

- **V1-012: Formula reconstruction (best-effort)**
  - *Desc:* Normalize Unicode math; wrap detected equations as LaTeX-like tokens for indexing.
  - *Deps:* V1-010
  - *DoD:* Equations appear as `$$ ... $$` or similar placeholders in extracted text.

- **V1-012a: Text Cleaning & Noise Removal**
  - *Desc:* Produce cleaned text for indexing/LLM while preserving raw anchors for citations. Remove headers, footers, page numbers, hyphenation, and boilerplate; mark footnotes for optional exclusion.
  - *Deps:* V1-010
  - *DoD:* Cleaned text improves retrieval quality; raw citations remain accurate; configurable thresholds for removal.

- **V1-013: Layout-aware chunking**
  - *Desc:* Implement `ingestion/chunking.py` (900–1200 tokens, 150–200 overlap) with section/page anchors.
  - *Deps:* V1-010, V1-011
  - *DoD:* Chunks carry `{doc_id, section, page_start/end, char_start/end, chunk_idx}`.

- **V1-014: Duplicate detection**
  - *Desc:* Compute md5; skip identical PDFs (even if renamed).
  - *Deps:* V1-010
  - *DoD:* Re-ingestion of duplicates results in no new chunks.

- **V1-015: Ingestion status & errors**
  - *Desc:* Status object with counts, timings, errors; emit to logs and UI.
  - *Deps:* V1-010..V1-014
  - *DoD:* UI can display per-doc status and error messages.

---

## EPIC 2 — Indexing Backends (Chroma + BM25)
**Goal:** Persist search indexes locally; GPU embeddings; simple BM25.

- **V1-020: Chroma initialization**
  - *Desc:* Create/attach persistent Chroma DB in `data/indexes/`; collection schema for chunks + metadata.
  - *Deps:* 1
  - *DoD:* Chroma can upsert/search; vectors persist across runs.

- **V1-021: Embeddings pipeline (GPU)**
  - *Desc:* `BGE-Large-EN v1.5` embeddings with batch auto-tune for 8GB VRAM.
  - *Deps:* V1-020
  - *DoD:* Throughput validated; OOM handled with smaller batches.

- **V1-022: BM25 index**
  - *Desc:* Build lightweight BM25 (`rank_bm25`/Whoosh) over chunk texts.
  - *Deps:* V1-013, V1-020
  - *DoD:* BM25 returns stable top-K for keyword queries.

- **V1-023: Corpus/version tracking**
  - *Desc:* Store corpus hash, embeddings model version per indexing run.
  - *Deps:* V1-020..V1-022
  - *DoD:* Version metadata saved and exposed for audits.

- **V1-024: Manual Reindex**
  - *Desc:* Recompute index for new/changed PDFs; skip duplicates; UI button triggers.
  - *Deps:* V1-014, V1-020..V1-022
  - *DoD:* Reindex updates only changed docs; status visible in UI.

---

## EPIC 3 — Retrieval & Ranking
**Goal:** Hybrid dense+BM25 retrieval, fused and re-ranked with MMR diversity.

- **V1-030: Dense retrieval**
  - *Desc:* Query embeddings; top-K₁ from Chroma with metadata.
  - *Deps:* V1-021, V1-020
  - *DoD:* Returns scored candidates with ids & page anchors.

- **V1-031: BM25 retrieval**
  - *Desc:* Top-K₂ lexical hits.
  - *Deps:* V1-022
  - *DoD:* Returns scored candidates; compatible schema with dense.

- **V1-032: RRF fusion**
  - *Desc:* Merge dense+BM25 via Reciprocal Rank Fusion; dedup by chunk id.
  - *Deps:* V1-030, V1-031
  - *DoD:* Stable ordering across runs; unit tests on toy data.

- **V1-033: Cross-encoder reranker**
  - *Desc:* `bge-reranker-large` GPU rerank top fused set to R.
  - *Deps:* V1-032
  - *DoD:* Reranked list improves relevance on sample queries.

- **V1-034: MMR diversity**
  - *Desc:* Apply MMR (λ=0.7) to final list to reduce redundancy across docs/sections.
  - *Deps:* V1-033
  - *DoD:* Selected set shows diversity by `doc_id`/`section`.

- **V1-035: Query expansion hooks (disabled by default)**
  - *Desc:* Add Multi-Query & HyDE plumbing with thresholds; keep off by default.
  - *Deps:* V1-032..V1-034
  - *DoD:* Feature flag present; off has zero effect; on works in dev mode.

- **V1-036: Thresholds & scoring schema**
  - *Desc:* Centralize top-K, R, N; confidence thresholds; abstention inputs.
  - *Deps:* V1-032..V1-034
  - *DoD:* All knobs read from `config.yaml`; UI does not expose them.

---

## EPIC 4 — Generation & Grounding
**Goal:** Adaptive context packing, GPT-4.1 generation, citations, abstention.

- **V1-040: OpenAI API integration**
  - *Desc:* `generation/openai_api.py` reads `OPENAI_API_KEY` from `.env`; model GPT-4.1.
  - *Deps:* 0
  - *DoD:* Healthy call with retry/backoff and rate-limit handling.

- **V1-041: Adaptive context packing**
  - *Desc:* Use `tiktoken` to pack top-N passages under relaxed token budget; no mid-chunk cuts.
  - *Deps:* V1-034
  - *DoD:* Packing respects limits; logs packed vs skipped.

- **V1-042: Citation assembly**
  - *Desc:* Construct `[(Title (Year), p. X, "quote")]`; ensure quote length ≤200 chars; include char offsets.
  - *Deps:* V1-013, V1-034
  - *DoD:* All citations map back to valid chunk offsets/pages.

- **V1-043: Abstention policy**
  - *Desc:* “Not found in corpus” if <3 candidates ≥0.5 after rerank or LLM self-confidence <0.4.
  - *Deps:* V1-036, V1-040
  - *DoD:* Deterministic abstention with clear user message + near-miss citations.

- **V1-044: Output schema & validation**
  - *Desc:* Enforce JSON schema `{answer, citations[], confidence}`; validate before UI render.
  - *Deps:* V1-042, V1-043
  - *DoD:* Invalid outputs rejected with logged error & user-safe fallback.

---

## EPIC 5 — Streamlit UI
**Goal:** Minimal, focused UI per requirements.

- **V1-050: App skeleton & state**
  - *Desc:* `ui/app.py` with sidebar nav; `ui/state.py` for session objects & token budget setting (config-only).
  - *Deps:* 0
  - *DoD:* App runs; placeholder panels visible.

- **V1-051: File uploader & ingestion status**
  - *Desc:* Upload to `data/pdfs/`; show parse/chunk/index counts; errors surfaced from logs.
  - *Deps:* 1, 2
  - *DoD:* User can upload and trigger ingestion; progress statuses appear.

- **V1-052: Search debugger**
  - *Desc:* Show dense/BM25 scores, fusion ranks, rerank scores, and selected top-N with MMR.
  - *Deps:* 3
  - *DoD:* Sorted tables render; expandable chunk previews.

- **V1-053: Ask/Answer view**
  - *Desc:* Input box; display grounded answer; list citations with file link + quoted text (no deep page links).
  - *Deps:* 4
  - *DoD:* Usable end-to-end Q→A with citations.

- **V1-054: Reindex button**
  - *Desc:* Manual reindex action; shows ingestion status updates.
  - *Deps:* V1-024
  - *DoD:* Reindex performs incremental update; UI confirmation visible.

- **V1-055: English-only labels & minimal styling**
  - *Desc:* Ensure consistent copy, spacing, and basic readability.
  - *Deps:* V1-050..V1-053
  - *DoD:* Visual QA passes; no i18n toggles.

---

## EPIC 6 — Sessions, Conversational Retrieval & Persistence
**Goal:** Token-budgeted chat with per-session retrieval, saved locally.

- **V1-060: Session store**
  - *Desc:* Save turns, settings, evidence IDs to `data/sessions/`.
  - *Deps:* 5
  - *DoD:* Sessions persist across restarts; resumable by ID.

- **V1-061: Conversational retrieval (per-session)**
  - *Desc:* Ephemeral Chroma collection for chat turns; retrieve relevant past snippets each query.
  - *Deps:* V1-060, V1-030
  - *DoD:* Older but relevant turns appear in evidence when helpful.

- **V1-062: Token budget enforcement**
  - *Desc:* Cap chat history tokens packed into generation input; adjustable via config.
  - *Deps:* V1-041, V1-060
  - *DoD:* Logs show truncation/compression decisions.

- **V1-063: Log correlation**
  - *Desc:* Tag logs with session & query IDs for traceability.
  - *Deps:* V1-003, V1-060
  - *DoD:* One-click trace from UI action to logs.

---

## EPIC 7 — Testing & QA
**Goal:** Minimum safety net; acceptance aligned with v1 gate.

- **V1-070: Unit tests (ingestion/retrieval/generation)**
  - *Desc:* Basic tests for parser, chunker, fusion, reranker, packing, citation assembly.
  - *Deps:* 1–4
  - *DoD:* Tests pass locally; CI placeholder (optional).

- **V1-071: E2E smoke test**
  - *Desc:* Script to ingest small corpus and answer one query end-to-end.
  - *Deps:* 1–5
  - *DoD:* Returns grounded answer with ≥1 correct citation.

- **V1-072: Acceptance test — 5 queries**
  - *Desc:* Definition, equation lookup, policy summary, cross-doc compare, fact check.
  - *Deps:* 1–6
  - *DoD:* Each returns grounded answers with accurate citations or abstains.

- **V1-073: Error handling tests**
  - *Desc:* Corrupt PDF, zero-hit query, API error, OOM batch fallback.
  - *Deps:* 1–5
  - *DoD:* Graceful UI messages; logs contain actionable diagnostics.

- **V1-074: Latency logging (informational)**
  - *Desc:* Measure retrieval, rerank, LLM time; no targets yet.
  - *Deps:* 3–5
  - *DoD:* Timings appear in logs and debugger panel.

---

## EPIC 8 — Documentation
**Goal:** Make it repeatable to run v1 locally.

- **V1-080: README — setup & run**
  - *Desc:* venv creation, deps install, `.env` keys, folder permissions, `streamlit run`.
  - *Deps:* 0–5
  - *DoD:* New dev can run app and ingest sample PDFs.

- **V1-081: Config reference**
  - *Desc:* Explain `config.yaml` fields (chunk sizes, K values, thresholds, paths).
  - *Deps:* V1-002
  - *DoD:* All knobs documented; defaults match code.

- **V1-082: Troubleshooting guide**
  - *Desc:* Common ingestion errors, GPU OOM, API issues, Windows path quirks.
  - *Deps:* 1–7
  - *DoD:* Links to relevant logs; mitigation steps listed.

---

## EPIC 9 — Release Prep
**Goal:** Create a clean, pinned, runnable v1.

- **V1-090: Dependency pinning**
  - *Desc:* `requirements.txt` pinned to known-good versions.
  - *Deps:* All dev work
  - *DoD:* Fresh venv installs without conflicts on Windows.

- **V1-091: Entry points**
  - *Desc:* `src/main.py` to start Streamlit; short run command in README.
  - *Deps:* 5
  - *DoD:* Single command launches UI.

- **V1-092: Versioning & tag**
  - *Desc:* Mark `v1.0.0`; record corpus hash, embeddings model version in release notes.
  - *Deps:* All
  - *DoD:* Tagged commit; changelog updated.

---

## Cross-Epic Conventions
- **Security:** API keys only in `.env`; never logged or committed.
- **Persistence:** Indexes & sessions under `data/` as per config; no backups in v1.
- **Citations:** Always cite retrieved passages only; verify offsets before display.
- **Abstention:** Prefer “Not found in corpus” over unsupported synthesis.